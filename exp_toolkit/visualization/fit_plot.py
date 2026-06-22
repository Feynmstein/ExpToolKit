"""拟合结果可视化 — plot_fit_result() + plot_spectroscopy_2d()。

使用 matplotlib 面向对象 API，接受 ax 参数。
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from exp_toolkit.fitting.engine import FitResult
from exp_toolkit.io.readers import Experiment

__all__ = ["plot_fit_result", "plot_spectroscopy_2d"]

# 参数文本框位置 → (x, y, ha, va) 映射
_PARAM_LOC_MAP: dict[str, tuple[float, float, str, str]] = {
    "lower left": (0.02, 0.02, "left", "bottom"),
    "lower right": (0.98, 0.02, "right", "bottom"),
    "upper left": (0.02, 0.98, "left", "top"),
    "upper right": (0.98, 0.98, "right", "top"),
}


def plot_fit_result(
    x: np.ndarray,
    y: np.ndarray,
    result: FitResult,
    *,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    show_residuals: bool = True,
    param_loc: str = "lower left",
    ax: plt.Axes | None = None,
    ax_res: plt.Axes | None = None,
) -> tuple[plt.Figure, plt.Axes, plt.Axes | None]:
    """标准拟合结果图：数据点 + 拟合曲线 + 可选残差子图。

    Parameters
    ----------
    x : np.ndarray
        自变量数据。
    y : np.ndarray
        因变量数据（含 NaN 的数据点显示为散点）。
    result : FitResult
        拟合结果对象。
    title : str or None
        图表标题。
    xlabel / ylabel : str or None
        轴标签。
    show_residuals : bool
        是否绘制残差子图。
    param_loc : str
        参数文本框位置，可选 "lower left"（默认）、"lower right"、
        "upper left"、"upper right"。
    ax : plt.Axes or None
        主图 Axes，为 None 时创建。
    ax_res : plt.Axes or None
        残差图 Axes，为 None 时创建（仅 show_residuals=True 时使用）。

    Returns
    -------
    tuple[plt.Figure, plt.Axes, plt.Axes | None]
        (fig, ax_main, ax_residuals)
    """
    if show_residuals and ax is not None and ax_res is None:
        # 用户提供了主 ax 但没提供残差 ax → 需要创建复合布局
        # 这种情况较复杂，统一从 scratch 创建
        pass

    if ax is None:
        if show_residuals:
            fig, (ax, ax_res) = plt.subplots(
                2, 1, figsize=(8, 6),
                gridspec_kw={"height_ratios": [3, 1]},
                sharex=True,
            )
        else:
            fig, ax = plt.subplots(figsize=(8, 5))
            ax_res = None
    else:
        fig = ax.figure
        if ax_res is None:
            ax_res = None

    # 主图：数据点 + 拟合曲线
    valid = np.isfinite(y)
    ax.scatter(x[valid], y[valid], s=12, c="#4C72B0", alpha=0.7,
               label="Data", zorder=3)

    if len(result.y_fit) > 0:
        fit_valid = np.isfinite(result.y_fit)
        ax.plot(x[fit_valid], result.y_fit[fit_valid],
                "-", color="#C44E52", linewidth=2, label="Fit", zorder=4)

    ax.set_ylabel(ylabel or "Signal")
    if title:
        ax.set_title(title)
    ax.legend(fontsize=8, loc="best")
    ax.grid(True, alpha=0.3)

    # 拟合参数标注
    param_lines: list[str] = []
    for pname, pval in result.params.items():
        err = result.errors.get(pname, float("nan"))
        if np.isfinite(err):
            param_lines.append(f"{pname} = {pval:.4g} ± {err:.3g}")
        else:
            param_lines.append(f"{pname} = {pval:.4g}")
    param_lines.append(f"$R^2$ = {result.r_squared:.4f}")
    if np.isfinite(result.red_chi2):
        param_lines.append(f"$\\chi^2_\\nu$ = {result.red_chi2:.2f}")
    loc = _PARAM_LOC_MAP.get(param_loc, _PARAM_LOC_MAP["lower left"])
    ax.text(
        loc[0], loc[1], "\n".join(param_lines),
        transform=ax.transAxes,
        fontsize=7, fontfamily="monospace",
        horizontalalignment=loc[2],
        verticalalignment=loc[3],
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
    )

    # 残差图
    if show_residuals and ax_res is not None:
        if len(result.residuals) > 0:
            ax_res.axhline(0, color="gray", linewidth=0.8, linestyle="--")
            # 残差数组可能比 x 短（fit() 内部剔除 NaN），按有效点对齐
            x_for_res = x
            if len(x_for_res) != len(result.residuals):
                valid_mask = np.isfinite(x) & np.isfinite(y)
                x_for_res = x[valid_mask]
            if len(x_for_res) == len(result.residuals):
                ax_res.scatter(x_for_res, result.residuals, s=8, c="#555555", alpha=0.6)
        ax_res.set_ylabel("Residuals")
        ax_res.set_xlabel(xlabel or "x")
        ax_res.grid(True, alpha=0.3)

    # 如果没有残差子图，给主图加 xlabel
    if not show_residuals or ax_res is None:
        ax.set_xlabel(xlabel or "x")

    return fig, ax, ax_res


def plot_spectroscopy_2d(
    exp: Experiment,
    *,
    z_slice: float | None = None,
    ax: plt.Axes | None = None,
    ax_slice: plt.Axes | None = None,
) -> tuple[plt.Figure, plt.Axes, plt.Axes | None]:
    """2D 光谱伪彩图 + 可选 1D 切片。

    Parameters
    ----------
    exp : Experiment
        2D 光谱实验数据（需含 zpa 和 dr_freq 两个自变量）。
    z_slice : float or None
        在伪彩图上标注的 zpa 切片垂直线。为 None 时仅绘制 2D 图。
    ax : plt.Axes or None
        2D 图 Axes。
    ax_slice : plt.Axes or None
        1D 切片图 Axes（仅 z_slice 不为 None 时使用）。

    Returns
    -------
    tuple[plt.Figure, plt.Axes, plt.Axes | None]
    """
    if len(exp.independent_vars) < 2:
        raise ValueError(
            "plot_spectroscopy_2d requires 2D data with at least 2 "
            "independent variables"
        )

    n_ind = len(exp.independent_vars)
    zpa_col = 0
    freq_col = 1

    # 找第一个因变量列（IQ Amp 或 P1）
    from exp_toolkit.fitting.experiments._base import _find_column
    match = (
        _find_column(exp.dependent_vars, "IQ Amp")
        or _find_column(exp.dependent_vars, "P1")
        or 0
    )
    y_col = n_ind + match

    zpa_data = exp.data[:, zpa_col]
    freq_data = exp.data[:, freq_col]
    y_data = exp.data[:, y_col]

    zpa_unique = np.unique(zpa_data)
    freq_unique = np.unique(freq_data)

    # 重建 2D 网格
    grid = np.full((len(zpa_unique), len(freq_unique)), np.nan)
    for i, (z, f, yv) in enumerate(zip(zpa_data, freq_data, y_data)):
        zi = int(np.searchsorted(zpa_unique, z))
        fi = int(np.searchsorted(freq_unique, f))
        if 0 <= zi < len(zpa_unique) and 0 <= fi < len(freq_unique):
            grid[zi, fi] = yv

    # 布局
    if z_slice is not None:
        if ax is None:
            fig, (ax, ax_slice) = plt.subplots(
                1, 2, figsize=(14, 5),
                gridspec_kw={"width_ratios": [2, 1]},
            )
        else:
            fig = ax.figure
    else:
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        else:
            fig = ax.figure
        ax_slice = None

    # 2D 伪彩图
    extent = [freq_unique[0], freq_unique[-1], zpa_unique[-1], zpa_unique[0]]
    im = ax.imshow(
        grid, aspect="auto", origin="upper",
        extent=extent, cmap="viridis",
    )
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("ZPA bias")
    fig.colorbar(im, ax=ax, label="Signal")

    # 可选：标注 z_slice 线
    if z_slice is not None:
        ax.axhline(z_slice, color="red", linewidth=1, linestyle="--")
        # 1D 切片
        zi_slice = int(np.argmin(np.abs(zpa_unique - z_slice)))
        if 0 <= zi_slice < len(zpa_unique):
            ax_slice.plot(freq_unique, grid[zi_slice, :],
                          "-", color="#C44E52", linewidth=1.5)
            ax_slice.set_xlabel("Frequency (GHz)")
            ax_slice.set_ylabel("Signal")
            ax_slice.set_title(f"Slice at zpa={zpa_unique[zi_slice]:.3f}")
            ax_slice.grid(True, alpha=0.3)

    return fig, ax, ax_slice
