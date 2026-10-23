# -*- coding: utf-8 -*-
"""tools/decision.py —— 拍板台账 CLI（件套⑤）。

人在环 RSI 的 reward model + 安全闸落地形态：每个决策一笔，可回溯、可对账。

用法::
    python tools/decision.py add --decision "..." --why "..." --scope "..." [--ledger path]
    python tools/decision.py list [--ledger path] [--last 5]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.ledger import AppendLedger  # noqa: E402

REQUIRED = ("decision", "why", "scope")


def next_id(entries: list) -> str:
    import time
    today = time.strftime("%Y%m%d")
    n = sum(1 for e in entries if str(e.get("id", "")).startswith(f"D-{today}"))
    return f"D-{today}-{n + 1:02d}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default="docs/decisions.jsonl")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_a = sub.add_parser("add")
    ap_a.add_argument("--decision", required=True, help="拍板内容（一句话）")
    ap_a.add_argument("--why", required=True, help="理由/背景")
    ap_a.add_argument("--scope", required=True, help="影响范围")
    ap_a.add_argument("--reversible", default="true", choices=["true", "false"])
    ap_a.add_argument("--ref", default="", help="对账指针：档/工单/commit")

    ap_l = sub.add_parser("list")
    ap_l.add_argument("--last", type=int, default=10)

    a = ap.parse_args()
    led = AppendLedger(Path(ROOT) / a.ledger)
    if a.cmd == "add":
        rec = led.append({
            "id": next_id(led.entries()),
            "decision": a.decision, "why": a.why, "scope": a.scope,
            "reversible": a.reversible == "true", "ref": a.ref,
        })
        print(f"recorded {rec['id']}: {rec['decision']}")
    else:
        es = led.last(a.last)
        for e in es:
            rev = "reversible" if e.get("reversible") else "one-way"
            print(f"[{e['id']} {e['ts'][:10]}] {e['decision']} ({rev}, scope={e['scope']})"
                  + (f" ref={e['ref']}" if e.get("ref") else ""))
        print(f"-- {len(es)} shown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
