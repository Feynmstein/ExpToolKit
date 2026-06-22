# Phase 8 修改计划 — Drive Efficiency 修正 + 列宽修复 + 表头 + 对齐

**文档日期**：2026-06-18
**角色**：Supervisor（设计文档，供实现侧 Claude Code 执行）
**设计基准**：Phase 6+7 完成后的代码

---

## 一、需求

| 需求 | 说明 | 影响文件 |
|------|------|---------|
| R1 | Drive Efficiency: (a) 公式修正为 1/(pi_amp×pi_width); (b) 归一化 | chip_state.py, generator.py |
| R2 | qubit card 4 列正确显示（sources 列被挤出卡片） | generator.py (CSS) |
| R3 | qubit card 增加表头行（Parameter / Value / Frequency / Source） | generator.py |
| R4 | Data Sources 表：Source Exp 和 Qubits 列数据居中 | generator.py (CSS + HTML) |

---

## 二、R1 — Drive Efficiency 公式修正 + 归一化

### 2.1 问题诊断

**R1a — 公式错误**：
当前 `DriveEntry.product = pi_amp * pi_width_ns`（`chip_state.py:472`）。
物理上驱动效率 ∝ 1/(π 脉冲面积)，正确的量应为 `1.0 / (pi_amp * pi_width_ns)`。

波及范围：
| 位置 | 当前 | 需改 |
|------|------|------|
| `chip_state.py:57-79` DriveEntry docstring | "pi_amp × pi_width 的乘积" | 更新为 1/(pi_amp × pi_width) |
| `chip_state.py:472` add_drive_efficiency() | `product=pi_amp*pi_width_ns` | `product=1.0/(pi_amp*pi_width_ns)` |
| `generator.py:283` _get_annotate_values() | 读 `product` | 自动跟随新值 |
| `generator.py:316` _get_colormap_values() | 读 `product` | 自动跟随新值 |
| `generator.py:417` qubit card | 显示 `product` | 自动跟随新值 |

**R1b — 归一化**：
驱动效率原始值（1/面积）量纲为 1/(任意单位·ns)，不同 chip 之间不可直接比较。需要归一化到 [0, 1] 区间，使 colormap 有统一尺度。

归一化策略：除以所有已测 qubit 的最大值（best qubit = 1.0）。归一化仅在报告生成层执行，不修改 `DriveEntry.product` 原始值。

### 2.2 设计

#### 2a. DriveEntry.product 公式修改

```python
# chip_state.py:472 — 改前
product=pi_amp * pi_width_ns,

# 改后
product=1.0 / (pi_amp * pi_width_ns),
```

同步更新 DriveEntry 的 docstring（line 58, 66–67）。

#### 2b. 归一化辅助函数（generator.py 新增）

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

#### 2c. 归一化接入点

在 `_build_single_topology_figure()` 中对 `drive_efficiency` 参数调用归一化：

```python
# 数值参数 → 色标
values_for_colormap = values
if param == "drive_efficiency":
    values_for_colormap = _normalize_values(values)
sm = artist.colormap_param(param, values_for_colormap, ...)
```

qubit card 中的显示值保持原始物理量（`1/(pi_amp×pi_width)`），不归一化——用户需要看到真实物理值。归一化仅用于拓扑色标。

---

## 三、R2 — Qubit Card 多值参数拆分为多行

### 3.1 问题诊断

Phase 7 已将 `.qubit-grid` 改为 `minmax(380px, 1fr)` 并加了 `overflow-x: auto`，但 sources 列仍被挤出。根因是以下两个参数将多个子值拼在一行，导致 value 列过宽：

| 参数 | 当前格式 | 预估宽度 |
|------|---------|---------|
| Drive Eff | `10.0 (π-amp=0.500, π-w=20.0 ns)` | ~220px |
| Readout | `F0=0.9500, F1=0.9200, Avg=0.9350` | ~250px |

单行 value 最宽 250px，在 380px 卡片中（内容区 ~300px），加上 th + freq + src 列 → 溢出。

### 3.2 设计

将多值参数拆分为独立子行：第一行为主值 + @freq + source，后续子行为子参数名 + 子值（freq 和 source 列留空）。

**Drive Efficiency 拆分**：

```html
<!-- 改前（单行） -->
<tr><th>Drive Eff</th><td class="value">10.0 (π-amp=0.500, π-w=20.0 ns)</td><td>@ 5.120 GHz</td><td class="src">(00060)</td></tr>

<!-- 改后（3 行） -->
<tr><th>Drive Eff</th><td class="value">10.0</td><td>@ 5.120 GHz</td><td class="src">(00060)</td></tr>
<tr><th class="sub">π-amp</th><td class="value">0.500</td><td></td><td></td></tr>
<tr><th class="sub">π-width</th><td class="value">20.0 ns</td><td></td><td></td></tr>
```

**Readout Fidelity 拆分**：

```html
<!-- 改前（单行） -->
<tr><th>Readout</th><td class="value">F0=0.9500, F1=0.9200, Avg=0.9350</td><td>@ 7.000 GHz</td><td class="src">(00060)</td></tr>

<!-- 改后（3 行） -->
<tr><th>Readout</th><td class="value">0.9350</td><td>@ 7.000 GHz</td><td class="src">(00060)</td></tr>
<tr><th class="sub">F0</th><td class="value">0.9500</td><td></td><td></td></tr>
<tr><th class="sub">F1</th><td class="value">0.9200</td><td></td><td></td></tr>
```

**CSS 补充**（子行 label 缩进 + 弱化）：

```css
.qubit-card th.sub {
    padding-left: 16px;
    font-weight: 400;
    color: var(--muted);
    font-size: 0.9em;
}
```

**`_build_qubit_card()` 改动**：

```python
# drive efficiency — 拆分
if qs.drive_efficiency:
    entry = qs.drive_efficiency[-1]
    rows.append(_make_param_row(
        "Drive Eff", f"{entry.product:.3f}",
        entry.freq_GHz, entry.source_exp,
    ))
    rows.append(_make_sub_row("π-amp", f"{entry.pi_amp:.3f}"))
    rows.append(_make_sub_row("π-width", f"{entry.pi_width_ns:.1f} ns"))
else:
    rows.append(_make_missing_row("Drive Eff"))

# readout fidelity — 拆分
if qs.readout_fidelity:
    entry = qs.readout_fidelity[-1]
    rows.append(_make_param_row(
        "Readout", f"{entry.avg:.4f}",
        entry.freq_GHz, entry.source_exp,
    ))
    rows.append(_make_sub_row("F0", f"{entry.F0:.4f}"))
    rows.append(_make_sub_row("F1", f"{entry.F1:.4f}"))
else:
    rows.append(_make_missing_row("Readout"))
```

**新增 `_make_sub_row()` 辅助函数**：

```python
def _make_sub_row(label: str, value_str: str) -> str:
    """Render a sub-parameter row (indented label, empty freq/src columns)."""
    return (
        f'<tr><th class="sub">{label}</th>'
        f'<td class="value">{value_str}</td>'
        f'<td></td><td></td></tr>'
    )
```

**效果**：
- 每行最宽 value ≤ 60px（单个数），4 列轻松容纳
- 子参数独立可读，层次清晰
- `white-space: nowrap` 保留无影响

---

## 四、R3 — Qubit Card 增加表头

### 4.1 问题诊断

当前 qubit card 表格仅有 `<tbody>`，无 `<thead>`。用户无法一眼看出每列的含义（虽然通过内容可推断）。

### 4.2 设计

`_build_qubit_card()` 中的表格改为含 `<thead>`：

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

**CSS 补充**（表头与数据行视觉区分）：

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

---

## 五、R4 — Data Sources 表 Source Exp / Qubits 列居中

### 5.1 问题诊断

当前 Data Sources 表格：
```html
<tr><td>{src}</td><td>{qubits_str}</td>{checkmark_tds}...</tr>
```

CSS：`table.sources td { text-align: left; }` — 所有数据列左对齐。仅 check mark 列（`.check` / `.empty`）居中。

用户要求 Source Exp 和 Qubits 两列数据也居中。

### 5.2 设计

给前两列 `<td>` 添加 CSS class：

```python
# _build_sources_table() 中 — 改前
f'<tr><td>{src}</td><td>{qubits_str}</td>'

# 改后
f'<tr><td class="src-col">{src}</td><td class="qubits-col">{qubits_str}</td>'
```

**CSS 新增**：

```css
table.sources td.src-col { text-align: center; }
table.sources td.qubits-col { text-align: center; }
```

---

## 六、文件清单

| 文件 | 改动需求 | 改动量 |
|------|---------|--------|
| `exp_toolkit/state/chip_state.py` | R1a: DriveEntry.product 公式 + docstring | ~3 行 |
| `exp_toolkit/report/generator.py` | R1b: 归一化函数 + 接入; R2: 拆行 + CSS sub; R3: thead + CSS; R4: class + CSS | ~45 行 |
| `tests/test_phase3.py` | R1–R4 测试 | ~10 用例 |

---

## 七、测试计划

### R1 — Drive Efficiency
| 测试 | 说明 |
|------|------|
| `test_drive_product_formula` | `product = 1/(pi_amp * pi_width)` |
| `test_drive_efficiency_normalized_colormap` | 色标值 ≤ 1.0，最大值 = 1.0 |
| `test_drive_efficiency_raw_in_card` | qubit card 仍显示原始物理值 |

### R2 — 多值参数拆行
| 测试 | 说明 |
|------|------|
| `test_drive_eff_split_rows` | Drive Eff 拆为 3 行：主行 + π-amp 子行 + π-width 子行 |
| `test_readout_split_rows` | Readout 拆为 3 行：主行(avg) + F0 子行 + F1 子行 |
| `test_sub_row_has_sub_class` | 子行 `<th class="sub">`，空 `<td>` 占位 freq/src |

### R3 — 表头
| 测试 | 说明 |
|------|------|
| `test_qubit_card_has_thead` | qubit card HTML 含 `<thead>` 和 "Parameter" / "Value" / "Frequency" / "Source" |

### R4 — Data Sources 对齐
| 测试 | 说明 |
|------|------|
| `test_sources_src_qubits_center` | CSS 含 `td.src-col { text-align: center }` 和 `td.qubits-col { text-align: center }` |

---

## 八、Breaking Changes

| 改动 | 影响 | 迁移 |
|------|------|------|
| `DriveEntry.product` 公式 | 已有 chip_state.json 中的 product 值变为错误含义 | 需重新运行 `add_drive_efficiency()` 或手动更新 JSON |
| 多值参数拆行 | qubit card 行数增加（Drive Eff +2 行，Readout +2 行） | 视觉改善，card 高度略增 |

---

## 九、实施顺序

```
Phase A: R1a (product 公式)     ── chip_state.py
Phase B: R1b+R2+R3+R4           ── generator.py (可并行)
```

---

## 十、验证

```bash
python -m pytest tests/test_phase3.py tests/ -v --tb=short
# 预期：236 + ~10 新增 ≈ 246 passed
```
