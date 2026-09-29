"""CLI.

  python -m survival_agent init --seed 50000      시드 입금(최초 1회)
  python -m survival_agent status                  잔고·단계·승인대기 보기
  python -m survival_agent run --once              사이클 1회
  python -m survival_agent run                     단계별 간격으로 계속 실행
  python -m survival_agent queue                   승인 대기열
  python -m survival_agent approve 3 [--note ..]   승인(= 내가 실행하겠다)
  python -m survival_agent reject 3 --note "이유"  거절(이유는 에이전트가 읽음)
  python -m survival_agent done 3 --note "결과"    실행 완료 + 결과 메모
  python -m survival_agent revenue 9900 "크몽 판매 1건"   실제 입금액 기록
  python -m survival_agent execute 5               실행 준비된 제안(유튜브 업로드·사이트 배포)을 한 줄로 실행
  python -m survival_agent youtube-auth            유튜브 계정 연결(최초 1회)
"""
from __future__ import annotations

import argparse
import sys

from .agent import SurvivalAgent
from .approvals import KIND_LABEL, Approvals
from .channels import Channels, youtube
from .config import DATA_DIR, WORKSPACE_DIR, Settings
from .ledger import Ledger
from .tools import ToolBox


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="survival_agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("--seed", type=int, default=Settings().seed_krw)
    sub.add_parser("status")
    p = sub.add_parser("run"); p.add_argument("--once", action="store_true")
    sub.add_parser("queue")
    for name in ("approve", "reject", "done"):
        p = sub.add_parser(name); p.add_argument("id", type=int); p.add_argument("--note", default="")
    p = sub.add_parser("revenue"); p.add_argument("krw", type=int); p.add_argument("memo")
    p = sub.add_parser("execute"); p.add_argument("id", type=int)
    sub.add_parser("youtube-auth")
    a = ap.parse_args(argv)

    settings = Settings.load()
    ledger, approvals = Ledger(settings=settings), Approvals()
    channels = Channels(settings, ledger, approvals, WORKSPACE_DIR, DATA_DIR)
    if a.cmd == "youtube-auth":
        youtube.authorize(DATA_DIR)
        print("유튜브 인증 완료 → data/youtube_token.json")
        return 0
    if a.cmd == "init":
        Settings.load().save()
        ledger.init(a.seed)
        print(f"시드 {a.seed:,}원 입금. 설정은 data/config.json 에서 조정")
        return 0
    if not ledger.exists():
        print("먼저 init 실행: python -m survival_agent init --seed 50000")
        return 1

    if a.cmd == "status":
        s, t = ledger.state(), ledger.tier()
        print(f"단계 {t.label if t else '사망'} | 잔고 {s['balance_krw']:,.0f}원 / 시드 {s['seed_krw']:,}원")
        print(f"누적 비용 {s['total_cost_krw']:,.0f}원 | 누적 수익 {s['total_revenue_krw']:,.0f}원 | 사이클 {s['cycles']}회")
        pending = [i for i in approvals.all() if i["status"] == "pending"]
        print(f"승인 대기 {len(pending)}건")
    elif a.cmd == "queue":
        for i in approvals.all():
            print(f"#{i['id']} [{i['status']}] {KIND_LABEL.get(i['kind'], i['kind'])} · {i['channel']} · {i['title']}"
                  f" (기대 {i['expected_revenue_krw']:,}원 / 비용 {i['cost_krw']:,}원)")
            print("   " + i["detail"].replace("\n", "\n   "))
            if i["note"]:
                print(f"   메모: {i['note']}")
    elif a.cmd in ("approve", "reject", "done"):
        status = {"approve": "approved", "reject": "rejected", "done": "done"}[a.cmd]
        try:
            it = approvals.set_status(a.id, status, a.note)
        except KeyError as e:
            print(e.args[0])
            return 1
        print(f"#{it['id']} → {status}")
    elif a.cmd == "execute":
        try:
            it = approvals.get(a.id)
        except KeyError as e:
            print(e.args[0])
            return 1
        if not it.get("payload"):
            print("실행 준비된 제안이 아님 → 직접 실행 후 `done` 으로 결과 기록")
            return 1
        result = channels.execute(it["payload"])
        approvals.set_status(a.id, "done", result)
        print(result)
    elif a.cmd == "revenue":
        s = ledger.add_revenue(a.krw, a.memo)
        print(f"수익 +{a.krw:,}원 기록 → 잔고 {s['balance_krw']:,.0f}원")
    elif a.cmd == "run":
        agent = SurvivalAgent(ledger, approvals, ToolBox(ledger, approvals, channels=channels))
        if a.once:
            agent.run_cycle()
        else:
            agent.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
