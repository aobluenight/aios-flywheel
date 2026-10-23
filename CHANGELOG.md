# Changelog

## 0.2.0 — 2026-10-23

M1：五件套收官。件套②~⑤落地，自测扩到 33 项。

- core.ledger：AppendLedger（JSONL 只增台账，ts/schema_version 自动盖）+ guard_overwrite 覆盖保护三策略（refuse/sidecar/backup）——覆盖在库里没有静默语法
- core.gate：坑→门禁运行器（规则=正则+glob 作用域+block/warn，message 强制回溯判例）
- core.triage：变更分级（config 放行/script 提示降级/stable 拦截；contract_files 一票否决；先中先用——严格层必须排前面，示例配置已体现）
- tools/：ledger / pit_gate / triage / decision 四个 CLI；decision 自动编号 D-YYYYMMDD-nn
- 判例+2：03 自反馈飞轮吃掉自己的账（静默劣化）/ 04 字符集外一个对勾部署即炸（坑→门禁首例实证）
- 自测 33/33；triage 与 pit_gate CLI 各自实测（triage 对本仓 core/engine.py 正确判 block）

## 0.1.0 — 2026-10-23

M0：件套①「飞轮自检器」通用化落地。

- core.engine：配置加载 / 检查器调度 / 事件回调 / 报告（keep_last 轮转）
- ext.checkers：state_freshness（含 WAL 最小龄判定）/ json_metric（独立基线增量判定）/ roster_health / queue_backlog / ledger_soft
- tools/self_test.py：内置 fixture 冒烟，覆盖全部判例行为
- 判例两篇：推送腿静默死亡 / 监控自污染与 WAL 时钟骗局
- 五件套路线图：②增量台账 ③坑→门禁 ④变更分级 ⑤拍板台账（待续）
