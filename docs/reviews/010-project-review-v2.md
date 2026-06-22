# 审查报告 #010 — ExpToolKit 项目全面审查 v2

**审查日期**：2026-06-19
**审查范围**：全项目（Phase 1–8，22 源文件 + 5 测试文件）
**审查基准**：`docs/requirements.md` v3 + `CLAUDE.md` + 审查报告 #001–#009
**上次全面审查**：[#006](006-project-review.md)（2026-06-18，Phase 1–4）
**审查人角色**：Supervisor

---

## 一、执行摘要

ExpToolKit Phase 1–8 全部高质量完成。相较于 #006 时的 Phase 1–4，Phase 5–8 新增 53 个测试（250 总量）、零回归、连续两次零问题审查（#008, #009）。

| 指标 | #006 时 (Phase 1–4) | 当前 (Phase 1–8) | 变化 |
|------|---------------------|------------------|------|
| 测试数量 | 197 | **250** | +53 (+27%) |
| 执行时间 | 3.75s | 7.16s | 合理增长 |
| 源代码文件 | 16 | 22 | +6 |
| TODO/FIXME/HACK | 0 | 0 | — |
| 审查报告累计 | 6 | 10 | +4 |

**本次发现 3 个 P2 问题**（均为 `requirements.md` 文档过时），2 个 P3 远期项。**零 P1 阻塞项。零代码回归。**

---

## 二、架构约定合规性（对照 CLAUDE.md）

| # | 约定 | 判定 | 证据 |
|---|------|------|------|
| 1 | 模型纯函数 `(x, **params) -> np.ndarray` | ✅ | 6 个模型零 lmfit 调用 |
| 2 | 按实验类型独立 `fit_*()` | ✅ | 6 个实验函数 + YAML 调度 |
| 3 | 拟合与持久化解耦 | ✅ | `_normalize_values()` 仅在报告层 |
| 4 | 拓扑不硬编码坐标 | ✅ | `ChipTopology(layout=dict)` |
| 5 | 参数标注测量频率 | ✅ | `ParameterEntry.freq_GHz`；f01 存 min/max |
| 6 | matplotlib OO API | ✅ | 全代码库 `fig, ax = plt.subplots()` |
| 7 | 公开 API 完整类型标注 | ✅ | 全部函数签名含类型 |
| 8 | 每模型至少一个合成数据测试 | ✅ | 参数恢复验证 ≤ 3σ |

**8/8 全部合规。零违规。**

---

## 三、需求覆盖矩阵（对照 requirements.md v3）

| § | 内容 | 状态 | 证据 |
|---|------|------|------|
| §3.1 | IO 模块（4 公共 API + 5 数据类） | ✅ | `readers.py`，44 tests |
| §3.2.1 | 子模块结构 | ✅ | 6 个实验类型独立文件 |
| §3.2.2 | 两种使用模式 | ✅ | `fit_t1()` 自动 + `fit()` 手动 |
| §3.2.3 | `_auto_fit()` 分发 | ✅ | 列选择 → 模型绑定 → fit() |
| §3.2.4 | 实验型拟合函数 | ✅ | 6 个函数全部实现 |
| §3.2.5 | 物理模型 | ✅ | 6 个纯函数模型 |
| §3.2.6 | 参数猜测器 | ✅ | 5 个 guesser |
| §3.2.7 | FitResult | ✅ | 10 字段 dataclass |
| §3.2.8 | 读取保真度 | ✅ | 2/3 态，9 tests |
| §3.3.1 | 芯片拓扑图 | ✅ | 3 模式 + categorical_param |
| §3.3.2 | 拟合结果图 | ✅ | `plot_fit_result()` |
| §3.3.3 | 2D 光谱图 | ✅ | `plot_spectroscopy_2d()` |
| §3.4 | State 模块 | ✅ | ChipState + 6 add_*() |
| §3.5 | 报告模块 | ✅ | ReportGenerator + 4 section |
| §7.1 | 错误处理 | ✅ | 英文异常 + Warning 分层 |
| §7.2 | JSON 验证标记 | ✅ | `QubitParams.verified` |
| §7.3 | 测试策略 | ✅ | 合成数据 + tmp_path |
| §7.4 | 实验类型映射 | ✅ | YAML → infer → get_fit_function |

**18/18 需求项全部完成。零遗漏。**

---

## 四、逐模块代码审查

### 4.1 主包入口 (`__init__.py`, 7 行)

🟢 **优秀**。仅暴露 `__version__`，干净。

---

### 4.2 IO 模块 (`readers.py`, 820 行)

🟢 **优秀**。

**亮点**：
- `_parse_complex()` 手动实现复数解析（从右侧扫描 +/-），**显式拒绝科学记数法**（已知限制已文档化）
- `_find_matching_files()` 支持从 CSV 或 INI 任一入口查找三元组
- `_extract_verified_qubits()` 从 3 个 INI 参数源聚合（`-qidxs` / `-ancilla_ouput` / `measure`），双格式覆盖（`Q07` + `Q7`）
- `_EXTRACTED_KEYS` frozenset 确保未知 JSON 字段保留在 `extras` 中
- JSON 缺失时仅 Warning，不阻塞加载
- `_find_column` 三级回退匹配（精确 category → 子串 category → label fallback）

**关注点**：
- 单文件 820 行（P3 远期可拆分）

---

### 4.3 拟合模块

#### 4.3.1 模型 (`models.py`, 180 行)

🟢 **优秀**。6 个纯函数，LaTeX 公式在 docstring。Rabi 有意复用 `decaying_sinusoid`。**无问题。**

#### 4.3.2 引擎 (`engine.py`, 235 行)

🟢 **优秀**。输入校验三步（形状 → 空数据 → NaN/Inf ≥3 有效点）；拟合异常返回 `FitResult(success=False)` 而非崩溃；`y_fit` 对无效点填 NaN；`dof` 下限 1 防除零。**无问题。**

#### 4.3.3 猜测器 (`guessers.py`, 273 行)

🟢 **良好**。`guess_decaying_sinusoid` FFT 主频 + 包络拟合；`guess_rb_exp` p 值裁剪到 [0.5, 0.9999]。遗留 #002 P2-5（phase=0.0，远期）。

#### 4.3.4 实验函数

| 文件 | 行数 | 评级 | 要点 |
|------|------|------|------|
| `_base.py` | 367 | 🟢 | `_auto_fit()` 干净；`_find_column` 三级回退 + exclude |
| `t1.py` | 63 | 🟢 | 简洁委托 |
| `spectro.py` | 304 | 🟢 | 2D→1D + f01 dispersion 两步法；负幅度 guard 已修复 |
| `ramsey.py` | 65 | 🟢 | 与 t1 结构一致 |
| `rabi.py` | 80 | 🟢 | `drive_var` 校验 |
| `rb.py` | 66 | 🟢 | `y_pattern="P0"` 专用于 RB |

遗留 #002 P2-4（`fit_spectro` z_slice 分支双重 `_select_columns`，远期）。

---

### 4.4 IQ 分析 (`iq_analysis.py`, 138 行)

🟢 **优秀**。2 态 `½·erfc(d/(2σ√2))` 公式验证正确；3 态 pairwise 平均；输入校验完整。**无问题。**

---

### 4.5 可视化模块

#### 4.5.1 芯片拓扑 (`chip_plot.py`, 716 行)

🟢 **优秀**。

**Phase 5–8 增量**：
- `FancyBboxPatch` 0.7×0.525 圆角矩形（替代 Circle）
- `draw(show_labels=False)` 支持去除重复 ID
- `categorical_param()` 布尔参数着色（True=#ADD8E6 / False=#D9D9D9）
- `_make_box()` 工厂方法统一 patch 创建
- 新旧拓扑格式兼容（`from_dict` 优先新格式，回退旧格式）

**关注点**：
- `categorical_param` 的 `param_name` 参数未使用（docstring 注明"保留未使用"）

#### 4.5.2 拟合绘图 (`fit_plot.py`, 244 行)

🟢 **良好**。参数文本框 4 位置，无效值回退 "lower left"；残差图共享 x 轴；`plot_spectroscopy_2d` grid 重建正确。**无问题。**

---

### 4.6 State 模块 (`chip_state.py`, 588 行)

🟢 **优秀**。

**Phase 8 关键修改**：`DriveEntry.product = 1.0 / (pi_amp * pi_width_ns)` ✅。下游自动跟随。

**关注点**：`_ensure_qubit()` 允许向不在拓扑中的比特添加参数（P3 远期：显式文档化或添加校验）。

---

### 4.7 报告模块 (`generator.py`, 829 行)

🟢 **优秀**。

**Phase 5–8 增量全览**：

| 功能 | 阶段 | 状态 |
|------|------|------|
| 多参数独立拓扑图（`_build_overview` 循环） | Phase 6 | ✅ |
| `topology_params` 自动检测 + 手动指定 | Phase 6 | ✅ |
| `_resolve_topology_param()` bool/numeric 分发 | Phase 6 | ✅ |
| bool/int 类型陷阱防护 | Phase 6 | ✅ |
| `figcaption` 每图标题 | Phase 7 | ✅ |
| `minmax(380px, 1fr)` 列宽 | Phase 7 | ✅ |
| `_normalize_values()` 归一化 | Phase 8 | ✅ |
| `_make_sub_row()` 多值拆行 | Phase 8 | ✅ |
| `<thead>` 表头 | Phase 8 | ✅ |
| `src-col` / `qubits-col` 居中 | Phase 8 | ✅ |

**关键设计决策审查**：
1. **归一化仅在 colormap 层**：product 保持物理量，归一化仅调用在 `_build_single_topology_figure()` 中的 `drive_efficiency` 分支 ✅
2. **子行空 `<td>` 占位**：`<td></td><td></td>` 保持 4 列 grid 对齐 ✅
3. **f01 Frequency 列留空**：f01 是范围非单频，设计合理 ✅
4. **bool/int 陷阱防护**：`isinstance(v, (int, float)) and not isinstance(v, bool)` 在多处正确使用 ✅

---

## 五、测试质量评估

### 5.1 测试分布

| 文件 | 用例 | 覆盖模块 |
|------|------|---------|
| `test_io.py` | 44 | IO 全部 |
| `test_fitting.py` | 36 | engine + models + guessers + t1/spectro |
| `test_phase2.py` | 57 | State + 可视化 + fit_plot |
| `test_phase3.py` | 75 | IQ + Report + Phase 5–8 |
| `test_phase4.py` | 38 | ramsey/rabi/rb + 调度 + f01 dispersion |
| **合计** | **250** | **全覆盖** |

### 5.2 测试结果

```
250 passed in 7.16s
1 warning: matplotlib RuntimeWarning (>20 figures, test-side, benign)
```

**零 flaky，零跳过，零失败。**

---

## 六、发现的问题

### 6.1 P2 — 应修复

| 编号 | 文件 | 行号 | 问题 | 建议 |
|------|------|------|------|------|
| **#010 P2-1** | `docs/requirements.md` | L549 | `chip_state.json` 示例 `"product": 19.8` 为旧公式值（`pi_amp×pi_width=0.66×30=19.8`），与 Phase 8 修正后的 `1/(0.66×30)≈0.0505` 不一致 | 更新为 `"product": 0.0505` |
| **#010 P2-2** | `docs/requirements.md` | L577 | `drive_efficiency：存 pi_amp × pi_width(ns) 的乘积` 描述过时 | 更新为 `drive_efficiency：存 1/(pi_amp × pi_width_ns)` |
| **#010 P2-3** | `docs/requirements.md` | L696 | `generate()` API 草稿使用 `colormap_param: str = "f01"`，当前实现为 `topology_params: list[str] \| None = None` | 更新草稿签名匹配实现 |

### 6.2 P3 — 远期/低优先级

| 编号 | 文件 | 问题 | 建议 |
|------|------|------|------|
| #010 P3-1 | `chip_state.py:385–388` | `_ensure_qubit()` 允许向不在拓扑中的比特添加参数 | 显式文档化或添加成员校验 |
| #010 P3-2 | `chip_plot.py:542–549` | `categorical_param()` 的 `param_name` 参数未使用 | 远期使用或移除 |

### 6.3 跨 Phase 遗留问题追踪

| 编号 | 来源 | 问题 | 状态 |
|------|------|------|------|
| #002 P2-4 | Phase 1 | `fit_spectro()` z_slice 分支双重 `_select_columns` | ⚪ 远期 |
| #002 P2-5 | Phase 1 | `guess_decaying_sinusoid` phase=0.0 | ⚪ 远期 |
| #007 P3-1 | Phase 5 | docstring 残留"圆圈"术语 | ⚪ 远期 |
| **#010 P2-1** | **本次** | **requirements.md product 值过时 (L549)** | **🟡 应修** |
| **#010 P2-2** | **本次** | **requirements.md drive_efficiency 描述过时 (L577)** | **🟡 应修** |
| **#010 P2-3** | **本次** | **requirements.md generate() 签名过时 (L696)** | **🟡 应修** |

---

## 七、代码健康度

```
$ grep -r "TODO\|FIXME\|HACK\|XXX" exp_toolkit/ tests/
→ 0 matches
```

**全代码库零技术债务标记。**

---

## 八、生产就绪度评估

| 维度 | 评级 | 说明 |
|------|------|------|
| API 稳定性 | 🟢 生产就绪 | 8 个 Phase 无 breaking change（product 公式除外，已文档化） |
| 测试覆盖 | 🟢 优秀 | 250 tests，零失败，零 flaky |
| 错误处理 | 🟢 生产就绪 | 英文异常 + Warning 分层；NaN/Inf/空数据全覆盖 |
| 真实数据兼容 | 🟡 谨慎使用 | `_parse_complex` 不支持科学记数法；需更多真实数据验证 |
| 性能 | 🟢 就绪 | 250 tests 7.16s |
| 文档 | 🟡 需刷新 | `requirements.md` 3 处过时（#010 P2-1/2/3） |
| 代码质量 | 🟢 优秀 | 零 TODO，零回归，清晰分层 |

---

## 九、累计审查统计

| 审查报告 | Phase | 发现问题 | 已修复 | 待处理 | 状态 |
|---------|-------|---------|--------|--------|------|
| #001–#005 | Phase 1–4 | 23 | 19 | 4 | 闭环 |
| #006 | 全项目 v1 | — | — | — | 参考 |
| #007 | Phase 5 | 1 (P3) | 0 | 1 | 远期 |
| #008 | Phase 6 | 0 | — | — | 零问题 |
| #009 | Phase 8 | 0 | — | — | 零问题 |
| **#010** | **全项目 v2** | **3 (P2)** | **0** | **3** | **本次** |
| **合计** | — | **27** | **19** | **8** | — |

### 待处理项总览

| 优先级 | 数量 | 项目 |
|--------|------|------|
| P2（应修复） | 3 | #010 P2-1, P2-2, P2-3（均为 requirements.md 文档过时） |
| P3（远期） | 5 | #002 P2-4, #002 P2-5, #007 P3-1, #010 P3-1, #010 P3-2 |

---

> **审查报告版本**：v2
> **关联文档**：[requirements.md](../requirements.md) | [006-project-review](006-project-review.md)
> **项目状态**：Phase 1–8 全部完成。250 tests，10 次审查闭环。代码库零 TODO，零回归。`requirements.md` 需同步刷新 3 处。
