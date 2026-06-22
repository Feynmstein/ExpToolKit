# 审查报告 #007 — Phase 5 完成审查（芯片拓扑增强 + State 扩展 + 报告改进）

**审查日期**：2026-06-18  
**审查范围**：R1–R4 全部（last_updated 修复、extras、FancyBboxPatch、colormap 扩展、annotate_fields、qubit card 全部展示）  
**审查基准**：`docs/phase-5-design.md` + `docs/requirements.md` v3 + `CLAUDE.md`  
**上一审查**：[#006](006-project-review.md)（项目全面审查）  
**审查人角色**：Supervisor（不主动写实现代码）

---

## 一、总体判定

| 维度 | 评级 | 说明 |
|------|------|------|
| 设计一致性 | 🟢 完全吻合 | 7 个子需求全部按设计文档实现，零偏离 |
| 测试覆盖 | 🟢 优秀 | 226/226 passed (4.49s)，+29 新用例，零回归 |
| 架构合规 | 🟢 合规 | extras 不耦合拟合模块，ChipArtist 与 ReportGenerator 保持解耦 |
| 代码质量 | 🟢 优秀 | 工厂方法消除重复，helper 函数职责单一，类型标注完整 |
| 边界处理 | 🟢 完善 | 旧 JSON 兼容、bool/int 陷阱、空 extras 省略、非存在字段静默 |

**结论：Phase 5 可以验收。无 P1/P2 问题。1 个 P3 建议。**

---

## 二、逐需求核验

### 2.1 R1 — save() 保留 last_updated ✅

| 项目 | 设计 | 实现 | 判定 |
|------|------|------|------|
| `save()` line 376 | `self.last_updated or date.today().isoformat()` | 完全一致 | ✅ |
| `None` → 当天 | `or` 短路求值 | 符合预期 | ✅ |
| 已有值保留 | 通过 `load()` 读入 → `save()` 不覆盖 | `test_save_preserves_last_updated` 通过 | ✅ |

### 2.2 R2 — QubitState.extras + set_extras() ✅

| 项目 | 设计位置 | 实现 | 判定 |
|------|---------|------|------|
| `extras` 字段 | `QubitState:152` | `dict[str, Any] = field(default_factory=dict)` | ✅ |
| `save()` 序列化 | 条件写入 | `if qs.extras: qj["extras"] = qs.extras` (line 368) | ✅ |
| `load()` 反序列化 | `.get("extras", {})` | line 295 | ✅ |
| `set_extras()` | 合并更新 | `qs.extras.update(kwargs)` (line 511)，保留已有键 | ✅ |
| 旧 JSON 兼容 | 缺失键 → `{}` | `test_old_json_no_extras` 通过 | ✅ |

### 2.3 R3a — 圆形 → 圆角矩形 ✅

| 项目 | 设计 | 实现 | 判定 |
|------|------|------|------|
| import | `from matplotlib.patches import FancyBboxPatch` | line 15 | ✅ |
| 尺寸常量 | `_BOX_WIDTH=0.7, _BOX_HEIGHT=0.525` | lines 290–291 | ✅ |
| 工厂方法 | `_make_box(x, y, facecolor, edgecolor, ...)` | lines 333–345，`boxstyle="round,pad=0.02"` | ✅ |
| `draw()` 替换 | `plt.Circle` → `_make_box()` | lines 386–390 | ✅ |
| `highlight_measured()` 替换 | `plt.Circle` → `_make_box()` | lines 429–433 | ✅ |
| `colormap_param()` 替换 | `plt.Circle` → `_make_box()` | lines 506–509 | ✅ |
| `annotate()` 偏移 | `_RADIUS` → `_BOX_HEIGHT / 2` | line 601 | ✅ |

**额外验证**：
- `test_draw_uses_fancybbox` — 确认 patch 为 `FancyBboxPatch` 实例 ✅
- `test_box_dimensions` — 确认尺寸 = `_BOX_WIDTH × _BOX_HEIGHT` ✅
- `test_highlight_measured_uses_fancybbox` — `highlight_measured()` 无 `Circle` ✅
- `test_colormap_param_uses_fancybbox` — `colormap_param()` 无 `Circle` ✅

### 2.4 R3b — colormap_param() 内显示参数值 ✅

| 项目 | 设计 | 实现 | 判定 |
|------|------|------|------|
| 新参数 | `show_values`, `value_format`, `value_unit` | lines 453–455 | ✅ |
| show_values=True + 有数据 | `"Q16\n45.2 μs"` + 白色文字 | lines 514–517 | ✅ |
| show_values=True + 无数据 | `"Q16"` + 黑色文字 | lines 518–520 | ✅ |
| show_values=False | 原有行为 + 自适应文字颜色 | lines 521–523 | ✅ |

**实现增强**（超出设计）：当 `show_values=False` 时，`text_color` 也根据 `has_value` 自适应（白/黑），而非简单的固定黑色。这避免了深色色标上 black text 不可读的问题——好的改进。

### 2.5 R3c — ReportGenerator 色标扩展 ✅

| 项目 | 设计 | 实现 | 判定 |
|------|------|------|------|
| `_COLORMAP_LABELS` 扩展 | T2echo + drive_efficiency | lines 228–229 | ✅ |
| `_COLORMAP_UNITS` 新增 | 6 种内置参数 | lines 233–240 | ✅ |
| `_get_colormap_values()` T2echo | `T2echo_us[-1].value` | lines 306–308 | ✅ |
| `_get_colormap_values()` drive_efficiency | `drive_efficiency[-1].product` | lines 309–311 | ✅ |
| extras 数值回退 | `isinstance(val, (int, float)) and not isinstance(val, bool)` | lines 316–319 | ✅ |
| 动态验证 | `_valid_colormap_params()` | lines 603–614 | ✅ |
| `generate()` 验证 | 动态而非硬编码 | lines 559–563 | ✅ |
| `_build_overview()` colorbar label | `_COLORMAP_LABELS.get(param, param)` 回退 | line 627 | ✅ |
| `_build_overview()` value_unit | `_COLORMAP_UNITS.get(param)` | line 628 | ✅ |

**bool 陷阱处理正确**：`isinstance(True, int)` 为 `True`，代码显式排除了 bool。`test_colormap_extras_bool_rejected` 验证通过。

### 2.6 R3d — annotate_fields 接线 ✅

| 项目 | 设计 | 实现 | 判定 |
|------|------|------|------|
| `_get_annotate_values()` | 提取 built-in + extras | lines 243–285 | ✅ |
| `generate()` 新参数 | `annotate_fields: list[str] \| None = None` | line 526 | ✅ |
| `_build_overview()` 接线 | 传递给 `artist.annotate()` | lines 644–647 | ✅ |
| 不存在字段 | 静默跳过 | `test_annotate_nonexistent_field` 通过 | ✅ |

### 2.7 R4 — qubit card 全部展示 ✅

| 项目 | 设计 | 实现 | 判定 |
|------|------|------|------|
| CSS `.qubit-card td.missing` | `color: #cc6666; font-style: italic;` | line 112 | ✅ |
| `_make_missing_row(label)` | 辅助函数 | lines 346–351 | ✅ |
| 6 行始终渲染 | f01/T1/T2*/T2echo/Drive Eff/Readout | lines 364–427 | ✅ |
| extras bool → Yes/No | `isinstance(val, bool)` → `"Yes"/"No"` | lines 432–433 | ✅ |
| extras key 排序 | `sorted(qs.extras.items())` | line 431 | ✅ |
| 无 `<p>No data</p>` fallback | rows 永不为空 | line 442（无 fallback） | ✅ |

---

## 三、架构约定合规性

| # | 约定 | 判定 | 证据 |
|---|------|------|------|
| 1 | 拟合与持久化解耦 | ✅ | `set_extras()` 仅写内存，需手动 `save()` |
| 2 | 拟合模块不自动持久化 | ✅ | 本次不改动拟合模块 |
| 3 | ChipArtist 与 ReportGenerator 解耦 | ✅ | `colormap_param()` 接受任意 `dict[str, float]`，ReportGenerator 独立构建 |
| 4 | 拓扑不硬编码坐标 | ✅ | `_make_box()` 使用 `ChipTopology.iter_qubits()` 坐标 |
| 5 | 参数标注测量条件 | ✅ | extras 为工程判定标志，不涉及 freq_GHz/timestamp |
| — | 类型标注完整 | ✅ | `set_extras(**kwargs: Any)`, `_valid_colormap_params() -> set[str]` 等 |
| — | matplotlib OO API | ✅ | 仅通过 `ax.add_patch()` / `ax.text()` |

---

## 四、新发现问题

### 🟢 P3-1 — docstring 残留"圆圈"术语

**位置**：`chip_plot.py:289` `_RADIUS` 注释、`:326` `_get_circle_center` 方法名、`:573` `annotate()` docstring

**问题**：圆角矩形已替代圆形，但以下注释仍使用"圆圈"或"circle"：
- line 289: `_RADIUS = 0.35  # 比特圆圈半径（保留用于旧代码兼容）` — 注释已更新为"保留用于旧代码兼容"，但 `_RADIUS` 本身仅被 `_BOX_WIDTH`/`_BOX_HEIGHT` 引用作为推导常数，不直接使用 ✅ （实际已正确处理）
- line 326: `_get_circle_center()` — 方法名仍是 `_get_circle_center`，被 `add_coupler_lines()` 调用。功能正确（中心点相同），仅命名过时。
- line 573: `"""在每个比特圆圈下方标注参数文本。"""` — docstring 仍说"圆圈"。

**影响**：无功能影响。纯文档问题。

**建议**：可选重命名 `_get_circle_center` → `_get_qubit_center`，更新 `annotate()` docstring。

---

## 五、测试质量评估

### 5.1 新增测试覆盖

| 测试类 | 用例 | 评级 | 覆盖 |
|--------|------|------|------|
| `TestSaveLastUpdated` | 2 | 🟢 | 保留已有值、None 回退 |
| `TestExtras` | 4 | 🟢 | roundtrip、默认空、旧 JSON 兼容、合并 |
| `TestFancyBboxPatch` | 4 | 🟢 | 三处绘图方法 + 尺寸验证 |
| `TestColormapShowValues` | 4 | 🟢 | show_values、默认、无数据、无单位 |
| `TestReportColormapExpansion` | 7 | 🟢 | T2echo/DE 色标、数值提取、extras 数值/bool、非法参数 |
| `TestAnnotateFields` | 3 | 🟢 | 标注字段、extras 字段、不存在字段 |
| `TestQubitCardAllRows` | 5 | 🟢 | 全行渲染、CSS、extras flags、缺失计数、overview 值显示 |

### 5.2 累计测试

```
226 passed in 4.49s
  ├── tests/test_io.py ........... 44
  ├── tests/test_fitting.py ...... 36
  ├── tests/test_phase2.py ....... 57
  ├── tests/test_phase3.py ....... 51 (+29 Phase 5)
  └── tests/test_phase4.py ....... 38
```

---

## 六、设计偏差分析

| 项目 | 设计文档 | 实现 | 评价 |
|------|---------|------|------|
| text_color 自适应 | 仅描述 `show_values` 分支 | 增加了 `!show_values` 时的自适应（白/黑） | 🟢 改进 |
| extras 排序 | 未指定排序 | `sorted(qs.extras.items())` | 🟢 改进（卡片展示可预测） |
| `_make_missing_row` helper | 未单独提出 | 独立辅助函数 | 🟢 改进（代码更干净） |
| `_valid_colormap_params` | 验证逻辑直接写在 `generate()` | 独立方法 | 🟢 改进（可测试性更好） |
| `_RADIUS` 保留 | 未提及 | 保留 + 注释"用于旧代码兼容" | 🟢 合理 |

**零设计偏差。4 处实现增强，均在合理范围内。**

---

## 七、跨 Phase 遗留问题追踪

| 编号 | 来源 | 问题 | 状态 |
|------|------|------|------|
| #002 P2-4 | Phase 1 | `fit_spectro()` 双重 `_select_columns` | ⚪ 远期 |
| #002 P2-5 | Phase 1 | `guess_decaying_sinusoid` phase=0.0 | ⚪ 远期 |

**Phase 5 零新遗留问题。仅 1 个 P3 建议（docstring 术语更新）。**

---

## 八、验收结论

**Phase 5 全部 7 个子需求按设计文档正确实现。** 226 测试通过（含 +29 新增），零回归。无设计偏离，4 处实现增强合理。无 P1/P2 阻塞项。

| 需求 | 状态 |
|------|------|
| R1: save() 保留 last_updated | ✅ 验收 |
| R2: QubitState.extras + set_extras() | ✅ 验收 |
| R3a: 圆角矩形 FancyBboxPatch | ✅ 验收 |
| R3b: colormap 内显示参数值 | ✅ 验收 |
| R3c: 色标扩展 T2echo/DE/extras | ✅ 验收 |
| R3d: annotate_fields 接线 | ✅ 验收 |
| R4: qubit card 全部展示 | ✅ 验收 |

**Phase 5 可以验收。**

---

> **审查报告版本**：v1  
> **关联文档**：[[phase-5-design]](../designs/phase-5-design.md) | [[006-project-review]](006-project-review.md) | [[requirements.md]](../requirements.md)  
> **项目状态**：Phase 1–5 全部完成，226 tests，7 次审查闭环。ExpToolKit 骨架完整，可进入生产使用。
