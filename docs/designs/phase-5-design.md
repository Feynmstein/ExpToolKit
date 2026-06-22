# Phase 5 设计文档 — 芯片拓扑增强 + State 扩展 + 报告改进

**设计日期**：2026-06-18  
**设计来源**：Supervisor 审查会话（需求讨论 + 分析）  
**实现会话**：待指派  
**需求基准**：4 项用户需求（经 Supervisor 确认范围）

---

## 需求背景

用户提出 4 项改进需求，经 Supervisor 分析后确认范围为：

| 需求 | 判定 | 范围 |
|------|------|------|
| R1: 手动编辑 chip_state.json | ✅ 已基本支持 | 修复 `save()` 覆盖 `last_updated` 的问题 |
| R2: 自定义参数字段 | ❌ 不支持 | 新增 `QubitState.extras`（JSON 基本类型），save/load 支持 |
| R3: 手动指定展示参数 | 🟡 部分支持 | 圆形→圆角矩形、参数值显示、色标扩展、annotate 接线 |
| R4: 缺失参数标注 | ❌ 不支持 | qubit card 始终展示全部参数行（缺失显示"No data"） |

**不在本次范围**：
- CZ 门保真度 / `EdgeState`（后续需要时按固定字段新增）
- `flags` 异常标注机制（以"无数据"本身为异常信号）
- `extras` 限制为 JSON 基本类型（bool/str/float/int），当前仅需 `readout_cavity_response`、`bias_tunable` 两个布尔标志

---

## 一、R1 — save() 保留用户手动设置的 last_updated

**文件**：`exp_toolkit/state/chip_state.py:369`

```python
# 改前
"last_updated": date.today().isoformat(),
# 改后
"last_updated": self.last_updated or date.today().isoformat(),
```

`None` 时回退到今天；用户通过 `load()` 加载的已有值被保留。

---

## 二、R2 — QubitState.extras

**文件**：`exp_toolkit/state/chip_state.py`

### 2a. QubitState 新增字段 (line 151)
```python
extras: dict[str, Any] = field(default_factory=dict)
```

### 2b. save() 序列化（条件写入，空 dict 省略）
```python
if qs.extras:
    qj["extras"] = qs.extras
```

### 2c. load() 反序列化（兼容旧 JSON 无 extras 键）
```python
qs.extras = qdata.get("extras", {})
```

### 2d. ChipState 新增 set_extras() 方法
```python
def set_extras(self, qubit: str, **kwargs: Any) -> None:
    """Set extra qubit properties (e.g. readout_cavity_response, bias_tunable).
    Existing keys not in kwargs are preserved.
    Values must be JSON-serializable (bool, str, float, int)."""
    qs = self._ensure_qubit(qubit)
    qs.extras.update(kwargs)
```

### 预期 JSON
```json
{
  "qubits": {
    "Q16": {
      "T1_us": [...],
      "extras": {
        "readout_cavity_response": true,
        "bias_tunable": false
      }
    }
  }
}
```

---

## 三、R3a — 圆形 → 圆角矩形 (FancyBboxPatch)

**文件**：`exp_toolkit/visualization/chip_plot.py`

### 设计依据
- 用户偏好圆角矩形以提供更大的文本显示空间
- 网格间距 1.0 单位 → 矩形尺寸 0.7×0.525（宽高比约 4:3）
- 水平间隙 0.3 单位、垂直间隙 0.475 单位，无重叠风险

### 3a.1 新增 import + 常量
```python
from matplotlib.patches import FancyBboxPatch

_BOX_WIDTH = 0.7     # 2 × _RADIUS
_BOX_HEIGHT = 0.525   # 1.5 × _RADIUS，容纳双行文本
```

### 3a.2 新增 `_make_box()` 工厂方法
```python
def _make_box(self, x, y, facecolor, edgecolor, linewidth=1.5, zorder=2):
    """Create a rounded-rectangle patch for a qubit centered at (x, y)."""
    return FancyBboxPatch(
        (x - self._BOX_WIDTH / 2, y - self._BOX_HEIGHT / 2),
        self._BOX_WIDTH, self._BOX_HEIGHT,
        boxstyle="round,pad=0.02",
        facecolor=facecolor, edgecolor=edgecolor,
        linewidth=linewidth, zorder=zorder,
    )
```

### 3a.3 替换三处 `plt.Circle`
| 方法 | 行号 | 改动 |
|------|------|------|
| `draw()` | 369–376 | `box = self._make_box(x, y, "#D9D9D9", "#888888")` |
| `highlight_measured()` | 415–422 | `box = self._make_box(x, y, color, "#333333")` |
| `colormap_param()` | 486–490 | `box = self._make_box(x, y, fc, ec)` |

### 3a.4 annotate() 偏移量更新 (line 568)
```python
# 改前: y - self._RADIUS - 0.15
# 改后: y - self._BOX_HEIGHT / 2 - 0.15
```

---

## 四、R3b — colormap_param() 内显示参数值

**文件**：`exp_toolkit/visualization/chip_plot.py`

### 4a. 签名扩展
```python
def colormap_param(
    self,
    param_name: str,
    values: dict[str, float],
    cmap: str = "viridis",
    vmin: float | None = None,
    vmax: float | None = None,
    show_values: bool = False,         # 新增
    value_format: str = "{:.1f}",       # 新增
    value_unit: str | None = None,      # 新增
) -> matplotlib.cm.ScalarMappable | None:
```

### 4b. 文本逻辑
当 `show_values=True` 且有数据时，文本从 `"Q16"` 变为 `"Q16\n45.2 μs"`：
- 有色背景（有参数值）→ 白色文字
- 灰色背景（无数据）→ 黑色文字
- 用户偏好**完整格式**（含单位）

---

## 五、R3c — ReportGenerator 色标扩展

**文件**：`exp_toolkit/report/generator.py`

### 5a. `_COLORMAP_LABELS` 新增
```python
"T2echo": "T2 echo (μs)",
"drive_efficiency": "Drive Efficiency (a.u.)",
```

### 5b. 新增 `_COLORMAP_UNITS`
```python
_COLORMAP_UNITS = {
    "f01": "GHz", "T1": "μs", "T2star": "μs", "T2echo": "μs",
    "drive_efficiency": "", "readout_fidelity": "",
}
```

### 5c. `_get_colormap_values()` 扩展
- `T2echo` → `qs.T2echo_us[-1].value`
- `drive_efficiency` → `qs.drive_efficiency[-1].product`
- extras 数值字段回退：`isinstance(val, (int, float)) and not isinstance(val, bool)` → `float(val)`

### 5d. `generate()` colormap_param 验证
从硬编码 4 种改为动态：内置 6 种 + 所有 qubit extras 中的数值 key。

### 5e. `_build_overview()` 接线
传入 `show_values=True` + `value_unit` + `annotate_fields`。

---

## 六、R3d — annotate_fields 接线

**文件**：`exp_toolkit/report/generator.py`

### 6a. 新增 `_get_annotate_values(state, fields)`
提取 built-in（f01/f01_max/f01_min/T1/T2star/T2echo/drive_efficiency/readout_fidelity）+ extras 值，返回 `dict[str, dict[str, Any]]`。

### 6b. `generate()` 新增参数
```python
annotate_fields: list[str] | None = None
```
传递给 `_build_overview()` → `artist.annotate(fields, values)`。

---

## 七、R4 — qubit card 始终展示全部参数行

**文件**：`exp_toolkit/report/generator.py`

### 7a. CSS 新增
```css
.qubit-card td.missing { color: #cc6666; font-style: italic; }
```

### 7b. `_build_qubit_card()` 重写
6 个固定参数类型（f01/T1/T2*/T2echo/Drive Eff/Readout）**始终渲染一行**：
- 有数据 → 当前格式
- 无数据 → `<td class="missing" colspan="3">No data</td>`

extras 标志展现在卡片末尾：bool → "Yes"/"No"；其他 → `str(val)`。

---

## 实现顺序

```
Phase 1 (R1) ──┐
               ├──→ chip_state.py，独立可并行
Phase 2 (R2) ──┘
               │
Phase 3 (R3a) ──→ chip_plot.py 内部重构
Phase 4 (R3b) ──→ 依赖 Phase 3
               │
Phase 5 (R3c) ──┐
Phase 6 (R4)  ──┼──→ generator.py，均依赖 Phase 2 + Phase 4
Phase 7 (R3d) ──┘
```

---

## 测试计划

全部测试在 `tests/test_phase3.py` 中新增（预计 ~20 个新测试）：

| Phase | 测试 |
|-------|------|
| R1 | `test_save_preserves_last_updated`, `test_save_defaults_when_none` |
| R2 | `test_extras_roundtrip`, `test_extras_empty_default`, `test_old_json_no_extras`, `test_set_extras_merge` |
| R3a | `test_draw_uses_fancybbox`, `test_box_dimensions` |
| R3b | `test_colormap_show_values`, `test_colormap_no_show_values` |
| R3c | `test_colormap_T2echo`, `test_colormap_drive_efficiency`, `test_colormap_extras_numeric`, `test_colormap_extras_bool_rejected`, `test_colormap_invalid_raises` |
| R3d | `test_generate_with_annotate_fields`, `test_annotate_nonexistent_field` |
| R4 | `test_card_all_rows_present`, `test_missing_data_css`, `test_card_extras_flags`, `test_no_data_card` |

---

## 关键设计决策

1. **extras 不设新 Entry 类型**：与测量参数（需要 value/error/freq_GHz/timestamp/source_exp）不同，extras 是静态的工程判定标志，简单的 key-value 足够。

2. **CZ 门保真度不在本次实现**：它属于 edge 而非 qubit，需要 `EdgeState` + 新的 JSON section。等真实数据到达时按固定字段新增。

3. **圆角矩形尺寸 0.7×0.525**：宽高比约 4:3，横向空间足够显示 `Q16\n45.2 μs`（8pt 字体），1.0 间距下无重叠。

4. **"No data" vs 沉默跳过**：用户确认"全部展示"——qubit card 固定结构有助于对比不同比特的数据完整度。

---

> **设计文档版本**：v1  
> **关联文档**：[[requirements.md]](../requirements.md) | [[006-project-review]](../reviews/006-project-review.md)  
> **下一环节**：实现会话阅读本文档后开始编码。完成后 Supervisor 进行 Phase 5 审查。
