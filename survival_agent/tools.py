"""에이전트가 쓸 수 있는 도구. 파일은 workspace/ 안에서만 읽고 쓴다."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .approvals import KINDS, Approvals
from .config import WORKSPACE_DIR
from .ledger import Ledger

MAX_FILE_BYTES = 200_000
JOURNAL = "생존일지.md"


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


TOOL_SCHEMAS = [
    {"name": "get_status",
     "description": "현재 잔고·생존 단계·누적 수익/비용·승인 대기열 상태(사람이 승인/거절/실행한 결과와 메모 포함)를 조회한다.",
     "input_schema": _obj({}, [])},
    {"name": "list_files",
     "description": "workspace 안의 파일 목록을 본다. 이전 사이클에서 만든 상품·원고·랜딩페이지를 확인할 때 쓴다.",
     "input_schema": _obj({"subdir": {"type": "string", "description": "workspace 기준 하위 폴더. 전체는 빈 문자열"}}, ["subdir"])},
    {"name": "read_file",
     "description": "workspace 안의 파일 하나를 읽는다.",
     "input_schema": _obj({"path": {"type": "string"}}, ["path"])},
    {"name": "write_file",
     "description": "workspace 안에 파일을 만들거나 덮어쓴다. 판매할 디지털 상품(템플릿·전자책 원고), 상품 설명, 랜딩페이지 HTML, 블로그 원고 등을 만든다. 파일을 만드는 것만으로는 외부에 공개되지 않는다.",
     "input_schema": _obj({"path": {"type": "string", "description": "예: products/사업계획서_템플릿/본문.md"},
                           "content": {"type": "string"}}, ["path", "content"])},
    {"name": "propose_action",
     "description": "외부 세계에 영향을 주는 행동(게시·상품등록·발신·광고비·구매·계정개설)을 사람에게 승인 요청한다. 사람이 승인하면 사람이 직접 실행하고 결과를 메모로 남긴다. 결과는 다음 사이클의 get_status 에서 확인한다.",
     "input_schema": _obj({
         "kind": {"type": "string", "enum": KINDS},
         "title": {"type": "string", "description": "한 줄 요약"},
         "channel": {"type": "string", "description": "실행 채널. 예: 크몽, 네이버 블로그, 스마트스토어, 인스타그램"},
         "detail": {"type": "string", "description": "사람이 그대로 실행할 수 있게: 올릴 파일 경로, 가격, 게시 문구, 단계별 절차"},
         "expected_revenue_krw": {"type": "integer", "description": "기대 수익(원). 근거 없으면 0"},
         "cost_krw": {"type": "integer", "description": "실행에 드는 돈(원). 없으면 0"},
     }, ["kind", "title", "channel", "detail", "expected_revenue_krw", "cost_krw"])},
    {"name": "write_journal",
     "description": "생존일지에 이번 사이클의 판단·가설·다음 계획을 기록한다. 다음 사이클의 나는 이 일지만 보고 이어서 일한다. 사이클 끝에 반드시 한 번 쓴다.",
     "input_schema": _obj({"entry": {"type": "string"}}, ["entry"])},
]
# 스키마 보장 (forced tool_choice 대신 strict 사용)
for _t in TOOL_SCHEMAS:
    _t["strict"] = True


class ToolError(Exception):
    pass


class ToolBox:
    def __init__(self, ledger: Ledger, approvals: Approvals, workspace: Path = WORKSPACE_DIR):
        self.ledger = ledger
        self.approvals = approvals
        self.ws = workspace.resolve()
        self.ws.mkdir(parents=True, exist_ok=True)

    def _safe(self, rel: str) -> Path:
        p = (self.ws / rel).resolve()
        if p != self.ws and self.ws not in p.parents:
            raise ToolError("workspace 밖 경로는 사용할 수 없음")
        return p

    def run(self, name: str, args: dict) -> str:
        fn = getattr(self, f"t_{name}", None)
        if fn is None:
            raise ToolError(f"알 수 없는 도구: {name}")
        return fn(**args)

    # ---- 도구 구현 ----
    def t_get_status(self) -> str:
        s = self.ledger.state()
        tier = self.ledger.tier()
        revenues = self.ledger.entries("revenue")[-10:]
        return json.dumps({
            "잔고_원": round(s["balance_krw"]), "시드_원": s["seed_krw"],
            "잔고비율": round(s["balance_krw"] / s["seed_krw"], 3),
            "생존단계": tier.label if tier else "사망",
            "누적비용_원": round(s["total_cost_krw"]), "누적수익_원": round(s["total_revenue_krw"]),
            "사이클수": s["cycles"], "최근수익": revenues,
            "승인대기열": self.approvals.all()[-20:],
        }, ensure_ascii=False, indent=1)

    def t_list_files(self, subdir: str) -> str:
        base = self._safe(subdir or ".")
        if not base.exists():
            return "(없음)"
        files = [str(p.relative_to(self.ws)) for p in sorted(base.rglob("*")) if p.is_file()]
        return "\n".join(files[:300]) or "(비어 있음)"

    def t_read_file(self, path: str) -> str:
        p = self._safe(path)
        if not p.is_file():
            raise ToolError(f"파일 없음: {path}")
        return p.read_text(encoding="utf-8")[:MAX_FILE_BYTES]

    def t_write_file(self, path: str, content: str) -> str:
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ToolError("파일이 너무 큼(200KB 초과). 나눠서 저장")
        p = self._safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"저장됨: {path} ({len(content)}자)"

    def t_propose_action(self, kind, title, channel, detail, expected_revenue_krw, cost_krw) -> str:
        if kind not in KINDS:
            raise ToolError(f"kind 는 {KINDS} 중 하나")
        item = self.approvals.propose(kind, title, channel, detail, expected_revenue_krw, cost_krw)
        return f"승인 요청 #{item['id']} 등록. 사람이 확인 후 실행함. 결과는 다음 사이클 get_status 에서 확인"

    def t_write_journal(self, entry: str) -> str:
        p = self.ws / JOURNAL
        stamp = datetime.now().strftime("%Y. %m. %d. %H:%M")
        with p.open("a", encoding="utf-8") as f:
            f.write(f"\n\n## {stamp} (사이클 {self.ledger.state()['cycles'] + 1})\n\n{entry.strip()}\n")
        return "일지 기록됨"

    def journal_tail(self, chars: int = 6000) -> str:
        p = self.ws / JOURNAL
        if not p.exists():
            return "(첫 사이클 — 일지 없음)"
        return p.read_text(encoding="utf-8")[-chars:]
