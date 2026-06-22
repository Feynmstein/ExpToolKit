"""光谱测量拟合 — fit_spectro() + fit_f01_dispersion()。

- fit_spectro(): 沿 freq 轴 Lorentzian 峰拟合
- fit_f01_dispersion(): 两步拟合 → f01 vs bias 色散曲线
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from exp_toolkit.io.readers import Experiment
from exp_toolkit.fitting.engine import FitResult, fit
from exp_toolkit.fitting.models import lorentzian, gaussian
from exp_toolkit.fitting.guessers import guess_lorentzian, guess_gaussian
from exp_toolkit.fitting.experiments._base import _auto_fit, _select_columns

__all__ = ["fit_spectro", "fit_f01_dispersion", "F01Dispersion"]


def fit_spectro(
    exp: Experiment,
    *,
    x_col: str | int = "auto",
    y_col: str | int = "auto",
    z_slice: float | None = None,
    params_hint: dict[str, float] | None = None,
) -> FitResult:
    """光谱峰拟合 — 沿频率轴的 Lorentzian 拟合。

    对于 2D 光谱数据（含 zpa 和 dr_freq 两个自变量），
    ``z_slice`` 指定要拟合的 zpa 值。
    z_slice=None 时使用第一个 zpa 值。

    默认列选择：
    - y: 因变量中 category 匹配 "IQ Amp" 或 "P1" 的列

    Parameters
    ----------
    exp : Experiment
        光谱实验数据。
    x_col : str or int
        x 列选择。"auto" 使用 "dr_freq" 列。
    y_col : str or int
        y 列选择。"auto" 匹配 "IQ Amp" 或 "P1"。
    z_slice : float | None
        2D 数据时指定 zpa 切片值。1D 数据忽略。
    params_hint : dict[str, float] | None
        手动指定初始参数。

    Returns
    -------
    FitResult
        含参数: amplitude, center, gamma, offset。
        f01 ≈ center（共振频率，GHz）。
    """
    is_2d = len(exp.independent_vars) >= 2

    # 2D 数据且未指定 z_slice → 自动选第一个 zpa 值
    if is_2d and z_slice is None:
        zpa_col = 0
        zpa_unique = np.unique(exp.data[:, zpa_col])
        actual_zpa = float(zpa_unique[len(zpa_unique) // 2])  # 取中间 zpa
        import warnings
        warnings.warn(
            f"fit_spectro: 2D data with no z_slice specified. "
            f"Auto-selecting zpa={actual_zpa:.3f} "
            f"(available: {zpa_unique[0]:.3g}–{zpa_unique[-1]:.3g}). "
            f"Use z_slice=... to select a specific bias."
        )
        z_slice = actual_zpa

    # 对 2D 数据筛选 zpa 切片
    if z_slice is not None and is_2d:
        zpa_col = 0  # 第一个独立变量通常是 zpa
        zpa_values = np.unique(exp.data[:, zpa_col])
        # 找到最近的 zpa 值
        idx = int(np.argmin(np.abs(zpa_values - z_slice)))
        actual_zpa = float(zpa_values[idx])

        mask = np.isclose(exp.data[:, zpa_col], actual_zpa)
        x_full, y_full, x_lbl, y_lbl = _select_columns(
            exp, x_col=x_col, y_col=y_col,
            x_pattern="dr_freq", y_pattern="IQ Amp",
        )
        x = x_full[mask]
        y = y_full[mask]

        result = fit(x, y, lorentzian, guesser=guess_lorentzian,
                     params_hint=params_hint)
    else:
        result = _auto_fit(
            exp,
            model_func=lorentzian,
            guesser=guess_lorentzian,
            x_col=x_col,
            y_col=y_col,
            x_pattern="dr_freq",
            y_pattern="IQ Amp",
            params_hint=params_hint,
        )

    if not result.success:
        import warnings
        warnings.warn(
            f"[警告] fit_spectro 拟合未收敛："
            f"exp={exp.exp_id} | χ²_ν={result.red_chi2:.1f}"
        )

    return result


# =============================================================================
# f01 Dispersion
# =============================================================================


@dataclass
class F01Dispersion:
    """f01 色散曲线拟合结果。

    Attributes
    ----------
    f01_min : float
        f01 范围最小值 (GHz)。
    f01_max : float
        f01 范围最大值 (GHz)。
    zpa_values : np.ndarray
        各 zpa 点。
    f01_values : np.ndarray
        各 zpa 对应的 f01 值。
    f01_errors : np.ndarray | None
        各 f01 的拟合误差。
    fit_result : FitResult | None
        f01 vs zpa 的 Gaussian 拟合结果。
    """

    f01_min: float
    f01_max: float
    zpa_values: np.ndarray
    f01_values: np.ndarray
    f01_errors: np.ndarray | None = None
    fit_result: FitResult | None = None


def fit_f01_dispersion(
    exp: Experiment,
    *,
    x_col: str | int = "auto",
    y_col: str | int = "auto",
) -> F01Dispersion:
    """f01 色散曲线拟合 — 两步法。

    1. 沿频率轴，对每个 zpa 切片 Lorentzian 拟合 → 得到 f01(zpa)
    2. 对 (zpa, f01) 点 Gaussian 拟合 → 获取 f01 min/max

    Parameters
    ----------
    exp : Experiment
        2D 光谱实验数据（必须有两个自变量：zpa 和 dr_freq）。
    x_col / y_col : str or int
        列选择，见 fit_spectro()。

    Returns
    -------
    F01Dispersion
    """
    if len(exp.independent_vars) < 2:
        raise ValueError(
            "fit_f01_dispersion() requires 2D data with zpa and dr_freq as "
            f"independent variables. Got {len(exp.independent_vars)}."
        )

    # 识别 zpa 列和 freq 列
    zpa_idx: int | None = None
    freq_idx: int | None = None
    for i, col in enumerate(exp.independent_vars):
        if "zpa" in col.label.lower():
            zpa_idx = i
        if "freq" in col.label.lower() or "dr_freq" in col.label.lower():
            freq_idx = i
    if zpa_idx is None:
        zpa_idx = 0
    if freq_idx is None:
        freq_idx = 1

    # 选择 y 列
    n_ind = len(exp.independent_vars)
    if isinstance(y_col, int):
        y_idx = y_col
    else:
        from exp_toolkit.fitting.experiments._base import _find_column
        match = _find_column(exp.dependent_vars, "IQ Amp")
        if match is None:
            match = _find_column(exp.dependent_vars, "P1")
        if match is None:
            raise ValueError(
                "Cannot find y column for spectroscopy. "
                "Expected 'IQ Amp' or 'P1' in dependent categories."
            )
        y_idx = n_ind + match

    zpa_all = exp.data[:, zpa_idx]
    y_all = exp.data[:, y_idx]

    # 选择 x 列（频率）
    if isinstance(x_col, int):
        freq_all = exp.data[:, x_col]
    else:
        freq_all = exp.data[:, freq_idx]

    # 按 zpa 分组
    zpa_unique = np.unique(zpa_all)
    f01_list: list[float] = []
    f01_err_list: list[float] = []
    zpa_list: list[float] = []

    for zpa_val in zpa_unique:
        mask = np.isclose(zpa_all, zpa_val)
        freq_slice = freq_all[mask]
        y_slice = y_all[mask]

        # 按频率排序
        sort_idx = np.argsort(freq_slice)
        freq_sorted = freq_slice[sort_idx]
        y_sorted = y_slice[sort_idx]

        if len(freq_sorted) < 6:
            continue

        try:
            res = fit(freq_sorted, y_sorted, lorentzian,
                      guesser=guess_lorentzian)
            if res.success and "center" in res.params:
                f01_list.append(res.params["center"])
                f01_err_list.append(res.errors.get("center", np.nan))
                zpa_list.append(float(zpa_val))
        except Exception:
            continue

    if len(f01_list) < 3:
        raise ValueError(
            f"fit_f01_dispersion: only {len(f01_list)} valid f01 points "
            f"(need at least 3). Check data quality."
        )

    f01_arr = np.array(f01_list)
    zpa_arr = np.array(zpa_list)
    f01_err_arr = np.array(f01_err_list)

    # Step 2: Gaussian 拟合 f01 vs zpa
    try:
        gauss_res = fit(zpa_arr, f01_arr, gaussian, guesser=guess_gaussian)
    except Exception:
        gauss_res = None

    f01_empirical_min = float(np.min(f01_arr))
    f01_empirical_max = float(np.max(f01_arr))
    f01_min = f01_empirical_min
    f01_max = f01_empirical_max

    # 如果有成功的 Gaussian 拟合，从拟合结果提取范围
    if gauss_res is not None and gauss_res.success:
        center = gauss_res.params.get("center", 0.0)
        amplitude = gauss_res.params.get("amplitude", 0.0)
        offset = gauss_res.params.get("offset", 0.0)
        # f01 在 center 附近的范围
        #   A>0 (peak):  center 附近 f01 更高 → max=offset+A, min=offset
        #   A<0 (dip):   center 附近 f01 更低 → max=offset, min=offset+A
        f01_fit_low = min(amplitude + offset, offset)
        f01_fit_high = max(amplitude + offset, offset)

        # Guard: 防止 Gaussian 拟合外推超过经验数据 ±30%
        empirical_span = f01_empirical_max - f01_empirical_min
        if empirical_span > 0:
            margin = 0.3 * empirical_span
            if (f01_fit_low < f01_empirical_min - margin
                    or f01_fit_high > f01_empirical_max + margin):
                import warnings
                warnings.warn(
                    f"fit_f01_dispersion: Gaussian fit range "
                    f"({f01_fit_low:.3f}–{f01_fit_high:.3f} GHz) deviates "
                    f"significantly from empirical data "
                    f"({f01_empirical_min:.3f}–{f01_empirical_max:.3f} GHz). "
                    f"Using empirical range."
                )
            else:
                f01_min = f01_fit_low
                f01_max = f01_fit_high
        else:
            # 数据无变化（所有 f01 相同）→ 使用拟合值
            f01_min = f01_fit_low
            f01_max = f01_fit_high

    return F01Dispersion(
        f01_min=f01_min,
        f01_max=f01_max,
        zpa_values=zpa_arr,
        f01_values=f01_arr,
        f01_errors=f01_err_arr if np.any(np.isfinite(f01_err_arr)) else None,
        fit_result=gauss_res,
    )
