"""유튜브 업로드 (YouTube Data API v3, OAuth).

최초 1회: Google Cloud 콘솔에서 OAuth 클라이언트(데스크톱 앱) 생성 → data/youtube_client_secret.json 저장
         → `python -m survival_agent youtube-auth` 로 브라우저 로그인
※ 감사(audit)를 통과하지 않은 API 프로젝트로 올린 영상은 공개 설정과 무관하게 '비공개'로 잠김
"""
from __future__ import annotations

from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]  # 성과 조회용


def authorize(data_dir: Path) -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    secret = data_dir / "youtube_client_secret.json"
    if not secret.exists():
        raise FileNotFoundError(f"{secret} 없음. README 5장 참고")
    creds = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES).run_local_server(port=0)
    (data_dir / "youtube_token.json").write_text(creds.to_json(), encoding="utf-8")


def is_ready(data_dir: Path) -> bool:
    return (data_dir / "youtube_token.json").exists()


def build_service(data_dir: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token = data_dir / "youtube_token.json"
    creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        token.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def upload(service, video_path: str, title: str, description: str, tags: list[str],
           privacy: str, category_id: str) -> str:
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {"title": title[:100], "description": description[:4900],
                    "tags": tags[:15], "categoryId": category_id, "defaultLanguage": "ko"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
                   "containsSyntheticMedia": True},   # AI 제작 공식 표시
    }
    req = service.videos().insert(part="snippet,status", body=body,
                                  media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return f"https://youtube.com/shorts/{resp['id']}"


def stats(service, video_ids: list[str]) -> dict:
    out = {}
    for i in range(0, len(video_ids), 50):
        resp = service.videos().list(part="statistics,status", id=",".join(video_ids[i:i + 50])).execute()
        for it in resp.get("items", []):
            st = it.get("statistics", {})
            out[it["id"]] = {"조회수": int(st.get("viewCount", 0)), "좋아요": int(st.get("likeCount", 0)),
                             "댓글": int(st.get("commentCount", 0)),
                             "공개상태": it.get("status", {}).get("privacyStatus", "")}
    return out
