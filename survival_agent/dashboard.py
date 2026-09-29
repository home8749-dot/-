"""현황판: 무엇이 나왔는지 · 무엇이 필요한지 · 무엇을 해야 하는지.

장부·승인 대기열·산출물 폴더·설정을 읽어 HTML 한 장으로 만든다. 외부 API 는 부르지 않는다.
  python -m survival_agent dashboard   → workspace/dashboard.html
사이클이 끝날 때마다 자동으로 다시 만들어진다.
"""
from __future__ import annotations

import html
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import TIERS, Settings

E = html.escape

# 구축 현황(코드·문서) — 기능이 추가되면 여기에 반영
BUILD = [
    ("생존 루프·장부", "잔고 차감, 정상→절약→위기→사망 단계별 모델 전환", "done"),
    ("편집장 심사", "기획안 6항목 채점, 통과해야 제작", "done"),
    ("쇼츠 제작", "자막 카드 + 선택 음성 → 세로 영상(최대 60초)", "done"),
    ("유튜브 업로드·성과 조회", "AI 제작 표시 자동, 조회수·좋아요·댓글", "unverified"),
    ("인스타 릴스", "같은 영상 재사용, 자체 사이트 경유 공개 주소", "unverified"),
    ("자체 블로그 + 네이버 초안", "GitHub Pages 자동 게시, 네이버는 복사용 초안", "unverified"),
    ("개인정보 3중 차단", "원자료 가림 · AI 지침 · 발행 직전 재검사", "done"),
    ("현황판", "이 화면. 사이클마다 자동 갱신", "done"),
]
BUILD_LABEL = {"done": "구현·테스트 완료", "unverified": "구현 완료 · 실계정 미검증"}
DOCS = ["수익구조_채널설계_v1_20260929.md", "AI자율수익에이전트_실현가능성검토_v2_20260929.md", "README.md"]


# ---------------------------------------------------------------- 수집
def _json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def collect(data_dir: Path, ws_dir: Path, settings: Settings | None = None, env=None, today: date | None = None) -> dict:
    s = settings or Settings.load()
    env = os.environ if env is None else env
    today = today or date.today()
    state = _json(data_dir / "state.json", None)
    ledger = _jsonl(data_dir / "ledger.jsonl")
    approvals = _json(data_dir / "approvals.json", [])
    pub = _jsonl(data_dir / "publish_log.jsonl")
    stats = _json(data_dir / "video_stats.json", {"rows": []})

    snap: dict = {"now": datetime.now().strftime("%Y. %m. %d. %H:%M"), "initialized": state is not None}

    # 상태·생존
    if state:
        ratio = state["balance_krw"] / state["seed_krw"] if state["seed_krw"] else 0
        dead = bool(state.get("died_at")) or state["balance_krw"] <= 0
        tier = None if dead else next((t for t in TIERS if ratio >= t.min_ratio), TIERS[-1])
        snap["state"] = {**state, "ratio": ratio, "dead": dead,
                         "tier": tier.name if tier else "dead", "tier_label": tier.label if tier else "사망",
                         "model": tier.model if tier else "-"}
    # 일별 비용·수익(최근 30일)
    by_day = defaultdict(lambda: [0.0, 0.0])
    for r in ledger:
        d = r["at"][:10]
        if r["type"] == "cost":
            by_day[d][0] += r["krw"]
        elif r["type"] == "revenue":
            by_day[d][1] += r["krw"]
    days = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    snap["series"] = [(d, round(by_day[d][0]), round(by_day[d][1])) for d in days]
    recent = [c for _, c, _ in snap["series"][-7:] if c > 0]
    avg = sum(recent) / len(recent) if recent else 0
    snap["runway_days"] = (state["balance_krw"] / avg) if (state and avg and not snap["state"]["dead"]) else None
    snap["revenues"] = [r for r in ledger if r["type"] == "revenue"][-5:][::-1]

    # 준비 현황
    sources = [p for p in (data_dir / "sources").rglob("*") if p.suffix in {".md", ".txt"}] \
        if (data_dir / "sources").exists() else []
    terms_file = data_dir / "redact_terms.txt"
    terms = [t for t in terms_file.read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")] \
        if terms_file.exists() else []
    yt_ready = (data_dir / "youtube_token.json").exists()
    yt_public = any(r.get("공개상태") == "public" for r in stats.get("rows", []))
    ig_ready = bool(s.ig_user_id and env.get("IG_ACCESS_TOKEN"))
    site_ready = bool(s.site_repo_url and s.site_base_url)
    connected = {"youtube": yt_ready, "instagram": ig_ready, "site": site_ready}
    auto_ok = all(s.autopilot.get(k) for k, v in connected.items() if v) and any(connected.values())
    products_listed = sum(1 for a in approvals if a["kind"] == "list_product" and a["status"] == "done")
    snap["setup"] = [
        # key, 이름, 상태(True/False/None=알 수 없음), 설명, 방법, 필수
        ("api", "Claude API 키", bool(env.get("ANTHROPIC_API_KEY")) or None,
         "에이전트의 두뇌. 콘솔에서 월 사용 한도도 시드 금액으로", "export ANTHROPIC_API_KEY=…", True),
        ("init", "시드 입금", snap["initialized"], "생존 장부 시작", "python -m survival_agent init --seed 100000", True),
        ("sources", f"원자료 {len(sources)}건", len(sources) >= 3, "콘텐츠의 1차 원천. 3건 이상 권장",
         "data/sources/ 에 .md·.txt 넣기", True),
        ("terms", f"금지어 {len(terms)}개", len(terms) > 0, "고객사·수강생 이름 등 자동으로 가릴 단어",
         "data/redact_terms.txt 에 한 줄에 하나", True),
        ("site", "자체 블로그(GitHub Pages)", site_ready, "블로그 글·릴스 영상 공개 주소", "config.json 의 site_repo_url · site_base_url", True),
        ("youtube", "유튜브 계정 연결", yt_ready, "업로드·성과 조회", "python -m survival_agent youtube-auth", True),
        ("audit", "유튜브 API 감사 통과", True if yt_public else None,
         "통과 전 업로드는 비공개로 잠김. 수주 걸릴 수 있어 먼저 신청", "Google 'YouTube API Services 감사 및 할당량 확장' 양식", True),
        ("instagram", "인스타 비즈니스 계정 연결", ig_ready, "릴스 자동 발행", "config.json 의 ig_user_id + IG_ACCESS_TOKEN", False),
        ("tts", "음성(TTS) 키", bool(env.get(s.tts_api_key_env)) or None, "없으면 자막형 무음 영상",
         f"export {s.tts_api_key_env}=…", False),
        ("autopilot", "전자동 켜기", auto_ok, "연결된 채널을 승인 없이 발행", 'config.json 의 "autopilot" 을 true 로', True),
        ("product", f"판매 상품 {products_listed}개 등록", products_listed > 0, "수익 거점. 첫 사이클에서 등록 제안이 올라옴",
         "크몽·스마트스토어에 등록 후 done 으로 기록", True),
    ]

    # 대기열
    pend = [a for a in approvals if a["status"] == "pending"]
    snap["pending"] = [a for a in pend if a["kind"] != "filming"]
    snap["filming"] = [a for a in pend if a["kind"] == "filming"]

    # 산출물
    briefs = {p.stem: _json(p, {}) for p in sorted((ws_dir / "briefs").glob("*.json"))} if (ws_dir / "briefs").exists() else {}
    published = defaultdict(list)
    for r in pub:
        published[r["title"]].append(r)
    stat_by_title = {r["제목"]: r for r in stats.get("rows", [])}
    videos = []
    for v in sorted((ws_dir / "videos").glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True) \
            if (ws_dir / "videos").exists() else []:
        b = briefs.get(v.stem, {})
        last = (b.get("reviews") or [{}])[-1].get("scores", {})
        title = b.get("title", v.stem)
        videos.append({"slug": v.stem, "title": title, "date": datetime.fromtimestamp(v.stat().st_mtime).strftime("%m. %d."),
                       "score": round(sum(last.values()) / len(last), 1) if last else None,
                       "channels": sorted({r["channel"] for r in published.get(title, [])}),
                       "views": stat_by_title.get(title, {}).get("조회수")})
    snap["videos"] = videos
    snap["briefs"] = {"total": len(briefs), "passed": sum(1 for b in briefs.values() if b.get("passed")),
                      "failed": [(k, b.get("title", k), (b.get("reviews") or [{}])[-1].get("feedback", ""))
                                 for k, b in briefs.items() if not b.get("passed")][:5]}
    posts = _json(ws_dir / "site/blog/posts.json", [])
    snap["posts"] = posts[::-1][:8]
    snap["naver_drafts"] = sorted(p.stem for p in (ws_dir / "naver_drafts").glob("*.md")) \
        if (ws_dir / "naver_drafts").exists() else []
    snap["stats_at"] = stats.get("at")
    snap["publish_counts"] = {c: sum(1 for r in pub if r["channel"] == c) for c in ("youtube", "instagram", "site")}

    # 일지 마지막 항목
    j = ws_dir / "생존일지.md"
    if j.exists():
        parts = j.read_text(encoding="utf-8").split("\n## ")
        snap["journal"] = ("## " + parts[-1]).strip()[:1500] if len(parts) > 1 else parts[-1][:1500]
    else:
        snap["journal"] = ""

    snap["todos"] = _todos(snap)
    return snap


def _todos(snap: dict) -> list[tuple[str, str, str]]:
    """(우선순위, 할 일, 방법). now = 오늘, next = 이번 주, opt = 여유 있을 때"""
    out = []
    setup = {k: (label, ok, how, req) for k, label, ok, _, how, req in snap["setup"]}
    first = {"api": "Claude API 키 발급·등록", "init": "시드 입금으로 가동 시작",
             "sources": f"원자료 3건 이상 넣기 (현재 {setup['sources'][0].split()[-1]})", "terms": "금지어 목록 작성 (고객사·수강생 이름)"}
    for k in ("api", "init", "sources", "terms"):
        label, ok, how, _ = setup[k]
        if not ok:
            out.append(("now", first[k], how))
    if not setup["audit"][1]:
        out.append(("now", "유튜브 API 감사 신청 (통과까지 가장 오래 걸림)", setup["audit"][2]))
    for k in ("site", "youtube", "product", "autopilot"):
        label, ok, how, _ = setup[k]
        if not ok:
            out.append(("next", f"{label}", how))
    if snap["pending"]:
        out.append(("now", f"승인 대기 {len(snap['pending'])}건 처리", "python -m survival_agent queue → execute / reject"))
    st = snap.get("state")
    if st and not st["dead"] and st["ratio"] < 0.5:
        out.append(("now", f"잔고 {st['ratio'] * 100:.0f}% — {st['tier_label']} 단계", "수익 입금 기록(revenue) 또는 시드 추가 검토"))
    if snap["initialized"] and setup["api"][1] is not False:
        out.append(("next", "하루 1사이클 실행", "python -m survival_agent run --once  (또는 crontab 자동)"))
    for k in ("instagram", "tts"):
        label, ok, how, _ = setup[k]
        if not ok:
            out.append(("opt", label, how))
    if snap["filming"]:
        out.append(("opt", f"촬영 요청 {len(snap['filming'])}건 (응답 없어도 루틴은 계속)", "python -m survival_agent queue"))
    if snap["naver_drafts"]:
        out.append(("opt", f"네이버 블로그 초안 {len(snap['naver_drafts'])}건 복사 게시", "workspace/naver_drafts/"))
    return out


# ---------------------------------------------------------------- 렌더
STYLE = """
/* 레이아웃: 상단 생존 게이지 → [할 일 | 준비 현황] 2단 → 산출물 → 비용·수익 → 구축 현황 */
:root{
  --bg:#f3f5f7; --panel:#ffffff; --ink:#15202b; --muted:#5b6876; --line:#dbe1e7;
  --accent:#1d4ed8; --accent-soft:#e3eafc;
  --ok:#157347; --ok-soft:#dcf1e5; --warn:#a15c00; --warn-soft:#fdefd6; --crit:#b42318; --crit-soft:#fbe2df;
  --cost:#8a97a6; --rev:#157347;
  --f-display:"IBM Plex Sans KR","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  --f-body:"IBM Plex Sans KR","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  --f-data:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0f151c; --panel:#161e27; --ink:#e4e9ee; --muted:#93a1b0; --line:#27323e;
  --accent:#7aa2ff; --accent-soft:#1c2a4a;
  --ok:#56c48a; --ok-soft:#15301f; --warn:#f0b35a; --warn-soft:#352711; --crit:#ff8a7a; --crit-soft:#3a1714;
  --cost:#5d6b7a; --rev:#56c48a; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0f151c; --panel:#161e27; --ink:#e4e9ee; --muted:#93a1b0; --line:#27323e;
  --accent:#7aa2ff; --accent-soft:#1c2a4a;
  --ok:#56c48a; --ok-soft:#15301f; --warn:#f0b35a; --warn-soft:#352711; --crit:#ff8a7a; --crit-soft:#3a1714;
  --cost:#5d6b7a; --rev:#56c48a; color-scheme:dark}
body{background:var(--bg);color:var(--ink);font:15px/1.6 var(--f-body)}
.wrap{max-width:1120px;margin:0 auto;padding-inline:16px;padding-block:24px 48px;display:grid;gap:20px}
h1,h2{font-family:var(--f-display);text-wrap:balance;margin:0}
h1{font-size:1.45rem;font-weight:700;letter-spacing:-.01em}
h2{font-size:1rem;font-weight:700}
.muted{color:var(--muted)} .num{font-family:var(--f-data);font-variant-numeric:tabular-nums}
.eyebrow{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600}
header.top{display:flex;flex-wrap:wrap;gap:12px 20px;align-items:flex-end;justify-content:space-between}
.tabs{display:flex;gap:4px;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:3px}
.tabs button{font:inherit;font-size:.85rem;border:0;background:transparent;color:var(--muted);padding:6px 12px;border-radius:6px;cursor:pointer}
.tabs button[aria-selected="true"]{background:var(--accent-soft);color:var(--accent);font-weight:600}
.tabs button:focus-visible,.check:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
section.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px;display:grid;gap:14px;min-width:0;align-content:start}
#live,#demo{display:grid;gap:20px}
#live[hidden],#demo[hidden]{display:none}
.grid2{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:20px}
@media (max-width:820px){.grid2{grid-template-columns:1fr}}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:.78rem;font-weight:600;padding:2px 10px;border-radius:999px;white-space:nowrap}
.pill::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.p-ok{background:var(--ok-soft);color:var(--ok)} .p-warn{background:var(--warn-soft);color:var(--warn)}
.p-crit{background:var(--crit-soft);color:var(--crit)} .p-idle{background:var(--accent-soft);color:var(--accent)}
.p-none{background:var(--bg);color:var(--muted);border:1px solid var(--line)}
/* 생존 게이지 */
.vitals{display:grid;grid-template-columns:minmax(0,1.6fr) repeat(3,minmax(0,1fr));gap:20px;align-items:end}
@media (max-width:820px){.vitals{grid-template-columns:1fr 1fr}.vitals .gauge-box{grid-column:1/-1}}
.kpi .v{font-family:var(--f-data);font-size:1.45rem;font-weight:600;font-variant-numeric:tabular-nums;line-height:1.2}
.kpi .l{font-size:.8rem;color:var(--muted)}
.gauge{position:relative;height:14px;background:var(--bg);border:1px solid var(--line);border-radius:7px;margin-top:26px}
.gauge .fill{position:absolute;inset:0 auto 0 0;border-radius:7px}
.gauge .mark{position:absolute;top:-22px;bottom:-4px;border-left:1.5px dashed var(--muted);font-size:.7rem;color:var(--muted);padding-left:4px;white-space:nowrap}
.gauge-legend{display:flex;justify-content:space-between;font-size:.75rem;color:var(--muted);margin-top:6px}
/* 할 일 */
ol.todo{list-style:none;margin:0;padding:0;display:grid;gap:8px}
ol.todo li{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 10px;align-items:start;padding:10px 12px;border:1px solid var(--line);border-radius:8px}
ol.todo .t{font-weight:600} ol.todo code{grid-column:2}
code{font-family:var(--f-data);font-size:.78rem;color:var(--muted);word-break:break-all}
.pri{font-size:.7rem;font-weight:700;padding:2px 7px;border-radius:5px;margin-top:2px}
.pri.now{background:var(--crit-soft);color:var(--crit)} .pri.next{background:var(--warn-soft);color:var(--warn)} .pri.opt{background:var(--bg);color:var(--muted);border:1px solid var(--line)}
/* 준비 현황 */
ul.setup{list-style:none;margin:0;padding:0;display:grid}
ul.setup li{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:10px;align-items:center;padding:9px 0;border-top:1px solid var(--line)}
ul.setup li:first-child{border-top:0}
.dot{width:14px;height:14px;border-radius:50%;border:2px solid var(--line)}
.dot.ok{background:var(--ok);border-color:var(--ok)} .dot.no{border-color:var(--crit)} .dot.unk{border-color:var(--warn);border-style:dashed}
.setup .d{font-size:.8rem;color:var(--muted)}
.opt-tag{font-size:.7rem;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 5px}
/* 표 */
.tablebox{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th{font-size:.72rem;letter-spacing:.06em;color:var(--muted);text-align:left;font-weight:600;padding:6px 8px;border-bottom:1px solid var(--line)}
td{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}
td.r,th.r{text-align:right}
.chip{display:inline-block;font-size:.72rem;padding:1px 7px;border-radius:4px;background:var(--accent-soft);color:var(--accent);margin-right:4px}
.empty{padding:18px;border:1px dashed var(--line);border-radius:8px;color:var(--muted);font-size:.9rem}
.stats3{display:flex;flex-wrap:wrap;gap:8px 24px}
.stats3 div{display:grid} .stats3 b{font-family:var(--f-data);font-size:1.15rem}
/* 차트 */
.chart svg{width:100%;height:auto;display:block}
.chart .axis{stroke:var(--line)} .chart text{fill:var(--muted);font:11px var(--f-data)}
.bar-cost{fill:var(--cost)} .bar-rev{fill:var(--rev)}
.legend{display:flex;gap:16px;font-size:.8rem;color:var(--muted)} .legend span::before{content:"";display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.legend .c::before{background:var(--cost)} .legend .r::before{background:var(--rev)}
.build{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
.build div{border:1px solid var(--line);border-radius:8px;padding:10px 12px;display:grid;gap:4px}
.build b{font-size:.9rem}
pre.journal{white-space:pre-wrap;font-family:var(--f-body);font-size:.88rem;margin:0;color:var(--ink);max-height:280px;overflow:auto}
.demo-note{background:var(--warn-soft);color:var(--warn);border-radius:8px;padding:8px 12px;font-size:.85rem;font-weight:600}
@media (prefers-reduced-motion:no-preference){.gauge .fill{transition:width .6s ease}}
"""


def _won(v: float) -> str:
    return f"{v:,.0f}원"


def _chart(series) -> str:
    W, H, pl, pb, pt = 720, 190, 56, 26, 12
    mx = max([max(c, r) for _, c, r in series] + [1])
    step = 10 ** max(0, len(str(int(mx))) - 1)
    top = ((int(mx) // step) + 1) * step
    ih, iw = H - pb - pt, W - pl - 8
    bw = iw / len(series)
    y = lambda v: pt + ih - (v / top) * ih
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="최근 30일 일별 비용과 수익">']
    for t in (0, top / 2, top):
        parts.append(f'<line class="axis" x1="{pl}" x2="{W - 8}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                     f'<text x="{pl - 6}" y="{y(t) + 4:.1f}" text-anchor="end">{t:,.0f}</text>')
    for i, (d, c, r) in enumerate(series):
        x = pl + i * bw
        w = max(bw / 2 - 1.5, 1)
        if c:
            parts.append(f'<rect class="bar-cost" x="{x + 1:.1f}" y="{y(c):.1f}" width="{w:.1f}" height="{pt + ih - y(c):.1f}" rx="1.5"><title>{d} 비용 {c:,}원</title></rect>')
        if r:
            parts.append(f'<rect class="bar-rev" x="{x + 1 + w + 1:.1f}" y="{y(r):.1f}" width="{w:.1f}" height="{pt + ih - y(r):.1f}" rx="1.5"><title>{d} 수익 {r:,}원</title></rect>')
        if i % 7 == 0 or (i == len(series) - 1 and i % 7 >= 4):
            parts.append(f'<text x="{x + bw / 2:.1f}" y="{H - 8}" text-anchor="middle">{d[5:].replace("-", ".")}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _view(snap: dict, demo: bool = False) -> str:
    st = snap.get("state")
    o = []
    if demo:
        o.append('<p class="demo-note">예시 화면입니다. 가상의 2주 운영 데이터로 만든 모습이며 실제 실적이 아닙니다.</p>')

    # ① 생존 상태
    if st:
        tier_cls = {"normal": "p-ok", "low": "p-warn", "critical": "p-crit", "dead": "p-crit"}[st["tier"]]
        ratio = max(0.0, min(st["ratio"], 1.0))
        fill_col = {"normal": "var(--ok)", "low": "var(--warn)"}.get(st["tier"], "var(--crit)")
        runway = f'{snap["runway_days"]:.0f}일' if snap["runway_days"] else "산출 전"
        net = st["total_revenue_krw"] - st["total_cost_krw"]
        o.append(f'''<section class="panel" aria-label="생존 상태"><div class="vitals">
<div class="gauge-box"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
<span class="pill {tier_cls}">{E(st["tier_label"])} 단계</span><span class="muted" style="font-size:.85rem">모델 {E(st["model"])} · 사이클 {st["cycles"]}회</span></div>
<div class="kpi" style="margin-top:8px"><div class="v">{_won(st["balance_krw"])}</div><div class="l">잔고 / 시드 {_won(st["seed_krw"])} ({st["ratio"] * 100:.0f}%)</div></div>
<div class="gauge"><div class="fill" style="width:{ratio * 100:.1f}%;background:{fill_col}"></div>
<span class="mark" style="left:20%">위기 20%</span><span class="mark" style="left:50%">정상 50%</span></div>
<div class="gauge-legend"><span>0 = 사망</span><span>시드 100%</span></div></div>
<div class="kpi"><div class="v" style="color:var(--rev)">{_won(st["total_revenue_krw"])}</div><div class="l">누적 수익</div></div>
<div class="kpi"><div class="v">{_won(st["total_cost_krw"])}</div><div class="l">누적 비용 · 순손익 {"+" if net >= 0 else "−"}{_won(abs(net))}</div></div>
<div class="kpi"><div class="v">{runway}</div><div class="l">예상 생존 (최근 7일 평균 지출 기준)</div></div>
</div></section>''')
    else:
        o.append('<section class="panel" aria-label="생존 상태"><div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">'
                 '<span class="pill p-idle">가동 전</span><span>아직 시드를 넣지 않았습니다. 준비 항목을 채운 뒤 '
                 '<code>python -m survival_agent init --seed 100000</code> 으로 시작합니다.</span></div></section>')

    # ② 할 일 | 준비 현황
    pri_label = {"now": "지금", "next": "이번 주", "opt": "여유"}
    todo = "".join(f'<li><span class="pri {p}">{pri_label[p]}</span><span class="t">{E(t)}</span><code>{E(h)}</code></li>'
                   for p, t, h in snap["todos"]) or '<li><span class="pri opt">완료</span><span class="t">지금 할 일이 없습니다. 에이전트가 매일 돌고 있습니다.</span></li>'
    done_n = sum(1 for _, _, ok, _, _, req in snap["setup"] if ok and req)
    req_n = sum(1 for *_, req in snap["setup"] if req)
    rows = []
    for key, label, ok, desc, how, req in snap["setup"]:
        cls, txt = ("ok", "완료") if ok else (("unk", "확인 필요") if ok is None else ("no", "필요"))
        pcls = {"ok": "p-ok", "unk": "p-warn", "no": "p-none" if not req else "p-crit"}[cls]
        rows.append(f'<li><span class="dot {cls}" aria-hidden="true"></span><div><div>{E(label)} '
                    f'{"" if req else "<span class=opt-tag>선택</span>"}</div><div class="d">{E(desc)}</div></div>'
                    f'<span class="pill {pcls}">{txt}</span></li>')
    o.append(f'''<div class="grid2">
<section class="panel"><div><div class="eyebrow">해야 할 일</div><h2>우선순위 순</h2></div><ol class="todo">{todo}</ol></section>
<section class="panel"><div><div class="eyebrow">필요한 것</div><h2>준비 현황 <span class="num muted" style="font-weight:500">{done_n}/{req_n} 필수 완료</span></h2></div>
<ul class="setup">{"".join(rows)}</ul></section></div>''')

    # ③ 산출물
    b = snap["briefs"]
    pc = snap["publish_counts"]
    ch_name = {"youtube": "유튜브", "instagram": "인스타", "site": "블로그"}
    vid_rows = []
    for v in snap["videos"]:
        chips = "".join(f'<span class="chip">{ch_name[c]}</span>' for c in v["channels"]) or '<span class="muted">미발행</span>'
        score = v["score"] if v["score"] is not None else "-"
        views = f'{v["views"]:,}' if v["views"] is not None else "-"
        vid_rows.append(f'<tr><td class="num">{E(v["date"])}</td><td>{E(v["title"])}<div class="muted" style="font-size:.78rem">{E(v["slug"])}</div></td>'
                        f'<td class="r num">{score}</td><td>{chips}</td><td class="r num">{views}</td></tr>')
    vid_rows = "".join(vid_rows)
    videos = (f'<div class="tablebox"><table><thead><tr><th>제작일</th><th>영상</th><th class="r">심사 평균</th><th>발행</th>'
              f'<th class="r">조회수</th></tr></thead><tbody>{vid_rows}</tbody></table></div>') if snap["videos"] else \
        '<div class="empty">아직 만든 영상이 없습니다. 첫 사이클에서 기획안이 편집장 심사를 통과하면 여기에 쌓입니다.</div>'
    posts = "".join(f'<li>{E(p["title"])} <span class="muted num">{E(p["date"])}</span></li>' for p in snap["posts"])
    fails = "".join(f'<li><b>{E(t)}</b> <span class="muted">— {E(fb[:90])}</span></li>' for _, t, fb in b["failed"])
    stats_note = f' · 조회수 기준 {E(snap["stats_at"][:16].replace("T", " "))}' if snap.get("stats_at") else ""
    o.append(f'''<section class="panel"><div><div class="eyebrow">나온 것</div><h2>산출물</h2></div>
<div class="stats3"><div><b>{len(snap["videos"])}</b><span class="muted">쇼츠 제작</span></div>
<div><b>{b["passed"]}/{b["total"]}</b><span class="muted">기획안 심사 통과</span></div>
<div><b>{pc["youtube"]}</b><span class="muted">유튜브 발행</span></div><div><b>{pc["instagram"]}</b><span class="muted">인스타 발행</span></div>
<div><b>{len(snap["posts"])}</b><span class="muted">블로그 글</span></div><div><b>{len(snap["naver_drafts"])}</b><span class="muted">네이버 초안</span></div></div>
{videos}<div class="muted" style="font-size:.78rem">심사 평균은 6항목 1∼5점{stats_note}</div>
<div class="grid2"><div style="min-width:0"><h2 style="font-size:.9rem;margin-bottom:6px">최근 블로그 글</h2>{f"<ul style='margin:0;padding-left:18px'>{posts}</ul>" if posts else "<div class=empty>아직 없음</div>"}</div>
<div style="min-width:0"><h2 style="font-size:.9rem;margin-bottom:6px">심사 탈락 기획안</h2>{f"<ul style='margin:0;padding-left:18px'>{fails}</ul>" if fails else "<div class=empty>없음</div>"}</div></div></section>''')

    # ④ 비용·수익
    has_money = any(c or r for _, c, r in snap["series"])
    rev = "".join(f'<li><span class="num">{E(r["at"][:10])}</span> {_won(r["krw"])} <span class="muted">{E(r["memo"])}</span></li>'
                  for r in snap["revenues"])
    o.append(f'''<section class="panel"><div><div class="eyebrow">돈의 흐름</div><h2>최근 30일 일별 비용·수익</h2></div>
{('<div class="chart">' + _chart(snap["series"]) + '</div><div class="legend"><span class="c">AI·음성 비용</span><span class="r">실제 입금 수익</span></div>') if has_money else '<div class="empty">가동 후 매일의 AI 사용료와 입금 수익이 막대로 쌓입니다.</div>'}
{f"<div><h2 style='font-size:.9rem;margin-bottom:6px'>최근 수익</h2><ul style='margin:0;padding-left:18px'>{rev}</ul></div>" if rev else ""}</section>''')

    # ⑤ 일지
    if snap["journal"]:
        o.append(f'<section class="panel"><div><div class="eyebrow">에이전트 기억</div><h2>최근 생존일지</h2></div>'
                 f'<pre class="journal">{E(snap["journal"])}</pre></section>')

    # ⑥ 구축 현황
    blds = "".join(f'<div><b>{E(n)}</b><span class="muted" style="font-size:.82rem">{E(d)}</span>'
                   f'<span class="pill {"p-ok" if s == "done" else "p-warn"}" style="justify-self:start">{BUILD_LABEL[s]}</span></div>'
                   for n, d, s in BUILD)
    docs = " · ".join(f"<code>{E(d)}</code>" for d in DOCS)
    o.append(f'''<section class="panel"><div><div class="eyebrow">시스템</div><h2>구축 현황</h2></div><div class="build">{blds}</div>
<div class="muted" style="font-size:.82rem">문서: {docs}</div></section>''')
    return "\n".join(o)


def render_fragment(snap: dict, demo: dict | None = None) -> str:
    head = ('<title>생존 에이전트 현황판</title>\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap">'
            f'<style>{STYLE}</style>')
    tabs = ""
    if demo is not None:
        tabs = ('<div class="tabs" role="tablist"><button role="tab" id="tab-live" aria-selected="true" aria-controls="live">현재 상태</button>'
                '<button role="tab" id="tab-demo" aria-selected="false" aria-controls="demo">가동 후 예시</button></div>')
    top = (f'<header class="top"><div><div class="eyebrow">정부지원사업 실무 콘텐츠 · 생존형 수익 에이전트</div>'
           f'<h1>생존 에이전트 현황판</h1><div class="muted" style="font-size:.85rem">기준 {E(snap["now"])}</div></div>{tabs}</header>')
    body = f'<div id="live" role="tabpanel">{_view(snap)}</div>'
    script = ""
    if demo is not None:
        body += f'<div id="demo" role="tabpanel" hidden>{_view(demo, demo=True)}</div>'
        script = """<script>
(function(){var t={live:document.getElementById('tab-live'),demo:document.getElementById('tab-demo')};
function show(k){for(var n in t){var on=n===k;t[n].setAttribute('aria-selected',on);document.getElementById(n).hidden=!on;}
try{localStorage.setItem('dash-tab',k)}catch(e){}}
t.live.onclick=function(){show('live')};t.demo.onclick=function(){show('demo')};
var k=location.hash==='#demo'?'demo':null;if(!k){try{k=localStorage.getItem('dash-tab')}catch(e){}}
if(k==='demo')show('demo');})();
</script>"""
    return f'{head}\n<main class="wrap">{top}{body}</main>{script}'


def render_document(snap: dict, demo: dict | None = None) -> str:
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'{render_fragment(snap, demo)}</html>')


def write(data_dir: Path, ws_dir: Path, settings: Settings | None = None) -> Path:
    ws_dir.mkdir(parents=True, exist_ok=True)
    out = ws_dir / "dashboard.html"
    out.write_text(render_document(collect(data_dir, ws_dir, settings)), encoding="utf-8")
    return out


# ---------------------------------------------------------------- 예시 데이터
def build_demo(root: Path, today: date | None = None) -> dict:
    """가상의 2주 운영 상태를 만들어 스냅샷을 돌려준다(현황판 예시·테스트용)."""
    today = today or date.today()
    data, ws = root / "data", root / "workspace"
    for d in (data / "sources", ws / "videos", ws / "briefs", ws / "site/blog", ws / "naver_drafts"):
        d.mkdir(parents=True, exist_ok=True)
    ts = lambda n, h=9: (datetime.combine(today - timedelta(days=n), datetime.min.time()) + timedelta(hours=h)).isoformat(timespec="seconds")
    ledger, cost_total = [{"at": ts(14), "type": "seed", "krw": 100000, "memo": "시드 입금"}], 0
    daily = [2400, 2650, 2100, 2800, 2300, 1900, 2550, 2200, 2450, 2050, 2700, 2350, 2150, 2500]
    for i, c in enumerate(daily):
        ledger.append({"at": ts(13 - i, 9), "type": "cost", "krw": c, "memo": "사이클"})
        cost_total += c
    revs = [(3, 29000, "크몽 · 예비창업패키지 작성 가이드 1건")]
    for n, k, m in revs:
        ledger.append({"at": ts(n, 15), "type": "revenue", "krw": k, "memo": m})
    rev_total = sum(k for _, k, _ in revs)
    (data / "ledger.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ledger), encoding="utf-8")
    (data / "state.json").write_text(json.dumps({
        "seed_krw": 100000, "balance_krw": 100000 - cost_total + rev_total, "born_at": ts(14), "died_at": None,
        "cycles": 14, "total_cost_krw": cost_total, "total_revenue_krw": rev_total, "last_cycle_at": ts(0)}), encoding="utf-8")
    for i in range(6):
        (data / "sources" / f"자료{i}.md").write_text("예시", encoding="utf-8")
    (data / "redact_terms.txt").write_text("고객사A\n수강생B\n", encoding="utf-8")
    (data / "youtube_token.json").write_text("{}", encoding="utf-8")
    titles = [("docs-3", "예비창업패키지, 서류 3개만 먼저", 4.2, 1840), ("fail-reason", "서류 탈락 1위는 이것", 4.0, 3120),
              ("bm-one-line", "사업모델 한 줄로 쓰는 법", 3.8, 960), ("budget-table", "사업비 표, 이렇게 쪼개면 통과", 3.7, 610),
              ("pitch-3min", "발표평가 3분 구조", 3.9, 1270)]
    pub, stat_rows = [], []
    for i, (slug, title, score, views) in enumerate(titles):
        (ws / "videos" / f"{slug}.mp4").write_bytes(b"demo")
        os.utime(ws / "videos" / f"{slug}.mp4", (0, datetime.fromisoformat(ts(i * 2)).timestamp()))
        (ws / "briefs" / f"{slug}.json").write_text(json.dumps({"title": title, "passed": True, "reviews": [
            {"scores": {k: round(score) for k in ("demand", "viewer", "hook", "originality", "payoff", "product_fit")}}]},
            ensure_ascii=False), encoding="utf-8")
        pub.append({"at": ts(i * 2, 10), "channel": "youtube", "title": title, "result": f"https://youtube.com/shorts/demo{i}"})
        pub.append({"at": ts(i * 2, 10), "channel": "instagram", "title": title, "result": f"1790000{i}"})
        stat_rows.append({"제목": title, "조회수": views, "공개상태": "public"})
    (ws / "briefs" / "grant-myths.json").write_text(json.dumps({"title": "지원사업 오해 5가지", "passed": False, "reviews": [
        {"scores": {"demand": 2}, "feedback": "수요 근거가 추측뿐. 실제 검색량·유사 영상 조회수 근거 필요"}]}, ensure_ascii=False),
        encoding="utf-8")
    (data / "publish_log.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in pub), encoding="utf-8")
    (data / "video_stats.json").write_text(json.dumps({"at": ts(0, 8), "rows": stat_rows}, ensure_ascii=False), encoding="utf-8")
    (ws / "site/blog/posts.json").write_text(json.dumps([{"slug": s, "title": t, "date": (today - timedelta(days=i * 2)).strftime("%Y. %m. %d.")}
                                                          for i, (s, t, _, _) in enumerate(titles)][::-1], ensure_ascii=False), encoding="utf-8")
    for s, *_ in titles[:2]:
        (ws / "naver_drafts" / f"{s}.md").write_text("초안", encoding="utf-8")
    (data / "approvals.json").write_text(json.dumps([
        {"id": 1, "kind": "list_product", "title": "예비창업패키지 작성 가이드 등록", "channel": "크몽", "detail": "", "status": "done",
         "expected_revenue_krw": 29000, "cost_krw": 0, "note": "등록 완료"},
        {"id": 2, "kind": "filming", "title": "발표평가 실전 롱폼(대표 출연)", "channel": "유튜브", "detail": "대본 첨부", "status": "pending",
         "expected_revenue_krw": 0, "cost_krw": 0, "note": ""}], ensure_ascii=False), encoding="utf-8")
    (ws / "생존일지.md").write_text(
        f"\n\n## {(today).strftime('%Y. %m. %d.')} 09:12 (사이클 14)\n\n"
        "- 조회수 상위 2편 공통점: 첫 장면이 '탈락·실수' 같은 손실 표현 → 다음 3편도 손실 프레임으로 검증\n"
        "- 오늘: '사업비 표' 영상 후속으로 인건비 산정 요령 쇼츠 + 블로그 1편\n"
        "- 첫 가이드 판매 1건은 블로그 경유 추정 → 블로그 글 하단 상품 링크 위치를 본문 중간으로 이동 제안\n",
        encoding="utf-8")
    s = Settings(site_repo_url="git@github.com:demo/demo.github.io.git", site_base_url="https://demo.github.io",
                 ig_user_id="178000", autopilot={"youtube": True, "instagram": True, "site": True})
    snap = collect(data, ws, s, env={"ANTHROPIC_API_KEY": "x", "IG_ACCESS_TOKEN": "x"}, today=today)
    return snap
