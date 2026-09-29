"""잔고 장부: 시드 + 수익 - API 비용. 잔고 0 이하 = 사망."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR, TIERS, Settings, Tier


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Ledger:
    def __init__(self, data_dir: Path = DATA_DIR, settings: Settings | None = None):
        self.dir = data_dir
        self.settings = settings or Settings.load()
        self.state_path = self.dir / "state.json"
        self.log_path = self.dir / "ledger.jsonl"

    # ---- 상태 ----
    def exists(self) -> bool:
        return self.state_path.exists()

    def init(self, seed_krw: int) -> None:
        if self.exists():
            raise RuntimeError("이미 초기화됨. 새로 시작하려면 data/ 폴더를 다른 이름으로 옮긴 뒤 실행")
        self.dir.mkdir(parents=True, exist_ok=True)
        state = {"seed_krw": seed_krw, "balance_krw": float(seed_krw),
                 "born_at": _now(), "died_at": None, "cycles": 0,
                 "total_cost_krw": 0.0, "total_revenue_krw": 0.0, "last_cycle_at": None}
        self._write(state)
        self._append({"type": "seed", "krw": seed_krw, "memo": "시드 입금"})

    def state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _write(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _append(self, entry: dict) -> None:
        entry = {"at": _now(), **entry}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def entries(self, type_: str | None = None) -> list[dict]:
        if not self.log_path.exists():
            return []
        rows = [json.loads(l) for l in self.log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        return [r for r in rows if type_ is None or r["type"] == type_]

    # ---- 돈 ----
    def cost_of(self, model: str, usage) -> float:
        """response.usage → 원화 비용."""
        p = self.settings.prices.get(model) or self.settings.prices["claude-opus-5-5"]
        g = lambda name: getattr(usage, name, None) or 0
        usd = (g("input_tokens") * p["input"]
               + g("cache_creation_input_tokens") * p["input"] * 1.25
               + g("cache_read_input_tokens") * p["cache_read"]
               + g("output_tokens") * p["output"]) / 1_000_000
        stu = getattr(usage, "server_tool_use", None)
        if stu is not None:
            usd += (getattr(stu, "web_search_requests", 0) or 0) * self.settings.web_search_usd
        return usd * self.settings.krw_per_usd

    def charge(self, krw: float, memo: str) -> dict:
        s = self.state()
        s["balance_krw"] -= krw
        s["total_cost_krw"] += krw
        if s["balance_krw"] <= 0 and not s["died_at"]:
            s["died_at"] = _now()
        self._write(s)
        self._append({"type": "cost", "krw": round(krw, 2), "memo": memo})
        return s

    def add_revenue(self, krw: int, memo: str) -> dict:
        """사람이 실제 입금 확인 후 기록. 사망 상태에서는 부활하지 않음(새 시드로 재시작)."""
        s = self.state()
        s["balance_krw"] += krw
        s["total_revenue_krw"] += krw
        self._write(s)
        self._append({"type": "revenue", "krw": krw, "memo": memo})
        return s

    def mark_cycle(self) -> None:
        s = self.state()
        s["cycles"] += 1
        s["last_cycle_at"] = _now()
        self._write(s)

    # ---- 생존 단계 ----
    def is_dead(self) -> bool:
        s = self.state()
        return bool(s["died_at"]) or s["balance_krw"] <= 0

    def tier(self) -> Tier | None:
        if self.is_dead():
            return None
        s = self.state()
        ratio = s["balance_krw"] / s["seed_krw"]
        for t in TIERS:
            if ratio >= t.min_ratio:
                return t
        return TIERS[-1]
