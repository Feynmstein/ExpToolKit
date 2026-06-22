# 审查报告 #001 — Phase 1 IO 模块

**审查日期**：2026-06-17  
**审查范围**：`exp_toolkit/io/` 子包（`__init__.py`, `readers.py`）+ `tests/test_io.py`  
**审查基准**：`docs/requirements.md` v3 + `CLAUDE.md` 架构约定  
**审查人角色**：Supervisor（不主动写实现代码）  
**下一执行者**：实现侧 Claude Code 会话

---

## 一、总体判定

| 维度 | 评级 | 说明 |
|------|------|------|
| API 与需求一致性 | 🟢 良好 | 4 个公开函数 + 6 个数据类全部匹配需求文档草稿 |
| 架构约定遵守 | 🟡 1 项偏离 | HDF5/NPZ 支持缺失（需澄清定位） |
| 测试覆盖 | 🟢 良好 | 41 用例全部通过，覆盖正常+错误路径 |
| 错误处理 | 🟢 良好 | 遵循 §7.1 约定 |
| 类型标注 | 🟢 良好 | 公开 API 均有完整标注 |

**结论：IO 模块可以接受，但有一个 P0 数据丢失 bug 必须在拟合模块开始前修复。**

---

## 二、发现的问题

### 🔴 P0 — `_QUERY_FIELD_MAP` 导致 JSON 参数静默丢弃

**位置**：`exp_toolkit/io/readers.py:602–662`

**问题描述**：

`_QUERY_FIELD_MAP` 定义了 24 个 JSON → Python 的字段映射。其用途是标记"已知字段"以避免它们进入 `extras`。但实际只有 6 个字段被提取到 `QubitParams` 结构体：

| 被提取 (6) | 在 MAP 中但被丢弃 (18) |
|------------|----------------------|
| `f01(GHz)` → `f01` | `readout_lo_freq(GHz)`, `readout_lo_power(dBm)` |
| `f12(GHz)` → `f12` | `dr_lo_freq(GHz)`, `dr_lo_power(dBm)` |
| `pi_amp` → `pi_amp` | `offset`, `shape` |
| `pi_width(ns)` → `pi_width` | `pi_drag(ns)`, `pihalf_amp`, `pihalf_width(ns)`, `pihalf_drag(ns)` |
| `readout_freq(GHz)` → `readout_freq` | `pi12_amp`, `pi12_width(ns)`, `demod_len` |
| `readout_amp(dBm)` → `readout_amp` | `gate_zpa`, `gate_zpa_start(us)`, `readout_zpa`, `readout_zpa_start(us)` |
| | `readout3_freq(GHz)`, `readout3_amp(dBm)` |

**关键逻辑** (`readers.py:649–651`)：
```python
for json_key, val in qdata.items():
    if json_key not in _QUERY_FIELD_MAP:
        extras[json_key] = val
```

在 `_QUERY_FIELD_MAP` 中的 18 个字段**既不在 QubitParams 里，也不在 extras 里**——永久丢失。后续拟合模块无法访问 `pi_drag(ns)`, `gate_zpa`, `demod_len` 等参数。

**影响范围**：
- `fit_rabi()` 需要 `pi_drag` 做 DRAG 校准 → 无法获取
- `fit_spectro()` 可能需要 `gate_zpa` / `readout_zpa` 理解 bias 范围 → 无法获取
- `assignment_fidelity()` 可能需要 `demod_len` → 无法获取
- 任何用到 π/2 脉冲、π12 脉冲的拟合 → 参数不可用

**修复方向**（不写具体代码，供实现侧参考）：

> 方案 A：将所有 `_QUERY_FIELD_MAP` 中的键**都保留到 extras**。将 MAP 的用途从"排除列表"改为"文档性映射"，不再用于过滤。新增一个单独的 `_EXCLUDE_FROM_EXTRAS` 集合（空或仅含冗余字段）。
>
> 方案 B：扩展 `QubitParams` 数据类，将常用的 18 个字段作为可选属性（`float | None = None`）。但这会让 QubitParams 膨胀。
>
> **推荐方案 A**：改动最小，向后兼容，不丢失任何数据。拟合模块从 `extras` 中按需取值。

### 🟡 P1 — CLAUDE.md 中 HDF5/NPZ 的定位不明确

**位置**：`CLAUDE.md` 第 19 行

```
- 数据 I/O：支持 HDF5 和 NPZ 格式；CSV/Excel 仅用于人工可读的元数据表
```

当前 IO 模块只实现了 CSV 读取。HDF5/NPZ 完全未涉及。

**需要决策**：HDF5/NPZ 的角色是什么？

- **如果是中间存储格式**（处理后的 Experiment / FitResult 保存为 HDF5）：应在 requirements.md 或后续阶段中明确，更新 CLAUDE.md 措辞。
- **如果是原始数据读取格式**（设备直接输出 HDF5）：IO 模块需要新增 reader。

**建议**：在开始 Phase 2 前，明确此定位并更新 CLAUDE.md 相应行。当前判断：实际实验数据全部为 CSV 三元组，HDF5/NPZ 更可能是**中间存储格式**，应在 State 模块或 IO 模块的 writer 部分实现。

### 🟡 P1 — `-ancilla_ouput` 提取路径无测试覆盖

**位置**：`exp_toolkit/io/readers.py:490–500`（`_extract_verified_qubits` 中检查 `-ancilla_ouput` 的分支）

两个测试 fixture（`_write_t1_files`, `_write_spectro_files`）的 INI 均不含 `-ancilla_ouput` 参数。该代码路径未被 pytest 覆盖。

**修复**：在 T1 fixture 的 INI 中增加一个 `-ancilla_ouput` Parameter 节，并在端到端测试中断言对应比特被标记为 verified。

### 🟢 P2 — `_parse_complex` 无法处理科学记数法

**位置**：`exp_toolkit/io/readers.py:238–260`

正则 `(?<=[0-9.])[-+]` 会误匹配科学记数法中的指数符号（如 `1.5e-5+2j` → 在 `-5` 处错误切分）。

**评估**：当前真实数据（`-67110.8047-166303.3734j`）不含科学记数法，暂时安全。但这是隐性炸弹。

**建议**：至少添加显式检测——若字符串含 `e` 或 `E`，抛出 `ValueError("Scientific notation in complex numbers is not yet supported")`，而不是静默产生错误数值。健壮修复可考虑从右侧向左扫描找最后一个 `+`/`-`（跳过末尾的 `j`）。

### 🟢 P2 — 真实数据端到端验证脚本待确认

**位置**：`docs/phase-1-notes.md` 声称

> 三个真实实验数据端到端验证通过（00747 T1 / 00023 Spectro IQ / 00732 Spectro Prob）

但 `tests/test_io.py` 中全部使用合成数据（`tmp_path` fixture），且 `tests/manual/` 目录不存在。

**建议**：确认验证脚本的位置（可能在实现者本地未提交），并按 §7.3 约定放入 `tests/manual/`。若确实未编写脚本，修正 phase-1-notes 中的措辞为"三个真实数据格式已人工审查，格式兼容性已确认"。

---

## 三、Phase 1 Notes 准确性核验

对 `docs/phase-1-notes.md` 各项声明的逐条验证：

| # | 声明 | 核验结果 |
|---|------|---------|
| 1 | `ColumnMeta`, `QubitParams`, `IQBlobs`, `ParamsSnapshot`, `IniMeta`, `Experiment` 6 个数据类 | ✅ 确认存在且与需求一致 |
| 2 | `parse_ini_metadata()`, `load_parameters()`, `load_csv_with_meta()`, `load_experiment()` 4 个公开函数 | ✅ 确认存在 |
| 3 | 41 个 pytest 测试全部通过 | ✅ 实测确认（0.22s, 41 passed） |
| 4 | `IniMeta.parameters` 存储原始字符串，`Experiment.settings` 类型化 | ✅ 确认逻辑正确 |
| 5 | `readout_amp(dBm)` 被设为必需字段 | ✅ 确认与 `_REQUIRED_KEYS` 一致 |
| 6 | verified_qubits 检查三个来源 | ✅ 确认，但 ancilla 路径未测试 |
| 7 | 三个真实实验数据端到端验证 | ⚠️ 见上节 P2 |
| 8 | Spectro 2D 拟合需重建网格 | ✅ 确认，属于拟合模块职责 |

---

## 四、与后续阶段的接口契约确认

IO 模块暴露给拟合模块的接口如下。拟合模块实现者应据此对齐：

### 4.1 `Experiment` 对象中拟合模块会用到的字段

```python
exp.independent_vars   # list[ColumnMeta] — 通过 .label / .units / .category 匹配列
exp.dependent_vars     # list[ColumnMeta] — 同上
exp.data               # np.ndarray, shape=(n_rows, n_cols)
                       #   前 n_independent 列 = 自变量
                       #   后 n_dependent 列 = 因变量
exp.params             # ParamsSnapshot | None — 比特参数（频率等）
exp.params.qubits[name].f01       # 比特频率 (GHz)
exp.params.qubits[name].verified  # 本次实验是否确认该比特
exp.settings           # dict[str, Any] — INI 参数的类型化值
exp.exp_id             # str — 实验编号
exp.title              # str — 实验标题（用于推断实验类型，§7.4）
```

### 4.2 列匹配关键信息

- T1 实验：因变量 `category` 如 `"Q16 P1"`, `"Q16 P0"` — `fit_t1()` 应匹配 `"P1"`（排除 `"for |0>"` 校准列）
- Spectro IQ 实验：因变量 `category` 如 `"Q07 IQ Amp"`, `"Q07 IQ phase"` — `fit_spectro()` 应匹配 `"IQ Amp"`
- Spectro Prob 实验：因变量 `category` 如 `"Q15 P0"`, `"Q15 P1"` — 匹配 `"P1"`
- 列索引：`exp.data[:, 0]` 到 `exp.data[:, n_independent-1]` 是自变量；其余为因变量

### 4.3 f01 频率获取

拟合函数需要比特频率来标注测量条件（§3.4.1 要求 T1 等参数标注 `freq_GHz`）：

```python
if exp.params and name in exp.params.qubits:
    freq = exp.params.qubits[name].f01
else:
    # 无法获取频率，发出警告
```

⚠️ 此处依赖 `QubitParams.verified` 字段（§7.2）。拟合模块应在使用未验证比特参数时发出警告。

### 4.4 未完成项对拟合模块的阻塞

| 阻塞项 | 严重性 | 说明 |
|--------|--------|------|
| P0: JSON 参数丢弃 | 🔴 阻塞 | `pi_drag` 等参数不可用，影响 Rabi 拟合 |
| HDF5/NPZ 缺失 | 🟢 不阻塞 | 拟合模块不依赖此功能 |
| ancilla 测试缺失 | 🟢 不阻塞 | 不影响拟合模块开发 |

---

## 五、Phase 1 进度评估

对照 `CLAUDE.md` 的 Phase 1 定义：

```
阶段 1：数据 IO + 基础拟合（T1/Lorentzian/DecayingSinusoid + 拟合引擎）
```

| 子任务 | 状态 | 占比 |
|--------|------|------|
| `exp_toolkit/io/readers.py` | ✅ 完成（P0 bug 待修） | 30% |
| `exp_toolkit/fitting/models.py` | ❌ 未开始 | 15% |
| `exp_toolkit/fitting/engine.py` | ❌ 未开始 | 15% |
| `exp_toolkit/fitting/guessers.py` | ❌ 未开始 | 15% |
| `exp_toolkit/fitting/experiments/_base.py` | ❌ 未开始 | 10% |
| `exp_toolkit/fitting/experiments/t1.py` | ❌ 未开始 | 5% |
| `exp_toolkit/fitting/experiments/spectro.py` | ❌ 未开始 | 5% |
| `tests/` — 拟合模块测试 | ❌ 未开始 | 5% |
| **Phase 1 总进度** | | **~30%** |

---

## 六、下一阶段行动清单

实现侧 Claude Code 会话应按以下顺序执行：

### 第一步：修复 P0 bug（必须）

- [ ] **修复 `_QUERY_FIELD_MAP` 数据丢弃问题**（见 §二 P0）
  - 将所有 MAP 中的键也放入 `extras`，不再静默丢弃
  - 验证：修复后 `QubitParams.extras` 应包含 `pi_drag`, `gate_zpa` 等字段

### 第二步：文档清理（建议）

- [ ] 澄清 HDF5/NPZ 定位并更新 CLAUDE.md
- [ ] 确认/编写 `tests/manual/` 下的真实数据验证脚本
- [ ] 补充 `-ancilla_ouput` 测试用例

### 第三步：拟合模块实现（Phase 1 剩余部分）

按以下依赖顺序开发：

```
models.py → guessers.py → engine.py → experiments/_base.py
                                            ↓
                                   experiments/t1.py
                                   experiments/spectro.py
```

**关键提醒**：
- 模型必须是纯函数，不调用 lmfit（CLAUDE.md 架构约定 1）
- 每个模型必须附带合成数据测试（CLAUDE.md 协作约定）
- `fit_*()` 内部通过 `_auto_fit()` 做列选择，不硬编码列索引
- 实现前先给出 API 设计草稿供 supervisor 确认
- `experiment_types.yaml` 按 §7.4 约定创建

### 第四步：Phase 2 预备

- State 模块 (`exp_toolkit/state/`) + 芯片拓扑可视化 (`exp_toolkit/visualization/`)
- 需要拟合模块的 `FitResult` 和 `assignment_fidelity()` 作为输入

---

> **审查报告版本**：v1  
> **关联文档**：[[phase-1-notes]] | [[requirements.md]]  
> **下次审查**：拟合模块 `experiments/_base.py` + `t1.py` + `spectro.py` 完成后
