# -*- coding: utf-8 -*-
"""ext.checkers —— 动态层内置检查器。

新增检查器三步：
  1. 本文件（或同目录新模块）写一个类：name / version / check(spec, ctx)
  2. 把类加进本模块底部 ALL 列表
  3. yaml 的 checks: 下加同名键 —— 引擎零改动

每个检查器的 spec 契约见各 docstring；全部字段即阈值/路径，零硬编码业务数字。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from core.engine import (
    Result,
    LEVEL_GREEN,
    LEVEL_IDLE,
    LEVEL_DEAD,
    LEVEL_OBSERVE,
)


def _age_hours(p: Path):
    try:
        return (time.time() - p.stat().st_mtime) / 3600
    except OSError:
        return None


def _load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


class StateFreshness:
    """state_freshness —— 自动化静默死亡检测。

    spec 契约 v1:
        state: 相对 root 的状态档路径
        stale_hours: 超龄判定阈值（必填）
        optional: true 时缺失/超龄降级（笔记本关机日不算故障）
        wal: true 时按 SQLite WAL 库判定（取主库与 -wal 的最小龄；
             主库 mtime 因 checkpoint 周期会滞后——真实误报判例的通用化）
    """

    name = "state_freshness"
    version = 1

    def check(self, spec, ctx):
        base = ctx.root / spec["state"]
        stale = float(spec["stale_hours"])
        optional = bool(spec.get("optional"))
        label = spec.get("label", spec["state"])
        if spec.get("wal"):
            best = None
            for suffix in ("", "-wal"):
                age = _age_hours(Path(str(base) + suffix))
                if age is not None and (best is None or age < best):
                    best = age
            if best is None:
                return Result(self.name, LEVEL_DEAD, f"{label} 不存在（WAL 判定）")
            if best > stale:
                return Result(self.name, LEVEL_DEAD, f"{label} 超龄 {best:.1f}h（WAL 判定，>={stale}h）")
            return Result(self.name, LEVEL_GREEN, f"{label} {best*60:.0f}min 前有写入（WAL）")
        age = _age_hours(base)
        if age is None:
            if optional:
                return Result(self.name, LEVEL_OBSERVE, f"{label} 不在位（optional，跳过）")
            return Result(self.name, LEVEL_DEAD, f"{label} 状态档不存在")
        if age > stale:
            if optional:
                return Result(self.name, LEVEL_IDLE, f"{label} 超龄 {age:.0f}h——需核实：没新料还是没在跑")
            return Result(self.name, LEVEL_DEAD, f"{label} 超龄 {age:.0f}h（>={stale}h）")
        return Result(self.name, LEVEL_GREEN, f"{label} {age:.1f}h 前有写入")


class JsonMetric:
    """json_metric —— 增量判定（防"空转"），核心纪律：基线独立存档。

    spec 契约 v1:
        state: json 状态档（读取判增量）
        metric_path: 点分路径，如 last_summary.results.modules.slices
        stale_hours: 状态档超龄阈值（超龄先判 dead，增量没意义）
        baseline_file: 基线独立文件路径（相对 root）。
            铁律：基线绝不写回被监控 state——监控器写被监控文件会 touch mtime 自污染
            （真实事故判例：首跑即把"活着"误判成"刚写过"）。
        first_run_observe: 无基线时判 observe（只记基线不判空转），默认 true

    判定：本轮指标 == 上轮基线 且 state 存在 → idle（磨在转料没进）；有增量 → green。
    """

    name = "json_metric"
    version = 1

    def _dig(self, obj, dotted):
        cur = obj
        for part in dotted.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur

    def check(self, spec, ctx):
        st_path = ctx.root / spec["state"]
        stale = float(spec["stale_hours"])
        age = _age_hours(st_path)
        if age is None:
            return Result(self.name, LEVEL_DEAD, "状态档不存在")
        if age > stale:
            return Result(self.name, LEVEL_DEAD, f"状态档超龄 {age:.0f}h（>={stale}h）")
        try:
            st = _load_json(st_path)
        except Exception as e:
            return Result(self.name, LEVEL_DEAD, f"状态档解析失败: {e}")
        val = self._dig(st, spec["metric_path"])
        if val is None:
            return Result(self.name, LEVEL_OBSERVE, f"指标 {spec['metric_path']} 缺失")
        val = int(val)
        base_path = ctx.root / spec["baseline_file"]
        try:
            base = _load_json(base_path) if base_path.is_file() else {}
        except Exception:
            base = {}
        key = spec.get("baseline_key", self.name)
        first = key not in base
        prev = base.get(key, val)
        # 基线写独立文件（禁写回被监控 state——自污染判例）
        base[key] = val
        base_path.parent.mkdir(parents=True, exist_ok=True)
        base_path.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
        msg = f"{spec['metric_path']}={val}（上轮 {prev}）· {age:.1f}h 前写入"
        if first and spec.get("first_run_observe", True):
            return Result(self.name, LEVEL_OBSERVE, "首跑只记基线不判空转 · " + msg)
        if val == prev:
            return Result(self.name, LEVEL_IDLE, "零增量疑似空转 · " + msg)
        return Result(self.name, LEVEL_GREEN, f"增量 +{val - prev} · " + msg)


class RosterHealth:
    """roster_health —— 守护名册失真检测。

    spec 契约 v1:
        state: json 名册，结构 {children: {name: {alive: bool, circuit: bool}}}
        stale_hours: 名册超龄阈值（名册死=守护自己可能死了）
    """

    name = "roster_health"
    version = 1

    def check(self, spec, ctx):
        p = ctx.root / spec["state"]
        age = _age_hours(p)
        if age is None:
            return Result(self.name, LEVEL_DEAD, "名册不存在")
        if age > float(spec["stale_hours"]):
            return Result(self.name, LEVEL_DEAD, f"名册超龄 {age:.0f}h（守护自己可能死了）")
        try:
            r = _load_json(p)
        except Exception as e:
            return Result(self.name, LEVEL_DEAD, f"名册解析失败: {e}")
        children = r.get("children") or {}
        dead = [k for k, v in children.items() if not v.get("alive")]
        circuit = [k for k, v in children.items() if v.get("circuit")]
        if dead:
            return Result(self.name, LEVEL_DEAD, f"{len(dead)} 服死: {','.join(dead[:6])}")
        if circuit:
            return Result(self.name, LEVEL_IDLE, f"熔断中: {','.join(circuit)}")
        return Result(self.name, LEVEL_GREEN, f"{len(children)} 服全绿")


class QueueBacklog:
    """queue_backlog —— 积压检测（消化能力软信号）。

    spec 契约 v1:
        queue_dir: 待办队列目录（相对 root）
        glob: 文件匹配，默认 *.md
        done_marker: 文件含此串视为已完结，默认【状态】
        backlog_warn: 积压阈值（超阈判 idle 提醒，不是故障）
    """

    name = "queue_backlog"
    version = 1

    def check(self, spec, ctx):
        q = ctx.root / spec["queue_dir"]
        if not q.is_dir():
            return Result(self.name, LEVEL_OBSERVE, "队列目录不在位")
        marker = spec.get("done_marker", "【状态】")
        g = spec.get("glob", "*.md")
        open_items = [f.name for f in q.glob(g)
                      if marker not in f.read_text(encoding="utf-8", errors="replace")]
        n = len(open_items)
        warn = int(spec.get("backlog_warn", 10))
        if n > warn:
            return Result(self.name, LEVEL_IDLE, f"积压 {n}（>{warn}）: {','.join(open_items[:3])}")
        return Result(self.name, LEVEL_GREEN, f"在役待办 {n}")


class LedgerSoft:
    """ledger_soft —— 经验沉淀停转软信号。

    spec 契约 v1:
        ledger: 经验/判例档案路径（相对 root）
        soft_days: N 天无更新 → observe（只提示不报警）
    """

    name = "ledger_soft"
    version = 1

    def check(self, spec, ctx):
        p = ctx.root / spec["ledger"]
        age = _age_hours(p)
        if age is None:
            return Result(self.name, LEVEL_OBSERVE, "档案不在位")
        days = age / 24
        if days > float(spec["soft_days"]):
            return Result(self.name, LEVEL_OBSERVE, f"{days:.0f} 天无更新——经验沉淀软停转提示")
        return Result(self.name, LEVEL_GREEN, f"{days:.1f} 天内有更新")


ALL = [StateFreshness, JsonMetric, RosterHealth, QueueBacklog, LedgerSoft]
