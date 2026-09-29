"""인스타그램 릴스 발행 (Instagram Graph API, 비즈니스·크리에이터 계정).

준비: 인스타 계정을 프로페셔널(비즈니스/크리에이터)로 전환 → 페이스북 페이지 연결 → Meta 개발자 앱 생성
     → instagram_content_publish 권한 토큰 발급 → 환경변수 IG_ACCESS_TOKEN, data/config.json 의 ig_user_id
※ 릴스는 공개 URL 의 mp4 만 받으므로, 영상을 먼저 GitHub Pages 사이트(media/)에 올린 뒤 그 주소를 넘긴다
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request


def _call(method: str, url: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def wait_until_public(url: str, timeout_s: int = 600, interval_s: int = 15, sleep=time.sleep) -> None:
    """GitHub Pages 반영(보통 1∼2분)까지 대기."""
    waited = 0
    while True:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
                if r.status == 200:
                    return
        except Exception:
            pass
        if waited >= timeout_s:
            raise RuntimeError(f"영상 공개 주소가 열리지 않음: {url}")
        sleep(interval_s)
        waited += interval_s


def publish_reel(base: str, ig_user_id: str, token: str, video_url: str, caption: str,
                 call=_call, sleep=time.sleep, timeout_s: int = 600) -> str:
    c = call("POST", f"{base}/{ig_user_id}/media",
             {"media_type": "REELS", "video_url": video_url, "caption": caption[:2200],
              "share_to_feed": "true", "access_token": token})
    cid = c["id"]
    waited = 0
    while True:
        st = call("GET", f"{base}/{cid}", {"fields": "status_code", "access_token": token})["status_code"]
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED") or waited >= timeout_s:
            raise RuntimeError(f"릴스 처리 실패: {st}")
        sleep(10)
        waited += 10
    return call("POST", f"{base}/{ig_user_id}/media_publish", {"creation_id": cid, "access_token": token})["id"]
