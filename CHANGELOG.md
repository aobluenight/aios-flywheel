# Changelog

## 0.1.0 — 2026-10-23

M0：件套①「飞轮自检器」通用化落地。

- core.engine：配置加载 / 检查器调度 / 事件回调 / 报告（keep_last 轮转）
- ext.checkers：state_freshness（含 WAL 最小龄判定）/ json_metric（独立基线增量判定）/ roster_health / queue_backlog / ledger_soft
- tools/self_test.py：内置 fixture 冒烟，覆盖全部判例行为
- 判例两篇：推送腿静默死亡 / 监控自污染与 WAL 时钟骗局
- 五件套路线图：②增量台账 ③坑→门禁 ④变更分级 ⑤拍板台账（待续）
