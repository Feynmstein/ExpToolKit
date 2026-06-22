"""实验分发辅助 — _auto_fit() 公共入口 + 列匹配工具 + 实验类型调度。

每个 ``fit_*()`` 函数内部通过 ``_auto_fit()`` 完成：
1. 列选择（从 Experiment 中找到 x_col / y_col）
2. 模型 + 猜测器绑定
3. 调用 engine.fit() → FitResult

实验类型调度通过 ``infer_experiment_type()`` 和 ``get_fit_function()``
从 experiment_types.yaml 推断实验类型并返回对应的 fit_*() 函数。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

import numpy as np

from exp_toolkit.io.readers import ColumnMeta, Experiment
from exp_toolkit.fitting.engine import FitResult, fit

__all__ = [
    "_auto_fit",
    "_find_column",
    "_select_columns",
    "infer_experiment_type",
    "get_fit_function",
]


def _find_column(
    cols: list[ColumnMeta],
    pattern: str,
    exclude_pattern: str | None = None,
) -> int | None:
    """按模式匹配列索引。

    匹配规则（按优先级）：
    1. 精确匹配 category（排除 exclude_pattern 命中项）
    2. category 包含 pattern（不区分大小写）
    3. label 包含 pattern（不区分大小写）

    Parameters
    ----------
    cols : list[ColumnMeta]
        列元数据列表。
    pattern : str
        搜索模式。
    exclude_pattern : str | None
        排除模式 — category 或 label 包含此字符串的列会被跳过。

    Returns
    -------
    int or None
        匹配到的列索引，未找到返回 None。
    """
    pattern_lower = pattern.lower()
    exclude_lower = exclude_pattern.lower() if exclude_pattern else None

    def _is_excluded(col: ColumnMeta) -> bool:
        if exclude_lower is None:
            return False
        return (
            exclude_lower in col.category.lower()
            or exclude_lower in col.label.lower()
        )

    # 1. 精确匹配 category
    for i, col in enumerate(cols):
        if col.category.lower() == pattern_lower and not _is_excluded(col):
            return i

    # 2. category 包含 pattern
    for i, col in enumerate(cols):
        if pattern_lower in col.category.lower() and not _is_excluded(col):
            return i

    # 3. label 包含 pattern
    for i, col in enumerate(cols):
        if pattern_lower in col.label.lower() and not _is_excluded(col):
            return i

    return None


def _select_columns(
    exp: Experiment,
    x_col: str | int = "auto",
    y_col: str | int = "auto",
    x_pattern: str = "",
    y_pattern: str = "",
    y_exclude_pattern: str | None = None,
) -> tuple[np.ndarray, np.ndarray, str, str]:
    """从 Experiment 中选择 x 和 y 列。

    Parameters
    ----------
    exp : Experiment
    x_col : str or int
        "auto" → 使用最后一个独立变量列，或用 x_pattern 搜索。
        整数 → 直接索引（0 为第一列）。
    y_col : str or int
        "auto" → 使用 y_pattern 在因变量列中搜索。
        整数 → 绝对列索引。
    x_pattern : str
        x_col="auto" 时在独立变量列中搜索的模式。
    y_pattern : str
        y_col="auto" 时在因变量列中搜索的模式。
    y_exclude_pattern : str | None
        排除模式 — 因变量列的 category/label 包含此字符串时跳过。
        用于排除校准列（如 "for |0>"）。

    Returns
    -------
    tuple[np.ndarray, np.ndarray, str, str]
        (x_data, y_data, x_label, y_label)

    Raises
    ------
    ValueError
        无法找到匹配列或索引越界。
    """
    n_total = exp.data.shape[1]
    n_ind = len(exp.independent_vars)

    # --- X 列 ---
    if isinstance(x_col, int):
        if x_col < 0 or x_col >= n_total:
            raise ValueError(
                f"x_col={x_col} out of range (0..{n_total - 1})"
            )
        x_idx = x_col
        x_label = f"col_{x_col}"
    else:  # "auto" or string pattern
        search = x_col if x_col != "auto" else x_pattern
        if search:
            match_idx = _find_column(exp.independent_vars, search)
            if match_idx is not None:
                x_idx = match_idx
                x_label = exp.independent_vars[match_idx].label or f"indep_{match_idx}"
            else:
                available = [c.category or c.label for c in exp.independent_vars]
                raise ValueError(
                    f"Cannot find x column matching '{search}' in independent vars. "
                    f"Available: {available}"
                )
        else:
            # 默认：最后一个独立变量
            x_idx = n_ind - 1 if n_ind > 0 else 0
            x_label = (
                exp.independent_vars[x_idx].label
                if x_idx < len(exp.independent_vars)
                else f"col_{x_idx}"
            )

    # --- Y 列 ---
    if isinstance(y_col, int):
        if y_col < 0 or y_col >= n_total:
            raise ValueError(
                f"y_col={y_col} out of range (0..{n_total - 1})"
            )
        y_idx = y_col
        y_label = f"col_{y_col}"
    else:  # "auto" or string pattern
        search = y_col if y_col != "auto" else y_pattern
        if search:
            match_idx = _find_column(exp.dependent_vars, search,
                                     exclude_pattern=y_exclude_pattern)
            if match_idx is not None:
                # 因变量列在 data 中的绝对索引
                y_idx = n_ind + match_idx
                y_label = exp.dependent_vars[match_idx].category or f"dep_{match_idx}"
            else:
                available = [c.category or c.label for c in exp.dependent_vars]
                raise ValueError(
                    f"Cannot find y column matching '{search}' in dependent vars. "
                    f"Available: {available}"
                )
        else:
            raise ValueError(
                "y_col='auto' requires y_pattern to be specified"
            )

    return exp.data[:, x_idx], exp.data[:, y_idx], x_label, y_label


def _auto_fit(
    exp: Experiment,
    model_func: Callable[..., np.ndarray],
    guesser: Callable[..., dict[str, float]] | None,
    *,
    x_col: str | int = "auto",
    y_col: str | int = "auto",
    x_pattern: str = "",
    y_pattern: str = "",
    y_exclude_pattern: str | None = None,
    params_hint: dict[str, float] | None = None,
    fix: dict[str, float] | None = None,
) -> FitResult:
    """自动列选择 + 模型分发 → fit()。

    Parameters
    ----------
    exp : Experiment
        实验数据对象。
    model_func : Callable
        物理模型纯函数。
    guesser : Callable | None
        参数猜测器。
    x_col / y_col : str or int
        列选择模式。"auto" 时根据 x_pattern / y_pattern 搜索。
    x_pattern / y_pattern : str
        搜索模式。
    y_exclude_pattern : str | None
        排除模式，传给 _select_columns()。
    params_hint / fix : dict
        传递给 fit() 的额外参数。

    Returns
    -------
    FitResult
    """
    x, y, x_lbl, y_lbl = _select_columns(
        exp,
        x_col=x_col,
        y_col=y_col,
        x_pattern=x_pattern,
        y_pattern=y_pattern,
        y_exclude_pattern=y_exclude_pattern,
    )

    result = fit(x, y, model_func, guesser=guesser,
                 params_hint=params_hint, fix=fix)

    # 警告：拟合不收敛
    if not result.success:
        import warnings
        warnings.warn(
            f"[警告] {model_func.__name__} 拟合未收敛："
            f"exp={exp.exp_id} | χ²_ν={result.red_chi2:.1f}"
        )

    return result


# =============================================================================
# 实验类型调度
# =============================================================================

# 模块级缓存
_TYPE_REGISTRY: dict[str, Any] | None = None


def _load_type_registry() -> dict[str, Any]:
    """加载 experiment_types.yaml 并缓存。"""
    global _TYPE_REGISTRY
    if _TYPE_REGISTRY is not None:
        return _TYPE_REGISTRY

    try:
        import yaml
    except ImportError:
        raise ImportError(
            "yaml required for experiment type dispatch. "
            "Install with: pip install pyyaml"
        )

    cfg_path = Path(__file__).resolve().parent.parent / "experiment_types.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"experiment_types.yaml not found at {cfg_path}"
        )

    with open(cfg_path, encoding="utf-8") as f:
        _TYPE_REGISTRY = yaml.safe_load(f)

    return _TYPE_REGISTRY


def infer_experiment_type(title: str) -> str | None:
    """从实验标题推断实验类型。

    将 title 与 experiment_types.yaml 中的 match_keywords
    进行不区分大小写的**子串匹配**（``kw.lower() in title.lower()``）。
    返回 YAML 中第一个命中类型的 key；无匹配时返回 None。

    子串匹配意味着 ``"t1"`` 会命中任何包含 "t1" 的标题
    （如 ``"test1_ground"``）。实际操作中实验标题遵循
    ``"<type>_<details>, <qubit>"`` 格式，误触发概率极低。

    Parameters
    ----------
    title : str
        实验标题（来自 INI ``General.title``）。

    Returns
    -------
    str or None
        实验类型标识符（如 ``"T1"``, ``"ramsey"``, ``"rabi"``），
        无法推断时返回 None。

    Notes
    -----
    - 使用子串匹配（非精确匹配/词边界匹配）。
    - 首次匹配即返回（YAML 中靠前的类型有更高优先级）。
    - YAML 中的关键词顺序决定同标题多条匹配时的结果。
    """
    registry = _load_type_registry()
    title_lower = title.lower()

    for type_name, config in registry.items():
        for kw in config.get("match_keywords", []):
            if kw.lower() in title_lower:
                return type_name

    return None


def get_fit_function(exp_type: str) -> Callable[..., Any] | None:
    """根据实验类型标识符返回对应的 fit_*() 函数。

    Parameters
    ----------
    exp_type : str
        实验类型标识符（如 "T1", "ramsey"）。

    Returns
    -------
    Callable or None
        对应的拟合函数，类型未知时返回 None。

    Raises
    ------
    ValueError
        exp_type 已知但 fit_func 配置名称不合法。
    """
    registry = _load_type_registry()

    if exp_type not in registry:
        return None

    func_name = registry[exp_type].get("fit_func")
    if func_name is None:
        return None

    # 延迟导入，避免循环依赖
    if func_name == "fit_t1":
        from exp_toolkit.fitting.experiments.t1 import fit_t1
        return fit_t1
    elif func_name == "fit_spectro":
        from exp_toolkit.fitting.experiments.spectro import fit_spectro
        return fit_spectro
    elif func_name == "fit_ramsey":
        from exp_toolkit.fitting.experiments.ramsey import fit_ramsey
        return fit_ramsey
    elif func_name == "fit_rabi":
        from exp_toolkit.fitting.experiments.rabi import fit_rabi
        return fit_rabi
    elif func_name == "fit_rb":
        from exp_toolkit.fitting.experiments.rb import fit_rb
        return fit_rb
    else:
        raise ValueError(
            f"Unknown fit_func '{func_name}' for experiment type '{exp_type}'"
        )
