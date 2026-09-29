"""브랜드 쇼츠 렌더링 (Remotion 템플릿: video/). 대본 묶음(scripts.json) → mp4 + 썸네일.

  python -m survival_agent render-batch content/batch_20260929/scripts.json [--tts edge]

- 대본 형식: content/batch_20260929/scripts.json 참고. 문구의 ==강조== 는 형광펜으로 그어짐
- --tts edge: 무료 edge-tts(마이크로소프트 엣지 음성)로 장면별 한국어 음성 생성 → 장면 길이를 음성에 맞춤
  ※ edge-tts 는 공식 상용 API 가 아님. 수익 채널에 쓰기 전 약관 확인 필요 (대안: Google Cloud TTS)
- 크롬이 자동으로 안 잡히면 환경변수 REMOTION_BROWSER 에 크롬(헤드리스 셸) 경로 지정
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .. import redact
from ..config import DATA_DIR, ROOT
from . import shorts

VIDEO_DIR = ROOT / "video"
FPS = 30
TRANSITION_FRAMES = 8


def plain(text: str) -> str:
    return text.replace("==", "")


def frames_for_text(scene: dict) -> int:
    """음성 없을 때: 글자 수로 읽는 시간 추정(3∼6.5초)."""
    n = len(plain(scene["text"] + scene.get("sub", "")))
    return round(FPS * min(6.5, max(3.0, 1.8 + n * 0.085)))


def brand_props(brand: dict) -> dict:
    return {"name": brand["name"], "sealText": brand["seal_text"], "footer": brand["footer"], "colors": brand["colors"]}


def edge_tts(text: str, out: Path, voice: str = "ko-KR-SunHiNeural", rate: str = "+8%") -> None:
    import edge_tts as et  # 선택 의존성

    async def run():
        await et.Communicate(text, voice, rate=rate).save(str(out))
    asyncio.run(run())


def guard(video: dict, terms: list[str]) -> None:
    texts = [video["title"], video.get("description", ""), video.get("caption", "")]
    for s in video["scenes"]:
        texts += [s["text"], s.get("sub", ""), s.get("narration", "")]
    hits = redact.find_leaks("\n".join(texts), terms)
    if hits:
        raise ValueError(f"{video['slug']}: 개인정보 의심 문구 → 렌더링 중단 ({', '.join(sorted(set(hits)))})")


def build_props(video: dict, brand: dict, tts: str | None, audio_root: Path) -> dict:
    scenes = []
    for i, s in enumerate(video["scenes"]):
        sc = {k: s[k] for k in ("kind", "text", "sub", "label") if k in s}
        if tts == "edge":
            rel = f"audio/{video['slug']}/{i:02d}.mp3"
            mp3 = audio_root / rel
            mp3.parent.mkdir(parents=True, exist_ok=True)
            edge_tts(s.get("narration") or plain(s["text"]), mp3)
            sc["audio"] = rel
            sc["durationInFrames"] = round((shorts.audio_seconds(mp3) + 0.6) * FPS) + (TRANSITION_FRAMES if i else 0)
        else:
            sc["durationInFrames"] = frames_for_text(s)
        scenes.append(sc)
    return {"brand": brand_props(brand), "scenes": scenes}


def _npx(*args: str) -> None:
    cmd = ["npx", "remotion", *args]
    if os.environ.get("REMOTION_BROWSER"):
        cmd.append(f"--browser-executable={os.environ['REMOTION_BROWSER']}")
    p = subprocess.run(cmd, cwd=VIDEO_DIR, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"remotion 실패: {(p.stderr or p.stdout)[-800:]}")


def render_batch(scripts_path: Path, tts: str | None = None, only: list[str] | None = None, log=print) -> list[dict]:
    batch = json.loads(scripts_path.read_text(encoding="utf-8"))
    brand = json.loads((scripts_path.parent / batch["brand"]).read_text(encoding="utf-8"))
    terms = redact.load_terms(DATA_DIR)
    out_dir = scripts_path.parent / "videos"
    out_dir.mkdir(exist_ok=True)
    props_dir = VIDEO_DIR / "props"
    props_dir.mkdir(exist_ok=True)
    results = []
    for v in batch["videos"]:
        if only and v["slug"] not in only:
            continue
        guard(v, terms)
        props = build_props(v, brand, tts, VIDEO_DIR / "public")
        pf = props_dir / f"{v['slug']}.json"
        pf.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
        mp4, png = out_dir / f"{v['slug']}.mp4", out_dir / f"{v['slug']}.png"
        _npx("render", "src/index.ts", "ShortVideo", str(mp4.resolve()), f"--props={pf.resolve()}", "--log=error")
        _npx("still", "src/index.ts", "ShortVideo", str(png.resolve()), f"--props={pf.resolve()}", "--frame=45", "--log=error")
        total = sum(s["durationInFrames"] for s in props["scenes"]) - TRANSITION_FRAMES * (len(props["scenes"]) - 1)
        results.append({"slug": v["slug"], "seconds": round(total / FPS, 1), "voice": bool(tts), "mp4": str(mp4)})
        log(f"렌더 완료: {mp4.name} ({total / FPS:.1f}초, {'음성' if tts else '자막형 무음'})")
    (out_dir / "render_log.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return results


def queue_for_review(scripts_path: Path, approvals, workspace: Path, only: list[str] | None = None) -> list[int]:
    """검수 통과한 영상(only 로 지정)을 발행 대기열에 올린다(유튜브·인스타 각각 execute 한 줄로 발행)."""
    batch = json.loads(scripts_path.read_text(encoding="utf-8"))
    ids = []
    for v in batch["videos"]:
        if only and v["slug"] not in only:
            continue
        src = scripts_path.parent / "videos" / f"{v['slug']}.mp4"
        if not src.exists():
            continue
        dst = workspace / "videos" / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        rel = f"videos/{src.name}"
        desc = f"{v['description']}\n\n※ 이 콘텐츠는 AI로 기획·제작되었습니다."
        yt = approvals.propose("publish", v["title"], "유튜브", f"영상 {rel}", 0, 0,
                               {"action": "youtube_upload", "video_path": rel, "title": v["title"],
                                "description": desc, "tags": v["tags"]})
        ig = approvals.propose("publish", v["title"], "인스타그램", f"릴스 {rel}", 0, 0,
                               {"action": "instagram_reel", "video_path": rel,
                                "caption": f"{v['caption']}\n\n※ 이 콘텐츠는 AI로 기획·제작되었습니다."})
        ids += [yt["id"], ig["id"]]
    return ids


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")
