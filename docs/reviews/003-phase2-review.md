# 审查报告 #003 — Phase 2 完成审查（State 模块 + 芯片拓扑可视化）

**审查日期**：2026-06-18  
**审查范围**：`exp_toolkit/state/` + `exp_toolkit/visualization/` + `tests/test_phase2.py` + Phase 1 P1 修复  
**审查基准**：`docs/requirements.md` v3 + `CLAUDE.md` 架构约定 + [审查报告 #002](002-phase1-complete-review.md) 行动清单  
**上一审查**：[#002](002-phase1-complete-review.md)（Phase 1 完成审查，3 P1 + 5 P2）  
**审查人角色**：Supervisor（不主动写实现代码）

---

## 一、总体判定

| 维度 | 评级 | 说明 |
|------|------|------|
| #002 P1 修复完成度 | 🟢 全部通过 | P1-1/P1-2/P1-3 全部修复，新增 3 个回归测试 |
| API 与需求一致性 | 🟢 良好 | State 模块 API 与 requirements.md §3.4 高度吻合 |
| 架构约定合规 | 🟢 良好 | 11 项架构约束全部满足 |
| 测试覆盖 | 🟢 良好 | 123/123 passed (1.79s)，新增 43 个 Phase 2 测试 |
| 代码质量 | 🟡 1 个 P1 + 4 个 P2 | 详见 §三 |
| 文档准确性 | 🟡 1 处偏差 | 报告行数统计与实际略有出入 |

**结论：Phase 2 可以验收。1 个 P1 问题（已知局限，需在 Phase 3 前解决）+ 4 个 P2 改进建议。**

---

## 二、#002 行动清单核验

| # | 严重性 | 问题 | 修复状态 | 验证证据 |
|---|--------|------|---------|---------|
| P1-1 | 🔴 | `fit_spectro()` 2D 无 z_slice 静默垃圾拟合 | ✅ 已修复 | 自动选中间 zpa + `UserWarning`；`test_fit_spectro_no_slice_auto_selects_zpa` 通过；`test_fit_spectro_different_zpa_different_f01` 通过 |
| P1-2 | 🟡 | `fit_t1()` P1 匹配无校准列排除 | ✅ 已修复 | `_find_column()` 增加 `exclude_pattern` 参数；`fit_t1()` 传入 `y_exclude_pattern="for \|0>"`；`test_exclude_calibration_column` + `test_exclude_no_match` 通过 |
| P1-3 | 🟡 | `_FIELD_MAP` 未使用 | ✅ 已修复 | `_FIELD_MAP` 已从代码中完全移除（grep 无命中） |

**#002 全部 P1 修复项验证通过。** 拟合测试从 33 增至 36 个（+3 个回归测试）。拟合 `__init__.py` 同时扩展了公共导出（`guessers`, `fit_t1`, `fit_spectro`, `fit_f01_dispersion`, `F01Dispersion`）。

---

## 三、新发现问题

### 🔴 P1-1 — `ChipState.save()` 硬编码拓扑序列化参数，非默认拓扑 roundtrip 后位置映射错误

**位置**：`exp_toolkit/state/chip_state.py:368–375`

**问题**：

```python
# save() 始终写入固定值：
output = {
    ...
    "topology": {
        "rows": self.topology.rows,
        "cols": self.topology.cols,
        "numbering": "row-major",   # ← 硬编码
        "start": 1,                  # ← 硬编码
    },
    ...
}
```

而 `load()` 无条件使用这些参数重建拓扑：

```python
# load() 无条件使用保存的值：
tp = ChipTopology.from_grid(
    rows=topo_raw.get("rows", 5),
    cols=topo_raw.get("cols", 5),
    numbering=topo_raw.get("numbering", "row-major"),
    start=topo_raw.get("start", 1),
)
```

**影响矩阵**：

| 原始拓扑 | save() 写入 | load() 重建 | pos_of() 正确？ | 参数数据正确？ |
|---------|------------|------------|----------------|-------------|
| `from_grid(5,5)` row-major | row-major, start=1 | row-major, start=1 | ✅ | ✅ |
| `from_grid(5,5, numbering="col-major")` | row-major, start=1 | row-major, start=1 | ❌ 位置全错 | ✅ 数据按 qubit name 保留 |
| `from_grid(5,5, start=5)` | row-major, start=1 | row-major, start=1 → Q01-Q25 | ❌ 名称偏移 | ⚠️ qubit key 对不上 |
| 自定义 `ChipTopology(layout)` | `rows`/`cols` 计算自 layout | row-major 重建 | ❌ 完全错误 | ✅ 但 qubit name 可能不对应 |

参数数据（T1/T2/f01）按 qubit name 保留在 `_qubits` dict 中，因此**数据不丢失**。但：
- `pos_of()` 返回错误位置 → ChipArtist 绘制位置错误 → 报告中的芯片图不可信
- `get_neighbors()` 基于错误拓扑 → 邻居查询结果错误
- 自定义 layout（带 None 间隙的拓扑）完全无法 roundtrip

**严重性**：此问题在 Phase 2 报告中 §4.1 点 2 和 §4.3 点 1 已明确记录为"已知局限"，但标记为局限性而非 bug。对于标准 `from_grid(5, 5)` 使用场景（且 numbering="row-major"），行为正确。对于 Phase 3 报告生成，如果芯片使用非默认拓扑，生成的 SVG 图会标注错误位置。

**建议修复**：
> `save()` 应序列化 `ChipTopology` 的完整布局信息（至少保存 `_layout` dict 和/或 `numbering`/`start` 参数）。两种方案：
> - **方案 A（保守）**：`save()` 中写入实际的 `numbering` 和 `start`（需 ChipTopology 记录创建参数）
> - **方案 B（完整）**：`save()` 中序列化完整的 `_layout` dict → `load()` 中直接 `ChipTopology(layout)` 而非 `from_grid()`

### 🟡 P2 建议（非阻塞，可择机处理）

#### P2-1 — `_PAD` 常量定义但未使用

**位置**：`exp_toolkit/visualization/chip_plot.py:215`

```python
_PAD = 0.6  # 边缘留白比例
```

全文仅此一处引用。`draw()` 中轴边距计算使用硬编码的 `±1.0`：
```python
ax.set_xlim(x_min - 1.0, x_max + 1.0)
ax.set_ylim(y_min - 1.0, y_max + 1.0)
```

应为 `x_min - self._PAD, x_max + self._PAD`，或删除 `_PAD` 常量。

#### P2-2 — `_layout_positions()` 跨类访问私有属性

**位置**：`exp_toolkit/visualization/chip_plot.py:509`

```python
def _layout_positions(self) -> list[tuple[int, int]]:
    return list(self._topo._layout.keys())
```

`ChipArtist` 访问 `ChipTopology._layout`（私有属性）。`draw()` 需要所有位置（含 None 间隙）计算轴范围，而 `iter_qubits()` 跳过 None。两类方案：
- ChipTopology 新增 `iter_positions() → Iterator[tuple[int, int]]` 公开方法（返回所有位置含 None）
- 或维持现状，加注释说明为何需要直接访问

#### P2-3 — `highlight_measured()` 和 `colormap_param()` 通过叠加补丁实现，无重置方法

**位置**：`exp_toolkit/visualization/chip_plot.py:320–356, 358–424`

两个方法都在 `draw()` 的灰色圆圈**之上**叠加新 Circle 补丁。行为后果：
- 连续调用 `highlight_measured()` 两次 → 叠加两层彩色圆圈（视觉上无问题但不必要）
- 调用 `highlight_measured()` 后再调用 `colormap_param()` → 彩标圆圈叠在 highlight 圆圈之上
- 无 `reset()` 方法恢复到 `draw()` 的基础状态

**当前影响**：低。用户一般只调用其中一个方法一次。但若在 Jupyter notebook 中反复实验，ax 中会累积大量 patches。

**建议**：添加 `reset()` 方法清除所有后添加的 patches，或在 `highlight_measured()`/`colormap_param()` 前先移除之前的覆盖层。

#### P2-4 — `save()` 不支持 SVG 以外的格式参数覆盖

**位置**：`exp_toolkit/visualization/chip_plot.py:487–498`

```python
def save(self, path, format="svg"):
    fig.savefig(path, format=format, bbox_inches="tight", dpi=150)
```

`dpi` 和 `bbox_inches` 硬编码，调用者无法覆盖。对 PNG 输出，150 dpi 可能不够。建议 `**kwargs` 透传或显式暴露这两个参数。

#### P2-5 — `plot_fit_result()` 拟合参数文本框位置硬编码

**位置**：`exp_toolkit/visualization/fit_plot.py:102–108`

```python
ax.text(
    0.02, 0.02, "\n".join(param_lines),
    transform=ax.transAxes, ...
)
```

参数框始终在左下角 `(0.02, 0.02)`。如果数据点密集分布在该区域，框会遮挡数据。建议添加 `param_loc: str = "lower left"` 参数，支持 `"upper right"` 等常用位置。

---

## 四、架构约定合规性逐条审查

逐条对照 CLAUDE.md 架构约定：

| # | 约定 | 判定 | 证据 |
|---|------|------|------|
| 4 | 拓扑用 `ChipTopology` 描述，可自定义任意布局 | ✅ | `__init__(layout: dict)` 接受任意 `(row,col)→name` 映射 |
| 4 | 缺失比特用 `None` 占位 | ✅ | `ChipTopology({(0,0): "QA", (0,1): None})` → `iter_qubits()` 跳过 None |
| 4 | 比特间连接（耦合器）作为可选层叠加 | ✅ | `add_coupler()` + `add_coupler_lines()` 独立于 draw() |
| 4 | 禁止在绘图代码中硬编码比特坐标或 5×5 假设 | ✅ | 所有坐标来自 `ChipTopology._layout` + `_to_xy()` |
| — | 可视化统一使用 matplotlib 面向对象 API | ✅ | 所有函数接受 `ax` 参数；`ChipArtist.draw(ax=...)` + `plot_fit_result(ax=...)` |
| — | 色标使用 perceptually uniform colormap | ✅ | `colormap_param()` 默认 `viridis` |
| 5 | 所有参数标注测量时的比特频率 (freq_GHz) | ✅ | `ParameterEntry.freq_GHz`, `DriveEntry.freq_GHz`, `ReadoutEntry.freq_GHz` |
| 5 | f01 存 min/max 范围（来自 f01 dispersion 拟合） | ✅ | `F01Range(min, max, source_exp)` → `QubitState.f01_GHz` |
| 5 | 同类型多值保留全部历史，报告时按时间戳取最新 | ✅ | `add_T1()` 等 append 到列表；`get_latest()` 返回 `entries[-1]` |
| 5 | 禁止用标量存参数值而不标注测量条件 | ✅ | 所有 Entry 数据类含 `freq_GHz` + `timestamp` + `source_exp` |

**11 项架构约束全部合规。**

### §4.1 拟合→State 解耦验证

按照 CLAUDE.md 架构约定 3（拟合与持久化解耦），验证：

```python
# ✅ 正确流程：用户手动控制保存
exp = load_experiment("00747 - T1_ground, Q16.csv")
r = fit_t1(exp)

state = ChipState.new("chip-001", topo)
state.add_T1("Q16",
    value=r.params["tau"],
    error=r.errors["tau"],
    freq_GHz=exp.params.qubits["Q16"].f01,  # 用户手动从 exp.params 提取
    source_exp=exp.exp_id,
)
state.save("chip_state.json")
```

- ✅ `FitResult` 不自动持久化 — 无 `save()` 方法
- ✅ `freq_GHz` 由用户在调用 `add_T1()` 时手动传入（不自动从 `exp.params` 提取）
- ✅ 用户决定哪些实验结果进入 State

---

## 五、需求文档对照

逐条对照 `requirements.md` §3.3–§3.4 的 API 设计：

### 5.1 ChipTopology (§3.3)

| 需求 API | 实现 | 一致性 |
|---------|------|--------|
| `ChipTopology(layout: dict)` | ✅ `__init__(self, layout)` | 一致 |
| `from_grid(rows, cols, numbering, start)` | ✅ 类方法 | 一致 |
| `add_coupler(q1, q2, **params)` | ✅ | 一致 |
| `get_neighbors(name) → list[str]` | ✅ | 一致 |
| `iter_qubits() → Iterator` | ✅ 返回 `Iterator[tuple[tuple[int,int], str]]` | 一致 |
| `pos_of(name) → tuple[int,int]` | ✅ 返回 `tuple[int,int] \| None` | 一致 |
| `rows` / `cols` / `qubit_names` / `couplers` | ✅ 全部实现为 property | 一致 |

### 5.2 ChipArtist (§3.3)

| 需求 API | 实现 | 一致性 |
|---------|------|--------|
| `draw(ax=None)` | ✅ | 一致 |
| `highlight_measured(qubits, color)` | ✅ `color="#4C72B0"` 默认值 | 一致 |
| `colormap_param(name, values, cmap, vmin, vmax)` | ✅ 返回 `ScalarMappable \| None` | 一致 |
| `add_coupler_lines()` | ✅ `ax` 可选参数 | 一致（略有扩展） |
| `annotate(fields, values)` | ✅ | 一致 |
| `save(path, format)` | ✅ 默认 SVG | 一致 |
| `get_figure()` | ✅ | 一致 |

### 5.3 ChipState / 数据类 (§3.4)

| 需求 API | 实现 | 一致性 |
|---------|------|--------|
| `ParameterEntry(value, error, freq_GHz, timestamp, source_exp)` | ✅ | 一致 |
| `DriveEntry(pi_amp, pi_width_ns, product, freq_GHz, ...)` | ✅ product 自动计算 | 一致（增强） |
| `ReadoutEntry(F0, F1, avg, freq_GHz, ...)` | ✅ | 一致 |
| `F01Range(min, max, source_exp)` | ✅ | 一致 |
| `QubitState(f01_GHz, T1_us, T2star_us, T2echo_us, drive_efficiency, readout_fidelity)` | ✅ 全部实现为 list/可选 | 一致 |
| `ChipState.new(chip_id, topology)` | ✅ 类方法 | 一致 |
| `ChipState.load(path)` | ✅ 类方法 | 一致 |
| `save(path)` | ✅ | 一致（见 P1-1） |
| `add_T1(qubit, value, error, freq_GHz, source_exp)` | ✅ `timestamp` 为可选参数 | 一致（增强） |
| `add_T2star(...)` / `add_T2echo(...)` | ✅ | 一致 |
| `add_f01_range(qubit, f01_min, f01_max, source_exp)` | ✅ 覆盖语义 | 一致 |
| `add_drive_efficiency(...)` / `add_readout_fidelity(...)` | ✅ | 一致 |
| `get_qubit(name) → QubitState` | ✅ 不存在时 raise KeyError | 一致 |
| `get_latest(name, param) → Entry \| None` | ✅ 支持别名（"T1"\|"T1_us"） | 一致（增强） |
| `list_measured_qubits() → list[str]` | ✅ | 一致 |

**全部 28 项 API 对照通过。** 实现侧在需求基础上做了合理增强：
- `DriveEntry.product` 自动计算而非手动传入
- `get_latest()` 支持参数名别名（`"T1"` / `"T1_us"` 均可）
- `add_*()` 的 `timestamp` 为可选参数（默认当天）

---

## 六、测试质量评估

### 6.1 Phase 2 测试覆盖

| 测试类 | 用例数 | 覆盖维度 | 评级 |
|--------|--------|---------|------|
| `TestChipTopology` | 11 | from_grid(row-major/col-major/offset)、custom layout、couplers、neighbors、pos_of、错误路径（空/重复/非法编号） | 🟢 充分 |
| `TestChipArtist` | 10 | draw(含已有ax)、highlight_measured、colormap_param(含NaN/空值/Null返回)、annotate、coupler_lines、save SVG(≥100 bytes)、auto-draw | 🟢 充分 |
| `TestChipState` | 12 | new/load/save roundtrip(含JSON内容校验)、add_T1/add_f01_range/add_drive_efficiency/add_readout_fidelity、get_latest(含f01)、list_measured、空状态roundtrip、f01覆盖语义 | 🟢 充分 |
| `TestDataClasses` | 5 | ParameterEntry/DriveEntry/ReadoutEntry/F01Range/QubitState 构造和默认值 | 🟢 充分 |
| `TestPlotFitResult` | 3 | 基本绘图、无残差模式、NaN数据对齐 | 🟡 基础 |
| `TestPlotSpectroscopy2D` | 3 | 2D伪彩图、z_slice切片、1D数据拒绝 | 🟡 基础 |

### 6.2 测试缺失项

| # | 缺失内容 | 优先级 |
|---|---------|--------|
| 1 | `ChipArtist` 对含 None 间隙的拓扑绘图测试 | P2 |
| 2 | `highlight_measured()` 含不存在的 qubit name 的行为测试 | P2 |
| 3 | `ChipState.save()/load()` 对 col-major 拓扑的 roundtrip 测试（当前仅测 row-major） | P1 |
| 4 | `colormap_param()` 返回 `ScalarMappable` 后添加 `fig.colorbar()` 的集成测试 | P2 |
| 5 | `plot_fit_result()` 同时传入 `ax` 和 `ax_res` 的模式测试 | P2 |

其中 **缺失 3** 直接关联 P1-1（拓扑序列化问题），如果有此测试会直接暴露 bug。

### 6.3 累计测试（Phase 1 + Phase 2）

```
123 passed in 1.79s
  ├── tests/test_io.py ........... 44  (IO 模块)
  ├── tests/test_fitting.py ...... 36  (拟合模块，+3 P1回归)
  └── tests/test_phase2.py ....... 43  (State + 可视化)
```

---

## 七、phase-2-report.md 准确性核验

| # | Report 声明 | 核验结果 |
|---|-----------|---------|
| 1 | 核心包 993 行 + 测试 390 行 | 🟡 实测：chip_state.py 571 行 + chip_plot.py 509 行 + fit_plot.py 229 行 + init 文件 = ~1,340 行核心；测试 440 行（略有偏差，不影响结论） |
| 2 | State → Visualization 单向依赖 | ✅ `chip_state.py` import `ChipTopology` from `chip_plot.py`；visualization 不 import state |
| 3 | 无循环依赖 | ✅ 确认（visualization 不依赖 state） |
| 4 | 11 项架构约定合规 | ✅ 已逐条核验（见 §四） |
| 5 | 123 passed | ✅ 实测 123 passed in 1.79s |
| 6 | `from_grid()` 支持 row-major / col-major | ✅ 确认 |
| 7 | `save()` 仅保存 rows/cols/numbering/start | ✅ 确认（见 P1-1，numbering/start 硬编码为 "row-major"/1） |
| 8 | `colormap_param()` 返回 `ScalarMappable` | ✅ 确认 |
| 9 | `save()` 默认 SVG + `bbox_inches="tight"` | ✅ 确认 |
| 10 | 拟合→State 连线确认 | ✅ 确认（freq_GHz 由用户手动传入） |
| 11 | State→IO 连线确认 | ✅ ChipState.load() 可读取 chip_state.json |
| 12 | 已知局限 6 项 | ✅ 全部与实际代码一致 |

---

## 八、与 Phase 3 的接口契约确认

Phase 3（HTML 报告生成 + 读取保真度计算）将从以下接口获取数据：

### 8.1 从 State 模块

```python
state = ChipState.load("chip_state.json")
# → state.chip_id, state.topology
# → state.list_measured_qubits()
# → state.get_qubit(name).f01_GHz          # F01Range | None
# → state.get_latest(name, "T1")            # ParameterEntry | None
# → state.get_latest(name, "readout_fidelity")  # ReadoutEntry | None
```

### 8.2 从可视化模块

```python
artist = ChipArtist(state.topology)
artist.draw()
artist.colormap_param("f01 (GHz)", {name: state.get_latest(name, "f01").value ...})
artist.save("report_chip.svg")
```

### 8.3 Phase 3 需注意

1. **拓扑 roundtrip 限制（P1-1）**：如果芯片使用 col-major 或自定义布局，`ChipState.load()` 后 `state.topology` 将是 row-major 重建版本 → 报告中的 SVG 图位置错误
2. **`colormap_param()` 的值提取模式**：Phase 3 需从 `get_latest(name, "f01")` 获取 `F01Range` 再取 `.max`（或 `.min`），当前无便捷的 `get_latest_value()` 快捷方法
3. **`F01Range` 无 `freq_GHz` 标注**：与 ParameterEntry 不同，F01Range 不标注读取频率——f01 范围本身是频率值
4. **`DriveEntry.product`** 自动计算，但在 load/save roundtrip 中是显式字段（序列化存储），反序列化时不再重新计算——如果 pi_amp 或 pi_width_ns 被修改则 product 不会更新。当前这两个字段为只读（构造后不可变），暂不影响正确性

---

## 九、行动清单

### Phase 3 启动前（建议修复）

| 优先级 | 编号 | 问题 | 预计工作量 |
|--------|------|------|-----------|
| 🔴 P1 | P1-1 | `save()` 硬编码拓扑序列化 → 非默认拓扑 roundtrip 位置错误 | 中（需决定方案 A 或 B + 补充测试） |

### Phase 3 期间（择机处理）

| 优先级 | 编号 | 问题 |
|--------|------|------|
| 🟢 P2 | P2-1 | `_PAD` 常量未使用 |
| 🟢 P2 | P2-2 | `_layout_positions()` 跨类访问私有属性 |
| 🟢 P2 | P2-3 | `highlight_measured()`/`colormap_param()` 叠加绘制，无 `reset()` |
| 🟢 P2 | P2-4 | `save()` 不支持 dpi/bbox_inches 参数覆盖 |
| 🟢 P2 | P2-5 | `plot_fit_result()` 参数框位置硬编码 |

### Phase 4（远期，不阻塞）

| 编号 | 问题 |
|------|------|
| — | `experiment_types.yaml` 接入调度 + `fit_ramsey`/`fit_rabi`/`fit_rb` 实现（延续 #002 P2-3） |
| — | `assignment_fidelity()` 实现（`iq_analysis.py`） |
| — | ChipArtist 交互式模式（点击/悬停），当前明确不考虑 |

---

## 十、积极发现

Phase 2 实现质量良好，以下设计决策值得肯定：

1. **ChipState 依赖 ChipTopology 但不耦合绘图** — State 只依赖拓扑数据结构，不依赖 ChipArtist。符合单一职责。
2. **`get_latest()` 参数别名支持** — 用户可用 `"T1"` 或 `"T1_us"`，降低记忆负担。
3. **`colormap_param()` 返回 `ScalarMappable`** — 调用者可自行添加 `fig.colorbar()`，不强制自动添加。
4. **`DriveEntry.product` 自动计算** — 确保乘积始终与分量一致，消除人工计算错误。
5. **`_ensure_drawn()` 惰性绘制** — 用户无需显式调用 `draw()`，调用任何方法自动触发。
6. **`colormap_param()` 正确处理 NaN 和空值** — `np.isfinite()` 过滤 + 空 dict 返回 None，不会崩溃。
7. **`ChipState.__init__` 自动补全拓扑比特** — 确保所有拓扑比特都有 `QubitState` 条目，即使无测量数据。

---

> **审查报告版本**：v1  
> **关联文档**：[[002-phase1-complete-review]](002-phase1-complete-review.md) | [[phase-2-report]](../reports/phase-2-report.md) | [[requirements.md]](../requirements.md)  
> **下次审查**：Phase 3 — HTML 报告生成 + 读取保真度计算（`exp_toolkit/report/` + `exp_toolkit/fitting/iq_analysis.py`）
