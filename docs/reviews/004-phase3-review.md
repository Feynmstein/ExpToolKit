# 审查报告 #004 — Phase 3 完成审查（HTML 报告 + 读取保真度）

**审查日期**：2026-06-18  
**审查范围**：`exp_toolkit/fitting/iq_analysis.py` + `exp_toolkit/report/` + `tests/test_phase3.py` + #003 修复核验  
**审查基准**：`docs/requirements.md` v3 + `CLAUDE.md` 架构约定 + [审查报告 #003](003-phase2-review.md) 行动清单  
**上一审查**：[#003](003-phase2-review.md)（Phase 2 完成审查，1 P1 + 5 P2）  
**审查人角色**：Supervisor（不主动写实现代码）

---

## 一、总体判定

| 维度 | 评级 | 说明 |
|------|------|------|
| #003 P1 修复 | 🟢 已修复 | `to_dict()`/`from_dict()` 完整序列化 + 向后兼容 |
| #003 P2 修复 | 🟢 5/5 全部通过 | _PAD 使用、iter_positions()、reset()、save()参数、param_loc |
| API 与需求一致性 | 🟢 良好 | iq_analysis + ReportGenerator 接口清晰 |
| 架构约定合规 | 🟢 良好 | 拟合→State 解耦、报告仅读 ChipState 公共 API |
| 测试覆盖 | 🟢 良好 | 159/159 passed (3.22s)，新增 22 个 Phase 3 + 14 个 #003 修复测试 |
| 代码质量 | 🟢 无 P1 | 3 个 P2 建议 |
| 文档准确性 | 🟢 良好 | 行数统计基本准确 |

**结论：Phase 3 可以验收。无 P1 阻塞项。3 个 P2 改进建议。**

---

## 二、#003 行动清单逐项核验

### 2.1 P1-1 — save() 拓扑序列化 ✅ 已修复

**修复方案**：方案 B（完整序列化）+ 向后兼容

`ChipTopology` 新增两个方法：

```python
# chip_plot.py:173 — 完整布局 + 耦合器
def to_dict(self) -> dict[str, Any]:
    return {"layout": {"0,0": "Q01", "0,1": None, ...},
            "couplers": [{"q1": "Q01", "q2": "Q02", ...}, ...]}

# chip_plot.py:198 — 反序列化，兼容新旧格式
@classmethod
def from_dict(cls, d: dict[str, Any]) -> "ChipTopology":
    if "layout" in d:       # 新格式
        ...
        return cls(layout)   # 含 couplers
    return cls.from_grid(...) # 旧格式 {rows, cols, numbering, start}
```

`ChipState` 变更：
- `save()`: `"topology": self.topology.to_dict()`（替换硬编码）
- `load()`: `tp = ChipTopology.from_dict(topo_raw)`（替换 `from_grid(...)`）

**向后兼容**：旧格式 `chip_state.json`（`{rows, cols, numbering, start}`）仍可正常加载。

**新回归测试（4 个）**：

| 测试 | 覆盖 |
|------|------|
| `test_save_load_col_major_roundtrip` | col-major `pos_of()` 保留 |
| `test_save_load_custom_layout_roundtrip` | 含 None 间隙自定义布局 + T1 数据 |
| `test_save_load_preserves_couplers` | 耦合器完整 roundtrip |
| `test_load_old_format_json` | 旧格式 JSON 向后兼容 |

### 2.2 #003 P2 修复核验

| # | 问题 | 修复状态 | 证据 |
|---|------|---------|------|
| P2-1 | `_PAD` 常量未使用 | ✅ | `ax.set_xlim(x_min - self._PAD, x_max + self._PAD)` — chip_plot.py:386–387 |
| P2-2 | `_layout_positions()` 访问私有属性 | ✅ | `ChipTopology.iter_positions()` 公开方法 + `_layout_positions()` 通过 `self._topo.iter_positions()` 调用 |
| P2-3 | highlight/colormap 叠加绘制无 reset | ✅ | `_overlay_patches: list[Artist]` + `reset()` 方法；highlight/colormap/annotate/coupler_lines 均追踪；`test_reset_removes_overlays` 通过 |
| P2-4 | `save()` 不支持 dpi/bbox_inches | ✅ | `save(path, format="svg", dpi=150, bbox_inches="tight")` |
| P2-5 | `plot_fit_result()` 参数框固定位置 | ✅ | `param_loc` 参数 + `_PARAM_LOC_MAP`（lower left/right, upper left/right）；`test_param_loc_upper_right` + `test_param_loc_invalid_falls_back` 通过 |

### 2.3 test_phase2.py 增长

```
43 tests (Phase 2 初版)
→ 57 tests (+14: 4 拓扑 roundtrip + 1 reset + 2 param_loc + 5 ChipArtist 补充 + 2 ChipState)
```

---

## 三、Phase 3 新增代码审查

### 3.1 `exp_toolkit/fitting/iq_analysis.py`（137 行）

**`ReadoutFidelity` 数据类**：

| 字段 | 类型 | 含义 |
|------|------|------|
| `fidelity_01` | float | \|0⟩→\|0⟩ 保真度 (F0) |
| `fidelity_10` | float | \|1⟩→\|1⟩ 保真度 (F1) |
| `avg_fidelity` | float | 平均保真度 (F0+F1)/2 |
| `snr` | float | 信噪比 |

**`assignment_fidelity(iq_blobs) → ReadoutFidelity`**：

算法审查（2 态）：
```
d = |c₁ - c₀|          → IQ 平面中两态中心距离
σ = √variance           → 每个态的 RMS 噪声
SNR = d / σ
P(error) = ½·erfc(d / (2σ√2))   → 等方差 2D Gaussian 重叠积分
fidelity = 1 - P(error)
```

公式验证：2D 各向同性 Gaussian 沿中心连线方向的投影为 1D Gaussian（方差 σ²），决策边界在 d/2 处。单类错误率为 Φ(-d/(2σ)) = ½·erfc(d/(2σ√2))。平衡先验下总错误率 = ½·Φ(-d/(2σ)) + ½·Φ(-d/(2σ)) = Φ(-d/(2σ))。✅ 公式正确。

3 态算法：pairwise 保真度平均 → `avg_fidelity`；`fidelity_01`/`fidelity_10` 取自 (0,1) 对。已文档化 pairwise 近似局限性。✅ 合理。

输入校验：
- `n_states ∈ {2,3}` ✅
- `len(centers) == n_states` ✅
- `variance > 0` ✅

**结论**：算法正确，边界处理完整。

### 3.2 `exp_toolkit/report/generator.py`（535 行）

**`ReportGenerator(state: ChipState)`** — 单文件自包含 HTML 生成器。

**模板系统**：

| 组件 | 内容 |
|------|------|
| `_CSS` | 内联 CSS 变量系统（`--bg`, `--card-bg`, `--text`, `--accent` 等），无外部依赖 |
| `_HTML_SKELETON` | HTML5 骨架 + `<style>` 内嵌 + `<main>` 插槽 |
| `_OVERVIEW_SECTION` | 芯片拓扑 SVG + colormap |
| `_MEASURED_SECTION_*` | 比特参数卡片网格（CSS Grid `auto-fill, minmax(300px, 1fr)`） |
| `_UNMEASURED_SECTION` | 未测量比特灰色标签 |
| `_SOURCES_SECTION` | 数据来源汇总表 |

**参数卡片渲染**（`_build_qubit_card`）：

| 参数 | 渲染 | 格式 |
|------|------|------|
| f01 | 范围 | `4.200–4.900 GHz (00023)` |
| T1 | 值±误差 @ freq | `38.100 ± 1.800 μs @ 4.850 GHz (00789)` |
| T2* | 同上 | `12.300 ± 0.500 μs @ 4.710 GHz (00750)` |
| T2 echo | 同上 | (同格式) |
| Drive Eff | product + 分量 | `19.8 (π-amp=0.660, π-w=30.0 ns) @ 4.710 GHz (00747)` |
| Readout | F0, F1, Avg | `F0=0.9500, F1=0.9200, Avg=0.9350 @ 6.237 GHz (00747)` |

**数据来源表**（`_build_sources_table`）：
- 按 source_exp 聚合
- 含 T1 / T2* / f01 / RO / DE 列（见 P2-1）
- checkmarks（✓/—）表示参数类型存在性

**SVG 内嵌**（`_build_overview`）：
- `ChipArtist(state.topology)` → `draw()` → `colormap_param()` → `to_svg()`
- SVG 字符串嵌入 `<figure>` 标签，无外部文件引用
- XML declaration 被 strip（仅保留 `<svg>...</svg>`）

### 3.3 `ChipArtist.to_svg()`（chip_plot.py:598–612）

```python
def to_svg(self) -> str:
    fig, _ = self._ensure_drawn()
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    return buf.read().decode("utf-8")
```

简洁、正确。惰性 draw（`_ensure_drawn()` 自动触发）。

---

## 四、新发现问题

### 🟡 P2-1 — `_build_sources_table` 缺失 T2echo 列

**位置**：`report/generator.py:328–370`

**问题**：`_build_sources_table` 追踪 T1、T2*、f01、RO、DE 五种参数类型，但不追踪 T2echo。表格表头（line 204–211）也无 T2echo 列。然而 `_build_qubit_card`（line 304–308）**确实渲染 T2echo 行**。

**影响**：如果 ChipState 中有 T2echo 数据，比特卡片中会显示 T2 echo 值，但数据来源表中不会体现该实验为 T2echo 的来源。用户无法从来源表追溯 T2echo 数据的出处。

**建议修复**：
> `_build_sources_table` 中增加 `for entry in qs.T2echo_us:` 循环；表头增加 `<th>T2 echo</th>` 列。同步更新 `mk()` 检查列。

### 🟡 P2-2 — `_build_overview` 访问 `artist._ax` 私有属性

**位置**：`report/generator.py:489`

```python
fig.colorbar(sm, ax=artist._ax, label=..., fraction=0.046, pad=0.04)
```

`_ax` 是 ChipArtist 的私有属性。colorbar 需要 ax 引用以调整布局。规避方案：
- ChipArtist 新增 `ax` 只读 property（一行代码）
- 或在 `colormap_param()` 中自动附加 colorbar（但违反单一职责）

**影响**：当前代码正常工作（同包内访问），但违反封装约定。若 ChipArtist 后续重构 `_ax` 改名/移除，此处静默断裂。

### 🟡 P2-3 — `ReportGenerator.generate()` 硬编码 `last_updated="—"`

**位置**：`report/generator.py:466`

```python
html = _HTML_SKELETON.format(
    ...
    last_updated="—",
    ...
)
```

`ChipState.save()` 写入 `last_updated: date.today().isoformat()`，但 `load()` 不将其存入 ChipState 对象属性。ReportGenerator 也无从读取。报告 header 中始终显示 `Updated: —`。

**影响**：生成的 HTML 报告不显示数据更新时间。用户需手动在 `title` 中注明日期。

**建议**：`ChipState` 增加 `last_updated: str | None` 属性；`load()` 读取 `raw.get("last_updated")` 存入；ReportGenerator 使用 `state.last_updated or "—"`。

### 🟢 P3 建议（非阻塞）

#### P3-1 — `assignment_fidelity` 硬编码 √2 字面量

**位置**：`iq_analysis.py:97, 117`

```python
p_error = 0.5 * float(erfc(d / (2.0 * sigma * 1.4142135623730951)))
```

`1.4142135623730951` 应为 `math.sqrt(2)`。不影响正确性（15 位精度足够），但降低可读性。

#### P3-2 — `to_svg()` 在函数体内 `import io`

**位置**：`chip_plot.py:606`

`import io` 在方法体内。这不是错误但非惯用写法。可移至文件顶部。

---

## 五、架构约定合规性

| # | 约定 | 判定 | 证据 |
|---|------|------|------|
| 3 | 拟合与持久化解耦 | ✅ | `assignment_fidelity()` 返回纯 `ReadoutFidelity`，不写文件 |
| 3 | FitResult 不自动持久化 | ✅ | `ReadoutFidelity` 无 `save()` 方法 |
| — | 报告从 ChipState 读取（公共 API） | ✅ | `ReportGenerator` 仅使用 `state.topology`, `state.chip_id`, `state.list_measured_qubits()`, `state.get_qubit()` |
| — | 可视化使用 matplotlib OO API | ✅ | `to_svg()` 使用 `fig.savefig(buf)` |
| — | 不硬编码比特坐标 | ✅ | 拓扑来自 `state.topology`（P1-1 修复后完整 roundtrip） |

### 端到端工作流验证

Phase 3 报告中的端到端工作流（§五）经代码路径追踪确认可行：

```
load_experiment()  →  Experiment
fit_t1(exp)        →  FitResult
assignment_fidelity(iq_blobs)  →  ReadoutFidelity
state.add_T1(...) / state.add_f01_range(...) / state.add_readout_fidelity(...)
state.save("chip_state.json")
ChipState.load(...)  →  Reconstructed ChipState（P1-1 修复后拓扑正确）
ReportGenerator(state).generate("report.html")  →  自包含 HTML
```

所有步骤通过合成数据验证。

---

## 六、测试质量评估

### 6.1 Phase 3 测试覆盖

| 测试类 | 用例数 | 评级 | 说明 |
|--------|--------|------|------|
| `TestAssignmentFidelity` | 9 | 🟢 充分 | 2 态精确恢复、完美分离、非原点中心、3 态 pairwise、等边三角形、n_states 校验、centers 不匹配、variance≤0、字段可访问 |
| `TestChipArtistToSvg` | 2 | 🟢 充分 | SVG 字符串格式、自动 draw |
| `TestReportGenerator` | 11 | 🟢 充分 | 完整报告、section 子集、overview only、colormap/section 校验、参数变体、空状态、默认标题、SVG 内嵌、最新值展示、sources 表 |

### 6.2 累计测试

```
159 passed in 3.22s
  ├── tests/test_io.py ........... 44  (IO)
  ├── tests/test_fitting.py ...... 36  (拟合)
  ├── tests/test_phase2.py ....... 57  (State + 可视化 + #003 修复，+14)
  └── tests/test_phase3.py ....... 22  (IQ 保真度 + HTML 报告)
```

---

## 七、phase-3-report.md 准确性核验

| # | Report 声明 | 核验结果 |
|---|-----------|---------|
| 1 | 核心包 ~400 行 + 测试 ~120 行 | 🟡 iq_analysis.py 137 行 + generator.py 535 行 + \_\_init\_\_.py 8 行 = 680 行核心；测试 331 行（偏差较大，不影响结论） |
| 2 | 159 passed in 3.35s | 🟡 实测 159 passed in 3.22s（微小波动） |
| 3 | test_phase2 从 43 → 57 (+14) | ✅ 实测 57 个测试 |
| 4 | `assignment_fidelity` 算法描述 | ✅ 与代码一致 |
| 5 | ReportGenerator 4 节结构 | ✅ overview/qubits/unmeasured/sources |
| 6 | SVG 内嵌非外部链接 | ✅ `to_svg()` → strip XML decl → 内嵌 |
| 7 | P1-1 修复后 roundtrip 正确 | ✅ 4 个新测试全部通过 |
| 8 | #003 P2 修复项 | ✅ 5/5 已确认 |
| 9 | 已知局限（等方差、2/3 态、pairwise 近似） | ✅ 与代码一致 |
| 10 | 无历史展开、无 JS 交互、CSS 内联固定 | ✅ 与代码一致 |

> **行数偏差说明**：实现报告称 ~520 行，实测 ~680 行核心 + 331 行测试。偏差主要来自 generator.py 的 HTML/CSS 模板字符串（~180 行模板），这些是声明式代码，不影响逻辑复杂度判断。

---

## 八、与 Phase 4 的接口契约

Phase 4（更多拟合模型 + 2D 拟合优化 + Notebook 集成）与前序阶段的接口：

### 8.1 已有接口（不变）

```python
# 拟合模型模式（Phase 4 新增模型沿用）
models.ramsey(x, amplitude, tau, frequency, phase, offset)  # 纯函数
# → 搭配 guesser + _auto_fit() → fit_ramsey(exp)

# 报告模块（不变）
ReportGenerator(state).generate("report.html")
# → 自动渲染新增参数类型（T2echo 已有渲染分支）

# State 模块（不变）
state.add_T2echo(...)  # 已支持
```

### 8.2 Phase 4 需新增

| 模块 | 内容 |
|------|------|
| `fitting/models.py` | `ramsey_oscillation`, `rabi_oscillation`, `rb_decay` 模型 |
| `fitting/guessers.py` | 对应参数猜测器 |
| `fitting/experiments/ramsey.py` | `fit_ramsey()` |
| `fitting/experiments/rabi.py` | `fit_rabi()` |
| `fitting/experiments/rb.py` | `fit_rb()` |
| `fitting/experiments/experiment_types.yaml` | 接线到调度逻辑 |

### 8.3 Phase 4 注意事项

1. **`experiment_types.yaml` 仍未被调度逻辑使用**（延续 #002 P2-3）。Phase 4 实现新 `fit_*()` 后是接线的最佳时机。
2. **Ramsey 模型复用 `decaying_sinusoid`**（已实现），`fit_ramsey()` 可立即委托 `_auto_fit(exp, model_func=decaying_sinusoid, guesser=guess_decaying_sinusoid)`。
3. **T2echo 的 sources table 列**应在启动 Phase 4 前补充（P2-1）。
4. **2D 拟合优化**（如 `fit_f01_dispersion` 的 Gaussian 负幅度边界情况，#002 P2-2）可在 Phase 4 中一并处理。

---

## 九、行动清单

### Phase 4 启动前（建议修复）

| 优先级 | 编号 | 问题 | 预计工作量 |
|--------|------|------|-----------|
| 🟡 P2 | P2-1 | `_build_sources_table` 缺失 T2echo 列 | 极小（+5 行 + 1 表头） |
| 🟡 P2 | P2-2 | `_build_overview` 访问 `artist._ax` | 极小（ChipArtist 加 `ax` property） |

### Phase 4 期间（择机处理）

| 优先级 | 编号 | 问题 |
|--------|------|------|
| 🟡 P2 | P2-3 | `generate()` 硬编码 `last_updated="—"` |
| 🟢 P3 | P3-1 | `1.4142135623730951` → `math.sqrt(2)` |
| 🟢 P3 | P3-2 | `import io` 移至文件顶部 |

### Phase 4（远期）

| 编号 | 问题 |
|------|------|
| — | `experiment_types.yaml` 接入调度 + `fit_ramsey`/`fit_rabi`/`fit_rb` 实现（#002 P2-3） |
| — | `fit_f01_dispersion()` Gaussian 负幅度边界（#002 P2-2） |
| — | Notebook 集成示例 |

---

> **审查报告版本**：v1  
> **关联文档**：[[003-phase2-review]](003-phase2-review.md) | [[phase-3-report]](../reports/phase-3-report.md) | [[requirements.md]](../requirements.md)  
> **下次审查**：Phase 4 — 更多拟合模型 + 2D 拟合优化 + Notebook 集成
