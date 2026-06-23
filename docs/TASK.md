# ExpToolKit 当前任务状态

> **最后更新**：2026-06-19（Phase 11 完成后）  
> **角色**：精炼的上下文文档 — 新会话接手时，本文档 + `requirements.md` 是最小阅读集

---

## 当前阶段

- **已完成**：Phase 1–12（全部核心开发）
- **Phase 12**：生产部署与需求演进流程设计 → `docs/deployment-guide.md`
- **下一步**：按 `deployment-guide.md` §4 流程，从实验电脑收取首批需求卡片

---

## 模块完成度

| 模块 | 路径 | 状态 | 关键能力 |
|------|------|------|---------|
| IO | `exp_toolkit/io/` | ✅ | CSV+INI+JSON 三元组读取，6 数据类 + 4 公共函数 |
| Fitting | `exp_toolkit/fitting/` | ✅ | 6 个物理模型 + 6 个 `fit_*()` 函数 + YAML 调度 |
| State | `exp_toolkit/state/` | ✅ | ChipState 累积管理，6 个 `add_*()` 方法 + coherence 按频率分组 |
| Visualization | `exp_toolkit/visualization/` | ✅ | ChipTopology + ChipArtist（含 categorical_param None 态） |
| Report | `exp_toolkit/report/` | ✅ | ReportGenerator → 自包含 HTML，coherence-row 同行显示 |

**测试**：264 passed / 264 collected（零回归，+14 Phase 11）  
**审查**：10 份审查报告（#001–#010），零 P0/P1 阻塞项

---

## 最近关键决策

1. **Coherence 按频率分组**（Phase 11）
   → T1/T2\*/T2echo 从三个独立列表改为 `coherence: list[CoherenceGroup]`，归组键为 `freq_GHz`。新增 `CoherenceEntry`/`CoherenceGroup` 数据类，保留 `add_T1/add_T2star/add_T2echo` 公开 API（独立入口 + 自动归组，方案 B）。
   详见：[`designs/phase-11-design.md`](designs/phase-11-design.md)

2. **DriveEntry.product 改为计算属性**（Phase 11）
   → `product` 不再存入 JSON，改为 `@property`（`1/(pi_amp × pi_width_ns)`）。JSON 仅存储 `pi_amp` 和 `pi_width_ns`。

3. **方案 B：良率指标保持 extras**（Phase 10）

---

## 最近关键决策

1. **方案 B：良率指标保持 extras**（Phase 10）
   → `measurable`/`readout_cavity_response`/`bias_tunable` 不提升为 `QubitState` 一级字段，保持 `extras` 灵活性。待语义完全稳定后再评估。
   详见：[`designs/phase-10-design.md`](designs/phase-10-design.md) §二

2. **Yield section 固定渲染**（Phase 10）
   → 报告中 Chip Yield 节不再条件渲染——即使无数据也展示全灰拓扑图（`None` 态 = 白底虚线 `?`），倒逼数据完整性。
   详见：[`reports/phase-10-report.md`](reports/phase-10-report.md)

3. **拟合与持久化解耦**（Phase 1，贯穿全项目）
   → `FitResult` 是纯内存对象，不自动写入文件。用户通过 `ChipState.add_*()` 手动控制持久化。

4. **多参数独立拓扑图**（Phase 6）
   → 每参数一张独立 SVG 拓扑图（不再用 `annotate()` 集中展示），支持 built-in + extras 混合渲染。

---

## 已知局限

- `ramsey`/`rabi`/`rb` 的 YAML 条目已预置，但无真实数据验证（`fit_ramsey`/`fit_rabi`/`fit_rb` 仅有合成数据测试）
- `chip_state.json` 无版本迁移机制（v1 阶段不做兼容性保证）
- 多比特批量拟合未实现（留待阶段 4+）
- Phase 7 缺少完成报告、Phase 9 缺少设计文档（历史遗留，标注在 `README.md`）

---

## 下次会话 Checklist

- [ ] 读 `docs/requirements.md`（架构级设计）
- [ ] 读本文档（当前状态）
- [ ] 确认 CLAUDE.md "当前阶段" 是否最新
- [ ] 明确本会话的目标 Phase 和范围
