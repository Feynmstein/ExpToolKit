"""拟合子包 — 量子计算实验常用物理模型的拟合工具。

提供两种使用模式：

**自动模式（推荐）** — 按实验类型调用 fit_*()：
    >>> from exp_toolkit.fitting import fit_t1, fit_spectro, fit_ramsey
    >>> result = fit_t1(exp)       # 自动选列 + ExponentialDecay
    >>> result = fit_spectro(exp)  # 自动选列 + Lorentzian
    >>> result = fit_ramsey(exp)   # 自动选列 + DecayingSinusoid

**手动模式（回退）** — 直接控制列和模型：
    >>> from exp_toolkit.fitting import fit, models
    >>> result = fit(x, y, models.exp_decay)

**实验类型推断** — 从标题自动匹配：
    >>> from exp_toolkit.fitting.experiments._base import infer_experiment_type
    >>> exp_type = infer_experiment_type("T2*_ramsey, Q16")
"""

from exp_toolkit.fitting.engine import FitResult, fit
from exp_toolkit.fitting import models
from exp_toolkit.fitting import guessers
from exp_toolkit.fitting.experiments.t1 import fit_t1
from exp_toolkit.fitting.experiments.spectro import fit_spectro, fit_f01_dispersion, F01Dispersion
from exp_toolkit.fitting.experiments.ramsey import fit_ramsey
from exp_toolkit.fitting.experiments.rabi import fit_rabi
from exp_toolkit.fitting.experiments.rb import fit_rb
from exp_toolkit.fitting.iq_analysis import assignment_fidelity, ReadoutFidelity

__all__ = [
    # Engine
    "FitResult",
    "fit",
    # Models
    "models",
    # Guessers
    "guessers",
    # Experiment-specific
    "fit_t1",
    "fit_spectro",
    "fit_f01_dispersion",
    "F01Dispersion",
    "fit_ramsey",
    "fit_rabi",
    "fit_rb",
    # IQ analysis
    "assignment_fidelity",
    "ReadoutFidelity",
]
