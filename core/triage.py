# -*- coding: utf-8 -*-
"""core.triage —— 变更分级闸门（件套④，稳定层）。

每次变更先分诊：动的是哪一层，就给哪一级预警。
分级规则全在 yaml（顺序匹配，先中先用）；契约文件一票否决为 block。

契约 v1::
    layers:                       # 有序，先中先用
      - name: config              # 层名（展示用）
        level: pass|notice|block  # 预警级
        patterns: ["config/**"]   # glob 列表
    contract_files: ["..."]       # 显式契约清单，任何命中直接 block（优先于 layers）
    default_layer: script         # 都不匹配时的兜底层名（该层必须存在）
    messages: {notice: ..., block: ...}   # 展示话术，可覆盖

级别语义（对齐迭代安全机制）：
    pass   只动配置/数值表，直接放行
    notice 触及脚本层——提示"考虑降级为配置"，人工过目
    block  触及稳定层/接口契约——冻结期内禁改，须人工确认+影响评估
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

LEVEL_PASS = "pass"
LEVEL_NOTICE = "notice"
LEVEL_BLOCK = "block"

DEFAULT_MESSAGES = {
    LEVEL_NOTICE: "触及脚本层：考虑降级为配置（阈值/规则/流程分支优先走 yaml）",
    LEVEL_BLOCK: "触及稳定层/接口契约：冻结期内禁改；需人工确认并附影响评估",
}


def _match(rel: str, patterns: list) -> bool:
    for pat in patterns:
        p = pat.replace("\\", "/")
        if fnmatch.fnmatch(rel, p):
            return True
        if p.startswith("**/"):
            short = p[3:]
            if fnmatch.fnmatch(rel, short) or rel_path_eq(rel, short):
                return True
    return False


def rel_path_eq(a: str, b: str) -> bool:
    return Path(a) == Path(b)


@dataclass
class TriageResult:
    assignments: list = field(default_factory=list)  # (rel_path, layer_name, level)
    notice: list = field(default_factory=list)
    block: list = field(default_factory=list)

    @property
    def level(self) -> str:
        if self.block:
            return LEVEL_BLOCK
        if self.notice:
            return LEVEL_NOTICE
        return LEVEL_PASS

    @property
    def ok(self) -> bool:
        return self.level != LEVEL_BLOCK


def load_triage(cfg: dict):
    """返回 (layers, contract_files, default_layer, messages)。校验 default_layer 存在。"""
    layers = cfg.get("layers") or []
    if not layers:
        raise ValueError("triage 配置缺 layers")
    names = {l["name"] for l in layers}
    default = cfg.get("default_layer") or layers[0]["name"]
    if default not in names:
        raise ValueError(f"default_layer={default} 不在 layers 里")
    msgs = dict(DEFAULT_MESSAGES)
    msgs.update(cfg.get("messages") or {})
    return layers, list(cfg.get("contract_files") or []), default, msgs


def classify(paths: list, cfg: dict, root: Path | None = None) -> TriageResult:
    layers, contracts, default, _msgs = load_triage(cfg)
    res = TriageResult()
    for raw in paths:
        p = Path(raw)
        rel = str(p).replace("\\", "/")
        if root is not None:
            try:
                rel = str(p.resolve().relative_to(Path(root).resolve())).replace("\\", "/")
            except ValueError:
                pass
        # 契约一票否决
        if any(rel_path_eq(rel, c.replace("\\", "/")) or rel == c.replace("\\", "/") for c in contracts):
            res.assignments.append((rel, "contract", LEVEL_BLOCK))
            res.block.append((rel, "contract"))
            continue
        level, layer_name = None, None
        for l in layers:
            if _match(rel, l.get("patterns") or []):
                layer_name, level = l["name"], l.get("level", LEVEL_NOTICE)
                break
        if layer_name is None:
            layer_name, level = default, dict(
                (l["name"], l.get("level", LEVEL_NOTICE)) for l in layers)[default]
        res.assignments.append((rel, layer_name, level))
        if level == LEVEL_BLOCK:
            res.block.append((rel, layer_name))
        elif level == LEVEL_NOTICE:
            res.notice.append((rel, layer_name))
    return res
