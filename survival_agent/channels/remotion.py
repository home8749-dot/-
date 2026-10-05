"""브랜드 쇼츠 렌더링 (Remotion 템플릿: video/). 대본 묶음(scripts.json) → mp4 + 썸네일.

  python -m survival_agent render-batch content/batch_20260929/scripts.json [--tts edge]

- 대본 형식: content/batch_20260929/scripts.json 참고. 문구의 ==강조== 는 형광펜으로 그어짐
- --tts gemini [권장]: Gemini TTS(구글 AI 스튜디오와 같은 음성). 환경변수 GEMINI_API_KEY(AI 스튜디오 키) 필요
  기본 목소리 Charon(차분한 남성), 여성 대안 Kore. 말투는 GEMINI_STYLE 지시문으로 조절
- --tts google: Google Cloud TTS Chirp 3 HD(가장 자연스러운 등급). 환경변수 GOOGLE_TTS_API_KEY 필요
  기본 목소리 ko-KR-Chirp3-HD-Charon(차분한 남성). 여성 대안 ko-KR-Chirp3-HD-Kore → --voice 로 지정
- --tts edge: 무료 edge-tts. 기본 ko-KR-InJoonNeural(남성), 대안 ko-KR-SunHiNeural(여성)
  ※ edge-tts 는 공식 상용 API 가 아님. 수익 채널에 쓰기 전 약관 확인 필요
- 장면 길이는 음성 길이 + 0.6초로 자동 조정. 내레이션은 대본의 narration(말하듯 쓴 문장)을 읽음
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


DEFAULT_VOICE = {"gemini": "Charon", "google": "ko-KR-Chirp3-HD-Charon", "edge": "ko-KR-InJoonNeural"}
GEMINI_MODELS = ["gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts"]
GEMINI_STYLE = ("정부지원사업을 오래 다뤄 본 차분하고 신뢰감 있는 컨설턴트가, 처음 준비하는 창업자에게 "
                "옆에서 설명하듯 자연스럽게 말해 주세요. 과장 없이 또박또박, 문장 끝은 부드럽게 내려 주세요. 읽을 문장:")


def edge_tts(text: str, out: Path, voice: str, rate: str = "+5%") -> None:
    import edge_tts as et  # 선택 의존성

    async def run():
        await et.Communicate(text, voice, rate=rate).save(str(out))
    asyncio.run(run())


def google_tts(text: str, out: Path, voice: str, rate: float = 1.05) -> None:
    """Google Cloud Text-to-Speech REST (API 키). Chirp 3 HD 는 SSML·피치 대신 자연스러운 기본 억양을 씀."""
    import base64
    import urllib.request

    key = os.environ.get("GOOGLE_TTS_API_KEY", "")
    if not key:
        raise RuntimeError("GOOGLE_TTS_API_KEY 환경변수가 없음")
    body = json.dumps({"input": {"text": text},
                       "voice": {"languageCode": voice[:5], "name": voice},
                       "audioConfig": {"audioEncoding": "MP3", "speakingRate": rate}}).encode()
    req = urllib.request.Request(f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}",
                                 data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out.write_bytes(base64.b64decode(json.loads(r.read())["audioContent"]))


def _pcm_to_wav(pcm: bytes, rate: int = 24000) -> bytes:
    import struct
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " +
            struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", len(pcm)) + pcm)


def gemini_tts(text: str, out: Path, voice: str, post=None) -> None:
    """Gemini API TTS. 응답은 base64 오디오(16bit PCM 24kHz 모노 또는 WAV) → mp3 로 저장."""
    import base64
    import urllib.error
    import urllib.request

    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 없음 (aistudio.google.com 에서 발급)")
    style = os.environ.get("GEMINI_STYLE", GEMINI_STYLE)
    body = {"contents": [{"parts": [{"text": f"{style}\n{text}"}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}

    def _post(model: str) -> dict:
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())

    post = post or _post
    models = [os.environ["GEMINI_TTS_MODEL"]] if os.environ.get("GEMINI_TTS_MODEL") else GEMINI_MODELS
    last = None
    for model in models:
        try:
            resp = post(model)
            break
        except urllib.error.HTTPError as e:  # 모델 이름이 바뀌었으면 다음 후보로
            last = e
            if e.code not in (400, 404):
                raise
    else:
        raise RuntimeError(f"Gemini TTS 모델 호출 실패: {last}")
    part = next(p for p in resp["candidates"][0]["content"]["parts"] if "inlineData" in p)
    audio = base64.b64decode(part["inlineData"]["data"])
    rate = 24000
    m = re.search(r"rate=(\d+)", part["inlineData"].get("mimeType", ""))
    if m:
        rate = int(m.group(1))
    wav = audio if audio[:4] == b"RIFF" else _pcm_to_wav(audio, rate)
    tmp = out.with_suffix(".wav")
    tmp.write_bytes(wav)
    shorts._ffmpeg("-i", str(tmp), "-ac", "1", "-ar", "44100", "-b:a", "160k", str(out))
    tmp.unlink()


def synthesize(provider: str, text: str, out: Path, voice: str | None) -> None:
    v = voice or DEFAULT_VOICE[provider]
    {"gemini": gemini_tts, "google": google_tts, "edge": edge_tts}[provider](text, out, v)


def guard(video: dict, terms: list[str]) -> None:
    texts = [video["title"], video.get("description", ""), video.get("caption", "")]
    for s in video["scenes"]:
        texts += [s["text"], s.get("sub", ""), s.get("narration", "")]
    hits = redact.find_leaks("\n".join(texts), terms)
    if hits:
        raise ValueError(f"{video['slug']}: 개인정보 의심 문구 → 렌더링 중단 ({', '.join(sorted(set(hits)))})")


def build_props(video: dict, brand: dict, tts: str | None, audio_root: Path, voice: str | None = None) -> dict:
    scenes = []
    for i, s in enumerate(video["scenes"]):
        sc = {k: s[k] for k in ("kind", "text", "sub", "label") if k in s}
        if tts:
            rel = f"audio/{video['slug']}/{i:02d}.mp3"
            mp3 = audio_root / rel
            mp3.parent.mkdir(parents=True, exist_ok=True)
            synthesize(tts, s.get("narration") or plain(s["text"]), mp3, voice)
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


def render_batch(scripts_path: Path, tts: str | None = None, only: list[str] | None = None, log=print,
                 voice: str | None = None) -> list[dict]:
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
        props = build_props(v, brand, tts, VIDEO_DIR / "public", voice)
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
