"""物理模型纯函数 — 量子计算实验常用拟合模型的前向计算。

每个模型是独立纯函数，签名 ``(x: np.ndarray, **params) -> np.ndarray``。
**不包含拟合逻辑，不调用 lmfit 或任何 optimizer。**

模型列表：
- :func:`exp_decay` — 指数衰减 (T1, T2_echo)
- :func:`decaying_sinusoid` — 衰减正弦 (T2* Ramsey)
- :func:`lorentzian` — Lorentzian 峰 (光谱)
- :func:`gaussian` — Gaussian 峰 (f01 dispersion)
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "exp_decay",
    "decaying_sinusoid",
    "lorentzian",
    "gaussian",
    "rb_exp",
]


def exp_decay(
    x: np.ndarray,
    amplitude: float,
    tau: float,
    offset: float,
) -> np.ndarray:
    r"""指数衰减：:math:`A \cdot \exp(-x / \tau) + C`。

    用于 T1 弛豫时间测量和 T2 echo 测量。

    Parameters
    ----------
    x : np.ndarray
        自变量（延迟时间，μs）。
    amplitude : float
        衰减幅度 A。
    tau : float
        衰减时间常数 τ（与 x 单位相同）。
    offset : float
        基线偏移 C。

    Returns
    -------
    np.ndarray
    """
    return amplitude * np.exp(-x / tau) + offset


def decaying_sinusoid(
    x: np.ndarray,
    amplitude: float,
    tau: float,
    frequency: float,
    phase: float,
    offset: float,
) -> np.ndarray:
    r"""衰减正弦振荡：:math:`A \cdot \exp(-x / \tau) \cdot \cos(2\pi f x + \phi) + C`。

    用于 T2* Ramsey 干涉测量。

    Parameters
    ----------
    x : np.ndarray
        自变量（延迟时间）。
    amplitude : float
        振荡幅度 A。
    tau : float
        衰减时间常数 τ（T2*）。
    frequency : float
        振荡频率 f（失谐 Δf）。
    phase : float
        初始相位 φ（弧度）。
    offset : float
        基线偏移 C。

    Returns
    -------
    np.ndarray
    """
    return (
        amplitude * np.exp(-x / tau) * np.cos(2 * np.pi * frequency * x + phase)
        + offset
    )


def lorentzian(
    x: np.ndarray,
    amplitude: float,
    center: float,
    gamma: float,
    offset: float,
) -> np.ndarray:
    r"""Lorentzian 峰：:math:`A \cdot \frac{\gamma^2}{(x - x_0)^2 + \gamma^2} + C`。

    用于光谱测量中的共振峰拟合。

    Parameters
    ----------
    x : np.ndarray
        自变量（频率，GHz）。
    amplitude : float
        峰幅度 A。
    center : float
        中心频率 x₀（共振频率 f01）。
    gamma : float
        半宽 γ（HWHM）。
    offset : float
        基线偏移 C。

    Returns
    -------
    np.ndarray
    """
    return amplitude * (gamma**2) / ((x - center) ** 2 + gamma**2) + offset


def gaussian(
    x: np.ndarray,
    amplitude: float,
    center: float,
    sigma: float,
    offset: float,
) -> np.ndarray:
    r"""Gaussian 峰：:math:`A \cdot \exp\left(-\frac{(x - x_0)^2}{2\sigma^2}\right) + C`。

    用于 f01 vs bias 色散曲线拟合。

    Parameters
    ----------
    x : np.ndarray
        自变量。
    amplitude : float
        峰幅度 A。
    center : float
        中心位置 x₀。
    sigma : float
        标准偏差 σ。
    offset : float
        基线偏移 C。

    Returns
    -------
    np.ndarray
    """
    return amplitude * np.exp(-((x - center) ** 2) / (2 * sigma**2)) + offset


def rb_exp(
    x: np.ndarray,
    amplitude: float,
    p: float,
    offset: float,
) -> np.ndarray:
    r"""随机基准测试衰减：:math:`A \cdot p^N + B`。

    用于随机基准测试 (RB) 测量，拟合序列保真度随 Clifford
    序列长度 N 的衰减。单比特门保真度 F = 1 - (1-p)/2。

    Parameters
    ----------
    x : np.ndarray
        自变量（Clifford 序列长度 N）。
    amplitude : float
        衰减幅度 A。
    p : float
        衰减因子 p。范围为 (0, 1]。
    offset : float
        基线偏移 B（通常 ≈ 0.5 对于单比特 RB）。

    Returns
    -------
    np.ndarray
    """
    return amplitude * np.power(p, x) + offset
