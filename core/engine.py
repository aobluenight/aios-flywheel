# -*- coding: utf-8 -*-
"""core.engine —— 飞轮自检引擎（稳定层）。

设计约定（与本仓库 README §架构约定一致）：

1. 检查器契约（ext 层实现，core 只认契约）::

       class MyChecker:
           name = "my_checker"          # 与 yaml checks: 下的键对应
           version = 1                  # spec 契约版本（向前兼容）
           def init(self, ctx): ...     # 可选钩子：引擎启动时调用一次
           def check(self, spec, ctx):  # 必须实现：spec=yaml 子配置，返回 Result
               ...
           def teardown(self, ctx): ... # 可选钩子：引擎收尾（资源清理，防泄漏）

2. 检查器之间零直接引用：结果统一经引擎的 on_result 事件回调分发。

3. 配置优先：全部阈值/路径在 yaml；spec 未知字段引擎容忍（向前兼容，只告警不炸）。

4. 判级口径（飞轮铁律）：
   green=活着且有增量 / idle=在跑但零增量 / dead=停转（超龄/进程死/解析失败）
   observe=软信号只提示不报警。
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

try:
    import yaml
except ImportError as e:  # 唯一第三方依赖
    raise SystemExit("aios-flywheel 需要 PyYAML：pip install pyyaml") from e

# ---------- 判级常量 ----------
LEVEL_GREEN = "green"
LEVEL_IDLE = "idle"
LEVEL_DEAD = "dead"
LEVEL_OBSERVE = "observe"

GLYPH = {
    LEVEL_GREEN: "GREEN",
    LEVEL_IDLE: "IDLE ",
    LEVEL_DEAD: "DEAD ",
    LEVEL_OBSERVE: "OBSRV",
}

# 钩子生命周期顺序（Init → Load → Update(check) → Unload → Destroy）
HOOKS_BEFORE = ("init",)
HOOKS_AFTER = ("teardown",)


@dataclass
class Result:
    """单检查项结果。level 取四常量之一；detail 供报告与事件回调使用。"""

    name: str
    level: str
    detail: str = ""
    extras: dict = field(default_factory=dict)

    def ok(self) -> bool:
        return self.level in (LEVEL_GREEN, LEVEL_OBSERVE)


@dataclass
class Context:
    """检查器运行上下文。root=仓库/产线根目录；emitter 用于引擎级事件。"""

    root: Path
    _listeners: list = field(default_factory=list)

    def emit(self, event: str, payload: dict) -> None:
        for fn in self._listeners:
            fn(event, payload)

    def on(self, fn: Callable[[str, dict], None]) -> None:
        self._listeners.append(fn)


def _age_hours(p: Path) -> Optional[float]:
    try:
        return (time.time() - p.stat().st_mtime) / 3600
    except OSError:
        return None


class Engine:
    """加载 yaml → 实例化 ext 检查器 → 逐项 check → 报告。

    用法::

        eng = Engine.from_config(Path("config/flywheels.yaml"), root=Path("."))
        results = eng.run()
        eng.write_report(Path("out"), results)
    """

    def __init__(self, cfg: dict, root: Path, checkers: Optional[list] = None):
        self.cfg = cfg or {}
        self.root = Path(root)
        # checkers: [(配置键名, 实例)]；键名默认取实例 .name，可在 yaml 用 kind 覆盖
        items = checkers or []
        self.checkers: list[tuple[str, object]] = []
        for it in items:
            if isinstance(it, tuple):
                self.checkers.append(it)
            else:
                self.checkers.append((it.name, it))
        self.ctx = Context(root=self.root)

    # ---------- 装载 ----------
    @classmethod
    def from_config(cls, config_path: Path, root: Path,
                    checker_classes: Optional[list] = None) -> "Engine":
        cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
        if checker_classes is None:
            from ext import checkers as builtin
            checker_classes = builtin.ALL
        by_name = {c.name: c for c in checker_classes}
        want = cfg.get("checks") or {}
        instances = []
        for key, spec in want.items():
            spec = dict(spec or {})
            kind = spec.get("kind", key)      # kind 允许同一检查器配多个实例
            if kind not in by_name:
                raise SystemExit(f"配置项 [{key}] 的检查器未注册: {kind}；已注册: {sorted(by_name)}")
            inst = by_name[kind]()
            instances.append((key, inst))
        eng = cls(cfg, root, instances)
        # Init / Load 钩子
        for _, c in eng.checkers:
            if hasattr(c, "init"):
                c.init(eng.ctx)
        return eng

    # ---------- Update ----------
    def run(self) -> dict[str, Result]:
        specs = self.cfg.get("checks") or {}
        results: dict[str, Result] = {}
        for key, c in self.checkers:
            spec = dict(specs.get(key) or {})
            spec_version = spec.get("spec_version", 1)
            if spec_version != getattr(c, "version", 1):
                # 向前兼容：版本不匹配降级为 observe，不炸
                results[key] = Result(key, LEVEL_OBSERVE,
                                      f"spec_version={spec_version} 与检查器 v{getattr(c, 'version', 1)} 不匹配，请升级配置")
                continue
            try:
                r = c.check(spec, self.ctx)
                r.name = key  # 报告与事件里用配置键名
            except Exception as e:  # 检查器自身崩=observe，不拖垮整轮体检
                r = Result(key, LEVEL_OBSERVE, f"检查器异常: {e!r}")
            results[key] = r
            self.ctx.emit("result", {"name": key, "level": r.level, "detail": r.detail})
        # Unload / Destroy 钩子（资源清理防泄漏）
        for _, c in self.checkers:
            if hasattr(c, "teardown"):
                c.teardown(self.ctx)
        return results

    # ---------- 报告 ----------
    def summary(self, results: dict[str, Result]) -> str:
        if any(r.level == LEVEL_DEAD for r in results.values()):
            return LEVEL_DEAD
        if any(r.level == LEVEL_IDLE for r in results.values()):
            return LEVEL_IDLE
        return LEVEL_GREEN

    def render_report(self, results: dict[str, Result], title: str = "flywheel check") -> str:
        lines = [f"# {title} {time.strftime('%Y-%m-%d %H:%M')} · overall={GLYPH[self.summary(results)]}", "",
                 "| flywheel | level | detail |", "|---|---|---|"]
        for name, r in results.items():
            lines.append(f"| {name} | {GLYPH[r.level]} | {r.detail} |")
        lines += ["", "> levels: GREEN=alive with increment / IDLE=running but zero increment / DEAD=stalled / OBSRV=soft signal"]
        return "\n".join(lines) + "\n"

    def write_report(self, out_dir: Path, results: dict[str, Result],
                     title: str = "flywheel check", keep_last: int = 30) -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        rep = out_dir / f"check_{time.strftime('%Y%m%d')}.md"
        rep.write_text(self.render_report(results, title), encoding="utf-8")
        olds = sorted(out_dir.glob("check_*.md"))
        for old in olds[:-keep_last] if len(olds) > keep_last else []:
            old.unlink()  # 报告是可再生缓存，直接清；业务数据从不走这里
        return rep


def _cli() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="aios-flywheel 飞轮自检引擎")
    ap.add_argument("--config", required=True, help="yaml 配置路径")
    ap.add_argument("--root", default=".", help="产线根目录（相对路径基准），默认当前目录")
    ap.add_argument("--out", default=None, help="报告目录，默认 config.report.out_dir")
    a = ap.parse_args()
    cfg_path = Path(a.config)
    root = Path(a.root).resolve()
    eng = Engine.from_config(cfg_path, root)
    results = eng.run()
    for name, r in results.items():
        print(f"[{GLYPH[r.level]}] {name}: {r.detail}")
    out = Path(a.out) if a.out else root / ((eng.cfg.get("report") or {}).get("out_dir", "work/flywheel_checks"))
    rep = eng.write_report(out, results)
    print(f"report: {rep} · overall={GLYPH[eng.summary(results)]}")
    return 0 if eng.summary(results) != LEVEL_DEAD else 1


if __name__ == "__main__":
    sys.exit(_cli())
