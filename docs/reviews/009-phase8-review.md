# 审查报告 #009 — Phase 8 完成审查（Drive Efficiency 修正 + 列宽修复 + 表头 + 对齐）

**审查日期**：2026-06-18
**审查范围**：R1–R4（公式修正、归一化、多值拆行、表头、Data Sources 居中）
**审查基准**：`docs/phase-8-design.md` + `docs/requirements.md` + `CLAUDE.md`
**上一审查**：[#008](008-phase6-review.md)（Phase 6 完成审查）
**审查人角色**：Supervisor（不主动写实现代码）

---

## 一、总体判定

| 维度 | 评级 | 说明 |
|------|------|------|
| 设计一致性 | 🟢 完全吻合 | 5 个子需求全部按设计文档实现，零偏离 |
| 测试覆盖 | 🟢 优秀 | 250/250 passed (7.84s)，+9 新 Phase 8 用例，零回归（含 3 处回归修复） |
| 架构合规 | 🟢 合规 | 归一化仅在报告层，不修改 state；拆行保持数据完整性 |
| 代码质量 | 🟢 优秀 | `_make_sub_row()` / `_normalize_values()` 职责单一，类型标注完整 |
| 边界处理 | 🟢 完善 | 空 dict 归一化、除零保护、子行空 td 占位、回归测试修复 |

**结论：Phase 8 可以验收。无 P1/P2/P3 问题。连续第 2 次零问题审查。**

---

## 二、逐需求核验

### 2.1 R1a — DriveEntry.product 公式修正 ✅

| 项目 | 设计 | 实现 | 判定 |
|------|------|------|------|
| `DriveEntry` docstring (line 58) | `1/(π 脉冲面积)` | `1/(π 脉冲面积) = 1/(pi_amp × pi_width_ns)` | ✅ |
| `product` docstring (line 67) | `1.0 / (pi_amp * pi_width_ns)` | 一致 | ✅ |
| `add_drive_efficiency()` docstring (line 467) | 更新公式 | `product = 1.0 / (pi_amp * pi_width_ns)` | ✅ |
| 实际计算 (line 472) | `1.0 / (pi_amp * pi_width_ns)` | `product=1.0 / (pi_amp * pi_width_ns)` | ✅ |

**物理验证**：`pi_amp=0.5, pi_width=40ns` → `1/(0.5×40) = 1/20 = 0.05` ✅

### 2.2 R1b — Drive Efficiency 色标归一化 ✅

| 项目 | 设计 | 实现 | 判定 |
|------|------|------|------|
| `_normalize_values()` 位置 | generator.py 模块级函数 | lines 264–271 | ✅ |
| 逻辑：除以 max | 设计指定 | `{k: v / max_val for k, v in values.items()}` | ✅ |
| 空 dict 保护 | 返回 `{}` | `if not values: return {}` | ✅ |
| 除零保护 | 返回原值 | `if max_val == 0.0: return values` | ✅ |
| 接入点 | `_build_single_topology_figure()` 内 `param == "drive_efficiency"` 时归一化 | lines 748–749 | ✅ |
| Card 保留原始值 | 不归一化 | card 显示 `{entry.product:.3f}` 原始物理值 | ✅ |

### 2.3 R2 — 多值参数拆分为多行 ✅

| 项目 | 设计 | 实现 | 判定 |
|------|------|------|------|
| `_make_sub_row()` 辅助函数 | `label, value_str → <tr><th class="sub">...</tr>` | lines 385–392 | ✅ |
| Drive Eff 拆为 3 行 | 主行 + π-amp + π-width | lines 449–457 | ✅ |
| Readout 拆为 3 行 | 主行(avg) + F0 + F1 | lines 461–469 | ✅ |
| CSS `th.sub` | `padding-left: 16px; font-weight: 400; color: muted; font-size: 0.9em` | lines 131–136 | ✅ |
| 子行空 td 占位 | `<td></td><td></td>` 保持 4 列对齐 | `_make_sub_row()` return | ✅ |

**效果验证**：
- 拆行前 Drive Eff value 列最宽 ~220px → 拆行后每行 ≤ 60px ✅
- 拆行前 Readout value 列最宽 ~250px → 拆行后每行 ≤ 60px ✅

### 2.4 R3 — Qubit Card 表头 ✅

| 项目 | 设计 | 实现 | 判定 |
|------|------|------|------|
| `<thead>` 列标题 | Parameter / Value / Frequency / Source | lines 222–231 | ✅ |
| CSS `thead th` | 加粗、#333、2px 底边、uppercase、letter-spacing | lines 126–129 | ✅ |

### 2.5 R4 — Data Sources 前两列居中 ✅

| 项目 | 设计 | 实现 | 判定 |
|------|------|------|------|
| `src-col` class | `<td class="src-col">` | line 538 | ✅ |
| `qubits-col` class | `<td class="qubits-col">` | line 538 | ✅ |
| CSS `src-col` | `text-align: center` | line 167 | ✅ |
| CSS `qubits-col` | `text-align: center` | line 168 | ✅ |

---

## 三、架构约定合规性

| # | 约定 | 判定 | 证据 |
|---|------|------|------|
| 1 | 拟合与持久化解耦 | ✅ | 本次不改动拟合模块 |
| 2 | 拟合模块不自动持久化 | ✅ | `_normalize_values()` 仅在报告层，不写回 state |
| 3 | ChipArtist 与 ReportGenerator 解耦 | ✅ | 归一化在 generator 层执行，不侵入 ChipArtist |
| 4 | 拓扑不硬编码坐标 | ✅ | 未变 |
| — | 类型标注完整 | ✅ | `_normalize_values() -> dict[str, float]`，`_make_sub_row() -> str` |
| — | 归一化不修改原始数据 | ✅ | `product` 保留物理量，colormap 独立副本 |

---

## 四、设计偏差分析

| 项目 | 设计文档 | 实现 | 评价 |
|------|---------|------|------|
| Drive Eff main value 精度 | 设计 `.1f` | 实现 `.3f` | 🟢 改进（公式修正后值很小，需要更高精度） |
| Readout main value | 设计 `Avg=0.9350` | 实现 `0.9350`（省略 "Avg="） | 🟢 合理（表头和标签已说明是 Avg，无需重复） |
| 空 dict 归一化 | 设计提及但无具体代码 | 实现显式返回 `{}` | 🟢 防御性编程 |
| 除零保护 | 设计未提及 | 实现 `if max_val == 0.0: return values` | 🟢 防御性编程 |
| 3 处回归修复 | 设计未提及 | test_phase2.py ×2 + test_phase3.py ×1 product 期望值更新 | 🟢 必要跟进 |

**零设计偏离。5 处实现增强/防御，均在合理范围内。**

---

## 五、测试质量评估

### 5.1 新增测试覆盖

| 测试类 | 用例 | 评级 | 覆盖 |
|--------|------|------|------|
| `TestDriveEfficiencyFix` | 4 | 🟢 | 公式、归一化、空值、card 原始值 |
| `TestMultiValueSplitRows` | 3 | 🟢 | Drive Eff 拆行、Readout 拆行、sub class |
| `TestQubitCardThead` | 1 | 🟢 | thead HTML + CSS |
| `TestSourcesCenterAlignment` | 1 | 🟢 | CSS class + HTML class |

### 5.2 回归修复

| 测试 | 文件 | 修改 |
|------|------|------|
| `test_save_load_roundtrip` | test_phase2.py | product 期望值适配新公式 |
| `test_drive_entry_product` | test_phase2.py | product 期望值适配新公式 |
| `test_colormap_values_drive_efficiency` | test_phase3.py | product 期望值适配新公式 |

### 5.3 累计测试

```
250 passed in 7.84s
  ├── tests/test_io.py ........... 44
  ├── tests/test_fitting.py ...... 36
  ├── tests/test_phase2.py ....... 57
  ├── tests/test_phase3.py ....... 75 (+9 Phase 8)
  └── tests/test_phase4.py ....... 38
```

---

## 六、Breaking Changes 审查

| 改动 | 设计预期 | 实际 | 判定 |
|------|---------|------|------|
| `DriveEntry.product` 公式 | 已有 JSON 需更新 | 3 处测试期望值已同步修复，用户需手动更新 JSON | ✅ 符合设计，文档已说明 |
| 多值参数拆行 | card 行数增加 | 每卡 +2–4 行，视觉改善 | ✅ 符合设计 |
| card 新增 `<thead>` | 行数 +1 | 已实施 | ✅ 符合设计 |

---

## 七、跨 Phase 遗留问题追踪

| 编号 | 来源 | 问题 | 状态 |
|------|------|------|------|
| #007 P3-1 | Phase 5 | docstring 残留"圆圈"术语 | ⚪ 远期 |
| #002 P2-4 | Phase 1 | `fit_spectro()` 双重 `_select_columns` | ⚪ 远期 |
| #002 P2-5 | Phase 1 | `guess_decaying_sinusoid` phase=0.0 | ⚪ 远期 |

**Phase 8 零新遗留问题。**

---

## 八、验收结论

**Phase 8 全部 5 个子需求按设计文档正确实现。** 250 测试通过（+9 新增 + 3 回归修复），零回归。零设计偏离，5 处实现增强均在合理范围内。无 P1/P2/P3 阻塞项。

| 需求 | 状态 |
|------|------|
| R1a: DriveEntry.product 公式修正 | ✅ 验收 |
| R1b: Drive Efficiency 色标归一化 | ✅ 验收 |
| R2: 多值参数拆分为多行 | ✅ 验收 |
| R3: qubit card 表头 | ✅ 验收 |
| R4: Data Sources 前两列居中 | ✅ 验收 |

**Phase 8 可以验收。连续第 2 次零问题审查。**

---

> **审查报告版本**：v1
> **关联文档**：[[phase-8-design]](../designs/phase-8-design.md) | [[008-phase6-review]](008-phase6-review.md)
> **项目状态**：Phase 1–8 全部完成，250 tests，9 次审查闭环。
