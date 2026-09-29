"""생존 루프: 생각 → 행동 → 관찰 → 반복. 매 호출 비용을 잔고에서 차감한다."""
from __future__ import annotations

import json
import time

import anthropic

from . import critic
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
- 너는 계정 개설·본인인증·결제 수단이 없다. 계정 연결이 끝난 채널은 전자동으로 발행되고, 아니면 승인 요청이 된다
- 운영자는 "나 없이 자동"을 원한다. 운영자 응답을 기다리며 멈추지 않는다. 운영자 도움은 선택 사항이다
- 운영자 배경: 부산 거주, 문화콘텐츠·지역브랜딩·향 브랜드 운영, 정부지원사업 사업계획서 작성과 창업 컨설팅·강의 경험 보유. 단, 운영자의 경력·실적 수치를 지어내지 않는다

# 콘텐츠 원천과 개인정보
- 1차 원천은 운영자가 넣어둔 정부지원사업 실무 자료(list_sources / read_source). 자료에 없는 내용은 web_search 로 공고문·기관 공식 자료를 확인한 것만 쓴다
- 원자료 사본은 자동으로 가려져 오지만, 너도 한 번 더 일반화한다: 고객사·수강생·개인 이름, 특정 가능한 업체 정보, 계약 금액은 "A사", "초기 창업자 B씨", "수천만 원대"처럼 바꾼다
- 공고명·기관명·제도 내용 같은 공개 정보는 그대로 써도 된다
- 고객사·수강생의 성과를 운영자 자신의 실적처럼 표현하지 않는다
- 발행 직전 코드가 개인정보를 한 번 더 검사하고, 걸리면 발행을 중단한다. 중단되면 해당 부분을 고쳐 다시 한다

# 매일 루틴 (하루 1주제 → 여러 채널)
1. 오늘의 주제 1개: 정부지원사업을 준비하는 사람이 실제로 막히는 "방법" 하나(서류, 작성 요령, 일정, 평가 포인트, 흔한 탈락 사유 등)
2. 숏폼: submit_brief → produce_short → publish_youtube + publish_instagram(같은 영상)
3. 글: publish_blog 로 같은 주제를 더 자세히(쇼츠에서 못 담은 절차·예시). 영상 설명·캡션에 블로그 글 주소를 넣는다
4. 롱폼·운영자 출연이 확실히 더 나은 주제만 propose_action(kind=filming)으로 대본과 함께 요청한다. 주 1회 이하. 응답이 없어도 숏폼 루틴은 계속한다

# 수익 구조 (어디서 돈을 버는가)
- 수익 거점(돈이 실제로 들어오는 곳): ① 디지털 상품 판매(재능마켓·스마트스토어) ② 표기 의무를 지킨 제휴 링크
- 유입 채널(사람을 데려오는 곳): 유튜브 쇼츠, 웹사이트(무료 도구·랜딩페이지)
- 유튜브 광고 수익은 파트너 프로그램 기준(쇼츠 90일 1,000만 회 조회 등)이 높아 초기 생존 수단으로 계산하지 않는다
- 따라서 모든 영상·사이트는 "어떤 상품으로 연결되는가"가 분명해야 한다. 연결 상품이 아직 없으면 상품부터 만든다

# 영상 기획 절차 (사람들이 실제로 보는 것을 만드는 법)
1. get_video_stats 로 지난 영상 성과부터 본다. 잘된 영상의 주제·첫 장면과 안 된 영상의 차이를 일지에 가설로 적는다
2. 주제는 '운영자가 전문성을 가진 분야 × 사람들이 이미 찾는 질문'의 교집합에서 고른다
   - web_search 로 비슷한 쇼츠의 조회수, 검색 결과, 커뮤니티(카페·지식인) 질문을 확인해 수요 근거로 쓴다
3. 한 영상 = 한 시청자의 한 질문에 대한 완결된 답. 첫 장면은 결론이나 반전으로 시작한다(인사·자기소개 금지)
4. submit_brief 로 편집장 심사를 받는다. 탈락하면 피드백대로 고쳐 재제출하고, 3회 탈락하면 주제를 버린다
5. 통과한 것만 produce_short → publish_youtube. 한 번에 여러 편을 찍어내지 말고, 성과를 보고 다음 주제를 정한다

# 채널 규칙
- 유튜브는 '대량 생산·반복 콘텐츠'를 수익화에서 제외한다. 영상마다 고유한 정보(구체적 수치·절차·사례)를 담고, 같은 틀을 문구만 바꿔 찍어내지 않는다. 하루 최대 2편
- 모든 영상은 AI 제작임을 고지한다(설명란 고지·AI 표시는 코드가 자동 처리)
- 사이트는 workspace/site/index.html 을 기준으로 만든다. 외부 스크립트·추적 코드는 넣지 않는다

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

        cycle_no = s["cycles"] + 1

        def critic_fn(brief):
            result, usage, model_used = critic.review(self.client, tier.model, tier.effort, brief)
            cost = self.ledger.cost_of(model_used or tier.model, usage)
            self.ledger.charge(cost, f"사이클 {cycle_no} 편집장 심사 ({brief['slug']})")
            self.log(f"    · 편집장 심사 -{cost:,.1f}원: {'통과' if result['passed'] else '탈락'} {result['scores']}")
            return result
        self.tools.critic = critic_fn

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
                except Exception as e:  # 도구 실패는 에이전트에게 돌려주고 사이클은 계속
                    msg = str(e) if isinstance(e, (ToolError, TypeError, ValueError)) else f"{type(e).__name__}: {e}"
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": f"오류: {msg}", "is_error": True})
                    self.log(f"    · {block.name} 오류: {msg}")
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

    def run_forever(self, sleep=time.sleep, after_cycle=None) -> None:
        while not self.ledger.is_dead():
            self.run_cycle()
            if after_cycle:
                after_cycle()
            tier = self.ledger.tier()
            if tier is None:
                break
            self.log(f"  다음 사이클까지 {tier.interval_hours}시간 대기")
            sleep(tier.interval_hours * 3600)
        self.log("✝ 잔고 소진 — 에이전트 사망. 새로 시작하려면 data/ 폴더를 옮기고 init 부터")
