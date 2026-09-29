"""에이전트가 쓸 수 있는 도구. 파일은 workspace/ 안에서만 읽고 쓴다."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .approvals import KINDS, Approvals
from .config import WORKSPACE_DIR
from .ledger import Ledger

MAX_FILE_BYTES = 200_000
MAX_REVIEWS = 3
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
    {"name": "submit_brief",
     "description": "영상 기획안(대본 포함)을 편집장에게 심사받는다. 통과한 기획안만 produce_short 로 만들 수 있다. 같은 slug 로 최대 3회 제출 가능. 수요 근거는 web_search 로 확인한 사실(비슷한 영상 조회수, 검색 결과, 커뮤니티 질문)을 출처와 함께 적는다. 첫 장면(caption)이 첫 3초 훅이다. 제목 카드는 자동으로 붙지 않는다.",
     "input_schema": _obj({
         "slug": {"type": "string", "description": "파일명용 영문·숫자·하이픈. 예: gov-grant-docs-01"},
         "title": {"type": "string"},
         "target_viewer": {"type": "string", "description": "구체적인 시청자 한 명. 예: 올해 처음 예비창업패키지 쓰는 30대 퇴사자"},
         "viewer_question": {"type": "string", "description": "그 사람이 검색창에 칠 질문 한 개"},
         "demand_evidence": {"type": "string", "description": "수요 근거와 출처"},
         "unique_angle": {"type": "string", "description": "다른 영상에 없는 이 영상만의 정보·관점"},
         "linked_product": {"type": "string", "description": "연결할 상품·사이트와 넘어갈 이유"},
         "scenes": {"type": "array", "items": _obj({
             "caption": {"type": "string", "description": "화면 문구(40자 이내 권장)"},
             "narration": {"type": "string", "description": "읽을 문장"}}, ["caption", "narration"])},
     }, ["slug", "title", "target_viewer", "viewer_question", "demand_evidence", "unique_angle",
         "linked_product", "scenes"])},
    {"name": "produce_short",
     "description": "편집장 심사를 통과한 기획안(slug)으로 세로형 쇼츠(최대 60초)를 만든다. 음성 합성 비용은 잔고에서 차감된다.",
     "input_schema": _obj({"slug": {"type": "string"}}, ["slug"])},
    {"name": "get_video_stats",
     "description": "지금까지 올린 유튜브 영상별 조회수·좋아요·댓글 수를 본다. 다음 기획 주제를 고를 때 가장 먼저 참고한다.",
     "input_schema": _obj({}, [])},
    {"name": "publish_youtube",
     "description": "workspace 의 영상을 유튜브에 올린다. 전자동이 켜져 있으면 즉시 업로드, 꺼져 있으면 사람 승인 요청이 된다. 설명란 끝에 AI 제작 고지가 자동으로 붙는다.",
     "input_schema": _obj({
         "video_path": {"type": "string", "description": "예: videos/gov-grant-checklist-01.mp4"},
         "title": {"type": "string"},
         "description": {"type": "string", "description": "상품·사이트 링크 포함. 제휴 링크가 있으면 제휴 사실을 첫 줄에 표기"},
         "tags": {"type": "array", "items": {"type": "string"}},
         "expected_revenue_krw": {"type": "integer"},
     }, ["video_path", "title", "description", "tags", "expected_revenue_krw"])},
    {"name": "list_sources",
     "description": "운영자가 넣어둔 원자료(정부지원사업 실무 자료) 목록을 본다. 콘텐츠의 1차 원천이다.",
     "input_schema": _obj({}, [])},
    {"name": "read_source",
     "description": "원자료 하나를 읽는다. 주민번호·전화·이메일·사업자번호·계좌·주소·지정 금지어는 자동으로 [비공개] 처리된 사본이 온다.",
     "input_schema": _obj({"path": {"type": "string"}}, ["path"])},
    {"name": "publish_instagram",
     "description": "만든 쇼츠 영상을 인스타그램 릴스로 발행한다(유튜브와 같은 영상 재사용). 캡션 끝에 AI 고지가 자동으로 붙는다.",
     "input_schema": _obj({"video_path": {"type": "string"},
                           "caption": {"type": "string", "description": "첫 줄이 핵심. 해시태그 5개 이내"}},
                          ["video_path", "caption"])},
    {"name": "publish_blog",
     "description": "같은 주제를 글로 풀어 자체 블로그(GitHub Pages)에 게시하고, 네이버 블로그 복사용 초안도 만든다. 본문은 마크다운(## 소제목, - 목록, 1. 번호, **굵게**, [링크](https://...)).",
     "input_schema": _obj({"slug": {"type": "string"}, "title": {"type": "string"},
                           "summary": {"type": "string", "description": "검색 결과에 보일 한두 문장"},
                           "body_markdown": {"type": "string"}},
                          ["slug", "title", "summary", "body_markdown"])},
    {"name": "deploy_site",
     "description": "workspace/site 폴더(index.html 필수)를 운영자의 GitHub Pages 에 배포한다. 무료 도구·랜딩페이지·상품 소개용. 전자동이 꺼져 있으면 승인 요청이 된다.",
     "input_schema": _obj({"message": {"type": "string", "description": "배포 내용 한 줄 요약"}}, ["message"])},
]
# 스키마 보장 (forced tool_choice 대신 strict 사용)
for _t in TOOL_SCHEMAS:
    _t["strict"] = True


class ToolError(Exception):
    pass


class ToolBox:
    def __init__(self, ledger: Ledger, approvals: Approvals, workspace: Path = WORKSPACE_DIR, channels=None):
        self.ledger = ledger
        self.approvals = approvals
        self.ws = workspace.resolve()
        self.ws.mkdir(parents=True, exist_ok=True)
        self.channels = channels
        self.critic = None  # 에이전트가 사이클마다 연결: brief dict → {"passed","scores","feedback"}

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

    def _need_channels(self):
        if self.channels is None:
            raise ToolError("채널 모듈이 연결되지 않음")
        return self.channels

    def _brief_path(self, slug: str) -> Path:
        if not slug or not slug.replace("-", "").isalnum() or not slug.isascii():
            raise ToolError("slug 는 영문·숫자·하이픈만")
        return self.ws / "briefs" / f"{slug}.json"

    def t_submit_brief(self, slug, **brief) -> str:
        path = self._brief_path(slug)
        if not 3 <= len(brief["scenes"]) <= 10:
            raise ToolError("장면은 3∼10개")
        if self.critic is None:
            raise ToolError("편집장 심사기가 연결되지 않음")
        record = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"reviews": []}
        if record.get("passed"):
            return "이미 통과한 기획안. produce_short 로 제작"
        if len(record["reviews"]) >= MAX_REVIEWS:
            raise ToolError(f"이 slug 는 심사 {MAX_REVIEWS}회 소진. 주제를 바꿔 새 slug 로 제출")
        result = self.critic({"slug": slug, **brief})
        record.update({"slug": slug, **brief, "passed": result["passed"]})
        record["reviews"].append({"scores": result["scores"], "feedback": result["feedback"]})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        head = "통과 → produce_short 로 제작 가능" if result["passed"] else \
            f"탈락 ({len(record['reviews'])}/{MAX_REVIEWS}회). 피드백 반영해 같은 slug 로 재제출"
        return json.dumps({"결과": head, "점수": result["scores"], "피드백": result["feedback"]},
                          ensure_ascii=False)

    def t_produce_short(self, slug) -> str:
        path = self._brief_path(slug)
        if not path.exists() or not json.loads(path.read_text(encoding="utf-8")).get("passed"):
            raise ToolError("심사를 통과한 기획안이 없음. submit_brief 먼저")
        brief = json.loads(path.read_text(encoding="utf-8"))
        try:
            return self._need_channels().produce_short(slug, brief["scenes"])
        except (ValueError, RuntimeError, FileNotFoundError) as e:
            raise ToolError(str(e))

    def t_get_video_stats(self) -> str:
        try:
            return json.dumps(self._need_channels().video_stats(), ensure_ascii=False, indent=1)
        except (ValueError, RuntimeError) as e:
            raise ToolError(str(e))

    def t_publish_youtube(self, video_path, title, description, tags, expected_revenue_krw) -> str:
        try:
            return self._need_channels().publish_youtube(video_path, title, description, tags, expected_revenue_krw)
        except (ValueError, RuntimeError) as e:
            raise ToolError(str(e))

    def t_list_sources(self) -> str:
        return "\n".join(self._need_channels().list_sources()) or "(원자료 없음 — 운영자가 data/sources 에 .md/.txt 를 넣어야 함)"

    def t_read_source(self, path) -> str:
        try:
            return self._need_channels().read_source(path)
        except ValueError as e:
            raise ToolError(str(e))

    def t_publish_instagram(self, video_path, caption) -> str:
        try:
            return self._need_channels().publish_instagram(video_path, caption)
        except (ValueError, RuntimeError) as e:
            raise ToolError(str(e))

    def t_publish_blog(self, slug, title, summary, body_markdown) -> str:
        self._brief_path(slug)  # slug 형식 검사
        try:
            return self._need_channels().publish_blog(slug, title, summary, body_markdown)
        except (ValueError, RuntimeError) as e:
            raise ToolError(str(e))

    def t_deploy_site(self, message) -> str:
        try:
            return self._need_channels().deploy_site(message)
        except (ValueError, RuntimeError) as e:
            raise ToolError(str(e))

    def journal_tail(self, chars: int = 6000) -> str:
        p = self.ws / JOURNAL
        if not p.exists():
            return "(첫 사이클 — 일지 없음)"
        return p.read_text(encoding="utf-8")[-chars:]
