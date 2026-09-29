"""승인 대기열: 에이전트는 외부 행동을 '제안'만 하고, 실행은 사람이 한다."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR

KINDS = ["publish", "list_product", "send_message", "ad_spend", "purchase", "account_setup", "filming", "other"]
KIND_LABEL = {
    "publish": "게시(블로그·SNS)", "list_product": "상품 등록", "send_message": "외부 발신",
    "ad_spend": "광고비 지출", "purchase": "구매·결제", "account_setup": "계정 개설", "filming": "운영자 촬영 요청(선택)", "other": "기타",
}


class Approvals:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.path = data_dir / "approvals.json"

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def all(self) -> list[dict]:
        return self._load()

    def get(self, item_id: int) -> dict:
        for it in self._load():
            if it["id"] == item_id:
                return it
        raise KeyError(f"승인 항목 #{item_id} 없음")

    def propose(self, kind: str, title: str, channel: str, detail: str,
                expected_revenue_krw: int, cost_krw: int, payload: dict | None = None) -> dict:
        """payload 가 있으면 `execute <id>` 한 줄로 사람이 바로 실행할 수 있다."""
        items = self._load()
        item = {"id": len(items) + 1, "kind": kind, "title": title, "channel": channel,
                "detail": detail, "expected_revenue_krw": expected_revenue_krw, "cost_krw": cost_krw,
                "status": "pending", "note": "", "payload": payload,
                "created_at": datetime.now().isoformat(timespec="seconds")}
        items.append(item)
        self._save(items)
        return item

    def set_status(self, item_id: int, status: str, note: str = "") -> dict:
        items = self._load()
        for it in items:
            if it["id"] == item_id:
                it["status"] = status
                if note:
                    it["note"] = note
                it["updated_at"] = datetime.now().isoformat(timespec="seconds")
                self._save(items)
                return it
        raise KeyError(f"승인 항목 #{item_id} 없음")
