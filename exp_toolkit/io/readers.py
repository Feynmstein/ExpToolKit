"""IO 模块 — 实验数据的统一读写。

提供实验三元组（CSV + INI + JSON）的读取和结构化。
"""

from __future__ import annotations

import ast
import configparser
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ColumnMeta:
    """列元数据 — 描述实验数据中某一列的物理含义。

    Attributes
    ----------
    label : str
        列标签，来自 INI [Independent N] 或 [Dependent N] 节的 label 字段。
    units : str
        物理单位，如 "us", "GHz", "rad"。
    category : str
        列含义的核心描述，如 "Q16 P1", "Q07 IQ Amp"。
    """

    label: str
    units: str
    category: str


@dataclass
class QubitParams:
    """单个比特的参数快照，提取自 parameters.json。

    Attributes
    ----------
    f01 : float
        |0⟩→|1⟩ 跃迁频率 (GHz)。
    pi_amp : float
        π 脉冲幅度。
    pi_width : float
        π 脉冲宽度 (ns)。
    readout_freq : float
        读取频率 (GHz)。
    readout_amp : float
        读取脉冲幅度 (dBm)。
    f12 : float | None
        |1⟩→|2⟩ 跃迁频率 (GHz)，缺失时为 None。
    verified : bool
        本次实验是否确认了该比特的测量参数。
    extras : dict
        JSON 中其他未标准化的字段。
    """

    f01: float
    pi_amp: float
    pi_width: float
    readout_freq: float
    readout_amp: float
    f12: float | None = None
    verified: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class IQBlobs:
    """IQ 分类器参数 — IQ 平面上的 Gaussian 分类中心。

    Attributes
    ----------
    centers : list[complex]
        分类中心（2 或 3 个复数坐标）。
    variance : float
        分类方差。
    n_states : int
        分类数（2 或 3）。
    """

    centers: list[complex]
    variance: float
    n_states: int


@dataclass
class ParamsSnapshot:
    """芯片参数快照，解析自 parameters.json。

    Attributes
    ----------
    qubits : dict[str, QubitParams]
        各比特的物理参数，key 为比特名（如 "Q16"）。
    couplers : dict[str, Any]
        耦合器参数（保留原始结构）。
    readout_iq : dict[str, IQBlobs]
        IQ 分类器参数，key 为标识符（如 "Q16_2"）。
    lines : dict[str, dict[str, float]]
        线路/滤波器参数。
    """

    qubits: dict[str, QubitParams]
    couplers: dict[str, Any]
    readout_iq: dict[str, IQBlobs]
    lines: dict[str, dict[str, float]]


@dataclass
class IniMeta:
    """INI 文件解析结果 — 实验元数据。

    Attributes
    ----------
    title : str
        实验标题，如 "T1_ground, Q16"。
    created : datetime | None
        实验创建时间。
    n_independent : int
        自变量列数。
    n_dependent : int
        因变量列数。
    independent_vars : list[ColumnMeta]
        自变量列元数据列表。
    dependent_vars : list[ColumnMeta]
        因变量列元数据列表。
    parameters : dict[str, str]
        原始 Parameter 节内容，key=label, value=data（字符串，未做类型转换）。
    comments : str
        注释内容。
    """

    title: str
    created: datetime | None
    n_independent: int
    n_dependent: int
    independent_vars: list[ColumnMeta]
    dependent_vars: list[ColumnMeta]
    parameters: dict[str, str]
    comments: str = ""


@dataclass
class Experiment:
    """一次实验的完整数据，包含原始数据、元数据和参数快照。

    Attributes
    ----------
    exp_id : str
        实验编号，如 "00747"。
    title : str
        实验标题，来自 INI General.title。
    timestamp : datetime | None
        实验时间戳。
    independent_vars : list[ColumnMeta]
        自变量列元数据。
    dependent_vars : list[ColumnMeta]
        因变量列元数据。
    data : np.ndarray
        原始数据矩阵，shape = (n_rows, n_independent + n_dependent)。
        前 n_independent 列为自变量，其余为因变量。
    params : ParamsSnapshot | None
        参数快照（来自 parameters.json），缺失时为 None。
    settings : dict[str, Any]
        INI Parameter 节的类型化键值对。
    source_dir : Path
        数据文件所在目录。
    csv_path : Path
        CSV 文件路径。
    ini_path : Path
        INI 文件路径。
    json_path : Path | None
        JSON 文件路径，缺失时为 None。
    """

    exp_id: str
    title: str
    timestamp: datetime | None
    independent_vars: list[ColumnMeta]
    dependent_vars: list[ColumnMeta]
    data: np.ndarray
    params: ParamsSnapshot | None
    settings: dict[str, Any]
    source_dir: Path
    csv_path: Path
    ini_path: Path
    json_path: Path | None = None


# =============================================================================
# Helpers
# =============================================================================


def _extract_exp_id(filename: str | Path) -> str:
    """从文件名中提取实验编号（数字前缀）。

    Parameters
    ----------
    filename : str or Path
        文件名或路径。

    Returns
    -------
    str
        实验编号字符串，如 "00747"。

    Raises
    ------
    ValueError
        无法提取实验编号时抛出。
    """
    name = Path(filename).name
    # 匹配开头连续数字 + 空格 + 横线
    m = re.match(r"^(\d+)\s+-", name)
    if m:
        return m.group(1)
    # 回退：取开头连续数字
    m = re.match(r"^(\d+)", name)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot extract experiment ID from filename: '{name}'")


def _parse_complex(s: str) -> complex:
    """解析复数字符串 'real+imagj' 或 'real-imagj' 为 Python complex。

    从右侧扫描最后一个非指数符号的 +/- 号作为虚部分隔。

    Parameters
    ----------
    s : str
        复数字符串，如 "-67110.8047-166303.3734j"。

    Returns
    -------
    complex

    Raises
    ------
    ValueError
        若字符串含科学记数法（尚未支持）或无法解析。
    """
    s = s.strip()

    # 显式拒绝含科学记数法的输入，避免误切分
    if "e" in s.lower():
        raise ValueError(
            f"Scientific notation in complex numbers is not yet supported: '{s}'"
        )

    suffix = ""
    if s.endswith("j") or s.endswith("J"):
        suffix = s[-1]
        s = s[:-1]

    # 从右向左找第一个 +/-（跳过末尾的数值部分）
    # 但要跳过开头符号（首个字符的 +/-）
    split_pos = -1
    for i in range(len(s) - 1, 0, -1):  # 从 len-1 到 1，跳过 s[0]
        if s[i] in ("+", "-"):
            split_pos = i
            break

    if split_pos > 0:
        real_str = s[:split_pos]
        imag_str = s[split_pos:]
    else:
        # 纯虚数或纯实数
        # 如果原字符串以 j 结尾则为纯虚数，否则为纯实数
        if suffix:
            real_str = "0"
            imag_str = s
        else:
            real_str = s
            imag_str = "0"

    imag_str = imag_str.strip()
    if imag_str in ("+", "-", ""):
        imag_str += "1"
    return complex(float(real_str), float(imag_str))


def _parse_ini_value(raw: str) -> Any:
    r"""将 INI 数据字符串转换为适当的 Python 类型。

    转换规则：
    - 纯数字 → int 或 float
    - 单引号包裹 → 去引号后尝试 JSON/数字解析，否则为字符串
    - JSON 数组 → list
    - 其他 → 原字符串

    Parameters
    ----------
    raw : str
        INI data= 后的原始字符串。

    Returns
    -------
    Any
    """
    raw = raw.strip()

    if not raw:
        return ""

    # 单引号包裹的字符串
    if raw.startswith("'") and raw.endswith("'"):
        inner = raw[1:-1]
        # 尝试解析内部内容
        try:
            return json.loads(inner)
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            return int(inner)
        except ValueError:
            pass
        try:
            return float(inner)
        except ValueError:
            pass
        return inner

    # 以 [ 开头的 JSON 数组
    if raw.startswith("["):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            pass

    # 裸数字
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass

    # 保持原字符串
    return raw


def _find_matching_files(path: str | Path) -> tuple[Path, Path, Path | None]:
    """根据 CSV 或 INI 路径，找到同编号的三个文件。

    Parameters
    ----------
    path : str or Path
        CSV 或 INI 文件路径。

    Returns
    -------
    tuple[Path, Path, Path | None]
        (csv_path, ini_path, json_path)。JSON 可能为 None。
    """
    p = Path(path).resolve()
    directory = p.parent
    exp_id = _extract_exp_id(p.name)

    # 获取当前文件的 stem（去掉扩展名）来确定 CSV/INI 基名
    if p.suffix.lower() == ".csv":
        csv_path = p
        base = p.stem
        ini_path = directory / f"{base}.ini"
    elif p.suffix.lower() == ".ini":
        ini_path = p
        base = p.stem
        csv_path = directory / f"{base}.csv"
    else:
        raise ValueError(
            f"Unsupported file type: '{p.suffix}'. Expected .csv or .ini"
        )

    # JSON 文件：{exp_id} - parameters.json
    json_path = directory / f"{exp_id} - parameters.json"
    if not json_path.exists():
        json_path = None

    # 验证 CSV 和 INI 文件存在
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    if not ini_path.exists():
        raise FileNotFoundError(f"INI file not found: {ini_path}")

    return csv_path, ini_path, json_path


def _extract_verified_qubits(ini_meta: IniMeta) -> list[str]:
    r"""从 INI 参数中提取本次实验确认有效的比特列表。

    检查以下参数：
    - ``-qidxs``：直接测量的比特索引
    - ``-ancilla_ouput``：ancilla 比特索引
    - ``measure``：比特名称列表（如 ['Q16']）

    Parameters
    ----------
    ini_meta : IniMeta
        INI 元数据。

    Returns
    -------
    list[str]
        比特名称列表，如 ["Q16", "Q11", "Q12", ...]。
    """
    verified: set[str] = set()

    def _add_qubit_name(idx: int) -> None:
        """将比特索引转换为名称并加入 verified 集合。
        尝试零填充格式 (Q07) 和非填充格式 (Q7)，覆盖两种命名约定。
        """
        verified.add(f"Q{idx:02d}")
        verified.add(f"Q{idx}")

    # 从 -qidxs 提取（索引 → 比特名称）
    qidxs_raw = ini_meta.parameters.get("-qidxs")
    if qidxs_raw:
        try:
            indices = _parse_ini_value(qidxs_raw)
            if isinstance(indices, list):
                for idx in indices:
                    if isinstance(idx, int):
                        _add_qubit_name(idx)
        except Exception:
            pass

    # 从 -ancilla_ouput 提取
    ancilla_raw = ini_meta.parameters.get("-ancilla_ouput")
    if ancilla_raw:
        try:
            indices = _parse_ini_value(ancilla_raw)
            if isinstance(indices, list):
                for idx in indices:
                    if isinstance(idx, int):
                        _add_qubit_name(idx)
        except Exception:
            pass

    # 从 measure 参数提取（直接给出名称）
    measure_raw = ini_meta.parameters.get("measure")
    if measure_raw:
        try:
            names = _parse_ini_value(measure_raw)
            if isinstance(names, list):
                for name in names:
                    if isinstance(name, str) and name.startswith("Q"):
                        verified.add(name)
        except Exception:
            pass

    return sorted(verified)


# =============================================================================
# Public API
# =============================================================================


def parse_ini_metadata(ini_path: str | Path) -> IniMeta:
    """解析 INI 实验配置文件，提取元数据。

    Parameters
    ----------
    ini_path : str or Path
        INI 文件路径。

    Returns
    -------
    IniMeta

    Raises
    ------
    FileNotFoundError
        INI 文件不存在。
    IOError
        INI 格式不合法（缺少必需的节或字段）。
    """
    ini_path = Path(ini_path)
    if not ini_path.exists():
        raise FileNotFoundError(f"INI file not found: {ini_path}")

    cfg = configparser.ConfigParser(
        inline_comment_prefixes=(";",),
        empty_lines_in_values=False,
    )
    try:
        with open(ini_path, encoding="utf-8") as f:
            cfg.read_file(f)
    except configparser.Error as e:
        raise IOError(f"Failed to parse INI file '{ini_path}': {e}") from e

    if "General" not in cfg:
        raise IOError(
            f"Failed to parse INI '{ini_path}': missing [General] section"
        )

    general = cfg["General"]

    # === General 节 ===
    title = general.get("title", "")
    n_independent = general.getint("independent", 0)
    n_dependent = general.getint("dependent", 0)
    n_parameters = general.getint("parameters", 0)

    created_str = general.get("created", "")
    created: datetime | None = None
    if created_str:
        try:
            created = datetime.strptime(created_str, "%Y-%m-%d, %H:%M:%S")
        except ValueError:
            # 日期格式可能不完全一致，保留为 None
            pass

    # === Independent 节 ===
    independent_vars: list[ColumnMeta] = []
    for i in range(1, n_independent + 1):
        section_name = f"Independent {i}"
        if section_name in cfg:
            sec = cfg[section_name]
            independent_vars.append(
                ColumnMeta(
                    label=sec.get("label", ""),
                    units=sec.get("units", ""),
                    category=sec.get("category", ""),
                )
            )
        else:
            independent_vars.append(ColumnMeta(label="", units="", category=""))

    # === Dependent 节 ===
    dependent_vars: list[ColumnMeta] = []
    for i in range(1, n_dependent + 1):
        section_name = f"Dependent {i}"
        if section_name in cfg:
            sec = cfg[section_name]
            dependent_vars.append(
                ColumnMeta(
                    label=sec.get("label", ""),
                    units=sec.get("units", ""),
                    category=sec.get("category", ""),
                )
            )
        else:
            dependent_vars.append(ColumnMeta(label="", units="", category=""))

    # === Parameter 节 ===
    parameters: dict[str, str] = {}
    for i in range(1, n_parameters + 1):
        section_name = f"Parameter {i}"
        if section_name in cfg:
            sec = cfg[section_name]
            label = sec.get("label", "")
            data = sec.get("data", "")
            if label:
                parameters[label] = data

    # === Comments 节 ===
    comments = ""
    if "Comments" in cfg:
        comments = cfg["Comments"].get("comments", "")

    return IniMeta(
        title=title,
        created=created,
        n_independent=n_independent,
        n_dependent=n_dependent,
        independent_vars=independent_vars,
        dependent_vars=dependent_vars,
        parameters=parameters,
        comments=comments,
    )


def load_parameters(
    json_path: str | Path,
    verified_qubits: list[str] | None = None,
) -> ParamsSnapshot:
    """解析 parameters.json 芯片参数快照。

    Parameters
    ----------
    json_path : str or Path
        JSON 文件路径。
    verified_qubits : list[str] | None
        本次实验已确认有效的比特名称列表。
        对应比特的 ``QubitParams.verified`` 将被设为 True。
        通常由 ``load_experiment()`` 从 INI 中自动提取后传入。

    Returns
    -------
    ParamsSnapshot

    Raises
    ------
    FileNotFoundError
        JSON 文件不存在。
    """
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"Parameters JSON not found: {json_path}")

    with open(json_path, encoding="utf-8") as f:
        raw: dict[str, Any] = json.load(f)

    verified_set = set(verified_qubits or [])

    # === Qubits ===
    qubits: dict[str, QubitParams] = {}
    raw_qubits: dict[str, dict[str, Any]] = raw.get("qubits", {})

    # 已提取到 QubitParams 顶层字段的 JSON key，不重复进入 extras。
    # 其余所有 JSON 字段（pi_drag, gate_zpa, pihalf_amp 等）均保留在 extras 中，
    # 不会丢弃。JSON key → QubitParams attr 对应关系见 QubitParams docstring。
    _EXTRACTED_KEYS = frozenset({
        "f01(GHz)", "f12(GHz)", "pi_amp", "pi_width(ns)",
        "readout_freq(GHz)", "readout_amp(dBm)",
    })
    # Required fields
    _REQUIRED_KEYS = (
        "f01(GHz)",
        "pi_amp",
        "pi_width(ns)",
        "readout_freq(GHz)",
        "readout_amp(dBm)",
    )

    for name, qdata in raw_qubits.items():
        # 检查必需字段
        missing = [k for k in _REQUIRED_KEYS if k not in qdata]
        if missing:
            raise ValueError(
                f"Qubit '{name}' in {json_path} is missing required fields: {missing}"
            )

        extras: dict[str, Any] = {}
        for json_key, val in qdata.items():
            if json_key not in _EXTRACTED_KEYS:
                extras[json_key] = val

        qubits[name] = QubitParams(
            f01=float(qdata["f01(GHz)"]),
            pi_amp=float(qdata["pi_amp"]),
            pi_width=float(qdata["pi_width(ns)"]),
            readout_freq=float(qdata["readout_freq(GHz)"]),
            readout_amp=float(qdata["readout_amp(dBm)"]),
            f12=float(qdata["f12(GHz)"]) if "f12(GHz)" in qdata else None,
            verified=name in verified_set,
            extras=extras,
        )

    # === Couplers ===
    couplers: dict[str, Any] = raw.get("couplers", {})

    # === Readout IQ ===
    readout_iq: dict[str, IQBlobs] = {}
    raw_iq: dict[str, dict[str, Any]] = raw.get("readout_IQ", {})
    for key, iq_data in raw_iq.items():
        centers_raw = iq_data.get("centers", [])
        centers: list[complex] = []
        for c in centers_raw:
            if isinstance(c, str):
                centers.append(_parse_complex(c))
            elif isinstance(c, (int, float)):
                # 纯实数
                centers.append(complex(float(c), 0.0))
            else:
                centers.append(complex(c))

        variance = float(iq_data.get("varis", 0.0))
        n_states = len(centers)
        if n_states not in (2, 3):
            raise ValueError(
                f"readout_IQ '{key}' in {json_path}: "
                f"expected 2 or 3 centers, got {n_states}"
            )

        readout_iq[key] = IQBlobs(
            centers=centers,
            variance=variance,
            n_states=n_states,
        )

    # === Lines ===
    lines: dict[str, dict[str, float]] = {}
    raw_lines: dict[str, dict[str, Any]] = raw.get("lines", {})
    for key, line_data in raw_lines.items():
        lines[key] = {k: float(v) for k, v in line_data.items()}

    return ParamsSnapshot(
        qubits=qubits,
        couplers=couplers,
        readout_iq=readout_iq,
        lines=lines,
    )


def load_csv_with_meta(
    csv_path: str | Path,
    ini_meta: IniMeta,
) -> tuple[np.ndarray, list[ColumnMeta], list[ColumnMeta]]:
    """读取 CSV 数据文件并分割自变量/因变量列。

    Parameters
    ----------
    csv_path : str or Path
        CSV 文件路径。
    ini_meta : IniMeta
        INI 元数据，用于确定列数和分割点。

    Returns
    -------
    tuple[np.ndarray, list[ColumnMeta], list[ColumnMeta]]
        (data, independent_vars, dependent_vars)
        data shape = (n_rows, n_independent + n_dependent)

    Raises
    ------
    FileNotFoundError
        CSV 文件不存在。
    ValueError
        CSV 列数与 INI 声明的列数不匹配。
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    data = np.loadtxt(csv_path, delimiter=",", ndmin=2)

    expected_cols = ini_meta.n_independent + ini_meta.n_dependent
    if data.shape[1] != expected_cols:
        raise ValueError(
            f"Column mismatch in '{csv_path}': "
            f"CSV has {data.shape[1]} columns, "
            f"INI declares {expected_cols} "
            f"({ini_meta.n_independent} independent + {ini_meta.n_dependent} dependent)"
        )

    return data, ini_meta.independent_vars, ini_meta.dependent_vars


def load_experiment(path: str | Path) -> Experiment:
    """加载一次实验的完整数据（CSV + INI + JSON）。

    传入 CSV 或 INI 路径（任其一），自动在同目录下查找同编号的三个文件并解析。

    JSON 参数文件缺失时仅发出警告，``Experiment.params`` 设为 None，
    不抛出异常。

    Parameters
    ----------
    path : str or Path
        CSV 或 INI 文件路径。

    Returns
    -------
    Experiment

    Raises
    ------
    FileNotFoundError
        CSV 或 INI 文件不存在。
    IOError
        INI 解析失败。
    ValueError
        文件类型不支持或列数不匹配。
    """
    csv_path, ini_path, json_path = _find_matching_files(path)

    # === 解析 INI ===
    ini_meta = parse_ini_metadata(ini_path)

    # === 加载 CSV ===
    data, independent_vars, dependent_vars = load_csv_with_meta(csv_path, ini_meta)

    # === 构建 typed settings ===
    settings: dict[str, Any] = {}
    for label, raw_val in ini_meta.parameters.items():
        settings[label] = _parse_ini_value(raw_val)

    # === 加载 JSON (optional) ===
    params: ParamsSnapshot | None = None
    verified_qubits = _extract_verified_qubits(ini_meta)

    if json_path is not None:
        params = load_parameters(json_path, verified_qubits=verified_qubits)
    else:
        import warnings

        warnings.warn(
            f"[警告] 未找到 {ini_meta.title} 的 parameters.json（实验编号 {_extract_exp_id(path)}），"
            f"参数快照将为空"
        )

    return Experiment(
        exp_id=_extract_exp_id(path),
        title=ini_meta.title,
        timestamp=ini_meta.created,
        independent_vars=independent_vars,
        dependent_vars=dependent_vars,
        data=data,
        params=params,
        settings=settings,
        source_dir=csv_path.parent,
        csv_path=csv_path,
        ini_path=ini_path,
        json_path=json_path,
    )
