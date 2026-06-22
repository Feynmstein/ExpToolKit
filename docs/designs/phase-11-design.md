# Phase 11 设计文档：Coherence 分组 + DriveEntry Product 清理

> **日期**：2026-06-19  
> **状态**：已完成

---

## 一、背景

两个问题被发现并纳入本次改进：

1. **`DriveEntry.product` 冗余存储**：`product = 1/(pi_amp × pi_width_ns)` 是纯派生量，却存储在 JSON 中。Phase 8 公式修正时因此需要数据迁移——这正是派生量持久化的后果。
2. **Coherence 参数无分组**：T1、T2*、T2echo 在物理上是同一比特频率下的测量值，但 `chip_state.json` 中存为三个独立列表，丢失了"同一工作点"的语义关联。

---

## 二、设计决策

### 决策 1：`product` 改为计算属性

**选择**：`product` 从 `DriveEntry` dataclass 字段改为 `@property`，JSON 不再存储。

```python
@property
def product(self) -> float:
    return 1.0 / (self.pi_amp * self.pi_width_ns)
```

**理由**：
- 消除数据冗余，避免 `product` 与 `pi_amp/pi_width_ns` 不一致
- 公式变更时无需数据迁移（Phase 8 的教训）
- 向后兼容：所有 `entry.product` 读取代码无需修改

### 决策 2：Coherence 按频率分组

**选择**：新增 `CoherenceGroup` 数据类，以 `freq_GHz` 为归组键，将 T1/T2*/T2echo 组织在同一频率组下。

**归组键**：仅 `freq_GHz`（用户确认：不同实验同一频率应归入同一组。T1、T2*、T2echo 可能由不同实验测量。）

**API 方案**：方案 B — 保留 `add_T1()`、`add_T2star()`、`add_T2echo()` 三个独立入口，内部自动按 `freq_GHz` 归组。

**数据结构**：

```python
@dataclass
class CoherenceEntry:
    value: float
    error: float | None
    source_exp: str          # 每个参数独立来源

@dataclass
class CoherenceGroup:
    freq_GHz: float          # 归组键
    timestamp: str
    T1_us: CoherenceEntry | None = None
    T2star_us: CoherenceEntry | None = None
    T2echo_us: CoherenceEntry | None = None
```

**向后兼容**：`QubitState` 保留 `T1_us`/`T2star_us`/`T2echo_us` 三个 `@property`，从 `coherence` 展平并按时间戳排序返回 `list[ParameterEntry]`。现有只读代码无需改动。

### 决策 3：报告中 coherence 拓扑图同行显示

**选择**：新增 `.coherence-row` CSS flex 容器，`_build_overview()` 将 T1/T2*/T2echo 三个参数的拓扑图包裹在同一行。

---

## 三、涉及文件

| 文件 | 改动 |
|------|------|
| `exp_toolkit/state/chip_state.py` | 主改动：+2 数据类，DriveEntry 字段→property，QubitState 字段替换 +3 兼容属性，add 方法重写，save/load/__all__ 更新 |
| `exp_toolkit/state/__init__.py` | 导出新类 |
| `exp_toolkit/report/generator.py` | CSS +.coherence-row，_build_overview 同行逻辑 |
| `tests/test_phase2.py` | 修复 1 测试 + 新增 12 测试 |
| `tests/test_phase3.py` | 新增 2 测试 |
| `data/*.json` | 格式迁移 |

---

## 四、测试

- 原有：250 测试全部通过（零回归）
- 新增：14 测试（12 coherence 分组 + 2 coherence-row HTML）
- 总计：264 passed, 0 failed
