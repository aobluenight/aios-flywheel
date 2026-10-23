# -*- coding: utf-8 -*-
"""core.ledger —— 增量台账 + 覆盖保护（件套②，稳定层）。

防的是"静默劣化"（真实判例：自反馈飞轮把历史数据吃掉，无人察觉）：

1. **AppendLedger**：只增不覆盖的 JSONL 台账。append 校验结构、自动盖时间戳与
   schema_version（向前兼容），绝不改写已有行。
2. **guard_overwrite**：任何"写文件"动作过闸，三种策略——
   refuse（已存在即拒，默认）/ sidecar（写到带时间戳的兄弟文件）/ backup（旧文件挪 .bak 后再写）。
   直接 truncate 覆盖在这个库里没有语法——想覆盖必须显式选策略并留下痕迹。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

SCHEMA_VERSION = 1

POLICY_REFUSE = "refuse"
POLICY_SIDECAR = "sidecar"
POLICY_BACKUP = "backup"
POLICIES = (POLICY_REFUSE, POLICY_SIDECAR, POLICY_BACKUP)


def _ts() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def guard_overwrite(path: Path, text: str, policy: str = POLICY_REFUSE) -> Path:
    """受保护的写文件。返回实际写入的路径。

    - refuse：目标已存在 → FileExistsError（调用方自己决定怎么办）
    - sidecar：目标已存在 → 写到 <name>.<ts>.new，原文件不动
    - backup：目标已存在 → 旧文件先挪 <name>.<ts>.bak，再写原路径
    """
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path
    if policy == POLICY_REFUSE:
        raise FileExistsError(f"覆盖保护触发（policy=refuse）: {path} 已存在；换 sidecar/backup 或显式确认")
    if policy == POLICY_SIDECAR:
        side = path.with_name(f"{path.name}.{_ts()}.new")
        side.write_text(text, encoding="utf-8")
        return side
    if policy == POLICY_BACKUP:
        bak = path.with_name(f"{path.name}.{_ts()}.bak")
        path.rename(bak)
        path.write_text(text, encoding="utf-8")
        return path
    raise ValueError(f"未知覆盖策略: {policy}（可选 {POLICIES}）")


class AppendLedger:
    """JSONL 只增台账。

    entry 会被加上 `ts`（ISO 时间）与 `schema_version`；已有行永不改写。
    用在：坑档案取号、产线增量计数、判例回流——一切"历史不可变"的账。
    """

    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, entry: dict) -> dict:
        if not isinstance(entry, dict):
            raise TypeError("entry 必须是 dict")
        if "ts" in entry or "schema_version" in entry:
            raise ValueError("ts / schema_version 为保留字段，禁止自带")
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "schema_version": SCHEMA_VERSION, **entry}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def entries(self) -> list[dict]:
        if not self.path.is_file():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def last(self, n: int = 1) -> list[dict]:
        return self.entries()[-n:]

    def count(self) -> int:
        return len(self.entries())
