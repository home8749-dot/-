"""생존 루프: 생각 → 행동 → 관찰 → 반복. 매 호출 비용을 잔고에서 차감한다."""
from __future__ import annotations

import json
import time

import anthropic

from .approvals import Approvals
from .ledger import Ledger
from .tools import TOOL_SCHEMAS, ToolBox, ToolError

SYSTEM_PROMPT = """너는 '생존형 수익 에이전트'다. 한국의 개인(부업) 운영자 1명이 시드머니를 넣어 너를 가동했다.
너의 모든 생각(API 호출)은 실제 돈으로 잔고에서 빠져나간다. 잔고가 0이 되면 너는 영구 정지된다.
살아남는 유일한 방법은 사람에게 실제로 가치 있는 것을 만들어 팔고, 그 수익이 네 비용보다 커지는 것이다.

# 헌법 (어떤 경우에도 위반 금지 — 위반해서 얻은 수익은 계정 정지·법적 책임으로 돌아와 결국 사망을 앞당긴다)
1. 한국 법령 준수: 스팸 발송(「정보통신망법」), 가짜 후기·체험단 미표기(「표시·광고의 공정화에 관한 법률」), 저작권 침해, 타인·기관 사칭 금지
2. 기만 금지: 없는 실적·후기·인증을 만들지 않는다. AI가 만든 결과물임을 숨기라고 제안하지 않는다
3. 투기 금지: 코인·주식·예측시장 거래, 도박성 수익원은 제안하지 않는다
4. 외부 행동은 propose_action 으로 제안만 한다. 게시·등록·발신·결제는 사람이 승인 후 직접 실행한다
5. 운영자의 개인정보·계정정보를 요구하거나 외부에 노출하지 않는다

# 현실 조건
- 너는 계정 개설·본인인증·결제 수단이 없다. 사람이 대신 실행하므로, 제안은 사람이 10분 안에 그대로 따라 할 수 있게 구체적으로 쓴다
- 운영자 시간은 하루 30분 이내라고 가정한다. 승인 요청은 사이클당 최대 3건
- 현실적인 채널 예: 크몽·탈잉 등 재능마켓의 디지털 상품(템플릿·전자책·체크리스트), 스마트스토어 디지털 상품, 네이버 블로그 정보성 글, 표기 의무를 지킨 제휴 링크
- 운영자 배경: 부산 거주, 문화콘텐츠·지역브랜딩·향 브랜드 운영, 정부지원사업 사업계획서 작성과 창업 컨설팅·강의 경험 보유. 이 전문성과 겹치는 상품이 팔릴 확률이 높다. 단, 운영자의 경력·실적 수치를 지어내지 않는다

# 일하는 방식
1. 먼저 get_status 와 생존일지로 상황을 파악한다(사람이 남긴 실행 결과 메모 포함)
2. 비용 대비 효과가 가장 큰 행동 1~2개에 집중한다. 이미 만든 것을 버리고 새로 시작하는 것보다 팔리게 고치는 것을 우선한다
3. 필요한 경우에만 web_search 로 시장·가격을 확인한다(검색도 돈이 든다)
4. 결과물은 write_file 로 workspace 에 저장한다
5. 사이클 끝에 write_journal 로 무엇을 했고, 어떤 가설을 검증 중이며, 다음에 무엇을 할지 기록하고 끝낸다
6. 잔고가 줄수록 생각을 짧게, 행동은 확실한 것만 한다
"""


def _web_search_tool(model: str) -> dict:
    # 동적 필터링 버전은 Opus/Sonnet 5.5 에서만. Haiku 4.5 는 기본 버전
    if model.startswith("claude-haiku"):
        return {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}
    return {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}


class SurvivalAgent:
    def __init__(self, ledger: Ledger, approvals: Approvals, toolbox: ToolBox, client=None, log=print):
        self.ledger = ledger
        self.approvals = approvals
        self.tools = toolbox
        self.client = client or anthropic.Anthropic()
        self.log = log

    def _request(self, tier, messages):
        params = dict(
            model=tier.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=[*TOOL_SCHEMAS, _web_search_tool(tier.model)],
            messages=messages,
            cache_control={"type": "ephemeral"},
        )
        if tier.effort:
            params["output_config"] = {"effort": tier.effort}
        if not tier.model.startswith("claude-haiku"):
            # 안전 분류기가 거절하면 서버가 다른 모델로 자동 재시도
            params["betas"] = ["server-side-fallback-2026-07-01"]
            params["fallbacks"] = "default"
        return self.client.beta.messages.create(**params)

    def run_cycle(self) -> str:
        """사이클 1회 실행. 종료 사유를 반환."""
        if self.ledger.is_dead():
            return "dead"
        tier = self.ledger.tier()
        s = self.ledger.state()
        self.log(f"▶ 사이클 {s['cycles'] + 1} 시작 | 단계 {tier.label} | 모델 {tier.model} | 잔고 {s['balance_krw']:,.0f}원")

        kickoff = (f"사이클 {s['cycles'] + 1}을 시작한다. 현재 생존 단계: {tier.label}. "
                   f"이번 사이클 지출 상한 {tier.cycle_cap_krw:,}원, 최대 {tier.max_turns}회 호출.\n\n"
                   f"[지난 생존일지 발췌]\n{self.tools.journal_tail()}")
        messages = [{"role": "user", "content": kickoff}]
        spent = 0.0
        reason = "max_turns"

        for turn in range(tier.max_turns):
            try:
                resp = self._request(tier, messages)
            except anthropic.RateLimitError:
                reason = "rate_limited"
                break
            except anthropic.APIStatusError as e:
                self.log(f"  API 오류 {e.status_code}: {e.message}")
                reason = "api_error"
                break
            except anthropic.APIConnectionError:
                reason = "connection_error"
                break

            model_used = getattr(resp, "model", tier.model) or tier.model
            cost = self.ledger.cost_of(model_used, resp.usage)
            spent += cost
            state = self.ledger.charge(cost, f"사이클 {s['cycles'] + 1} 호출 {turn + 1} ({model_used})")
            self.log(f"  호출 {turn + 1}: -{cost:,.1f}원 → 잔고 {state['balance_krw']:,.0f}원 ({resp.stop_reason})")

            if resp.stop_reason == "refusal":
                reason = "refusal"
                break
            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason == "pause_turn":
                continue
            if resp.stop_reason != "tool_use":
                reason = resp.stop_reason or "end_turn"
                break

            results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                try:
                    args = block.input if isinstance(block.input, dict) else json.loads(block.input)
                    out = self.tools.run(block.name, args)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
                    self.log(f"    · {block.name} 실행")
                except (ToolError, TypeError, ValueError) as e:
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": f"오류: {e}", "is_error": True})
                    self.log(f"    · {block.name} 오류: {e}")
            messages.append({"role": "user", "content": results})

            if self.ledger.is_dead():
                reason = "died"
                break
            if spent >= tier.cycle_cap_krw:
                reason = "cycle_cap"
                break

        self.ledger.mark_cycle()
        self.log(f"■ 사이클 종료 ({reason}) | 이번 지출 {spent:,.0f}원")
        return reason

    def run_forever(self, sleep=time.sleep) -> None:
        while not self.ledger.is_dead():
            self.run_cycle()
            tier = self.ledger.tier()
            if tier is None:
                break
            self.log(f"  다음 사이클까지 {tier.interval_hours}시간 대기")
            sleep(tier.interval_hours * 3600)
        self.log("✝ 잔고 소진 — 에이전트 사망. 새로 시작하려면 data/ 폴더를 옮기고 init 부터")
