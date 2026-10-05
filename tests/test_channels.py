"""채널 테스트: 실제 ffmpeg 로 영상 제작, 유튜브는 가짜 서비스, 배포는 로컬 git 저장소."""
import json
import subprocess
from pathlib import Path

import pytest

from survival_agent.approvals import Approvals
from survival_agent.channels import Channels, shorts
from survival_agent.config import Settings
from survival_agent.ledger import Ledger
from survival_agent.tools import ToolBox, ToolError

SCENES = [{"caption": "정부지원사업 서류, 3가지만 먼저", "narration": "첫째"},
          {"caption": "1. 사업자등록증명원", "narration": "둘째"},
          {"caption": "2. 부가세 과세표준증명", "narration": "셋째"}]


BRIEF = {"title": "제목", "target_viewer": "예비창업자", "viewer_question": "서류 뭐 내요?",
         "demand_evidence": "검색 결과", "unique_angle": "체크리스트", "linked_product": "템플릿", "scenes": SCENES}
PASS = {"passed": True, "scores": {"demand": 4}, "feedback": "좋음"}
FAIL = {"passed": False, "scores": {"demand": 2}, "feedback": "수요 근거 부족"}


class FakeYouTube:
    def __init__(self):
        self.bodies = []

    def videos(self):
        return self

    def list(self, part, id):
        self._ids = id.split(",")
        return self

    def execute(self):
        return {"items": [{"id": i, "statistics": {"viewCount": "120", "likeCount": "7", "commentCount": "1"},
                           "status": {"privacyStatus": "public"}} for i in self._ids]}

    def insert(self, part, body, media_body):
        self.bodies.append(body)
        return self

    def next_chunk(self):
        return None, {"id": "abc123"}


def _setup(tmp_path, **overrides):
    s = Settings(seed_krw=50_000, **overrides)
    data, ws = tmp_path / "data", tmp_path / "workspace"
    ledger = Ledger(data, s)
    ledger.init(50_000)
    approvals = Approvals(data)
    yt = FakeYouTube()
    deployed = []
    ch = Channels(s, ledger, approvals, ws, data, youtube_service_factory=lambda: yt,
                  site_deployer=lambda *a: deployed.append(a) or "rev1")
    box = ToolBox(ledger, approvals, ws, channels=ch)
    return ch, box, ledger, approvals, yt, deployed, data, ws


def _font_or_skip():
    try:
        return shorts.find_font()
    except FileNotFoundError:
        pytest.skip("한글 폰트 없음")


def test_produce_short_renders_video(tmp_path, monkeypatch):
    _font_or_skip()
    monkeypatch.delenv("GOOGLE_TTS_API_KEY", raising=False)
    ch, box, ledger, *_ , ws = _setup(tmp_path)
    box.critic = lambda b: PASS
    assert "통과" in box.run("submit_brief", {"slug": "test-01", **BRIEF})
    msg = box.run("produce_short", {"slug": "test-01"})
    assert "무음·자막형" in msg
    video = ws / "videos/test-01.mp4"
    assert video.stat().st_size > 10_000
    assert "12.0초" in msg  # 장면 3 × 4초
    assert ledger.state()["balance_krw"] == 50_000  # TTS 미사용 → 비용 0


def test_produce_short_charges_tts(tmp_path, monkeypatch):
    _font_or_skip()
    monkeypatch.setenv("GOOGLE_TTS_API_KEY", "k")

    def fake_tts(text, path, key, voice):  # 1초짜리 무음 mp3
        shorts._ffmpeg("-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "1", str(path))
    monkeypatch.setattr(shorts, "synthesize_tts", fake_tts)
    ch, box, ledger, *_ = _setup(tmp_path)
    box.critic = lambda b: PASS
    box.run("submit_brief", {"slug": "t2", **BRIEF})
    assert "음성 포함" in box.run("produce_short", {"slug": "t2"})
    assert ledger.state()["balance_krw"] < 50_000


def test_bad_inputs_rejected(tmp_path):
    ch, box, *_ = _setup(tmp_path)
    box.critic = lambda b: PASS
    with pytest.raises(ToolError):
        box.run("submit_brief", {"slug": "../x", **BRIEF})
    with pytest.raises(ToolError):
        box.run("submit_brief", {"slug": "ok", **{**BRIEF, "scenes": SCENES[:2]}})
    with pytest.raises(ToolError):
        box.run("publish_youtube", {"video_path": "../data/state.json", "title": "t",
                                    "description": "d", "tags": [], "expected_revenue_krw": 0})


def _video(ws: Path) -> str:
    (ws / "videos").mkdir(parents=True, exist_ok=True)
    (ws / "videos/v.mp4").write_bytes(b"x")
    return "videos/v.mp4"


def test_youtube_manual_mode_queues_executable_proposal(tmp_path):
    ch, box, ledger, approvals, yt, _, data, ws = _setup(tmp_path)
    out = box.run("publish_youtube", {"video_path": _video(ws), "title": "제목", "description": "설명",
                                      "tags": ["a"], "expected_revenue_krw": 0})
    assert "승인 요청 #1" in out and yt.bodies == []
    item = approvals.get(1)
    assert item["payload"]["action"] == "youtube_upload"
    assert "AI로 기획·제작" in item["payload"]["description"]
    # 사람이 execute 하면 그때 업로드
    assert "abc123" in ch.execute(item["payload"])
    assert yt.bodies[0]["status"]["containsSyntheticMedia"] is True


def test_youtube_autopilot_uploads_with_daily_limit(tmp_path):
    ch, box, ledger, approvals, yt, _, data, ws = _setup(
        tmp_path, autopilot={"youtube": True, "site": False}, daily_limits={"youtube": 1, "site": 3})
    (data / "youtube_token.json").write_text("{}")
    args = {"video_path": _video(ws), "title": "제목", "description": "설명", "tags": [], "expected_revenue_krw": 0}
    assert "업로드 완료" in box.run("publish_youtube", args)
    assert "한도 도달" in box.run("publish_youtube", args)
    assert len(yt.bodies) == 1 and approvals.all() == []


def test_site_autopilot_and_manual(tmp_path):
    ch, box, ledger, approvals, yt, deployed, *_ = _setup(tmp_path)
    assert "승인 요청" in box.run("deploy_site", {"message": "첫 배포"}) and deployed == []
    ch.s.autopilot["site"] = True
    ch.s.site_repo_url = "git@example:me/me.github.io.git"
    assert "배포 완료" in box.run("deploy_site", {"message": "두 번째"}) and len(deployed) == 1


def test_real_git_deploy(tmp_path):
    from survival_agent.channels import site
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", "-q", str(remote), str(seed)], check=True)
    (seed / "old.html").write_text("old")
    for cmd in (["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"],
                ["push", "-q", "origin", "HEAD:main"]):
        subprocess.run(["git", *cmd], cwd=seed, check=True)
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("<h1>도구</h1>", encoding="utf-8")
    rev = site.deploy(site_dir, str(remote), "main", tmp_path / "checkout", "배포")
    assert rev and rev != "변경 없음"
    files = subprocess.run(["git", "ls-tree", "--name-only", "main"], cwd=remote,
                           capture_output=True, text=True).stdout.split()
    assert files == ["index.html"]
    assert site.deploy(site_dir, str(remote), "main", tmp_path / "checkout", "재배포") == "변경 없음"


def test_brief_gate_and_review_limit(tmp_path):
    ch, box, *_ = _setup(tmp_path)
    box.critic = lambda b: FAIL
    with pytest.raises(ToolError, match="심사를 통과한 기획안이 없음"):
        box.run("produce_short", {"slug": "topic-a"})
    for i in range(3):
        out = json.loads(box.run("submit_brief", {"slug": "topic-a", **BRIEF}))
        assert out["결과"].startswith(f"탈락 ({i + 1}/3")
        assert out["피드백"] == "수요 근거 부족"
    with pytest.raises(ToolError, match="소진"):
        box.run("submit_brief", {"slug": "topic-a", **BRIEF})
    with pytest.raises(ToolError):
        box.run("produce_short", {"slug": "topic-a"})


def test_video_stats(tmp_path):
    ch, box, ledger, approvals, yt, _, data, ws = _setup(
        tmp_path, autopilot={"youtube": True, "site": False})
    (data / "youtube_token.json").write_text("{}")
    assert json.loads(box.run("get_video_stats", {})) == []
    box.run("publish_youtube", {"video_path": _video(ws), "title": "첫 영상", "description": "d",
                                "tags": [], "expected_revenue_krw": 0})
    stats = json.loads(box.run("get_video_stats", {}))
    assert stats[0]["제목"] == "첫 영상" and stats[0]["조회수"] == 120


def test_redaction_and_false_positives(tmp_path):
    from survival_agent import redact
    raw = ("대표 연락처 010-1234-5678, abc@medium.kr, 사업자 123-45-67890, 주민 900101-1234567, "
           "계좌 110-123-456789, 부산시 동구 중앙대로 123-4, 고객사 캐빈스보일링크랩")
    out = redact.redact(raw, ["캐빈스보일링크랩"])
    for leak in ["010-1234-5678", "abc@medium.kr", "123-45-67890", "900101-1234567", "110-123-456789",
                 "중앙대로 123", "캐빈스보일링크랩"]:
        assert leak not in out
    # 오탐 방지: 날짜·일반 문장은 통과
    safe = "2026-09-29 공고, 신청은 3단계로 5분이면 끝남. 2026. 3. 31. 13:00∼18:00 접수, 5,000만 원 지원"
    assert redact.find_leaks(safe, []) == []


def test_sources_are_redacted(tmp_path):
    ch, box, *_ , data, ws = _setup(tmp_path)
    (data / "sources").mkdir()
    (data / "sources/예창패_후기.md").write_text("담당자 010-9876-5432 에게 문의한 A 대표", encoding="utf-8")
    (data / "redact_terms.txt").write_text("A 대표\n", encoding="utf-8")
    assert "예창패_후기.md" in box.run("list_sources", {})
    text = box.run("read_source", {"path": "예창패_후기.md"})
    assert "010-9876-5432" not in text and "A 대표" not in text
    with pytest.raises(ToolError):
        box.run("read_source", {"path": "../state.json"})


def test_publish_blocked_on_leak(tmp_path):
    ch, box, *_ , ws = _setup(tmp_path)
    with pytest.raises(ToolError, match="개인정보"):
        box.run("publish_youtube", {"video_path": _video(ws), "title": "문의 010-1111-2222",
                                    "description": "d", "tags": [], "expected_revenue_krw": 0})
    with pytest.raises(ValueError, match="개인정보"):
        ch.produce_short("x", [{"caption": "메일 me@a.com", "narration": "n"}] * 3)


def test_blog_post_and_naver_draft(tmp_path):
    ch, box, ledger, approvals, yt, deployed, data, ws = _setup(
        tmp_path, autopilot={"youtube": False, "instagram": False, "site": True},
        site_repo_url="git@example:me/me.github.io.git")
    out = box.run("publish_blog", {"slug": "docs-01", "title": "예창패 서류 3가지", "summary": "요약",
                                   "body_markdown": "## 준비물\n- 사업자등록증명원\n- **부가세** 증명\n\n본문 [공고](https://www.k-startup.go.kr)"})
    post = (ws / "site/blog/docs-01.html").read_text(encoding="utf-8")
    assert "<h2>준비물</h2>" in post and "<strong>부가세</strong>" in post and 'href="https://www.k-startup.go.kr"' in post
    assert "예창패 서류 3가지" in (ws / "site/blog/index.html").read_text(encoding="utf-8")
    assert (ws / "site/index.html").exists()
    assert "사이트 배포 완료" in out and len(deployed) == 1
    assert (ws / "naver_drafts/docs-01.md").exists()


def test_site_deploy_blocked_if_site_has_leak(tmp_path):
    ch, box, *_ , ws = _setup(tmp_path, autopilot={"site": True}, site_repo_url="x")
    (ws / "site").mkdir(parents=True)
    (ws / "site/index.html").write_text("연락 010-2222-3333", encoding="utf-8")
    with pytest.raises(ToolError, match="개인정보"):
        box.run("deploy_site", {"message": "m"})


def test_instagram_reel_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_ACCESS_TOKEN", "tok")
    published, waited = [], []
    s = Settings(seed_krw=50_000, autopilot={"instagram": True}, ig_user_id="178", site_repo_url="x",
                 site_base_url="https://me.github.io/")
    data, ws = tmp_path / "data", tmp_path / "workspace"
    ledger = Ledger(data, s); ledger.init(50_000)
    deployed = []
    ch = Channels(s, ledger, Approvals(data), ws, data, site_deployer=lambda *a: deployed.append(a) or "r",
                  instagram_publisher=lambda url, cap: published.append((url, cap)) or "IG1",
                  url_waiter=waited.append)
    out = ch.publish_instagram(_video(ws), "서류 3가지 #정부지원사업")
    assert out == "인스타 릴스 발행 완료: IG1"
    assert waited == ["https://me.github.io/media/v.mp4"] and (ws / "site/media/v.mp4").exists()
    assert "AI로 기획·제작" in published[0][1]
    assert "한도 도달" in ch.publish_instagram(_video(ws), "두 번째")


def test_instagram_graph_calls():
    from survival_agent.channels import instagram
    calls, states = [], iter(["IN_PROGRESS", "FINISHED"])

    def fake_call(method, url, params):
        calls.append((method, url, params))
        if url.endswith("/media"):
            return {"id": "C1"}
        if url.endswith("/C1"):
            return {"status_code": next(states)}
        return {"id": "M1"}
    mid = instagram.publish_reel("https://graph.facebook.com/v22.0", "178", "t", "https://x/v.mp4", "cap",
                                 call=fake_call, sleep=lambda s: None)
    assert mid == "M1"
    assert calls[0][2]["media_type"] == "REELS" and calls[-1][2]["creation_id"] == "C1"


def test_dashboard_empty_and_demo(tmp_path):
    from datetime import date
    from survival_agent import dashboard
    empty = dashboard.collect(tmp_path / "d", tmp_path / "w", Settings(), env={})
    assert not empty["initialized"]
    assert [t[1] for t in empty["todos"]][:2] == ["Claude API 키 발급·등록", "시드 입금으로 가동 시작"]
    demo = dashboard.build_demo(tmp_path / "demo", today=date(2026, 9, 29))
    assert demo["state"]["tier"] == "normal" and demo["briefs"] == {
        "total": 6, "passed": 5, "failed": demo["briefs"]["failed"]}
    assert demo["videos"][0]["views"] == 1840 and demo["videos"][0]["channels"] == ["instagram", "youtube"]
    assert all(ok for _, _, ok, _, _, req in demo["setup"] if req)
    page = dashboard.render_fragment(empty, demo)
    assert page.startswith("<title>생존 에이전트 현황판</title>") and "<html" not in page
    assert "가동 후 예시" in page and "예시 화면입니다" in page
    doc = dashboard.render_document(empty)
    assert doc.startswith("<!doctype html>")


def test_dashboard_cli_before_init(tmp_path, monkeypatch):
    import survival_agent.__main__ as cli
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cli, "WORKSPACE_DIR", tmp_path / "ws")
    assert cli.main(["dashboard"]) == 0
    assert "준비 현황" in (tmp_path / "ws/dashboard.html").read_text(encoding="utf-8")


def test_remotion_props_and_queue(tmp_path):
    from survival_agent.channels import remotion
    batch = json.loads(Path("content/batch_20260929/scripts.json").read_text(encoding="utf-8"))
    brand = json.loads(Path("content/brand/brand.json").read_text(encoding="utf-8"))
    assert len(batch["videos"]) == 7
    for v in batch["videos"]:
        remotion.guard(v, [])  # 대본에 개인정보 패턴 없음
        props = remotion.build_props(v, brand, None, tmp_path)
        assert props["scenes"][0]["kind"] == "hook" and props["scenes"][-1]["kind"] == "cta"
        secs = sum(s["durationInFrames"] for s in props["scenes"]) / 30
        assert 15 <= secs <= 60
    with pytest.raises(ValueError, match="개인정보"):
        remotion.guard({**batch["videos"][0], "title": "문의 010-1234-5678"}, [])
    # 검수 통과분만 대기열로
    scripts = tmp_path / "b" / "scripts.json"
    (tmp_path / "b" / "videos").mkdir(parents=True)
    scripts.write_text(json.dumps({**batch, "brand": "x"}, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "b/videos/02-psst.mp4").write_bytes(b"x")
    ap = Approvals(tmp_path / "data")
    ids = remotion.queue_for_review(scripts, ap, tmp_path / "ws", only=["02-psst"])
    assert len(ids) == 2 and (tmp_path / "ws/videos/02-psst.mp4").exists()
    assert {a["payload"]["action"] for a in ap.all()} == {"youtube_upload", "instagram_reel"}


def test_voice_render_props_use_audio_length(tmp_path, monkeypatch):
    from survival_agent.channels import remotion
    calls = []

    def fake_synth(provider, text, out, voice):  # 2초짜리 무음 mp3
        calls.append((provider, voice, text))
        shorts._ffmpeg("-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "2", str(out))
    monkeypatch.setattr(remotion, "synthesize", fake_synth)
    batch = json.loads(Path("content/batch_20260929/scripts.json").read_text(encoding="utf-8"))
    brand = json.loads(Path("content/brand/brand.json").read_text(encoding="utf-8"))
    v = batch["videos"][0]
    props = remotion.build_props(v, brand, "google", tmp_path, None)
    assert calls[0][2] == v["scenes"][0]["narration"] and "삼십 쪽" in calls[0][2]
    assert props["scenes"][0]["audio"] == "audio/01-notice-3-spots/00.mp3"
    assert abs(props["scenes"][0]["durationInFrames"] - round(2.6 * 30)) <= 2  # 음성 약 2초 + 0.6초
    assert props["scenes"][1]["durationInFrames"] - props["scenes"][0]["durationInFrames"] == 8  # 전환 겹침 보정
    assert remotion.DEFAULT_VOICE["google"] == "ko-KR-Chirp3-HD-Charon"


def test_gemini_tts_request_and_audio(tmp_path, monkeypatch):
    import base64
    from survival_agent.channels import remotion
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.delenv("GEMINI_TTS_MODEL", raising=False)
    sent = []

    def fake_post(model):
        sent.append(model)
        if model == remotion.GEMINI_MODELS[0]:   # 첫 모델이 없어졌다고 가정 → 다음 후보로
            import urllib.error
            raise urllib.error.HTTPError("u", 404, "not found", {}, None)
        pcm = b"\x00\x00" * 24000  # 1초 무음 PCM
        return {"candidates": [{"content": {"parts": [{"inlineData": {
            "mimeType": "audio/L16;codec=pcm;rate=24000", "data": base64.b64encode(pcm).decode()}}]}}]}
    out = tmp_path / "a.mp3"
    remotion.gemini_tts("공고문 삼십 쪽", out, "Charon", post=fake_post)
    assert sent == remotion.GEMINI_MODELS[:2]
    assert 0.9 < shorts.audio_seconds(out) < 1.2
    assert remotion.DEFAULT_VOICE["gemini"] == "Charon"


def test_scene_boundaries_prefer_long_pauses():
    from survival_agent.channels import remotion
    gaps = [(1.46, .5), (6.13, .99), (7.32, .67), (18.29, 1.15), (19.5, .6), (28.49, 1.04), (37.23, .95)]
    starts = remotion.scene_boundaries(["a" * 37, "b" * 62, "c" * 59, "d" * 45, "e" * 33], 42.48, gaps)
    assert starts == [0.0, 6.13, 18.29, 28.49, 37.23]
