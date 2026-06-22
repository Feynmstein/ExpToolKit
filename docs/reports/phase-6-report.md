# Phase 6 工作报告 — 报告增强 + 多图拓扑 + Extras 可视化

**报告日期**：2026-06-18  
**执行会话**：2026-06-18（同日完成）  
**设计基准**：[`phase-6-design.md`](../designs/phase-6-design.md)  
**总耗时代码量**：~150 行核心改动 + ~200 行测试  
**最终测试**：236 passed / 236 collected（Phase 1+2+3+4+5+6，累计零回归）

---

## 一、需求覆盖

| 需求 | 说明 | 状态 |
|------|------|------|
| R1 | 每参数一张独立拓扑图（不用 annotate），报告只有一个 .html | ✅ |
| R2 | extras bool 用浅蓝/灰标识，float/int 用色标 | ✅ |
| R3 | 去除 draw() 中的黑色比特 ID（只保留 colormap 中的白色 ID） | ✅ |
| R4 | Data Sources 表头居中对齐 + 不用缩写 | ✅ |

---

## 二、交付物清单

### 2.1 R3 — `ChipArtist.draw(show_labels)` 

**文件**：`exp_toolkit/visualization/chip_plot.py:349`

```python
# 改前
def draw(self, ax: plt.Axes | None = None) -> tuple[plt.Figure, plt.Axes]:

# 改后
def draw(self, ax: plt.Axes | None = None, show_labels: bool = True,
         ) -> tuple[plt.Figure, plt.Axes]:
```

行为：
- `show_labels=True`（默认）→ 现有行为：灰盒子 + 黑色比特名
- `show_labels=False` → 仅灰盒子，不画文字
- `ax.text()` 调用被 `if show_labels:` 条件包裹

向后兼容：默认值 `True`，所有现有调用方不受影响。

### 2.2 R2 — `ChipArtist.categorical_param()` 新方法

**文件**：`exp_toolkit/visualization/chip_plot.py:541`

```python
def categorical_param(
    self,
    param_name: str,
    values: dict[str, bool],
    true_color: str = "#ADD8E6",   # 浅蓝
    false_color: str = "#D9D9D9",  # 灰
    edge_color: str = "#888888",
) -> None:
```

行为：
- 遍历 `values` 中的每个 qubit
- `True` → `_make_box(facecolor="#ADD8E6", edgecolor="#888888")`，黑字 qubit 名
- `False` → `_make_box(facecolor="#D9D9D9", edgecolor="#AAAAAA")`，黑字 qubit 名
- 不在 `values` 中的 qubit → 跳过（保留 `draw(show_labels=False)` 的灰底）
- 不需要 colorbar（分类数据）
- 所有 patches 和 texts 加入 `_overlay_patches`，支持 `reset()` 清除

### 2.3 R1 — 报告多参数独立拓扑图

**文件**：`exp_toolkit/report/generator.py`

#### 3a. `generate()` 签名变更

```python
# 改前
def generate(self, output_path, *, title=None, sections=None,
             colormap_param: str = "f01",
             annotate_fields: list[str] | None = None) -> Path:

# 改后
def generate(self, output_path, *, title=None, sections=None,
             topology_params: list[str] | None = None) -> Path:
```

- `colormap_param` 移除（breaking change，仅 report 生成受影响）
- `annotate_fields` 移除（`ChipArtist.annotate()` 方法和 `_get_annotate_values()` 保留给独立使用场景）
- `topology_params=None` → 自动检测所有可用参数
- `topology_params=["T1", "T2star", ...]` → 仅生成指定参数的图
- 非法参数名抛出 `ValueError`（match="topology"）

#### 3b. 新增 `_get_all_topology_params()` 

```python
def _get_all_topology_params(self) -> list[str]:
```

收集逻辑：
1. 遍历 6 种 built-in 参数（`_COLORMAP_LABELS` 的 key），有数据的加入列表
2. 遍历所有 qubit 的 `extras` key 的并集（不限于已测比特）
3. 排序：built-in 按 `_COLORMAP_LABELS` 固定顺序在前，extras 按字母顺序在后

#### 3c. 新增 `_resolve_topology_param()`

```python
def _resolve_topology_param(self, param: str) -> tuple[dict[str, Any], bool]:
```

返回 `({qubit: value}, is_bool)`：
- 内置参数 → 通过 `_get_colormap_values()` 获取，`is_bool=False`
- extras 字段 → 遍历所有 qubit 收集值
  - 全部为 `bool` → `is_bool=True`
  - 全部为 `int/float`（非 bool）→ `is_bool=False`，转为 `float`
  - 混合类型 → 返回 `({}, False)`，静默跳过
- 无数据 → 返回 `({}, False)`

#### 3d. 新增 `_build_single_topology_figure()`

```python
def _build_single_topology_figure(self, param: str) -> str | None:
```

单参数拓扑图生成：
1. 调用 `_resolve_topology_param(param)` → `(values, is_bool)`
2. 无数据返回 `None`
3. 创建新 `ChipArtist`，调用 `draw(show_labels=False)`（R3：不画黑色 ID）
4. `is_bool=True` → `artist.categorical_param(param, values)`
5. `is_bool=False` → `artist.colormap_param(param, values, show_values=True, value_unit=...)` + `fig.colorbar()`
6. 返回 SVG 字符串（已去除 XML 声明）

#### 3e. `_build_overview()` 重写

```python
def _build_overview(self, topology_params: list[str]) -> str:
```

改为循环：每个参数生成一个 `<section id="overview-{param}">` + `<h2>1. Chip Topology — {label}</h2>` + `<figure>{svg}</figure>`。

不再使用 `_OVERVIEW_SECTION` 模板（已删除），HTML 在方法内直接拼接。

#### 3f. 验证逻辑变更

```python
# 改前：验证单个 colormap_param
valid_cmap_params = self._valid_colormap_params()
if colormap_param not in valid_cmap_params: ...

# 改后：验证 topology_params 列表
all_params = self._get_all_topology_params()
if topology_params is None:
    topology_params = all_params  # 自动检测
else:
    for p in topology_params:
        if p not in all_params: raise ValueError(...)
```

### 2.4 R4 — Data Sources 表头样式

**文件**：`exp_toolkit/report/generator.py`

#### 4a. CSS 拆分（`th` / `td` 分离）

```css
/* 改前 */
table.sources th, table.sources td { text-align: left; ... }
table.sources th { background: #f0f0f0; font-weight: 600; }

/* 改后 */
table.sources th { text-align: center; ... background: #f0f0f0; font-weight: 600; }
table.sources td { text-align: left; ... }
```

- `th` → `text-align: center`（表头居中）
- `td` → `text-align: left`（数据列保持左对齐）
- `td.check` / `td.empty` 的 `text-align: center` 覆盖不受影响

#### 4b. 表头文本

```html
<!-- 改前 -->
<th>RO</th><th>DE</th>

<!-- 改后 -->
<th>Readout</th><th>Drive Eff</th>
```

完整表头：`Source Exp | Qubits | T1 | T2* | T2 echo | f01 | Readout | Drive Eff`

---

## 三、架构合规性

| # | 约定 | 合规 |
|---|------|------|
| 1 | 拟合与持久化解耦 | ✅ 本次改动不涉及拟合模块 |
| 3 | 拟合模块不自动持久化 | ✅ 未修改任何持久化行为 |
| 4 | 芯片拓扑不硬编码坐标 | ✅ `ChipTopology` 未变 |
| 5 | 参数标注测量条件 | ✅ extras 为工程判定标志，不涉及 freq_GHz/timestamp |
| — | 类型标注完整 | ✅ 所有新方法有完整类型标注 |
| — | 面向对象 API | ✅ matplotlib 仅通过 `ax.add_patch()` / `ax.text()` |
| — | draw(show_labels) 默认 True | ✅ 向后兼容，现有调用方不受影响 |
| — | ChipArtist.annotate() 保留 | ✅ 方法未移除，独立使用仍可用 |

---

## 四、Breaking Changes

| 改动 | 影响范围 | 迁移方案 |
|------|---------|---------|
| `generate(colormap_param=)` 移除 | 报告生成调用方 | 改为 `generate(topology_params=["T1"])` |
| `generate(annotate_fields=)` 移除 | 报告生成调用方 | 每个参数已有独立拓扑图，不再需要 annotate |
| `_OVERVIEW_SECTION` 模板删除 | 无（模块私有） | 不影响外部调用方 |

---

## 五、测试覆盖

全部在 `tests/test_phase3.py` 中新增，文件从 Phase 5 的 51 用例扩展至 61 用例（+12 新，-3 旧 annotate 测试，+1 annotate 替换测试，净增 +10）。

### 5.1 R1 — `TestMultiFigureTopology`（3 用例）

| 测试 | 说明 |
|------|------|
| `test_generate_multi_figure` | 默认生成多张 SVG（≥ 2 张），多 section |
| `test_generate_topology_params_auto` | `topology_params=None` 自动检测 built-in + extras |
| `test_generate_topology_params_explicit` | 指定参数列表仅生成对应的图，其他不出现 |

### 5.2 R1 补充 — `TestAnnotateFields` 替换（1 用例）

| 测试 | 说明 |
|------|------|
| `test_overview_no_annotate_text` | HTML 中不含 `T1=45.20` 等 annotate 文本 |

### 5.3 R2 — `TestExtrasTopologyVisualization`（4 用例）

| 测试 | 说明 |
|------|------|
| `test_categorical_param_bool` | `_resolve_topology_param` 正确识别 bool extras，`is_bool=True` |
| `test_categorical_param_labels` | 分类图报告中包含比特名和 SVG |
| `test_extras_numeric_colormap` | 数值 extras（f01_max_GHz）`is_bool=False`，值正确提取 |
| `test_extras_bool_vs_numeric_dispatch` | 同一报告 bool 和 numeric extras 分别处理，各生成独立 SVG |

### 5.4 R3 — `TestDrawShowLabels`（3 用例）

| 测试 | 说明 |
|------|------|
| `test_draw_show_labels_false` | `draw(show_labels=False)` 无 qubit 名文本 |
| `test_draw_show_labels_true_default` | 默认 `show_labels=True`，向后兼容，4 个 qubit 名 |
| `test_draw_show_labels_false_still_draws_boxes` | 无文本但仍绘制 FancyBboxPatch |

### 5.5 R4 — `TestSourcesTableStyle`（2 用例）

| 测试 | 说明 |
|------|------|
| `test_sources_header_center_aligned` | CSS 中 `table.sources th { text-align: center }` |
| `test_sources_header_no_abbrev` | 表头不含 `>RO<` 或 `>DE<`，含 `Readout` 和 `Drive Eff` |

---

## 六、边界情况与设计取舍

### 6.1 已处理的边界

| 场景 | 处理 |
|------|------|
| extras 混合类型（部分 bool 部分 numeric） | `_resolve_topology_param()` 静默返回 `({}, False)`，跳过该参数 |
| extras key 在所有 qubit 上均无值 | 返回空 dict，不在 `_get_all_topology_params()` 中出现 |
| topology_params 为空列表 | overview section 为空字符串，其他 sections 正常生成 |
| 旧 JSON 无 extras 键 | `qs.extras` 默认为空 dict，不影响参数收集 |
| draw(show_labels=False) 后再调 colormap_param | colormap 中的白色文本成为唯一标识，无重复 ID |
| extras 在未测量比特上有值 | `_resolve_topology_param` 遍历所有 qubit（不限于已测），未测比特也会出现在拓扑图中 |

### 6.2 设计决策

1. **每参数独立 ChipArtist** — 每张拓扑图创建新的 `ChipArtist` 实例，避免叠加层累积和 reset 竞态。代价是每张图重新创建 Figure，但报告生成非性能关键路径
2. **categorical_param 不画无数据比特** — bool 参数对无数据比特保持 `draw(show_labels=False)` 的灰色底盒，视觉上区别于 False 的显式灰色（边缘不同：`#888888` vs `#AAAAAA`）
3. **_get_all_topology_params 遍历所有 qubit** — extras 收集不限于已测比特，确保 `measureable=False` 等未测比特的 extras 也能生成拓扑图
4. **built-in 参数保持固定顺序** — 按 `_COLORMAP_LABELS` 的 key 顺序排列，确保报告一致性；extras 按字母顺序排列，可预测
5. **annotate 从 generate() 移除但方法保留** — `ChipArtist.annotate()` 和 `_get_annotate_values()` 仍可用于脚本中手动生成带标注的独立图

---

## 七、端到端验证

使用真实数据 `data/chip_state_RICON_rebonded.json`（6 个已测比特 + 19 个未测比特）验证：

```
Auto-detected params (8): T1, T2star, T2echo, bias_tunable,
                          dispersive_shift_MHz, f01_max_GHz,
                          measureable, readout_cavity_response
SVG count: 8 (每参数一张)
Topology sections: 8 (每参数一个 section)
Readout (not RO): ✅
Drive Eff (not DE): ✅
th text-align center: ✅
报告大小: 397 KB
```

分发逻辑：
- 内置 3 个（T1, T2star, T2echo）→ colormap + colorbar
- 数值 extras 2 个（dispersive_shift_MHz, f01_max_GHz）→ colormap + colorbar
- bool extras 3 个（bias_tunable, measureable, readout_cavity_response）→ categorical_param（浅蓝/灰）

---

## 八、未来方向（不在本次范围）

| 项目 | 说明 |
|------|------|
| topology_params 通配符/分组 | 支持 `"T*"` 通配符或预定义分组（"lifetime" = T1+T2*+T2echo） |
| 分类参数支持多类别 | 当前仅 True/False 二值，未来可扩展 multi-category 色板 |
| colorbar 复用 | 多张同类型色标图可共享 colorbar 范围 |
| CZ 门保真度 / EdgeState | 需要 `EdgeState` 数据类 + 新 JSON section，等真实数据到达时实现 |
| 增量报告更新 | 仅重绘数据变化的参数图，避免全量重生成 |

---

> **报告版本**：v1  
> **关联文档**：[`phase-6-design.md`](../designs/phase-6-design.md) | [`phase-5-design.md`](../designs/phase-5-design.md) | [`requirements.md`](../requirements.md)  
> **下一环节**：Supervisor 审查本报告 + 代码 diff，对照设计文档检查一致性

---

## 九、审查记录

### 9.1 Phase 6 完成审查（2026-06-18）

> **审查报告**：[`docs/reviews/008-phase6-review.md`](../reviews/008-phase6-review.md)  
> **总体判定**：Phase 6 可以验收。零 P1/P2/P3 问题。Phase 1–6 首次零问题审查。  
> **设计一致性**：4/4 子需求完全吻合设计文档，零设计偏离，3 处合理增强。  
> **测试**：236/236 passed（+10 Phase 6），零回归。  
> **架构合规**：全部通过。Phase 1–6 累计 236 tests，8 次审查闭环。
