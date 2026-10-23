# -*- coding: utf-8 -*-
"""tools/self_test.py —— 冒烟自测：内置 fixture，不碰真实产线。

每个用例对应一个真实事故判例的通用化行为（判例见 docs/cases/）。
跑法：python tools/self_test.py   （预期末行 PASS x/y）
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.engine import Engine, LEVEL_GREEN, LEVEL_IDLE, LEVEL_DEAD, LEVEL_OBSERVE  # noqa: E402
from ext.checkers import ALL  # noqa: E402

PASS = 0
FAIL = 0


def old_mtime(p: Path, hours: float):
    t = time.time() - hours * 3600
    os.utime(p, (t, t))


def check(desc, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  PASS {desc} -> {got}")
    else:
        FAIL += 1
        print(f"  FAIL {desc}: want {want}, got {got}")


def fresh_state(p: Path, hours: float = 0.1):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}", encoding="utf-8")
    old_mtime(p, hours)


def build_cfg(root: Path) -> dict:
    return {
        "checks": {
            "state_freshness": {"state": "runtime/state/fresh.json", "stale_hours": 2},
            "json_metric": {
                "state": "runtime/state/pipe.json", "metric_path": "results.total",
                "stale_hours": 24, "baseline_file": "runtime/state/.baseline.json",
            },
            "roster_health": {"state": "runtime/state/roster.json", "stale_hours": 1},
            "queue_backlog": {"queue_dir": "work/queue", "backlog_warn": 2},
            "ledger_soft": {"ledger": "docs/ledger.md", "soft_days": 30},
        }
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # ---- fixtures ----
        fresh_state(root / "runtime/state/fresh.json")
        st = root / "runtime/state/pipe.json"
        st.parent.mkdir(parents=True, exist_ok=True)
        st.write_text(json.dumps({"results": {"total": 5}}), encoding="utf-8")
        roster = root / "runtime/state/roster.json"
        roster.parent.mkdir(parents=True, exist_ok=True)
        roster.write_text(json.dumps({"children": {
            "a": {"alive": True}, "b": {"alive": True, "circuit": False}}}), encoding="utf-8")
        q = root / "work/queue"
        q.mkdir(parents=True, exist_ok=True)
        for i in range(3):
            (q / f"order_{i}.md").write_text("no marker here", encoding="utf-8")
        led = root / "docs/ledger.md"
        led.parent.mkdir(parents=True, exist_ok=True)
        led.write_text("cases", encoding="utf-8")
        old_mtime(led, 24 * 40)  # 40 天无更新 -> observe

        engine = Engine(build_cfg(root), root, [c() for c in ALL])

        print("[1] 常规体检（全部健康基线）")
        r = engine.run()
        check("fresh state -> green", r["state_freshness"].level, LEVEL_GREEN)
        check("roster all alive -> green", r["roster_health"].level, LEVEL_GREEN)
        check("ledger 40d -> observe", r["ledger_soft"].level, LEVEL_OBSERVE)
        check("queue 3>2 -> idle", r["queue_backlog"].level, LEVEL_IDLE)

        print("[2] 增量判定：首跑记基线 / 零增=空转 / 有增=green")
        check("metric first run -> observe", r["json_metric"].level, LEVEL_OBSERVE)
        r = engine.run()
        check("metric same value -> idle(空转)", r["json_metric"].level, LEVEL_IDLE)
        st.write_text(json.dumps({"results": {"total": 9}}), encoding="utf-8")
        r = engine.run()
        check("metric +4 -> green", r["json_metric"].level, LEVEL_GREEN)
        bl = root / "runtime/state/.baseline.json"
        check("baseline standalone file holds the key (not written into monitored state)",
              "json_metric" in json.loads(bl.read_text(encoding="utf-8")), True)

        print("[3] 事故通用化：静默死亡 / WAL 滞后 / 名册失真 / 前向兼容")
        old_mtime(root / "runtime/state/fresh.json", 10)
        r = engine.run()
        check("state 10h > 2h -> dead", r["state_freshness"].level, LEVEL_DEAD)
        fresh_state(root / "runtime/state/fresh.json")  # 复位

        db = root / "runtime/state/ledger.db"
        db.write_bytes(b"x"); old_mtime(db, 5)          # 主库 5h 前（checkpoint 滞后）
        wal = root / "runtime/state/ledger.db-wal"
        wal.write_bytes(b"y")                            # wal 刚写
        sf = [c() for c in ALL if c.name == "state_freshness"][0]
        rr = sf.check({"state": "runtime/state/ledger.db", "wal": True, "stale_hours": 2}, engine.ctx)
        check("WAL: old db + fresh -wal -> green(取最小龄)", rr.level, LEVEL_GREEN)

        roster.write_text(json.dumps({"children": {
            "a": {"alive": True}, "b": {"alive": False}}}), encoding="utf-8")
        r = engine.run()
        check("roster one dead -> dead", r["roster_health"].level, LEVEL_DEAD)

        bad_cfg = dict(build_cfg(root))
        bad_cfg["checks"]["future_checker_v9"] = {"state": "x", "spec_version": 9}
        be = Engine(bad_cfg, root, [c() for c in ALL])
        br = be.run()
        # 未注册检查器配置会被 from_config 拦；直接构造时多余键被忽略=容忍未知 spec 字段的另一面
        check("forward-compat: unknown spec keys tolerated (no crash)", isinstance(br, dict), True)

        print("[4] 报告输出")
        rep = engine.write_report(root / "out", r, title="selftest")
        check("report written", rep.is_file(), True)

    print(f"\nPASS {PASS}/{PASS + FAIL}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
