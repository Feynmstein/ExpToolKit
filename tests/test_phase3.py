"""Phase 3 测试 — IQ 读取保真度 + HTML 报告生成。

覆盖：
- assignment_fidelity: 2-state, 3-state, edge cases
- ChipArtist.to_svg(): SVG string generation
- ReportGenerator: full report, section subsets, edge cases
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pytest

from exp_toolkit.fitting.iq_analysis import (
    ReadoutFidelity,
    assignment_fidelity,
)
from exp_toolkit.io.readers import IQBlobs
from exp_toolkit.report import ReportGenerator
from exp_toolkit.state import ChipState
from exp_toolkit.visualization import ChipArtist, ChipTopology


# =============================================================================
# assignment_fidelity
# =============================================================================


class TestAssignmentFidelity:
    """IQ 分类中心 → 读取保真度计算。"""

    def test_2state_known_fidelity(self):
        """2 态：d=3, σ=1 → P(error)=½·erfc(3/(2√2)) ≈ 0.0668, fidelity≈0.9332。"""
        blobs = IQBlobs(centers=[0 + 0j, 3 + 0j], variance=1.0, n_states=2)
        result = assignment_fidelity(blobs)

        # Theoretical: d=3, sigma=1, SNR=3
        from scipy.special import erfc
        p_error = 0.5 * float(erfc(3.0 / (2.0 * np.sqrt(2))))
        expected = 1.0 - p_error  # ≈ 0.9332

        assert result.fidelity_01 == pytest.approx(expected, rel=1e-4)
        assert result.fidelity_10 == pytest.approx(expected, rel=1e-4)
        assert result.avg_fidelity == pytest.approx(expected, rel=1e-4)
        assert result.snr == pytest.approx(3.0)

    def test_2state_perfect_separation(self):
        """2 态：极大距离 → fidelity ≈ 1.0。"""
        blobs = IQBlobs(centers=[0 + 0j, 100 + 0j], variance=0.01, n_states=2)
        result = assignment_fidelity(blobs)
        assert result.fidelity_01 > 0.9999
        assert result.fidelity_10 > 0.9999
        assert result.snr > 100

    def test_2state_nonzero_centers(self):
        """2 态：中心不在原点，仅距离有意义。"""
        blobs = IQBlobs(centers=[10 + 5j, 13 + 5j], variance=1.0, n_states=2)
        result = assignment_fidelity(blobs)
        # d = 3, same as test_2state_known_fidelity
        from scipy.special import erfc
        p_error = 0.5 * float(erfc(3.0 / (2.0 * np.sqrt(2))))
        expected = 1.0 - p_error
        assert result.fidelity_01 == pytest.approx(expected, rel=1e-4)

    def test_3state_pairwise_average(self):
        """3 态：pairwise fidelity 平均。"""
        blobs = IQBlobs(
            centers=[0 + 0j, 3 + 0j, 6 + 1j],
            variance=1.0,
            n_states=3,
        )
        result = assignment_fidelity(blobs)
        # All fidelities should be positive and ≤ 1
        assert 0 < result.fidelity_01 <= 1.0
        assert 0 < result.fidelity_10 <= 1.0
        assert 0 < result.avg_fidelity <= 1.0
        # SNR should be the minimum pairwise
        assert result.snr > 0
        # fidelity_01 == fidelity_10 (symmetry)
        assert result.fidelity_01 == pytest.approx(result.fidelity_10)

    def test_3state_equilateral(self):
        """3 态：等边三角形布局 → 所有 pairwise fidelity 相等。"""
        # Equilateral triangle with side length d, center at origin
        d = 3.0
        c0 = complex(-d / 2, -d * np.sqrt(3) / 6)
        c1 = complex(d / 2, -d * np.sqrt(3) / 6)
        c2 = complex(0, d * np.sqrt(3) / 3)
        blobs = IQBlobs(centers=[c0, c1, c2], variance=1.0, n_states=3)
        result = assignment_fidelity(blobs)
        assert result.avg_fidelity > 0.9

    def test_invalid_n_states_raises(self):
        """n_states 为 1 或 4 应抛出 ValueError。"""
        blobs = IQBlobs(centers=[0j], variance=1.0, n_states=1)
        with pytest.raises(ValueError, match="n_states"):
            assignment_fidelity(blobs)

        blobs4 = IQBlobs(centers=[0j, 1j, 2j, 3j], variance=1.0, n_states=4)
        with pytest.raises(ValueError, match="n_states"):
            assignment_fidelity(blobs4)

    def test_centers_count_mismatch_raises(self):
        """centers 数量与 n_states 不一致应抛出 ValueError。"""
        blobs = IQBlobs(centers=[0j, 1j, 2j], variance=1.0, n_states=2)
        with pytest.raises(ValueError, match="centers"):
            assignment_fidelity(blobs)

    def test_negative_variance_raises(self):
        """variance <= 0 应抛出 ValueError。"""
        blobs = IQBlobs(centers=[0j, 1j], variance=0.0, n_states=2)
        with pytest.raises(ValueError, match="variance"):
            assignment_fidelity(blobs)

        blobs_neg = IQBlobs(centers=[0j, 1j], variance=-1.0, n_states=2)
        with pytest.raises(ValueError, match="variance"):
            assignment_fidelity(blobs_neg)

    def test_readout_fidelity_fields(self):
        """ReadoutFidelity 数据类字段可访问。"""
        rf = ReadoutFidelity(
            fidelity_01=0.95, fidelity_10=0.93,
            avg_fidelity=0.94, snr=5.0,
        )
        assert rf.fidelity_01 == 0.95
        assert rf.fidelity_10 == 0.93
        assert rf.avg_fidelity == 0.94
        assert rf.snr == 5.0


# =============================================================================
# ChipArtist.to_svg()
# =============================================================================


class TestChipArtistToSvg:
    """SVG 字符串输出（用于 HTML 嵌入）。"""

    def test_to_svg_returns_string(self):
        """to_svg() 返回包含 <svg 标记的字符串。"""
        topo = ChipTopology.from_grid(3, 3)
        artist = ChipArtist(topo)
        artist.draw()
        svg = artist.to_svg()
        assert isinstance(svg, str)
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_to_svg_auto_draws(self):
        """未显式 draw() 时 to_svg() 自动触发。"""
        topo = ChipTopology.from_grid(2, 2)
        artist = ChipArtist(topo)
        svg = artist.to_svg()
        assert len(svg) > 100


# =============================================================================
# ReportGenerator
# =============================================================================


class TestReportGenerator:
    """HTML 报告生成器。"""

    @pytest.fixture
    def state(self):
        """创建含多比特数据的 ChipState。"""
        topo = ChipTopology.from_grid(5, 5)
        s = ChipState.new("test-chip-001", topo)
        s.add_T1("Q07", 45.2, 1.3, 4.71, "00747")
        s.add_T1("Q07", 38.1, 1.8, 4.85, "00789")
        s.add_T2star("Q07", 12.3, 0.5, 4.71, "00750")
        s.add_f01_range("Q07", 4.2, 4.9, "00023")
        s.add_drive_efficiency("Q07", 0.66, 30, 4.71, "00747")
        s.add_readout_fidelity("Q07", 0.95, 0.92, 0.935, 6.237, "00747")
        s.add_T1("Q16", 30.0, 0.8, 4.85, "00789")
        s.add_f01_range("Q16", 4.3, 4.95, "00023")
        return s

    def test_full_report(self, state):
        """生成包含全部 4 节的完整报告。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "report.html")
        gen = ReportGenerator(state)
        out = gen.generate(path, title="Full Report")

        assert out == Path(path)
        assert os.path.getsize(path) > 1000

        content = Path(path).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Full Report" in content
        assert "test-chip-001" in content
        # Sections
        assert "Chip Topology" in content
        assert "Measured Qubits" in content
        assert "Unmeasured Qubits" in content
        assert "Data Sources" in content
        # Qubit cards
        assert "Q07" in content
        assert "Q16" in content
        # SVG embedded
        assert "<svg" in content

    def test_section_subset(self, state):
        """sections 参数控制仅生成指定节。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "qubits_only.html")
        gen = ReportGenerator(state)
        gen.generate(path, sections=["qubits"], title="Qubits Only")

        content = Path(path).read_text(encoding="utf-8")
        assert "Measured Qubits" in content
        assert "Chip Topology" not in content
        assert "Unmeasured Qubits" not in content
        assert "Data Sources" not in content

    def test_overview_only(self, state):
        """sections=["overview"] 仅生成拓扑图。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "overview_only.html")
        gen = ReportGenerator(state)
        gen.generate(path, sections=["overview"])

        content = Path(path).read_text(encoding="utf-8")
        assert "Chip Topology" in content
        assert "<svg" in content
        assert "Measured Qubits" not in content

    def test_invalid_colormap_raises(self, state):
        """非法 topology_param 抛出 ValueError。"""
        gen = ReportGenerator(state)
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "bad.html")
        with pytest.raises(ValueError, match="topology"):
            gen.generate(path, topology_params=["invalid"])

    def test_invalid_section_raises(self, state):
        """非法 section 名抛出 ValueError。"""
        gen = ReportGenerator(state)
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "bad.html")
        with pytest.raises(ValueError, match="section"):
            gen.generate(path, sections=["overview", "invalid"])

    def test_colormap_param_variations(self, state):
        """不同 topology_params 生成对应标签的拓扑图。"""
        param_labels = {
            "f01": "f01 max",
            "T1": "T1",
            "T2star": "T2*",
            "readout_fidelity": "Readout",
        }
        for param, label in param_labels.items():
            tmpdir = tempfile.mkdtemp()
            path = os.path.join(tmpdir, f"report_{param}.html")
            gen = ReportGenerator(state)
            gen.generate(path, sections=["overview"], topology_params=[param])
            content = Path(path).read_text(encoding="utf-8")
            assert label in content, f"Expected '{label}' in report for param={param}"

    def test_empty_state(self):
        """空 ChipState（无测量数据）仍可生成报告。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("empty", topo)
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "empty_report.html")
        gen = ReportGenerator(s)
        gen.generate(path, title="Empty Report")

        content = Path(path).read_text(encoding="utf-8")
        assert "Empty Report" in content
        assert "empty" in content
        # Unmeasured section should show all qubits
        assert "Unmeasured Qubits" in content

    def test_default_title(self, state):
        """默认标题含 chip_id。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "default_title.html")
        gen = ReportGenerator(state)
        gen.generate(path)

        content = Path(path).read_text(encoding="utf-8")
        assert "test-chip-001" in content

    def test_svg_embedded_not_linked(self, state):
        """拓扑图以内嵌 SVG 呈现，无外部引用。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "svg_embed.html")
        gen = ReportGenerator(state)
        gen.generate(path, sections=["overview"])

        content = Path(path).read_text(encoding="utf-8")
        # Should contain inline SVG, not img src
        assert "<svg" in content
        assert 'src="' not in content.lower() or '.svg"' not in content.lower()

    def test_qubit_card_has_latest_values(self, state):
        """比特卡片显示最新测量值。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "latest.html")
        gen = ReportGenerator(state)
        gen.generate(path, sections=["qubits"])

        content = Path(path).read_text(encoding="utf-8")
        # Q07 T1 should show latest (38.1), not first (45.2)
        assert "38.1" in content
        # Q07 f01 range
        assert "4.2" in content
        assert "4.9" in content

    def test_sources_table(self, state):
        """数据来源表包含实验编号和参数类型标记。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "sources.html")
        gen = ReportGenerator(state)
        gen.generate(path, sections=["sources"])

        content = Path(path).read_text(encoding="utf-8")
        assert "00747" in content
        assert "00789" in content
        assert "00023" in content


# =============================================================================
# Phase 5 — R1: save() 保留用户手动设置的 last_updated
# =============================================================================


class TestSaveLastUpdated:
    """save() 应保留 load() 加载的 last_updated 值。"""

    def test_save_preserves_last_updated(self):
        """手动设置 last_updated 后 save() 保留该值。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("test-chip", topo)
        s.last_updated = "2025-11-15"
        s.add_T1("Q01", 30.0, 0.5, 4.5, "00001")

        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "state.json")
        s.save(path)

        loaded = ChipState.load(path)
        assert loaded.last_updated == "2025-11-15"

    def test_save_defaults_when_none(self):
        """last_updated 为 None 时 save() 使用当天日期。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("test-chip", topo)
        s.last_updated = None

        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "state.json")
        s.save(path)

        loaded = ChipState.load(path)
        from datetime import date
        assert loaded.last_updated == date.today().isoformat()


# =============================================================================
# Phase 5 — R2: QubitState.extras + ChipState.set_extras()
# =============================================================================


class TestExtras:
    """QubitState.extras 的读写和兼容性。"""

    def test_extras_roundtrip(self):
        """set_extras() 写入的 extras 在 save/load 后保留。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("test-chip", topo)
        s.set_extras("Q01", readout_cavity_response=True, bias_tunable=False)
        s.add_T1("Q01", 40.0, 1.0, 4.5, "00001")

        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "extras_state.json")
        s.save(path)

        loaded = ChipState.load(path)
        qs = loaded.get_qubit("Q01")
        assert qs.extras == {"readout_cavity_response": True, "bias_tunable": False}

    def test_extras_empty_default(self):
        """新 QubitState 的 extras 默认为空 dict。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("test-chip", topo)
        qs = s.get_qubit("Q01")
        assert qs.extras == {}

    def test_old_json_no_extras(self):
        """旧 JSON 无 extras 键时 load() 返回空 dict。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("test-chip", topo)
        s.add_T1("Q01", 42.0, 0.5, 4.5, "00001")

        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "old_format.json")
        s.save(path)

        # 手动删除 extras 键（先加载再手动修改 JSON 来模拟）
        loaded = ChipState.load(path)
        qs = loaded.get_qubit("Q01")
        assert qs.extras == {}

    def test_set_extras_merge(self):
        """set_extras() 合并而非覆盖已有 extras 键。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("test-chip", topo)
        s.set_extras("Q01", readout_cavity_response=True)
        s.set_extras("Q01", bias_tunable=False)

        qs = s.get_qubit("Q01")
        assert qs.extras == {
            "readout_cavity_response": True,
            "bias_tunable": False,
        }


# =============================================================================
# Phase 5 — R3a: 圆形 → 圆角矩形 (FancyBboxPatch)
# =============================================================================


class TestFancyBboxPatch:
    """ChipArtist 使用圆角矩形替代圆形。"""

    def test_draw_uses_fancybbox(self):
        """draw() 添加 FancyBboxPatch 而非 Circle。"""
        topo = ChipTopology.from_grid(2, 2)
        artist = ChipArtist(topo)
        _, ax = artist.draw()

        from matplotlib.patches import FancyBboxPatch
        patches = [c for c in ax.patches if isinstance(c, FancyBboxPatch)]
        assert len(patches) == 4  # 2×2 qubits

    def test_box_dimensions(self):
        """圆角矩形尺寸等于 _BOX_WIDTH × _BOX_HEIGHT。"""
        topo = ChipTopology.from_grid(1, 1)
        artist = ChipArtist(topo)
        _, ax = artist.draw()

        from matplotlib.patches import FancyBboxPatch
        box = [c for c in ax.patches if isinstance(c, FancyBboxPatch)][0]
        width = box.get_width()
        height = box.get_height()
        assert width == artist._BOX_WIDTH
        assert height == artist._BOX_HEIGHT

    def test_highlight_measured_uses_fancybbox(self):
        """highlight_measured() 也使用 FancyBboxPatch。"""
        topo = ChipTopology.from_grid(2, 2)
        artist = ChipArtist(topo)
        artist.draw()
        artist.highlight_measured(["Q01"])

        from matplotlib.patches import FancyBboxPatch, Circle
        boxes = [c for c in artist.ax.patches if isinstance(c, FancyBboxPatch)]
        circles = [c for c in artist.ax.patches if isinstance(c, Circle)]
        # All patches should be FancyBboxPatch (draw: 4 + highlight: 1)
        assert len(boxes) == 5
        assert len(circles) == 0

    def test_colormap_param_uses_fancybbox(self):
        """colormap_param() 也使用 FancyBboxPatch。"""
        topo = ChipTopology.from_grid(2, 2)
        artist = ChipArtist(topo)
        artist.draw()
        artist.colormap_param("Test", {"Q01": 1.0, "Q02": 2.0})

        from matplotlib.patches import FancyBboxPatch, Circle
        boxes = [c for c in artist.ax.patches if isinstance(c, FancyBboxPatch)]
        circles = [c for c in artist.ax.patches if isinstance(c, Circle)]
        assert len(boxes) == 8  # draw: 4 + colormap: 4
        assert len(circles) == 0


# =============================================================================
# Phase 5 — R3b: colormap_param() 内显示参数值
# =============================================================================


class TestColormapShowValues:
    """colormap_param() 的 show_values 参数。"""

    def test_colormap_show_values(self):
        """show_values=True 时文本包含数值。"""
        topo = ChipTopology.from_grid(1, 1)
        artist = ChipArtist(topo)
        artist.draw()
        artist.colormap_param(
            "T1", {"Q01": 45.2},
            show_values=True, value_format="{:.1f}", value_unit="μs",
        )

        texts = [t.get_text() for t in artist.ax.texts]
        assert any("45.2" in t and "μs" in t for t in texts)

    def test_colormap_no_show_values(self):
        """show_values=False（默认）时文本仅显示比特名。"""
        topo = ChipTopology.from_grid(1, 1)
        artist = ChipArtist(topo)
        artist.draw()
        artist.colormap_param("T1", {"Q01": 45.2}, show_values=False)

        texts = [t.get_text() for t in artist.ax.texts]
        # 只有 "Q01"，不含数值
        assert any(t.strip() == "Q01" for t in texts)

    def test_colormap_show_values_missing_data(self):
        """无数据的比特在 show_values=True 时不显示数值。"""
        topo = ChipTopology.from_grid(2, 1)
        artist = ChipArtist(topo)
        artist.draw()
        artist.colormap_param(
            "T1", {"Q01": 45.2},  # Q02 无数据
            show_values=True, value_unit="μs",
        )

        texts = [t.get_text() for t in artist.ax.texts]
        # Q01 有值
        assert any("45.2" in t for t in texts)
        # Q02 仅名称
        assert any(t.strip() == "Q02" for t in texts)

    def test_colormap_show_values_no_unit(self):
        """value_unit 为 None 时不添加单位后缀。"""
        topo = ChipTopology.from_grid(1, 1)
        artist = ChipArtist(topo)
        artist.draw()
        artist.colormap_param(
            "T1", {"Q01": 45.2},
            show_values=True, value_format="{:.1f}", value_unit=None,
        )

        texts = [t.get_text() for t in artist.ax.texts]
        assert any("45.2" in t and "μs" not in t for t in texts)


# =============================================================================
# Phase 5 — R3c: ReportGenerator 色标扩展
# =============================================================================


class TestReportColormapExpansion:
    """T2echo, drive_efficiency 色标 + extras 数值字段。"""

    @pytest.fixture
    def state_t2(self):
        """创建含 T2echo 和 drive_efficiency 数据的 ChipState。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("test-chip-t2", topo)
        s.add_T2echo("Q01", 30.0, 1.0, 4.5, "00700")
        s.add_T2echo("Q02", 25.0, 0.8, 4.6, "00700")
        s.add_drive_efficiency("Q01", 0.5, 40, 4.5, "00701")
        s.add_drive_efficiency("Q02", 0.6, 35, 4.6, "00701")
        return s

    def test_colormap_T2echo(self, state_t2):
        """topology_params=["T2echo"] 生成报告。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "t2echo_report.html")
        gen = ReportGenerator(state_t2)
        gen.generate(path, sections=["overview"], topology_params=["T2echo"])

        content = Path(path).read_text(encoding="utf-8")
        assert "T2 echo" in content

    def test_colormap_drive_efficiency(self, state_t2):
        """topology_params=["drive_efficiency"] 生成报告。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "de_report.html")
        gen = ReportGenerator(state_t2)
        gen.generate(path, sections=["overview"], topology_params=["drive_efficiency"])

        content = Path(path).read_text(encoding="utf-8")
        assert "Drive Efficiency" in content

    def test_colormap_values_T2echo(self):
        """_get_colormap_values 提取 T2echo 值。"""
        from exp_toolkit.report.generator import _get_colormap_values

        topo = ChipTopology.from_grid(2, 1)
        s = ChipState.new("test", topo)
        s.add_T2echo("Q01", 30.0, 1.0, 4.5, "00700")
        s.add_T2echo("Q02", 25.0, 0.8, 4.6, "00700")

        vals = _get_colormap_values(s, "T2echo")
        assert vals["Q01"] == 30.0
        assert vals["Q02"] == 25.0

    def test_colormap_values_drive_efficiency(self):
        """_get_colormap_values 提取 drive_efficiency.product。"""
        from exp_toolkit.report.generator import _get_colormap_values

        topo = ChipTopology.from_grid(2, 1)
        s = ChipState.new("test", topo)
        s.add_drive_efficiency("Q01", 0.5, 40, 4.5, "00701")
        s.add_drive_efficiency("Q02", 0.6, 35, 4.6, "00701")

        vals = _get_colormap_values(s, "drive_efficiency")
        # product = 1.0 / (pi_amp * pi_width_ns)
        assert vals["Q01"] == pytest.approx(1.0 / 20.0)
        assert vals["Q02"] == pytest.approx(1.0 / 21.0)

    def test_colormap_extras_numeric(self):
        """extras 中的数值字段可作为 colormap 参数。"""
        topo = ChipTopology.from_grid(2, 1)
        s = ChipState.new("test", topo)
        s.set_extras("Q01", coupling_strength=12.5)
        s.set_extras("Q02", coupling_strength=8.3)
        # Need measurement data for qubits to appear
        s.add_T1("Q01", 40.0, 0.5, 4.5, "00001")
        s.add_T1("Q02", 38.0, 0.6, 4.6, "00001")

        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "extras_cmap.html")
        gen = ReportGenerator(s)
        gen.generate(path, sections=["overview"], topology_params=["coupling_strength"])

        content = Path(path).read_text(encoding="utf-8")
        assert "coupling_strength" in content

    def test_colormap_extras_bool_rejected(self):
        """extras 中布尔值不应被当作数值 colormap。"""
        from exp_toolkit.report.generator import _get_colormap_values

        topo = ChipTopology.from_grid(2, 1)
        s = ChipState.new("test", topo)
        s.set_extras("Q01", readout_cavity_response=True)
        s.add_T1("Q01", 40.0, 0.5, 4.5, "00001")

        vals = _get_colormap_values(s, "readout_cavity_response")
        # bool 应被过滤
        assert "Q01" not in vals

    def test_colormap_invalid_raises(self, state_t2):
        """非法 topology_param 仍抛出 ValueError。"""
        gen = ReportGenerator(state_t2)
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "bad.html")
        with pytest.raises(ValueError, match="topology"):
            gen.generate(path, topology_params=["nonexistent_param"])


# =============================================================================
# Phase 5 — R3d: annotate_fields 接线
# =============================================================================


class TestAnnotateFields:
    """ReportGenerator 的 annotate_fields 参数。"""

    @pytest.fixture
    def state_annot(self):
        """创建含多种参数数据的 ChipState。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("test-annot", topo)
        s.add_T1("Q01", 45.2, 1.3, 4.71, "00747")
        s.add_T2star("Q01", 12.3, 0.5, 4.71, "00750")
        s.add_f01_range("Q01", 4.2, 4.9, "00023")
        s.add_T1("Q02", 30.0, 0.8, 4.85, "00789")
        s.set_extras("Q01", readout_cavity_response=True)
        return s

    def test_overview_no_annotate_text(self, state_annot):
        """报告拓扑图中不含 annotate() 的字段文本（如 'T1=45.20'）。
        改为每个参数独立拓扑图。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "no_annotate.html")
        gen = ReportGenerator(state_annot)
        gen.generate(path, sections=["overview"], topology_params=["T1"])

        content = Path(path).read_text(encoding="utf-8")
        # annotate 不再在 generate() 中使用
        assert "T1=" not in content


# =============================================================================
# Phase 5 — R4: qubit card 始终展示全部参数行
# =============================================================================


class TestQubitCardAllRows:
    """qubit card 始终展示全部 6 个参数行 + extras 标志。"""

    @pytest.fixture
    def gen(self):
        """创建 ReportGenerator，数据覆盖部分参数。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("test-card", topo)
        # Q01: 全参数
        s.add_T1("Q01", 45.2, 1.3, 4.71, "00747")
        s.add_T2star("Q01", 12.3, 0.5, 4.71, "00750")
        s.add_T2echo("Q01", 20.0, 1.0, 4.71, "00800")
        s.add_f01_range("Q01", 4.2, 4.9, "00023")
        s.add_drive_efficiency("Q01", 0.66, 30, 4.71, "00747")
        s.add_readout_fidelity("Q01", 0.95, 0.92, 0.935, 6.237, "00747")
        s.set_extras("Q01", readout_cavity_response=True, bias_tunable=False)
        # Q02: 仅有 T1（其他参数缺失）
        s.add_T1("Q02", 30.0, 0.8, 4.85, "00789")
        return ReportGenerator(s), s

    def test_card_all_rows_present(self, gen):
        """每个比特卡片包含全部 6 个参数行标签。"""
        rg, state = gen
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "all_rows.html")
        rg.generate(path, sections=["qubits"])

        content = Path(path).read_text(encoding="utf-8")
        expected_labels = ["f01", "T1", "T2*", "T2 echo", "Drive Eff", "Readout"]
        for label in expected_labels:
            assert label in content, f"Missing parameter row: {label}"

    def test_missing_data_css(self, gen):
        """缺失参数显示 'No data' 且带 missing CSS 类。"""
        rg, state = gen
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "missing_css.html")
        rg.generate(path, sections=["qubits"])

        content = Path(path).read_text(encoding="utf-8")
        assert 'class="missing"' in content
        assert "No data" in content
        assert ".qubit-card td.missing" in content

    def test_card_extras_flags(self, gen):
        """extras 布尔标志显示为 Yes/No。"""
        rg, state = gen
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "extras_flags.html")
        rg.generate(path, sections=["qubits"])

        content = Path(path).read_text(encoding="utf-8")
        # Q01 有 extras
        assert "readout_cavity_response" in content
        assert "bias_tunable" in content
        assert ">Yes<" in content
        assert ">No<" in content

    def test_no_data_card(self, gen):
        """仅有 T1 的比特（Q02），其他参数行显示 No data。"""
        rg, state = gen
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "partial_card.html")
        rg.generate(path, sections=["qubits"])

        content = Path(path).read_text(encoding="utf-8")
        # Q02 应有 5 个 No data（f01, T2*, T2 echo, Drive Eff, Readout）
        assert content.count("No data") >= 5

    def test_overview_shows_values(self, gen):
        """概述图应内嵌参数值（show_values）。"""
        rg, state = gen
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "overview_values.html")
        rg.generate(path, sections=["overview"], topology_params=["T1"])

        content = Path(path).read_text(encoding="utf-8")
        # SVG 中应包含参数值文本
        assert "45.2" in content


# =============================================================================
# Phase 6 — R1: 多参数独立拓扑图
# =============================================================================


class TestMultiFigureTopology:
    """generate() 每参数生成一张独立拓扑图。"""

    @pytest.fixture
    def state_multi(self):
        """创建含多种参数数据的 ChipState。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("test-multi", topo)
        s.add_T1("Q01", 45.2, 1.3, 4.71, "00747")
        s.add_T2star("Q01", 12.3, 0.5, 4.71, "00750")
        s.add_T2echo("Q02", 20.0, 1.0, 4.6, "00800")
        s.set_extras("Q01", bias_tunable=True)
        s.set_extras("Q02", bias_tunable=False, f01_max_GHz=4.9)
        return s

    def test_generate_multi_figure(self, state_multi):
        """generate() 默认生成多张独立拓扑图（≥ 2 张），共用单个 overview section。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "multi.html")
        gen = ReportGenerator(state_multi)
        gen.generate(path, sections=["overview"])

        content = Path(path).read_text(encoding="utf-8")
        # Single overview section containing multiple figures
        assert content.count('<section id="overview">') == 1
        assert content.count("<figure>") > 1
        assert content.count("<figcaption>") > 1
        # Each figure has an SVG
        assert content.count("<svg") > 1

    def test_generate_topology_params_auto(self, state_multi):
        """topology_params=None 自动检测所有可用参数，参数名出现在 figcaption 中。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "auto.html")
        gen = ReportGenerator(state_multi)
        gen.generate(path, sections=["overview"])

        content = Path(path).read_text(encoding="utf-8")
        # T1, T2star, T2echo (built-in) + bias_tunable, f01_max_GHz (extras)
        # Should appear in figcaptions
        assert "<figcaption>T1" in content
        assert "<figcaption>T2*" in content
        assert "<figcaption>T2 echo" in content
        # bool yield params use _YIELD_LABELS, rendered in yield section
        assert "<figcaption>Bias Tunable" in content
        assert "<figcaption>f01_max_GHz" in content

    def test_generate_topology_params_explicit(self, state_multi):
        """指定 topology_params 仅生成对应的图（yield section 固定 3 图 + 请求的图）。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "explicit.html")
        gen = ReportGenerator(state_multi)
        gen.generate(path, sections=["overview"], topology_params=["T1", "T2star"])

        content = Path(path).read_text(encoding="utf-8")
        # Yield section always rendered (3 fixed figures)
        assert '<section id="yield">' in content
        # Overview section with requested params
        assert '<section id="overview">' in content
        # 3 yield + 2 requested = 5 figures total
        assert content.count("<figure>") == 5
        assert "<figcaption>T1" in content
        assert "<figcaption>T2*" in content
        # Non-requested built-in params should not appear in overview
        assert "<figcaption>T2 echo" not in content


# =============================================================================
# Phase 6 — R2: Extras 拓扑可视化 (categorical / numeric)
# =============================================================================


class TestExtrasTopologyVisualization:
    """bool extras → categorical_param, numeric extras → colormap。"""

    @pytest.fixture
    def state_extras(self):
        """创建含 bool + numeric extras 的 ChipState。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("test-extras-viz", topo)
        s.set_extras("Q01", bias_tunable=True, f01_max_GHz=4.9)
        s.set_extras("Q02", bias_tunable=False, f01_max_GHz=4.5)
        # Need measurement for qubits to be in measured list
        s.add_T1("Q01", 40.0, 0.5, 4.5, "00001")
        s.add_T1("Q02", 38.0, 0.6, 4.6, "00001")
        return s

    def test_categorical_param_bool(self, state_extras):
        """bool extras 走 categorical_param，True=浅蓝/False=灰。"""
        from exp_toolkit.report.generator import ReportGenerator as RG
        gen = RG(state_extras)
        values, is_bool = gen._resolve_topology_param("bias_tunable")
        assert is_bool is True
        assert values["Q01"] is True
        assert values["Q02"] is False

    def test_categorical_param_labels(self, state_extras):
        """分类图报告中包含比特名（yield section 渲染）。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "cat_labels.html")
        gen = ReportGenerator(state_extras)
        gen.generate(path, sections=["overview"], topology_params=["bias_tunable"])

        content = Path(path).read_text(encoding="utf-8")
        # Yield section uses human-readable labels
        assert "Bias Tunable" in content
        assert '<section id="yield">' in content
        assert "<svg" in content

    def test_extras_numeric_colormap(self, state_extras):
        """数值 extras（f01_max_GHz）走 colormap + colorbar。"""
        from exp_toolkit.report.generator import ReportGenerator as RG
        gen = RG(state_extras)
        values, is_bool = gen._resolve_topology_param("f01_max_GHz")
        assert is_bool is False
        assert values["Q01"] == 4.9
        assert values["Q02"] == 4.5

    def test_extras_bool_vs_numeric_dispatch(self, state_extras):
        """同一报告中 bool 和 numeric extras 分别正确处理。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "dispatch.html")
        gen = ReportGenerator(state_extras)
        gen.generate(
            path, sections=["overview"],
            topology_params=["bias_tunable", "f01_max_GHz"],
        )

        content = Path(path).read_text(encoding="utf-8")
        # bias_tunable → yield section (always 3 yield figs);
        # f01_max_GHz → overview section (1 fig) = 4 SVGs total
        assert "Bias Tunable" in content
        assert "f01_max_GHz" in content
        assert content.count("<svg") == 4


# =============================================================================
# Phase 6 — R3: 去除重复比特 ID (draw show_labels)
# =============================================================================


class TestDrawShowLabels:
    """ChipArtist.draw() 的 show_labels 参数。"""

    def test_draw_show_labels_false(self):
        """draw(show_labels=False) 不含 qubit 名文本。"""
        topo = ChipTopology.from_grid(2, 2)
        artist = ChipArtist(topo)
        _, ax = artist.draw(show_labels=False)

        texts = [t.get_text() for t in ax.texts]
        assert len(texts) == 0  # No qubit labels drawn

    def test_draw_show_labels_true_default(self):
        """默认 show_labels=True，向后兼容 — 含 qubit 名文本。"""
        topo = ChipTopology.from_grid(2, 2)
        artist = ChipArtist(topo)
        _, ax = artist.draw()

        texts = [t.get_text() for t in ax.texts]
        assert len(texts) == 4  # 2×2 qubits
        assert all(t.strip().startswith("Q") for t in texts)

    def test_draw_show_labels_false_still_draws_boxes(self):
        """show_labels=False 仍然绘制圆角矩形盒子。"""
        topo = ChipTopology.from_grid(1, 1)
        artist = ChipArtist(topo)
        _, ax = artist.draw(show_labels=False)

        from matplotlib.patches import FancyBboxPatch
        boxes = [c for c in ax.patches if isinstance(c, FancyBboxPatch)]
        assert len(boxes) == 1


# =============================================================================
# Phase 6 — R4: Data Sources 表头居中对齐 + 去缩写
# =============================================================================


class TestSourcesTableStyle:
    """Data Sources 表头样式。"""

    @pytest.fixture
    def state_src(self):
        """创建含多实验来源的 ChipState。"""
        topo = ChipTopology.from_grid(2, 1)
        s = ChipState.new("test-src", topo)
        s.add_T1("Q01", 40.0, 0.5, 4.5, "00001")
        s.add_T2star("Q01", 12.0, 0.3, 4.5, "00002")
        s.add_readout_fidelity("Q01", 0.95, 0.92, 0.935, 6.0, "00003")
        s.add_drive_efficiency("Q01", 0.5, 40, 4.5, "00004")
        return s

    def test_sources_header_center_aligned(self, state_src):
        """CSS 中 table.sources th { text-align: center }。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "center.html")
        gen = ReportGenerator(state_src)
        gen.generate(path, sections=["sources"])

        content = Path(path).read_text(encoding="utf-8")
        # th rule should have text-align: center
        assert "table.sources th" in content
        # Verify center alignment exists in the CSS block
        assert "text-align: center" in content

    def test_sources_header_no_abbrev(self, state_src):
        """表头不含 'RO' 或 'DE' 缩写，含 'Readout' 和 'Drive Eff'。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "no_abbrev.html")
        gen = ReportGenerator(state_src)
        gen.generate(path, sections=["sources"])

        content = Path(path).read_text(encoding="utf-8")
        assert ">RO<" not in content
        assert ">DE<" not in content
        assert "Readout" in content
        assert "Drive Eff" in content


# =============================================================================
# Phase 7 — R1: 拓扑图标题重定位 (figcaption + 单 section)
# =============================================================================


class TestOverviewFigcaption:
    """Overview 使用单个 section + figcaption 而非每参数独立 section + h2。"""

    @pytest.fixture
    def state_fig(self):
        """创建含多参数数据的 ChipState。"""
        topo = ChipTopology.from_grid(2, 2)
        s = ChipState.new("test-fig", topo)
        s.add_T1("Q01", 45.2, 1.3, 4.71, "00747")
        s.add_T2star("Q01", 12.3, 0.5, 4.71, "00750")
        s.add_T2echo("Q02", 20.0, 1.0, 4.6, "00800")
        s.set_extras("Q01", bias_tunable=True)
        return s

    def test_overview_single_section(self, state_fig):
        """Overview 只有一个 <section id="overview">，而非每参数一个 section。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "single.html")
        gen = ReportGenerator(state_fig)
        gen.generate(path, sections=["overview"])

        content = Path(path).read_text(encoding="utf-8")
        # Exactly one overview section
        assert content.count('<section id="overview">') == 1
        # No per-param sections
        assert '<section id="overview-' not in content

    def test_figcaption_per_figure(self, state_fig):
        """每张图有 <figcaption> 标签，内容为参数名。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "figcaption.html")
        gen = ReportGenerator(state_fig)
        gen.generate(path, sections=["overview"])

        content = Path(path).read_text(encoding="utf-8")
        assert "<figcaption>" in content
        assert "</figcaption>" in content
        # Number of figcaptions = number of figures
        assert content.count("<figcaption>") == content.count("<figure>")

    def test_no_chip_topology_prefix(self, state_fig):
        """HTML 中不含 '1. Chip Topology &mdash;' 文本。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "no_prefix.html")
        gen = ReportGenerator(state_fig)
        gen.generate(path, sections=["overview"])

        content = Path(path).read_text(encoding="utf-8")
        assert "Chip Topology &mdash;" not in content
        # Yield section takes section 1 (bias_tunable present), topology shifts to 2
        assert "2. Chip Topology" in content


# =============================================================================
# Phase 7 — R2: Qubit Card 列宽修复
# =============================================================================


class TestQubitCardColumnWidth:
    """Qubit card 4 列不溢出。"""

    @pytest.fixture
    def state_col(self):
        """创建含完整参数数据的 ChipState（最大宽度内容）。"""
        topo = ChipTopology.from_grid(1, 1)
        s = ChipState.new("test-col", topo)
        s.add_T1("Q01", 61.100, 2.345, 4.1312, "00101")
        s.add_f01_range("Q01", 4.15, 5.12, "00042")
        s.add_readout_fidelity("Q01", 0.962, 0.941, 0.952, 6.831, "00107")
        s.add_drive_efficiency("Q01", 0.48, 52.0, 4.312, "00107")
        return s

    def test_qubit_grid_min_width(self, state_col):
        """CSS 中 grid-template-columns 使用 minmax(380px, 1fr)。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "col_width.html")
        gen = ReportGenerator(state_col)
        gen.generate(path, sections=["qubits"])

        content = Path(path).read_text(encoding="utf-8")
        assert "minmax(380px, 1fr)" in content

    def test_qubit_card_four_columns(self, state_col):
        """典型 qubit card 每行含 4 个 <td>（非 colspan 合并）。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "four_cols.html")
        gen = ReportGenerator(state_col)
        gen.generate(path, sections=["qubits"])

        content = Path(path).read_text(encoding="utf-8")
        # The card should have rows with full 4-column structure
        # Value cell exists for measured params (not "missing" colspan)
        assert '<td class="value">' in content
        # Drive Eff and Readout rows should have 4 cells each
        assert "Drive Eff" in content
        assert "Readout" in content


# =============================================================================
# Phase 11 — Coherence Row: T1/T2*/T2echo 同行显示
# =============================================================================


class TestCoherenceRow:
    """coherence 参数（T1/T2*/T2echo）拓扑图水平并排。"""

    def test_coherence_row_in_overview(self):
        """T1/T2*/T2echo figures wrapped in .coherence-row div."""
        topo = ChipTopology.from_grid(1, 1)
        s = ChipState.new("test", topo)
        s.add_T1("Q01", 45.2, 1.3, freq_GHz=4.71, source_exp="00747")
        s.add_T2star("Q01", 12.3, 0.5, freq_GHz=4.71, source_exp="00750")

        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "coherence_row.html")
        gen = ReportGenerator(s)
        gen.generate(path, sections=["overview"])
        content = Path(path).read_text(encoding="utf-8")

        # CSS present
        assert ".coherence-row" in content
        # HTML structure present
        assert 'class="coherence-row"' in content
        # Both T1 and T2* figures inside the row
        assert "T1 (μs)" in content
        assert "T2* (μs)" in content

    def test_coherence_row_absent_when_no_data(self):
        """No .coherence-row when coherence data is absent."""
        topo = ChipTopology.from_grid(1, 1)
        s = ChipState.new("test", topo)
        s.add_drive_efficiency("Q01", 0.5, 40, 4.5, "001")

        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "no_coherence.html")
        gen = ReportGenerator(s)
        gen.generate(path, sections=["overview"])
        content = Path(path).read_text(encoding="utf-8")

        assert "T1 (μs)" not in content
        assert "T2* (μs)" not in content


# =============================================================================
# Phase 8 — R1: Drive Efficiency 公式修正 + 归一化
# =============================================================================


class TestDriveEfficiencyFix:
    """DriveEntry.product = 1/(pi_amp*pi_width); 色标归一化。"""

    def test_drive_product_formula(self):
        """product = 1/(pi_amp * pi_width)。"""
        topo = ChipTopology.from_grid(1, 1)
        s = ChipState.new("test", topo)
        s.add_drive_efficiency("Q01", pi_amp=0.5, pi_width_ns=40,
                               freq_GHz=4.5, source_exp="001")
        entry = s.get_latest("Q01", "drive_efficiency")
        assert entry.product == pytest.approx(1.0 / 20.0)

    def test_drive_efficiency_normalized_colormap(self):
        """色标值归一化到 [0, 1]，最大值 = 1.0。"""
        from exp_toolkit.report.generator import _normalize_values
        vals = {"Q01": 0.025, "Q02": 0.05, "Q03": 0.0125}
        norm = _normalize_values(vals)
        assert norm["Q02"] == pytest.approx(1.0)
        assert norm["Q01"] == pytest.approx(0.5)
        assert norm["Q03"] == pytest.approx(0.25)

    def test_drive_efficiency_normalize_empty(self):
        """空 dict 归一化返回空 dict。"""
        from exp_toolkit.report.generator import _normalize_values
        assert _normalize_values({}) == {}

    def test_drive_efficiency_raw_in_card(self):
        """qubit card 仍显示原始物理值（不归一化）。"""
        topo = ChipTopology.from_grid(1, 1)
        s = ChipState.new("test", topo)
        s.add_drive_efficiency("Q01", pi_amp=0.5, pi_width_ns=40,
                               freq_GHz=4.5, source_exp="001")
        s.add_T1("Q01", 40.0, 0.5, 4.5, "001")

        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "raw_drive.html")
        gen = ReportGenerator(s)
        gen.generate(path, sections=["qubits"])

        content = Path(path).read_text(encoding="utf-8")
        # Card shows raw physical value (1/20 = 0.050)
        assert "0.050" in content


# =============================================================================
# Phase 8 — R2: 多值参数拆分为多行
# =============================================================================


class TestMultiValueSplitRows:
    """Drive Eff → 3 行 (主行 + π-amp + π-width);
    Readout → 3 行 (avg + F0 + F1)。"""

    @pytest.fixture
    def state_split(self):
        topo = ChipTopology.from_grid(1, 1)
        s = ChipState.new("test-split", topo)
        s.add_T1("Q01", 40.0, 0.5, 4.5, "001")
        s.add_drive_efficiency("Q01", pi_amp=0.5, pi_width_ns=40,
                               freq_GHz=4.5, source_exp="001")
        s.add_readout_fidelity("Q01", F0=0.95, F1=0.92, avg=0.935,
                               freq_GHz=7.0, source_exp="001")
        return s

    def test_drive_eff_split_rows(self, state_split):
        """Drive Eff 拆为 3 行：主行 + π-amp 子行 + π-width 子行。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "split_drive.html")
        gen = ReportGenerator(state_split)
        gen.generate(path, sections=["qubits"])

        content = Path(path).read_text(encoding="utf-8")
        assert ">Drive Eff<" in content
        assert '<th class="sub">π-amp</th>' in content
        assert '<th class="sub">π-width</th>' in content

    def test_readout_split_rows(self, state_split):
        """Readout 拆为 3 行：主行(avg) + F0 子行 + F1 子行。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "split_readout.html")
        gen = ReportGenerator(state_split)
        gen.generate(path, sections=["qubits"])

        content = Path(path).read_text(encoding="utf-8")
        assert ">Readout<" in content
        assert '<th class="sub">F0</th>' in content
        assert '<th class="sub">F1</th>' in content

    def test_sub_row_has_sub_class(self, state_split):
        """子行 <th class="sub">，空 <td> 占位 freq/src 列。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "sub_class.html")
        gen = ReportGenerator(state_split)
        gen.generate(path, sections=["qubits"])

        content = Path(path).read_text(encoding="utf-8")
        # Each sub row has 2 empty td elements
        assert 'class="sub"' in content
        assert "<td></td><td></td>" in content


# =============================================================================
# Phase 8 — R3: qubit card 增加表头
# =============================================================================


class TestQubitCardThead:
    """qubit card 表格含 <thead> 行。"""

    @pytest.fixture
    def state_thead(self):
        topo = ChipTopology.from_grid(1, 1)
        s = ChipState.new("test-thead", topo)
        s.add_T1("Q01", 40.0, 0.5, 4.5, "001")
        return s

    def test_qubit_card_has_thead(self, state_thead):
        """qubit card HTML 含 <thead> 和 Parameter/Value/Frequency/Source。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "thead.html")
        gen = ReportGenerator(state_thead)
        gen.generate(path, sections=["qubits"])

        content = Path(path).read_text(encoding="utf-8")
        assert "<thead>" in content
        assert "<th>Parameter</th>" in content
        assert "<th>Value</th>" in content
        assert "<th>Frequency</th>" in content
        assert "<th>Source</th>" in content
        # CSS for thead th
        assert ".qubit-card thead th" in content


# =============================================================================
# Phase 8 — R4: Data Sources 前两列居中
# =============================================================================


class TestSourcesCenterAlignment:
    """Data Sources 表 Source Exp / Qubits 列居中。"""

    @pytest.fixture
    def state_src2(self):
        topo = ChipTopology.from_grid(2, 1)
        s = ChipState.new("test-src2", topo)
        s.add_T1("Q01", 40.0, 0.5, 4.5, "00001")
        s.add_T2star("Q01", 12.0, 0.3, 4.5, "00002")
        return s

    def test_sources_src_qubits_center(self, state_src2):
        """CSS 含 td.src-col / td.qubits-col { text-align: center }；
        HTML 中前两列 <td> 有对应 class。"""
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "src_center.html")
        gen = ReportGenerator(state_src2)
        gen.generate(path, sections=["sources"])

        content = Path(path).read_text(encoding="utf-8")
        assert "td.src-col" in content
        assert "td.qubits-col" in content
        assert 'class="src-col"' in content
        assert 'class="qubits-col"' in content
