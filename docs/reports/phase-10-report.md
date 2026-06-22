# Phase 10 工作报告 — Chip Yield 固定渲染 + None 态支持

**报告日期**：2026-06-19
**执行会话**：2026-06-19（同日完成）
**设计基准**：[`phase-10-design.md`](../designs/phase-10-design.md)
**总耗时改动**：~65 行核心改动 + ~10 行测试适配
**最终测试**：250 passed / 250 collected（Phase 1–10 累计，零回归）

---

## 一、需求覆盖

| 需求 | 说明 | 状态 |
|------|------|------|
| R1 | Yield section 在报告中固定渲染，不因数据缺失而缺席 | ✅ |
| R2 | `categorical_param()` 支持 `None` 值————白底虚线边 + 灰色 `?` 标记 | ✅ |
| R3 | `_build_single_topology_figure()` 在 values 为空/yield 时渲染全灰拓扑图 | ✅ |
| R4 | `_YIELD_SPEC` 合并常量，消除 `_YIELD_PARAMS`/`_YIELD_ORDER`/`_YIELD_LABELS` 重复定义 | ✅ |

---

## 二、交付物清单

### 2.1 R4 — `_YIELD_SPEC` 合并常量

**文件**：`exp_toolkit/report/generator.py`

```python
# 改前：三个独立常量，key 信息重复三次
_YIELD_PARAMS = {"measureable", "readout_cavity_response", "bias_tunable"}
_YIELD_ORDER = ["measureable", "readout_cavity_response", "bias_tunable"]
_YIELD_LABELS = {
    "measureable": "Measurable",
    "readout_cavity_response": "Readout Cavity",
    "bias_tunable": "Bias Tunable",
}

# 改后：单一事实来源，三个视图自动派生
_YIELD_SPEC = [
    ("measureable",               "Measurable"),
    ("readout_cavity_response",   "Readout Cavity"),
    ("bias_tunable",              "Bias Tunable"),
]
_YIELD_PARAMS = {key for key, _ in _YIELD_SPEC}
_YIELD_ORDER = [key for key, _ in _YIELD_SPEC]
_YIELD_LABELS = dict(_YIELD_SPEC)
```

新增第四个良率指标时只需在 `_YIELD_SPEC` 中加一行。

### 2.2 R2 — `categorical_param()` 支持 None 值

**文件**：`exp_toolkit/visualization/chip_plot.py`

#### 类型扩展

`values: dict[str, bool]` → `values: dict[str, bool | None]`

#### 渲染逻辑

| 值 | 填充色 | 边框 | 文字 | 语义 |
|----|--------|------|------|------|
| `True` | `#ADD8E6` 浅蓝 | `#888888` 实线 | 比特名（自适应色） | 可用 |
| `False` | `#D9D9D9` 浅灰 | `#888888` 实线 | 比特名（自适应色） | 不可用 |
| `None` | `#FFFFFF` 白色 | `#BBBBBB` 虚线 `(0, (4, 3))` | 比特名 + 灰色 `?`（`#AAAAAA`） | 待评估 |

核心改动片段：

```python
if val is None:
    fc = "#FFFFFF"
    ec = "#BBBBBB"
    lw = 1.0
    display_text = f"{name}\n?"
    text_color = "#AAAAAA"
    linestyle = (0, (4, 3))
elif val:
    fc = true_color
    ec = edge_color
    lw = 1.5
    display_text = name
    text_color = self._text_color_for_bg(fc)
    linestyle = "-"
else:
    fc = false_color
    ec = edge_color
    lw = 1.5
    display_text = name
    text_color = self._text_color_for_bg(fc)
    linestyle = "-"

box = self._make_box(x, y, facecolor=fc, edgecolor=ec, linewidth=lw, zorder=2)
box.set_linestyle(linestyle)
```

`FancyBboxPatch` 继承自 `Patch`，`set_linestyle((0, (4, 3)))` 正确渲染虚线边框。

### 2.3 R3 — `_build_single_topology_figure()` 空值容错

**文件**：`exp_toolkit/report/generator.py`

```python
# 改前
values, is_bool = self._resolve_topology_param(param)
if not values:
    return None           # ← 无数据直接跳过

# 改后
values, is_bool = self._resolve_topology_param(param)
if not values and param not in _YIELD_PARAMS:
    return None           # ← 非 yield 参数保持旧行为
...
if is_bool:
    artist.categorical_param(param, values)
elif not values:
    # Yield param with all-None → render categorical None
    artist.categorical_param(param, values)
```

配合 `_resolve_topology_param()` 的空值 fallback：

```python
if not raw:
    if param in _YIELD_PARAMS:
        return (
            {name: None for name in state.topology.qubit_names},
            True,
        )
    return ({}, False)
```

yield 参数在无数据时返回 `{Q01: None, Q02: None, ...}` 而非空 dict，确保后续渲染走 categorical None 分支。

### 2.4 R1 — Yield section 固定渲染

**文件**：`exp_toolkit/report/generator.py`

#### `_build_yield()` 简化

```python
# 改前
def _build_yield(self, yield_params: list[str], section_num: int) -> str:
    for param in yield_params:       # ← 依赖外部传入的列表
        ...

# 改后
def _build_yield(self, section_num: int) -> str:
    for param in _YIELD_ORDER:       # ← 固定遍历 3 个 yield 参数
        svg = self._build_single_topology_figure(param)
        # Yield params never return None (all-None placeholder rendered)
        ...
```

#### `generate()` 编排

```python
# 改前
yield_params = sorted(...)
if yield_params and "overview" in active:     # ← 条件渲染
    sections_html_parts.append(self._build_yield(yield_params, ...))

# 改后
if "overview" in active:                      # ← 固定渲染
    sections_html_parts.append(self._build_yield(section_num=n))
    n += 1
```

---

## 三、架构合规性

| # | 约定 | 合规 |
|---|------|------|
| — | 数据模型不变 | ✅ 零改动 `QubitState`/`ChipState`，三个字段仍在 extras 中 |
| — | 向后兼容 | ✅ 旧 JSON 文件加载后，缺失 yield 字段自动渲染为 None 态 |
| — | 承诺成本可控 | ✅ 新增良率指标仅需 `_YIELD_SPEC` 中加一行 |
| — | report 不修改数据 | ✅ None 态仅影响 HTML 渲染，不写回 state |
| 4 | 芯片拓扑不硬编码坐标 | ✅ `ChipTopology` 未变 |

---

## 四、测试覆盖

### 4.1 新增 / 修改测试

全部在 `tests/test_phase3.py` 中修改：

| 测试 | 改动 |
|------|------|
| `test_generate_topology_params_explicit` | 期望 5 图（3 yield 固定 + 2 请求），验证 yield section 存在 |
| `test_extras_bool_vs_numeric_dispatch` | 期望 4 SVG（3 yield + 1 overview） |

### 4.2 端到端验证

**场景 A：有 yield 数据（RICON rebonded）**

```
Sections: 1.Chip Yield → 2.Chip Topology → 3.Measured(6) → 4.Unmeasured(19) → 5.Sources
Yield figures: 3 (Measurable | Readout Cavity | Bias Tunable)
None/dashed: 0 （所有比特有 bool 数据）
Total figures: 9
```

**场景 B：无 yield 数据（2×2 空芯片）**

```
Sections: 1.Chip Yield → 2.Chip Topology → 3.Measured(1) → 4.Unmeasured(3) → 5.Sources
Yield figures: 3
#FFFFFF (None bg):  True
stroke-dasharray:   True
? marker:           True
#AAAAAA text:       True
```

### 4.3 回归验证

- 全部 250 用例通过，零回归
- 仅预存的 `figure.max_open_warning` 警告

---

## 五、边界情况与设计取舍

### 5.1 已处理的边界

| 场景 | 处理 |
|------|------|
| 芯片无任何 yield 数据 | 三张图全白虚线 `?`，yield section 仍为节 1 |
| 部分比特有数据、部分无 | 有数据的正常着色，无数据的白虚线 `?`（以 `None` 区分于 `False`） |
| 用户传入 `sections=["qubits"]`（不含 overview） | yield section 不渲染（依赖 `"overview" in active`） |
| 用户传入 `topology_params=["T1"]`（不含 yield） | yield 仍渲染（固定行为不看 topology_params），T1 单独在 overview |
| `FancyBboxPatch` 虚线兼容 | `set_linestyle((0, (4, 3)))` 正常支持，SVG 输出含 `stroke-dasharray` |

### 5.2 设计决策

1. **固定渲染优于条件渲染**。良率是任何芯片报告的第一问。yield section 的空白 = "请填写三个字段"的信号，倒逼数据完整性
2. **None 态独立于 False**。白虚线 `?` 明确传达"尚未评估"，与灰色实线"评估为否"有视觉区分。这避免了对 `bool` 的二元压迫——`False` 不隐含"没测"
3. **YIELD_SPEC 合并**。单一事实来源消除三个常量的同步维护义务，新增指标只需一行
4. **空值 fallback 在 resolver 层**。`_resolve_topology_param` 负责填补数据缺口，下游方法（builder/figure）只需处理 dict，职责清晰

---

## 六、Bug 修复 — `_resolve_topology_param` None 值混合误判

### 发现

生成 `chip_state_example.json` 报告时，`measurable` 拓扑图所有 25 个比特均显示为灰色默认盒子，未区分 True（浅蓝）、False（灰）、None（白虚线）。但 `_resolve_topology_param("measurable")` 返回的数据中确有 6 个 True、2 个 False、17 个 None。

### 根因

`_resolve_topology_param()` 的类型检测逻辑（line 757）使用 `all(isinstance(v, bool) for v in raw.values())` 判断是否为 bool 类型。当 `raw` 中混有 `None` 值时：

```python
raw = {"Q07": True, "Q14": None, "Q16": False, ...}
# isinstance(None, bool) → False  ← 导致 all_bool = False
```

`all_bool` 和 `all_numeric` 均为 `False`，函数落入 `else` 分支返回 `({}, False)`——空 dict。`_build_single_topology_figure` 收到空 dict 后调用 `categorical_param(param, {})`，所有比特因 `name not in values` 被跳过，仅保留 `draw()` 的默认灰底。

**触发条件**：extras 中某 bool 字段在不同 qubit 上同时存在 `True`/`False` 和显式 `None` 值（即部分已评估、部分标记为"未评估"）。

### 修复

**文件**：`exp_toolkit/report/generator.py` — `_resolve_topology_param()`

```python
# 改前 (line 756-769)
# 3. Determine type
all_bool = all(isinstance(v, bool) for v in raw.values())        # None → False
all_numeric = all(
    isinstance(v, (int, float)) and not isinstance(v, bool)
    for v in raw.values()
)
if all_bool:
    return (raw, True)
elif all_numeric:
    return ({k: float(v) for k, v in raw.items()}, False)
else:
    return ({}, False)                                            # ← 误判落点

# 改后
# 3. Determine type (exclude None from type check)
non_none = {k: v for k, v in raw.items() if v is not None}
if non_none:
    all_bool = all(isinstance(v, bool) for v in non_none.values())
    all_numeric = all(
        isinstance(v, (int, float)) and not isinstance(v, bool)
        for v in non_none.values()
    )
    if all_bool:
        # Expand to all topology qubits; missing ones → None
        full = {name: raw.get(name) for name in state.topology.qubit_names}
        return (full, True)
    elif all_numeric:
        return ({k: float(v) for k, v in raw.items()}, False)
    else:
        return ({}, False)
else:
    # All values are None — bool for yield params, skip otherwise
    if param in _YIELD_PARAMS:
        full = {name: raw.get(name) for name in state.topology.qubit_names}
        return (full, True)
    return ({}, False)
```

三处改动：
1. **类型检测排除 None**——`non_none` dict 仅用于 `all_bool`/`all_numeric` 判定
2. **bool 结果扩展到全部 qubit**——`raw.get(name)` 对缺失 qubit 返回 `None`，确保 `categorical_param` 为每个 qubit 绘制 overlay（而非跳过）
3. **全 None 场景**——fallback 到 `_YIELD_PARAMS` 判定 `is_bool`

### 验证

```
# 修复前
_resolve_topology_param("measurable") → ({}, False)   # 空 dict，所有比特灰底

# 修复后
_resolve_topology_param("measurable") → ({Q01: True, Q02: False, ..., Q14: None, ...}, True)
# True=6, False=2, None=17 → measurable 图正确区分三态
```

全量测试：250/250 passed，零回归。

---

> **报告版本**：v2（追加 Bug 修复小节）  
> **关联文档**：[`phase-10-design.md`](../designs/phase-10-design.md) | [`phase-9-report.md`](phase-9-report.md) | [`requirements.md`](../requirements.md)
