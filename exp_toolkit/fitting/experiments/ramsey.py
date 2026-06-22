"""Ramsey 干涉测量 — fit_ramsey()。

自动选择 (coherence delay, Qxx P1) 列对 + DecayingSinusoid 模型。
提取 T2* 和频率失谐 Δf。
"""

from __future__ import annotations

from exp_toolkit.io.readers import Experiment
from exp_toolkit.fitting.engine import FitResult
from exp_toolkit.fitting.models import decaying_sinusoid
from exp_toolkit.fitting.guessers import guess_decaying_sinusoid
from exp_toolkit.fitting.experiments._base import _auto_fit

__all__ = ["fit_ramsey"]


def fit_ramsey(
    exp: Experiment,
    *,
    x_col: str | int = "auto",
    y_col: str | int = "auto",
    params_hint: dict[str, float] | None = None,
) -> FitResult:
    """T2* Ramsey 干涉拟合。

    默认列选择：
    - x: 最后一个独立变量（通常为 "coherence delay"）
    - y: 因变量中 category 包含 "P1" 但不含 "for |0>" 的列

    Parameters
    ----------
    exp : Experiment
        实验数据对象（需为 Ramsey 实验）。
    x_col : str or int
        x 列选择。"auto" 使用最后一个独立变量列。
    y_col : str or int
        y 列选择。"auto" 自动匹配 "P1" 列（排除校准列）。
    params_hint : dict[str, float] | None
        手动指定初始参数。Keys: amplitude, tau, frequency, phase, offset。

    Returns
    -------
    FitResult
        含参数: amplitude, tau, frequency, phase, offset。
        T2* = params["tau"]（单位与 x 轴相同）。
        Δf = params["frequency"]（频率失谐）。

    Raises
    ------
    ValueError
        无法找到匹配列。
    """
    return _auto_fit(
        exp,
        model_func=decaying_sinusoid,
        guesser=guess_decaying_sinusoid,
        x_col=x_col,
        y_col=y_col,
        x_pattern="",  # 默认最后一个独立变量
        y_pattern="P1",  # 匹配 "Q16 P1" 或 "P1"
        y_exclude_pattern="for |0>",  # 排除校准列
        params_hint=params_hint,
    )
