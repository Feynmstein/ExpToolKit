"""芯片参数累积状态管理 — ChipState + QubitState + 条目数据类。

提供 chip_state.json 的读写接口。拟合模块不直接写入 State — 用户手动控制保存。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from exp_toolkit.visualization.chip_plot import ChipTopology

__all__ = [
    "ParameterEntry",
    "CoherenceEntry",
    "CoherenceGroup",
    "DriveEntry",
    "ReadoutEntry",
    "F01Range",
    "QubitState",
    "ChipState",
]


# =============================================================================
# Entry Data Classes
# =============================================================================


@dataclass
class ParameterEntry:
    """单次参数测量值（T1, T2*, T2echo 等标量参数）。

    Attributes
    ----------
    value : float
        测量值。
    error : float or None
        1σ 标准误差。
    freq_GHz : float
        测量时的比特（或读取）频率 (GHz)。
    timestamp : str
        测量日期，格式 "YYYY-MM-DD"。
    source_exp : str
        实验编号。
    """

    value: float
    error: float | None
    freq_GHz: float
    timestamp: str
    source_exp: str


@dataclass
class CoherenceEntry:
    """coherence 组内的单个参数测量值（T1 / T2* / T2echo）。

    每个 CoherenceEntry 有独立的 source_exp，因为同一频率下的
    T1、T2*、T2echo 可能由不同实验测量得到。

    Attributes
    ----------
    value : float
        测量值。
    error : float or None
        1σ 标准误差。
    source_exp : str
        实验编号。
    """

    value: float
    error: float | None
    source_exp: str


@dataclass
class CoherenceGroup:
    """同一比特频率下的一组 coherence 测量。

    将同频率下的 T1、T2*、T2echo 归为一组，体现物理上
    "同一工作点"的语义关联。各组独立维护时间戳。

    Attributes
    ----------
    freq_GHz : float
        比特频率 (GHz) — 归组键。
    timestamp : str
        组最后更新时间，格式 "YYYY-MM-DD"。
    T1_us : CoherenceEntry or None
    T2star_us : CoherenceEntry or None
    T2echo_us : CoherenceEntry or None
    """

    freq_GHz: float
    timestamp: str
    T1_us: CoherenceEntry | None = None
    T2star_us: CoherenceEntry | None = None
    T2echo_us: CoherenceEntry | None = None


@dataclass
class DriveEntry:
    """驱动效率条目 — 1/(π 脉冲面积) = 1/(pi_amp × pi_width_ns)。

    Attributes
    ----------
    pi_amp : float
        π 脉冲幅度。
    pi_width_ns : float
        π 脉冲宽度 (ns)。
    freq_GHz : float
        测量时的比特频率 (GHz)。
    timestamp : str
    source_exp : str

    Notes
    -----
    ``product`` 是计算属性（1/(pi_amp × pi_width_ns)），
    不会持久化到 JSON。
    """

    pi_amp: float
    pi_width_ns: float
    freq_GHz: float
    timestamp: str
    source_exp: str

    @property
    def product(self) -> float:
        """驱动效率：1.0 / (pi_amp * pi_width_ns)。"""
        return 1.0 / (self.pi_amp * self.pi_width_ns)


@dataclass
class ReadoutEntry:
    """读取保真度条目。

    Attributes
    ----------
    F0 : float
        |0⟩→|0⟩ 保真度。
    F1 : float
        |1⟩→|1⟩ 保真度。
    avg : float
        平均读取保真度。
    freq_GHz : float
        读取频率 (GHz)。
    timestamp : str
    source_exp : str
    """

    F0: float
    F1: float
    avg: float
    freq_GHz: float
    timestamp: str
    source_exp: str


@dataclass
class F01Range:
    """f01 频率范围，来自 f01 dispersion 拟合。

    Attributes
    ----------
    min : float
        f01 最小值 (GHz)。
    max : float
        f01 最大值 (GHz)。
    source_exp : str
        来源实验编号。
    """

    min: float
    max: float
    source_exp: str


# =============================================================================
# QubitState
# =============================================================================


@dataclass
class QubitState:
    """单个比特的累积参数状态。

    Attributes
    ----------
    f01_GHz : F01Range or None
    coherence : list[CoherenceGroup]
        按频率分组的 coherence 测量（T1 / T2* / T2echo）。
    drive_efficiency : list[DriveEntry]
    readout_fidelity : list[ReadoutEntry]

    Notes
    -----
    ``T1_us`` / ``T2star_us`` / ``T2echo_us`` 是向后兼容的计算属性，
    从 ``coherence`` 组中展平并按时间戳排序返回。
    """

    f01_GHz: F01Range | None = None
    coherence: list[CoherenceGroup] = field(default_factory=list)
    drive_efficiency: list[DriveEntry] = field(default_factory=list)
    readout_fidelity: list[ReadoutEntry] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    # ---- backward-compat coherence flattening ----

    @property
    def T1_us(self) -> list[ParameterEntry]:
        """向后兼容：从 coherence 组展平 T1 条目，按时间戳排序。"""
        result: list[ParameterEntry] = []
        for g in self.coherence:
            if g.T1_us is not None:
                result.append(ParameterEntry(
                    value=g.T1_us.value,
                    error=g.T1_us.error,
                    freq_GHz=g.freq_GHz,
                    timestamp=g.timestamp,
                    source_exp=g.T1_us.source_exp,
                ))
        result.sort(key=lambda e: e.timestamp)
        return result

    @property
    def T2star_us(self) -> list[ParameterEntry]:
        """向后兼容：从 coherence 组展平 T2* 条目，按时间戳排序。"""
        result: list[ParameterEntry] = []
        for g in self.coherence:
            if g.T2star_us is not None:
                result.append(ParameterEntry(
                    value=g.T2star_us.value,
                    error=g.T2star_us.error,
                    freq_GHz=g.freq_GHz,
                    timestamp=g.timestamp,
                    source_exp=g.T2star_us.source_exp,
                ))
        result.sort(key=lambda e: e.timestamp)
        return result

    @property
    def T2echo_us(self) -> list[ParameterEntry]:
        """向后兼容：从 coherence 组展平 T2echo 条目，按时间戳排序。"""
        result: list[ParameterEntry] = []
        for g in self.coherence:
            if g.T2echo_us is not None:
                result.append(ParameterEntry(
                    value=g.T2echo_us.value,
                    error=g.T2echo_us.error,
                    freq_GHz=g.freq_GHz,
                    timestamp=g.timestamp,
                    source_exp=g.T2echo_us.source_exp,
                ))
        result.sort(key=lambda e: e.timestamp)
        return result


# =============================================================================
# ChipState
# =============================================================================


class ChipState:
    """芯片参数累积状态管理器。

    提供 chip_state.json 的读写，以及各参数类型的 add 方法。
    所有 add_*() 方法追加到对应列表，不覆盖历史值。

    Examples
    --------
    >>> topo = ChipTopology.from_grid(5, 5)
    >>> state = ChipState.new("chip-001", topo)
    >>> state.add_T1("Q16", value=45.2, error=1.3, freq_GHz=4.71, source_exp="00747")
    >>> state.save("chip_state.json")
    """

    def __init__(
        self,
        chip_id: str,
        topology: ChipTopology,
        qubits: dict[str, QubitState] | None = None,
        last_updated: str | None = None,
    ) -> None:
        self.chip_id = chip_id
        self.topology = topology
        self._qubits: dict[str, QubitState] = qubits or {}
        self.last_updated: str | None = last_updated

        # Ensure all topology qubits have an entry
        for name in topology.qubit_names:
            if name not in self._qubits:
                self._qubits[name] = QubitState()

    @classmethod
    def new(cls, chip_id: str, topology: ChipTopology) -> "ChipState":
        """创建空的芯片状态。

        Parameters
        ----------
        chip_id : str
            芯片标识符。
        topology : ChipTopology
            芯片拓扑。

        Returns
        -------
        ChipState
        """
        return cls(chip_id=chip_id, topology=topology)

    @classmethod
    def load(cls, path: str | Path) -> "ChipState":
        """从 chip_state.json 加载芯片状态。

        Parameters
        ----------
        path : str or Path
            JSON 文件路径。

        Returns
        -------
        ChipState
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"ChipState JSON not found: {path}")

        with open(path, encoding="utf-8") as f:
            raw: dict[str, Any] = json.load(f)

        # Topology（新格式完整序列化，旧格式 from_grid 兼容）
        topo_raw = raw.get("topology", {})
        tp = ChipTopology.from_dict(topo_raw)

        # Qubits
        qubits: dict[str, QubitState] = {}
        for qname, qdata in raw.get("qubits", {}).items():
            qs = QubitState()

            # f01
            if "f01_GHz" in qdata and qdata["f01_GHz"] is not None:
                fd = qdata["f01_GHz"]
                qs.f01_GHz = F01Range(
                    min=fd["min"],
                    max=fd["max"],
                    source_exp=fd.get("source_exp", ""),
                )

            # coherence (grouped by freq_GHz)
            for group_data in qdata.get("coherence", []):
                group = CoherenceGroup(
                    freq_GHz=group_data["freq_GHz"],
                    timestamp=group_data.get("timestamp", ""),
                )
                for param_key in ("T1_us", "T2star_us", "T2echo_us"):
                    entry_data = group_data.get(param_key)
                    if entry_data is not None:
                        setattr(group, param_key, CoherenceEntry(
                            value=entry_data["value"],
                            error=entry_data.get("error"),
                            source_exp=entry_data.get("source_exp", ""),
                        ))
                qs.coherence.append(group)

            # drive_efficiency
            for entry in qdata.get("drive_efficiency", []):
                qs.drive_efficiency.append(DriveEntry(
                    pi_amp=entry["pi_amp"],
                    pi_width_ns=entry["pi_width_ns"],
                    freq_GHz=entry["freq_GHz"],
                    timestamp=entry["timestamp"],
                    source_exp=entry["source_exp"],
                ))

            # readout_fidelity
            for entry in qdata.get("readout_fidelity", []):
                qs.readout_fidelity.append(ReadoutEntry(
                    F0=entry["F0"], F1=entry["F1"],
                    avg=entry["avg"],
                    freq_GHz=entry["freq_GHz"],
                    timestamp=entry["timestamp"],
                    source_exp=entry["source_exp"],
                ))

            # extras (compatible with old JSON missing the key)
            qs.extras = qdata.get("extras", {})

            qubits[qname] = qs

        return cls(
            chip_id=raw.get("chip_id", "unknown"),
            topology=tp,
            qubits=qubits,
            last_updated=raw.get("last_updated"),
        )

    def save(self, path: str | Path) -> None:
        """保存芯片状态到 chip_state.json。

        Parameters
        ----------
        path : str or Path
            输出文件路径。
        """
        path = Path(path)

        # qubits → JSON-serializable
        qubits_json: dict[str, Any] = {}
        for qname, qs in sorted(self._qubits.items()):
            qj: dict[str, Any] = {}

            if qs.f01_GHz is not None:
                qj["f01_GHz"] = {
                    "min": qs.f01_GHz.min,
                    "max": qs.f01_GHz.max,
                    "source_exp": qs.f01_GHz.source_exp,
                }

            if qs.coherence:
                qj["coherence"] = []
                for group in qs.coherence:
                    gd: dict[str, Any] = {
                        "freq_GHz": group.freq_GHz,
                        "timestamp": group.timestamp,
                    }
                    for param_key in ("T1_us", "T2star_us", "T2echo_us"):
                        entry = getattr(group, param_key)
                        if entry is not None:
                            gd[param_key] = {
                                "value": entry.value,
                                "error": entry.error,
                                "source_exp": entry.source_exp,
                            }
                        else:
                            gd[param_key] = None
                    qj["coherence"].append(gd)

            if qs.drive_efficiency:
                qj["drive_efficiency"] = [
                    {"pi_amp": e.pi_amp, "pi_width_ns": e.pi_width_ns,
                     "freq_GHz": e.freq_GHz,
                     "timestamp": e.timestamp, "source_exp": e.source_exp}
                    for e in qs.drive_efficiency
                ]

            if qs.readout_fidelity:
                qj["readout_fidelity"] = [
                    {"F0": e.F0, "F1": e.F1, "avg": e.avg,
                     "freq_GHz": e.freq_GHz,
                     "timestamp": e.timestamp, "source_exp": e.source_exp}
                    for e in qs.readout_fidelity
                ]

            if qs.extras:
                qj["extras"] = qs.extras

            qubits_json[qname] = qj

        output: dict[str, Any] = {
            "chip_id": self.chip_id,
            "topology": self.topology.to_dict(),
            "last_updated": self.last_updated or date.today().isoformat(),
            "qubits": qubits_json,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    # ---- add_*() methods ----

    def _ensure_qubit(self, name: str) -> QubitState:
        if name not in self._qubits:
            self._qubits[name] = QubitState()
        return self._qubits[name]

    def _today(self) -> str:
        return date.today().isoformat()

    def add_T1(
        self,
        qubit: str,
        value: float,
        error: float | None,
        freq_GHz: float,
        source_exp: str,
        timestamp: str | None = None,
    ) -> None:
        """添加 T1 测量值，按 freq_GHz 自动归组。

        查找同频率的已有 CoherenceGroup，将 T1_us 写入该组；
        若不存在同频率组则创建新组。
        同频率重复调用会覆盖 T1_us 值。
        """
        qs = self._ensure_qubit(qubit)
        ts = timestamp or self._today()
        entry = CoherenceEntry(value=value, error=error, source_exp=source_exp)

        for group in qs.coherence:
            if group.freq_GHz == freq_GHz:
                group.T1_us = entry
                group.timestamp = ts
                return

        qs.coherence.append(CoherenceGroup(
            freq_GHz=freq_GHz, timestamp=ts, T1_us=entry,
        ))

    def add_T2star(
        self,
        qubit: str,
        value: float,
        error: float | None,
        freq_GHz: float,
        source_exp: str,
        timestamp: str | None = None,
    ) -> None:
        """添加 T2* 测量值，按 freq_GHz 自动归组。

        查找同频率的已有 CoherenceGroup，将 T2star_us 写入该组；
        若不存在同频率组则创建新组。
        同频率重复调用会覆盖 T2star_us 值。
        """
        qs = self._ensure_qubit(qubit)
        ts = timestamp or self._today()
        entry = CoherenceEntry(value=value, error=error, source_exp=source_exp)

        for group in qs.coherence:
            if group.freq_GHz == freq_GHz:
                group.T2star_us = entry
                group.timestamp = ts
                return

        qs.coherence.append(CoherenceGroup(
            freq_GHz=freq_GHz, timestamp=ts, T2star_us=entry,
        ))

    def add_T2echo(
        self,
        qubit: str,
        value: float,
        error: float | None,
        freq_GHz: float,
        source_exp: str,
        timestamp: str | None = None,
    ) -> None:
        """添加 T2 echo 测量值，按 freq_GHz 自动归组。

        查找同频率的已有 CoherenceGroup，将 T2echo_us 写入该组；
        若不存在同频率组则创建新组。
        同频率重复调用会覆盖 T2echo_us 值。
        """
        qs = self._ensure_qubit(qubit)
        ts = timestamp or self._today()
        entry = CoherenceEntry(value=value, error=error, source_exp=source_exp)

        for group in qs.coherence:
            if group.freq_GHz == freq_GHz:
                group.T2echo_us = entry
                group.timestamp = ts
                return

        qs.coherence.append(CoherenceGroup(
            freq_GHz=freq_GHz, timestamp=ts, T2echo_us=entry,
        ))

    def add_f01_range(
        self,
        qubit: str,
        f01_min: float,
        f01_max: float,
        source_exp: str,
    ) -> None:
        """设置 f01 频率范围（覆盖之前的值）。"""
        qs = self._ensure_qubit(qubit)
        qs.f01_GHz = F01Range(min=f01_min, max=f01_max, source_exp=source_exp)

    def add_drive_efficiency(
        self,
        qubit: str,
        pi_amp: float,
        pi_width_ns: float,
        freq_GHz: float,
        source_exp: str,
        timestamp: str | None = None,
    ) -> None:
        """添加驱动效率测量值。product 由 DriveEntry 自动计算。"""
        qs = self._ensure_qubit(qubit)
        qs.drive_efficiency.append(DriveEntry(
            pi_amp=pi_amp,
            pi_width_ns=pi_width_ns,
            freq_GHz=freq_GHz,
            timestamp=timestamp or self._today(),
            source_exp=source_exp,
        ))

    def add_readout_fidelity(
        self,
        qubit: str,
        F0: float,
        F1: float,
        avg: float,
        freq_GHz: float,
        source_exp: str,
        timestamp: str | None = None,
    ) -> None:
        """添加读取保真度测量值。"""
        qs = self._ensure_qubit(qubit)
        qs.readout_fidelity.append(ReadoutEntry(
            F0=F0, F1=F1, avg=avg,
            freq_GHz=freq_GHz,
            timestamp=timestamp or self._today(),
            source_exp=source_exp,
        ))

    def set_extras(self, qubit: str, **kwargs: Any) -> None:
        """Set extra qubit properties (e.g. readout_cavity_response, bias_tunable).

        Existing keys not in *kwargs* are preserved.
        Values must be JSON-serializable (bool, str, float, int).

        Parameters
        ----------
        qubit : str
            Qubit name.
        **kwargs : Any
            Key-value pairs to merge into the qubit's extras dict.
        """
        qs = self._ensure_qubit(qubit)
        qs.extras.update(kwargs)

    # ---- query methods ----

    def get_qubit(self, name: str) -> QubitState:
        """获取某比特的参数状态。

        Raises
        ------
        KeyError
            比特不存在。
        """
        if name not in self._qubits:
            raise KeyError(f"Qubit '{name}' not in chip state")
        return self._qubits[name]

    def get_latest(
        self, name: str, param: str
    ) -> ParameterEntry | DriveEntry | ReadoutEntry | F01Range | None:
        """获取某比特某参数的最新测量条目。

        Parameters
        ----------
        name : str
            比特名称。
        param : str
            参数名: "T1", "T2star", "T2echo", "drive_efficiency",
            "readout_fidelity", "f01".

        Returns
        -------
        ParameterEntry / DriveEntry / ReadoutEntry / F01Range / None
        """
        qs = self.get_qubit(name)
        entries: list[Any]
        if param in ("T1", "T1_us"):
            entries = qs.T1_us
        elif param in ("T2star", "T2star_us"):
            entries = qs.T2star_us
        elif param in ("T2echo", "T2echo_us"):
            entries = qs.T2echo_us
        elif param == "drive_efficiency":
            entries = qs.drive_efficiency
        elif param == "readout_fidelity":
            entries = qs.readout_fidelity
        elif param in ("f01", "f01_GHz"):
            return qs.f01_GHz
        else:
            raise ValueError(f"Unknown parameter: '{param}'")

        if not entries:
            return None
        # 列表按添加顺序排列，最后添加的即为最新
        return entries[-1]

    def list_measured_qubits(self) -> list[str]:
        """列出至少有一条参数数据的比特名称。

        Returns
        -------
        list[str]
        """
        measured: list[str] = []
        for name, qs in sorted(self._qubits.items()):
            if (qs.f01_GHz is not None
                    or qs.coherence
                    or qs.drive_efficiency
                    or qs.readout_fidelity):
                measured.append(name)
        return measured

    @property
    def qubits(self) -> dict[str, QubitState]:
        """全部比特状态字典。"""
        return dict(self._qubits)
