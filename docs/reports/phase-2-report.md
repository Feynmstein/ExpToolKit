# Phase 2 工作报告 — State 模块 + 芯片拓扑可视化

**报告日期**：2026-06-18  
**执行会话**：2026-06-18（同日完成）  
**总耗时代码量**：~1,380 行（核心包 993 + 测试 390）  
**最终测试**：123 passed / 123 collected（累计 Phase 1+2）  

---

## 一、交付物清单

### 1.1 State 模块 (`exp_toolkit/state/`)

| 文件 | 行数 | 内容 |
|------|------|------|
| `__init__.py` | 17 | 公共 API 导出（5 数据类 + 1 管理器） |
| `chip_state.py` | 430 | 数据类 + ChipState（new/load/save/add_*/get_*） |

**5 个数据类**：`ParameterEntry`, `DriveEntry`, `ReadoutEntry`, `F01Range`, `QubitState`

**ChipState 管理器**：

| 方法 | 说明 |
|------|------|
| `ChipState.new(chip_id, topology)` | 创建空状态 |
| `ChipState.load(path)` | 从 chip_state.json 加载 |
| `.save(path)` | 保存到 chip_state.json |
| `.add_T1(qubit, value, error, freq_GHz, source_exp)` | 追加 T1 测量值 |
| `.add_T2star(qubit, ...)` | 追加 T2* 测量值 |
| `.add_T2echo(qubit, ...)` | 追加 T2 echo 测量值 |
| `.add_f01_range(qubit, f01_min, f01_max, source_exp)` | 设置 f01 范围（覆盖） |
| `.add_drive_efficiency(qubit, pi_amp, pi_width_ns, freq_GHz, source_exp)` | 追加驱动效率（自动计算 product） |
| `.add_readout_fidelity(qubit, F0, F1, avg, freq_GHz, source_exp)` | 追加读取保真度 |
| `.get_qubit(name)` → `QubitState` | 获取比特状态 |
| `.get_latest(name, param)` → Entry | None | 获取最新参数条目 |
| `.list_measured_qubits()` → `list[str]` | 列出有数据的比特 |

### 1.2 可视化模块 (`exp_toolkit/visualization/`)

| 文件 | 行数 | 内容 |
|------|------|------|
| `__init__.py` | 16 | 公共 API 导出（2 类 + 2 函数） |
| `chip_plot.py` | 360 | `ChipTopology` + `ChipArtist` |
| `fit_plot.py` | 170 | `plot_fit_result()` + `plot_spectroscopy_2d()` |

**ChipTopology** — 芯片拓扑数据结构：

| 方法/属性 | 说明 |
|----------|------|
| `__init__(layout)` | `(row, col) → qubit_name \| None` |
| `from_grid(rows, cols, numbering, start)` | 快速创建标准网格（row-major / col-major） |
| `add_coupler(q1, q2, **params)` | 添加耦合连接 |
| `get_neighbors(name)` → `list[str]` | 查询耦合邻居 |
| `iter_qubits()` → `Iterator` | 遍历所有比特 (pos, name) |
| `pos_of(name)` → `(row, col) \| None` | 查比特坐标 |
| `rows`, `cols` | 拓扑行列数 |
| `qubit_names`, `couplers` | 比特列表、耦合器列表 |

**ChipArtist** — 芯片拓扑绘图器：

| 方法 | 说明 |
|------|------|
| `draw(ax=None)` | 绘制基础拓扑（灰色圆圈 + 标签） |
| `highlight_measured(qubits, color)` | 模式 A：高亮已测量比特 |
| `colormap_param(name, values, cmap, vmin, vmax)` | 模式 B：参数色标映射 |
| `add_coupler_lines()` | 绘制耦合连接线 |
| `annotate(fields, values)` | 在每个比特下方标注参数 |
| `save(path, format)` | 保存图片（默认 SVG） |
| `get_figure()` | 获取 matplotlib Figure |

**fit_plot 函数**：

| 函数 | 说明 |
|------|------|
| `plot_fit_result(x, y, result, *, title, xlabel, ylabel, show_residuals, ax, ax_res)` | 数据点 + 拟合曲线 + 残差子图 + 参数标注 |
| `plot_spectroscopy_2d(exp, *, z_slice, ax, ax_slice)` | 2D 伪彩图 + 可选 1D 切片 |

### 1.3 测试 (`tests/test_phase2.py`)

| 测试类 | 用例数 | 覆盖范围 |
|--------|--------|---------|
| TestChipTopology | 11 | from_grid (row-major/col-major/offset)、custom layout、couplers、neighbors、pos_of、错误路径（空/重复/非法编号） |
| TestChipArtist | 10 | draw (含已有 ax)、highlight_measured、colormap_param (含 NaN/空值/null 返回)、annotate、coupler_lines、save SVG (≥100 bytes)、auto-draw |
| TestChipState | 12 | new/load/save roundtrip（含 JSON 内容校验）、add_T1/add_f01_range/add_drive_efficiency/add_readout_fidelity、get_latest (含 f01)、list_measured、空状态 roundtrip、f01 覆盖语义 |
| TestDataClasses | 5 | ParameterEntry/DriveEntry/ReadoutEntry/F01Range/QubitState 构造和默认值 |
| TestPlotFitResult | 3 | 基本绘图、无残差模式、NaN 数据对齐 |
| TestPlotSpectroscopy2D | 2 | 2D 伪彩图、z_slice 切片、1D 数据拒绝 |

### 1.4 累计测试（Phase 1 + Phase 2）

```
123 passed in 1.80s
  ├── tests/test_io.py ........... 44  (IO 模块)
  ├── tests/test_fitting.py ...... 36  (拟合模块)
  └── tests/test_phase2.py ....... 43  (State + 可视化)
```

---

## 二、架构合规性

### 2.1 模块依赖

```
exp_toolkit/state/ ──────────────► exp_toolkit/visualization/ (ChipTopology)
        │                                      │
        │                                      ▼
        │                           matplotlib (OO API のみ)
        │
        ▼
    json, datetime, pathlib (stdlib)
```

- State → Visualization（单向，仅 ChipTopology 数据结构）
- 无循环依赖
- Visualization 不依赖 State

### 2.2 CLAUDE.md 架构约定合规

| # | 约定 | 合规 |
|---|------|------|
| 4 | 拓扑用 ChipTopology 描述，可自定义任意布局 | ✅ `__init__(layout)` + `from_grid()` |
| 4 | 缺失比特用 None 占位 | ✅ `ChipTopology({(1,1): None})` |
| 4 | 比特间连接（耦合器）作为可选层叠加 | ✅ `add_coupler()` + `add_coupler_lines()` |
| 4 | 禁止在绘图代码中硬编码比特坐标或 5×5 假设 | ✅ 坐标全部来自 `ChipTopology._layout` |
| - | 可视化统一使用 matplotlib 面向对象 API | ✅ 所有函数接受 `ax` 参数，`fig, ax = plt.subplots()` |
| - | 色标使用 perceptually uniform colormap | ✅ 默认 `viridis` |
| 5 | 参数标注测量条件（freq_GHz） | ✅ 所有 Entry 含 `freq_GHz` 字段 |
| 5 | f01 存 min/max 范围 | ✅ `F01Range(min, max, source_exp)` |
| 5 | 同类型多值保留全部历史 | ✅ `add_T1()` 等 append 到列表 |
| 5 | 禁止用标量存参数值而不标注测量条件 | ✅ 所有 Entry 含 `freq_GHz` + `timestamp` + `source_exp` |

### 2.3 ChipArtist 约束

| 约束 | 合规 |
|------|------|
| `draw()` 接受 `ax` 参数 | ✅ |
| `highlight_measured()` 不修改底层数据 | ✅ 仅添加 patches |
| `colormap_param()` 返回 `ScalarMappable` | ✅ 调用者可添加 `fig.colorbar()` |
| 未测量比特保持灰色 (`#D9D9D9`) | ✅ |
| `save()` 支持 SVG 格式 | ✅ 默认 `bbox_inches="tight"` |
| 坐标映射：col→x, row→-y（电子学惯例） | ✅ |

---

## 三、与 Phase 1 的接口连线验证

### 3.1 State ← 拟合模块

```python
# 已确认的工作流（requirements.md §4.2）：
exp = load_experiment("00747 - T1_ground, Q16.csv")
r = fit_t1(exp)

state = ChipState.new("5x5-chip-001", topo)
state.add_T1("Q16",
    value=r.params["tau"],
    error=r.errors["tau"],
    freq_GHz=exp.params.qubits["Q16"].f01,    # ← 用户手动传入
    source_exp=exp.exp_id,
)
```

✅ `ParameterEntry.freq_GHz` 标注测量频率  
✅ `ParameterEntry.source_exp` 记录实验来源  
✅ `QubitState.T1_us` 为列表，支持多次 add

### 3.2 State ← IO 模块

✅ `ChipState.load()` 可读取 IO 模块输出的 `chip_state.json`  
✅ `ChipState.save()` 生成的 JSON 可由 IO 模块后续读取  
✅ `verified` 标记由 IO 模块在 `load_experiment()` 阶段设置，State 模块不修改

---

## 四、已知局限与决策记录

### 4.1 ChipTopology

1. **拓扑形状**：`from_grid()` 仅支持矩形网格。自定义形状需手动构造 `layout` dict。
2. **from_grid 序列化**：`save()` 仅保存 `rows/cols/numbering/start`，不保存自定义 `layout` 的精确形状。加载时只重建 `from_grid()` 拓扑。
3. **耦合器序列化**：`save()` 未保存耦合器信息（chip_state.json 结构未定义 couplers 字段）。需要时可在后续版本扩展。

### 4.2 ChipArtist

1. **非交互式**：ChipArtist 仅生成静态图片。不持有点击/悬停事件。
2. **布局自适应**：`draw()` 根据拓扑自动计算轴范围，但不支持旋转或非等距布局。
3. **文本标注溢出**：`annotate()` 文本直接放置在圆圈下方，不检查重叠。复杂标注建议用 colormap 替代。

### 4.3 ChipState

1. **topology roundtrip**：`save()` 仅保存 `from_grid()` 参数。若原始 ChipTopology 为自定义 `layout`，加载后的拓扑可能不同。Phase 3（报告）需评估此影响。
2. **timestamp 默认值**：`add_*()` 的 `timestamp` 默认为当天日期，不记录小时/分钟。
3. **并发安全**：ChipState 非线程安全。多 notebook/进程同时写入同一 chip_state.json 可能导致数据丢失。

---

## 五、与 Phase 3 的接口契约

Phase 3（HTML 报告生成 + 读取保真度计算）将从以下接口获取数据：

### 5.1 从 State 模块

```python
state = ChipState.load("chip_state.json")
# → state.chip_id, state.topology
# → state.list_measured_qubits()               # 有数据的比特
# → state.get_qubit(name).f01_GHz              # F01Range
# → state.get_latest(name, "T1")               # ParameterEntry
# → state.get_latest(name, "T2star")           # ParameterEntry
# → state.get_latest(name, "readout_fidelity") # ReadoutEntry
```

### 5.2 从可视化模块

```python
artist = ChipArtist(state.topology)
artist.draw()
artist.colormap_param("f01 (GHz)", {name: state.get_latest(name, "f01")...})
artist.save("report_chip.svg")    # 内嵌到 HTML
```

### 5.3 需新增的模块（Phase 3）

- `exp_toolkit/fitting/iq_analysis.py` — `assignment_fidelity(iq_blobs) → ReadoutFidelity`
- `exp_toolkit/report/generator.py` — `ReportGenerator(state, topology) → HTML`

---

## 六、审查记录

### 6.1 Phase 2 完成审查（2026-06-18）

> **审查报告**：[`docs/reviews/003-phase2-review.md`](../reviews/003-phase2-review.md)  
> **总体判定**：Phase 2 可以验收。1 个 P1（拓扑序列化硬编码）+ 4 个 P2 建议。  
> **阻塞项**：P1-1（save() 硬编码 topology serialization）建议在 Phase 3 启动前修复。  
> **架构合规**：11 项全部通过。API 对照 28 项全部通过。  
> **#002 P1 修复**：3/3 全部验证通过（fit_spectro 自动选 zpa + fit_t1 校准列排除 + _FIELD_MAP 移除）。  

### 6.2 003 审查修复（2026-06-18）

| 编号 | 严重性 | 问题 | 修复方式 | 测试 |
|------|--------|------|---------|------|
| P1-1 | 🔴 | `save()` 硬编码拓扑序列化 → 非默认拓扑 roundtrip 位置错误 | `ChipTopology.to_dict()` + `from_dict()` 完整序列化布局+耦合器；`ChipState.save/load` 切换调用；`from_dict()` 兼容旧格式 | `test_to_from_dict_roundtrip`, `test_save_load_col_major_roundtrip`, `test_save_load_custom_layout_roundtrip`, `test_save_load_preserves_couplers`, `test_load_old_format_json` |
| P2-1 | 🟡 | `_PAD` 常量定义但未使用 | `draw()` 中 `±1.0` → `self._PAD` | — |
| P2-2 | 🟡 | `_layout_positions()` 跨类访问私有属性 | `ChipTopology.iter_positions()` 公开方法 | `test_iter_positions_includes_gaps` |
| P2-3 | 🟡 | `highlight_measured`/`colormap_param` 叠加绘制无 reset | `ChipArtist.reset()` + `_overlay_patches` 追踪 | `test_reset_removes_overlays` |
| P2-4 | 🟡 | `save()` 不支持 dpi/bbox_inches 覆盖 | `save(path, format, dpi=150, bbox_inches="tight")` | `test_save_with_custom_dpi` |
| P2-5 | 🟡 | `plot_fit_result()` 参数框位置硬编码 | `param_loc` 参数（lower left / lower right / upper left / upper right） | `test_param_loc_upper_right`, `test_param_loc_invalid_falls_back` |

**测试增量**：137 passed（+14 用例），覆盖：
- col-major / 自定义布局（含 None 间隙）roundtrip
- 耦合器序列化
- 旧格式 chip_state.json 向后兼容
- iter_positions 含间隙
- highlight 不存在的 qubit 静默忽略
- reset() 清除叠加层
- param_loc 定位 + 无效值回退

---

> **关联文档**：[[requirements.md]] | [[003-phase2-review]](../reviews/003-phase2-review.md)  
> **下一阶段**：Phase 3 — HTML 报告生成 + 读取保真度计算（`exp_toolkit/report/` + `exp_toolkit/fitting/iq_analysis.py`）
