"""세로형 쇼츠(1080×1920) 제작: 장면 카드 이미지 + 음성(TTS, 선택) → mp4.

외부 영상 생성 AI 없이 Pillow + ffmpeg 만으로 만든다(추가 비용 0원, TTS 제외).
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import urllib.request
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT_CANDIDATES = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",          # macOS
    "/Library/Fonts/NanumGothicBold.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",                        # Windows
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",  # Linux
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]
PALETTES = [((20, 24, 38), (255, 214, 102)), ((12, 52, 61), (255, 255, 255)),
            ((250, 245, 235), (30, 30, 30)), ((60, 20, 50), (255, 190, 200))]
MAX_SECONDS = 60


def find_font(preferred: str = "") -> str:
    for p in [preferred, *FONT_CANDIDATES]:
        if p and Path(p).exists():
            return p
    raise FileNotFoundError("한글 폰트를 찾지 못함. data/config.json 의 font_path 에 폰트 경로 지정")


def _wrap(draw, text, font, max_w):
    """띄어쓰기 단위로 줄바꿈, 한 단어가 한 줄보다 길 때만 글자 단위로 자른다."""
    fits = lambda s: draw.textlength(s, font=font) <= max_w
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            cand = f"{line} {word}" if line else word
            if fits(cand):
                line = cand
                continue
            if line:
                lines.append(line)
            line = ""
            for ch in word:
                if not fits(line + ch) and line:
                    lines.append(line)
                    line = ""
                line += ch
        lines.append(line)
    return lines


def render_card(text: str, out: Path, font_path: str, palette_idx: int, footer: str = "") -> None:
    bg, fg = PALETTES[palette_idx % len(PALETTES)]
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    size = 88 if len(text) < 40 else 72 if len(text) < 80 else 60
    font = ImageFont.truetype(font_path, size)
    lines = _wrap(d, text, font, W - 160)
    lh = int(size * 1.45)
    y = (H - lh * len(lines)) // 2
    for ln in lines:
        d.text(((W - d.textlength(ln, font=font)) // 2, y), ln, font=font, fill=fg)
        y += lh
    if footer:
        small = ImageFont.truetype(font_path, 36)
        d.text(((W - d.textlength(footer, font=small)) // 2, H - 180), footer, font=small, fill=fg)
    img.save(out)


def synthesize_tts(text: str, out: Path, api_key: str, voice: str) -> None:
    """Google Cloud Text-to-Speech REST (API 키 방식)."""
    body = json.dumps({"input": {"text": text},
                       "voice": {"languageCode": "ko-KR", "name": voice},
                       "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.1}}).encode()
    req = urllib.request.Request(
        f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}",
        data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out.write_bytes(base64.b64decode(json.loads(r.read())["audioContent"]))


def _ffmpeg(*args) -> str:
    p = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", *args],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패: {p.stderr[-500:]}")
    return p.stderr


def audio_seconds(path: Path) -> float:
    p = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", p.stderr)
    if not m:
        raise RuntimeError(f"오디오 길이 확인 실패: {path}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def render_short(scenes: list[dict], out_path: Path, font_path: str,
                 tts=None, seconds_per_scene: float = 4.0, footer: str = "") -> dict:
    """scenes: [{"caption": 화면 문구, "narration": 읽을 문장}]. 첫 장면이 곧 첫 3초 훅.
    tts(text, path) 가 None 이면 무음+자막.

    반환: {"path", "seconds", "tts_chars"}
    """
    work = out_path.parent / (out_path.stem + "_parts")
    work.mkdir(parents=True, exist_ok=True)
    cards = scenes
    segments, total, chars = [], 0.0, 0
    for i, sc in enumerate(cards):
        img = work / f"{i:02d}.png"
        render_card(sc["caption"], img, font_path, i, footer)
        seg = work / f"{i:02d}.mp4"
        if tts and sc.get("narration"):
            mp3 = work / f"{i:02d}.mp3"
            tts(sc["narration"], mp3)
            chars += len(sc["narration"])
            dur = audio_seconds(mp3) + 0.3
            audio_in = ["-i", str(mp3)]
        else:
            dur = seconds_per_scene
            audio_in = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        if total + dur > MAX_SECONDS:
            break
        _ffmpeg("-loop", "1", "-i", str(img), *audio_in, "-t", f"{dur:.2f}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
                "-c:a", "aac", "-ar", "44100", "-ac", "2", str(seg))
        segments.append(seg)
        total += dur
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{s.resolve()}'\n" for s in segments), encoding="utf-8")
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out_path))
    return {"path": str(out_path), "seconds": round(total, 1), "tts_chars": chars}
