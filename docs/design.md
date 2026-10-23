# 设计说明（v0.1）

## 分层

```
core/   稳定层  Engine / Context / Result / 判级常量。只依赖 PyYAML + 标准库。
ext/    动态层  检查器实现。依赖方向单向：ext → core，反向禁止。
tools/  冒烟    内置 fixture 自测，零外联。
config/ 配置    全部阈值/路径，代码零业务数字。
```

## 检查器契约

```python
class MyChecker:
    name = "my_checker"      # 与 yaml checks 键对应
    version = 1              # spec 契约版本
    def init(self, ctx): ...        # 可选：引擎装载后调用
    def check(self, spec, ctx): ... # 必须：返回 Result(name, level, detail, extras)
    def teardown(self, ctx): ...    # 可选：引擎收尾，资源清理防泄漏
```

生命周期映射：Init（实例化后）→ Load（from_config 装载完成）→ Update（逐项 check）→ Unload/Destroy（teardown 统一收尾）。

## 通信纪律

检查器之间**零直接引用**。结果经引擎 `Context.emit("result", payload)` 事件回调分发；外部观察者（推送、webhook）注册 listener，不侵入检查器。

## 实例化：键名与 kind

yaml `checks:` 下的**键名 = 实例名**（进报告、进事件）；同一检查器类型要配多个实例时，spec 里用 `kind:` 指定检查器类型（如两个 `state_freshness` 实例盯不同产物）。省略 `kind` 时默认键名即检查器名。

## 向前兼容

- spec 携带 `spec_version`；不匹配时引擎降级为 observe 并提示升级，不崩溃。
- spec 未知字段容忍（引擎不校验键集合）。
- 判级常量只增不改名：green / idle / dead / observe。

## 判级口径（飞轮铁律）

做完一次，第二次是否更快更强。硬指标：增量台账 + 自动触发器。

| level | 含义 |
|---|---|
| green | 活着且近期有增量 |
| idle | 在跑但增量=0（空转） |
| dead | 停转：超龄 / 进程死 / 解析失败 |
| observe | 软信号，只提示不报警 |

## 回滚

单机库无数据迁移；任何版本回滚 = `git checkout <上一 tag>`。报告目录为可再生缓存，可整目录删除重建，业务数据不落本仓库。
