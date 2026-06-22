# Phase 9 工作报告 — 数据修正 + 对比度优化 + Chip Yield 并排显示

**报告日期**：2026-06-19  
**执行会话**：2026-06-19（同日完成）  
**总耗时改动**：~80 行核心改动 + ~20 行测试适配  
**最终测试**：250 passed / 250 collected（Phase 1–9 累计，零回归）

---

## 一、需求覆盖

| 需求 | 说明 | 状态 |
|------|------|------|
| R1 | JSON 中 `product` 值从旧公式 `pi_amp×pi_width` 更新为 `1/(pi_amp×pi_width)` | ✅ |
| R2 | 色标拓扑图文字颜色自适应背景亮度，解决低对比度问题 | ✅ |
| R3 | 三个良率参数并排显示在报告开头，独立 Chip Yield 节 | ✅ |
| R4 | 良率参数顺序：Measurable → Readout Cavity → Bias Tunable | ✅ |

---

## 二、交付物清单

### 2.1 R1 — Drive Efficiency 数据修正

**文件**：`data/chip_state_RICON_rebonded.json`、`data/chip_state_example.json`

Phase 8 修改了 `add_drive_efficiency()` 的公式（`product = 1/(pi_amp × pi_width_ns)`），但 JSON 文件中已存的 `product` 值仍是旧公式计算的。本次修正 8 个 entry：

| 文件 | Qubit | pi_amp | pi_width | 旧 product | 新 product |
|------|-------|--------|----------|-----------|-----------|
| RICON | Q07 | 0.441 | 60 | 26.46 | 0.037793 |
| RICON | Q12 | 0.325 | 30 | 9.75 | 0.102564 |
| RICON | Q13 | 0.203 | 30 | 6.09 | 0.164204 |
| RICON | Q14 | 0.299 | 30 | 8.97 | 0.111483 |
| RICON | Q15 | 0.319 | 30 | 9.57 | 0.104493 |
| RICON | Q16 | 0.600 | 700 | 420 | 0.002381 |
| example | Q01 | 0.48 | 52 | 24.96 | 0.040064 |
| example | Q02 | 0.52 | 48 | 24.96 | 0.040064 |

### 2.2 R2 — 色标文字对比度自适应

**文件**：`exp_toolkit/visualization/chip_plot.py`

#### 新增 `_text_color_for_bg()` 静态方法

```python
@staticmethod
def _text_color_for_bg(bg_color: str | tuple[float, ...]) -> str:
    """Return 'black' or 'white' for readable contrast on *bg_color*."""
    if isinstance(bg_color, str):
        bg_color = matplotlib.colors.to_rgba(bg_color)
    r, g, b = bg_color[0], bg_color[1], bg_color[2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b  # ITU-R BT.601
    return "black" if lum > 0.5 else "white"
```

#### 接入点

| 方法 | 行 | 改动 |
|------|-----|------|
| `colormap_param()` | L535 | `text_color = "white"` → `text_color = self._text_color_for_bg(fc)` |
| `colormap_param()` | L541 | `"white" if has_value` → `self._text_color_for_bg(fc) if has_value` |
| `categorical_param()` | L601 | `color="black"` → `color=self._text_color_for_bg(fc)` |

**效果**：

```
viridis 0.0 (深紫 lum=0.12) → WHITE   ██
viridis 0.5 (青绿 lum=0.43) → WHITE   █████████
viridis 0.75 (亮绿 lum=0.62) → BLACK  ████████████    ← 之前白字看不清
viridis 1.0 (亮黄 lum=0.85) → BLACK  █████████████████ ← 之前白字完全不可见
```

### 2.3 R3 — Chip Yield 并排显示

**文件**：`exp_toolkit/report/generator.py`

#### 新增常量

```python
_YIELD_PARAMS = {"measureable", "readout_cavity_response", "bias_tunable"}

_YIELD_ORDER = ["measureable", "readout_cavity_response", "bias_tunable"]

_YIELD_LABELS = {
    "measureable": "Measurable",
    "readout_cavity_response": "Readout Cavity",
    "bias_tunable": "Bias Tunable",
}
```

#### 新增 CSS

```css
.yield-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 20px;
    margin-bottom: 24px;
}
.yield-row figure {
    flex: 0 1 auto;
    min-width: 260px;
    max-width: 380px;
}
```

#### 新增 `_build_yield()` 方法

```python
def _build_yield(self, yield_params: list[str], section_num: int) -> str:
    """Render yield-parameter topology figures side-by-side."""
    figures_html: list[str] = []
    for param in yield_params:
        svg = self._build_single_topology_figure(param)
        if svg is None:
            continue
        label = _YIELD_LABELS.get(param, param)
        figures_html.append(
            f'<figure><figcaption>{label}</figcaption>{svg}</figure>'
        )
    if not figures_html:
        return ""
    figures_block = "\n".join(figures_html)
    return (
        f'<section id="yield">'
        f'<h2>{section_num}. Chip Yield</h2>'
        f'<div class="yield-row">{figures_block}</div>'
        f'</section>'
    )
```

#### 节编号动态化

所有 section builder 方法新增 `section_num` 参数，不再硬编码节号：

| 方法 | 改动 |
|------|------|
| `_build_overview()` | `"1. Chip Topology"` → `f"{section_num}. Chip Topology"` |
| `_build_measured_qubits()` | `"2. Measured Qubits"` → `f"{section_num}. Measured Qubits"` |
| `_build_unmeasured()` | `"3. Unmeasured Qubits"` → `f"{section_num}. Unmeasured Qubits"` |
| `_build_sources()` | `"4. Data Sources"` → `f"{section_num}. Data Sources"` |

#### `generate()` 编排逻辑

```python
# Separate yield params from topology params
yield_params = sorted(
    [p for p in topology_params if p in _YIELD_PARAMS],
    key=lambda p: _YIELD_ORDER.index(p) if p in _YIELD_ORDER else 99,
)
other_params = [p for p in topology_params if p not in _YIELD_PARAMS]

n = 1
if yield_params and "overview" in active:
    sections_html_parts.append(self._build_yield(yield_params, section_num=n))
    n += 1
if "overview" in active and other_params:
    sections_html_parts.append(self._build_overview(other_params, section_num=n))
    n += 1
# ... remaining sections increment n
```

**报告结构**（有良率数据时）：

```
1. Chip Yield          ← 三图并排（Measurable | Readout Cavity | Bias Tunable）
2. Chip Topology       ← 其他参数色标图
3. Measured Qubits (N)
4. Unmeasured Qubits (N)
5. Data Sources
```

无良率数据时编号自动回退（1→1, 2→2, …），保持旧有行为。

### 2.4 R4 — 良率参数排序

通过 `_YIELD_ORDER` 列表控制排序，`generate()` 中使用 `sorted(key=...)` 按预定义顺序排列。三图始终以 **Measurable → Readout Cavity → Bias Tunable** 顺序展示。

---

## 三、架构合规性

| # | 约定 | 合规 |
|---|------|------|
| 1 | 拟合与持久化解耦 | ✅ 本次不涉及拟合模块 |
| 3 | 拟合模块不自动持久化 | ✅ 仅更新 JSON 数据文件的存储值 |
| 4 | 芯片拓扑不硬编码坐标 | ✅ `ChipTopology` 未变 |
| — | 类型标注完整 | ✅ `_text_color_for_bg()` 有完整类型标注 |
| — | 向后兼容 | ✅ 无 yield 数据时节编号回退至旧行为 |
| — | 自适应对比度不影响数据 | ✅ 仅改变显示颜色，原始数据不变 |

---

## 四、测试覆盖

### 4.1 新增 / 修改测试

全部在 `tests/test_phase3.py` 中修改，4 个用例适配新行为：

| 测试 | 改动 |
|------|------|
| `test_generate_topology_params_auto` | `bias_tunable` → `Bias Tunable`（适配 yield label） |
| `test_categorical_param_labels` | 验证 `Bias Tunable` + `id="yield"` section 存在 |
| `test_extras_bool_vs_numeric_dispatch` | `bias_tunable` → `Bias Tunable` |
| `test_no_chip_topology_prefix` | `1. Chip Topology` → `2. Chip Topology`（yield 占用节 1） |

### 4.2 回归验证

- 全部 250 用例通过（Phase 1–9 累计），零回归
- 无新警告（仅预存的 figure.max_open_warning）

---

## 五、边界情况与设计取舍

### 5.1 已处理的边界

| 场景 | 处理 |
|------|------|
| 无 yield 参数 | 节编号回退：1.Topology → 2.Qubits → 3.Unmeasured → 4.Sources |
| yield 参数部分缺失 | 仅展示存在的参数（如只有 2 个 → 2 图并排） |
| 窄屏幕 | `flex-wrap: wrap` 自动换行为上下排列 |
| `_text_color_for_bg` 接收 hex 字符串 | 通过 `matplotlib.colors.to_rgba()` 统一转换为 RGBA tuple |
| colormap 亮端（黄/绿 lum>0.5） | 黑字 |
| colormap 暗端（紫/蓝 lum<0.5） | 白字 |
| 无值比特 `#D9D9D9` 灰底 | lum=0.85 → 黑字 |

### 5.2 设计决策

1. **对比度阈值 0.5** — ITU-R BT.601 感知亮度公式，0.5 是业界标准分界点，对 viridis / plasma / magma 等常见色标均适用
2. **yield 独立节而非子节** — 良率是芯片评估的一级指标，独立成节能让读者在第一眼看到芯片健康状态，而非埋在 Topology 的多图之中
3. **节编号动态化** — 用计数器 `n` 递推而非硬编码，确保未来增减节时无需逐个修改编号
4. **yield params 从 topology_params 中自动分离** — 用户无需手动区分，`_YIELD_PARAMS` 集合自动判定；显式传入 `topology_params` 时也会正确分离

---

## 六、端到端验证

使用 `data/chip_state_RICON_rebonded.json` 验证：

```
Yield params:    ['measureable', 'readout_cavity_response', 'bias_tunable']
Yield captions:  Measurable → Readout Cavity → Bias Tunable ✅
Section order:   1.Yield → 2.Topology → 3.Qubits(6) → 4.Unmeasured(19) → 5.Sources ✅
Product values:  6/6 match 1/(pi_amp×pi_width) ✅
Contrast:        light bg→black text, dark bg→white text ✅
Tests:           250/250 passed ✅
```

---

> **报告版本**：v1  
> **关联文档**：[`phase-8-design.md`](../designs/phase-8-design.md) | [`requirements.md`](../requirements.md)
