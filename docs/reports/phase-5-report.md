# Phase 5 工作报告 — 芯片拓扑增强 + State 扩展 + 报告改进

**报告日期**：2026-06-18  
**执行会话**：2026-06-18（同日完成）  
**设计基准**：[`phase-5-design.md`](../designs/phase-5-design.md)  
**总耗时代码量**：~80 行核心改动 + ~270 行测试  
**最终测试**：226 passed / 226 collected（Phase 1+2+3+4+5，累计零回归）

---

## 一、需求覆盖

| 需求 | 说明 | 状态 |
|------|------|------|
| R1 | 手动编辑 `chip_state.json` 后 `last_updated` 不被覆盖 | ✅ |
| R2 | 自定义参数字段 `QubitState.extras` | ✅ |
| R3a | 圆形 → 圆角矩形 `FancyBboxPatch` | ✅ |
| R3b | `colormap_param()` 内显示参数值 | ✅ |
| R3c | ReportGenerator 色标扩展（T2echo, drive_efficiency） | ✅ |
| R3d | `annotate_fields` 接线 | ✅ |
| R4 | qubit card 始终展示全部参数行（缺失显示"No data"） | ✅ |

---

## 二、交付物清单

### 2.1 R1 — `save()` 保留用户手动设置的 `last_updated`

**文件**：`exp_toolkit/state/chip_state.py:369`

```python
# 改前
"last_updated": date.today().isoformat(),
# 改后
"last_updated": self.last_updated or date.today().isoformat(),
```

`None` 时回退到今天；用户通过 `load()` 加载的已有值被保留。

### 2.2 R2 — `QubitState.extras` + `ChipState.set_extras()`

**文件**：`exp_toolkit/state/chip_state.py`

| 改动 | 位置 | 说明 |
|------|------|------|
| `QubitState.extras: dict[str, Any]` | dataclass 字段 | 默认 `field(default_factory=dict)` |
| `save()` 序列化 | line 365 | `if qs.extras: qj["extras"] = qs.extras` — 空 dict 省略 |
| `load()` 反序列化 | line 295 | `qs.extras = qdata.get("extras", {})` — 兼容旧 JSON |
| `ChipState.set_extras(qubit, **kwargs)` | 新方法 | 合并更新，保留已有键 |

### 2.3 R3a — 圆形 → 圆角矩形 `FancyBboxPatch`

**文件**：`exp_toolkit/visualization/chip_plot.py`

| 改动 | 说明 |
|------|------|
| `from matplotlib.patches import FancyBboxPatch` | 新增 import |
| `_BOX_WIDTH = 0.7, _BOX_HEIGHT = 0.525` | 圆角矩形尺寸（宽高比 4:3） |
| `_make_box(x, y, facecolor, edgecolor, ...)` | 工厂方法，返回 `FancyBboxPatch` |
| `draw()` 替换 `plt.Circle` → `_make_box()` | 基础拓扑绘制 |
| `highlight_measured()` 替换 → `_make_box()` | 测量覆盖高亮 |
| `colormap_param()` 替换 → `_make_box()` | 参数色标图 |
| `annotate()` 偏移量: `_RADIUS` → `_BOX_HEIGHT / 2` | 标注位置适配矩形 |

### 2.4 R3b — `colormap_param()` 内显示参数值

**文件**：`exp_toolkit/visualization/chip_plot.py`

新增参数：
```python
def colormap_param(self, ..., show_values: bool = False,
                   value_format: str = "{:.1f}",
                   value_unit: str | None = None) -> ...:
```

行为：
- `show_values=True` + 有数据 → 文本 `"Q16\n45.2 μs"`，白色文字
- `show_values=True` + 无数据 → 文本 `"Q16"`，黑色文字
- `show_values=False` → 原有行为，文本颜色根据有无数据自适应（白/黑）

### 2.5 R3c — ReportGenerator 色标扩展

**文件**：`exp_toolkit/report/generator.py`

| 改动 | 说明 |
|------|------|
| `_COLORMAP_LABELS` 新增 | `"T2echo": "T2 echo (μs)"`, `"drive_efficiency": "Drive Efficiency (a.u.)"` |
| `_COLORMAP_UNITS` 新增 | 6 种内置参数的单位映射 |
| `_get_colormap_values()` 扩展 | T2echo → `T2echo_us[-1].value`；drive_efficiency → `drive_efficiency[-1].product`；extras 数值回退 |
| `_valid_colormap_params()` 新增 | 动态收集：内置 6 种 + 所有 qubit extras 中的数值 key |
| `generate()` 验证 | 从硬编码 4 种改为动态 `_valid_colormap_params()` |
| `_build_overview()` | 传入 `show_values=True` + `value_unit`（含 annotate_fields 接线） |

### 2.6 R3d — `annotate_fields` 接线

**文件**：`exp_toolkit/report/generator.py`

| 改动 | 说明 |
|------|------|
| `_get_annotate_values(state, fields)` | 新辅助函数，提取 built-in（f01/f01_max/f01_min/T1/T2star/T2echo/drive_efficiency/readout_fidelity）+ extras 值 |
| `generate(annotate_fields: list[str] | None = None)` | 新增参数 |
| `_build_overview(colormap_param, annotate_fields)` | 接收并传递给 `artist.annotate()` |

### 2.7 R4 — qubit card 始终展示全部参数行

**文件**：`exp_toolkit/report/generator.py`

| 改动 | 说明 |
|------|------|
| CSS `.qubit-card td.missing` | `color: #cc6666; font-style: italic;` |
| `_make_missing_row(label)` | 新辅助函数，生成 `<td class="missing" colspan="3">No data</td>` |
| `_build_qubit_card()` 重写 | 6 个固定参数行（f01, T1, T2*, T2 echo, Drive Eff, Readout）**始终渲染**；有数据显示值，无数据显示 "No data" |
| extras 标志 | bool → "Yes"/"No"；其他 → `str(val)`；按 key 排序 |

---

## 三、架构合规性

| # | 约定 | 合规 |
|---|------|------|
| 1 | 拟合与持久化解耦 | ✅ 本次改动不涉及拟合模块 |
| 3 | 拟合模块不自动持久化 | ✅ `set_extras()` 仅写内存，需手动 `save()` |
| 4 | 芯片拓扑不硬编码坐标 | ✅ `ChipTopology` 未变，`_make_box()` 使用拓扑坐标 |
| 5 | 参数标注测量条件 | ✅ extras 为工程判定标志，非测量参数，不涉及 freq_GHz/timestamp |
| — | 类型标注完整 | ✅ 所有新方法有完整类型标注 |
| — | 面向对象 API | ✅ matplotlib 仅通过 `ax.add_patch()` / `ax.text()` |

---

## 四、测试覆盖

全部在 `tests/test_phase3.py` 中新增，文件从 22 用例扩展至 51 用例（+29）。

### 4.1 R1 — `TestSaveLastUpdated`（2 用例）

| 测试 | 说明 |
|------|------|
| `test_save_preserves_last_updated` | 手动设置后被 `save()`/`load()` 保留 |
| `test_save_defaults_when_none` | `None` 时回退当天日期 |

### 4.2 R2 — `TestExtras`（4 用例）

| 测试 | 说明 |
|------|------|
| `test_extras_roundtrip` | `set_extras` → `save` → `load` 完整往返 |
| `test_extras_empty_default` | 新 `QubitState` 的 `extras` 为空 dict |
| `test_old_json_no_extras` | 旧 JSON 无 extras 键兼容 |
| `test_set_extras_merge` | 多次调用合并而非覆盖 |

### 4.3 R3a — `TestFancyBboxPatch`（4 用例）

| 测试 | 说明 |
|------|------|
| `test_draw_uses_fancybbox` | `draw()` 使用 `FancyBboxPatch` |
| `test_box_dimensions` | 尺寸 = `_BOX_WIDTH × _BOX_HEIGHT` |
| `test_highlight_measured_uses_fancybbox` | `highlight_measured()` 无 `Circle` |
| `test_colormap_param_uses_fancybbox` | `colormap_param()` 无 `Circle` |

### 4.4 R3b — `TestColormapShowValues`（4 用例）

| 测试 | 说明 |
|------|------|
| `test_colormap_show_values` | 文本含 `45.2 μs` |
| `test_colormap_no_show_values` | 默认仅显示比特名 |
| `test_colormap_show_values_missing_data` | 无数据比特仅显示名称 |
| `test_colormap_show_values_no_unit` | `value_unit=None` 时不添加单位 |

### 4.5 R3c — `TestReportColormapExpansion`（7 用例）

| 测试 | 说明 |
|------|------|
| `test_colormap_T2echo` | T2echo 色标报告生成 |
| `test_colormap_drive_efficiency` | drive_efficiency 色标报告生成 |
| `test_colormap_values_T2echo` | `_get_colormap_values` 提取 T2echo |
| `test_colormap_values_drive_efficiency` | 验证 product = pi_amp × pi_width_ns |
| `test_colormap_extras_numeric` | extras 数值字段可用作色标 |
| `test_colormap_extras_bool_rejected` | 布尔值不被当作数值色标 |
| `test_colormap_invalid_raises` | 非法参数仍抛出 `ValueError` |

### 4.6 R3d — `TestAnnotateFields`（3 用例）

| 测试 | 说明 |
|------|------|
| `test_generate_with_annotate_fields` | 标注字段出现在 SVG |
| `test_annotate_extras_field` | extras 字段可用于标注 |
| `test_annotate_nonexistent_field` | 不存在字段不导致错误 |

### 4.7 R4 — `TestQubitCardAllRows`（5 用例）

| 测试 | 说明 |
|------|------|
| `test_card_all_rows_present` | 6 个参数行标签全部出现 |
| `test_missing_data_css` | "No data" + `class="missing"` + CSS |
| `test_card_extras_flags` | bool → "Yes"/"No" |
| `test_no_data_card` | 部分数据比特的缺失行数 ≥ 5 |
| `test_overview_shows_values` | 概述图内嵌参数值 |

---

## 五、边界情况与设计取舍

### 5.1 已处理的边界

| 场景 | 处理 |
|------|------|
| 旧 JSON 无 `extras` 键 | `load()` 使用 `.get("extras", {})` 回退空 dict |
| extras 空 dict | `save()` 条件写入，不产生冗余 JSON |
| extras 布尔值用做色标 | `_get_colormap_values()` 过滤 `bool`（`isinstance(True, int)` 陷阱） |
| colormap 参数是 extras key | `_valid_colormap_params()` 动态收集；`_COLORMAP_LABELS` 无则使用 raw key |
| annotate 字段不存在 | 静默跳过，不报错 |
| qubit 仅有部分参数 | 6 行全部渲染，缺失行显示 "No data" |

### 5.2 设计决策

1. **extras 不设新 Entry 类型** — 与测量参数（需 value/error/freq_GHz/timestamp/source_exp）不同，extras 是静态工程判定，简单 key-value 足够
2. **圆角矩形尺寸 0.7×0.525** — 宽高比约 4:3，容纳 `Q16\n45.2 μs`（8pt 字体），1.0 间距下无重叠
3. **"No data" vs 沉默跳过** — 用户确认"全部展示"，固定卡结构便于对比不同比特的数据完整度
4. **text_color 自适应** — 有色背景白色文字，灰色背景黑色文字（`show_values` 时强制；否则自动适配）
5. **`_COLORMAP_LABELS` vs `_COLORMAP_UNITS`** — 标签含完整格式（供 colorbar），单位独立（供 `value_unit` 拼接），职责分离

---

## 六、未来方向（不在本次范围）

| 项目 | 说明 |
|------|------|
| CZ 门保真度 / `EdgeState` | 需要 `EdgeState` 数据类 + 新 JSON section，等真实数据到达时实现 |
| `flags` 异常标注机制 | 当前以"No data"本身为异常信号，暂不引入显式 flag |
| extras 类型校验 | 当前信任调用方传入 JSON 基本类型，后续可加运行时 schema 验证 |
| 多芯片支持 | `ChipState` 当前单芯片，未来可扩展为 `ChipStateCollection` |

---

> **报告版本**：v1  
> **关联文档**：[`phase-5-design.md`](../designs/phase-5-design.md) | [`requirements.md`](../requirements.md)  
> **下一环节**：Supervisor 审查本报告 + 代码 diff，对照设计文档检查一致性

---

## 七、审查记录

### 7.1 Phase 5 完成审查（2026-06-18）

> **审查报告**：[`docs/reviews/007-phase5-review.md`](../reviews/007-phase5-review.md)  
> **总体判定**：Phase 5 可以验收。无 P1/P2 阻塞项。1 个 P3（docstring 残留"圆圈"术语）。  
> **设计一致性**：7/7 子需求完全吻合设计文档，零设计偏离，4 处合理增强。  
> **测试**：226/226 passed（+29 Phase 5），零回归。  
> **架构合规**：全部通过。Phase 1–5 累计 226 tests，7 次审查闭环。
