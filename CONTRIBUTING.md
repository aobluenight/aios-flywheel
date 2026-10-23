# 贡献指南（CONTRIBUTING）

欢迎。本仓库的贡献形态有四类，按门槛从低到高排列。

## 0. 环境准备

```bash
git clone https://github.com/aobluenight/aios-flywheel.git
cd aios-flywheel
pip install pyyaml          # 唯一第三方依赖
python tools/self_test.py   # 预期末行 PASS 33/33
```

## 1. 报坑（Issue）

描述三件事：**现象 / 期望 / 复现步骤**。如果你撞坑的是 Agent 自动化产线，
顺带说明你的架构（什么在定时跑、状态记在哪），这决定能不能沉淀成检查器。

## 2. 提判例（docs/cases/）

本仓库的灵魂贡献。格式照抄现有判例（见 `docs/cases/`），必含四段：
**事故 → 根因 → 沉淀纪律 → 对应件**。请脱敏：无真实路径、凭据、内部系统名。

## 3. 加检查器（ext/checkers.py）

三步：写类（`name` / `version` / `check(spec, ctx)`，可选 `init`/`teardown` 钩子）
→ 加进模块底部 `ALL` 列表 → 在 `config/flywheels.example.yaml` 加示例。
契约与生命周期见 `docs/design.md`。**新检查器必须有判例背书**（README 判例库一节）。

## 4. 提门禁规则（config/gates.example.yaml）

**纪律：规则必须回溯真实事故**——message 里写清是哪个坑、什么先例。
没有事故背书的规则会被拒：没有代价的拦截只会训练人绕过门禁。

## 提交流程

1. Fork → 建 feature 分支（`git checkout -b my-checker`）
2. 改动 + 补自测（`tools/self_test.py`，保持全绿）
3. 若触及 `core/`，跑一次变更分诊自检：`python tools/triage.py --rules config/triage.example.yaml --git`
   —— 本仓库吃自己的狗粮，core 层变更需在 PR 里说明影响面
4. 提 PR，描述里写清对应判例（如有）

## 约定

- 判级常量只增不改名：green / idle / dead / observe
- spec 契约向前兼容：`spec_version` 不匹配时降级不崩溃
- 配置优先：阈值/路径进 yaml，代码里不带业务数字
