"""자체 블로그(GitHub Pages) 글 생성. 네이버·티스토리는 글쓰기 API 가 종료돼 자동 게시 불가 → 초안만 만든다."""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path

PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><meta name="description" content="{summary}">
<style>body{{max-width:720px;margin:0 auto;padding:24px 16px;font:17px/1.75 -apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#222;background:#fff}}
h1{{font-size:1.6em;line-height:1.35}}h2{{margin-top:2em}}a{{color:#0a58ca}}.meta,.notice{{color:#777;font-size:.9em}}
@media (prefers-color-scheme:dark){{body{{background:#161616;color:#e6e6e6}}a{{color:#7ab4ff}}}}</style></head>
<body><p class="meta"><a href="./">← 전체 글</a> · {date}</p><h1>{title}</h1>
{body}
<p class="notice">※ 이 글은 AI가 기획·작성하고 개인정보를 가린 자료를 바탕으로 합니다.</p></body></html>"""

INDEX = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>정부지원사업 실무 노트</title>
<style>body{{max-width:720px;margin:0 auto;padding:24px 16px;font:17px/1.7 -apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#222;background:#fff}}
li{{margin:.6em 0}}span{{color:#777;font-size:.9em}}a{{color:#0a58ca}}
@media (prefers-color-scheme:dark){{body{{background:#161616;color:#e6e6e6}}a{{color:#7ab4ff}}}}</style></head>
<body><h1>정부지원사업 실무 노트</h1><ul>{items}</ul></body></html>"""


def _inline(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return re.sub(r"\[(.+?)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', t)


def md_to_html(md: str) -> str:
    out, para, lst = [], [], None
    flush = lambda: para and (out.append(f"<p>{_inline(' '.join(para))}</p>"), para.clear())

    def close():
        nonlocal lst
        if lst:
            out.append(f"</{lst}>")
            lst = None

    for line in md.splitlines():
        s = line.strip()
        if not s:
            flush(); close(); continue
        m = re.match(r"(#{2,3})\s+(.*)", s)
        if m:
            flush(); close()
            out.append(f"<h{len(m[1])}>{_inline(m[2])}</h{len(m[1])}>"); continue
        m = re.match(r"(?:[-*]|\d+[.)])\s+(.*)", s)
        if m:
            flush()
            kind = "ol" if s[0].isdigit() else "ul"
            if lst != kind:
                close(); out.append(f"<{kind}>"); lst = kind
            out.append(f"<li>{_inline(m[1])}</li>"); continue
        close(); para.append(s)
    flush(); close()
    return "\n".join(out)


def write_post(site_dir: Path, slug: str, title: str, summary: str, body_md: str) -> str:
    blog = site_dir / "blog"
    blog.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y. %m. %d.")
    (blog / f"{slug}.html").write_text(
        PAGE.format(title=html.escape(title), summary=html.escape(summary), date=today, body=md_to_html(body_md)),
        encoding="utf-8")
    idx_path = blog / "posts.json"
    posts = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else []
    posts = [p for p in posts if p["slug"] != slug] + [{"slug": slug, "title": title, "date": today}]
    idx_path.write_text(json.dumps(posts, ensure_ascii=False, indent=1), encoding="utf-8")
    items = "".join(f'<li><a href="{p["slug"]}.html">{html.escape(p["title"])}</a> <span>{p["date"]}</span></li>'
                    for p in reversed(posts))
    (blog / "index.html").write_text(INDEX.format(items=items), encoding="utf-8")
    if not (site_dir / "index.html").exists():
        (site_dir / "index.html").write_text('<meta http-equiv="refresh" content="0; url=blog/">', encoding="utf-8")
    return f"blog/{slug}.html"
