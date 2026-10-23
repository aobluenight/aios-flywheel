# -*- coding: utf-8 -*-
"""tools/pit_gate.py —— 坑→门禁 CLI（件套③）。

用法::
    python tools/pit_gate.py --rules config/gates.yaml --scan <dir>     # 扫目录
    python tools/pit_gate.py --rules config/gates.yaml --paths a.lua b/ # 扫指定文件

退出码：0=过闸（warn 不算拦）；1=有 block 命中。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from core.gate import load_rules, run_gate, scan_tree  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", required=True)
    ap.add_argument("--scan", default=None, help="目录扫描模式")
    ap.add_argument("--paths", nargs="*", default=None, help="指定文件模式")
    ap.add_argument("--root", default=".", help="相对路径基准")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    rules = load_rules(yaml.safe_load(Path(a.rules).read_text(encoding="utf-8")) or {})
    rep = (scan_tree(rules, Path(a.scan).resolve())
           if a.scan else run_gate(rules, [Path(p) for p in (a.paths or [])], root))

    for f, rule, sample in rep.blocked:
        print(f"BLOCK {f} <- {rule}\n  ...{sample}...")
    for f, rule, sample in rep.warned:
        print(f"WARN  {f} <- {rule}\n  ...{sample}...")
    for r in rules:
        hits = sum(1 for _, n, _ in rep.blocked + rep.warned if n == r.name)
        if r.message and hits:
            print(f"  [{r.name}] {r.message}")
    print(f"-- scanned={rep.scanned} blocked={len(rep.blocked)} warned={len(rep.warned)}")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
