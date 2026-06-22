"""Rabi 振荡测量 — fit_rabi()。

自动选择 (驱动宽度/幅度, Qxx P1) 列对 + DecayingSinusoid 模型。
提取 π 脉冲校准值（pi_width 或 pi_amp）。
"""

from __future__ import annotations

from exp_toolkit.io.readers import Experiment
from exp_toolkit.fitting.engine import FitResult
from exp_toolkit.fitting.models import decaying_sinusoid
from exp_toolkit.fitting.guessers import guess_decaying_sinusoid
from exp_toolkit.fitting.experiments._base import _auto_fit

__all__ = ["fit_rabi"]


def fit_rabi(
    exp: Experiment,
    *,
    x_col: str | int = "auto",
    y_col: str | int = "auto",
    drive_var: str = "width",
    params_hint: dict[str, float] | None = None,
) -> FitResult:
    """Rabi 振荡拟合。

    使用衰减正弦模型拟合 Rabi 振荡数据，提取 Rabi 频率 Ω
    和 π 脉冲校准值。

    默认列选择：
    - x: 最后一个独立变量（驱动宽度或幅度）
    - y: 因变量中 category 包含 "P1" 但不含 "for |0>" 的列

    Parameters
    ----------
    exp : Experiment
        实验数据对象（需为 Rabi 实验）。
    x_col : str or int
        x 列选择。"auto" 使用最后一个独立变量列。
    y_col : str or int
        y 列选择。"auto" 自动匹配 "P1" 列（排除校准列）。
    drive_var : str
        驱动变量类型：
        - ``"width"`` — x 轴为 π pulse width (ns)，
          pi_pulse = 1/(2*frequency) 为 π 脉冲宽度
        - ``"amplitude"`` — x 轴为 pulse amplitude (arb)，
          pi_pulse = 1/(2*frequency) 为 π 脉冲幅度
    params_hint : dict[str, float] | None
        手动指定初始参数。

    Returns
    -------
    FitResult
        含参数: amplitude, tau, frequency, phase, offset。
        Rabi 频率 Ω = params["frequency"]（单位与 x 轴倒数相同）。
        π 脉冲校准值 = 1/(2*Ω)。

    Raises
    ------
    ValueError
        无法找到匹配列或 drive_var 不合法。
    """
    if drive_var not in ("width", "amplitude"):
        raise ValueError(
            f"drive_var must be 'width' or 'amplitude', got '{drive_var}'"
        )

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
