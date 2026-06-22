# Phase 6 设计文档 — 报告增强 + 多图拓扑 + Extras 可视化

**文档日期**：2026-06-18
**角色**：Supervisor（设计文档，供实现侧 Claude Code 执行）
**设计基准**：Phase 5 完成后的代码（`exp_toolkit/report/generator.py`, `exp_toolkit/visualization/chip_plot.py`）
**数据文件**：`data/chip_state_RICON_rebonded.json`

---

## 一、需求覆盖

| 需求 | 说明 | 影响文件 |
|------|------|---------|
| R1 | 每参数一张独立拓扑图（不用 annotate），报告只有一个 .html | generator.py, chip_plot.py |
| R2 | extras bool 用浅蓝/灰标识，float/int 用色标 | chip_plot.py, generator.py |
| R3 | 去除 draw() 中的黑色比特 ID（只保留 colormap 中的白色 ID） | chip_plot.py, generator.py |
| R4 | Data Sources 表头居中对齐 + 不用缩写 | generator.py |

> **注意**：qubit card 表格（Label | Value | @Freq | Source）4 列结构保持不变。用户已确认 HTML 源码中 4 列均存在，无需修改。

---

## 二、文件清单

| 文件 | 改动需求 |
|------|---------|
| `exp_toolkit/visualization/chip_plot.py` | R1 (draw show_labels), R2 (categorical_param), R3 |
| `exp_toolkit/report/generator.py` | R1 (多图 loop), R2 (extras 分发), R3 (show_labels=False), R4 (CSS + 表头) |
| `tests/test_phase3.py` | R1–R4 测试 |

---

## 三、R1 — 多参数独立拓扑图（不需要 annotate）

### 当前问题

`_build_overview()` 只生成 **一张** SVG，colormap + annotate 全部参数集中展示。用户要求每个参数一张独立图：
- 第一张：T1 色标
- 第二张：T2* 色标
- 第三张：T2 echo 色标
- 以此类推（含 extras 中的数值和 bool 字段）
- 每张图只展示一个参数，不用 `annotate()`

### 设计

#### 3a. `generate()` 签名变更

```python
# 改前
def generate(self, colormap_param: str, annotate_fields: list[str] | None = None) -> str:

# 改后
def generate(self, topology_params: list[str] | None = None) -> str:
```

- `topology_params=None` → 自动检测所有可用参数（built-in 6 种 + 所有 extras key 的并集）
- `topology_params=["T1", "T2star", ...]` → 仅生成指定参数的图
- `annotate_fields` 参数从 `generate()` 移除（报告不再使用 annotate，但 `ChipArtist.annotate()` 方法保留给独立使用场景）

#### 3b. `_build_overview()` 重写

改为循环生成多张 SVG，每参数一张 `<section>` + `<figure>`：

```python
def _build_overview(self, topology_params: list[str]) -> str:
    figures_html: list[str] = []
    for param in topology_params:
        svg = self._build_single_topology_figure(param)
        if svg is None:
            continue
        label = _COLORMAP_LABELS.get(param, param)
        figures_html.append(
            f'<section id="overview-{param}">'
            f'<h2>1. Chip Topology &mdash; {label}</h2>'
            f'<figure>{svg}</figure>'
            f'</section>'
        )
    return "\n".join(figures_html)
```

#### 3c. `_build_single_topology_figure()` 新方法

```python
def _build_single_topology_figure(self, param: str) -> str | None:
    """为单个参数生成一张拓扑图 SVG，无数据则返回 None。"""
    values, is_bool = self._resolve_topology_param(param)
    if not values:
        return None

    artist = ChipArtist(self._state.topology)
    artist.draw(show_labels=False)  # R3: 不画 draw() 的黑 ID

    if is_bool:
        # R2: 布尔参数 → 分类着色
        artist.categorical_param(param, values)
    else:
        # 数值参数 → 色标
        label = _COLORMAP_LABELS.get(param, param)
        unit = _COLORMAP_UNITS.get(param)
        sm = artist.colormap_param(
            param, values, show_values=True, value_unit=unit
        )
        if sm is not None:
            artist.fig.colorbar(sm, ax=artist.ax, label=label)

    svg = artist.to_svg()
    # 去除 XML 声明（与现有 _build_overview 处理方式一致）
    ...
    return svg
```

#### 3d. `_resolve_topology_param()` 新辅助函数

```python
def _resolve_topology_param(self, param: str) -> tuple[dict[str, Any], bool]:
    """返回 ({qubit: value}, is_bool)。

    查找顺序：
    1. built-in 6 种参数（T1, T2star, T2echo, f01, drive_efficiency, readout_fidelity）
    2. extras 字段（遍历所有 qubit 的 extras 并集）
    3. 无任何 qubit 有数据 → 返回 ({}, False)

    is_bool 判定：遍历所有非 None 的 value，全为 bool → True，全为 numeric → False
    """
```

#### 3e. `_get_all_topology_params()` 新辅助函数

```python
def _get_all_topology_params(self) -> list[str]:
    """自动检测所有可用拓扑图参数。

    1. 遍历 6 种 built-in 参数，有数据的加入列表
    2. 遍历所有 qubit 的 extras key 的并集
    3. 排序：built-in 按固定顺序先，extras 按字母顺序后
    """
```

#### 3f. `ChipArtist.draw()` 新增 `show_labels` 参数（兼顾 R3）

```python
def draw(
    self, ax: plt.Axes | None = None, show_labels: bool = True
) -> tuple[plt.Figure, plt.Axes]:
```

- `show_labels=True`（默认）→ 现有行为：灰盒子 + 黑色比特名
- `show_labels=False` → 仅灰盒子，**不画文字**

### 关联影响

- 现有 `_COLORMAP_LABELS`、`_COLORMAP_UNITS`、`_valid_colormap_params()`、`_get_colormap_values()` 保留，用于数值参数
- `annotate_fields` 从 `generate()` 签名移除，`ChipArtist.annotate()` 方法本身保留不变

---

## 四、R2 — Extras 在拓扑图上可视化

### 当前问题

extras（`bias_tunable`, `f01_max_GHz` 等）只在 qubit card 中以文字展示，不出现在芯片拓扑图中。

### 设计要求

- bool 类型（`bias_tunable`, `readout_cavity_response`, `measureable`）→ True=浅蓝，False=灰
- float/int 类型（`f01_max_GHz`, `dispersive_shift_MHz`）→ 正常 colormap 色标

### 设计

#### 4a. `ChipArtist.categorical_param()` 新方法

```python
def categorical_param(
    self,
    param_name: str,
    values: dict[str, bool],
    true_color: str = "#ADD8E6",   # 浅蓝
    false_color: str = "#D9D9D9",  # 灰
    edge_color: str = "#888888",
) -> None:
    """为布尔/分类参数着色拓扑图。

    每个比特盒子按 True/False 涂色，盒子内居中显示比特名。
    不需要 colorbar（分类数据）。
    """
```

行为详述：
- 遍历 `values` 中的每个 qubit
- `True` → `_make_box(facecolor="#ADD8E6", edgecolor="#888888")`，黑字 qubit 名
- `False` → `_make_box(facecolor="#D9D9D9", edgecolor="#AAAAAA")`，黑字 qubit 名
- 不在 `values` 中的 qubit → 不画盒子（仅显示 `draw(show_labels=False)` 的灰底）
  - 或者补画一个灰色盒子表明无数据

#### 4b. ReportGenerator 中的分发逻辑

在 `_resolve_topology_param()` 中自动判断参数类型：

```
查 built-in + extras → {qubit: raw_value}
过滤 None / 缺失 qubit
检查所有 value 的类型：
  - 全是 bool           → is_bool=True, 走 categorical_param()
  - 全是 int/float(!bool) → is_bool=False, 走 colormap_param()
  - 混合类型             → 警告并跳过
```

#### 4c. 自动检测逻辑

`_get_all_topology_params()` 收集：
1. built-in 6 种中有数据的 → 全部是数值，走 colormap
2. 所有 qubit 的 `extras` key 并集 → 按 value 类型分发

---

## 五、R3 — 去除重复比特 ID

### 当前问题

`draw()` 在每个盒子内画黑色比特名，随后 `colormap_param(show_values=True)` 又在同一位置画白色比特名+数值 → 视觉上两个 ID 叠加。

用户要求比特标识只出现一次（保留 colormap/categorical 中的 ID，去除 draw() 中的黑色 ID）。

### 设计

#### 5a. `ChipArtist.draw()` 签名扩展（同 R1 §3f）

```python
def draw(
    self, ax: plt.Axes | None = None, show_labels: bool = True
) -> tuple[plt.Figure, plt.Axes]:
```

- `show_labels=True`（默认）→ 现有行为，灰盒子 + 黑色比特名
- `show_labels=False` → 仅灰盒子，**不画文字**

#### 5b. ReportGenerator 中的调用

```python
artist.draw(show_labels=False)
```

随后 `colormap_param(show_values=True)` 或 `categorical_param()` 中的文字成为唯一的比特标识。

---

## 六、R4 — Data Sources 表头居中对齐 + 去除缩写

### 当前问题

1. 实验类型 check mark（✓ / —）和表头对齐不一致：表头 `text-align: left`，check mark `text-align: center`
2. 表头使用缩写："RO"（Readout）、"DE"（Drive Efficiency）

### 设计

#### 6a. CSS 修改（`_CSS` 内）

```css
/* 改前 */
table.sources th { text-align: left; ... }

/* 改后 */
table.sources th { text-align: center; ... }
```

#### 6b. 表头文本修改（`_build_sources_table()` 内）

```python
# 改前
<th>RO</th><th>DE</th>

# 改后
<th>Readout</th><th>Drive Eff</th>
```

完整表头（改后）：
```
Source Exp | Qubits | T1 | T2* | T2 echo | f01 | Readout | Drive Eff
```

---

## 七、实施顺序

```
Phase A: R3 (draw show_labels)     ── chip_plot.py 独立改动
Phase B: R2 (categorical_param)    ── chip_plot.py 独立改动
Phase C: R1 (多图 loop)            ── generator.py，依赖 Phase A+B
Phase D: R4 (CSS + 表头)           ── generator.py，独立
```

Phase A+B 可并行（均仅改 chip_plot.py）；Phase C 依赖 A+B；Phase D 与 C 可并行。

---

## 八、测试计划

全部在 `tests/test_phase3.py` 中新增：

### R1 — 多图拓扑
| 测试 | 说明 |
|------|------|
| `test_generate_multi_figure` | `generate()` 默认生成多张 SVG（≥ 2 张） |
| `test_generate_topology_params_auto` | `topology_params=None` 自动检测所有参数 |
| `test_generate_topology_params_explicit` | 指定参数列表仅生成对应的图 |
| `test_overview_no_annotate` | HTML 中不含 `annotate()` 产生的文本 |

### R2 — Extras 拓扑可视化
| 测试 | 说明 |
|------|------|
| `test_categorical_param_bool` | bool extras 使用 `categorical_param()`，True=浅蓝/False=灰 |
| `test_categorical_param_labels` | 分类图中比特名显示在盒子内 |
| `test_extras_numeric_colormap` | 数值 extras（f01_max_GHz）走 colormap + colorbar |
| `test_extras_bool_vs_numeric_dispatch` | 同一报告中 bool 和 numeric extras 分别处理 |

### R3 — 去除重复比特 ID
| 测试 | 说明 |
|------|------|
| `test_draw_show_labels_false` | `draw(show_labels=False)` 不含 qubit 名文本 |
| `test_draw_show_labels_true_default` | 默认 `show_labels=True`，向后兼容 |

### R4 — Data Sources 样式
| 测试 | 说明 |
|------|------|
| `test_sources_header_center_aligned` | CSS 中 `table.sources th { text-align: center }` |
| `test_sources_header_no_abbrev` | 表头不含 "RO" 或 "DE"，含 "Readout" 和 "Drive Eff" |

---

## 九、向后兼容性

| 改动 | 兼容策略 |
|------|---------|
| `draw(show_labels)` | 默认 `True`，现有调用方不变 |
| `generate(topology_params)` | 新参数名，旧 `colormap_param` 移除 — **breaking change**，仅 report 生成受影响 |
| `ChipArtist.categorical_param()` | 纯新增，不影响现有 API |
| `annotate_fields` 从 generate() 移除 | `ChipArtist.annotate()` 方法保留，独立使用仍可用 |

---

## 十、验证

```bash
python -m pytest tests/test_phase3.py tests/ -v --tb=short
# 预期：226 + ~13 新增 ≈ 239 passed
```

---

> **设计文档版本**：v1
> **关联文档**：[requirements.md](../requirements.md) | [phase-5-design.md](phase-5-design.md)
> **下一环节**：实现侧 Claude Code 按本文档实施，完成后 Supervisor 审查
