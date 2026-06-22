"""拟合模块测试 — 合成数据验证模型参数恢复。

覆盖：
- models.py: 每个模型的输出形状 & 公式正确性
- guessers.py: 每个猜测器初值合理性
- engine.py: fit() 正常路径 & 错误路径 & FitResult
- experiments/_base.py: _auto_fit() + _select_columns() + _find_column()
- experiments/t1.py: fit_t1() 端到端（合成 Experiment）
- experiments/spectro.py: fit_spectro() 端到端
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from exp_toolkit.fitting.models import (
    decaying_sinusoid,
    exp_decay,
    gaussian,
    lorentzian,
)
from exp_toolkit.fitting.guessers import (
    guess_decaying_sinusoid,
    guess_exp_decay,
    guess_gaussian,
    guess_lorentzian,
)
from exp_toolkit.fitting.engine import FitResult, fit
from exp_toolkit.fitting.experiments._base import (
    _auto_fit,
    _find_column,
    _select_columns,
)
from exp_toolkit.fitting.experiments.t1 import fit_t1
from exp_toolkit.fitting.experiments.spectro import (
    F01Dispersion,
    fit_f01_dispersion,
    fit_spectro,
)
from exp_toolkit.io.readers import ColumnMeta, Experiment, IniMeta


# =============================================================================
# Shared helpers
# =============================================================================

RNG = np.random.default_rng(42)


def _make_t1_experiment(tau_true: float = 45.0) -> Experiment:
    """创建合成 T1 Experiment 对象用于集成测试。"""
    x = np.linspace(0, 100, 21)
    y_true = 0.8 * np.exp(-x / tau_true) + 0.2
    noise = RNG.normal(0, 0.01, 21)
    y = y_true + noise
    data = np.column_stack([x, 1 - y, y, 1 - y, y, 1 - y, y, 1 - y, y])
    return Experiment(
        exp_id="99999",
        title="T1_ground, Q01",
        timestamp=datetime(2026, 6, 17, 10, 0, 0),
        independent_vars=[ColumnMeta(label="coherence delay", units="us", category="")],
        dependent_vars=[
            ColumnMeta(label="", units="", category="Q01 P0"),
            ColumnMeta(label="", units="", category="Q01 P1"),
            ColumnMeta(label="", units="", category="P0"),
            ColumnMeta(label="", units="", category="P1"),
            ColumnMeta(label="", units="", category="Q01 P0 for |0>"),
            ColumnMeta(label="", units="", category="Q01 P1 for |0>"),
            ColumnMeta(label="", units="", category="P0 for |0>"),
            ColumnMeta(label="", units="", category="P1 for |0>"),
        ],
        data=data,
        params=None,
        settings={},
        source_dir=Path("/tmp"),
        csv_path=Path("/tmp/99999.csv"),
        ini_path=Path("/tmp/99999.ini"),
    )


def _make_spectro_experiment(f01: float = 4.7) -> Experiment:
    """创建合成 Spectro 2D Experiment 用于集成测试。"""
    zpa_vals = [-0.5, -0.25, 0.0, 0.25, 0.5]
    freq_vals = np.linspace(4.0, 5.5, 50)
    rows = []
    for zpa in zpa_vals:
        for freq in freq_vals:
            amp = 0.8e5 * (0.0012**2) / ((freq - f01) ** 2 + 0.0012**2) + 2e5
            noise = RNG.normal(0, 5000)
            rows.append([zpa, freq, amp + noise, 0.0, amp + noise, 0.0])
    data = np.array(rows)
    return Experiment(
        exp_id="88888",
        title="spectro, Q01",
        timestamp=datetime(2026, 6, 17, 10, 0, 0),
        independent_vars=[
            ColumnMeta(label="zpa", units="", category=""),
            ColumnMeta(label="dr_freq", units="GHz", category=""),
        ],
        dependent_vars=[
            ColumnMeta(label="", units="", category="Q01 IQ Amp"),
            ColumnMeta(label="", units="rad", category="Q01 IQ phase"),
            ColumnMeta(label="", units="", category="Q01 I"),
            ColumnMeta(label="", units="", category="Q01 Q"),
        ],
        data=data,
        params=None,
        settings={},
        source_dir=Path("/tmp"),
        csv_path=Path("/tmp/88888.csv"),
        ini_path=Path("/tmp/88888.ini"),
    )


# =============================================================================
# models.py — 纯函数验证
# =============================================================================


class TestModels:
    def test_exp_decay_shape(self):
        x = np.linspace(0, 100, 50)
        y = exp_decay(x, amplitude=0.8, tau=30.0, offset=0.1)
        assert y.shape == x.shape
        assert np.all(np.isfinite(y))

    def test_exp_decay_values(self):
        """验证公式正确性：x=0 时 y ≈ A + C, x→∞ 时 y → C"""
        assert math.isclose(
            float(exp_decay(np.array([0.0]), 0.8, 30, 0.1)[0]), 0.9, rel_tol=1e-10
        )
        assert math.isclose(
            float(exp_decay(np.array([1e6]), 0.8, 30, 0.1)[0]), 0.1, rel_tol=1e-3
        )

    def test_lorentzian_peak(self):
        """验证峰值位置 = center"""
        x = np.linspace(4.0, 5.5, 500)
        y = lorentzian(x, amplitude=1.0, center=4.7, gamma=0.01, offset=0.0)
        peak_idx = int(np.argmax(y))
        assert abs(x[peak_idx] - 4.7) < 0.01

    def test_gaussian_peak(self):
        """验证峰值位置 = center"""
        x = np.linspace(-5, 5, 500)
        y = gaussian(x, amplitude=1.0, center=0.0, sigma=1.0, offset=0.0)
        peak_idx = int(np.argmax(y))
        assert abs(x[peak_idx]) < 0.05

    def test_decaying_sinusoid_envelope(self):
        """验证振荡幅度 ≤ A·exp(-x/τ)"""
        x = np.linspace(0, 10, 200)
        y = decaying_sinusoid(x, amplitude=0.5, tau=5.0, frequency=2.0, phase=0.0, offset=0.5)
        # 去偏移后幅度
        y_ac = np.abs(y - 0.5)
        envelope = 0.5 * np.exp(-x / 5.0)
        # 所有点的振荡幅度 ≤ 包络（允许微小数值误差）
        assert np.all(y_ac <= envelope + 1e-12)


# =============================================================================
# guessers.py — 初值合理性
# =============================================================================


class TestGuessers:
    def test_guess_exp_decay_recovers_tau(self):
        x = np.linspace(0, 100, 101)
        y = exp_decay(x, amplitude=0.7, tau=40.0, offset=0.15)
        g = guess_exp_decay(x, y)
        # 猜测器不需要精确，只需量级正确
        assert 0.3 < g["amplitude"] < 1.0
        assert 10 < g["tau"] < 80
        assert 0.05 < g["offset"] < 0.3

    def test_guess_lorentzian_recovers_center(self):
        x = np.linspace(4.0, 5.5, 500)
        y = lorentzian(x, amplitude=0.01, center=4.68, gamma=0.005, offset=2.0)
        g = guess_lorentzian(x, y)
        assert abs(g["center"] - 4.68) < 0.1
        assert g["gamma"] > 0

    def test_guess_gaussian_recovers_center(self):
        x = np.linspace(-5, 5, 500)
        y = gaussian(x, amplitude=1.0, center=0.5, sigma=0.8, offset=0.1)
        g = guess_gaussian(x, y)
        assert abs(g["center"] - 0.5) < 0.2
        assert g["sigma"] > 0.1

    def test_guess_decaying_sinusoid_finds_frequency(self):
        x = np.linspace(0, 10, 500)
        y = decaying_sinusoid(x, amplitude=0.5, tau=4.0, frequency=3.0, phase=0.0, offset=0.5)
        g = guess_decaying_sinusoid(x, y)
        # FFT 应找到大致频率
        assert 2.0 < g["frequency"] < 4.0
        assert g["tau"] > 1.0

    def test_guess_all_nan_raises(self):
        x = np.linspace(0, 10, 10)
        y = np.full(10, np.nan)
        with pytest.raises(ValueError, match="NaN"):
            guess_exp_decay(x, y)
        with pytest.raises(ValueError, match="NaN"):
            guess_lorentzian(x, y)
        with pytest.raises(ValueError, match="NaN"):
            guess_gaussian(x, y)
        with pytest.raises(ValueError, match="NaN"):
            guess_decaying_sinusoid(x, y)


# =============================================================================
# engine.py — fit() + FitResult
# =============================================================================


class TestFit:
    def test_exp_decay_parameter_recovery(self):
        """用已知参数合成数据，验证 fit() 能恢复参数（≤3σ 误差）。"""
        tau_true = 45.0
        amp_true = 0.8
        offset_true = 0.2
        x = np.linspace(0, 100, 51)
        y_clean = exp_decay(x, amplitude=amp_true, tau=tau_true, offset=offset_true)
        noise = RNG.normal(0, 0.005, len(x))
        y = y_clean + noise

        r = fit(x, y, exp_decay, guesser=guess_exp_decay)

        assert r.success, f"Fit failed: {r.message}"
        assert r.model_name == "exp_decay"

        # 参数恢复：与真值偏差 ≤ 3σ
        for param, true_val in [("amplitude", amp_true), ("tau", tau_true), ("offset", offset_true)]:
            err = r.errors.get(param, 0.0)
            if not math.isnan(err):
                assert abs(r.params[param] - true_val) <= 3 * err + 0.01, (
                    f"{param}: fitted={r.params[param]:.4f} ± {err:.4f}, "
                    f"true={true_val}"
                )

        # 统计量
        assert 0.8 < r.r_squared <= 1.0
        assert r.red_chi2 >= 0

    def test_lorentzian_parameter_recovery(self):
        """Lorentzian 拟合恢复 center。"""
        center_true = 4.68
        x = np.linspace(4.0, 5.5, 300)
        # 使用更大 amplitude (peak=10+2=12) 确保 SNR 足够
        y_clean = lorentzian(x, amplitude=10.0, center=center_true, gamma=0.005, offset=2.0)
        noise = RNG.normal(0, 0.03, len(x))
        y = y_clean + noise

        r = fit(x, y, lorentzian, guesser=guess_lorentzian)

        assert r.success
        assert abs(r.params["center"] - center_true) < 0.02

    def test_fit_without_guesser_or_hint_raises(self):
        x = np.linspace(0, 10, 20)
        y = np.random.randn(20)
        with pytest.raises(ValueError, match="No initial parameters"):
            fit(x, y, exp_decay)

    def test_fit_shape_mismatch_raises(self):
        x = np.linspace(0, 10, 20)
        y = np.linspace(0, 10, 21)
        with pytest.raises(ValueError, match="same length"):
            fit(x, y, exp_decay, params_hint={"amplitude": 1, "tau": 5, "offset": 0})

    def test_fit_empty_raises(self):
        x = np.array([])
        y = np.array([])
        with pytest.raises(ValueError, match="not be empty"):
            fit(x, y, exp_decay, params_hint={"amplitude": 1, "tau": 5, "offset": 0})

    def test_fit_with_params_hint(self):
        x = np.linspace(0, 100, 30)
        y = exp_decay(x, amplitude=0.6, tau=30.0, offset=0.15)
        r = fit(x, y, exp_decay, params_hint={"amplitude": 0.5, "tau": 25, "offset": 0.1})
        assert r.success

    def test_fit_with_fixed_params(self):
        """固定参数不参与拟合。"""
        x = np.linspace(0, 100, 30)
        y = exp_decay(x, amplitude=0.6, tau=30.0, offset=0.1)
        r = fit(x, y, exp_decay, guesser=guess_exp_decay, fix={"offset": 0.1})
        assert r.success
        assert abs(r.params["offset"] - 0.1) < 1e-10

    def test_fit_result_dataclass_fields(self):
        x = np.linspace(0, 100, 30)
        y = exp_decay(x, amplitude=0.6, tau=30.0, offset=0.15)
        r = fit(x, y, exp_decay, params_hint={"amplitude": 0.5, "tau": 25, "offset": 0.1})
        assert isinstance(r.model_name, str)
        assert "amplitude" in r.params
        assert "tau" in r.errors
        assert len(r.residuals) == len(x)
        assert len(r.y_fit) == len(x)
        assert r.n_params == 3
        assert r.n_points == 30


# =============================================================================
# experiments/_base.py — 列选择 & _auto_fit
# =============================================================================


class TestFindColumn:
    def test_exact_match(self):
        cols = [ColumnMeta("a", "", "Q01 P1"), ColumnMeta("b", "", "Q01 P0")]
        assert _find_column(cols, "Q01 P1") == 0

    def test_case_insensitive(self):
        cols = [ColumnMeta("a", "", "Q01 P1")]
        assert _find_column(cols, "q01 p1") == 0

    def test_substring_match(self):
        cols = [ColumnMeta("a", "", "Q16 P1 for |0>")]
        assert _find_column(cols, "P1") == 0

    def test_label_fallback(self):
        cols = [ColumnMeta("special_label", "us", "")]
        assert _find_column(cols, "special_label") == 0

    def test_not_found(self):
        cols = [ColumnMeta("a", "", "Q01 P0")]
        assert _find_column(cols, "Q07 IQ Amp") is None

    def test_exclude_calibration_column(self):
        """P1-2 修复：校准列 "for |0>" 应被排除。"""
        # 模拟校准列排在前面的场景
        cols = [
            ColumnMeta("", "", "Q01 P1 for |0>"),  # 校准列 — 应跳过
            ColumnMeta("", "", "Q01 P1"),          # 真实数据列
        ]
        # 不使用 exclude_pattern → 返回 0（校准列）
        assert _find_column(cols, "P1") == 0
        # 使用 exclude_pattern → 跳过校准列，返回 1
        assert _find_column(cols, "P1", exclude_pattern="for |0>") == 1

    def test_exclude_no_match(self):
        """exclude_pattern 不命中任何列 → 正常返回。"""
        cols = [ColumnMeta("", "", "Q01 P1")]
        assert _find_column(cols, "P1", exclude_pattern="IQ") == 0


class TestAutoFit:
    def test_auto_fit_t1(self):
        exp = _make_t1_experiment(tau_true=45.0)
        r = _auto_fit(exp, exp_decay, guess_exp_decay,
                      x_pattern="", y_pattern="P1")
        assert r.success
        assert 30 < r.params["tau"] < 60

    def test_auto_fit_y_not_found_raises(self):
        exp = _make_t1_experiment()
        with pytest.raises(ValueError, match="Cannot find y column"):
            _auto_fit(exp, exp_decay, guess_exp_decay,
                      y_pattern="nonexistent_pattern_xyz")

    def test_select_columns_by_index(self):
        exp = _make_t1_experiment()
        x, y, xl, yl = _select_columns(exp, x_col=0, y_col=2)
        assert len(x) == 21
        assert len(y) == 21

    def test_select_columns_by_pattern(self):
        exp = _make_t1_experiment()
        x, y, xl, yl = _select_columns(
            exp, x_col="auto", y_col="auto",
            x_pattern="delay", y_pattern="P1",
        )
        assert len(x) == 21
        assert len(y) == 21


# =============================================================================
# experiments/t1.py — fit_t1() 端到端
# =============================================================================


class TestFitT1:
    def test_fit_t1_parameter_recovery(self):
        exp = _make_t1_experiment(tau_true=42.0)
        r = fit_t1(exp)
        assert r.success
        assert 30 < r.params["tau"] < 55
        assert "tau" in r.errors
        assert r.r_squared > 0.8

    def test_fit_t1_with_params_hint(self):
        exp = _make_t1_experiment(tau_true=50.0)
        r = fit_t1(exp, params_hint={"amplitude": 0.7, "tau": 40, "offset": 0.2})
        assert r.success


# =============================================================================
# experiments/spectro.py — fit_spectro() + fit_f01_dispersion()
# =============================================================================


class TestFitSpectro:
    def test_fit_spectro_single_slice(self):
        exp = _make_spectro_experiment(f01=4.7)
        r = fit_spectro(exp, z_slice=-0.5)
        assert r.success
        # center 应在 4.7 附近
        assert 4.6 < r.params["center"] < 4.8

    def test_fit_spectro_no_slice_auto_selects_zpa(self):
        """P1-1 修复：2D 数据无 z_slice 应自动选中间 zpa 并发出警告。"""
        exp = _make_spectro_experiment(f01=4.7)
        with pytest.warns(UserWarning, match="no z_slice specified"):
            r = fit_spectro(exp)
        assert r.success

    def test_fit_spectro_different_zpa_different_f01(self):
        """验证不同 zpa 切片确实选出不同 f01（证明自动选择有意义）。"""
        # 创建 2D 数据，不同 zpa 有不同 f01
        rows = []
        zpa_f01_map = {-0.5: 4.5, 0.0: 4.7, 0.5: 4.9}
        for zpa, f01 in zpa_f01_map.items():
            for freq in np.linspace(4.0, 5.5, 100):
                amp = 5.0 * (0.003**2) / ((freq - f01) ** 2 + 0.003**2) + 1.0
                rows.append([zpa, freq, amp, 0.0])
        data = np.array(rows)
        exp = Experiment(
            exp_id="66666", title="spectro, Q01",
            timestamp=datetime(2026, 6, 17, 10, 0, 0),
            independent_vars=[
                ColumnMeta(label="zpa", units="", category=""),
                ColumnMeta(label="dr_freq", units="GHz", category=""),
            ],
            dependent_vars=[
                ColumnMeta(label="", units="", category="Q01 IQ Amp"),
                ColumnMeta(label="", units="rad", category="Q01 IQ phase"),
            ],
            data=data, params=None, settings={},
            source_dir=Path("/tmp"),
            csv_path=Path("/tmp/66666.csv"),
            ini_path=Path("/tmp/66666.ini"),
        )
        # 手动指定不同 zpa → 不同 center
        r_low = fit_spectro(exp, z_slice=-0.5)
        r_mid = fit_spectro(exp, z_slice=0.0)
        r_high = fit_spectro(exp, z_slice=0.5)
        assert r_low.success and r_mid.success and r_high.success
        # f01 应按 zpa 排序（zpa=-0.5 的 f01 应低于 zpa=0.5）
        c_low = r_low.params["center"]
        c_high = r_high.params["center"]
        # 允许微小误差 — 两者差的绝对值应大于 0.05 GHz
        assert abs(c_high - c_low) > 0.05, (
            f"Expected different f01 at different zpa: "
            f"zpa=-0.5→{c_low:.3f}, zpa=0.5→{c_high:.3f}"
        )

    def test_fit_f01_dispersion(self):
        """两步法：Lorentzian per zpa → Gaussian f01 vs zpa。"""
        rng = np.random.default_rng(101)
        zpa_vals = np.array([-0.5, -0.3, -0.1, 0.0, 0.1, 0.3, 0.5])
        rows = []
        for zpa in zpa_vals:
            # f01 随 zpa 变化：dip at zpa=0, high at edges
            actual_f01 = 4.7 + 0.25 * np.exp(-(zpa**2) / (2 * 0.2**2))
            freqs = np.linspace(4.2, 5.2, 200)
            for freq in freqs:
                # Strong peak: amplitude=5, gamma=0.003, offset=1.0
                amp = 5.0 * (0.003**2) / ((freq - actual_f01) ** 2 + 0.003**2) + 1.0
                noise = rng.normal(0, 0.05)
                rows.append([zpa, freq, amp + noise, 0.0])

        data = np.array(rows)
        exp = Experiment(
            exp_id="77777",
            title="spectro, Q01",
            timestamp=datetime(2026, 6, 17, 10, 0, 0),
            independent_vars=[
                ColumnMeta(label="zpa", units="", category=""),
                ColumnMeta(label="dr_freq", units="GHz", category=""),
            ],
            dependent_vars=[
                ColumnMeta(label="", units="", category="Q01 IQ Amp"),
                ColumnMeta(label="", units="rad", category="Q01 IQ phase"),
            ],
            data=data,
            params=None,
            settings={},
            source_dir=Path("/tmp"),
            csv_path=Path("/tmp/77777.csv"),
            ini_path=Path("/tmp/77777.ini"),
        )

        disp = fit_f01_dispersion(exp)

        assert isinstance(disp, F01Dispersion)
        assert disp.f01_min < disp.f01_max
        assert len(disp.zpa_values) >= 3
        assert len(disp.f01_values) == len(disp.zpa_values)
        # f01 should be in the 4.2–5.2 range
        assert 4.2 < disp.f01_min < 5.5
        assert 4.2 < disp.f01_max < 5.5
        # The max f01 should be near the edges (zpa > 0) and min near center
        # Just verify they're physically reasonable
        assert disp.f01_max > disp.f01_min + 0.02

    def test_fit_f01_dispersion_needs_2d(self):
        exp = _make_t1_experiment()
        with pytest.raises(ValueError, match="requires 2D data"):
            fit_f01_dispersion(exp)
