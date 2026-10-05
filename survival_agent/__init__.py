"""생존형 수익 에이전트 (개인용, 사람 승인형)."""
import os
from pathlib import Path

# 저장소 최상위 .env 의 키를 환경변수로 읽음(이미 설정된 값은 덮어쓰지 않음)
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _k, _, _v = _line.partition("=")
        if _k.strip() and not _k.strip().startswith("#") and _v.strip():
            os.environ.setdefault(_k.strip(), _v.strip())
