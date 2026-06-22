"""IO 模块测试 — 使用合成数据验证读取和解析功能。

测试覆盖：
- parse_ini_metadata: INI 解析（T1 1D + Spectro 2D）
- load_parameters: JSON 参数快照解析（含 verified_qubits）
- load_csv_with_meta: CSV 数据加载 + 列分割
- load_experiment: 端到端三元组加载
- 辅助函数: _extract_exp_id, _parse_complex, _parse_ini_value
- 错误路径: 缺失文件、格式错误、列数不匹配
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from exp_toolkit.io.readers import (
    ColumnMeta,
    Experiment,
    IQBlobs,
    ParamsSnapshot,
    QubitParams,
    _extract_exp_id,
    _parse_complex,
    _parse_ini_value,
    load_csv_with_meta,
    load_experiment,
    load_parameters,
    parse_ini_metadata,
)


# =============================================================================
# Fixtures — 合成数据生成
# =============================================================================


def _write_t1_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    """在临时目录创建 T1 实验三元组。"""
    exp_id = "00747"
    base = f"{exp_id} - T1_ground, Q16"

    # CSV: 21 行 × 9 列
    csv_path = tmp_path / f"{base}.csv"
    delay = np.linspace(0, 100, 21)
    tau_true = 45.0
    noise = np.random.default_rng(42).normal(0, 0.02, 21)
    p1 = 0.8 * np.exp(-delay / tau_true) + 0.2 + noise
    p0 = 1.0 - p1
    csv_data = np.column_stack(
        [delay] + [p0, p1, p0, p1, p0 + 0.05, p1 - 0.05, p0 + 0.05, p1 - 0.05]
    )
    np.savetxt(csv_path, csv_data, delimiter=",", fmt="%.10f")

    # INI
    ini_path = tmp_path / f"{base}.ini"
    ini_content = """[General]
created = 2026-06-10, 13:10:29
title = T1_ground, Q16
independent = 1
dependent = 8
parameters = 4
comments = 0

[Independent 1]
label = coherence delay
units = us

[Dependent 1]
label =
units =
category = Q16 P0

[Dependent 2]
label =
units =
category = Q16 P1

[Dependent 3]
label =
units =
category = P0

[Dependent 4]
label =
units =
category = P1

[Dependent 5]
label =
units =
category = Q16 P0 for |0>

[Dependent 6]
label =
units =
category = Q16 P1 for |0>

[Dependent 7]
label =
units =
category = P0 for |0>

[Dependent 8]
label =
units =
category = P1 for |0>

[Parameter 1]
label = -qidxs
data = '[16]'

[Parameter 2]
label = -ancilla_ouput
data = '[11, 12, 13, 14, 15, 17, 18, 19, 20]'

[Parameter 3]
label = -delay
data = 'r[0:100:5,us]'

[Parameter 4]
label = -reps
data = '600'

[Parameter 5]
label = measure
data = '["Q16"]'

[Comments]
"""
    ini_path.write_text(ini_content)

    # JSON
    json_path = tmp_path / f"{exp_id} - parameters.json"
    json_content = {
        "qubits": {
            "Q16": {
                "f01(GHz)": 4.7137,
                "f12(GHz)": 3.2,
                "pi_amp": 0.66,
                "pi_width(ns)": 30,
                "readout_freq(GHz)": 6.237,
                "readout_amp(dBm)": -10,
                # 以下字段不应被丢弃（P0 修复验证）
                "offset": -0.1,
                "shape": "cos",
                "pi_drag(ns)": 0,
                "pihalf_amp": 0.33,
                "pihalf_width(ns)": 30,
                "demod_len": 1000,
                "gate_zpa": 0,
                "gate_zpa_start(us)": 1,
                "readout_zpa": 0,
                "readout_zpa_start(us)": 48.02,
                "readout3_freq(GHz)": 6.1905,
                "readout3_amp(dBm)": -20,
                "dr_lo_freq(GHz)": 5,
                "dr_lo_power(dBm)": 9,
                "readout_lo_freq(GHz)": 6.3,
                "readout_lo_power(dBm)": 9,
                "pi12_amp": 0.6625,
                "pi12_width(ns)": 60,
                "pihalf_drag(ns)": 0,
                # 未知字段也应保留在 extras
                "unknown_future_param": "keep_me",
            },
            "Q07": {
                "f01(GHz)": 4.515,
                "pi_amp": 0.447,
                "pi_width(ns)": 30,
                "readout_freq(GHz)": 6.3085,
                "readout_amp(dBm)": 0,
            },
        },
        "couplers": {"C_01_02": {"coupling_MHz": 15.2}},
        "readout_IQ": {
            "Q16_2": {
                "centers": ["-84394.7862-32380.0077j", "-35725.2949-154515.2156j"],
                "varis": 63681.9432,
            }
        },
        "lines": {"Q16_z": {"delay(ns)": 6, "z_scale1": 0.0005}},
    }
    json_path.write_text(json.dumps(json_content))

    return csv_path, ini_path, json_path


def _write_spectro_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    """在临时目录创建 Spectro 2D 实验三元组。"""
    exp_id = "00023"
    base = f"{exp_id} - spectro, Q07"

    # CSV: 简化版 2D 光谱 (3 zpa × 5 freq = 15 rows, 6 cols)
    csv_path = tmp_path / f"{base}.csv"
    zpa_vals = [-0.5, 0.0, 0.5]
    freq_vals = [4.0, 4.2, 4.4, 4.6, 4.8]
    rows = []
    for zpa in zpa_vals:
        for freq in freq_vals:
            amp = 200000 + np.random.default_rng(42).normal(0, 5000)
            phase = 1.8 + np.random.default_rng(43).normal(0, 0.05)
            i_val = amp * math.cos(phase)
            q_val = amp * math.sin(phase)
            rows.append([zpa, freq, amp, phase, i_val, q_val])
    np.savetxt(csv_path, np.array(rows), delimiter=",", fmt="%.10f")

    # INI
    ini_path = tmp_path / f"{base}.ini"
    ini_content = """[General]
created = 2026-06-16, 15:35:42
title = spectro, Q07
independent = 2
dependent = 4
parameters = 4
comments = 0

[Independent 1]
label = zpa
units =

[Independent 2]
label = dr_freq
units = GHz

[Dependent 1]
label =
units =
category = Q07 IQ Amp

[Dependent 2]
label =
units = rad
category = Q07 IQ phase

[Dependent 3]
label =
units =
category = Q07 I

[Dependent 4]
label =
units =
category = Q07 Q

[Parameter 1]
label = -qidxs
data = '[7]'

[Parameter 2]
label = -dr_freq
data = 'r[4.0:5.4:0.004,GHz]'

[Parameter 3]
label = -zpa
data = 'r[-0.5:0.5:0.05]'

[Parameter 4]
label = measure
data = '["Q07"]'

[Comments]
"""
    ini_path.write_text(ini_content)

    # JSON (与 T1 共享结构，使用同一个即可)
    json_path = tmp_path / f"{exp_id} - parameters.json"
    json_content = {
        "qubits": {
            "Q07": {
                "f01(GHz)": 4.515,
                "pi_amp": 0.447,
                "pi_width(ns)": 30,
                "readout_freq(GHz)": 6.3085,
                "readout_amp(dBm)": 0,
            },
        },
        "couplers": {},
        "readout_IQ": {},
        "lines": {},
    }
    json_path.write_text(json.dumps(json_content))

    return csv_path, ini_path, json_path


# =============================================================================
# _extract_exp_id
# =============================================================================


class TestExtractExpId:
    def test_standard_format(self):
        assert _extract_exp_id("00747 - T1_ground, Q16.csv") == "00747"

    def test_with_path(self):
        assert _extract_exp_id("/data/00023 - spectro, Q07.csv") == "00023"

    def test_two_digit_exp_id(self):
        assert _extract_exp_id("42 - T1_ground, Q01.ini") == "42"

    def test_no_space_before_dash_raises(self):
        with pytest.raises(ValueError, match="Cannot extract experiment ID"):
            _extract_exp_id("nodash.csv")

    def test_only_leading_digits(self):
        assert _extract_exp_id("12345_something.csv") == "12345"


# =============================================================================
# _parse_complex
# =============================================================================


class TestParseComplex:
    def test_negative_imag(self):
        c = _parse_complex("-67110.8047-166303.3734j")
        assert math.isclose(c.real, -67110.8047)
        assert math.isclose(c.imag, -166303.3734)

    def test_negative_real_positive_imag(self):
        c = _parse_complex("-84394.7862+32380.0077j")
        assert math.isclose(c.real, -84394.7862)
        assert math.isclose(c.imag, 32380.0077)

    def test_positive_both(self):
        c = _parse_complex("100.0+200.5j")
        assert math.isclose(c.real, 100.0)
        assert math.isclose(c.imag, 200.5)

    def test_pure_imaginary(self):
        c = _parse_complex("0+123j")
        assert math.isclose(c.real, 0.0)
        assert math.isclose(c.imag, 123.0)

    def test_no_j_suffix(self):
        c = _parse_complex("10.5-3.2")
        assert math.isclose(c.real, 10.5)
        assert math.isclose(c.imag, -3.2)

    def test_scientific_notation_raises(self):
        """P2 修复：科学记数法应显式报错，而非静默产生错误数值。"""
        with pytest.raises(ValueError, match="Scientific notation"):
            _parse_complex("1.5e-5+2j")


# =============================================================================
# _parse_ini_value
# =============================================================================


class TestParseIniValue:
    def test_quoted_string_returns_unquoted(self):
        assert _parse_ini_value("'hello'") == "hello"

    def test_quoted_list_of_ints(self):
        assert _parse_ini_value("'[16]'") == [16]

    def test_quoted_range_spec(self):
        # r[...] 内部是 range spec，不是合法 JSON，退回字符串
        assert _parse_ini_value("'r[0:100:5,us]'") == "r[0:100:5,us]"

    def test_bare_int(self):
        assert _parse_ini_value("600") == 600

    def test_bare_float(self):
        assert _parse_ini_value("2.2e-07") == pytest.approx(2.2e-7)

    def test_json_array(self):
        assert _parse_ini_value('["Q16"]') == ["Q16"]

    def test_empty_string(self):
        assert _parse_ini_value("") == ""


# =============================================================================
# parse_ini_metadata
# =============================================================================


class TestParseIniMetadata:
    def test_t1_ini(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        meta = parse_ini_metadata(ini_p)

        assert meta.title == "T1_ground, Q16"
        assert meta.created == datetime(2026, 6, 10, 13, 10, 29)
        assert meta.n_independent == 1
        assert meta.n_dependent == 8
        assert len(meta.independent_vars) == 1
        assert len(meta.dependent_vars) == 8

        # Independent 列
        assert meta.independent_vars[0].label == "coherence delay"
        assert meta.independent_vars[0].units == "us"

        # Dependent 列
        assert meta.dependent_vars[0].category == "Q16 P0"
        assert meta.dependent_vars[1].category == "Q16 P1"

        # Parameters
        assert "-qidxs" in meta.parameters
        assert meta.parameters["-qidxs"] == "'[16]'"
        assert meta.parameters["-delay"] == "'r[0:100:5,us]'"

    def test_spectro_2d_ini(self, tmp_path):
        csv_p, ini_p, json_p = _write_spectro_files(tmp_path)
        meta = parse_ini_metadata(ini_p)

        assert meta.title == "spectro, Q07"
        assert meta.n_independent == 2
        assert meta.n_dependent == 4
        assert len(meta.independent_vars) == 2
        assert len(meta.dependent_vars) == 4

        assert meta.independent_vars[0].label == "zpa"
        assert meta.independent_vars[1].label == "dr_freq"
        assert meta.independent_vars[1].units == "GHz"

        assert meta.dependent_vars[0].category == "Q07 IQ Amp"
        assert meta.dependent_vars[2].category == "Q07 I"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_ini_metadata(tmp_path / "nonexistent.ini")

    def test_missing_general_section(self, tmp_path):
        ini_path = tmp_path / "bad.ini"
        ini_path.write_text("[Something]\nkey=val\n")
        with pytest.raises(IOError, match="missing \\[General\\]"):
            parse_ini_metadata(ini_path)


# =============================================================================
# load_parameters
# =============================================================================


class TestLoadParameters:
    def test_load_t1_params(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        params = load_parameters(json_p)

        assert "Q16" in params.qubits
        q = params.qubits["Q16"]
        assert math.isclose(q.f01, 4.7137)
        assert math.isclose(q.pi_amp, 0.66)
        assert math.isclose(q.pi_width, 30)
        assert math.isclose(q.readout_freq, 6.237)
        assert math.isclose(q.readout_amp, -10)
        assert math.isclose(q.f12, 3.2)
        assert q.verified is False  # 未传入 verified_qubits

        # Q07 也有数据
        assert "Q07" in params.qubits

    def test_verified_qubits(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        params = load_parameters(json_p, verified_qubits=["Q16"])

        assert params.qubits["Q16"].verified is True
        assert params.qubits["Q07"].verified is False

    def test_iq_blobs(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        params = load_parameters(json_p)

        assert "Q16_2" in params.readout_iq
        blob = params.readout_iq["Q16_2"]
        assert blob.n_states == 2
        assert blob.variance == pytest.approx(63681.9432)
        assert len(blob.centers) == 2
        assert blob.centers[0].imag == pytest.approx(-32380.0077)

    def test_couplers(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        params = load_parameters(json_p)

        assert "C_01_02" in params.couplers
        assert params.couplers["C_01_02"]["coupling_MHz"] == 15.2

    def test_lines(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        params = load_parameters(json_p)

        assert "Q16_z" in params.lines
        assert params.lines["Q16_z"]["delay(ns)"] == pytest.approx(6.0)

    def test_missing_required_field_raises(self, tmp_path):
        json_path = tmp_path / "bad_params.json"
        json_path.write_text(json.dumps({
            "qubits": {"Q01": {"f01(GHz)": 4.5}},
            "couplers": {},
            "readout_IQ": {},
            "lines": {},
        }))
        with pytest.raises(ValueError, match="missing required fields"):
            load_parameters(json_path)

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_parameters(tmp_path / "nope.json")


# =============================================================================
# load_csv_with_meta
# =============================================================================


class TestLoadCsvWithMeta:
    def test_t1_csv(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        meta = parse_ini_metadata(ini_p)

        data, ivars, dvars = load_csv_with_meta(csv_p, meta)

        assert data.shape == (21, 9)
        assert len(ivars) == 1
        assert len(dvars) == 8

        # 第一列 = delay (自变量)
        assert data[0, 0] == 0.0
        assert data[-1, 0] == 100.0

    def test_spectro_2d_csv(self, tmp_path):
        csv_p, ini_p, json_p = _write_spectro_files(tmp_path)
        meta = parse_ini_metadata(ini_p)

        data, ivars, dvars = load_csv_with_meta(csv_p, meta)

        assert data.shape == (15, 6)
        assert len(ivars) == 2
        assert len(dvars) == 4

    def test_column_count_mismatch(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        meta = parse_ini_metadata(ini_p)
        # 修改 meta 使其期望错误的列数
        meta.n_dependent = 2  # 期望 3 列，实际 9 列

        with pytest.raises(ValueError, match="Column mismatch"):
            load_csv_with_meta(csv_p, meta)

    def test_file_not_found(self, tmp_path):
        from exp_toolkit.io.readers import IniMeta as IM

        meta = IM(
            title="test", created=None,
            n_independent=1, n_dependent=2,
            independent_vars=[], dependent_vars=[],
            parameters={},
        )
        with pytest.raises(FileNotFoundError):
            load_csv_with_meta(tmp_path / "nope.csv", meta)


# =============================================================================
# load_experiment — 端到端
# =============================================================================


class TestLoadExperiment:
    def test_t1_end_to_end(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        exp = load_experiment(csv_p)

        assert exp.exp_id == "00747"
        assert exp.title == "T1_ground, Q16"
        assert exp.timestamp == datetime(2026, 6, 10, 13, 10, 29)
        assert exp.data.shape == (21, 9)
        assert len(exp.independent_vars) == 1
        assert len(exp.dependent_vars) == 8
        assert exp.params is not None
        assert "Q16" in exp.params.qubits
        # Verified qubits 应包含 Q16（来自 -qidxs=[16] 和 measure=["Q16"]）
        assert exp.params.qubits["Q16"].verified is True
        # Settings 应有类型化值
        assert exp.settings["-qidxs"] == [16]
        assert exp.settings["-reps"] == 600
        # 路径字段
        assert exp.csv_path == csv_p
        assert exp.ini_path == ini_p
        assert exp.json_path == json_p
        assert exp.source_dir == tmp_path

    def test_from_ini_path(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        exp = load_experiment(ini_p)

        assert exp.exp_id == "00747"
        assert exp.csv_path == csv_p

    def test_spectro_2d_end_to_end(self, tmp_path):
        csv_p, ini_p, json_p = _write_spectro_files(tmp_path)
        exp = load_experiment(csv_p)

        assert exp.exp_id == "00023"
        assert exp.title == "spectro, Q07"
        assert len(exp.independent_vars) == 2
        assert len(exp.dependent_vars) == 4
        assert exp.data.shape == (15, 6)

    def test_missing_json_warns(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        # 删除 JSON
        json_p.unlink()

        with pytest.warns(UserWarning, match="参数快照将为空"):
            exp = load_experiment(csv_p)

        assert exp.params is None
        assert exp.json_path is None

    def test_missing_csv(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        csv_p.unlink()

        with pytest.raises(FileNotFoundError, match="CSV file not found"):
            load_experiment(ini_p)

    def test_missing_ini(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        ini_p.unlink()

        with pytest.raises(FileNotFoundError, match="INI file not found"):
            load_experiment(csv_p)

    def test_unsupported_extension(self, tmp_path):
        bad_path = tmp_path / "00747.txt"
        bad_path.write_text("hello")
        with pytest.raises(ValueError, match="Unsupported file type"):
            load_experiment(bad_path)

    def test_csv_column_mismatch_raises(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        # 修改 INI 声明错误的列数
        meta = parse_ini_metadata(ini_p)
        # 创建一个声明错误列数的 INI
        bad_ini = tmp_path / "bad.ini"
        bad_ini.write_text(
            ini_p.read_text().replace("dependent = 8", "dependent = 2")
        )
        bad_csv = csv_p
        csv_p_bad = tmp_path / f"{csv_p.stem}_bad.csv"
        # 使用原来的 CSV 但指向错误的 INI
        # 需要重新走 _find_matching_files
        bad_base = csv_p.stem
        bad_ini2 = tmp_path / f"{bad_base}.ini"
        bad_ini2.write_text(
            ini_p.read_text().replace("dependent = 8", "dependent = 2")
        )

        with pytest.raises(ValueError, match="Column mismatch"):
            load_experiment(csv_p)

    def test_ancilla_ouput_verified(self, tmp_path):
        """P1 修复：ancilla_ouput 路径测试覆盖。"""
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        exp = load_experiment(csv_p)

        # ancilla_ouput = [11, 12, 13, 14, 15, 17, 18, 19, 20]
        # measure = ["Q16"]
        # qidxs = [16]
        # 因此 Q11-Q20 全部应被标记为 verified
        for idx in range(11, 21):
            qname = f"Q{idx:02d}"
            if qname in exp.params.qubits:
                assert exp.params.qubits[qname].verified is True, (
                    f"{qname} should be verified from ancilla list"
                )

    def test_p0_extras_preserved(self, tmp_path):
        """P0 修复：非提取字段（pi_drag, gate_zpa 等）应进入 extras，不丢弃。"""
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        from exp_toolkit.io.readers import load_parameters
        params = load_parameters(json_p)

        q16 = params.qubits["Q16"]
        # 验证非提取字段保留在 extras 中
        assert "pi_drag(ns)" in q16.extras
        assert q16.extras["pi_drag(ns)"] == 0
        assert "gate_zpa" in q16.extras
        assert "demod_len" in q16.extras
        assert "offset" in q16.extras
        assert q16.extras["offset"] == -0.1
        # 未知字段也应保留
        assert "unknown_future_param" in q16.extras
        assert q16.extras["unknown_future_param"] == "keep_me"
        # 验证提取字段不重复出现在 extras 中
        assert "f01(GHz)" not in q16.extras
        assert "pi_amp" not in q16.extras
        assert "readout_freq(GHz)" not in q16.extras

    def test_experiment_dataclass_fields(self, tmp_path):
        csv_p, ini_p, json_p = _write_t1_files(tmp_path)
        exp = load_experiment(csv_p)

        # 验证 Experiment 数据类的所有字段可访问
        assert isinstance(exp.exp_id, str)
        assert isinstance(exp.title, str)
        assert isinstance(exp.timestamp, datetime)
        assert isinstance(exp.independent_vars, list)
        assert isinstance(exp.dependent_vars, list)
        assert isinstance(exp.data, np.ndarray)
        assert isinstance(exp.params, ParamsSnapshot)
        assert isinstance(exp.settings, dict)
        assert isinstance(exp.source_dir, Path)
        assert isinstance(exp.csv_path, Path)
        assert isinstance(exp.ini_path, Path)
