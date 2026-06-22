"""拟合引擎 — 通用拟合入口 + FitResult 数据类。

底层使用 lmfit 拟合，包装物理模型纯函数。
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Callable

import lmfit
import numpy as np

__all__ = ["FitResult", "fit"]


@dataclass
class FitResult:
    """一次拟合的结果，包含参数、误差、统计量和诊断信息。

    Attributes
    ----------
    model_name : str
        模型名称（如 "ExponentialDecay"）。
    params : dict[str, float]
        最佳拟合参数值。
    errors : dict[str, float]
        1σ 标准误差（不可估计时值为 NaN）。
    r_squared : float
        决定系数 R²。
    residuals : np.ndarray
        残差 = y - y_fit。
    cov_matrix : np.ndarray | None
        协方差矩阵，不可估计时为 None。
    red_chi2 : float
        约化卡方 χ²/ν。
    success : bool
        拟合是否收敛。
    message : str
        lmfit 返回的诊断消息。
    x : np.ndarray
        输入的 x 数据。
    y : np.ndarray
        输入的 y 数据。
    y_fit : np.ndarray
        拟合曲线（在 x 点上）。
    """

    model_name: str
    params: dict[str, float]
    errors: dict[str, float]
    r_squared: float
    residuals: np.ndarray
    cov_matrix: np.ndarray | None
    red_chi2: float
    success: bool
    message: str
    x: np.ndarray = field(default_factory=lambda: np.array([]))
    y: np.ndarray = field(default_factory=lambda: np.array([]))
    y_fit: np.ndarray = field(default_factory=lambda: np.array([]))

    @property
    def n_params(self) -> int:
        """拟合参数数量。"""
        return len(self.params)

    @property
    def n_points(self) -> int:
        """数据点数量。"""
        return len(self.x)


def fit(
    x: np.ndarray,
    y: np.ndarray,
    model: Callable[..., np.ndarray],
    guesser: Callable[..., dict[str, float]] | None = None,
    *,
    params_hint: dict[str, float] | None = None,
    fix: dict[str, float] | None = None,
) -> FitResult:
    """通用拟合入口。

    将物理模型纯函数包装为 lmfit.Model，使用猜测器或参数提示作为初值，
    执行最小二乘拟合，返回标准化的 FitResult。

    Parameters
    ----------
    x : np.ndarray
        自变量数据（1D）。
    y : np.ndarray
        因变量数据（1D，与 x 等长）。
    model : Callable
        物理模型纯函数，签名 ``(x, **params) -> np.ndarray``。
    guesser : Callable | None
        参数猜测函数，签名 ``(x, y) -> dict[str, float]``。
        为 None 时使用 params_hint。两者都为 None 时抛出 ValueError。
    params_hint : dict[str, float] | None
        手动指定初始参数，优先级高于 guesser。
    fix : dict[str, float] | None
        固定参数及其值。这些参数不参与拟合。

    Returns
    -------
    FitResult

    Raises
    ------
    ValueError
        x/y 形状不匹配、无初值来源、或拟合异常。
    """
    # 输入校验
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()

    if x.size != y.size:
        raise ValueError(
            f"x and y must have the same length, got {x.size} and {y.size}"
        )
    if x.size == 0:
        raise ValueError("x and y must not be empty")

    # 剔除 NaN 和 Inf
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 3:
        raise ValueError(
            f"Need at least 3 finite (x, y) pairs, got {valid.sum()}"
        )
    x_clean = x[valid]
    y_clean = y[valid]

    # 模型名称
    model_name = getattr(model, "__name__", "unknown")

    # 创建 lmfit.Model
    try:
        lm_model = lmfit.Model(model)
    except Exception as e:
        raise ValueError(f"Failed to wrap model '{model_name}' in lmfit: {e}") from e

    # 确定初值
    if params_hint is not None:
        init_params: dict[str, float] = dict(params_hint)
    elif guesser is not None:
        try:
            init_params = guesser(x_clean, y_clean)
        except Exception as e:
            raise ValueError(
                f"Guesser failed for model '{model_name}': {e}"
            ) from e
    else:
        raise ValueError(
            f"No initial parameters supplied for model '{model_name}'. "
            f"Provide a guesser or params_hint."
        )

    # 转换为 lmfit.Parameters
    lm_params = lmfit.Parameters()
    for name, val in init_params.items():
        lm_params.add(name, value=val)

    # 应用固定参数
    if fix:
        for name, val in fix.items():
            if name in lm_params:
                lm_params[name].set(value=val, vary=False)
            else:
                lm_params.add(name, value=val, vary=False)

    # 执行拟合
    try:
        lm_result = lm_model.fit(y_clean, lm_params, x=x_clean)
    except Exception as e:
        return FitResult(
            model_name=model_name,
            params={},
            errors={},
            r_squared=0.0,
            residuals=np.array([]),
            cov_matrix=None,
            red_chi2=float("inf"),
            success=False,
            message=str(e),
            x=x,
            y=y,
            y_fit=np.array([]),
        )

    # 提取最佳参数
    best_params: dict[str, float] = {}
    errors: dict[str, float] = {}
    for name in lm_result.params:
        p = lm_result.params[name]
        best_params[name] = float(p.value)
        if p.stderr is not None:
            errors[name] = float(p.stderr)
        else:
            errors[name] = float("nan")

    # R²
    ss_res = float(np.sum(lm_result.residual**2))
    ss_tot = float(np.sum((y_clean - np.mean(y_clean)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1e-30 else 0.0

    # 约化卡方
    n_points = len(y_clean)
    n_varying = sum(1 for p in lm_result.params.values() if p.vary)
    dof = max(n_points - n_varying, 1)
    red_chi2 = ss_res / dof

    # 协方差矩阵
    cov_matrix: np.ndarray | None = None
    if lm_result.covar is not None:
        cov_matrix = np.array(lm_result.covar).copy()

        # 拟合曲线
    y_fit_full = np.full_like(y, np.nan, dtype=float)
    y_fit_full[valid] = lm_result.best_fit

    return FitResult(
        model_name=model_name,
        params=best_params,
        errors=errors,
        r_squared=float(r_squared),
        residuals=lm_result.residual,
        cov_matrix=cov_matrix,
        red_chi2=float(red_chi2),
        success=lm_result.success,
        message=lm_result.message or "",
        x=x,
        y=y,
        y_fit=y_fit_full,
    )
