"""생존형 수익 에이전트 설정값.

금액·단가·환율은 매년(또는 수시로) 바뀌는 값이므로 data/config.json 으로 덮어쓸 수 있다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WORKSPACE_DIR = ROOT / "workspace"

# 모델 단가 (USD / 100만 토큰). 2026. 9. 기준 Anthropic 공시 단가 — 변경 시 config.json 으로 갱신
PRICES_USD_PER_MTOK = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00, "cache_read": 0.10},
}
WEB_SEARCH_USD_PER_CALL = 0.01  # 검색 1,000회당 $10


@dataclass(frozen=True)
class Tier:
    name: str            # 내부 키
    label: str           # 표시용 한글명
    min_ratio: float     # 잔고/시드 비율 하한
    model: str
    effort: str | None   # Haiku 4.5 는 effort 미지원 → None
    interval_hours: int  # 사이클 간격
    cycle_cap_krw: int   # 1 사이클 지출 상한
    max_turns: int       # 1 사이클 최대 API 호출 수


TIERS = [
    Tier("normal", "정상", 0.5, "claude-opus-5-5", "medium", 6, 1500, 12),
    Tier("low", "절약", 0.2, "claude-sonnet-5-5", "low", 12, 700, 8),
    Tier("critical", "위기", 0.0, "claude-haiku-4-5", None, 24, 300, 5),
]


@dataclass
class Settings:
    seed_krw: int = 50_000          # 개인 시드머니 기본값 (B안: 상한 약 5만 원)
    krw_per_usd: float = 1_400.0    # 환율 가정값 — 확인 필요
    prices: dict = field(default_factory=lambda: dict(PRICES_USD_PER_MTOK))
    web_search_usd: float = WEB_SEARCH_USD_PER_CALL

    @classmethod
    def load(cls) -> "Settings":
        path = DATA_DIR / "config.json"
        s = cls()
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            for k, v in raw.items():
                if hasattr(s, k):
                    setattr(s, k, v)
        return s

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "config.json").write_text(
            json.dumps(self.__dict__, ensure_ascii=False, indent=2), encoding="utf-8"
        )
