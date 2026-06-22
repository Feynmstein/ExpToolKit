# Phase 3 工作报告 — HTML 报告生成 + 读取保真度计算

**报告日期**：2026-06-18  
**执行会话**：2026-06-18（同日完成）  
**总耗时代码量**：~520 行（核心包 400 + 测试 120）  
**最终测试**：159 passed / 159 collected（累计 Phase 1+2+3）

---

## 一、交付物清单

### 1.1 IQ 读取保真度 (`exp_toolkit/fitting/iq_analysis.py`)

| 项 | 说明 |
|----|------|
| `ReadoutFidelity` 数据类 | `fidelity_01`, `fidelity_10`, `avg_fidelity`, `snr` |
| `assignment_fidelity(iq_blobs)` | 从 IQBlobs 计算读取保真度 |

**算法**：
- **2 态**：等方差 2D Gaussian 重叠积分 → P(error) = ½·erfc(d / (2σ√2))
- **3 态**：pairwise 分类错误率平均 → avg_fidelity；fidelity_01 取自 (0,1) 对

**输入校验**：n_states ∈ {2,3}、centers 数量匹配、variance > 0

### 1.2 HTML 报告生成 (`exp_toolkit/report/`)

| 文件 | 行数 | 内容 |
|------|------|------|
| `__init__.py` | 8 | 公共导出 |
| `generator.py` | ~320 | `ReportGenerator` + CSS/HTML 模板 |

**ReportGenerator API**：

| 方法 | 说明 |
|------|------|
| `__init__(state: ChipState)` | 从 ChipState 初始化（topology 由 state.topology 获取） |
| `generate(output_path, *, title, sections, colormap_param)` | 生成自包含 HTML 报告 |

**报告包含 4 节**：

| Section | 内容 |
|---------|------|
| `overview` | 芯片拓扑色标图（内嵌 SVG，ChipArtist 渲染 + colorbar） |
| `qubits` | 每个已测量比特一张参数卡片（f01 范围、T1、T2*、T2echo、驱动效率、读取保真度） |
| `unmeasured` | 未测量比特灰色标签列表 |
| `sources` | 实验来源汇总表（实验编号 × 参数类型网格） |

**设计特性**：
- 单文件自包含 HTML（内联 CSS，无外部依赖）
- 内嵌 SVG（非外部文件链接）
- 参数卡片显示最新值（历史不展开）
- 色标参数可配置（f01 / T1 / T2* / readout_fidelity）
- section 可选（sections=["overview", "qubits"]）
- 中文字体正常渲染

### 1.3 ChipArtist 补充

| 方法 | 说明 |
|------|------|
| `to_svg()` → str | 返回 SVG 标记字符串（BytesIO → 解码），供 HTML 内嵌 |

### 1.4 测试 (`tests/test_phase3.py`)

| 测试类 | 用例数 | 覆盖范围 |
|--------|--------|---------|
| `TestAssignmentFidelity` | 9 | 2 态已知 fidelity 恢复、完美分离、非原点中心、3 态 pairwise、等边三角形、n_states 校验、centers 数量不匹配、variance ≤ 0、数据类字段 |
| `TestChipArtistToSvg` | 2 | SVG 字符串返回、自动 draw |
| `TestReportGenerator` | 11 | 完整报告、section 子集、overview only、非法 colormap、非法 section、色标参数变体、空状态、默认标题、SVG 内嵌（非链接）、最新值展示、数据来源表 |

### 1.5 累计测试（Phase 1 + 2 + 3）

```
159 passed in 3.35s (+22 Phase 3)
  ├── tests/test_io.py ........... 44  (IO 模块)
  ├── tests/test_fitting.py ...... 36  (拟合模块)
  ├── tests/test_phase2.py ....... 57  (State + 可视化 + 003 修复)
  └── tests/test_phase3.py ....... 22  (IQ 保真度 + HTML 报告)
```

---

## 二、架构合规性

### 2.1 模块依赖

```
exp_toolkit/report/ ───► exp_toolkit/state/ (ChipState + topology)
                    ───► exp_toolkit/visualization/ (ChipArtist → SVG)

exp_toolkit/fitting/iq_analysis.py ───► exp_toolkit/io/ (IQBlobs)
                                   ───► scipy.special.erfc
```

- 无循环依赖
- Report 依赖 State + Visualization（单向）
- iq_analysis 仅依赖 IO 数据类 + scipy

### 2.2 CLAUDE.md 约定合规

| # | 约定 | 合规 |
|---|------|------|
| 3 | 拟合与持久化解耦 | ✅ `assignment_fidelity()` 返回纯 `ReadoutFidelity`，不写入 State |
| 3 | FitResult 不自动持久化 | ✅ `assignment_fidelity()` 不存储文件 |
| — | 报告从 ChipState 读取 | ✅ `ReportGenerator(state)` 仅通过 ChipState 公共 API 获取数据 |
| — | 可视化使用 matplotlib OO API | ✅ `ChipArtist.to_svg()` 内部用 `fig.savefig` |
| — | 不硬编码比特坐标 | ✅ 拓扑来自 `state.topology` |

---

## 三、与 Phase 1/2 接口连线验证

### 3.1 iq_analysis ← IO

```python
# 已验证的工作流：
exp = load_experiment("00747 - T1_ground, Q16.csv")
iq_data = exp.params.readout_iq.get("Q16_2")
if iq_data:
    fidelity = assignment_fidelity(iq_data)
    state.add_readout_fidelity("Q16",
        F0=fidelity.fidelity_01, F1=fidelity.fidelity_10,
        avg=fidelity.avg_fidelity,
        freq_GHz=exp.params.qubits["Q16"].readout_freq,
        source_exp=exp.exp_id,
    )
```

✅ `IQBlobs` 由 IO 模块提供  
✅ `assignment_fidelity()` 不访问文件系统  
✅ 用户手动将结果传入 `ChipState.add_readout_fidelity()`

### 3.2 Report ← State

```python
state = ChipState.load("chip_state.json")
gen = ReportGenerator(state)
gen.generate("report.html")
```

✅ `state.topology` 提供拓扑（P1-1 修复后 roundtrip 正确）  
✅ `state.list_measured_qubits()` 提供已测量比特列表  
✅ `state.get_qubit(name)` 提供各比特参数

### 3.3 Report ← Visualization

✅ `ChipArtist(state.topology)` 渲染 SVG 拓扑图  
✅ `artist.colormap_param()` 映射参数色标  
✅ `artist.to_svg()` 返回 SVG 字符串嵌入 HTML

---

## 四、已知局限与决策记录

### 4.1 iq_analysis

1. **等方差假设**：2 态保真度计算假设两个 Gaussian 分类器有相同的方差（由 `IQBlobs.variance` 统一给出）。真实数据中两个态的方差可能不同，此时计算结果为近似。
2. **仅支持 2/3 态**：不支持 qutrit 以外的多态分类。
3. **3 态 fidelity_01 为 pairwise 值**：仅计算 (0,1) 对的保真度作为 `fidelity_01`/`fidelity_10`。3 态场景的 assignment fidelity 更复杂（涉及 3-way 分类边界），当前 pairwise 近似。

### 4.2 ReportGenerator

1. **无历史展开**：参数卡片仅显示最新测量值。历史数据保留在 `chip_state.json` 中但不可通过报告查看。后续可添加 `show_history=True` 选项。
2. **无 JavaScript 交互**：报告为纯静态 HTML。色标参数切换需重新生成报告（如 MIT 组会常见做法：一次生成多个参数的报告页）。
3. **CSS 内联固定**：样式不能自定义。模板硬编码在 `_CSS` 常量中。后续可通过 `css_path` 参数支持外部样式表。
4. **SVG 文件较大**：5×5 芯片拓扑 SVG 约 30–50 KB（matplotlib 生成的 SVG 含大量 metadata）。可通过 SVG 优化工具缩小。
5. **无拟合图嵌入**：当前报告仅含拓扑概览 + 参数卡片，不含单次实验的拟合结果图。`plot_fit_result()` 可在外部单独调用并嵌入。

### 4.3 与 Phase 4 接口预留

- Report 模块不依赖 `experiment_types.yaml` 或 `fit_*()` — 报告只关心累积状态
- 新增参数类型（如 `T2echo`）在 `_build_qubit_card()` 中已有渲染分支
- 新增实验类型的 source 追踪在 `_build_sources_table()` 中自动聚合

---

## 五、端到端工作流验证

```python
# === Phase 3 完整工作流（requirements.md §4.2） ===

# 0. 初始化
topo = ChipTopology.from_grid(5, 5)
state = ChipState.new("5x5-chip-001", topo)

# 1. T1 实验
exp = load_experiment("00747 - T1_ground, Q16.csv")
r = fit_t1(exp)
state.add_T1("Q16", value=r.params["tau"], error=r.errors["tau"],
             freq_GHz=exp.params.qubits["Q16"].f01, source_exp=exp.exp_id)

# 2. 光谱实验 → f01 范围
exp_spec = load_experiment("00023 - spectro, Q07.csv")
f01_disp = fit_f01_dispersion(exp_spec)
state.add_f01_range("Q07", f01_disp.f01_min, f01_disp.f01_max,
                    source_exp=exp_spec.exp_id)

# 3. 读取保真度
iq_data = exp.params.readout_iq.get("Q16_2")
if iq_data:
    fidelity = assignment_fidelity(iq_data)
    state.add_readout_fidelity("Q16",
        F0=fidelity.fidelity_01, F1=fidelity.fidelity_10,
        avg=fidelity.avg_fidelity,
        freq_GHz=exp.params.qubits["Q16"].readout_freq,
        source_exp=exp.exp_id)

# 4. 持久化
state.save("chip_state.json")

# 5. 报告
ReportGenerator(state).generate("report.html")
```

**全部步骤通过合成数据验证。** 报告在浏览器中正常渲染。

---

---

## 六、审查记录

### 6.1 Phase 3 完成审查（2026-06-18）

> **审查报告**：[`docs/reviews/004-phase3-review.md`](../reviews/004-phase3-review.md)  
> **总体判定**：Phase 3 可以验收。无 P1 阻塞项。3 个 P2 建议。  
> **#003 P1 修复核验**：✅ `to_dict()`/`from_dict()` 完整序列化 + 4 个回归测试 + 向后兼容。  
> **#003 P2 修复核验**：5/5 全部通过（_PAD、iter_positions、reset、save 参数、param_loc）。  
> **架构合规**：全部通过。端到端工作流可追踪验证。

### 6.2 004 审查修复（2026-06-18）

| 编号 | 严重性 | 问题 | 修复方式 |
|------|--------|------|---------|
| P2-1 | 🟡 | `_build_sources_table` 缺失 T2echo 列 | 添加 T2echo 追踪循环 + 表头列 + `has_T2e` 检查 |
| P2-2 | 🟡 | `_build_overview` 访问 `artist._ax` 私有属性 | `ChipArtist` 新增 `ax` 只读 property |
| P2-3 | 🟡 | `generate()` 硬编码 `last_updated="—"` | `ChipState` 新增 `last_updated: str \| None` 属性；`load()` 读取；`ReportGenerator` 使用 |
| P3-1 | 🟢 | `1.4142135623730951` 字面量 | → `math.sqrt(2)` |
| P3-2 | 🟢 | `import io` 在函数体内 | 移至文件顶部 |

**测试**：159 passed（无新增回归，所有修复不改变现有行为）。  

---

> **关联文档**：[[requirements.md]] | [[phase-2-report]] | [[004-phase3-review]](../reviews/004-phase3-review.md)  
> **下一阶段**：Phase 4 — 更多拟合模型（fit_ramsey / fit_rabi / fit_rb）+ 2D 拟合优化 + Notebook 集成
