"""芯片拓扑可视化 — ChipTopology（数据结构）+ ChipArtist（绘图器）。

使用 matplotlib 面向对象 API，不硬编码比特坐标。
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Iterator

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

__all__ = ["ChipTopology", "ChipArtist"]


# =============================================================================
# ChipTopology
# =============================================================================


class ChipTopology:
    """芯片拓扑描述 — 纯数据结构，不绘图。

    Parameters
    ----------
    layout : dict[tuple[int, int], str | None]
        (row, col) → qubit_name，None 表示空缺位。

    Examples
    --------
    >>> topo = ChipTopology.from_grid(5, 5)
    >>> topo.add_coupler("Q01", "Q02", coupling_MHz=15.0)
    >>> topo.get_neighbors("Q06")
    ['Q01', 'Q07', 'Q11']
    """

    def __init__(self, layout: dict[tuple[int, int], str | None]) -> None:
        if not layout:
            raise ValueError("layout must not be empty")
        self._layout: dict[tuple[int, int], str | None] = dict(layout)
        self._couplers: list[tuple[str, str, dict[str, Any]]] = []

        # 构建反向索引 name → pos
        self._name_to_pos: dict[str, tuple[int, int]] = {}
        for pos, name in self._layout.items():
            if name is not None:
                if name in self._name_to_pos:
                    raise ValueError(f"Duplicate qubit name: '{name}'")
                self._name_to_pos[name] = pos

    # ---- factories ----

    @classmethod
    def from_grid(
        cls,
        rows: int,
        cols: int,
        numbering: str = "row-major",
        start: int = 1,
    ) -> "ChipTopology":
        """从标准矩形网格创建拓扑。

        Parameters
        ----------
        rows : int
            行数。
        cols : int
            列数。
        numbering : str
            "row-major"：逐行编号（Q01=左上角，Q02=同行右一格）。
            "col-major"：逐列编号（Q01=左上角，Q02=同列下一格）。
        start : int
            起始比特编号。

        Returns
        -------
        ChipTopology
        """
        if numbering not in ("row-major", "col-major"):
            raise ValueError(
                f"numbering must be 'row-major' or 'col-major', got '{numbering}'"
            )

        layout: dict[tuple[int, int], str | None] = {}
        for i in range(rows * cols):
            if numbering == "row-major":
                r, c = divmod(i, cols)
            else:
                c, r = divmod(i, rows)
            qname = f"Q{start + i:02d}"
            layout[(r, c)] = qname

        return cls(layout)

    # ---- couplers ----

    def add_coupler(self, q1: str, q2: str, **params: Any) -> None:
        """添加比特间耦合连接。

        Parameters
        ----------
        q1, q2 : str
            耦合的两个比特名称。
        **params : Any
            耦合参数（如 coupling_MHz）。
        """
        if q1 not in self._name_to_pos:
            raise ValueError(f"Qubit '{q1}' not in topology")
        if q2 not in self._name_to_pos:
            raise ValueError(f"Qubit '{q2}' not in topology")
        self._couplers.append((q1, q2, params))

    def get_neighbors(self, name: str) -> list[str]:
        """获取某比特的所有耦合邻居。

        Parameters
        ----------
        name : str
            比特名称。

        Returns
        -------
        list[str]
        """
        neighbors: list[str] = []
        for q1, q2, _ in self._couplers:
            if q1 == name:
                neighbors.append(q2)
            elif q2 == name:
                neighbors.append(q1)
        return neighbors

    @property
    def couplers(self) -> list[tuple[str, str, dict[str, Any]]]:
        """耦合器列表。"""
        return list(self._couplers)

    # ---- iteration ----

    def iter_qubits(self) -> Iterator[tuple[tuple[int, int], str]]:
        """遍历所有 (position, name) 对，跳过空缺位。

        Yields
        ------
        tuple[tuple[int, int], str]
        """
        for pos, name in sorted(self._layout.items()):
            if name is not None:
                yield (pos, name)

    def iter_positions(self) -> Iterator[tuple[int, int]]:
        """遍历所有 (row, col) 位置，包含空缺位（None 占位）。

        Yields
        ------
        tuple[int, int]
        """
        yield from sorted(self._layout.keys())

    def pos_of(self, name: str) -> tuple[int, int] | None:
        """获取比特在拓扑中的 (row, col) 位置。

        Returns
        -------
        tuple[int, int] or None
        """
        return self._name_to_pos.get(name)

    # ---- serialization ----

    def to_dict(self) -> dict[str, Any]:
        """序列化拓扑为字典，完整保留布局（含空缺位）和耦合器。

        Returns
        -------
        dict
            {"layout": {"0,0": "Q01", "0,1": None, ...},
             "couplers": [{"q1": "Q01", "q2": "Q02", ...}, ...]}
        """
        layout_serialized: dict[str, str | None] = {}
        for (r, c), name in sorted(self._layout.items()):
            layout_serialized[f"{r},{c}"] = name

        couplers_serialized: list[dict[str, Any]] = []
        for q1, q2, params in self._couplers:
            entry: dict[str, Any] = {"q1": q1, "q2": q2}
            entry.update(params)
            couplers_serialized.append(entry)

        return {
            "layout": layout_serialized,
            "couplers": couplers_serialized,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ChipTopology":
        """从字典反序列化拓扑（含耦合器）。兼容旧格式 {rows, cols, numbering, start}。

        Parameters
        ----------
        d : dict
            序列化字典。优先使用 "layout" 键（新格式），
            回退到 from_grid() 解析旧格式。

        Returns
        -------
        ChipTopology
        """
        # New format: has "layout" key
        if "layout" in d:
            layout: dict[tuple[int, int], str | None] = {}
            for key, name in d["layout"].items():
                r_str, c_str = key.split(",")
                layout[(int(r_str), int(c_str))] = name
            topo = cls(layout)
            for entry in d.get("couplers", []):
                q1 = entry["q1"]
                q2 = entry["q2"]
                params = {k: v for k, v in entry.items() if k not in ("q1", "q2")}
                topo.add_coupler(q1, q2, **params)
            return topo

        # Old format: rows/cols/numbering/start → fallback to from_grid
        return cls.from_grid(
            rows=d.get("rows", 5),
            cols=d.get("cols", 5),
            numbering=d.get("numbering", "row-major"),
            start=d.get("start", 1),
        )

    # ---- properties ----

    @property
    def qubit_names(self) -> list[str]:
        """所有比特名称列表（按 row, col 排序）。"""
        result: list[str] = []
        for _, name in sorted(self._layout.items()):
            if name is not None:
                result.append(name)
        return result

    @property
    def rows(self) -> int:
        """行数。"""
        if not self._layout:
            return 0
        return max(r for r, _ in self._layout) + 1

    @property
    def cols(self) -> int:
        """列数。"""
        if not self._layout:
            return 0
        return max(c for _, c in self._layout) + 1


# =============================================================================
# ChipArtist
# =============================================================================


class ChipArtist:
    """芯片拓扑图绘制器。

    使用 matplotlib 面向对象 API，绘制比特圆圈 + 标签 + 连接线 + 色标 + 标注。

    Parameters
    ----------
    topology : ChipTopology
        芯片拓扑数据。
    figsize : tuple[float, float]
        图形尺寸（英寸）。

    Examples
    --------
    >>> topo = ChipTopology.from_grid(5, 5)
    >>> artist = ChipArtist(topo)
    >>> artist.draw()
    >>> artist.highlight_measured(["Q01", "Q07", "Q16"])
    >>> artist.save("chip.svg")
    """

    # 绘制定位常量
    _PAD = 0.6  # 边缘留白比例
    _RADIUS = 0.35  # 比特圆圈半径（保留用于旧代码兼容）
    _BOX_WIDTH = 0.7     # 2 × _RADIUS
    _BOX_HEIGHT = 0.525   # 1.5 × _RADIUS，容纳双行文本

    def __init__(
        self,
        topology: ChipTopology,
        figsize: tuple[float, float] = (8, 8),
    ) -> None:
        self._topo = topology
        self._figsize = figsize

        # 内部状态
        self._fig: plt.Figure | None = None
        self._ax: plt.Axes | None = None
        self._drawn: bool = False  # draw() 是否已调用

        # 缓存坐标映射
        self._qx: dict[str, float] = {}
        self._qy: dict[str, float] = {}

        # 叠加层追踪（用于 reset()）
        self._overlay_patches: list[plt.Artist] = []

    # ---- internal helpers ----

    def _to_xy(self, pos: tuple[int, int]) -> tuple[float, float]:
        """(row, col) → (x, y) 绘图坐标。col→x, row→-y（上方为正）。"""
        r, c = pos
        return (float(c), -float(r))

    def _ensure_drawn(self) -> tuple[plt.Figure, plt.Axes]:
        """确保 draw() 已被调用。"""
        if self._fig is None or self._ax is None:
            return self.draw()
        return self._fig, self._ax

    def _get_circle_center(self, name: str) -> tuple[float, float]:
        """获取比特圆圈中心绘图坐标。"""
        pos = self._topo.pos_of(name)
        if pos is None:
            raise ValueError(f"Qubit '{name}' not in topology")
        return self._to_xy(pos)

    @staticmethod
    def _text_color_for_bg(bg_color: str | tuple[float, ...]) -> str:
        """Return 'black' or 'white' for readable contrast on *bg_color*.

        Computes relative luminance (ITU-R BT.601) and picks black
        for light backgrounds, white for dark backgrounds.
        Accepts hex strings or RGBA tuples.
        """
        if isinstance(bg_color, str):
            bg_color = matplotlib.colors.to_rgba(bg_color)
        r, g, b = bg_color[0], bg_color[1], bg_color[2]
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        return "black" if lum > 0.5 else "white"

    def _make_box(
        self, x: float, y: float,
        facecolor: str, edgecolor: str,
        linewidth: float = 1.5, zorder: int = 2,
    ) -> FancyBboxPatch:
        """Create a rounded-rectangle patch for a qubit centered at (x, y)."""
        return FancyBboxPatch(
            (x - self._BOX_WIDTH / 2, y - self._BOX_HEIGHT / 2),
            self._BOX_WIDTH, self._BOX_HEIGHT,
            boxstyle="round,pad=0.02",
            facecolor=facecolor, edgecolor=edgecolor,
            linewidth=linewidth, zorder=zorder,
        )

    # ---- public API ----

    def draw(
        self, ax: plt.Axes | None = None, show_labels: bool = True,
    ) -> tuple[plt.Figure, plt.Axes]:
        """绘制基础拓扑（灰色圆角矩形 + 可选比特标签）。

        Parameters
        ----------
        ax : plt.Axes or None
            绘入已有 Axes，为 None 时创建新 Figure。
        show_labels : bool
            若 True（默认），在每个盒子内绘制黑色比特名。
            若 False，仅绘制灰色盒子，不绘制文字。

        Returns
        -------
        tuple[plt.Figure, plt.Axes]
        """
        if ax is not None:
            self._ax = ax
            self._fig = ax.figure
        else:
            self._fig, self._ax = plt.subplots(figsize=self._figsize)

        ax = self._ax

        # 计算坐标边界
        all_positions = list(self._layout_positions())
        if not all_positions:
            raise ValueError("Topology has no qubit positions")
        xs = [self._to_xy(p)[0] for p in all_positions]
        ys = [self._to_xy(p)[1] for p in all_positions]

        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        # 绘制比特圆圈
        for pos, name in self._topo.iter_qubits():
            x, y = self._to_xy(pos)
            self._qx[name] = x
            self._qy[name] = y
            box = self._make_box(
                x, y,
                facecolor="#D9D9D9", edgecolor="#888888",
                linewidth=1.5, zorder=2,
            )
            ax.add_patch(box)
            # 标签（可选）
            if show_labels:
                ax.text(
                    x, y, name,
                    ha="center", va="center",
                    fontsize=8, fontweight="bold",
                    zorder=3,
                )

        # 设置轴范围
        ax.set_xlim(x_min - self._PAD, x_max + self._PAD)
        ax.set_ylim(y_min - self._PAD, y_max + self._PAD)
        ax.set_aspect("equal")
        ax.axis("off")

        self._drawn = True
        return self._fig, ax

    def highlight_measured(
        self,
        measured_qubits: list[str],
        color: str = "#4C72B0",
    ) -> None:
        """高亮已测量的比特（模式 A：测量覆盖图）。

        Parameters
        ----------
        measured_qubits : list[str]
            已测量的比特名称列表。
        color : str
            填充颜色。
        """
        fig, ax = self._ensure_drawn()
        measured_set = set(measured_qubits)

        for pos, name in self._topo.iter_qubits():
            if name in measured_set:
                x, y = self._to_xy(pos)
                box = self._make_box(
                    x, y,
                    facecolor=color, edgecolor="#333333",
                    linewidth=1.5, zorder=2,
                )
                ax.add_patch(box)
                self._overlay_patches.append(box)
                # 重绘标签（确保在彩色圆圈上方）
                txt = ax.text(
                    x, y, name,
                    ha="center", va="center",
                    fontsize=8, fontweight="bold",
                    color="white",
                    zorder=4,
                )
                self._overlay_patches.append(txt)

    def colormap_param(
        self,
        param_name: str,
        values: dict[str, float],
        cmap: str = "viridis",
        vmin: float | None = None,
        vmax: float | None = None,
        show_values: bool = False,
        value_format: str = "{:.1f}",
        value_unit: str | None = None,
    ) -> matplotlib.cm.ScalarMappable | None:
        """用色标映射参数值（模式 B：参数色标图）。

        未在 values 中的比特保持灰色。

        Parameters
        ----------
        param_name : str
            参数名（用于 colorbar 标签）。
        values : dict[str, float]
            qubit_name → 参数值。
        cmap : str
            matplotlib colormap 名。
        vmin, vmax : float or None
            色标范围，为 None 时自动从 values 推断。
        show_values : bool
            若 True，在每个比特框内显示参数值（如 "Q16\\n45.2 μs"）。
        value_format : str
            数值格式化字符串（默认 "{:.1f}"）。
        value_unit : str or None
            显示在数值后的单位字符串。为 None 则不显示。

        Returns
        -------
        matplotlib.cm.ScalarMappable or None
            用于添加 colorbar 的 mappable。无有效值时返回 None。
        """
        fig, ax = self._ensure_drawn()

        valid_vals = [v for v in values.values() if np.isfinite(v)]
        if not valid_vals:
            return None

        if vmin is None:
            vmin = min(valid_vals)
        if vmax is None:
            vmax = max(valid_vals)

        cmap_obj = plt.get_cmap(cmap)
        norm = plt.Normalize(vmin=vmin, vmax=vmax)

        for pos, name in self._topo.iter_qubits():
            x, y = self._to_xy(pos)
            if name in values and np.isfinite(values[name]):
                fc = cmap_obj(norm(values[name]))
                ec = "#333333"
            else:
                fc = "#D9D9D9"
                ec = "#888888"

            box = self._make_box(
                x, y, facecolor=fc, edgecolor=ec,
                linewidth=1.5, zorder=2,
            )
            ax.add_patch(box)
            self._overlay_patches.append(box)
            # 构建显示文本
            has_value = name in values and np.isfinite(values[name])
            if show_values and has_value:
                unit_str = f" {value_unit}" if value_unit else ""
                display_text = f"{name}\n{value_format.format(values[name])}{unit_str}"
                text_color = self._text_color_for_bg(fc)
            elif show_values:
                display_text = name
                text_color = "black"
            else:
                display_text = name
                text_color = self._text_color_for_bg(fc) if has_value else "black"

            txt = ax.text(
                x, y, display_text,
                ha="center", va="center",
                fontsize=8, fontweight="bold",
                color=text_color,
                zorder=3,
            )
            self._overlay_patches.append(txt)

        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap_obj)
        sm.set_array([])
        return sm

    def categorical_param(
        self,
        param_name: str,
        values: dict[str, bool | None],
        true_color: str = "#ADD8E6",
        false_color: str = "#D9D9D9",
        edge_color: str = "#888888",
    ) -> None:
        """为布尔/分类参数着色拓扑图（模式 C：分类色标图）。

        每个比特盒子按 True/False/None 涂色，盒子内居中显示比特名。
        不需要 colorbar（分类数据）。

        Parameters
        ----------
        param_name : str
            参数名（用于标注，当前版本保留未使用）。
        values : dict[str, bool or None]
            qubit_name → True / False / None 值。
            None 表示未评估，渲染为白底虚线框 + 灰色 "?"。
        true_color : str
            True 时的盒子填充颜色（默认浅蓝）。
        false_color : str
            False 时的盒子填充颜色（默认灰）。
        edge_color : str
            盒子边框颜色（True/False 时使用）。
        """
        _, ax = self._ensure_drawn()

        for pos, name in self._topo.iter_qubits():
            if name not in values:
                continue
            x, y = self._to_xy(pos)
            val = values[name]

            if val is None:
                # 未评估：白底 + 虚线边框 + 灰色 ?
                fc = "#FFFFFF"
                ec = "#BBBBBB"
                lw = 1.0
                display_text = f"{name}\n?"
                text_color = "#AAAAAA"
                linestyle = (0, (4, 3))
            elif val:
                fc = true_color
                ec = edge_color
                lw = 1.5
                display_text = name
                text_color = self._text_color_for_bg(fc)
                linestyle = "-"
            else:
                fc = false_color
                ec = edge_color
                lw = 1.5
                display_text = name
                text_color = self._text_color_for_bg(fc)
                linestyle = "-"

            box = self._make_box(
                x, y,
                facecolor=fc, edgecolor=ec,
                linewidth=lw, zorder=2,
            )
            box.set_linestyle(linestyle)
            ax.add_patch(box)
            self._overlay_patches.append(box)
            txt = ax.text(
                x, y, display_text,
                ha="center", va="center",
                fontsize=8, fontweight="bold",
                color=text_color,
                zorder=3,
            )
            self._overlay_patches.append(txt)

    def add_coupler_lines(self, ax: plt.Axes | None = None) -> None:
        """绘制耦合连接线。

        Parameters
        ----------
        ax : plt.Axes or None
        """
        _, ax = (self._ensure_drawn() if ax is None
                 else (ax.figure, ax))

        for q1, q2, params in self._topo.couplers:
            x1, y1 = self._get_circle_center(q1)
            x2, y2 = self._get_circle_center(q2)
            (line,) = ax.plot(
                [x1, x2], [y1, y2],
                color="#AAAAAA",
                linewidth=1.0,
                zorder=1,
            )
            self._overlay_patches.append(line)

    def reset(self) -> None:
        """清除所有叠加层（highlight/colormap/annotate/coupler_lines 的
        后添加元素），恢复到 draw() 的基础状态。
        """
        for artist in self._overlay_patches:
            artist.remove()
        self._overlay_patches.clear()

    def annotate(
        self,
        fields: list[str],
        values: dict[str, dict[str, Any]],
        fontsize: int = 7,
    ) -> None:
        """在每个比特圆圈下方标注参数文本。

        Parameters
        ----------
        fields : list[str]
            要显示的字段名列表（如 ["f01", "T1"]）。
        values : dict[str, dict[str, Any]]
            qubit_name → {field: value}。
        fontsize : int
            字号。
        """
        _, ax = self._ensure_drawn()

        for pos, name in self._topo.iter_qubits():
            if name not in values:
                continue
            x, y = self._to_xy(pos)
            lines: list[str] = []
            for field in fields:
                if field in values[name]:
                    val = values[name][field]
                    if isinstance(val, float):
                        lines.append(f"{field}={val:.2f}")
                    else:
                        lines.append(f"{field}={val}")
            if lines:
                text = "\n".join(lines)
                txt = ax.text(
                    x, y - self._BOX_HEIGHT / 2 - 0.15,
                    text,
                    ha="center", va="top",
                    fontsize=fontsize,
                    zorder=3,
                )
                self._overlay_patches.append(txt)

    def save(
        self,
        path: str | Path,
        format: str = "svg",
        dpi: int = 150,
        bbox_inches: str | None = "tight",
    ) -> None:
        """保存图片到文件。

        Parameters
        ----------
        path : str or Path
            输出文件路径。
        format : str
            输出格式（svg, png, pdf...）。
        dpi : int
            输出分辨率（对 PNG 等光栅格式有效）。
        bbox_inches : str or None
            边界框模式，默认 "tight" 裁剪空白。
        """
        fig, _ = self._ensure_drawn()
        fig.savefig(path, format=format, bbox_inches=bbox_inches, dpi=dpi)

    def to_svg(self) -> str:
        """返回 SVG 字符串（用于 HTML 报告内嵌）。

        Returns
        -------
        str
            SVG 标记字符串。
        """
        fig, _ = self._ensure_drawn()
        buf = io.BytesIO()
        fig.savefig(buf, format="svg", bbox_inches="tight")
        buf.seek(0)
        return buf.read().decode("utf-8")

    def get_figure(self) -> plt.Figure:
        """获取 matplotlib Figure 对象。"""
        fig, _ = self._ensure_drawn()
        return fig

    @property
    def ax(self) -> plt.Axes:
        """获取当前绘图的 Axes 对象（只读）。"""
        _, ax = self._ensure_drawn()
        return ax

    # ---- internal ----

    def _layout_positions(self) -> list[tuple[int, int]]:
        """拓扑中所有 (row, col) 位置（含空缺位）。"""
        return list(self._topo.iter_positions())
