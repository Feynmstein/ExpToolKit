"""Phase 2 测试 — ChipTopology + ChipArtist + ChipState + fit_plot。

覆盖：
- ChipTopology: from_grid, custom layout, couplers, neighbors, pos_of, errors
- ChipArtist: draw, highlight_measured, colormap_param, annotate, coupler_lines, save
- ChipState: new/load/save roundtrip, add_*(), get_latest(), list_measured_qubits()
- fit_plot: plot_fit_result, plot_spectroscopy_2d
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest

from exp_toolkit.visualization import (
    ChipArtist,
    ChipTopology,
    plot_fit_result,
    plot_spectroscopy_2d,
)
from exp_toolkit.state import (
    ChipState,
    DriveEntry,
    F01Range,
    ParameterEntry,
    QubitState,
    ReadoutEntry,
)
from exp_toolkit.fitting.engine import FitResult, fit
from exp_toolkit.fitting.models import exp_decay, lorentzian
from exp_toolkit.fitting.guessers import guess_exp_decay, guess_lorentzian
from exp_toolkit.io.readers import ColumnMeta, Experiment


# =============================================================================
# ChipTopology
# =============================================================================


class TestChipTopology:
    def test_from_grid_5x5(self):
        topo = ChipTopology.from_grid(5, 5)
        assert topo.rows == 5
        assert topo.cols == 5
        assert len(topo.qubit_names) == 25
        # row-major: first row is Q01-Q05
        assert topo.qubit_names[:5] == ["Q01", "Q02", "Q03", "Q04", "Q05"]
        assert topo.pos_of("Q01") == (0, 0)
        assert topo.pos_of("Q25") == (4, 4)

    def test_from_grid_col_major(self):
        topo = ChipTopology.from_grid(3, 3, numbering="col-major")
        # col-major: Q01=(0,0), Q02=(1,0), Q03=(2,0), Q04=(0,1)...
        assert topo.pos_of("Q01") == (0, 0)
        assert topo.pos_of("Q02") == (1, 0)
        assert topo.pos_of("Q04") == (0, 1)

    def test_from_grid_start_offset(self):
        topo = ChipTopology.from_grid(2, 2, start=5)
        assert topo.qubit_names == ["Q05", "Q06", "Q07", "Q08"]

    def test_from_grid_bad_numbering(self):
        with pytest.raises(ValueError, match="numbering"):
            ChipTopology.from_grid(2, 2, numbering="snake")

    def test_custom_layout(self):
        topo = ChipTopology({
            (0, 0): "QA", (0, 1): "QB",
            (1, 0): None, (1, 1): "QD",  # gap at (1,0)
        })
        assert len(topo.qubit_names) == 3
        assert topo.pos_of("QA") == (0, 0)

    def test_empty_layout_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            ChipTopology({})

    def test_duplicate_name_raises(self):
        with pytest.raises(ValueError, match="Duplicate"):
            ChipTopology({(0, 0): "Q01", (0, 1): "Q01"})

    def test_add_coupler(self):
        topo = ChipTopology.from_grid(3, 3)
        topo.add_coupler("Q01", "Q02", coupling_MHz=15.0)
        topo.add_coupler("Q02", "Q05")
        assert "Q02" in topo.get_neighbors("Q01")
        assert "Q01" in topo.get_neighbors("Q02")
        assert len(topo.get_neighbors("Q02")) == 2
        assert len(topo.couplers) == 2

    def test_add_coupler_bad_qubit_raises(self):
        topo = ChipTopology.from_grid(2, 2)
        with pytest.raises(ValueError, match="'QX'"):
            topo.add_coupler("Q01", "QX")

    def test_iter_qubits_skips_none(self):
        topo = ChipTopology({(0, 0): "QA", (0, 1): None, (1, 0): "QB"})
        names = [n for _, n in topo.iter_qubits()]
        assert names == ["QA", "QB"]

    def test_properties(self):
        topo = ChipTopology.from_grid(3, 4)
        assert topo.rows == 3
        assert topo.cols == 4
        assert len(topo.qubit_names) == 12

    def test_to_from_dict_roundtrip(self):
        """to_dict() → from_dict() 完整 roundtrip 保留布局和耦合器。"""
        topo = ChipTopology.from_grid(3, 4, numbering="col-major", start=3)
        topo.add_coupler("Q03", "Q04")
        d = topo.to_dict()
        restored = ChipTopology.from_dict(d)
        assert restored.rows == topo.rows
        assert restored.cols == topo.cols
        assert restored.qubit_names == topo.qubit_names
        for name in topo.qubit_names:
            assert restored.pos_of(name) == topo.pos_of(name)
        assert len(restored.couplers) == 1

    def test_to_from_dict_with_gaps(self):
        """含 None 间隙的自定义布局 roundtrip 正确。"""
        topo = ChipTopology({
            (0, 0): "QA", (0, 1): None,
            (1, 0): "QB", (1, 1): "QC",
        })
        d = topo.to_dict()
        restored = ChipTopology.from_dict(d)
        assert restored.pos_of("QA") == (0, 0)
        assert restored.pos_of("QB") == (1, 0)
        assert restored.pos_of("QC") == (1, 1)
        assert "QA" in restored.qubit_names
        assert None not in restored.qubit_names
        positions = list(restored.iter_positions())
        assert (0, 1) in positions  # gap included

    def test_from_dict_old_format(self):
        """from_dict() 兼容旧格式 {rows, cols, numbering, start}。"""
        d = {"rows": 3, "cols": 2, "numbering": "row-major", "start": 5}
        topo = ChipTopology.from_dict(d)
        assert topo.rows == 3
        assert topo.cols == 2
        assert topo.pos_of("Q05") == (0, 0)
        assert topo.pos_of("Q06") == (0, 1)

    def test_iter_positions_includes_gaps(self):
        """iter_positions() 返回所有位置，包含 None 间隙。"""
        topo = ChipTopology({(0, 0): "QA", (1, 1): None, (2, 2): "QB"})
        positions = list(topo.iter_positions())
        assert len(positions) == 3
        assert (1, 1) in positions  # gap included


# =============================================================================
# ChipArtist
# =============================================================================


class TestChipArtist:
    @pytest.fixture
    def topo(self):
        return ChipTopology.from_grid(5, 5)

    def test_draw_returns_fig_ax(self, topo):
        artist = ChipArtist(topo)
        fig, ax = artist.draw()
        assert isinstance(fig, plt.Figure)
        assert isinstance(ax, plt.Axes)
        plt.close(fig)

    def test_draw_on_existing_ax(self, topo):
        fig, ax = plt.subplots()
        artist = ChipArtist(topo)
        fig2, ax2 = artist.draw(ax=ax)
        assert ax2 is ax
        plt.close(fig)

    def test_highlight_measured(self, topo):
        artist = ChipArtist(topo)
        artist.draw()
        artist.highlight_measured(["Q01", "Q07", "Q13", "Q16", "Q25"])
        fig = artist.get_figure()
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_colormap_param(self, topo):
        artist = ChipArtist(topo)
        artist.draw()
        rng = np.random.default_rng(0)
        values = {f"Q{i:02d}": rng.uniform(4.0, 5.0) for i in range(1, 26)}
        sm = artist.colormap_param("f01 (GHz)", values)
        assert sm is not None
        plt.close(artist.get_figure())

    def test_colormap_with_nan_values(self, topo):
        artist = ChipArtist(topo)
        artist.draw()
        values = {"Q01": 4.5, "Q07": np.nan, "Q13": 4.8}
        sm = artist.colormap_param("f01", values)
        assert sm is not None
        plt.close(artist.get_figure())

    def test_colormap_empty_returns_none(self, topo):
        artist = ChipArtist(topo)
        artist.draw()
        sm = artist.colormap_param("f01", {})
        assert sm is None
        plt.close(artist.get_figure())

    def test_annotate(self, topo):
        artist = ChipArtist(topo)
        artist.draw()
        artist.annotate(
            ["f01", "T1"],
            {"Q01": {"f01": 4.71, "T1": 45.2}, "Q07": {"f01": 4.52}},
        )
        plt.close(artist.get_figure())

    def test_coupler_lines(self, topo):
        topo.add_coupler("Q01", "Q02")
        topo.add_coupler("Q06", "Q11")
        artist = ChipArtist(topo)
        artist.draw()
        artist.add_coupler_lines()
        plt.close(artist.get_figure())

    def test_save_svg(self, topo):
        artist = ChipArtist(topo)
        artist.draw()
        artist.highlight_measured(["Q07", "Q13"])
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.svg")
        artist.save(path)
        assert os.path.getsize(path) > 100
        os.unlink(path)

    def test_get_figure_before_draw(self, topo):
        """get_figure() on undrawn artist triggers auto-draw."""
        artist = ChipArtist(topo)
        fig = artist.get_figure()
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_draw_with_gaps(self):
        """含 None 间隙的拓扑绘图不崩溃。"""
        topo = ChipTopology({(0, 0): "QA", (0, 1): None, (1, 0): "QB"})
        artist = ChipArtist(topo)
        fig, ax = artist.draw()
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_highlight_nonexistent_qubit_ignored(self):
        """highlight_measured() 含不存在的 qubit 名称时静默忽略。"""
        topo = ChipTopology.from_grid(3, 3)
        artist = ChipArtist(topo)
        artist.draw()
        artist.highlight_measured(["Q01", "Q99", "Q05"])
        plt.close(artist.get_figure())

    def test_reset_removes_overlays(self):
        """reset() 清除所有叠加层。"""
        topo = ChipTopology.from_grid(3, 3)
        artist = ChipArtist(topo)
        artist.draw()
        artist.highlight_measured(["Q01", "Q05"])
        assert len(artist._overlay_patches) > 0
        artist.reset()
        assert len(artist._overlay_patches) == 0
        plt.close(artist.get_figure())

    def test_save_with_custom_dpi(self):
        """save() 接受 dpi 和 bbox_inches 参数。"""
        topo = ChipTopology.from_grid(2, 2)
        artist = ChipArtist(topo)
        artist.draw()
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "test.png")
        artist.save(path, format="png", dpi=72, bbox_inches=None)
        assert os.path.getsize(path) > 50
        os.unlink(path)


# =============================================================================
# ChipState
# =============================================================================


class TestChipState:
    @pytest.fixture
    def topo(self):
        return ChipTopology.from_grid(5, 5)

    @pytest.fixture
    def state(self, topo):
        s = ChipState.new("chip-001", topo)
        s.add_T1("Q16", 45.2, 1.3, 4.71, "00747")
        s.add_T1("Q16", 38.1, 1.8, 4.85, "00789")
        s.add_f01_range("Q16", 4.2, 4.9, "00023")
        s.add_T2star("Q16", 12.3, 0.5, 4.71, "00750")
        s.add_drive_efficiency("Q16", 0.66, 30, 4.71, "00747")
        s.add_readout_fidelity("Q16", 0.95, 0.92, 0.935, 6.237, "00747")
        return s

    def test_new_state(self, topo):
        s = ChipState.new("test", topo)
        assert s.chip_id == "test"
        assert len(s.qubits) == 25

    def test_add_and_get(self, state):
        q = state.get_qubit("Q16")
        assert len(q.T1_us) == 2
        assert q.f01_GHz.min == 4.2
        assert len(q.T2star_us) == 1

    def test_get_latest(self, state):
        latest = state.get_latest("Q16", "T1")
        assert latest.value == 38.1  # 第二次添加的值
        assert latest.freq_GHz == 4.85

    def test_get_latest_f01(self, state):
        f01 = state.get_latest("Q16", "f01")
        assert isinstance(f01, F01Range)
        assert f01.min == 4.2

    def test_get_latest_empty(self, state):
        assert state.get_latest("Q01", "T1") is None

    def test_list_measured_qubits(self, state):
        measured = state.list_measured_qubits()
        assert measured == ["Q16"]

    def test_save_load_roundtrip(self, state, topo):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "chip_state.json")
        state.save(path)

        # Verify JSON content
        with open(path) as f:
            raw = json.load(f)
        assert raw["chip_id"] == "chip-001"
        assert "Q16" in raw["qubits"]

        # Load back
        s2 = ChipState.load(path)
        assert s2.chip_id == "chip-001"
        q2 = s2.get_qubit("Q16")
        assert len(q2.T1_us) == 2
        assert q2.T1_us[0].value == 45.2
        assert q2.T1_us[1].value == 38.1
        assert q2.f01_GHz.min == 4.2
        assert len(q2.drive_efficiency) == 1
        assert q2.drive_efficiency[0].product == pytest.approx(1.0 / 19.8)

    def test_save_empty_state(self, topo):
        s = ChipState.new("empty", topo)
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "empty_state.json")
        s.save(path)
        s2 = ChipState.load(path)
        assert s2.list_measured_qubits() == []

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            ChipState.load("/nonexistent/chip_state.json")

    def test_drive_entry_product(self):
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_drive_efficiency("Q01", 0.5, 40, 4.5, "00123")
        entry = s.get_latest("Q01", "drive_efficiency")
        assert entry.product == pytest.approx(0.05)

    def test_f01_range_overwrites(self, topo):
        s = ChipState.new("chip", topo)
        s.add_f01_range("Q01", 4.0, 4.5, "exp1")
        assert s.get_qubit("Q01").f01_GHz.min == 4.0
        # 第二次应覆盖
        s.add_f01_range("Q01", 4.1, 4.6, "exp2")
        assert s.get_qubit("Q01").f01_GHz.min == 4.1

    def test_save_load_col_major_roundtrip(self):
        """col-major 拓扑 save/load roundtrip 后位置保留。"""
        topo = ChipTopology.from_grid(3, 3, numbering="col-major")
        s = ChipState.new("chip-col", topo)
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "col_major_state.json")
        s.save(path)
        s2 = ChipState.load(path)
        assert s2.topology.pos_of("Q01") == (0, 0)
        assert s2.topology.pos_of("Q02") == (1, 0)  # col-major
        assert s2.topology.pos_of("Q04") == (0, 1)

    def test_save_load_custom_layout_roundtrip(self):
        """自定义布局（含 None 间隙）save/load roundtrip 后位置保留。"""
        topo = ChipTopology({(0, 0): "QA", (0, 1): None, (1, 0): "QB"})
        topo.add_coupler("QA", "QB")
        s = ChipState.new("chip-custom", topo)
        s.add_T1("QA", 30.0, 1.0, 4.5, "exp1")
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "custom_state.json")
        s.save(path)
        s2 = ChipState.load(path)
        assert s2.topology.pos_of("QA") == (0, 0)
        assert s2.topology.pos_of("QB") == (1, 0)
        assert s2.get_latest("QA", "T1").value == 30.0
        assert "QA" in s2.topology.qubit_names

    def test_save_load_preserves_couplers(self):
        """save/load roundtrip 保留耦合器信息。"""
        topo = ChipTopology.from_grid(3, 3)
        topo.add_coupler("Q01", "Q02", coupling_MHz=15.0)
        topo.add_coupler("Q02", "Q05")
        s = ChipState.new("chip-cpl", topo)
        s.add_T1("Q01", 40.0, 2.0, 5.0, "exp1")
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "coupler_state.json")
        s.save(path)
        s2 = ChipState.load(path)
        assert len(s2.topology.couplers) == 2
        assert "Q02" in s2.topology.get_neighbors("Q01")
        assert "Q05" in s2.topology.get_neighbors("Q02")

    def test_load_old_format_json(self):
        """load() 兼容旧格式 chip_state.json（{rows, cols, numbering, start}）。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "old_format_state.json")
        old_json = {
            "chip_id": "old-chip",
            "topology": {
                "rows": 3,
                "cols": 2,
                "numbering": "row-major",
                "start": 1,
            },
            "last_updated": "2026-06-01",
            "qubits": {},
        }
        with open(path, "w") as f:
            json.dump(old_json, f)
        s = ChipState.load(path)
        assert s.chip_id == "old-chip"
        assert s.topology.rows == 3
        assert s.topology.cols == 2


# =============================================================================
# Data Classes (unit tests)
# =============================================================================


class TestDataClasses:
    def test_parameter_entry_defaults(self):
        e = ParameterEntry(value=10.0, error=0.5, freq_GHz=4.5,
                           timestamp="2026-06-18", source_exp="001")
        assert e.value == 10.0
        assert e.error == 0.5

    def test_drive_entry_defaults(self):
        e = DriveEntry(pi_amp=0.5, pi_width_ns=40,
                       freq_GHz=4.5, timestamp="2026-06-18", source_exp="001")
        assert e.product == pytest.approx(1.0 / 20.0)  # 1/(0.5*40) = 0.05

    def test_readout_entry_defaults(self):
        e = ReadoutEntry(F0=0.95, F1=0.92, avg=0.935,
                         freq_GHz=6.2, timestamp="2026-06-18", source_exp="001")
        assert e.avg == 0.935

    def test_f01_range_defaults(self):
        r = F01Range(min=4.0, max=5.0, source_exp="001")
        assert r.min == 4.0

    def test_qubit_state_empty(self):
        qs = QubitState()
        assert qs.f01_GHz is None
        assert qs.T1_us == []
        assert qs.T2star_us == []
        assert qs.T2echo_us == []
        assert qs.coherence == []
        assert qs.drive_efficiency == []
        assert qs.readout_fidelity == []


# =============================================================================
# CoherenceGrouping
# =============================================================================


class TestCoherenceGrouping:
    """测试 coherence 按频率分组的行为。"""

    def test_add_T1_creates_group(self):
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_T1("Q01", 45.2, 1.3, freq_GHz=4.71, source_exp="00747")
        qs = s.get_qubit("Q01")
        assert len(qs.coherence) == 1
        g = qs.coherence[0]
        assert g.freq_GHz == 4.71
        assert g.T1_us is not None
        assert g.T1_us.value == 45.2
        assert g.T1_us.error == 1.3
        assert g.T1_us.source_exp == "00747"
        assert g.T2star_us is None
        assert g.T2echo_us is None

    def test_add_T2star_same_freq_merges(self):
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_T1("Q01", 45.2, 1.3, freq_GHz=4.71, source_exp="00747")
        s.add_T2star("Q01", 12.3, 0.5, freq_GHz=4.71, source_exp="00750")
        qs = s.get_qubit("Q01")
        assert len(qs.coherence) == 1
        g = qs.coherence[0]
        assert g.T1_us is not None
        assert g.T2star_us is not None
        assert g.T2star_us.value == 12.3
        assert g.T2star_us.source_exp == "00750"
        assert g.T2echo_us is None

    def test_add_T2echo_same_freq_merges(self):
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_T2star("Q01", 12.3, 0.5, freq_GHz=4.71, source_exp="00750")
        s.add_T2echo("Q01", 18.7, 0.7, freq_GHz=4.71, source_exp="00751")
        qs = s.get_qubit("Q01")
        assert len(qs.coherence) == 1
        g = qs.coherence[0]
        assert g.T2star_us is not None
        assert g.T2echo_us is not None

    def test_add_T1_same_freq_overwrites(self):
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_T1("Q01", 45.2, 1.3, freq_GHz=4.71, source_exp="00747")
        s.add_T1("Q01", 38.1, 1.8, freq_GHz=4.71, source_exp="00789")
        qs = s.get_qubit("Q01")
        assert len(qs.coherence) == 1
        assert qs.coherence[0].T1_us.value == 38.1
        assert qs.coherence[0].T1_us.error == 1.8
        assert qs.coherence[0].T1_us.source_exp == "00789"

    def test_add_T1_different_freq_creates_new_group(self):
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_T1("Q01", 45.2, 1.3, freq_GHz=4.71, source_exp="00747")
        s.add_T1("Q01", 38.1, 1.8, freq_GHz=4.85, source_exp="00789")
        qs = s.get_qubit("Q01")
        assert len(qs.coherence) == 2
        freqs = {g.freq_GHz for g in qs.coherence}
        assert freqs == {4.71, 4.85}

    def test_timestamp_updates_on_each_add(self):
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_T1("Q01", 45.2, 1.3, freq_GHz=4.71, source_exp="00747",
                 timestamp="2026-06-10")
        s.add_T2star("Q01", 12.3, 0.5, freq_GHz=4.71, source_exp="00750",
                     timestamp="2026-06-15")
        qs = s.get_qubit("Q01")
        assert qs.coherence[0].timestamp == "2026-06-15"

    def test_backward_compat_T1_us(self):
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_T1("Q01", 45.2, 1.3, freq_GHz=4.71, source_exp="00747")
        s.add_T1("Q01", 38.1, 1.8, freq_GHz=4.85, source_exp="00789")
        qs = s.get_qubit("Q01")
        t1_list = qs.T1_us
        assert len(t1_list) == 2
        assert t1_list[0].value == 45.2
        assert t1_list[0].freq_GHz == 4.71
        assert t1_list[1].value == 38.1
        assert t1_list[1].freq_GHz == 4.85

    def test_backward_compat_T2star_us(self):
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_T2star("Q01", 12.3, 0.5, freq_GHz=4.71, source_exp="00750")
        s.add_T2star("Q01", 15.0, 0.3, freq_GHz=4.85, source_exp="00800")
        qs = s.get_qubit("Q01")
        t2s_list = qs.T2star_us
        assert len(t2s_list) == 2
        assert t2s_list[0].value == 12.3
        assert t2s_list[1].value == 15.0

    def test_backward_compat_T2echo_us(self):
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_T2echo("Q01", 18.7, 0.7, freq_GHz=4.71, source_exp="00751")
        qs = s.get_qubit("Q01")
        t2e_list = qs.T2echo_us
        assert len(t2e_list) == 1
        assert t2e_list[0].value == 18.7

    def test_coherence_save_load_roundtrip(self):
        import tempfile
        import os
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_T1("Q01", 45.2, 1.3, freq_GHz=4.71, source_exp="00747")
        s.add_T2star("Q01", 12.3, 0.5, freq_GHz=4.71, source_exp="00750")
        s.add_T1("Q02", 38.1, 1.8, freq_GHz=4.85, source_exp="00789")
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "chip_state.json")
        s.save(path)
        s2 = ChipState.load(path)
        qs = s2.get_qubit("Q01")
        assert len(qs.coherence) == 1
        g = qs.coherence[0]
        assert g.freq_GHz == 4.71
        assert g.T1_us.value == 45.2
        assert g.T2star_us.value == 12.3
        assert g.T2echo_us is None
        qs2 = s2.get_qubit("Q02")
        assert len(qs2.coherence) == 1
        assert qs2.coherence[0].freq_GHz == 4.85

    def test_get_latest_T1_from_coherence(self):
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_T1("Q01", 45.2, 1.3, freq_GHz=4.71, source_exp="00747")
        s.add_T1("Q01", 38.1, 1.8, freq_GHz=4.85, source_exp="00789")
        latest = s.get_latest("Q01", "T1")
        assert latest is not None
        assert latest.value == 38.1  # 按时间戳，后添加的更新
        assert latest.freq_GHz == 4.85

    def test_list_measured_qubits_with_coherence(self):
        s = ChipState.new("test", ChipTopology.from_grid(2, 2))
        s.add_T1("Q01", 45.2, 1.3, freq_GHz=4.71, source_exp="00747")
        measured = s.list_measured_qubits()
        assert "Q01" in measured
        assert "Q02" not in measured


# =============================================================================
# fit_plot
# =============================================================================


class TestPlotFitResult:
    def test_basic_plot(self):
        x = np.linspace(0, 100, 30)
        y = 0.7 * np.exp(-x / 40) + 0.15
        r = fit(x, y, exp_decay, params_hint={"amplitude": 0.6, "tau": 35, "offset": 0.1})
        fig, ax, axr = plot_fit_result(x, y, r, title="T1 Fit")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_no_residuals(self):
        x = np.linspace(0, 100, 30)
        y = 0.7 * np.exp(-x / 40) + 0.15
        r = fit(x, y, exp_decay, params_hint={"amplitude": 0.6, "tau": 35, "offset": 0.1})
        fig, ax, axr = plot_fit_result(x, y, r, show_residuals=False)
        assert axr is None
        plt.close(fig)

    def test_with_nan_data(self):
        x = np.linspace(0, 100, 30)
        y = 0.7 * np.exp(-x / 40) + 0.15
        y[5] = np.nan
        r = fit(x, y, exp_decay, params_hint={"amplitude": 0.6, "tau": 35, "offset": 0.1})
        fig, ax, axr = plot_fit_result(x, y, r)
        # NaN 点应被跳过
        plt.close(fig)

    def test_param_loc_upper_right(self):
        """param_loc 参数控制文本框位置。"""
        x = np.linspace(0, 100, 30)
        y = 0.7 * np.exp(-x / 40) + 0.15
        r = fit(x, y, exp_decay, params_hint={"amplitude": 0.6, "tau": 35, "offset": 0.1})
        fig, ax, axr = plot_fit_result(x, y, r, param_loc="upper right")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_param_loc_invalid_falls_back(self):
        """未知 param_loc 回退到 "lower left"。"""
        x = np.linspace(0, 100, 30)
        y = 0.7 * np.exp(-x / 40) + 0.15
        r = fit(x, y, exp_decay, params_hint={"amplitude": 0.6, "tau": 35, "offset": 0.1})
        fig, ax, axr = plot_fit_result(x, y, r, param_loc="middle center")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestPlotSpectroscopy2d:
    def test_basic_2d_plot(self):
        """创建合成 2D 光谱数据并绘图。"""
        rows = []
        for zpa in np.linspace(-0.5, 0.5, 7):
            for freq in np.linspace(4.0, 5.5, 50):
                amp = 5.0 * (0.003**2) / ((freq - 4.7) ** 2 + 0.003**2) + 1.0
                rows.append([zpa, freq, amp, 0.0])
        data = np.array(rows)
        exp = Experiment(
            exp_id="test", title="spectro",
            timestamp=None,
            independent_vars=[
                ColumnMeta("zpa", "", ""),
                ColumnMeta("dr_freq", "GHz", ""),
            ],
            dependent_vars=[
                ColumnMeta("", "", "Q01 IQ Amp"),
                ColumnMeta("", "rad", "Q01 IQ phase"),
            ],
            data=data, params=None, settings={},
            source_dir=Path("/tmp"),
            csv_path=Path("/tmp/t.csv"), ini_path=Path("/tmp/t.ini"),
        )
        fig, ax, axs = plot_spectroscopy_2d(exp)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_with_slice(self):
        rows = []
        for zpa in np.linspace(-0.5, 0.5, 7):
            for freq in np.linspace(4.0, 5.5, 50):
                amp = 5.0 * (0.003**2) / ((freq - 4.7) ** 2 + 0.003**2) + 1.0
                rows.append([zpa, freq, amp, 0.0])
        data = np.array(rows)
        exp = Experiment(
            exp_id="test", title="spectro",
            timestamp=None,
            independent_vars=[
                ColumnMeta("zpa", "", ""),
                ColumnMeta("dr_freq", "GHz", ""),
            ],
            dependent_vars=[
                ColumnMeta("", "", "Q01 IQ Amp"),
                ColumnMeta("", "rad", "Q01 IQ phase"),
            ],
            data=data, params=None, settings={},
            source_dir=Path("/tmp"),
            csv_path=Path("/tmp/t.csv"), ini_path=Path("/tmp/t.ini"),
        )
        fig, ax, axs = plot_spectroscopy_2d(exp, z_slice=0.0)
        assert axs is not None
        plt.close(fig)

    def test_1d_data_raises(self):
        exp = Experiment(
            exp_id="test", title="T1",
            timestamp=None,
            independent_vars=[ColumnMeta("delay", "us", "")],
            dependent_vars=[ColumnMeta("", "", "P1")],
            data=np.zeros((10, 2)), params=None, settings={},
            source_dir=Path("/tmp"),
            csv_path=Path("/tmp/t.csv"), ini_path=Path("/tmp/t.ini"),
        )
        with pytest.raises(ValueError, match="2D data"):
            plot_spectroscopy_2d(exp)
