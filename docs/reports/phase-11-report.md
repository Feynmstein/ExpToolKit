# Phase 11 完成报告：Coherence 分组 + DriveEntry Product 清理

> **日期**：2026-06-19  
> **状态**：已完成

---

## 执行摘要

Phase 11 完成了两项数据结构优化：(1) `DriveEntry.product` 从持久化字段改为计算属性，消除数据冗余；(2) T1/T2\*/T2echo 从三个独立列表改为按 `freq_GHz` 分组的 `coherence` 结构，体现物理上的"同一工作点"语义关联。

**测试结果**：264 passed / 264 collected（+14 测试，零回归）。

---

## 变更明细

### 变更 1：DriveEntry.product → @property

- `DriveEntry` 数据类移除 `product: float` 字段
- 新增 `@property product` 计算属性（`1/(pi_amp × pi_width_ns)`）
- `save()`：不再序列化 `product`
- `load()`：忽略旧 JSON 中的 `product` 键
- `add_drive_efficiency()`：不再计算/传入 `product`
- 报告代码 `generator.py`：无需修改（`entry.product` 语义不变，通过 property 透明计算）

### 变更 2：Coherence 按频率分组

**新增数据类**：
- `CoherenceEntry(value, error, source_exp)` — 组内单个参数值
- `CoherenceGroup(freq_GHz, timestamp, T1_us, T2star_us, T2echo_us)` — 频率组

**QubitState 重构**：
- 移除 `T1_us`/`T2star_us`/`T2echo_us` 三个字段
- 新增 `coherence: list[CoherenceGroup]`
- 新增三个 `@property` 向后兼容（展平 coherence 组 → 排序 `list[ParameterEntry]`）

**add_T1/T2star/T2echo 重写**：
- 查找同 `freq_GHz` 的已有 CoherenceGroup → 设置对应字段
- 不存在则创建新组
- 同频重复调用 → 覆盖（不重复）

**save/load 更新**：
- 新的 coherence JSON 格式：`{"freq_GHz": ..., "timestamp": ..., "T1_us": {...}, "T2star_us": {...|null}, "T2echo_us": {...|null}}`
- `list_measured_qubits` 简化：`or qs.T1_us or qs.T2star_us or qs.T2echo_us` → `or qs.coherence`

### 变更 3：报告 coherence 同行显示

- CSS 新增 `.coherence-row` flex 容器
- `_build_overview()`：T1/T2\*/T2echo 三个参数的拓扑图包裹在 `<div class="coherence-row">` 中水平并排

---

## 测试覆盖

| 类别 | 数量 |
|------|------|
| 原有测试（零回归） | 250 |
| 新增 coherence 分组测试 | 12 |
| 新增 coherence-row HTML 测试 | 2 |
| **总计** | **264** |

关键测试场景：
- `add_T1` 创建组 / 同频合并 / 不同频独立 / 同频覆盖
- `add_T2star`/`add_T2echo` 同频合并
- 时间戳更新、向后兼容属性、save/load 往返、`get_latest`、`list_measured_qubits`
- HTML 中 `.coherence-row` div 和 CSS 存在性验证
- 无 coherence 数据时不生成 coherence-row

---

## 数据文件迁移

三个 chip_state JSON 文件已自动迁移：
- `data/chip_state_example.json` — 6 qubits
- `data/chip_state_RICON_new.json` — 16 qubits
- `data/chip_state_RICON_rebonded.json` — 6 qubits

迁移内容：T1_us/T2star_us/T2echo_us 按 `freq_GHz` 合并为 `coherence` 组 + 移除 `product` 键。

---

## 未改动模块

- 拟合模块（`exp_toolkit/fitting/`）
- IO 模块（`exp_toolkit/io/`）
- 可视化模块（`exp_toolkit/visualization/`）
- 文档目录（`docs/*`，除本文档和 TASK.md/CLAUDE.md 的阶段标注）
