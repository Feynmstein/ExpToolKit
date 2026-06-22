"""Phase 4 测试 — 新增拟合模型、实验函数、实验类型调度。

覆盖：
- models.rb_exp: 前向计算 & 公式正确性
- guessers.guess_rb_exp: 初值合理性
- experiments/ramsey.py: fit_ramsey() 端到端
- experiments/rabi.py: fit_rabi() 端到端
- experiments/rb.py: fit_rb() 端到端
- experiments/_base.py: infer_experiment_type() + get_fit_function()
- experiments/spectro.py: f01 dispersion 负幅度边界
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from exp_toolkit.fitting.models import rb_exp
from exp_toolkit.fitting.guessers import guess_rb_exp
from exp_toolkit.fitting.engine import FitResult, fit
from exp_toolkit.fitting.experiments.ramsey import fit_ramsey
from exp_toolkit.fitting.experiments.rabi import fit_rabi
from exp_toolkit.fitting.experiments.rb import fit_rb
from exp_toolkit.fitting.experiments.spectro import (
    F01Dispersion,
    fit_f01_dispersion,
    fit_spectro,
)
from exp_toolkit.fitting.experiments._base import (
    get_fit_function,
    infer_experiment_type,
)
from exp_toolkit.io.readers import ColumnMeta, Experiment

# =============================================================================
# Shared helpers
# =============================================================================

RNG = np.random.default_rng(42)


def _make_ramsey_experiment(
    T2star: float = 12.0,
    delta_f: float = 0.15,
) -> Experiment:
    """创建合成 Ramsey Experiment。"""
    x = np.linspace(0, 60, 61)  # 0-60 μs
    y_true = (
        0.4 * np.exp(-x / T2star)
        * np.cos(2 * np.pi * delta_f * x + 0.5)
        + 0.5
    )
    noise = RNG.normal(0, 0.02, len(x))
    y = y_true + noise
    data = np.column_stack([x, 1 - y, y, 1 - y, y])
    return Experiment(
        exp_id="88888",
        title="T2star_ramsey, Q05",
        timestamp=datetime(2026, 6, 18, 10, 0, 0),
        independent_vars=[ColumnMeta(label="coherence delay", units="us", category="")],
        dependent_vars=[
            ColumnMeta(label="", units="", category="Q05 P0"),
            ColumnMeta(label="", units="", category="Q05 P1"),
            ColumnMeta(label="", units="", category="P0"),
            ColumnMeta(label="", units="", category="P1"),
        ],
        data=data,
        params=None,
        settings={},
        source_dir=Path("/tmp"),
        csv_path=Path("/tmp/88888.csv"),
        ini_path=Path("/tmp/88888.ini"),
    )


def _make_rabi_experiment(
    pi_width: float = 30.0,
    decay: float = 80.0,
) -> Experiment:
    """创建合成 Rabi Experiment（width sweep）。"""
    rabi_freq = 1.0 / (2 * pi_width)  # Ω
    x = np.linspace(0, 120, 61)  # 0-120 ns
    y_true = (
        0.4 * np.exp(-x / decay)
        * np.cos(2 * np.pi * rabi_freq * x + 0.0)
        + 0.5
    )
    noise = RNG.normal(0, 0.015, len(x))
    y = y_true + noise
    data = np.column_stack([x, 1 - y, y, 1 - y, y])
    return Experiment(
        exp_id="77777",
        title="rabi_width, Q03",
        timestamp=datetime(2026, 6, 18, 11, 0, 0),
        independent_vars=[ColumnMeta(label="pulse width", units="ns", category="")],
        dependent_vars=[
            ColumnMeta(label="", units="", category="Q03 P0"),
            ColumnMeta(label="", units="", category="Q03 P1"),
            ColumnMeta(label="", units="", category="P0"),
            ColumnMeta(label="", units="", category="P1"),
        ],
        data=data,
        params=None,
        settings={},
        source_dir=Path("/tmp"),
        csv_path=Path("/tmp/77777.csv"),
        ini_path=Path("/tmp/77777.ini"),
    )


def _make_rb_experiment(p_true: float = 0.985) -> Experiment:
    """创建合成 RB Experiment。"""
    x = np.array([1, 2, 4, 8, 16, 32, 64, 128], dtype=float)
    y_true = 0.5 * np.power(p_true, x) + 0.5
    noise = RNG.normal(0, 0.008, len(x))
    y = y_true + noise
    data = np.column_stack([x, y, 1 - y, y, 1 - y])
    return Experiment(
        exp_id="66666",
        title="RB_benchmarking, Q10",
        timestamp=datetime(2026, 6, 18, 12, 0, 0),
        independent_vars=[ColumnMeta(label="Clifford length", units="", category="")],
        dependent_vars=[
            ColumnMeta(label="", units="", category="Q10 P0"),
            ColumnMeta(label="", units="", category="Q10 P1"),
            ColumnMeta(label="", units="", category="P0"),
            ColumnMeta(label="", units="", category="P1"),
        ],
        data=data,
        params=None,
        settings={},
        source_dir=Path("/tmp"),
        csv_path=Path("/tmp/66666.csv"),
        ini_path=Path("/tmp/66666.ini"),
    )


# =============================================================================
# Test rb_exp model
# =============================================================================


class TestRbExpModel:
    """rb_exp 前向计算测试。"""

    def test_basic_decay(self):
        """基本衰减：p=0.9, N=10 → A·0.9^10+B。"""
        x = np.array([0, 5, 10])
        y = rb_exp(x, amplitude=0.5, p=0.9, offset=0.5)
        assert y[0] == pytest.approx(1.0)  # A·p^0 + B = 0.5 + 0.5
        assert y[1] == pytest.approx(0.5 * 0.9**5 + 0.5)
        assert y[2] == pytest.approx(0.5 * 0.9**10 + 0.5)

    def test_p_equals_one(self):
        """p=1 → 无衰减，常数输出。"""
        x = np.array([0, 10, 100])
        y = rb_exp(x, amplitude=0.3, p=1.0, offset=0.5)
        expected = 0.3 + 0.5
        np.testing.assert_allclose(y, expected)

    def test_p_zero(self):
        """p→0 → 快速衰减到 offset。"""
        x = np.array([0, 1, 5])
        y = rb_exp(x, amplitude=0.5, p=0.01, offset=0.5)
        assert y[0] == pytest.approx(1.0)  # 0.5*0.01^0 + 0.5
        assert y[1] == pytest.approx(0.5 * 0.01 + 0.5)
        assert y[2] == pytest.approx(0.5, abs=1e-4)  # ~B

    def test_output_shape(self):
        """输出形状与输入 x 相同。"""
        x = np.linspace(0, 100, 50)
        y = rb_exp(x, amplitude=0.5, p=0.99, offset=0.5)
        assert y.shape == x.shape
        assert y.dtype == float

    def test_monotonically_decreasing(self):
        """对于 A>0, 0<p<1，函数单调递减。"""
        x = np.arange(0, 100)
        y = rb_exp(x, amplitude=0.5, p=0.95, offset=0.5)
        assert np.all(np.diff(y) <= 0)


# =============================================================================
# Test guess_rb_exp
# =============================================================================


class TestGuessRbExp:
    """guess_rb_exp 初值猜测测试。"""

    def test_typical_rb_data(self):
        """典型 RB 数据猜测合理初值。"""
        x = np.array([1, 2, 4, 8, 16, 32, 64, 128], dtype=float)
        y = 0.5 * np.power(0.99, x) + 0.5
        guess = guess_rb_exp(x, y)

        assert "amplitude" in guess
        assert "p" in guess
        assert "offset" in guess
        assert guess["amplitude"] > 0
        assert 0.5 <= guess["p"] <= 0.9999
        # y[-1] = 0.5*0.99^128 + 0.5 ≈ 0.638 (not yet converged to B)
        # The guesser uses y[-1] as the offset estimate → ~0.638
        assert guess["offset"] == pytest.approx(0.638, abs=0.1)

    def test_few_points_raises(self):
        """数据点不足时抛出 ValueError。"""
        x = np.array([1, 2], dtype=float)
        y = np.array([0.99, 0.98])
        with pytest.raises(ValueError, match="at least 3"):
            guess_rb_exp(x, y)

    def test_all_nan_raises(self):
        """全 NaN 数据抛出 ValueError。"""
        x = np.array([1, 2, 4], dtype=float)
        y = np.full(3, np.nan)
        with pytest.raises(ValueError, match="all NaN"):
            guess_rb_exp(x, y)


# =============================================================================
# Test fit_ramsey
# =============================================================================


class TestFitRamsey:
    """fit_ramsey() 端到端测试。"""

    def test_recovers_T2star(self):
        """合成数据拟合恢复 T2* 在 15% 以内。"""
        true_T2star = 12.0
        exp = _make_ramsey_experiment(T2star=true_T2star, delta_f=0.15)
        result = fit_ramsey(exp)

        assert result.success
        assert "tau" in result.params
        T2star_fit = result.params["tau"]
        assert T2star_fit == pytest.approx(true_T2star, rel=0.15)

    def test_recovers_frequency(self):
        """合成数据拟合恢复 Δf 在 20% 以内。"""
        true_df = 0.15
        exp = _make_ramsey_experiment(delta_f=true_df)
        result = fit_ramsey(exp)

        assert result.success
        assert "frequency" in result.params
        assert result.params["frequency"] == pytest.approx(true_df, rel=0.20)

    def test_returns_fit_result_type(self):
        """返回 FitResult 类型。"""
        exp = _make_ramsey_experiment()
        result = fit_ramsey(exp)
        assert isinstance(result, FitResult)

    def test_all_parameters_present(self):
        """返回的 params 包含所有模型参数。"""
        exp = _make_ramsey_experiment()
        result = fit_ramsey(exp)

        for key in ("amplitude", "tau", "frequency", "phase", "offset"):
            assert key in result.params

    def test_column_not_found_raises(self):
        """无匹配列时抛出 ValueError。"""
        x = np.linspace(0, 60, 61)
        data = np.column_stack([x, x])  # 无 P1 列
        exp = Experiment(
            exp_id="00001", title="ramsey",
            timestamp=datetime(2026, 6, 18, 10, 0, 0),
            independent_vars=[ColumnMeta(label="delay", units="us", category="")],
            dependent_vars=[ColumnMeta(label="", units="", category="Q05 UNKNOWN")],
            data=data, params=None, settings={}, source_dir=Path("/tmp"),
            csv_path=Path("/tmp/00001.csv"), ini_path=Path("/tmp/00001.ini"),
        )
        with pytest.raises(ValueError, match="Cannot find y column"):
            fit_ramsey(exp)

    def test_params_hint_override(self):
        """params_hint 覆盖猜测器初值。"""
        exp = _make_ramsey_experiment(T2star=15.0, delta_f=0.2)
        result = fit_ramsey(exp, params_hint={
            "amplitude": 0.4, "tau": 14.0, "frequency": 0.18,
            "phase": 0.5, "offset": 0.5,
        })
        assert result.success


# =============================================================================
# Test fit_rabi
# =============================================================================


class TestFitRabi:
    """fit_rabi() 端到端测试。"""

    def test_recovers_rabi_frequency(self):
        """合成数据拟合恢复 Rabi 频率 Ω。"""
        true_pi_width = 30.0  # ns
        true_rabi_freq = 1.0 / (2 * true_pi_width)  # ≈ 0.01667 GHz
        exp = _make_rabi_experiment(pi_width=true_pi_width)
        result = fit_rabi(exp)

        assert result.success
        assert "frequency" in result.params
        rabi_freq_fit = result.params["frequency"]
        assert rabi_freq_fit == pytest.approx(true_rabi_freq, rel=0.15)

    def test_pi_pulse_calculation(self):
        """π 脉冲校准值 = 1/(2*Ω)。"""
        true_pi_width = 30.0
        exp = _make_rabi_experiment(pi_width=true_pi_width)
        result = fit_rabi(exp)

        omega = result.params["frequency"]
        pi_cal = 1.0 / (2.0 * omega)
        assert pi_cal == pytest.approx(true_pi_width, rel=0.15)

    def test_drive_var_width(self):
        """drive_var='width' 正常工作。"""
        exp = _make_rabi_experiment()
        result = fit_rabi(exp, drive_var="width")
        assert result.success

    def test_drive_var_amplitude(self):
        """drive_var='amplitude' 正常工作。"""
        exp = _make_rabi_experiment()
        result = fit_rabi(exp, drive_var="amplitude")
        assert result.success

    def test_invalid_drive_var_raises(self):
        """drive_var 不合法时抛出 ValueError。"""
        exp = _make_rabi_experiment()
        with pytest.raises(ValueError, match="drive_var must be"):
            fit_rabi(exp, drive_var="phase")


# =============================================================================
# Test fit_rb
# =============================================================================


class TestFitRb:
    """fit_rb() 端到端测试。"""

    def test_recovers_p(self):
        """合成 RB 数据拟合恢复衰减因子 p 在 1% 以内。"""
        true_p = 0.985
        exp = _make_rb_experiment(p_true=true_p)
        result = fit_rb(exp)

        assert result.success
        assert "p" in result.params
        assert result.params["p"] == pytest.approx(true_p, rel=0.01)

    def test_gate_fidelity_calculation(self):
        """单比特门保真度 F = 1 - (1-p)/2。"""
        exp = _make_rb_experiment(p_true=0.99)
        result = fit_rb(exp)

        p_fit = result.params["p"]
        F_gate = 1.0 - (1.0 - p_fit) / 2.0
        # 真值: F = 1 - (1-0.99)/2 = 0.995
        assert F_gate == pytest.approx(0.995, abs=0.02)

    def test_returns_fit_result_type(self):
        """返回 FitResult 类型。"""
        exp = _make_rb_experiment()
        result = fit_rb(exp)
        assert isinstance(result, FitResult)

    def test_all_parameters_present(self):
        """返回的 params 包含 amplitude, p, offset。"""
        exp = _make_rb_experiment()
        result = fit_rb(exp)

        for key in ("amplitude", "p", "offset"):
            assert key in result.params

    def test_p_in_valid_range(self):
        """拟合的 p 在 (0.5, 1.0] 范围内。"""
        exp = _make_rb_experiment(p_true=0.95)
        result = fit_rb(exp)

        assert 0.5 < result.params["p"] <= 1.0

    def test_column_not_found_raises(self):
        """无匹配列时抛出 ValueError。"""
        x = np.array([1, 2, 4, 8], dtype=float)
        data = np.column_stack([x, x])
        exp = Experiment(
            exp_id="00002", title="RB",
            timestamp=datetime(2026, 6, 18, 12, 0, 0),
            independent_vars=[ColumnMeta(label="N", units="", category="")],
            dependent_vars=[ColumnMeta(label="", units="", category="UNKNOWN")],
            data=data, params=None, settings={}, source_dir=Path("/tmp"),
            csv_path=Path("/tmp/00002.csv"), ini_path=Path("/tmp/00002.ini"),
        )
        with pytest.raises(ValueError, match="Cannot find y column"):
            fit_rb(exp)


# =============================================================================
# Test experiment type dispatch
# =============================================================================


class TestExperimentTypeDispatch:
    """infer_experiment_type() + get_fit_function() 测试。"""

    def test_infer_T1(self):
        assert infer_experiment_type("T1_ground, Q16") == "T1"
        assert infer_experiment_type("t1_excited, Q01") == "T1"

    def test_infer_spectro(self):
        assert infer_experiment_type("spectro, Q07") == "spectro"
        assert infer_experiment_type("spectroscopy_2d, Q15") == "spectro"

    def test_infer_ramsey(self):
        assert infer_experiment_type("T2star_ramsey, Q05") == "ramsey"
        assert infer_experiment_type("ramsey_fringes, Q10") == "ramsey"
        assert infer_experiment_type("T2*_measurement, Q03") == "ramsey"

    def test_infer_rabi(self):
        assert infer_experiment_type("rabi_width, Q03") == "rabi"
        assert infer_experiment_type("rabi_amplitude, Q16") == "rabi"

    def test_infer_rb(self):
        assert infer_experiment_type("RB_benchmarking, Q10") == "rb"
        assert infer_experiment_type("randomized_benchmarking, Q01") == "rb"
        assert infer_experiment_type("benchmarking_1qb, Q05") == "rb"

    def test_infer_unknown(self):
        assert infer_experiment_type("unknown_experiment") is None
        assert infer_experiment_type("") is None

    def test_infer_case_insensitive(self):
        assert infer_experiment_type("Rb_Benchmarking, Q10") == "rb"
        assert infer_experiment_type("Ramsey_Fringes, Q05") == "ramsey"

    def test_get_fit_function_returns_callable(self):
        for exp_type in ("T1", "spectro", "ramsey", "rabi", "rb"):
            func = get_fit_function(exp_type)
            assert callable(func), f"get_fit_function({exp_type!r}) not callable"

    def test_get_fit_function_unknown(self):
        assert get_fit_function("unknown") is None

    def test_dispatch_roundtrip(self):
        """推断出的类型可以通过 get_fit_function 获取函数。"""
        exp_type = infer_experiment_type("T1_ground, Q16")
        func = get_fit_function(exp_type)
        assert func.__name__ == "fit_t1"


# =============================================================================
# Test f01 dispersion negative amplitude
# =============================================================================


class TestF01DispersionNegativeAmplitude:
    """#002 P2-2: f01 dispersion 负幅度 Gaussian 边界处理。"""

    def _make_2d_spectro_dip(
        self,
        zpa_vals: np.ndarray,
        freq_vals: np.ndarray,
        f01_at_zpa: callable,
    ) -> Experiment:
        """创建合成 2D 光谱 Experiment，f01 随 zpa 变化。"""
        rows = []
        independent_vars = [
            ColumnMeta(label="zpa", units="", category=""),
            ColumnMeta(label="dr_freq", units="GHz", category=""),
        ]
        dependent_vars = [
            ColumnMeta(label="", units="", category="Q07 IQ Amp"),
        ]

        for zpa in zpa_vals:
            f01 = f01_at_zpa(zpa)
            for freq in freq_vals:
                # Lorentzian centered at f01
                amps = 0.8
                gamma = 0.005
                y = amps * gamma**2 / ((freq - f01) ** 2 + gamma**2) + 0.1
                rows.append([zpa, freq, y])

        data = np.array(rows)
        return Experiment(
            exp_id="55555",
            title="spectro_dip, Q07",
            timestamp=datetime(2026, 6, 18, 13, 0, 0),
            independent_vars=independent_vars,
            dependent_vars=dependent_vars,
            data=data,
            params=None,
            settings={},
            source_dir=Path("/tmp"),
            csv_path=Path("/tmp/55555.csv"),
            ini_path=Path("/tmp/55555.ini"),
        )

    def test_positive_amplitude_dispersion(self):
        """正幅度 Gaussian（f01 peak vs zpa）正常拟合。"""
        zpa_vals = np.linspace(-0.3, 0.3, 11)
        freq_vals = np.linspace(4.0, 5.0, 101)

        # f01(zpa) = 0.4 * exp(-(zpa/0.1)^2 / 2) + 4.5  (peak)
        def f01_fn(zpa):
            return 0.4 * np.exp(-(zpa / 0.1) ** 2 / 2) + 4.5

        exp = self._make_2d_spectro_dip(zpa_vals, freq_vals, f01_fn)
        result = fit_f01_dispersion(exp)

        assert result.f01_max > result.f01_min
        assert result.f01_max == pytest.approx(4.9, rel=0.05)
        assert result.f01_min == pytest.approx(4.5, rel=0.05)

    def test_negative_amplitude_dispersion(self):
        """负幅度 Gaussian（f01 dip vs zpa）正确处理 min/max。"""
        zpa_vals = np.linspace(-0.3, 0.3, 11)
        freq_vals = np.linspace(4.0, 5.0, 101)

        # f01(zpa) = -0.4 * exp(-(zpa/0.1)^2 / 2) + 4.9  (dip)
        def f01_fn(zpa):
            return -0.4 * np.exp(-(zpa / 0.1) ** 2 / 2) + 4.9

        exp = self._make_2d_spectro_dip(zpa_vals, freq_vals, f01_fn)
        result = fit_f01_dispersion(exp)

        # Even with negative amplitude, max > min should hold
        assert result.f01_max > result.f01_min
        # min ~ 4.5 (at center of dip), max ~ 4.9 (at tails)
        assert result.f01_min == pytest.approx(4.5, rel=0.05)
        assert result.f01_max == pytest.approx(4.9, rel=0.05)

    def test_large_discrepancy_falls_back_to_empirical(self):
        """Gaussian 偏离过大时回退到经验范围。"""
        # Create data where zpa range is very narrow but f01 varies a lot
        zpa_vals = np.linspace(0, 0.01, 7)
        freq_vals = np.linspace(4.0, 5.0, 101)

        def f01_fn(zpa):
            return 0.3 * np.exp(-(zpa / 0.002) ** 2 / 2) + 4.5

        exp = self._make_2d_spectro_dip(zpa_vals, freq_vals, f01_fn)
        # Should not crash; might warn but still return valid range
        result = fit_f01_dispersion(exp)
        assert result.f01_max >= result.f01_min
        assert np.isfinite(result.f01_min)
        assert np.isfinite(result.f01_max)
