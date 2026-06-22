# 审查报告 #002 — Phase 1 完成审查（IO + 基础拟合）

**审查日期**：2026-06-18  
**审查范围**：`exp_toolkit/io/` + `exp_toolkit/fitting/` 全部文件 + `tests/test_io.py` + `tests/test_fitting.py` + `tests/manual/verify_real_data.py`  
**审查基准**：`docs/requirements.md` v3 + `CLAUDE.md` 架构约定 + [审查报告 #001](001-phase1-io-review.md) 修复清单  
**上一审查**：[#001](001-phase1-io-review.md)（仅 IO 模块，发现 1 P0 + 2 P1 + 2 P2）  
**审查人角色**：Supervisor（不主动写实现代码）

---

## 一、总体判定

| 维度 | 评级 | 说明 |
|------|------|------|
| #001 修复完成度 | 🟢 全部通过 | P0/P1/P2 共 5 项全部修复 |
| API 与需求一致性 | 🟢 良好 | 拟合模块 API 与 §3.2 设计吻合 |
| 架构约定遵守 | 🟢 良好 | 模型为纯函数、fit_*() 独立分发、FitResult 无持久化 |
| 测试覆盖 | 🟢 良好 | 77/77 passed，含参数恢复验收 |
| 代码质量 | 🟡 3 个 P1 建议 | 详见 §三 |
| 文档准确性 | 🟡 1 处不匹配 | 模型命名约定与代码不一致 |

**结论：Phase 1 可以验收。3 个 P1 问题建议在 Phase 2 启动前修复，其余为 P2 改进。**

---

## 二、#001 修复清单核验

| # | 严重性 | 问题 | 修复状态 | 验证证据 |
|---|--------|------|---------|---------|
| P0 | 🔴 | `_QUERY_FIELD_MAP` 静默丢弃 18 字段 | ✅ 已修复 | `_EXTRACTED_KEYS` frozenset（仅 6 个已提取字段）；`test_p0_extras_preserved` 通过 |
| P1 | 🟡 | HDF5/NPZ 定位不明确 | ✅ 已澄清 | CLAUDE.md 已更新为"中间存储（Future）" |
| P1 | 🟡 | `-ancilla_ouput` 无测试覆盖 | ✅ 已修复 | `test_ancilla_ouput_verified` 通过 |
| P2 | 🟢 | `_parse_complex` 科学记数法脆弱 | ✅ 已修复 | 显式拒绝 `e`/`E` → `ValueError`；从右向左扫描；`test_scientific_notation_raises` 通过 |
| P2 | 🟢 | 真实数据验证脚本缺失 | ✅ 已修复 | `tests/manual/verify_real_data.py` 已创建 |

**#001 全部修复项验证通过。**

---

## 三、新发现问题

### 🔴 P1-1 — `fit_spectro()` 在 2D 数据上不指定 z_slice 时静默产生垃圾拟合

**位置**：`exp_toolkit/fitting/experiments/spectro.py:53–78`

**问题**：当 `z_slice=None` 且数据是 2D（有 zpa + dr_freq），`fit_spectro()` 走 `else` 分支，调用 `_auto_fit()` 对**全部行**做 Lorentzian 拟合。这意味着不同 zpa 下不同 f01 的数据被混合在一起拟合，结果必然是垃圾。

```python
# spectro.py 当前逻辑：
if z_slice is not None and len(exp.independent_vars) >= 2:
    # 正确：筛选特定 zpa 后拟合
    ...
else:
    result = _auto_fit(exp, ...)  # ← 对 2D 全数据直接拟合！
```

**影响**：
- 用户调用 `fit_spectro(exp)` 不传 `z_slice` 时，如果恰巧 `success=True`（可能因为数据量大噪声小），会得到完全错误的 f01
- 即使 `success=False`，用户也只会看到通用警告"拟合未收敛"，不知道根本原因是忘记指定 z_slice

**建议修复**：
> 在 `else` 分支中检测 `len(exp.independent_vars) >= 2`，如果是 2D 数据且 z_slice 未指定，自动选择第一个（或中间的）zpa 值并发出信息性警告，而不是对全数据拟合。或者至少抛出 `ValueError` 要求用户显式指定 z_slice。

### 🟡 P1-2 — `fit_t1()` 的 "P1" 列匹配依赖列序，对校准列无显式排除

**位置**：`exp_toolkit/fitting/experiments/t1.py:55` + `exp_toolkit/fitting/experiments/_base.py:38–54`

**问题**：`_find_column()` 按优先级 `精确匹配 → 子串匹配 → label匹配` 返回**第一个**命中。T1 实验的因变量列通常是：

```
[Q16 P0, Q16 P1, P0, P1, Q16 P0 for |0>, Q16 P1 for |0>, P0 for |0>, P1 for |0>]
```

`"P1"` 的子串匹配第一个命中是 index 1 = `"Q16 P1"` ✅。但这依赖于 `"Q16 P1"` 在 `"Q16 P1 for |0>"` 之前。如果 INI 列序不同（例如某些设备将校准列放在前面），就会匹配到校准列。

**对比**：phase-1-notes §5.2 声称 "fit_t1() y_pattern = 'P1' 自动匹配包含 'P1' 的第一个因变量列。实际 INI 中 T1 实验通常按 (P0, P1, P0, P1, ...) 排列，'P1' 会匹配第二个因变量列，即 Qxx P1。" 这段承认了列序依赖但未将其标记为风险。

**建议修复**：
> `_find_column()` 增加 `exclude_pattern: str | None` 参数；`fit_t1()` 调用时传 `exclude_pattern="for |0>"`，跳过校准列。对 T1 实验这应成为默认行为。

### 🟡 P1-3 — `_FIELD_MAP` 未使用，造成代码困惑

**位置**：`exp_toolkit/io/readers.py:602–628`（`load_parameters()` 函数内）

**问题**：修复 #001-P0 时新增了 `_EXTRACTED_KEYS` frozenset 作为过滤依据，但保留了原来的 `_FIELD_MAP`（24 个条目）。`_FIELD_MAP` 在当前代码中**完全未被使用**——既不做过滤（已由 `_EXTRACTED_KEYS` 替代），也不做字段重命名（无代码读取它）。

```python
_FIELD_MAP: dict[str, str] = {
    "f01(GHz)": "f01",
    "f12(GHz)": "f12",
    ...  # 24 个条目
}
# ↑ 整个 dict 从未被引用
```

**影响**：维护者可能错误地认为修改 `_FIELD_MAP` 会影响行为。当 Phase 3 需要从这里取值时会困惑。

**建议修复**：
> 删除 `_FIELD_MAP` 或将其移到函数外部作为模块级常量，并加注释说明它仅作文档用途。如果未来需要 JSON key → Python attr 的映射逻辑，届时再激活。

---

### 🟢 P2 建议（非阻塞，可择机处理）

#### P2-1 — 模型名称为函数名而非需求文档中的 PascalCase

**位置**：`exp_toolkit/fitting/engine.py:124`

```python
model_name = getattr(model, "__name__", "unknown")
# 结果：model_name = "exp_decay"，而非需求文档中的 "ExponentialDecay"
```

**phase-1-notes §3.3** 声称 `model_name: str` 示例为 `"ExponentialDecay"`，但实际是函数的 `__name__` = `"exp_decay"`。

**建议**：文档与代码统一。可以在模型中加 `__model_name__` 属性，或更新文档说明用 snake_case。

#### P2-2 — `fit_f01_dispersion()` 的 f01_min/max 推算逻辑对负幅度 Gaussian 不正确

**位置**：`exp_toolkit/fitting/experiments/spectro.py:233–240`

```python
f01_at_center = amplitude + offset  # Gaussian 峰值
f01_far = offset                     # Gaussian 尾翼
f01_min = min(f01_at_center, f01_far)
f01_max = max(f01_at_center, f01_far)
```

这段逻辑假设 Gaussian 的 `amplitude` 为正（峰向上），此时 `center` 附近值最大。但 f01 dispersion 中 Gaussian 可能是谷（f01 在特定 bias 处最小），此时 `amplitude` 为负，`min`/`max` 的物理含义颠倒——`f01_min` 实际是偏移最小的值（即离 offset 最远的值），而不是 f01 物理范围的最小值。

**评估**：对于真实数据，f01 dispersion 通常是正的 Gaussian（f01 在 sweet spot 最大），这个逻辑碰巧正确。但如果遇到 inverted Gaussian（某些 transmon 参数下 f01 在 sweet spot 最小），min/max 会对调。

**建议**：加注释标记 `TODO(DOMAIN)`，或改用 zpa 轴上的实际 f01 范围（直接对 `f01_arr` 取 min/max）作为权威值，Gaussian 拟合结果作为补充。

#### P2-3 — `experiment_types.yaml` 已定义但未接入调度逻辑

**位置**：`exp_toolkit/fitting/experiments/experiment_types.yaml`

**问题**：YAML 定义了 5 种实验类型映射，但代码中没有任何 `_infer_experiment_type()` 或 `_dispatch_fit()` 函数使用它。phase-1-notes 已备注"ramsey/rabi/rb 的 fit_*() 未实现，映射条目已预置"，这是合理的 Phase 1 范围定义，但需在 Phase 2/4 时完成接线。

#### P2-4 — `fit_spectro()` z_slice 分支中 `_select_columns()` 被调用两次

**位置**：`exp_toolkit/fitting/experiments/spectro.py:65–81`

第一次在 `if z_slice` 分支中声明式地调用 `_select_columns()`，取到 `x_full, y_full` 后做 mask；然后又调用一次（代码路径不同但目的相同）。实际只需一次列查找然后 mask。不影响正确性，仅效率问题。

#### P2-5 — `guess_decaying_sinusoid` 硬编码 phase=0.0

**位置**：`exp_toolkit/fitting/guessers.py:118`

```python
"phase": 0.0,
```

Docstring 已解释"FFT 相位估计误差大，拟合器自行调整"。这是合理的工程取舍，但建议标记 `TODO(DOMAIN)` 以便未来探讨是否用 Hilbert 变换或复数 FFT 相位改进。

---

## 四、架构约定合规性审查

逐条对照 CLAUDE.md 架构约定：

| # | 约定 | 判定 | 证据 |
|---|------|------|------|
| 1 | 模型纯函数 `(x, **params) -> np.ndarray`，不调用 lmfit | ✅ | `models.py` 4 个函数均为纯 numpy 运算 |
| 2 | 按实验类型独立 `fit_*()` 函数 | ✅ | `fit_t1()`, `fit_spectro()`, `fit_f01_dispersion()` 已实现 |
| 2 | 禁止用字符串参数分发所有实验类型 | ✅ | 无 `fit_experiment(exp_type=...)` 函数 |
| 3 | FitResult 不自动持久化 | ✅ | FitResult 是纯 dataclass，无 `save()` 方法 |
| 4 | 拓扑相关 — Phase 2 关注 | — | 不适用 |
| 5 | 参数标注测量条件 — Phase 2 关注 | ⚠️ | 拟合模块当前未从 `exp.params` 提取 f01 标注（见 §五） |

### §五 拟合→State 接口预留情况

Phase 1 的拟合模块暴露给 Phase 2 State 模块的数据结构：

| 接口 | 当前状态 | Phase 2 就绪？ |
|------|---------|--------------|
| `FitResult.params` / `.errors` | ✅ 可用 | ✅ |
| `FitResult.x` / `.y_fit`（绘图用） | ✅ 可用 | ✅ |
| `F01Dispersion.f01_min` / `.f01_max` | ✅ 可用（见 P2-2 注意事项） | ⚠️ 验证 f01 推导逻辑 |
| `F01Dispersion.zpa_values` / `.f01_values` | ✅ 可用 | ✅ |
| `exp.params.qubits[name].f01`（测量频率） | ⚠️ fit_*() 未提取 | ❌ 拟合函数不自动标注 freq_GHz |

**注意**：按照 CLAUDE.md 架构约定 5 和 requirements.md §3.4.2，所有参数需标注测量时的比特频率。当前 `fit_t1()` 返回的 `FitResult` 不包含 `freq_GHz`。这个标注责任属于 State 模块（用户调用 `state.add_T1(freq_GHz=...)` 时手动传入），还是拟合模块应自动从 `exp.params` 提取？requirements.md §4.2 的示例代码中，`freq_GHz` 由用户从 `exp.params.qubits["Q16"].f01` 获取并传入 `state.add_T1()`。**这符合"拟合与持久化解耦"原则。**但需在 Phase 2 的 API 文档中明确说明这一约定。

---

## 五、测试质量评估

| 维度 | 评估 | 说明 |
|------|------|------|
| 模型公式验证 | 🟢 充分 | 形状、边界值、包络验证 |
| 猜测器基本功能 | 🟢 充分 | 量级恢复、全 NaN 报错 |
| fit() 参数恢复 | 🟢 充分 | ExponentialDecay ≤3σ, Lorentzian center 偏差 <0.02 |
| fit() 错误路径 | 🟢 充分 | 空输入、形状不匹配、无初值、固定参数 |
| 列匹配 | 🟢 充分 | 精确、不区分大小写、子串、label fallback |
| fit_t1 端到端 | 🟢 充分 | 参数恢复 + params_hint |
| fit_spectro 端到端 | 🟢 充分 | 单切片、无切片、f01_dispersion 两步法 |
| **缺失：y_pattern="P1" 排除校准列** | 🔴 无测试 | 没有测试验证 "P1 for \|0>" 不会被选中 |
| **缺失：fit_spectro 2D 无 z_slice 行为** | 🟡 无测试 | `test_fit_spectro_no_slice` 使用 z_slice=None，但合成数据中所有 zpa 的 f01 相同（4.7GHz），掩盖了混合拟合问题 |

**建议补充测试**：
1. 构造 T1 Experiment 其中 `"P1 for |0>"` 排在 `"P1"` 前面，验证 `fit_t1()` 仍正确选择后者
2. 构造 2D Spectro Experiment 其中不同 zpa 有不同 f01，验证 `z_slice=None` 时给出明确错误或警告

---

## 六、phase-1-notes.md 准确性核验

| # | Notes 声明 | 核验结果 |
|---|-----------|---------|
| 1 | 模型签名 `(x: np.ndarray, **params) -> np.ndarray` | ✅ 确认 |
| 2 | `exp_decay` 等 4 个模型已实现 | ✅ 确认 |
| 3 | 4 个猜测器策略正确 | ✅ 确认（phase=0.0 硬编码已备注） |
| 4 | `FitResult` 字段与需求一致（含 x, y, y_fit） | ✅ 确认 |
| 5 | `_auto_fit()` 流程：列选择 → 拟合 → 警告 | ✅ 确认 |
| 6 | `_find_column()` 三级匹配优先级 | ✅ 确认 |
| 7 | `fit_spectro()` z_slice 实现 | ✅ 确认（但见 P1-1） |
| 8 | `fit_f01_dispersion()` 两步法 + 降级策略 | ✅ 确认（但见 P2-2） |
| 9 | 77 tests passed in 0.92s | 🟡 实际 1.00s（系统波动，无实质差异） |
| 10 | IO 44 + Fitting 33 = 77 | ✅ 确认 |
| 11 | 参数恢复验收：exp_decay tau 45.0±0.0 | ✅ 测试通过 |
| 12 | 参数恢复验收：lorentzian center 4.68 | ✅ 测试通过 |
| 13 | 真实数据 3/3 验证通过 | ✅ 脚本就绪（需 data/ 下有效数据文件才能实际执行） |
| 14 | P0 修复：`_EXTRACTED_KEYS` frozenset | ✅ 确认 |

---

## 七、与 Phase 2 的接口契约确认

Phase 2（State + 可视化）模块将从以下接口获取数据：

### 7.1 从 IO 模块

```python
exp = load_experiment(path)
# → exp.params.qubits[name].f01          # 比特频率
# → exp.params.qubits[name].verified      # 是否被本次实验确认
# → exp.params.qubits[name].extras        # 所有非结构化字段
# → exp.params.readout_iq[key]            # IQ 分类器
# → exp.exp_id, exp.title, exp.timestamp  # 实验标识
```

### 7.2 从拟合模块

```python
# T1 拟合
r = fit_t1(exp)
# → r.params["tau"], r.errors["tau"]    # T1 值 + 误差
# → r.success, r.r_squared              # 质量控制

# f01 色散
disp = fit_f01_dispersion(exp)
# → disp.f01_min, disp.f01_max          # f01 范围
# → disp.f01_values, disp.zpa_values    # 色散曲线数据
```

### 7.3 Phase 2 需注意的约定

1. **freq_GHz 标注**：用户负责从 `exp.params.qubits[name].f01` 提取后传入 `state.add_T1(freq_GHz=...)`
2. **verified 标记**：`exp.params.qubits[name].verified` 已由 IO 模块自动设置（从 INI `-qidxs`/`measure` 提取）
3. **历史保留**：`add_T1()` 等不应覆盖旧值，应 append 到列表（见 requirements.md §3.4.2）
4. **FitResult 不持久化**：用户决定哪些拟合结果写入 ChipState

---

## 八、行动清单

### Phase 2 启动前（建议修复）

| 优先级 | 编号 | 问题 | 预计工作量 |
|--------|------|------|-----------|
| 🔴 P1 | P1-1 | `fit_spectro()` 2D 无 z_slice 静默错误 | 小（加检查和自动选择） |
| 🟡 P1 | P1-2 | `fit_t1()` P1 匹配无校准列排除 | 小（加 exclude_pattern 参数） |
| 🟡 P1 | P1-3 | `_FIELD_MAP` 未使用 | 极小（删除或标注） |

### Phase 2 期间（择机处理）

| 优先级 | 编号 | 问题 |
|--------|------|------|
| 🟢 P2 | P2-1 | 模型命名统一（snake_case vs PascalCase） |
| 🟢 P2 | P2-2 | f01 dispersion min/max 推算逻辑边界情况 |
| 🟢 P2 | P2-4 | `fit_spectro()` z_slice 分支双重调用优化 |
| 🟢 P2 | — | 补充校准列排除测试 |
| 🟢 P2 | — | 补充 2D 无 z_slice 行为的正确性测试 |

### Phase 4（远期，不阻塞）

| 编号 | 问题 |
|------|------|
| P2-3 | `experiment_types.yaml` 接入调度逻辑 + `fit_ramsey`/`fit_rabi`/`fit_rb` 实现 |
| P2-5 | `guess_decaying_sinusoid` phase 估计改进 |

---

> **审查报告版本**：v1  
> **关联文档**：[[001-phase1-io-review]](001-phase1-io-review.md) | [[phase-1-notes]](../notes/phase-1-notes.md) | [[requirements.md]](../requirements.md)  
> **下次审查**：Phase 2 State 模块 + ChipTopology + ChipArtist 完成后
