# -*- coding: utf-8 -*-
"""core.gate —— 坑→门禁运行器（件套③，稳定层）。

把事故教训变成机器拦的闸：规则 = 正则 + 作用域(glob) + 严重级(block/warn)。
规则本身在 yaml（配置优先），本层只认契约并跑闸。

契约 v1（yaml rules[] 每条）::
    name:      规则名（必填）
    pattern:   正则（必填，re.search 语义）
    scope:     glob 列表（相对路径匹配；缺省 "**/*"）
    severity:  block（命中即拦截，退出码 1）| warn（提示不拦）
    message:   命中时给人看的话——必须写清是哪个坑、先例编号

设计纪律：门禁规则永远由坑档案沉淀而来（规则里必须能回溯到判例），
禁凭空发明规则——没有事故背书的规则只会训练人绕过门禁。
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

SEVERITY_BLOCK = "block"
SEVERITY_WARN = "warn"


@dataclass
class GateRule:
    name: str
    pattern: re.Pattern
    scope: list = field(default_factory=lambda: ["**/*"])
    severity: str = SEVERITY_WARN
    message: str = ""

    @classmethod
    def from_spec(cls, spec: dict, index: int) -> "GateRule":
        for key in ("name", "pattern"):
            if not spec.get(key):
                raise ValueError(f"规则#{index} 缺必填字段 {key}")
        return cls(
            name=spec["name"],
            pattern=re.compile(spec["pattern"]),
            scope=list(spec.get("scope") or ["**/*"]),
            severity=spec.get("severity", SEVERITY_WARN),
            message=spec.get("message", ""),
        )


def _scope_match(rel_path: str, scope: list) -> bool:
    for pat in scope:
        p = pat.replace("\\", "/")
        if fnmatch.fnmatch(rel_path, p):
            return True
        if p.startswith("**/"):
            short = p[3:]
            if fnmatch.fnmatch(rel_path, short) or rel_path == short:
                return True
    return False


@dataclass
class GateReport:
    scanned: int = 0
    blocked: list = field(default_factory=list)   # (file, rule, match_sample)
    warned: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blocked


def load_rules(cfg: dict) -> list[GateRule]:
    return [GateRule.from_spec(s, i) for i, s in enumerate(cfg.get("rules") or [])]


def run_gate(rules: list[GateRule], paths: list[Path], root: Path) -> GateReport:
    """对给定文件逐个过闸。二进制/不可读文件跳过（门禁不背读取事故）。"""
    rep = GateReport()
    for p in paths:
        p = Path(p)
        try:
            rel = str(p.resolve().relative_to(Path(root).resolve())).replace("\\", "/")
        except ValueError:
            rel = str(p).replace("\\", "/")
        rules_hit = [r for r in rules if _scope_match(rel, r.scope)]
        if not rules_hit:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        rep.scanned += 1
        for r in rules_hit:
            m = r.pattern.search(text)
            if not m:
                continue
            sample = text[max(0, m.start() - 20):m.end() + 20].replace("\n", "\\n")
            item = (rel, r.name, sample)
            (rep.blocked if r.severity == SEVERITY_BLOCK else rep.warned).append(item)
    return rep


def scan_tree(rules: list[GateRule], root: Path, extra_globs: list | None = None) -> GateReport:
    """目录扫描模式：收集 scope 并集匹配的文件再过闸。"""
    root = Path(root)
    globs = set()
    for r in rules:
        globs.update(r.scope)
    if extra_globs:
        globs.update(extra_globs)
    files: list[Path] = []
    seen = set()
    for g in globs:
        for p in root.glob(g):
            if p.is_file() and "git" not in p.parts:
                key = str(p)
                if key not in seen:
                    seen.add(key)
                    files.append(p)
    return run_gate(rules, files, root)
