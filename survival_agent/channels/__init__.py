"""채널 실행기: 전자동(autopilot) 이면 바로 실행, 아니면 승인 대기열에 '실행 준비된 제안'으로 올린다.

외부로 나가는 모든 문구는 발행 직전에 개인정보 검사를 한 번 더 거친다(걸리면 중단).
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import date, datetime
from pathlib import Path

from .. import redact
from ..approvals import Approvals
from ..config import Settings
from ..ledger import Ledger
from . import blog, instagram, shorts, site, youtube

AI_NOTICE = "※ 이 콘텐츠는 AI로 기획·제작되었습니다."
SOURCE_EXT = {".md", ".txt"}


class Channels:
    def __init__(self, settings: Settings, ledger: Ledger, approvals: Approvals,
                 workspace: Path, data_dir: Path, youtube_service_factory=None, site_deployer=None,
                 instagram_publisher=None, url_waiter=None):
        self.s, self.ledger, self.approvals = settings, ledger, approvals
        self.ws, self.data = workspace, data_dir
        self.log_path = data_dir / "publish_log.jsonl"
        self._yt_factory = youtube_service_factory or (lambda: youtube.build_service(self.data))
        self._deploy = site_deployer or site.deploy
        self._ig_publish = instagram_publisher or (lambda url, caption: instagram.publish_reel(
            self.s.ig_graph_base, self.s.ig_user_id, os.environ.get("IG_ACCESS_TOKEN", ""), url, caption))
        self._wait_url = url_waiter or instagram.wait_until_public

    # ---- 발행 기록·한도 ----
    def _rows(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        return [json.loads(l) for l in self.log_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def _published_today(self, channel: str) -> int:
        today = date.today().isoformat()
        return sum(1 for r in self._rows() if r["channel"] == channel and r["at"].startswith(today))

    def _log(self, channel: str, result: str, title: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), "channel": channel,
                                "title": title, "result": result}, ensure_ascii=False) + "\n")

    def _auto(self, channel: str) -> bool:
        return bool(self.s.autopilot.get(channel))

    def _over_limit(self, channel: str) -> bool:
        return self._published_today(channel) >= self.s.daily_limits.get(channel, 1)

    # ---- 개인정보 ----
    def terms(self) -> list[str]:
        return redact.load_terms(self.data)

    def guard(self, *texts: str) -> None:
        hits = redact.find_leaks("\n".join(texts), self.terms())
        if hits:
            raise ValueError(f"개인정보 의심 문구 발견 → 발행 중단: {', '.join(sorted(set(hits)))}. 해당 부분을 일반화해 다시 작성")

    def list_sources(self) -> list[str]:
        src = self.data / "sources"
        if not src.exists():
            return []
        return [str(p.relative_to(src)) for p in sorted(src.rglob("*")) if p.suffix in SOURCE_EXT]

    def read_source(self, rel: str) -> str:
        src = (self.data / "sources").resolve()
        p = (src / rel).resolve()
        if src not in p.parents or p.suffix not in SOURCE_EXT or not p.is_file():
            raise ValueError(f"자료 없음: {rel}")
        return redact.redact(p.read_text(encoding="utf-8"), self.terms())[:60_000]

    def _video(self, video_path: str) -> Path:
        full = (self.ws / video_path).resolve()
        if self.ws.resolve() not in full.parents or not full.is_file():
            raise ValueError(f"영상 파일 없음: {video_path}")
        return full

    # ---- 쇼츠 제작 ----
    def produce_short(self, slug: str, scenes: list[dict]) -> str:
        if not 3 <= len(scenes) <= 10:
            raise ValueError("장면은 3∼10개")
        self.guard(*(f"{s['caption']}\n{s['narration']}" for s in scenes))
        key = os.environ.get(self.s.tts_api_key_env, "")
        tts = (lambda text, path: shorts.synthesize_tts(text, path, key, self.s.tts_voice)) if key else None
        out = self.ws / "videos" / f"{slug}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        info = shorts.render_short(scenes, out, shorts.find_font(self.s.font_path), tts=tts,
                                   footer="AI 제작 콘텐츠")
        if info["tts_chars"]:
            krw = info["tts_chars"] * self.s.tts_usd_per_mchar / 1_000_000 * self.s.krw_per_usd
            self.ledger.charge(krw, f"TTS {info['tts_chars']}자 ({slug})")
        voice = "음성 포함" if tts else "무음·자막형(TTS 키 없음)"
        return f"제작 완료: videos/{slug}.mp4 ({info['seconds']}초, {voice})"

    def _dispatch(self, channel: str, ready: bool, payload: dict, title: str, label: str,
                  detail: str, expected_revenue_krw: int = 0) -> str:
        if self._auto(channel) and ready:
            if self._over_limit(channel):
                return f"오늘 {label} 발행 한도 도달. 내일 다시 시도"
            return self.execute(payload)
        item = self.approvals.propose("publish", title, label, detail, expected_revenue_krw, 0, payload)
        return f"승인 요청 #{item['id']} 등록 (전자동 꺼짐 또는 계정 연결 전). 사람이 `execute {item['id']}` 로 실행"

    # ---- 유튜브 ----
    def publish_youtube(self, video_path: str, title: str, description: str, tags: list[str],
                        expected_revenue_krw: int = 0) -> str:
        self._video(video_path)
        desc = f"{description.strip()}\n\n{AI_NOTICE}"
        self.guard(title, desc, *tags)
        payload = {"action": "youtube_upload", "video_path": video_path, "title": title,
                   "description": desc, "tags": tags}
        return self._dispatch("youtube", youtube.is_ready(self.data), payload, title, "유튜브",
                              f"영상 {video_path} 업로드\n설명:\n{desc}", expected_revenue_krw)

    def video_stats(self) -> list[dict]:
        """발행 기록의 유튜브 영상별 조회수·좋아요·댓글."""
        videos = {r["result"].rsplit("/", 1)[-1]: r for r in self._rows() if r["channel"] == "youtube"}
        if not videos:
            return []
        if not youtube.is_ready(self.data):
            raise RuntimeError("유튜브 인증 전")
        stats = youtube.stats(self._yt_factory(), list(videos))
        rows = [{"채널": "유튜브", "제목": videos[v]["title"], "올린시각": videos[v]["at"], "주소": videos[v]["result"],
                 **stats.get(v, {"상태": "조회 불가(비공개·삭제)"})} for v in videos]
        # 현황판용 캐시 (현황판은 API 를 직접 부르지 않음)
        (self.data / "video_stats.json").write_text(
            json.dumps({"at": datetime.now().isoformat(timespec="seconds"), "rows": rows}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        return rows

    # ---- 인스타그램 릴스 ----
    def publish_instagram(self, video_path: str, caption: str) -> str:
        self._video(video_path)
        cap = f"{caption.strip()}\n\n{AI_NOTICE}"
        self.guard(cap)
        ready = bool(self.s.ig_user_id and os.environ.get("IG_ACCESS_TOKEN") and self.s.site_base_url)
        payload = {"action": "instagram_reel", "video_path": video_path, "caption": cap}
        return self._dispatch("instagram", ready, payload, caption[:40], "인스타그램",
                              f"릴스 {video_path} 발행\n캡션:\n{cap}")

    # ---- 블로그 ----
    def publish_blog(self, slug: str, title: str, summary: str, body_md: str) -> str:
        body = f"{body_md.strip()}"
        self.guard(title, summary, body)
        path = blog.write_post(self.ws / "site", slug, title, summary, body)
        msgs = [f"블로그 글 생성: site/{path}"]
        msgs.append(self.deploy_site(f"블로그: {title}"))
        if self.s.naver_blog_drafts:
            draft = self.ws / "naver_drafts" / f"{slug}.md"
            draft.parent.mkdir(parents=True, exist_ok=True)
            draft.write_text(f"# {title}\n\n{body}\n\n{AI_NOTICE}\n", encoding="utf-8")
            msgs.append(f"네이버 블로그용 초안: naver_drafts/{slug}.md (자동 게시 불가, 운영자 여유 있을 때 복사)")
        return "\n".join(msgs)

    # ---- 웹사이트 ----
    def deploy_site(self, message: str) -> str:
        payload = {"action": "site_deploy", "message": message}
        return self._dispatch("site", bool(self.s.site_repo_url), payload, f"사이트 배포: {message}",
                              "GitHub Pages", "workspace/site 전체를 배포")

    def _guard_site(self) -> None:
        site_dir = self.ws / "site"
        if site_dir.exists():
            self.guard(*(p.read_text(encoding="utf-8", errors="ignore") for p in site_dir.rglob("*")
                         if p.suffix in {".html", ".md", ".txt", ".json", ".js", ".css"}))

    # ---- 실제 실행 (전자동 또는 사람의 execute 명령) ----
    def execute(self, payload: dict) -> str:
        act = payload["action"]
        self.guard(*(v for k, v in payload.items() if isinstance(v, str) and k != "video_path"))
        if act in ("site_deploy", "instagram_reel"):
            self._guard_site()
        if act == "youtube_upload":
            url = youtube.upload(self._yt_factory(), str(self._video(payload["video_path"])),
                                 payload["title"], payload["description"], payload["tags"],
                                 self.s.youtube_privacy, self.s.youtube_category_id)
            self._log("youtube", url, payload["title"])
            return f"유튜브 업로드 완료: {url}"
        if act == "site_deploy":
            rev = self._deploy(self.ws / "site", self.s.site_repo_url, self.s.site_branch,
                               self.data / "site_checkout", payload["message"])
            self._log("site", rev, payload["message"])
            return f"사이트 배포 완료: {rev}"
        if act == "instagram_reel":
            src = self._video(payload["video_path"])
            media = self.ws / "site" / "media" / src.name
            media.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, media)
            self._deploy(self.ws / "site", self.s.site_repo_url, self.s.site_branch,
                         self.data / "site_checkout", f"릴스 영상 {src.name}")
            url = f"{self.s.site_base_url.rstrip('/')}/media/{src.name}"
            self._wait_url(url)
            media_id = self._ig_publish(url, payload["caption"])
            self._log("instagram", media_id, payload["caption"][:40])
            return f"인스타 릴스 발행 완료: {media_id}"
        raise ValueError(f"알 수 없는 실행: {act}")
