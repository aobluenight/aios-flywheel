# -*- coding: utf-8 -*-
"""tools/triage.py —— 变更分级闸门 CLI（件套④）。

用法::
    python tools/triage.py --rules config/triage.yaml --git         # git 变更集分诊
    python tools/triage.py --rules config/triage.yaml --paths a b   # 手工给文件清单

退出码：0=pass/notice（notice 有提示）；2=block（须人工确认）。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from core.triage import classify, load_triage, LEVEL_BLOCK, LEVEL_NOTICE  # noqa: E402


def git_changed(root: Path) -> list[str]:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                         capture_output=True, text=True, check=True).stdout
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        f = line[3:].strip().strip('"')
        if f.endswith("/"):
            continue  # 未跟踪目录让用户展开后再报
        files.append(f)
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", required=True)
    ap.add_argument("--git", action="store_true")
    ap.add_argument("--paths", nargs="*")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root).resolve()

    cfg = yaml.safe_load(Path(a.rules).read_text(encoding="utf-8")) or {}
    _, _, _, msgs = load_triage(cfg)
    paths = git_changed(root) if a.git else (a.paths or [])
    if not paths:
        print("no changed files")
        return 0

    res = classify(paths, cfg, root=root)
    for rel, layer, level in res.assignments:
        print(f"[{level.upper():6}] {rel}  ({layer})")
    if res.notice:
        print(f"NOTICE: {msgs[LEVEL_NOTICE]}")
    if res.block:
        print(f"BLOCK: {msgs[LEVEL_BLOCK]}")
        for rel, layer in res.block:
            print(f"  - {rel} ({layer})")
    print(f"-- overall={res.level} files={len(res.assignments)}")
    return 2 if res.level == LEVEL_BLOCK else 0


if __name__ == "__main__":
    sys.exit(main())
