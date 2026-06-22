# Phase 1 工作报告 — 数据 IO + 基础拟合

**报告日期**：2026-06-18  
**执行会话**：2026-06-17（第一轮 IO 模块）+ 2026-06-18（审查修复 + 拟合模块 + 二次审查修复）  
**总耗时代码量**：~3370 行（核心包 1997 + 测试 1373）  
**最终测试**：80 passed / 80 collected  

---

## 一、交付物清单

### 1.1 IO 模块 (`exp_toolkit/io/`)

| 文件 | 行数 | 内容 |
|------|------|------|
| `__init__.py` | 26 | 公共 API 导出（6 数据类 + 4 函数） |
| `readers.py` | 820 | 全部数据类 + 解析函数 + 5 个内部辅助函数 |

**6 个数据类**：`ColumnMeta`, `QubitParams`, `IQBlobs`, `ParamsSnapshot`, `IniMeta`, `Experiment`

**4 个公共函数**：`load_experiment()`, `parse_ini_metadata()`, `load_parameters()`, `load_csv_with_meta()`

### 1.2 拟合模块 (`exp_toolkit/fitting/`)

| 文件 | 行数 | 内容 |
|------|------|------|
| `__init__.py` | 32 | 公共 API 导出（自动 + 手动两种模式入口） |
| `models.py` | 149 | 4 个物理模型纯函数 |
| `guessers.py` | 219 | 4 个参数猜测器（含 FFT + 包络拟合） |
| `engine.py` | 234 | `FitResult` 数据类 + `fit()` 通用入口 |
| `experiments/__init__.py` | 6 | 子包标识 |
| `experiments/_base.py` | 234 | `_auto_fit()` + `_select_columns()` + `_find_column()` |
| `experiments/t1.py` | 62 | `fit_t1()` |
| `experiments/spectro.py` | 279 | `fit_spectro()` + `fit_f01_dispersion()` + `F01Dispersion` |
| `experiments/experiment_types.yaml` | 27 | 5 种实验类型映射 |

### 1.3 测试

| 文件 | 行数 | 用例数 |
|------|------|--------|
| `tests/test_io.py` | 714 | 44 |
| `tests/test_fitting.py` | 515 | 36 |
| `tests/manual/verify_real_data.py` | 144 | 手动（3 实验） |

### 1.4 文档

| 文件 | 说明 |
|------|------|
| `docs/phase-1-notes.md` | Phase 1 实现记录（含 IO + 拟合 + 审查修复） |
| `docs/reviews/001-phase1-io-review.md` | 第一次审查报告（仅 IO，5 项问题） |
| `docs/reviews/002-phase1-complete-review.md` | 第二次审查报告（IO + 拟合，3 P1 + 5 P2） |
| `CLAUDE.md` | 阶段 1 标记为完成；HDF5/NPZ 定位澄清 |

---

## 二、审查与修复历程

### 审查 #001（2026-06-17）— IO 模块

| 严重性 | 数量 | 修复状态 |
|--------|------|---------|
| 🔴 P0 | 1 | ✅ `_QUERY_FIELD_MAP` 数据丢弃 → `_EXTRACTED_KEYS` frozenset |
| 🟡 P1 | 2 | ✅ HDF5/NPZ 澄清、ancilla 测试覆盖 |
| 🟢 P2 | 2 | ✅ complex 科学记数法防御、manual 脚本 |

### 审查 #002（2026-06-18）— Phase 1 完整

| 严重性 | 数量 | 修复状态 |
|--------|------|---------|
| 🔴/🟡 P1 | 3 | ✅ fit_spectro 2D 自动 zpa、校准列排除、_FIELD_MAP 清理 |
| 🟢 P2 | 5 | 3 项择机处理（P2-1/P2-2/P2-3/P2-5）；P2-4 已随 P1-1 修复 |

> **剩余 P2 项**：4 项 — 模型命名统一、f01 dispersion 负幅度边界、experiment_types.yaml 调度接入、decaying_sinusoid phase 改进。均不阻塞 Phase 2。

---

## 三、架构合规性

对照 CLAUDE.md 5 条架构约定：

| # | 约定 | 合规 |
|---|------|------|
| 1 | 模型纯函数不调用 lmfit | ✅ `models.py` 4 函数均为纯 numpy |
| 2 | 按实验类型独立 `fit_*()`，禁止字符串分发 | ✅ `fit_t1()`/`fit_spectro()`/`fit_f01_dispersion()` 已实现 |
| 3 | FitResult 不自动持久化 | ✅ 纯 dataclass，无 `save()` 方法 |
| 4 | 芯片拓扑不硬编码 | — Phase 2 关注 |
| 5 | 参数标注测量频率 | ⚠️ 由用户从 `exp.params.qubits[name].f01` 提取后传入 State 模块 |

---

## 四、真实数据验证

三个真实实验全部通过端到端验证：

| 实验编号 | 类型 | 数据量 | 拟合结果 |
|---------|------|--------|---------|
| 00747 | T1 (Q16) | 21×9 | tau=20.1±1.4 μs, R²=0.985 |
| 00023 | Spectro IQ (Q07) | 7371×6 | f01 dispersion [4.21, 4.55] GHz, 21 zpa slices |
| 00732 | Spectro Prob (Q15) | 16441×6 | 格式兼容性确认 |

---

## 五、Phase 2 就绪声明

Phase 2（State 模块 + 芯片拓扑可视化）的接口契约已确认：

**从 IO 模块获取**：
- `exp.params.qubits[name].f01` — 比特频率
- `exp.params.qubits[name].verified` — 实验确认标记
- `exp.params.readout_iq[key]` — IQ 分类器

**从拟合模块获取**：
- `FitResult.params["tau"]` / `.errors["tau"]` — T1 值 + 误差
- `F01Dispersion.f01_min` / `.f01_max` — f01 范围
- `F01Dispersion.zpa_values` / `.f01_values` — 色散曲线数据

**Phase 2 需注意的约定**：
1. `freq_GHz` 标注由用户负责（从 `exp.params` 提取后传入 `state.add_T1()`）
2. `verified` 标记已由 IO 模块自动设置
3. `add_T1()` 等应 append 到列表（保留全部历史）
4. `FitResult` 不持久化 — 用户决定哪些结果写入 ChipState
