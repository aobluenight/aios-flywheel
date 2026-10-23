# -*- coding: utf-8 -*-
"""aios-flywheel core —— 稳定层。

只做三件事：加载配置、调度检查器、产出报告。
任何业务判定逻辑都在 ext 层检查器里，本层不认识具体产线。
"""
from .engine import (
    Engine,
    Context,
    Result,
    LEVEL_GREEN,
    LEVEL_IDLE,
    LEVEL_DEAD,
    LEVEL_OBSERVE,
)

__version__ = "0.1.0"

__all__ = [
    "Engine",
    "Context",
    "Result",
    "LEVEL_GREEN",
    "LEVEL_IDLE",
    "LEVEL_DEAD",
    "LEVEL_OBSERVE",
    "__version__",
]
