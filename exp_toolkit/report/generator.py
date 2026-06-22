"""芯片状态 HTML 报告生成器 — 自包含 HTML 文件，用于组会展示。

Usage:
    state = ChipState.load("chip_state.json")
    gen = ReportGenerator(state)
    gen.generate("report.html", title="5×5 Chip Status — June 2026")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from exp_toolkit.state.chip_state import ChipState
from exp_toolkit.visualization.chip_plot import ChipArtist

__all__ = ["ReportGenerator"]

# ---------------------------------------------------------------------------
# CSS 模板（内联，无外部依赖）
# ---------------------------------------------------------------------------

_CSS = """\
:root {
    --bg: #fafafa;
    --card-bg: #ffffff;
    --text: #333333;
    --muted: #888888;
    --border: #e0e0e0;
    --accent: #4C72B0;
    --radius: 6px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 20px;
}
header {
    text-align: center;
    margin-bottom: 30px;
}
header h1 {
    font-size: 1.8em;
    font-weight: 600;
    margin-bottom: 4px;
}
header .meta {
    font-size: 0.9em;
    color: var(--muted);
}
section {
    margin-bottom: 36px;
}
section h2 {
    font-size: 1.25em;
    font-weight: 600;
    border-bottom: 2px solid var(--accent);
    padding-bottom: 6px;
    margin-bottom: 16px;
}
figure {
    text-align: center;
    margin: 0;
}
figure svg {
    max-width: 100%;
    height: auto;
}
figcaption {
    text-align: center;
    font-weight: 600;
    margin-bottom: 8px;
    font-size: 0.95em;
}
.yield-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 20px;
    margin-bottom: 24px;
}
.yield-row figure {
    flex: 0 1 auto;
    min-width: 260px;
    max-width: 380px;
}
.coherence-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 20px;
    margin-bottom: 24px;
}
.coherence-row figure {
    flex: 0 1 auto;
    min-width: 260px;
    max-width: 380px;
}
.qubit-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 16px;
}
.qubit-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    overflow-x: auto;
}
.qubit-card h3 {
    font-size: 1.05em;
    font-weight: 600;
    color: var(--accent);
    margin-bottom: 10px;
}
.qubit-card table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85em;
}
.qubit-card th, .qubit-card td {
    text-align: left;
    padding: 3px 6px;
    border-bottom: 1px solid var(--border);
}
.qubit-card th {
    color: var(--muted);
    font-weight: 500;
    white-space: nowrap;
}
.qubit-card td.value {
    font-weight: 500;
    white-space: nowrap;
}
.qubit-card td.src {
    font-size: 0.8em;
    color: var(--muted);
}
.qubit-card td.missing { color: #cc6666; font-style: italic; }
.qubit-card th.sub {
    padding-left: 16px;
    font-weight: 400;
    color: var(--muted);
    font-size: 0.9em;
}
.qubit-card thead th {
    font-weight: 600;
    color: #333;
    border-bottom: 2px solid var(--border);
    font-size: 0.8em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.unmeasured-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.unmeasured-chip {
    display: inline-block;
    background: #e8e8e8;
    color: #999;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 0.82em;
    font-family: monospace;
}
table.sources {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9em;
}
table.sources th {
    text-align: center;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border);
    background: #f0f0f0;
    font-weight: 600;
}
table.sources td {
    text-align: left;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border);
}
table.sources td.check { text-align: center; color: var(--accent); }
table.sources td.empty { text-align: center; color: #ccc; }
table.sources td.src-col { text-align: center; }
table.sources td.qubits-col { text-align: center; }
"""

# ---------------------------------------------------------------------------
# HTML 骨架
# ---------------------------------------------------------------------------

_HTML_SKELETON = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{css}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <p class="meta">Chip ID: {chip_id} &middot; Updated: {last_updated}</p>
</header>
<main>
{sections_html}
</main>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Section templates
# ---------------------------------------------------------------------------

_MEASURED_SECTION_HEADER = """\
<section id="qubits">
<h2>{section_num}. Measured Qubits ({count})</h2>
<div class="qubit-grid">"""

_MEASURED_SECTION_FOOTER = """\
</div>
</section>"""

_UNMEASURED_SECTION = """\
<section id="unmeasured">
<h2>{section_num}. Unmeasured Qubits ({count})</h2>
<div class="unmeasured-list">
{chips}
</div>
</section>"""

_SOURCES_SECTION = """\
<section id="sources">
<h2>{section_num}. Data Sources</h2>
<table class="sources">
<thead><tr>
  <th>Source Exp</th>
  <th>Qubits</th>
  <th>T1</th>
  <th>T2*</th>
  <th>T2 echo</th>
  <th>f01</th>
  <th>Readout</th>
  <th>Drive Eff</th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>
</section>"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COLORMAP_LABELS = {
    "f01": "f01 max (GHz)",
    "T1": "T1 (μs)",
    "T2star": "T2* (μs)",
    "T2echo": "T2 echo (μs)",
    "drive_efficiency": "Drive Efficiency (a.u.)",
    "readout_fidelity": "Readout Fidelity",
}

_COLORMAP_UNITS = {
    "f01": "GHz",
    "T1": "μs",
    "T2star": "μs",
    "T2echo": "μs",
    "drive_efficiency": "",
    "readout_fidelity": "",
}

# Yield params: (key, label) pairs defining display order and labels.
# _YIELD_PARAMS, _YIELD_ORDER, _YIELD_LABELS are derived below.
_YIELD_SPEC = [
    ("measureable",               "Measurable"),
    ("readout_cavity_response",   "Readout Cavity"),
    ("bias_tunable",              "Bias Tunable"),
]
_YIELD_PARAMS = {key for key, _ in _YIELD_SPEC}
_YIELD_ORDER = [key for key, _ in _YIELD_SPEC]
_YIELD_LABELS = dict(_YIELD_SPEC)


def _normalize_values(values: dict[str, float]) -> dict[str, float]:
    """归一化到 [0, 1]，除以最大值。全零或空 dict 返回原值。"""
    if not values:
        return {}
    max_val = max(values.values())
    if max_val == 0.0:
        return values
    return {k: v / max_val for k, v in values.items()}


def _get_annotate_values(
    state: ChipState, fields: list[str],
) -> dict[str, dict[str, Any]]:
    """Extract annotation values from built-in params and extras.

    Parameters
    ----------
    state : ChipState
    fields : list[str]
        Field names: built-in (f01, f01_max, f01_min, T1, T2star, T2echo,
        drive_efficiency, readout_fidelity) or extras keys.

    Returns
    -------
    dict[str, dict[str, Any]]
        qubit_name → {field: value}.
    """
    result: dict[str, dict[str, Any]] = {}
    for name in state.list_measured_qubits():
        qs = state.get_qubit(name)
        field_vals: dict[str, Any] = {}
        for field in fields:
            if field == "f01" and qs.f01_GHz is not None:
                field_vals[field] = qs.f01_GHz.max
            elif field == "f01_max" and qs.f01_GHz is not None:
                field_vals[field] = qs.f01_GHz.max
            elif field == "f01_min" and qs.f01_GHz is not None:
                field_vals[field] = qs.f01_GHz.min
            elif field == "T1" and qs.T1_us:
                field_vals[field] = qs.T1_us[-1].value
            elif field == "T2star" and qs.T2star_us:
                field_vals[field] = qs.T2star_us[-1].value
            elif field == "T2echo" and qs.T2echo_us:
                field_vals[field] = qs.T2echo_us[-1].value
            elif field == "drive_efficiency" and qs.drive_efficiency:
                field_vals[field] = qs.drive_efficiency[-1].product
            elif field == "readout_fidelity" and qs.readout_fidelity:
                field_vals[field] = qs.readout_fidelity[-1].avg
            elif field in qs.extras:
                field_vals[field] = qs.extras[field]
        if field_vals:
            result[name] = field_vals
    return result


def _get_colormap_values(state: ChipState, param: str) -> dict[str, float]:
    """Extract {qubit_name: value} dict for colormap.

    Supports built-in params (f01, T1, T2star, T2echo, drive_efficiency,
    readout_fidelity) and numeric extras keys.
    """
    values: dict[str, float] = {}
    for name in state.list_measured_qubits():
        qs = state.get_qubit(name)
        if param == "f01":
            if qs.f01_GHz is not None:
                values[name] = qs.f01_GHz.max
        elif param == "T1":
            if qs.T1_us:
                values[name] = qs.T1_us[-1].value
        elif param == "T2star":
            if qs.T2star_us:
                values[name] = qs.T2star_us[-1].value
        elif param == "T2echo":
            if qs.T2echo_us:
                values[name] = qs.T2echo_us[-1].value
        elif param == "drive_efficiency":
            if qs.drive_efficiency:
                values[name] = qs.drive_efficiency[-1].product
        elif param == "readout_fidelity":
            if qs.readout_fidelity:
                values[name] = qs.readout_fidelity[-1].avg
        else:
            # Fallback: extras numeric fields
            val = qs.extras.get(param)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                values[name] = float(val)
    return values


def _fmt_val(value: float, error: float | None, unit: str) -> str:
    """Format value ± error with unit."""
    if error is not None:
        return f"{value:.3f} ± {error:.3f} {unit}"
    return f"{value:.3f} {unit}"


def _fmt_src(source_exp: str) -> str:
    """Format source experiment as a small tag."""
    return f'<span class="src">({source_exp})</span>'


def _make_param_row(label: str, value_str: str, freq: float | None, src: str) -> str:
    """Render a single parameter row in a qubit card."""
    freq_str = f"{freq:.3f} GHz" if freq is not None else "&mdash;"
    return (
        f'<tr><th>{label}</th>'
        f'<td class="value">{value_str}</td>'
        f'<td>@ {freq_str}</td>'
        f'<td class="src">{_fmt_src(src)}</td></tr>'
    )


def _make_missing_row(label: str) -> str:
    """Render a 'No data' row for a missing parameter."""
    return (
        f'<tr><th>{label}</th>'
        f'<td class="missing" colspan="3">No data</td></tr>'
    )


def _make_sub_row(label: str, value_str: str) -> str:
    """Render a sub-parameter row (indented label, empty freq/src columns)."""
    return (
        f'<tr><th class="sub">{label}</th>'
        f'<td class="value">{value_str}</td>'
        f'<td></td><td></td></tr>'
    )


def _build_qubit_card(name: str, state: ChipState) -> str:
    """Build HTML card for one measured qubit.

    Always renders all 6 fixed parameter rows (f01, T1, T2*, T2 echo,
    Drive Eff, Readout). Missing parameters show "No data".
    Extras bool flags are shown at the bottom as "Yes"/"No".
    """
    qs = state.get_qubit(name)
    rows: list[str] = []

    # --- 6 fixed parameter rows ---

    # f01 range
    if qs.f01_GHz is not None:
        f01 = qs.f01_GHz
        val = f"{f01.min:.3f}–{f01.max:.3f} GHz"
        rows.append(
            f'<tr><th>f01</th>'
            f'<td class="value">{val}</td>'
            f'<td></td>'
            f'<td class="src">{_fmt_src(f01.source_exp)}</td></tr>'
        )
    else:
        rows.append(_make_missing_row("f01"))

    # T1
    if qs.T1_us:
        entry = qs.T1_us[-1]
        rows.append(_make_param_row(
            "T1", _fmt_val(entry.value, entry.error, "μs"),
            entry.freq_GHz, entry.source_exp,
        ))
    else:
        rows.append(_make_missing_row("T1"))

    # T2*
    if qs.T2star_us:
        entry = qs.T2star_us[-1]
        rows.append(_make_param_row(
            "T2*", _fmt_val(entry.value, entry.error, "μs"),
            entry.freq_GHz, entry.source_exp,
        ))
    else:
        rows.append(_make_missing_row("T2*"))

    # T2 echo
    if qs.T2echo_us:
        entry = qs.T2echo_us[-1]
        rows.append(_make_param_row(
            "T2 echo", _fmt_val(entry.value, entry.error, "μs"),
            entry.freq_GHz, entry.source_exp,
        ))
    else:
        rows.append(_make_missing_row("T2 echo"))

    # drive efficiency — split into 3 rows
    if qs.drive_efficiency:
        entry = qs.drive_efficiency[-1]
        rows.append(_make_param_row(
            "Drive Eff", f"{entry.product:.3f}",
            entry.freq_GHz, entry.source_exp,
        ))
        rows.append(_make_sub_row("π-amp", f"{entry.pi_amp:.3f}"))
        rows.append(_make_sub_row("π-width", f"{entry.pi_width_ns:.1f} ns"))
    else:
        rows.append(_make_missing_row("Drive Eff"))

    # readout fidelity — split into 3 rows
    if qs.readout_fidelity:
        entry = qs.readout_fidelity[-1]
        rows.append(_make_param_row(
            "Readout", f"{entry.avg:.4f}",
            entry.freq_GHz, entry.source_exp,
        ))
        rows.append(_make_sub_row("F0", f"{entry.F0:.4f}"))
        rows.append(_make_sub_row("F1", f"{entry.F1:.4f}"))
    else:
        rows.append(_make_missing_row("Readout"))

    # --- extras flags ---
    if qs.extras:
        for key, val in sorted(qs.extras.items()):
            if isinstance(val, bool):
                display = "Yes" if val else "No"
            else:
                display = str(val)
            rows.append(
                f'<tr><th>{key}</th>'
                f'<td class="value">{display}</td>'
                f'<td></td><td></td></tr>'
            )

    header = (
        '<thead><tr>'
        '<th>Parameter</th><th>Value</th><th>Frequency</th><th>Source</th>'
        '</tr></thead>'
    )
    table = f'<table>{header}<tbody>{"".join(rows)}</tbody></table>'
    return f'<div class="qubit-card"><h3>{name}</h3>{table}</div>'


def _build_sources_table(state: ChipState) -> str:
    """Build data sources summary table."""
    # Collect source_exp → set of parameter types per qubit
    sources: dict[str, dict[str, set[str]]] = {}  # source → {qubit: {param_types}}

    for name in state.list_measured_qubits():
        qs = state.get_qubit(name)

        if qs.f01_GHz is not None:
            src = qs.f01_GHz.source_exp
            sources.setdefault(src, {}).setdefault(name, set()).add("f01")

        for entry in qs.T1_us:
            sources.setdefault(entry.source_exp, {}).setdefault(name, set()).add("T1")

        for entry in qs.T2star_us:
            sources.setdefault(entry.source_exp, {}).setdefault(name, set()).add("T2*")

        for entry in qs.T2echo_us:
            sources.setdefault(entry.source_exp, {}).setdefault(name, set()).add("T2e")

        for entry in qs.drive_efficiency:
            sources.setdefault(entry.source_exp, {}).setdefault(name, set()).add("DE")

        for entry in qs.readout_fidelity:
            sources.setdefault(entry.source_exp, {}).setdefault(name, set()).add("RO")

    # Render rows
    rows: list[str] = []
    for src in sorted(sources.keys()):
        qubits_map = sources[src]
        qubit_names = sorted(qubits_map.keys())
        qubits_str = ", ".join(qubit_names)

        has_T1 = any("T1" in params for params in qubits_map.values())
        has_T2s = any("T2*" in params for params in qubits_map.values())
        has_T2e = any("T2e" in params for params in qubits_map.values())
        has_f01 = any("f01" in params for params in qubits_map.values())
        has_RO = any("RO" in params for params in qubits_map.values())
        has_DE = any("DE" in params for params in qubits_map.values())

        mk = lambda b: '<td class="check">✓</td>' if b else '<td class="empty">—</td>'
        rows.append(
            f'<tr><td class="src-col">{src}</td><td class="qubits-col">{qubits_str}</td>'
            f'{mk(has_T1)}{mk(has_T2s)}{mk(has_T2e)}{mk(has_f01)}{mk(has_RO)}{mk(has_DE)}</tr>'
        )

    return "\n".join(rows)


# ---------------------------------------------------------------------------
# ReportGenerator
# ---------------------------------------------------------------------------


class ReportGenerator:
    """芯片状态 HTML 报告生成器。

    Parameters
    ----------
    state : ChipState
        芯片参数累积状态（含 topology）。

    Examples
    --------
    >>> state = ChipState.load("chip_state.json")
    >>> gen = ReportGenerator(state)
    >>> gen.generate("report.html", title="5×5 Chip Status")
    """

    def __init__(self, state: ChipState) -> None:
        self._state = state

    def generate(
        self,
        output_path: str | Path,
        *,
        title: str | None = None,
        sections: list[str] | None = None,
        topology_params: list[str] | None = None,
    ) -> Path:
        """生成自包含 HTML 报告。

        Parameters
        ----------
        output_path : str or Path
            输出文件路径。
        title : str or None
            报告标题，默认 "Chip Report — {chip_id}"。
        sections : list[str] or None
            包含的节。可选: ``"overview"``, ``"qubits"``, ``"unmeasured"``,
            ``"sources"``。为 None 时包含全部。
        topology_params : list[str] or None
            拓扑图参数列表。每参数生成一张独立拓扑图。
            内置参数: ``"f01"``, ``"T1"``, ``"T2star"``, ``"T2echo"``,
            ``"drive_efficiency"``, ``"readout_fidelity"``。
            也支持 extras 中的数值/布尔字段名。
            为 None 时自动检测所有可用参数。

        Returns
        -------
        Path
            生成的文件路径。

        Raises
        ------
        ValueError
            若 topology_params 中的名称不合法或 sections 中的名称不合法。
        """
        output_path = Path(output_path)

        # Resolve topology_params: auto-detect or validate user-provided
        all_params = self._get_all_topology_params()
        if topology_params is None:
            topology_params = all_params
        else:
            for p in topology_params:
                if p not in all_params:
                    raise ValueError(
                        f"Invalid topology_param '{p}'. "
                        f"Choose from: {sorted(all_params)}"
                    )

        valid_sections = {"overview", "qubits", "unmeasured", "sources"}
        if sections is not None:
            for s in sections:
                if s not in valid_sections:
                    raise ValueError(
                        f"Invalid section '{s}'. "
                        f"Choose from: {sorted(valid_sections)}"
                    )

        title = title or f"Chip Report — {self._state.chip_id}"

        # Separate yield params from topology params
        other_params = [p for p in topology_params if p not in _YIELD_PARAMS]

        # Build requested section HTML with dynamic numbering
        sections_html_parts: list[str] = []
        active = set(sections) if sections is not None else valid_sections
        n = 1  # section counter

        # Yield section — always rendered (fixed, regardless of data presence)
        if "overview" in active:
            sections_html_parts.append(self._build_yield(section_num=n))
            n += 1

        if "overview" in active and other_params:
            sections_html_parts.append(
                self._build_overview(other_params, section_num=n)
            )
            n += 1

        if "qubits" in active:
            sections_html_parts.append(self._build_measured_qubits(section_num=n))
            n += 1
        if "unmeasured" in active:
            sections_html_parts.append(self._build_unmeasured(section_num=n))
            n += 1
        if "sources" in active:
            sections_html_parts.append(self._build_sources(section_num=n))
            n += 1

        html = _HTML_SKELETON.format(
            title=title,
            css=_CSS,
            chip_id=self._state.chip_id,
            last_updated=self._state.last_updated or "—",
            sections_html="\n".join(sections_html_parts),
        )

        output_path.write_text(html, encoding="utf-8")
        return output_path

    def _get_all_topology_params(self) -> list[str]:
        """自动检测所有可用的拓扑图参数。

        1. 遍历 6 种 built-in 参数，有数据的加入列表
        2. 遍历所有 qubit 的 extras key 的并集
        3. 排序：built-in 按固定顺序先，extras 按字母顺序后
        """
        state = self._state
        params: list[str] = []
        builtin_order = list(_COLORMAP_LABELS.keys())

        # Built-in params: check via _get_colormap_values
        for param in builtin_order:
            vals = _get_colormap_values(state, param)
            if vals:
                params.append(param)

        # Extras keys: union across ALL qubits (not just measured)
        extras_keys: set[str] = set()
        for name in state.topology.qubit_names:
            qs = state.get_qubit(name)
            for key in qs.extras:
                if key not in extras_keys:
                    extras_keys.add(key)
        params.extend(sorted(extras_keys))

        return params

    def _resolve_topology_param(
        self, param: str,
    ) -> tuple[dict[str, Any], bool]:
        """解析单个拓扑图参数，返回 ({qubit: value}, is_bool)。

        查找顺序：
        1. built-in 6 种参数 → 全部是数值，is_bool=False
        2. extras 字段（遍历所有 qubit 的 extras）
        3. 无任何 qubit 有数据 → 返回 ({}, False)

        is_bool 判定：遍历所有非 None 的 value，
        全为 bool → True，全为 numeric → False。混合类型 → 返回 ({}, False)。
        """
        state = self._state

        # 1. Built-in params (always numeric)
        if param in _COLORMAP_LABELS:
            values = _get_colormap_values(state, param)
            return (values, False)

        # 2. Extras field — collect across ALL qubits
        raw: dict[str, Any] = {}
        for name in state.topology.qubit_names:
            qs = state.get_qubit(name)
            if param in qs.extras:
                raw[name] = qs.extras[param]

        if not raw:
            # Yield params: return all-None dict so caller renders placeholder
            if param in _YIELD_PARAMS:
                return (
                    {name: None for name in state.topology.qubit_names},
                    True,
                )
            return ({}, False)

        # 3. Determine type (exclude None from type check)
        non_none = {k: v for k, v in raw.items() if v is not None}
        if non_none:
            all_bool = all(isinstance(v, bool) for v in non_none.values())
            all_numeric = all(
                isinstance(v, (int, float)) and not isinstance(v, bool)
                for v in non_none.values()
            )
            if all_bool:
                # Expand to all topology qubits; missing ones → None
                full = {name: raw.get(name) for name in state.topology.qubit_names}
                return (full, True)
            elif all_numeric:
                return ({k: float(v) for k, v in raw.items()}, False)
            else:
                # Mixed types — skip
                return ({}, False)
        else:
            # All values are None — bool for yield params, skip otherwise
            if param in _YIELD_PARAMS:
                full = {name: raw.get(name) for name in state.topology.qubit_names}
                return (full, True)
            return ({}, False)

    def _build_single_topology_figure(self, param: str) -> str | None:
        """为单个参数生成一张拓扑图 SVG，无数据则返回 None。

        bool 参数 → categorical_param()（True=浅蓝, False=灰, None=白虚线?）
        数值参数 → colormap_param(show_values=True) + colorbar
        """
        values, is_bool = self._resolve_topology_param(param)
        # Non-yield params with no data: skip (keep legacy behaviour)
        if not values and param not in _YIELD_PARAMS:
            return None

        artist = ChipArtist(self._state.topology)
        artist.draw(show_labels=False)  # R3: 不画 draw() 的黑 ID

        if is_bool:
            artist.categorical_param(param, values)
        elif not values:
            # Yield param with all-None values — render as categorical None
            artist.categorical_param(param, values)
        else:
            label = _COLORMAP_LABELS.get(param, param)
            unit = _COLORMAP_UNITS.get(param)
            # R1b: normalize drive_efficiency for colormap
            values_for_colormap = values
            if param == "drive_efficiency":
                values_for_colormap = _normalize_values(values)
            sm = artist.colormap_param(
                param, values_for_colormap,
                show_values=True,
                value_unit=unit,
            )
            if sm is not None:
                fig = artist.get_figure()
                fig.colorbar(sm, ax=artist.ax, label=label,
                            fraction=0.046, pad=0.04)

        svg = artist.to_svg()

        # Strip XML declaration / DOCTYPE — keep only <svg>...</svg>
        svg_start = svg.find("<svg")
        if svg_start > 0:
            svg = svg[svg_start:]

        return svg

    # ---- private section builders ----

    def _build_yield(self, section_num: int) -> str:
        """Render yield-parameter topology figures side-by-side.

        Always renders three figures (Measurable | Readout Cavity | Bias Tunable)
        regardless of data presence. Missing data shows as white dashed boxes
        with grey "?" markers.
        """
        figures_html: list[str] = []
        for param in _YIELD_ORDER:
            svg = self._build_single_topology_figure(param)
            # Yield params never return None (all-None placeholder rendered)
            if svg is None:
                continue
            label = _YIELD_LABELS.get(param, param)
            figures_html.append(
                f'<figure>'
                f'<figcaption>{label}</figcaption>'
                f'{svg}'
                f'</figure>'
            )
        if not figures_html:
            return ""
        figures_block = "\n".join(figures_html)
        return (
            f'<section id="yield">'
            f'<h2>{section_num}. Chip Yield</h2>'
            f'<div class="yield-row">'
            f'{figures_block}'
            f'</div>'
            f'</section>'
        )

    def _build_overview(self, topology_params: list[str], section_num: int = 1) -> str:
        """为每个参数生成独立拓扑图，共用单个 overview section。

        T1/T2*/T2echo 三个 coherence 参数水平并排显示在同一行。
        其余参数各自独立成图。
        """
        coherence_keys = {"T1", "T2star", "T2echo"}
        coherence_params = [p for p in topology_params if p in coherence_keys]
        other_params = [p for p in topology_params if p not in coherence_keys]

        figures_html: list[str] = []

        # Coherence 参数同行显示
        if coherence_params:
            coherence_figs: list[str] = []
            for param in coherence_params:
                svg = self._build_single_topology_figure(param)
                if svg is None:
                    continue
                label = _COLORMAP_LABELS.get(param, param)
                coherence_figs.append(
                    f'<figure>'
                    f'<figcaption>{label}</figcaption>'
                    f'{svg}'
                    f'</figure>'
                )
            if coherence_figs:
                figures_html.append(
                    '<div class="coherence-row">\n'
                    + '\n'.join(coherence_figs)
                    + '\n</div>'
                )

        # 其余参数各自独立成图
        for param in other_params:
            svg = self._build_single_topology_figure(param)
            if svg is None:
                continue
            label = _COLORMAP_LABELS.get(param, param)
            figures_html.append(
                f'<figure>'
                f'<figcaption>{label}</figcaption>'
                f'{svg}'
                f'</figure>'
            )

        if not figures_html:
            return ""
        figures_block = "\n".join(figures_html)
        return (
            f'<section id="overview">'
            f'<h2>{section_num}. Chip Topology</h2>'
            f'{figures_block}'
            f'</section>'
        )

    def _build_measured_qubits(self, section_num: int = 2) -> str:
        """Generate per-qubit parameter cards."""
        state = self._state
        measured = state.list_measured_qubits()
        cards = [_build_qubit_card(name, state) for name in measured]
        return (
            _MEASURED_SECTION_HEADER.format(section_num=section_num, count=len(measured))
            + "\n".join(cards)
            + _MEASURED_SECTION_FOOTER
        )

    def _build_unmeasured(self, section_num: int = 3) -> str:
        """Generate unmeasured qubits list."""
        state = self._state
        all_qubits = set(state.topology.qubit_names)
        measured = set(state.list_measured_qubits())
        unmeasured = sorted(all_qubits - measured)

        chips_html = "\n".join(
            f'<span class="unmeasured-chip">{name}</span>'
            for name in unmeasured
        )
        return _UNMEASURED_SECTION.format(
            section_num=section_num,
            count=len(unmeasured),
            chips=chips_html,
        )

    def _build_sources(self, section_num: int = 4) -> str:
        """Generate data sources table."""
        rows = _build_sources_table(self._state)
        return _SOURCES_SECTION.format(section_num=section_num, rows=rows)
