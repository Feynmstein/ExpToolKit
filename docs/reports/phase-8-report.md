# Phase 8 工作报告 — Drive Efficiency 修正 + 列宽修复 + 表头 + 对齐

**报告日期**：2026-06-18  
**执行会话**：2026-06-18（同日完成）  
**设计基准**：[`phase-8-design.md`](../designs/phase-8-design.md)  
**总耗时代码量**：~60 行核心改动 + ~150 行测试  
**最终测试**：250 passed / 250 collected（Phase 1–8 累计，零回归）

---

## 一、需求覆盖

| 需求 | 说明 | 状态 |
|------|------|------|
| R1a | Drive Efficiency 公式修正为 `1/(pi_amp × pi_width)` | ✅ |
| R1b | Drive Efficiency 色标归一化到 [0, 1] | ✅ |
| R2 | qubit card 多值参数（Drive Eff, Readout）拆分为多行 | ✅ |
| R3 | qubit card 增加表头行（Parameter / Value / Frequency / Source） | ✅ |
| R4 | Data Sources 表 Source Exp 和 Qubits 列数据居中 | ✅ |

---

## 二、交付物清单

### 2.1 R1a — `DriveEntry.product` 公式修正

**文件**：`exp_toolkit/state/chip_state.py`

| 位置 | 改动 |
|------|------|
| `DriveEntry` docstring (line 58) | `pi_amp × pi_width 的乘积` → `1/(π 脉冲面积) = 1/(pi_amp × pi_width_ns)` |
| `DriveEntry.product` docstring (line 67) | `pi_amp * pi_width_ns` → `1.0 / (pi_amp * pi_width_ns)` |
| `add_drive_efficiency()` docstring (line 467) | `product = pi_amp * pi_width_ns` → `product = 1.0 / (pi_amp * pi_width_ns)` |
| `add_drive_efficiency()` 公式 (line 472) | `product=pi_amp * pi_width_ns` → `product=1.0 / (pi_amp * pi_width_ns)` |

**物理含义**：驱动效率 ∝ 1/(π 脉冲面积)。`pi_amp=0.5, pi_width=40ns` → `product=1/20=0.05`（改前为 20.0）。

**波及范围**：
- `generator.py:_get_colormap_values()` — 自动跟随新值
- `generator.py:_get_annotate_values()` — 自动跟随新值
- `generator.py:_build_qubit_card()` — 自动跟随新值
- 无需手动修改下游代码

### 2.2 R1b — Drive Efficiency 色标归一化

**文件**：`exp_toolkit/report/generator.py`

#### 新增 `_normalize_values()` 函数

```python
def _normalize_values(values: dict[str, float]) -> dict[str, float]:
    """归一化到 [0, 1]，除以最大值。全零或空 dict 返回原值。"""
    if not values:
        return {}
    max_val = max(values.values())
    if max_val == 0.0:
        return values
    return {k: v / max_val for k, v in values.items()}
```

#### 接入点：`_build_single_topology_figure()`

```python
# 仅在 colormap 层归一化，card 显示保持原始物理值
if param == "drive_efficiency":
    values_for_colormap = _normalize_values(values)
sm = artist.colormap_param(param, values_for_colormap, ...)
```

**设计决策**：
- 归一化仅在拓扑色标层执行 — 不同 chip 间 colormap 有统一 [0, 1] 尺度
- qubit card 显示保持原始物理量 — 用户需要看到真实值（如 `0.050`）
- `DriveEntry.product` 不修改 — 原始物理量是事实来源

### 2.3 R2 — 多值参数拆分为多行

**文件**：`exp_toolkit/report/generator.py`

#### 新增 `_make_sub_row()` 辅助函数

```python
def _make_sub_row(label: str, value_str: str) -> str:
    """Render a sub-parameter row (indented label, empty freq/src columns)."""
    return (
        f'<tr><th class="sub">{label}</th>'
        f'<td class="value">{value_str}</td>'
        f'<td></td><td></td></tr>'
    )
```

#### Drive Efficiency 拆分

```html
<!-- 改前（单行，value 列 ~220px） -->
<tr><th>Drive Eff</th><td class="value">10.0 (π-amp=0.500, π-w=20.0 ns)</td>
    <td>@ 5.120 GHz</td><td class="src">(00060)</td></tr>

<!-- 改后（3 行，每行 value ≤ 60px） -->
<tr><th>Drive Eff</th><td class="value">0.050</td>
    <td>@ 4.500 GHz</td><td class="src">(001)</td></tr>
<tr><th class="sub">π-amp</th><td class="value">0.500</td><td></td><td></td></tr>
<tr><th class="sub">π-width</th><td class="value">40.0 ns</td><td></td><td></td></tr>
```

#### Readout Fidelity 拆分

```html
<!-- 改前（单行，value 列 ~250px） -->
<tr><th>Readout</th><td class="value">F0=0.9500, F1=0.9200, Avg=0.9350</td>
    <td>@ 7.000 GHz</td><td class="src">(00060)</td></tr>

<!-- 改后（3 行） -->
<tr><th>Readout</th><td class="value">0.9350</td>
    <td>@ 7.000 GHz</td><td class="src">(001)</td></tr>
<tr><th class="sub">F0</th><td class="value">0.9500</td><td></td><td></td></tr>
<tr><th class="sub">F1</th><td class="value">0.9200</td><td></td><td></td></tr>
```

#### CSS 新增

```css
.qubit-card th.sub {
    padding-left: 16px;
    font-weight: 400;
    color: var(--muted);
    font-size: 0.9em;
}
```

**效果**：
- 每行 value 列宽 ≤ 60px，4 列在 380px 卡片内容区（~348px）内完全容纳
- 子参数缩进 + 灰色弱化，视觉层次清晰
- `white-space: nowrap` 无副作用

### 2.4 R3 — Qubit Card 表头

**文件**：`exp_toolkit/report/generator.py`

#### `_build_qubit_card()` 改动

```python
# 改前
table = f'<table><tbody>{"".join(rows)}</tbody></table>'

# 改后
header = (
    '<thead><tr>'
    '<th>Parameter</th><th>Value</th><th>Frequency</th><th>Source</th>'
    '</tr></thead>'
)
table = f'<table>{header}<tbody>{"".join(rows)}</tbody></table>'
```

#### CSS 新增

```css
.qubit-card thead th {
    font-weight: 600;
    color: #333;
    border-bottom: 2px solid var(--border);
    font-size: 0.8em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
```

**效果**：每张 qubit card 表格有明确的列标题，大写 + 加粗 + 2px 底边与数据行区分。

### 2.5 R4 — Data Sources 前两列居中

**文件**：`exp_toolkit/report/generator.py`

#### HTML class 添加

```python
# 改前
f'<tr><td>{src}</td><td>{qubits_str}</td>'

# 改后
f'<tr><td class="src-col">{src}</td><td class="qubits-col">{qubits_str}</td>'
```

#### CSS 新增

```css
table.sources td.src-col { text-align: center; }
table.sources td.qubits-col { text-align: center; }
```

**效果**：Source Exp 列（实验编号如 `00101`）和 Qubits 列（如 `Q07, Q12`）居中显示，与 check mark 列（✓ / —）风格一致。

---

## 三、架构合规性

| # | 约定 | 合规 |
|---|------|------|
| 1 | 拟合与持久化解耦 | ✅ 本次改动不涉及拟合模块 |
| 3 | 拟合模块不自动持久化 | ✅ `_normalize_values()` 仅在报告层，不写回 state |
| 4 | 芯片拓扑不硬编码坐标 | ✅ `ChipTopology` 未变 |
| — | 类型标注完整 | ✅ `_normalize_values()` 和 `_make_sub_row()` 有完整类型标注 |
| — | 归一化不修改原始数据 | ✅ product 保留物理量，归一化仅在 colormap 层 |
| — | 拆分保持数据完整性 | ✅ 子参数值精度不变，仅改变 HTML 呈现方式 |

---

## 四、Breaking Changes

| 改动 | 影响范围 | 迁移方案 |
|------|---------|---------|
| `DriveEntry.product` 公式 | 所有已有 `chip_state.json` 中的 product 值 | 需重新调用 `add_drive_efficiency()` 或手动更新 JSON 中的 product 字段 |
| 多值参数拆行 | qubit card 行数增加（每卡 +2–4 行），卡片高度略增 | 视觉改善，无需迁移 |
| card 新增 `<thead>` | 卡片行数 +1，卡片高度略增 | 视觉改善，无需迁移 |

---

## 五、测试覆盖

全部在 `tests/test_phase3.py` 中新增，文件从 Phase 7 的 66 用例扩展至 75 用例（+9 新）。

### 5.1 R1 — `TestDriveEfficiencyFix`（4 用例）

| 测试 | 说明 |
|------|------|
| `test_drive_product_formula` | `product = 1/(pi_amp * pi_width)`，0.5×40 → 0.05 |
| `test_drive_efficiency_normalized_colormap` | 归一化到 [0, 1]，max=1.0，其他按比例 |
| `test_drive_efficiency_normalize_empty` | 空 dict 归一化返回空 dict |
| `test_drive_efficiency_raw_in_card` | qubit card 显示原始物理值（`0.050`），非归一化值 |

### 5.2 R2 — `TestMultiValueSplitRows`（3 用例）

| 测试 | 说明 |
|------|------|
| `test_drive_eff_split_rows` | Drive Eff 拆为 3 行，含 `<th class="sub">π-amp</th>` 和 `π-width` |
| `test_readout_split_rows` | Readout 拆为 3 行，含 `<th class="sub">F0</th>` 和 `F1` |
| `test_sub_row_has_sub_class` | 子行 `class="sub"` + 空 `<td></td><td></td>` 占位 |

### 5.3 R3 — `TestQubitCardThead`（1 用例）

| 测试 | 说明 |
|------|------|
| `test_qubit_card_has_thead` | HTML 含 `<thead>` + Parameter/Value/Frequency/Source + CSS |

### 5.4 R4 — `TestSourcesCenterAlignment`（1 用例）

| 测试 | 说明 |
|------|------|
| `test_sources_src_qubits_center` | CSS 含 `td.src-col` / `td.qubits-col`；HTML 含对应 class |

### 5.5 回归修复（3 处）

| 测试 | 文件 | 修改 |
|------|------|------|
| `test_save_load_roundtrip` | test_phase2.py | product 期望值 `19.8` → `1.0/19.8` |
| `test_drive_entry_product` | test_phase2.py | product 期望值 `20.0` → `0.05` |
| `test_colormap_values_drive_efficiency` | test_phase3.py | product 期望值 `20.0, 21.0` → `1/20, 1/21` |

---

## 六、边界情况与设计取舍

### 6.1 已处理的边界

| 场景 | 处理 |
|------|------|
| `_normalize_values` 空 dict | 返回 `{}` |
| `_normalize_values` 最大值为 0 | 返回原值（避免除零） |
| Drive Eff 缺失但 Readout 存在 | 各独立判断，Drive Eff 显示 "No data"（1 行），Readout 正常拆为 3 行 |
| 子行 colspan 不合并 | 子行 freq 和 src 列为空 `<td></td>`，保持 4 列对齐 |
| 旧 JSON 中 product 为旧公式值 | Breaking change，需手动更新 JSON 或重新运行 `add_drive_efficiency()` |

### 6.2 设计决策

1. **归一化仅在 colormap 层** — `_normalize_values()` 只影响拓扑图色标范围，不影响 `DriveEntry.product` 和 qubit card 显示。原始物理量是事实来源，不可修改
2. **拆分而非缩写** — 对 Drive Eff 和 Readout 选择拆分为独立子行，而非压缩格式（如 `DE=0.050`）。子行方案保持每个数据点的精度，视觉层次清晰
3. **子行用空 `<td>` 占位** — 不用 `colspan`，保持 4 列 grid 对齐。空列在视觉上暗示"此子参数不单独关联频率和实验来源"
4. **thead 使用 uppercase** — 表头 `PARAMETER / VALUE / FREQUENCY / SOURCE` 大写 + letter-spacing，与数据行形成清晰视觉层级，符合科学报告惯例

---

## 七、端到端验证

使用 `data/chip_state_example.json` 验证：

```
Normalized: Q01=0.025→0.5, Q02=0.05→1.0 ✅
thead: True ✅
th class=sub: True ✅
src-col: True ✅
报告大小: 586 KB
```

---

## 八、未来方向（不在本次范围）

| 项目 | 说明 |
|------|------|
| 归一化策略可配置 | 当前固定 "除以最大值"，未来可支持 min-max、z-score 等 |
| 更多参数拆行 | T2* 的 Ramsey 频率分量、f01 dispersion 的 min/max 也可拆行 |
| thead 固定 | 长 card 滚动时 thead 可 sticky 定位 |
| product 迁移脚本 | 为已有 chip_state.json 提供自动迁移工具 |

---

> **报告版本**：v2  
> **关联文档**：[`phase-8-design.md`](../designs/phase-8-design.md) | [`phase-7-design.md`](../designs/phase-7-design.md) | [`requirements.md`](../requirements.md)  
> **下一环节**：Supervisor 审查本报告 + 代码 diff，对照设计文档检查一致性

---

## 九、审查记录

### 9.1 Phase 8 完成审查（2026-06-18）

> **审查报告**：[`docs/reviews/009-phase8-review.md`](../reviews/009-phase8-review.md)  
> **总体判定**：Phase 8 可以验收。零 P1/P2/P3 问题。连续第 2 次零问题审查。  
> **设计一致性**：5/5 子需求完全吻合设计文档，零设计偏离，5 处合理增强。  
> **测试**：250/250 passed（+9 Phase 8），零回归。  
> **架构合规**：全部通过。Phase 1–8 累计 250 tests，9 次审查闭环。
