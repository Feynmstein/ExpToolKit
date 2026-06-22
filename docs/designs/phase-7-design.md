# Phase 7 修改计划 — Chip Topology 标题位置 + Qubit Card 列宽修复

**文档日期**：2026-06-18
**角色**：Supervisor（设计文档，供实现侧 Claude Code 执行）
**设计基准**：Phase 6 完成后的代码（`exp_toolkit/report/generator.py`）

---

## 一、需求

| 需求 | 说明 | 影响文件 |
|------|------|---------|
| R1 | Chip Topology 每张图标题放在图的正上方，移除"1. Chip Topology — ***"章节名 | generator.py |
| R2 | qubit card 4 列（Label \| Value \| @Freq \| Source）正确显示，@Freq 列不被挤出卡片 | generator.py |

---

## 二、R1 — 拓扑图标题重定位

### 问题诊断

当前 `_build_overview()`（line 716–730）每参数生成独立 `<section>` + `<h2>`：

```html
<section id="overview-T1">
  <h2>1. Chip Topology — T1 (μs)</h2>
  <figure><svg>...</svg></figure>
</section>
```

这导致每张图前都有一个"1. Chip Topology — xxx"的章节标题，视觉效果冗余。

### 设计

将 N 张图合并到一个 `<section id="overview">` 下，共享一个章节标题 `1. Chip Topology`。每张图用 `<figcaption>` 标注参数名，置于图的正上方。

**_build_overview() 重写**：

```python
def _build_overview(self, topology_params: list[str]) -> str:
    figures_html: list[str] = []
    for param in topology_params:
        svg = self._build_single_topology_figure(param)
        if svg is None:
            continue
        label = _COLORMAP_LABELS.get(param, param)
        figures_html.append(
            f'<figure>'
            f'<figcaption>{label}</figcaption>'
            f'{svg}'
            f'</figure>'
        )
    if not figures_html:
        return ""
    return (
        f'<section id="overview">'
        f'<h2>1. Chip Topology</h2>'
        f'{"\n".join(figures_html)}'
        f'</section>'
    )
```

**CSS 新增**（在 `figure { }` 之后）：

```css
figcaption {
    text-align: center;
    font-weight: 600;
    margin-bottom: 8px;
    font-size: 0.95em;
}
```

**生成效果**：
```html
<section id="overview">
  <h2>1. Chip Topology</h2>
  <figure>
    <figcaption>T1 (μs)</figcaption>
    <svg>...</svg>
  </figure>
  <figure>
    <figcaption>T2* (μs)</figcaption>
    <svg>...</svg>
  </figure>
  ...
</section>
```

每个 `<figcaption>` 紧贴图的正上方，共享一个章节标题。

---

## 三、R2 — Qubit Card 4 列溢出修复

### 问题诊断

当前 `.qubit-grid` CSS（line 74）：
```css
grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
```

卡片最小宽度 300px。减去 `padding: 16px`（左右共 32px），内容区仅 268px。4 列表格最小需要约 340–380px：

| 列 | 典型内容 | 最小宽 |
|----|---------|--------|
| Label (th) | "Drive Eff" | ~55px |
| Value (td.value) | "61.100 ± 0.000 μs" + `white-space: nowrap` | ~130px |
| @Freq | "@ 4.131 GHz" | ~90px |
| Src | "(00051)" | ~50px |
| 单元格 padding | 4×2×6px | 48px |
| **合计** | | **~373px** |

300px 远低于 373px 需求，@Freq 列被挤出卡片。

### 设计

**3a. 增大 grid 最小列宽**：

```css
/* 改前 */
grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));

/* 改后 */
grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
```

380px 确保 4 列内容不被截断。在宽屏幕上 `auto-fill` 自动排多列，窄屏幕自动变单列。

**3b. 防御：qubit-card 溢出滚动**（可选增强）：

```css
.qubit-card {
    ...
    overflow-x: auto;
}
```

防止未来更宽的参数值导致溢出。

---

## 四、文件清单

| 文件 | 改动 |
|------|------|
| `exp_toolkit/report/generator.py` | R1: `_build_overview()` 重写 + CSS 新增 `figcaption`；R2: `.qubit-grid` 改 `minmax(380px, 1fr)` |

只改一个文件，~15 行核心改动。

---

## 五、测试计划

在 `tests/test_phase3.py` 中新增：

### R1
| 测试 | 说明 |
|------|------|
| `test_overview_single_section` | Overview 只有一个 `<section id="overview">`，而非每参数一个 section |
| `test_figcaption_per_figure` | 每张图有 `<figcaption>` 标签，内容为参数名 |
| `test_no_chip_topology_prefix` | HTML 中不含 "1. Chip Topology &mdash;" 文本 |

### R2
| 测试 | 说明 |
|------|------|
| `test_qubit_grid_min_width` | CSS 中 `minmax(380px, 1fr)` |
| `test_qubit_card_four_columns` | 典型 qubit card 含 4 个 `<td>` per row（非 colspan） |

---

## 六、验证

```bash
python -m pytest tests/test_phase3.py tests/ -v --tb=short
# 预期：236 + ~5 新增 ≈ 241 passed
```
