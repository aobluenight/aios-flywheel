# -*- coding: utf-8 -*-
"""tools/ledger.py —— 增量台账 + 覆盖保护 CLI（件套②）。

用法::
    python tools/ledger.py append <ledger.jsonl> --kind pit --text "..."   # 记一笔
    python tools/ledger.py list <ledger.jsonl> [--last 5]
    python tools/ledger.py write <file> --text "..." [--policy refuse|sidecar|backup]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.ledger import AppendLedger, guard_overwrite, POLICIES  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_a = sub.add_parser("append")
    ap_a.add_argument("ledger")
    ap_a.add_argument("--kind", required=True, help="条目类型，如 pit/case/gap")
    ap_a.add_argument("--text", required=True)
    ap_a.add_argument("--ref", default="", help="回溯指针：判例编号/文件路径")

    ap_l = sub.add_parser("list")
    ap_l.add_argument("ledger")
    ap_l.add_argument("--last", type=int, default=10)

    ap_w = sub.add_parser("write")
    ap_w.add_argument("file")
    ap_w.add_argument("--text", required=True)
    ap_w.add_argument("--policy", default="refuse", choices=POLICIES)

    a = ap.parse_args()
    if a.cmd == "append":
        rec = AppendLedger(Path(a.ledger)).append({"kind": a.kind, "text": a.text, "ref": a.ref})
        print(f"appended #{rec['ts']} -> {a.ledger}")
    elif a.cmd == "list":
        es = AppendLedger(Path(a.ledger)).last(a.last)
        for e in es:
            print(f"[{e['ts']}] {e.get('kind','?')}: {e.get('text','')[:80]}"
                  + (f" (ref={e['ref']})" if e.get("ref") else ""))
        print(f"-- {len(es)} shown")
    elif a.cmd == "write":
        out = guard_overwrite(Path(a.file), a.text, a.policy)
        print(f"wrote -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
