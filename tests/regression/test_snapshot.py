"""快照回归测试。

对真实数据运行拟合，结果与已有快照对比。容差：3σ + 1% 相对误差。

前置条件：
  - tests/regression/data/<exp_id>/*.csv, *.ini, *.json 存在（gitignore + LFS）
  - tests/regression/snapshots/<exp_id>_<param>.json 存在（git tracked）

新增快照：
  python -c "
  from exp_toolkit.io import load_experiment
  from exp_toolkit.fitting import fit_t1
  import json
  exp = load_experiment('tests/regression/data/00747/...csv')
  r = fit_t1(exp)
  json.dump({'tau': r.params['tau'], 'error_tau': r.errors['tau'],
             'success': r.success}, open('tests/regression/snapshots/00747_T1.json','w'), indent=2)
  "
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from exp_toolkit.io.readers import load_experiment
from exp_toolkit.fitting.experiments.t1 import fit_t1
from exp_toolkit.fitting.experiments.spectro import fit_spectro, fit_f01_dispersion

# conftest.py is auto-loaded by pytest; import via package path
from tests.regression.conftest import require_data

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


def _load_snapshot(snapshot_name: str) -> dict:
    """加载快照 JSON 文件。"""
    path = SNAPSHOT_DIR / snapshot_name
    if not path.exists():
        pytest.skip(f"快照 {snapshot_name} 不存在，需要先生成")
    with open(path) as f:
        return json.load(f)


def _check_param(value: float, error: float | None, snapshot: dict,
                 param_key: str, tol_relative: float = 0.01) -> None:
    """检查拟合参数与快照一致。

    Args:
        value: 当前拟合值
        error: 当前拟合不确定度
        snapshot: 快照字典
        param_key: 参数键名
        tol_relative: 相对容差（默认 1%）
    """
    snap_val = snapshot[param_key]
    # 容差 = max(3σ, tol_relative × |snap_val|)
    err_val = error if error and error > 0 else abs(snap_val) * 0.001
    tolerance = max(3 * err_val, tol_relative * abs(snap_val))
    diff = abs(value - snap_val)
    assert diff <= tolerance, (
        f"{param_key}: 当前={value:.4f}, 快照={snap_val:.4f}, "
        f"差值={diff:.4f}, 容差={tolerance:.4f} (3σ={3*err_val:.4f}, "
        f"相对={tol_relative*abs(snap_val):.4f})"
    )


# =============================================================================
# T1 回归
# =============================================================================

T1_EXPERIMENTS = []  # 按需扩充：["00747", "00812", ...]


@pytest.mark.regression
@pytest.mark.parametrize("exp_id", T1_EXPERIMENTS)
def test_t1_regression(exp_id: str):
    exp_dir = require_data(exp_id)
    csv_path = next(exp_dir.glob("*.csv"))
    exp = load_experiment(str(csv_path))
    result = fit_t1(exp)
    snapshot = _load_snapshot(f"{exp_id}_T1.json")

    assert result.success == snapshot.get("success", True), \
        f"拟合成功标志不一致: {result.success} ≠ {snapshot.get('success')}"
    _check_param(result.params["tau"], result.errors.get("tau"), snapshot, "tau")


# =============================================================================
# 光谱 f01 dispersion 回归
# =============================================================================

SPECTRO_EXPERIMENTS = []  # 按需扩充：["00023"]


@pytest.mark.regression
@pytest.mark.parametrize("exp_id", SPECTRO_EXPERIMENTS)
def test_f01_regression(exp_id: str):
    exp_dir = require_data(exp_id)
    csv_path = next(exp_dir.glob("*.csv"))
    exp = load_experiment(str(csv_path))
    result = fit_f01_dispersion(exp)
    snapshot = _load_snapshot(f"{exp_id}_f01.json")

    _check_param(result.f01_min, None, snapshot, "f01_min", tol_relative=0.02)
    _check_param(result.f01_max, None, snapshot, "f01_max", tol_relative=0.02)


# =============================================================================
# 快照生成辅助（手动运行）
# =============================================================================

def generate_t1_snapshot(exp_id: str) -> None:
    """手动生成 T1 快照文件。

    运行方式：
        python -c "from tests.regression.test_snapshot import generate_t1_snapshot; generate_t1_snapshot('00747')"
    """
    exp_dir = require_data(exp_id)
    csv_path = next(exp_dir.glob("*.csv"))
    exp = load_experiment(str(csv_path))
    result = fit_t1(exp)
    snapshot = {
        "tau": result.params["tau"],
        "error_tau": result.errors.get("tau"),
        "A": result.params.get("A"),
        "C": result.params.get("C"),
        "success": result.success,
        "r_squared": result.r_squared,
        "red_chi2": result.red_chi2,
    }
    out_path = SNAPSHOT_DIR / f"{exp_id}_T1.json"
    with open(out_path, "w") as f:
        json.dump(snapshot, f, indent=2, default=float)
    print(f"快照已生成: {out_path}")
    print(json.dumps(snapshot, indent=2, default=str))
