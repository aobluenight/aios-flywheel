# aios-flywheel · Human-in-the-Loop System-level RSI Toolkit

> 单机、人在环、系统层的自进化（Recursive Self-Improvement）工具集。
> 从一个真实运行的单人 AI OS 产线（30+ 产线 / 275+ 在役脚本）中提炼而来，全部为生产实证件。

## 它回答什么问题

当你让 AI Agent 持续替你干活，你会遇到四个经典问题：

1. **它还在转吗？** —— 常驻自动化静默死亡，没人知道（我们吃过亏：一条推送腿死了三周才发现）。
2. **它转得快，但吃进料了吗？** —— 流水线 rc=0、日志滚动，但产物零增量：空转。
3. **它会把监控自己的那份状态写坏吗？** —— 监控器把基线写回被监控文件，touch 了 mtime，自污染。
4. **经验教训怎么不靠人肉记住？** —— 坑 → 判例 → 自动门禁，让下一次同类事故被机器拦下。

`aios-flywheel` 把这些问题变成**可配置、可冒烟的检查器**。

## 判级口径（飞轮铁律）

> 做完一次，第二次是否更快更强？硬指标：有增量台账（不重复烧资源）+ 有自动触发器（没人推也转）。

| 判级 | 含义 |
|---|---|
| 🟢 | 健康：活着且近期有增量 |
| 🟡 | 空转：在跑但增量 = 0（磨还在转，料没进来） |
| 🔴 | 停转：产物超龄 / 进程死 / 解析失败 |
| ⚪ | 观察：软信号，只提示不报警 |

## 当前内容（v0.1 · M0）

### 件套一：飞轮自检器（flywheel checker）

通用化的自进化飞轮健康体检引擎，五个内置检查器，全部 YAML 驱动：

| 检查器 | 防什么事故 | 提炼自 |
|---|---|---|
| `state_freshness` | 自动化静默死亡；含 **WAL 库判定**（SQLite 主文件 mtime 会因 checkpoint 周期滞后，必须取 db/-wal 最大龄） | 活动账本误报事故 |
| `json_metric` | 空转（零增量）；**基线存独立文件，禁写回被监控 state**（自污染事故判例） | 拆解飞轮空转 / 监控自污染 |
| `roster_health` | 守护进程名册失真（名册说活着、子服已死） | 常驻总管监管失真 |
| `queue_backlog` | 消化能力退化（积压超阈） | 缺口单积压 |
| `ledger_soft` | 经验沉淀停转（N 天无新判例，软信号） | 经验飞轮软停转 |

```bash
# 冒烟自测（内置 fixture，零依赖除 PyYAML）
python tools/self_test.py

# 对自己的产线体检
python -m core.engine --config config/flywheels.yaml
```

### 路线图（五件套 · 全部落地 v0.2.0）

- [x] ① 飞轮自检器 —— 自我评估（RSI 核心件 ②）：`python -m core.engine --config config/flywheels.example.yaml`
- [x] ② 增量台账 + 覆盖保护 —— 防静默劣化：`python tools/ledger.py append ledger.jsonl --kind pit --text "..."`；`write --policy refuse|sidecar|backup`（覆盖必须显式留痕）
- [x] ③ 坑 → 门禁生成器 —— 经验沉淀成自动预检（RSI 核心件 ③）：`python tools/pit_gate.py --rules config/gates.example.yaml --scan <dir>`（规则必须回溯真实判例，禁凭空发明）
- [x] ④ 变更分级闸门 —— config 放行 / script 提示降级 / stable 拦截：`python tools/triage.py --rules config/triage.example.yaml --git`（block 退出码 2）
- [x] ⑤ 拍板台账 —— 人在环 reward model + 安全闸：`python tools/decision.py add --decision "..." --why "..." --scope "..."`（模板见 docs/templates/）

## 架构约定

```
core/   稳定层：引擎、检查器契约、报告。只依赖 PyYAML + 标准库。
ext/    动态层：内置检查器实现。新增检查器 = 在这里加一个类 + yaml 一行，零改引擎。
```

- **检查器契约**：`check(spec: dict, ctx: Context) -> Result`，可选 `init/teardown` 钩子；spec 带版本字段，引擎容忍未知字段（向前兼容）。
- **检查器之间零直接引用**，结果统一走引擎事件回调（`on_result`），杜绝耦合。
- **配置优先**：阈值、路径、开关全部 YAML；代码里没有业务数字。

## 判例库

见 [`docs/cases/`](docs/cases/) —— 每个检查器背后都是一次真实事故的脱敏复盘。这是本仓库和"又一个监控脚本"的区别。

## License

MIT
