# Phase 10 修改计划 — Chip Yield 固定渲染 + None 态支持

**文档日期**：2026-06-19
**角色**：Supervisor（设计文档，供实现侧 Claude Code 执行）
**设计基准**：Phase 9 完成后的代码（`exp_toolkit/report/generator.py`、`exp_toolkit/visualization/chip_plot.py`）

---

## 一、需求

| 需求 | 说明 | 影响文件 |
|------|------|---------|
| R1 | Yield section 在报告中固定渲染，不因数据缺失而缺席 | generator.py |
| R2 | `categorical_param()` 支持 `None` 值——白底虚线边 + 灰色 `?` 标记 | chip_plot.py |
| R3 | `_build_single_topology_figure()` 在 values 为空时渲染全灰拓扑图（而非返回 None） | generator.py |
| R4 | 空 yield 拓扑的 is_bool 类型从 `_YIELD_SPEC` 字典获取（不依赖数据推断） | generator.py |

---

## 二、背景：方案 A vs 方案 B

Phase 9 结束后，我们对三个良率参数（`measurable`、`readout_cavity_response`、`bias_tunable`）的长期定位进行了设计讨论。两个方向：

### 方案 A：提升为 QubitState 一级字段

将三个字段从 `extras: dict[str, Any]` 中提升为 `QubitState` 的 dataclass field：

```python
@dataclass
class QubitState:
    ...
    measurable: bool | None = None
    readout_cavity_response: bool | None = None
    bias_tunable: bool | None = None
    extras: dict[str, Any] = field(default_factory=dict)
```

### 方案 B：保持 extras，报告层固定渲染

数据结构不动，report generator 强制渲染 yield section，缺失数据时显示"未评估"的空白拓扑图。

### 决策：方案 B

**理由**：

1. **良率指标本身仍在演化**。Phase 1–9 之间 extras 字段的语义和显示方式多次调整。如果未来新增第四个良率指标（如 `flux_tunable`），方案 B 只需在 `_YIELD_ORDER` 中加一行；方案 A 需要修改 `QubitState` dataclass、`save()`、`load()`、`ChipState` setter、`get_latest()`、`list_measured_qubits()`、`generator.py` 中 4 个函数的显式分支，以及所有已有 JSON 文件的迁移逻辑。

2. **数据模型的承诺成本**（详见 [附录：承诺成本分析](#附录承诺成本分析)）。当前 extras 的 `dict[str, Any]` 为所有扩展字段提供了一条通用读写通道——save/load/report 全部自动跟随。提升一个字段到一级意味着它必须重新实现 6 层支撑代码（setter → save → load → get_latest → list_measured → 报告渲染），且后续每个新的代码路径都需要为该字段单独写处理逻辑。

3. **方案 B 同样实现了"倒逼效果"**——固定渲染 yield section 意味着即使数据缺失，报告也会在开头展示三张灰色拓扑图并标注 "?"。这份空白本身就是"请填写这三个字段"的信号。

4. **方案 A 更好的时机**：当三个字段的语义完全稳定，且发现自己在多个脚本中反复写 `qs.extras.get("measurable")` 并手动处理 KeyError / 类型转换时——那时提升为 field 是消除样板代码的自然重构。

> 完整的方案对比分析详见 [`phase-9-report.md`](../reports/phase-9-report.md) 第五节。

---

## 三、R1 — Yield section 固定渲染

### 问题诊断

当前 `generate()` 中，yield section 仅在 `yield_params` 非空时才构建：

```python
# 当前逻辑（generator.py generate()）
yield_params = sorted(
    [p for p in topology_params if p in _YIELD_PARAMS],
    key=lambda p: _YIELD_ORDER.index(p) if p in _YIELD_ORDER else 99,
)
...
if yield_params and "overview" in active:
    sections_html_parts.append(self._build_yield(yield_params, section_num=n))
    n += 1
```

问题：如果芯片数据中没有任何比特设置了这三个字段，yield section 完全消失，报告开头直接跳到 "2. Chip Topology"，读者无法判断"数据缺失"还是"所有比特都不可测"。

### 改动

移除条件判断中的 `yield_params and`，yield section **始终渲染**：

```python
# 改后
if "overview" in active:
    sections_html_parts.append(self._build_yield(section_num=n))
    n += 1
```

`_build_yield()` 不再接收 `yield_params` 参数，内部固定遍历 `_YIELD_ORDER`：

```python
def _build_yield(self, section_num: int) -> str:
    figures_html: list[str] = []
    for param in _YIELD_ORDER:
        svg = self._build_single_topology_figure(param)
        # R3: _build_single_topology_figure 在无数据时不再返回 None，
        # 而是渲染全灰拓扑图
        label = _YIELD_LABELS[param]
        figures_html.append(
            f'<figure><figcaption>{label}</figcaption>{svg}</figure>'
        )
    figures_block = "\n".join(figures_html)
    return (
        f'<section id="yield">'
        f'<h2>{section_num}. Chip Yield</h2>'
        f'<div class="yield-row">{figures_block}</div>'
        f'</section>'
    )
```

### yield_params 仍参与 topology_params 过滤

`other_params` 的计算逻辑不变——若三个良率字段出现在 `topology_params` 中，仍从 Chip Topology 节中排除（避免重复显示）：

```python
other_params = [p for p in topology_params if p not in _YIELD_PARAMS]
```

---

## 四、R2 — `categorical_param()` 支持 None 值

### 问题诊断

当前 `categorical_param()` 签名为 `values: dict[str, bool]`，每个比特的 value 必须是 `True` 或 `False`。如果某个比特的 extras 中不存在该字段，当前行为是直接跳过（`if name not in values: continue`）。

方案 B 要求在"无数据"时渲染一个视觉上不同的状态（白底 + 虚线边 + 灰色 `?`），以区分子"明确为 False"和"从未被评估"。

### 改动

**类型扩展**：`values` 参数从 `dict[str, bool]` 扩展为 `dict[str, bool | None]`。

**渲染逻辑**（`chip_plot.py` `categorical_param()`）：

```python
def categorical_param(
    self,
    param_name: str,
    values: dict[str, bool | None],     # ← 扩展类型
    true_color: str = "#ADD8E6",
    false_color: str = "#D9D9D9",
    edge_color: str = "#888888",
) -> None:
    _, ax = self._ensure_drawn()

    for pos, name in self._topo.iter_qubits():
        if name not in values:           # 完全不在 dict 中 → 跳过（保留 draw() 的灰底）
            continue
        x, y = self._to_xy(pos)
        val = values[name]

        if val is None:
            # 未评估：白底 + 虚线边框 + 灰色 ?
            fc = "#FFFFFF"
            ec = "#BBBBBB"
            linestyle = (0, (4, 3))     # 虚线
            display_text = f"{name}\n?"
            text_color = "#AAAAAA"
        elif val:
            fc = true_color
            ec = edge_color
            linestyle = "-"
            display_text = name
            text_color = self._text_color_for_bg(fc)
        else:
            fc = false_color
            ec = edge_color
            linestyle = "-"
            display_text = name
            text_color = self._text_color_for_bg(fc)

        box = self._make_box(
            x, y, facecolor=fc, edgecolor=ec,
            linewidth=1.5, zorder=2,
        )
        if val is None:
            box.set_linestyle(linestyle)
        ax.add_patch(box)
        self._overlay_patches.append(box)

        txt = ax.text(
            x, y, display_text,
            ha="center", va="center",
            fontsize=8, fontweight="bold",
            color=text_color, zorder=3,
        )
        self._overlay_patches.append(txt)
```

**注意**：`FancyBboxPatch` 的 `set_linestyle()` 是否支持虚线需要验证——若不行，改用 `box.set_edgecolor(ec)` + 降低 `linewidth`，或通过 `box.set_linestyle((0, (4, 3)))` 设置。

### 视觉对照表

| 值 | 填充色 | 边框 | 文字 | 语义 |
|----|--------|------|------|------|
| `True` | `#ADD8E6` 浅蓝 | `#888888` 实线 | 比特名（自适应色） | 可用 |
| `False` | `#D9D9D9` 浅灰 | `#888888` 实线 | 比特名（自适应色） | 不可用 |
| `None` | `#FFFFFF` 白色 | `#BBBBBB` 虚线 | 比特名 + 灰色 `?` | 待评估 |

---

## 五、R3 — `_build_single_topology_figure()` 空值容错

### 问题诊断

当前 `_build_single_topology_figure()` 在 `_resolve_topology_param()` 返回空 dict 时直接 `return None`：

```python
def _build_single_topology_figure(self, param: str) -> str | None:
    values, is_bool = self._resolve_topology_param(param)
    if not values:          # ← 无数据 → 放弃渲染
        return None
    ...
```

### 改动

移除 early return，空值时渲染全灰拓扑图：

```python
def _build_single_topology_figure(self, param: str) -> str:
    values, is_bool = self._resolve_topology_param(param)

    artist = ChipArtist(self._state.topology)
    artist.draw(show_labels=False)

    if not values:
        # 无数据：全灰占位拓扑
        # 不管是 bool 还是 numeric，都走 categorical_param 的 None 渲染
        # is_bool 可能无法从数据推断 → 使用 _YIELD_SPEC 预定义
        pass
        # 渲染逻辑见 R4
    elif is_bool:
        artist.categorical_param(param, values)
    else:
        label = _COLORMAP_LABELS.get(param, param)
        unit = _COLORMAP_UNITS.get(param)
        values_for_colormap = values
        if param == "drive_efficiency":
            values_for_colormap = _normalize_values(values)
        sm = artist.colormap_param(
            param, values_for_colormap,
            show_values=True, value_unit=unit,
        )
        if sm is not None:
            fig = artist.get_figure()
            fig.colorbar(sm, ax=artist.ax, label=label,
                        fraction=0.046, pad=0.04)

    svg = artist.to_svg()
    svg_start = svg.find("<svg")
    if svg_start > 0:
        svg = svg[svg_start:]
    return svg
```

返回值从 `str | None` 改为 `str`——调用方不再需要判断 None。

---

## 六、R4 — `_YIELD_SPEC` 元数据字典

### 问题诊断

`_resolve_topology_param()` 的类型判定逻辑依赖数据：

```python
# 当前: 从数据中推断类型
all_bool = all(isinstance(v, bool) for v in raw.values())
all_numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in raw.values())
```

当所有比特的 `measurable` 都为 None（即 `raw` 为空 dict），无法推断类型。需要外部元数据。

### 改动

新增 `_YIELD_SPEC` 字典，为每个 yield 参数预定义类型和标签：

```python
_YIELD_SPEC = {
    "measurable":               {"type": "bool", "label": "Measurable"},
    "readout_cavity_response":  {"type": "bool", "label": "Readout Cavity"},
    "bias_tunable":             {"type": "bool", "label": "Bias Tunable"},
}
```

`_YIELD_ORDER` 和 `_YIELD_LABELS` 可以从 `_YIELD_SPEC` 派生或保持独立。建议**合并**以消除重复定义：

```python
# 替换原有的 _YIELD_PARAMS, _YIELD_ORDER, _YIELD_LABELS
_YIELD_SPEC = [
    ("measurable",               "Measurable"),
    ("readout_cavity_response",  "Readout Cavity"),
    ("bias_tunable",             "Bias Tunable"),
]
# _YIELD_ORDER 从 _YIELD_SPEC 推导
_YIELD_ORDER = [key for key, _ in _YIELD_SPEC]
# _YIELD_PARAMS 从 _YIELD_ORDER 推导
_YIELD_PARAMS = set(_YIELD_ORDER)
# _YIELD_LABELS 从 _YIELD_SPEC 推导
_YIELD_LABELS = dict(_YIELD_SPEC)
```

**`_build_single_topology_figure()` 中的空值分支**：

```python
if not values:
    # 所有比特均为 None → 渲染全 None 拓扑
    # 从 _YIELD_SPEC 查类型
    yield_info = dict(_YIELD_SPEC).get(param)
    if yield_info and yield_info["type"] == "bool":
        none_values = {name: None for name in self._state.topology.qubit_names}
        artist.categorical_param(param, none_values)
    else:
        # 非 yield 参数，无数据 → 仍然 return None（或渲染全灰）
        return None  # 视需要调整
```

### `_resolve_topology_param()` 适配

当 `raw` 为空 dict 但 param 在 `_YIELD_PARAMS` 中时，返回全 None 的 dict + `is_bool=True`：

```python
def _resolve_topology_param(self, param: str):
    state = self._state

    # 1. Built-in params
    if param in _COLORMAP_LABELS:
        values = _get_colormap_values(state, param)
        return (values, False)

    # 2. Extras field
    raw: dict[str, Any] = {}
    for name in state.topology.qubit_names:
        qs = state.get_qubit(name)
        if param in qs.extras:
            raw[name] = qs.extras[param]

    if not raw:
        # 3. 空值 fallback
        if param in _YIELD_PARAMS:
            return ({name: None for name in state.topology.qubit_names}, True)
        return ({}, False)

    # 4. Determine type (unchanged)
    ...
```

---

## 七、改动文件清单

| 文件 | 改动内容 | 行数估算 |
|------|---------|---------|
| `exp_toolkit/report/generator.py` | R1: `generate()` 固定 yield 渲染；合并 `_YIELD_*` 常量；R3: `_build_single_topology_figure()` 空值容错；R4: `_resolve_topology_param()` None fallback | ~40 |
| `exp_toolkit/visualization/chip_plot.py` | R2: `categorical_param()` 支持 `bool \| None` 值，虚线白底 None 态渲染 | ~25 |
| `tests/test_phase3.py` | 新增：全空 yield 渲染、半空 yield 渲染、None 态 visual 验证、yield section 始终存在 | ~40 |

**总代码量**：~65 行实现 + ~40 行测试

---

## 八、边界情况

| 场景 | 预期行为 |
|------|---------|
| 芯片无任何 yield 数据 | 三张图全白虚线 `?`，yield section 仍为节 1 |
| 部分比特有数据、部分无 | 有数据的正常着色（蓝/灰实线），无数据的白虚线 `?` |
| 用户显式传入 `topology_params=["T1"]`（不含 yield） | `other_params` 不含 yield → Chip Topology 正常；yield section 仍渲染（因固定渲染不看 topology_params） |
| 用户显式传入 `sections=["qubits"]`（不含 overview） | yield section 依赖 `"overview" in active` → 跳过，行为一致 |
| `FancyBboxPatch` 不支持虚线 | 改用 `linewidth=1` + 更淡的边框颜色 `#CCCCCC` 来区分 None 态 |
| 非 yield extras 字段无数据 | 保持现有行为：不渲染拓扑图（`_build_single_topology_figure` 对非 yield 且空值的参数仍返回 None 或全灰） |

---

## 九、不在此次范围

| 项目 | 说明 |
|------|------|
| 方案 A 的 QubitState 重构 | 待良率指标语义完全稳定后再评估 |
| `list_measured_qubits()` 纳入 yield 判定 | yield 数据不改变 "measured" 定义——measured 仍由 T1/T2*/f01 等实验数据决定 |
| yield 数据的历史版本记录 | 三个 bool 字段当前是 scalar（覆盖写入），未来可考虑改为 list[YieldEntry] 支持时间戳追踪 |
| HTML 报告中 yield 的统计数字（如 "18/25 measurable"） | 后续 Phase 可加 |

---

## 十、附录：承诺成本分析

将 `measurable` 从 `extras` 提升为 `QubitState` 一级字段，意味着它必须复制以下全部支撑代码（当前 extras 中的所有字段共享同一个通用通道）：

```
chip_state.py:
  ├── QubitState dataclass          ← +1 field 声明
  ├── ChipState.set_*()             ← +1 专用 setter
  ├── ChipState.save()              ← +N 行显式序列化
  ├── ChipState.load()              ← +N 行反序列化 + 旧格式兼容
  ├── ChipState.get_latest()        ← +1 elif 分支（类型异构问题）
  └── ChipState.list_measured_qubits() ← 语义判定（改变"已测"定义？）

generator.py:
  ├── _get_qubit_field_values()     ← +1 elif 分支
  ├── _get_colormap_values()        ← +1 elif 分支
  ├── _resolve_topology_param()     ← 不再是通用 catch-all
  └── _build_qubit_card()           ← +5 行显式渲染块

外部:
  └── 所有直接读 chip_state.json 的脚本 ← JSON 结构变化致静默失败

测试:
  ├── test_phase2.py                ← save/load roundtrip × 3
  └── test_phase3.py                ← 渲染 + None 态 + 旧格式兼容
```

每个提升的字段都需要在 6 层代码路径中写独立的样板分支，且这种维护义务在字段的整个生命周期中持续存在。当前 `extras` 的 `dict[str, Any]` 为扩展字段提供了免维护的读写通道——这是方案 B 的核心优势。

---

> **文档版本**：v1  
> **关联文档**：[`phase-9-report.md`](../reports/phase-9-report.md) | [`phase-8-design.md`](phase-8-design.md) | [`requirements.md`](../requirements.md)  
> **下一环节**：执行实现（实现侧根据本文档编写代码和测试）
