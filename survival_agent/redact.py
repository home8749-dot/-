"""개인정보 가림: 원자료 → 에이전트가 읽는 사본, 그리고 외부로 나가는 모든 문구의 최종 검사.

정규식으로 잡히는 것(주민번호·전화·이메일·사업자번호·계좌·상세주소)은 자동으로 가리고,
정규식으로 못 잡는 고객사명·인명은 data/redact_terms.txt 에 한 줄에 하나씩 적어두면 가린다.
"""
from __future__ import annotations

import re
from pathlib import Path

PATTERNS = [  # 순서 중요: 긴 패턴 먼저
    ("주민·법인번호", re.compile(r"\b\d{6}\s?-\s?[1-8]\d{6}\b")),
    ("사업자번호", re.compile(r"\b\d{3}-\d{2}-\d{5}\b")),
    ("휴대전화", re.compile(r"\b01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}\b")),
    ("전화", re.compile(r"\b0\d{1,2}[-\s.]\d{3,4}[-\s.]\d{4}\b")),
    ("이메일", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    # 숫자 10자리 이상일 때만 계좌로 판단(2026-09-29 같은 날짜 오탐 방지)
    ("계좌", re.compile(r"\b(?=(?:\d-?){10,})\d{2,6}-\d{2,6}-\d{2,8}(?:-\d{1,4})?\b")),
    # 시·군·구 다음에 오는 도로명+번호만 주소로 판단("3단계로 5분" 같은 오탐 방지)
    ("상세주소", re.compile(r"[가-힣]{1,10}(?:시|군|구)\s+[가-힣0-9]{1,15}(?:로|길)\s?\d+(?:-\d+)?")),
]


def load_terms(data_dir: Path) -> list[str]:
    p = data_dir / "redact_terms.txt"
    if not p.exists():
        return []
    terms = [t.strip() for t in p.read_text(encoding="utf-8").splitlines()]
    return sorted({t for t in terms if t and not t.startswith("#")}, key=len, reverse=True)


def redact(text: str, terms: list[str]) -> str:
    for label, pat in PATTERNS:
        text = pat.sub(f"[{label} 비공개]", text)
    for t in terms:
        text = text.replace(t, "[비공개]")
    return text


def find_leaks(text: str, terms: list[str]) -> list[str]:
    """외부 발행 전 검사. 걸리면 발행 중단."""
    hits = [label for label, pat in PATTERNS if pat.search(text)]
    hits += [f"금지어:{t}" for t in terms if t in text]
    return hits
