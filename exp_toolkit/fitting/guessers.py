"""参数自动猜测器 — 为每个物理模型提供初始参数估计。

每个猜测器签名 ``(x: np.ndarray, y: np.ndarray) -> dict[str, float]``。
返回的字典可直接传入 ``fit(..., params_hint=guess)`` 或作为 lmfit 初值。
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "guess_exp_decay",
    "guess_decaying_sinusoid",
    "guess_lorentzian",
    "guess_gaussian",
    "guess_rb_exp",
]


def guess_exp_decay(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """指数衰减初值猜测。

    - amplitude = y.max() - y.min()
    - tau = (x.max() - x.min()) / 3
    - offset = y.min()

    Parameters
    ----------
    x : np.ndarray
    y : np.ndarray

    Returns
    -------
    dict[str, float]
        Keys: amplitude, tau, offset

    Raises
    ------
    ValueError
        y 值全为 NaN 或 x 范围为 0。
    """
    if np.all(np.isnan(y)):
        raise ValueError("Cannot guess exp_decay params: y values are all NaN")

    x_range = x.max() - x.min()
    if x_range <= 0:
        raise ValueError(
            f"Cannot guess exp_decay params: x range is {x_range}"
        )

    y_min = float(np.nanmin(y))
    y_max = float(np.nanmax(y))

    return {
        "amplitude": y_max - y_min,
        "tau": x_range / 3.0,
        "offset": y_min,
    }


def guess_decaying_sinusoid(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """衰减正弦振荡初值猜测。

    使用 FFT 估计主频率，包络拟合估计衰减时间。

    - 对 y 去趋势后做 FFT → 找到幅度最大的频率（去掉 DC）→ frequency
    - 对 |y - y.mean()| 的上包络拟合指数衰减 → tau
    - amplitude = (y.max() - y.min())
    - phase = 0（FFT 相位估计误差大，拟合器自行调整）
    - offset = y.mean()

    Parameters
    ----------
    x : np.ndarray
    y : np.ndarray

    Returns
    -------
    dict[str, float]
        Keys: amplitude, tau, frequency, phase, offset
    """
    if np.all(np.isnan(y)):
        raise ValueError("Cannot guess decaying_sinusoid params: y all NaN")

    # 去趋势
    y_detrended = y - np.mean(y)

    # FFT 找主频
    n = len(x)
    dt = (x[-1] - x[0]) / (n - 1) if n > 1 else 1.0
    if dt <= 0:
        raise ValueError(f"Cannot guess frequency: dt = {dt}")

    yf = np.abs(np.fft.rfft(y_detrended))
    freqs = np.fft.rfftfreq(n, d=dt)

    # 跳过 DC 分量 (freqs[0])，找幅度最大的频率
    if len(freqs) > 1:
        peak_idx = int(np.argmax(yf[1:])) + 1
        frequency = float(freqs[peak_idx])
    else:
        frequency = 1.0 / (x[-1] - x[0]) if x[-1] != x[0] else 1.0

    # 包络拟合估计 tau
    y_abs = np.abs(y_detrended)
    # 找上包络的点（局部极大值）
    envelope_x: list[float] = []
    envelope_y: list[float] = []
    for i in range(1, n - 1):
        if y_abs[i] >= y_abs[i - 1] and y_abs[i] >= y_abs[i + 1]:
            envelope_x.append(float(x[i]))
            envelope_y.append(float(y_abs[i]))
    # 如果局部极值点不足，使用全部正半周点
    if len(envelope_y) < 4:
        envelope_x = [float(v) for v in x]
        envelope_y = [float(v) for v in y_abs]

    env_x_arr = np.array(envelope_x)
    env_y_arr = np.array(envelope_y)
    env_y_arr = np.maximum(env_y_arr, 1e-12)  # 防止 log(0)

    # log 线性拟合估计 tau
    coeffs = np.polyfit(env_x_arr, np.log(env_y_arr), 1)
    tau_est = -1.0 / coeffs[0] if coeffs[0] < 0 else (x[-1] - x[0]) / 3.0

    return {
        "amplitude": float((np.nanmax(y) - np.nanmin(y)) / 2.0),
        "tau": max(float(tau_est), (x[-1] - x[0]) / 10.0),
        "frequency": max(abs(frequency), 1e-6),
        "phase": 0.0,
        "offset": float(np.nanmean(y)),
    }


def guess_lorentzian(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Lorentzian 峰初值猜测。

    - center = x[y.argmax()]
    - FWHM 估计 → gamma = FWHM / 2
    - amplitude = (y.max() - y.min()) * gamma  （使峰值高度=amplitude/γ² + C ≈ A + C）

    Parameters
    ----------
    x : np.ndarray
    y : np.ndarray

    Returns
    -------
    dict[str, float]
        Keys: amplitude, center, gamma, offset
    """
    if np.all(np.isnan(y)):
        raise ValueError("Cannot guess lorentzian params: y values are all NaN")

    y_max = float(np.nanmax(y))
    y_min = float(np.nanmin(y))
    center = float(x[np.nanargmax(y)])

    # 估计 FWHM：找到 y 降至半高处的两点
    half_max = y_min + (y_max - y_min) / 2.0
    above = y >= half_max
    # 找第一个和最后一个高于半高的点的索引
    indices = np.where(above)[0]
    if len(indices) >= 2:
        fwhm = float(x[indices[-1]] - x[indices[0]])
    else:
        fwhm = (x[-1] - x[0]) / 5.0

    gamma = max(fwhm / 2.0, 1e-9)

    return {
        "amplitude": (y_max - y_min) * gamma,
        "center": center,
        "gamma": gamma,
        "offset": y_min,
    }


def guess_gaussian(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Gaussian 峰初值猜测。

    - center = x[y.argmax()]
    - sigma = FWHM / 2.355
    - amplitude = y.max() - y.min()
    - offset = y.min()

    Parameters
    ----------
    x : np.ndarray
    y : np.ndarray

    Returns
    -------
    dict[str, float]
        Keys: amplitude, center, sigma, offset
    """
    if np.all(np.isnan(y)):
        raise ValueError("Cannot guess gaussian params: y values are all NaN")

    y_max = float(np.nanmax(y))
    y_min = float(np.nanmin(y))
    center = float(x[np.nanargmax(y)])

    # FWHM 估计
    half_max = y_min + (y_max - y_min) / 2.0
    above = y >= half_max
    indices = np.where(above)[0]
    if len(indices) >= 2:
        fwhm = float(x[indices[-1]] - x[indices[0]])
    else:
        fwhm = (x[-1] - x[0]) / 5.0

    sigma = max(fwhm / 2.355, 1e-9)

    return {
        "amplitude": y_max - y_min,
        "center": center,
        "sigma": sigma,
        "offset": y_min,
    }


def guess_rb_exp(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """RB 指数衰减初值猜测。

    - amplitude = y[0] - y[-1]（序列保真度衰减幅度）
    - p = exp(-1/mean(N)) 近似（典型值 ~0.99）
    - offset = y[-1]（长序列渐进值 ≈ 0.5）

    Parameters
    ----------
    x : np.ndarray
    y : np.ndarray

    Returns
    -------
    dict[str, float]
        Keys: amplitude, p, offset

    Raises
    ------
    ValueError
        y 值全为 NaN 或 x 范围不足。
    """
    if np.all(np.isnan(y)):
        raise ValueError("Cannot guess rb_exp params: y values are all NaN")

    if len(x) < 3:
        raise ValueError(
            f"Cannot guess rb_exp params: need at least 3 points, got {len(x)}"
        )

    y_start = float(y[0])
    y_end = float(y[-1])

    # amplitude: 序列从短到长的衰减幅度
    amplitude = y_start - y_end

    # p: 指数衰减率。用平均长度估计
    #   y ≈ A·p^N + B → log(y-B) ≈ log(A) + N·log(p)
    #   如果 y_end ≈ B，log(y - B) ≈ log(A) + N·log(p)
    offset_guess = min(y_end, float(np.nanmin(y)))
    y_shifted = np.maximum(y - offset_guess, 1e-12)
    coeffs = np.polyfit(x, np.log(y_shifted), 1)
    p_guess = float(np.exp(coeffs[0])) if coeffs[0] < 0 else 0.99
    p_guess = min(max(p_guess, 0.5), 0.9999)  # 裁剪到合理范围

    return {
        "amplitude": max(abs(amplitude), 0.01),
        "p": p_guess,
        "offset": float(offset_guess),
    }
