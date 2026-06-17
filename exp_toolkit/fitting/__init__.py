"""拟合子包 — 量子计算实验常用物理模型的拟合工具。

统一入口：engine.fit(x, y, model, guesser) -> FitResult
预定义模型：models 模块
"""

from exp_toolkit.fitting.engine import FitResult, fit
from exp_toolkit.fitting import models

__all__ = ["FitResult", "fit", "models"]
