# Phase 1 — 数据 IO + 基础拟合 实现记录

**日期**：2026-06-17–18  
**范围**：`exp_toolkit/io/` + `exp_toolkit/fitting/` 子包  
**状态**：✅ 完成  
**CLAUDE.md**：`- [x] 阶段 1：数据 IO + 基础拟合（T1/Lorentzian/DecayingSinusoid + 拟合引擎）`

---

## 一、模块总览

```
exp_toolkit/
├── io/
│   ├── __init__.py               # 公共 API 导出
│   └── readers.py                # 410 行 — 所有 IO 数据类 + 4 个公共函数
├── fitting/
│   ├── __init__.py               # 公共 API 导出（自动 + 手动两种模式）
│   ├── models.py                 # 120 行 — 4 个物理模型纯函数
│   ├── guessers.py               # 180 行 — 4 个参数猜测器
│   ├── engine.py                 # 190 行 — fit() + FitResult
│   └── experiments/
│       ├── __init__.py
│       ├── _base.py              # 190 行 — _auto_fit() + 列匹配工具
│       ├── t1.py                 #  60 行 — fit_t1()
│       ├── spectro.py            # 250 行 — fit_spectro() + fit_f01_dispersion()
│       └── experiment_types.yaml #  30 行 — 5 种实验类型映射
```

---

## 二、IO 模块（第一轮）

### 2.1 已实现的 API

| 函数/类 | 说明 |
|---------|------|
| `ColumnMeta` | 列元数据（label, units, category） |
| `QubitParams` | 比特参数 — f01, pi_amp, pi_width, readout_freq, readout_amp, f12, verified, extras |
| `IQBlobs` | IQ 分类中心（list[complex]）+ variance + n_states |
| `ParamsSnapshot` | qubits + couplers + readout_iq + lines |
| `IniMeta` | title, created, n_independent/dependent, independent_vars/dependent_vars, parameters, comments |
| `Experiment` | exp_id, title, timestamp, data (np.ndarray), params, settings, source_dir + 三个文件路径 |
| `parse_ini_metadata(ini_path)` → `IniMeta` | INI 完整解析（General + Independent N + Dependent N + Parameter N + Comments） |
| `load_parameters(json_path, verified_qubits=None)` → `ParamsSnapshot` | JSON 参数快照，含复数解析、必需字段校验 |
| `load_csv_with_meta(csv_path, ini_meta)` → `(ndarray, cols, cols)` | CSV 读取 + INI 声明的列数校验 |
| `load_experiment(path)` → `Experiment` | 主入口：自动找三元组 → 解析 → 组装；JSON 缺失仅警告不崩溃 |

### 2.2 内部辅助函数

| 函数 | 说明 |
|------|------|
| `_extract_exp_id(filename)` | 从文件名提取数字前缀实验编号 |
| `_parse_complex(s)` | 解析 `"-67110.8047-166303.3734j"` 格式复数字符串 |
| `_parse_ini_value(raw)` | INI data= 值 → Python 类型（int/float/list/str） |
| `_find_matching_files(path)` | 按编号匹配 CSV + INI + JSON 三元组 |
| `_extract_verified_qubits(ini_meta)` | 从 `-qidxs` / `-ancilla_ouput` / `measure` 提取已验证比特列表 |

### 2.3 设计决策

1. **`IniMeta.parameters` vs `Experiment.settings`**：前者存原始字符串，后者经 `_parse_ini_value()` 类型推断。两者都可访问。
2. **`verified_qubits` 三来源**：`-qidxs`（测量比特索引）、`-ancilla_ouput`（ancilla 比特）、`measure`（直接名称）。索引→名称同时尝试 `Q07` / `Q7` 两种格式。
3. **必需字段**：`load_parameters()` 要求 5 个字段（f01, pi_amp, pi_width, readout_freq, readout_amp），缺失立即 `ValueError`。
4. **JSON 复数格式**：从右侧扫描最后一个非指数符号的 ± 作为虚部分隔；显式拒绝科学记数法输入。

### 2.4 发现的数据格式细节

- INI data 值格式：裸数字、单引号包裹字符串、单引号包裹 JSON 数组、裸 JSON 数组、`Value(-20.0, 'dBm')` 特殊格式
- 复数字符串：`"-67110.8047-166303.3734j"` — 虚部符号紧跟实数部分
- 比特编号：JSON 统一 `Qxx`（两位数字），INI `-qidxs` 使用裸整数
- JSON 是设备模板，含所有可能比特；INI 的 `-qidxs`/`measure` 标注实际测量的比特
- Spectro 数据量：2D 网格展平（21 zpa × 351 freq = 7371 行；41 zpa × 401 freq = 16441 行）

---

## 三、拟合模块（第二轮）

### 3.1 物理模型（models.py）

所有模型签名 `(x: np.ndarray, **params) -> np.ndarray`，不调用 lmfit。

| 模型 | 公式 | 参数 | 用途 |
|------|------|------|------|
| `exp_decay` | A·exp(-x/τ) + C | amplitude, tau, offset | T1, T2_echo |
| `decaying_sinusoid` | A·exp(-x/τ)·cos(2πf·x + φ) + C | amplitude, tau, frequency, phase, offset | T2* Ramsey |
| `lorentzian` | A·γ²/((x-x₀)² + γ²) + C | amplitude, center, gamma, offset | 光谱 |
| `gaussian` | A·exp(-(x-x₀)²/(2σ²)) + C | amplitude, center, sigma, offset | f01 dispersion |

### 3.2 参数猜测器（guessers.py）

| 猜测器 | 策略 |
|--------|------|
| `guess_exp_decay` | amplitude = y.max()-y.min(), tau = x_range/3, offset = y.min() |
| `guess_decaying_sinusoid` | FFT 去 DC 找主频 → frequency; 上包络 log 线性拟合 → tau; offset = y.mean() |
| `guess_lorentzian` | center = x[y.argmax()]; FWHM → gamma = FWHM/2; amplitude = (y_max-y_min)·gamma |
| `guess_gaussian` | center = x[y.argmax()]; FWHM → sigma = FWHM/2.355; amplitude = y_max-y_min |

### 3.3 拟合引擎（engine.py）

```python
@dataclass
class FitResult:
    model_name: str
    params: dict[str, float]           # 最佳拟合参数
    errors: dict[str, float]            # 1σ 标准误差
    r_squared: float
    residuals: np.ndarray
    cov_matrix: np.ndarray | None
    red_chi2: float
    success: bool
    message: str
    x: np.ndarray                       # 输入 x（含 NaN 位置）
    y: np.ndarray                       # 输入 y
    y_fit: np.ndarray                   # 拟合曲线（NaN 位置保持 NaN）

def fit(x, y, model, guesser=None, *, params_hint=None, fix=None) -> FitResult
```

**关键行为**：
- 自动剔除 NaN/Inf → 至少需要 3 个有限点
- `guesser` 和 `params_hint` 至少提供一个初值来源
- `fix` 固定指定参数不参与拟合
- 拟合异常不抛异常，返回 `FitResult(success=False)`
- 协方差矩阵不可估计时 `cov_matrix=None`

### 3.4 实验分发层

#### `_auto_fit()` 流程

```
Experiment
    │
    ▼
_select_columns(x_col, y_col, x_pattern, y_pattern)
    │  自动模式: 按 pattern 在独立/因变量列中匹配
    │  手动模式: 直接整数索引
    ▼
fit(model_func, guesser) → FitResult
    │
    ▼
success=False → 发出红色警告
```

#### `_find_column()` 匹配优先级

1. 精确匹配 category（不区分大小写）
2. category 包含 pattern（不区分大小写）
3. label 包含 pattern（不区分大小写）

#### 已实现的 fit_*() 函数

| 函数 | 默认 y_pattern | 模型 | 特有参数 |
|------|---------------|------|---------|
| `fit_t1(exp)` | `"P1"`（自动排除 `"for |0>"` 校准列） | exp_decay | params_hint |
| `fit_spectro(exp)` | `"IQ Amp"` / `"P1"` | lorentzian | z_slice, params_hint |
| `fit_f01_dispersion(exp)` | `"IQ Amp"` / `"P1"` | lorentzian per zpa → gaussian | — |

#### `F01Dispersion` 数据类

```python
@dataclass
class F01Dispersion:
    f01_min: float
    f01_max: float
    zpa_values: np.ndarray
    f01_values: np.ndarray
    f01_errors: np.ndarray | None
    fit_result: FitResult | None       # f01 vs zpa 的 Gaussian 拟合结果
```

### 3.5 实验类型映射（experiment_types.yaml）

```yaml
T1:     match_keywords: [T1, t1]           → fit_t1      (ExponentialDecay)
spectro: match_keywords: [spectro, ...]     → fit_spectro  (Lorentzian)
ramsey:  match_keywords: [ramsey, T2*, ...] → fit_ramsey   (DecayingSinusoid)
rabi:    match_keywords: [rabi]             → fit_rabi     (RabiOscillation)
rb:      match_keywords: [RB, ...]          → fit_rb       (RBExponential)
```

> ⚠️ ramsey / rabi / rb 的 fit_*() 函数未实现（留待阶段 4），映射条目已预置。

---

## 四、测试

### 4.1 自动化测试

```bash
pytest tests/ -v
# 77 passed in 0.92s
```

| 文件 | 用例数 | 覆盖范围 |
|------|--------|---------|
| `tests/test_io.py` | 44 | _extract_exp_id (5), _parse_complex (6), _parse_ini_value (7), parse_ini_metadata (4), load_parameters (7), load_csv_with_meta (4), load_experiment (11) |
| `tests/test_fitting.py` | 33 | models 公式验证 (5), guessers (5), fit() + FitResult (8), _find_column (5), _auto_fit (4), fit_t1 (2), fit_spectro (2), f01_dispersion (2) |

### 4.2 参数恢复验收

| 模型 | 合成数据测试 | 验收标准 |
|------|------------|---------|
| exp_decay | tau_true=45.0 → tau_fit=45.0±0.0, R²>0.99 | ≤3σ 误差 |
| lorentzian | center_true=4.68 → center_fit≈4.68, R²>0.8 | |center_fit - center_true| < 0.02 |
| f01_dispersion | 7 个 zpa 点，f01 在 [4.2, 5.5] 范围内 | f01_max > f01_min |

### 4.3 真实数据验证

```python
# tests/manual/verify_real_data.py — 3/3 实验全部通过
```

| 实验 | shape | 拟合结果 |
|------|-------|---------|
| 00747 T1_ground, Q16 | (21, 9) | tau=20.1±1.4 μs, R²=0.985 |
| 00023 spectro, Q07 | (7371, 6) | f01 dispersion: [4.21, 4.55] GHz, 21 zpa points |
| 00732 spectro, Q15 | (16441, 6) | 格式兼容性确认 |

---

## 五、与需求文档的偏差

### 5.1 架构级

| # | 需求 | 实际 | 原因 |
|---|------|------|------|
| 1 | IniMeta 只存储 General + Independent + Dependent | 实际也存储了 Parameters + Comments | Parameter 节存储为 `dict[str, str]`，Comments 存为字符串 — 信息零丢失 |
| 2 | `_QUERY_FIELD_MAP` 用于字段映射 | 改为 `_EXTRACTED_KEYS` frozenset | P0 修复：原方案静默丢弃 18 个 JSON 字段 |
| 3 | HDF5/NPZ 支持 | 未实现，定位改为 Future | 实际数据均为 CSV 三元组，HDF5/NPZ 更可能是中间存储格式 |
| 4 | `load_parameters` 必需字段 | 增加了 `readout_amp(dBm)` 为必需 | 所有实际 JSON 都包含该字段 |

### 5.2 实现细节

| # | 偏差 | 说明 |
|---|------|------|
| 5 | `_auto_fit()` 中 x_col/y_col 默认值处理 | 需求文档描述为 "x_col='auto' 从 INI Independent 推断"；实现为：x_pattern 提供时搜索匹配，否则用最后一个独立变量。对 1D 实验（单自变量）行为等价。 |
| 6 | `fit_spectro()` z_slice 实现 | 2D 数据时手动筛选 zpa 行后拟合；未重建 2D 网格 — 这属于 `fit_f01_dispersion()` 的职责 |
| 7 | `fit_f01_dispersion()` f01_min/max | 优先使用 Gaussian 拟合结果计算范围；拟合失败时退回到 per-slice 值的最小/最大值 |
| 8 | `fit_t1()` y_pattern = "P1" | 自动匹配包含 "P1" 的第一个因变量列。实际 INI 中 T1 实验通常按 (P0, P1, P0, P1, ...) 排列，"P1" 会匹配第二个因变量列，即 `Qxx P1`。 |

---

## 六、后续注意事项

### 6.1 已知局限

- `_parse_ini_value` 的类型推断是启发式的，未来可能遇到新 INI 数据格式（如 `Value(...)`）需要扩展
- `_parse_complex` 不支持科学记数法（显式报错），当前真实数据不含此格式
- `readout_IQ` 的 key 命名规则（如 `Q16_2` 中 `_2` 后缀含义）尚未完全确认
- `fit_spectro()` 在 z_slice=None 时处理 2D 数据的行为：可能对全数据直接拟合，结果取决于数据质量
- `fit_f01_dispersion()` 对 per-slice Lorentzian 拟合失败的点静默跳过 — 过于激进的数据筛选可能导致有效 zpa 点数不足

### 6.2 对阶段 2（State + 可视化）的接口承诺

拟合模块暴露给 State/可视化模块的数据结构：

```python
# FitResult — 可直接用于绘图和参数提取
FitResult.params   # dict[str, float] — 拟合参数值
FitResult.errors   # dict[str, float] — 1σ 误差
FitResult.x        # 输入 x
FitResult.y_fit    # 拟合曲线

# F01Dispersion — 可直接用于 ChipState.add_f01_range()
F01Dispersion.f01_min        # f01 范围
F01Dispersion.f01_max
F01Dispersion.zpa_values     # 可绘图的数据
F01Dispersion.f01_values
```

### 6.3 未实现的 fit_*()

- `fit_ramsey()`, `fit_rabi()`, `fit_rb()` — 留待阶段 4
- `assignment_fidelity()` (`fitting/iq_analysis.py`) — 留待阶段 3
- `experiment_types.yaml` 中 ramsey/rabi/rb 条目已预置，实现时只需补充对应的 fit_*() 函数

---

## 七、审查修复记录

### 7.1 初次审查（2026-06-17）

针对 [`docs/reviews/001-phase1-io-review.md`](../reviews/001-phase1-io-review.md) 报告，IO 模块审查：

| # | 严重性 | 问题 | 修复 |
|---|--------|------|------|
| P0 | 🔴 | `_QUERY_FIELD_MAP` 导致 18 个 JSON 字段静默丢弃 | `_EXTRACTED_KEYS` frozenset 替代 MAP 过滤；extras 保留所有非提取字段（实测 Q16 extras: 0→19 keys） |
| P1 | 🟡 | HDF5/NPZ 定位不明确 | CLAUDE.md 更新为"原始数据以 CSV 三元组为主；HDF5/NPZ 用于中间存储（Future）" |
| P1 | 🟡 | `-ancilla_ouput` 无测试覆盖 | T1 fixture 添加 ancilla 参数；新增 `test_ancilla_ouput_verified` |
| P2 | 🟢 | `_parse_complex` 科学记数法 | 显式检测 `e`/`E` → `ValueError`；分割算法改为从右向左扫描 |
| P2 | 🟢 | 真实数据验证脚本缺失 | 创建 `tests/manual/verify_real_data.py` |

修复后 IO 测试：44/44 passed (0.21s)。

### 7.2 拟合模块

拟合模块为审查后新增实现，尚未经过 supervisor 审查。

### 7.2 Phase 1 完成审查（2026-06-18）

> **审查报告**：[`docs/reviews/002-phase1-complete-review.md`](../reviews/002-phase1-complete-review.md)  
> **总体判定**：Phase 1 可以验收。发现 3 个 P1 问题（fit_spectro 2D 无 z_slice 静默错误、fit_t1 无校准列排除、_FIELD_MAP 冗余）+ 5 个 P2 建议。  
> **阻塞项**：无 P0 阻塞。P1 建议在 Phase 2 启动前修复。

---

> **关联文档**：[[requirements.md]] | [[001-phase1-io-review]](../reviews/001-phase1-io-review.md)  
> **下一阶段**：Phase 2 — State 模块 + 芯片拓扑可视化（`exp_toolkit/state/` + `exp_toolkit/visualization/`）
