"""API 키 없이 돌아가는 테스트: 가짜 HTTP 서버로 SDK 요청 형식과 생존 로직을 검증."""
import json

import anthropic
import httpx2
import pytest

from survival_agent.agent import SurvivalAgent
from survival_agent.approvals import Approvals
from survival_agent.config import Settings
from survival_agent.ledger import Ledger
from survival_agent.tools import ToolBox


def _msg(content, stop_reason, model="claude-opus-5-5", inp=10_000, out=2_000):
    return {"id": "msg_x", "type": "message", "role": "assistant", "model": model,
            "content": content, "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": inp, "output_tokens": out}}


class FakeServer:
    """요청 본문을 기록하고 준비된 응답을 순서대로 돌려준다."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append({"headers": dict(request.headers), "body": json.loads(request.content)})
        return httpx2.Response(200, json=self.responses.pop(0))


def _setup(tmp_path, responses, seed=50_000):
    settings = Settings(seed_krw=seed)
    ledger = Ledger(tmp_path / "data", settings)
    ledger.init(seed)
    approvals = Approvals(tmp_path / "data")
    box = ToolBox(ledger, approvals, tmp_path / "workspace")
    server = FakeServer(responses)
    client = anthropic.Anthropic(api_key="test", max_retries=0,
                                 http_client=httpx2.Client(transport=httpx2.MockTransport(server)))
    agent = SurvivalAgent(ledger, approvals, box, client=client, log=lambda *_: None)
    return agent, ledger, approvals, box, server


def test_cycle_runs_tools_and_charges(tmp_path):
    responses = [
        _msg([{"type": "tool_use", "id": "t1", "name": "write_file",
               "input": {"path": "products/a.md", "content": "상품 원고"}},
              {"type": "tool_use", "id": "t2", "name": "propose_action",
               "input": {"kind": "list_product", "title": "템플릿 등록", "channel": "크몽",
                         "detail": "products/a.md 를 9,900원에 등록", "expected_revenue_krw": 9900, "cost_krw": 0}}],
             "tool_use"),
        _msg([{"type": "tool_use", "id": "t3", "name": "write_journal", "input": {"entry": "템플릿 1종 제작"}}],
             "tool_use"),
        _msg([{"type": "text", "text": "사이클 종료"}], "end_turn"),
    ]
    agent, ledger, approvals, box, server = _setup(tmp_path, responses)
    assert agent.run_cycle() == "end_turn"

    # 요청 형식: 정상 단계 → Opus 5.5, effort, fallbacks, strict 도구, 웹검색
    body = server.requests[0]["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in server.requests[0]["headers"]["anthropic-beta"]
    assert all(t.get("strict") for t in body["tools"] if "input_schema" in t)
    assert any(t.get("type") == "web_search_20260209" for t in body["tools"])
    # 두 번째 요청에 tool_result 2개가 한 메시지로 들어감
    results = server.requests[1]["body"]["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]

    # 비용: 호출당 (10,000×$4 + 2,000×$20)/1M = $0.08 × 1,400원 = 112원, 3회
    assert ledger.state()["balance_krw"] == pytest.approx(50_000 - 3 * 112)
    assert (tmp_path / "workspace/products/a.md").read_text(encoding="utf-8") == "상품 원고"
    assert approvals.all()[0]["status"] == "pending"
    assert "템플릿 1종 제작" in box.journal_tail()
    assert ledger.state()["cycles"] == 1


def test_tier_downgrade_and_death(tmp_path):
    agent, ledger, *_ = _setup(tmp_path, [])
    assert ledger.tier().name == "normal"
    ledger.charge(30_000, "테스트")          # 잔고 20,000 = 40%
    assert ledger.tier().name == "low"
    ledger.charge(15_000, "테스트")          # 5,000 = 10%
    assert ledger.tier().name == "critical"
    ledger.add_revenue(20_000, "판매")        # 25,000 = 50% → 회복
    assert ledger.tier().name == "normal"
    ledger.charge(25_000, "테스트")
    assert ledger.is_dead() and ledger.tier() is None
    assert agent.run_cycle() == "dead"
    ledger.add_revenue(10_000, "사후 입금")   # 사망 후 부활 없음
    assert ledger.is_dead()


def test_critical_tier_uses_haiku_without_effort_or_fallbacks(tmp_path):
    responses = [_msg([{"type": "text", "text": "끝"}], "end_turn", model="claude-haiku-4-5")]
    agent, ledger, _, _, server = _setup(tmp_path, responses)
    ledger.charge(45_000, "테스트")
    agent.run_cycle()
    body = server.requests[0]["body"]
    assert body["model"] == "claude-haiku-4-5"
    assert "output_config" not in body and "fallbacks" not in body
    assert any(t.get("type") == "web_search_20250305" for t in body["tools"])


def test_cycle_cap_stops_spending(tmp_path):
    big = lambda i: _msg([{"type": "tool_use", "id": f"t{i}", "name": "get_status", "input": {}}],
                         "tool_use", inp=200_000, out=20_000)  # 호출당 약 1,680원
    agent, ledger, _, _, server = _setup(tmp_path, [big(i) for i in range(5)])
    assert agent.run_cycle() == "cycle_cap"
    assert len(server.requests) == 1


def test_workspace_escape_blocked(tmp_path):
    responses = [
        _msg([{"type": "tool_use", "id": "t1", "name": "write_file",
               "input": {"path": "../data/state.json", "content": "{}"}}], "tool_use"),
        _msg([{"type": "text", "text": "끝"}], "end_turn"),
    ]
    agent, ledger, _, _, server = _setup(tmp_path, responses)
    agent.run_cycle()
    result = server.requests[1]["body"]["messages"][-1]["content"][0]
    assert result["is_error"] is True
    assert ledger.state()["seed_krw"] == 50_000  # 장부 훼손 없음


def test_refusal_ends_cycle(tmp_path):
    agent, *_ = _setup(tmp_path, [_msg([], "refusal")])
    assert agent.run_cycle() == "refusal"
