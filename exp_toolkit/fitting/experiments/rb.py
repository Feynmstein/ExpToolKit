"""随机基准测试 — fit_rb()。

自动选择 (Clifford 序列长度, Qxx P0/P1) 列对 + RBExponential 模型。
提取衰减因子 p → 单比特门保真度。
"""

from __future__ import annotations

from exp_toolkit.io.readers import Experiment
from exp_toolkit.fitting.engine import FitResult
from exp_toolkit.fitting.models import rb_exp
from exp_toolkit.fitting.guessers import guess_rb_exp
from exp_toolkit.fitting.experiments._base import _auto_fit

__all__ = ["fit_rb"]


def fit_rb(
    exp: Experiment,
    *,
    x_col: str | int = "auto",
    y_col: str | int = "auto",
    params_hint: dict[str, float] | None = None,
) -> FitResult:
    """随机基准测试 (RB) 拟合。

    使用 A·p^N + B 模型拟合序列保真度衰减，
    提取衰减因子 p 和单比特门保真度。

    默认列选择：
    - x: 最后一个独立变量（Clifford 序列长度 N）
    - y: 因变量中 category 包含 "P0" 的列

    Parameters
    ----------
    exp : Experiment
        实验数据对象（需为 RB 实验）。
    x_col : str or int
        x 列选择。"auto" 使用最后一个独立变量列。
    y_col : str or int
        y 列选择。"auto" 自动匹配 "P0" 列。
    params_hint : dict[str, float] | None
        手动指定初始参数。Keys: amplitude, p, offset。

    Returns
    -------
    FitResult
        含参数: amplitude, p, offset。
        单比特门保真度 F_gate = 1 - (1-p)/2。

    Raises
    ------
    ValueError
        无法找到匹配列。
    """
    return _auto_fit(
        exp,
        model_func=rb_exp,
        guesser=guess_rb_exp,
        x_col=x_col,
        y_col=y_col,
        x_pattern="",  # 默认最后一个独立变量
        y_pattern="P0",  # 匹配 "Q16 P0"（RB 通常用 P0）
        params_hint=params_hint,
    )
