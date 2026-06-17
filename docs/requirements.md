# ExpToolKit — 需求规格文档 v2

> **v2 修订日期**：2026-06-17  
> **v1 → v2 主要变更**：工作流重构（引入参数累积层）、拟合模块改为按实验类型分发、报告改为芯片级汇总、新增 state 模块、chip_state.json 结构更新、纠正命名规则描述  
> 后续实现会话应以本文档为准则。

---

## 目录

1. [项目背景](#1-项目背景)
2. [数据格式规格](#2-数据格式规格)
3. [模块需求](#3-模块需求)
   - 3.1 [IO 模块](#31-io-模块)
   - 3.2 [拟合模块](#32-拟合模块)
   - 3.3 [可视化模块](#33-可视化模块)
   - 3.4 [State 模块](#34-state-模块)
   - 3.5 [报告模块](#35-报告模块)
4. [完整工作流](#4-完整工作流)
5. [实现优先级](#5-实现优先级)
6. [开放问题](#6-开放问题)
7. [执行约定](#7-执行约定)

---

## 1. 项目背景

**领域**：超导量子计算芯片的表征与测量

**典型工作流**：
```
设计实验参数 → 设备 API 发送微波信号 → 读取返回信号 →
处理为可理解数据 → 拟合分析 → 累积参数到 chip_state.json → 生成 HTML 报告（组会展示）
```

**技术栈**：Python >= 3.10, numpy, scipy, matplotlib, lmfit, jupyter

**运行方式**：ExpToolKit 以可安装 Python 包形式使用（`pip install -e .`），用户在 Jupyter notebook 或脚本中调用。

**输出目标**：芯片级 HTML 报告，用于组会向同事展示整颗芯片的当前状态。

---

## 2. 数据格式规格

### 2.1 文件三元组

每个实验生成三个文件，三个文件的**编号始终一致**：

| 文件 | 命名格式 | 内容 |
|------|---------|------|
| CSV | `{编号} - {实验类型}, {比特}.csv` | 实验数据（无表头） |
| INI | `{编号} - {实验类型}, {比特}.ini` | 实验设置、列标签、仪器配置 |
| JSON | `{编号} - parameters.json` | 芯片参数快照 |

**示例**：

```
00747 - T1_ground, Q16.csv       ← CSV 和 INI 的基名相同（含实验类型+比特）
00747 - T1_ground, Q16.ini
00747 - parameters.json          ← JSON 只使用编号
```

**注意**：不同实验的 CSV/INI 基名格式可能不同（取决于实验控制软件），但编号总是一致的。

### 2.2 CSV 数据格式

**通用规则**：
- **无表头行** — 列含义由 INI 的 `[Dependent N]` 和 `[Independent N]` 定义
- 前 N 列为自变量（N = INI `General.independent`）
- 后 M 列为因变量（M = INI `General.dependent`）
- 分隔符为逗号

### 2.3 已确认的实验类型

#### 类型 1：T1 弛豫时间测量

| 属性 | 值 |
|------|-----|
| 自变量数 | 1 |
| 自变量 1 | `coherence delay` (μs)，线性步进 |
| 因变量数 | 8（可变） |
| 典型因变量 | Qxx P0, Qxx P1, 全局 P0, 全局 P1, 校准列... |
| 数据量级 | ~20–100 行 |
| 拟合模型 | 指数衰减：P1(t) = A·exp(-t/τ) + C |
| 提取参数 | T1 = τ（μs），及其测量时的比特频率 |

**已见示例**：`00747 - T1_ground, Q16.csv`（21 行 × 9 列）

#### 类型 2：光谱测量 — IQ 原始数据

| 属性 | 值 |
|------|-----|
| 自变量数 | 2 |
| 自变量 1 | `zpa`（flux bias，无量纲） |
| 自变量 2 | `dr_freq`（驱动频率，GHz） |
| 因变量数 | 4 |
| 因变量 | IQ Amp, IQ Phase (rad), I, Q |
| 数据量级 | ~数千–数万行（2D 网格展平） |
| 主要用途 | 提取 f01 频率响应 → 拟合 f01 vs bias 色散曲线 |
| 拟合模型 | 沿 freq 轴：Lorentzian 峰拟合；沿 bias 轴：Gaussian 的 f01 色散 |

**已见示例**：`00023 - spectro, Q07.csv`（7,371 行，21 个 zpa × 351 个频率）

**重要**：2D 光谱数据的核心用途之一是**提取比特频率随 bias 的变化曲线**（f01 dispersion）。流程：
1. 在每个 zpa 切片上沿 freq 轴拟合 Lorentzian，得到 `f01(zpa)`
2. 对所有的 `(zpa, f01)` 点拟合 `A·exp(-(zpa-center)²/(2σ²)) + offset`，获得 f01 范围（min/max）和最优 bias 工作点

#### 类型 3：光谱测量 — 概率数据

| 属性 | 值 |
|------|-----|
| 自变量数 | 2 |
| 自变量 1 | `zpa`（flux bias） |
| 自变量 2 | `dr_freq`（驱动频率，GHz） |
| 因变量数 | 4 |
| 因变量 | Qxx P0, Qxx P1, 全局 P0, 全局 P1 |
| 数据量级 | ~数万行 |
| 拟合模型 | 同类型 2，但在概率空间 |

**已见示例**：`00732 - spectro, Q15.csv`（16,441 行，41 个 zpa × 401 个频率）

#### 未来支持的实验类型（非穷举）

| 实验类型 | 自变量 | 拟合模型 | 提取参数 |
|---------|--------|---------|---------|
| T2* / Ramsey | 1（延迟时间） | 指数衰减正弦 | T2*，频率失谐 Δf |
| T2 Echo | 1（延迟时间） | 指数衰减 | T2_echo |
| Rabi | 1（驱动宽度或幅度） | 衰减正弦 | π 脉冲校准值，驱动效率 |
| Rabi Chevron | 2（频率 + 幅度） | 2D Chevron 图案 | 最优驱动参数 |
| 随机基准测试 (RB) | 1（Clifford 序列长度） | A·p^N + B | 门保真度 |

### 2.4 INI 配置格式

标准 INI 结构：

```ini
[General]
created = 2026-06-10, 13:10:29
title = T1_ground, Q16
independent = 1       # 自变量列数
dependent = 8          # 因变量列数
parameters = 278       # Parameter 节数量

[Independent 1]
label = coherence delay
units = us

[Dependent 1]
label = 
units = 
category = Q16 P0      # ← 列含义的核心来源

[Parameter 1]
label = -qidxs
data = '[16]'
...
```

**关键信息提取**：
- `General.title`：实验标题（用于推断实验类型）
- `General.independent` / `General.dependent`：列数
- `[Independent N]`：自变量标签和单位
- `[Dependent N]`：因变量标签、单位、类别（category 是最重要的列含义说明）
- `[Parameter N]`：实验参数元数据

**已确认识别模式**：
- `r[start:stop:step,unit]` → 扫描范围定义
- `[q1, q2, ...]` → 参与测量的比特或 ancilla 列表
- `Device.Qxx.ADC/DAC.*` → 设备链映射
- `Instrument.*` → 仪器配置
- `connection.*` → 网络连接

### 2.5 JSON 参数快照

结构见原始分析。关键字段：

- `qubits.Qxx.f01(GHz)` — 比特频率（用于标注测量时的频率）
- `qubits.Qxx.pi_amp` / `qubits.Qxx.pi_width(ns)` — 驱动参数（乘积的倒数表征驱动效率）
- `qubits.Qxx.readout_freq(GHz)` — 读取频率
- `readout_IQ.Qxx_2.centers` — IQ 分类中心（用于读取保真度计算）
- `readout_IQ.Qxx_2.varis` — 分类方差

**注意**：JSON 文件是配置模板，包含所有可能被测量的比特。实际测量哪些比特由 INI 参数决定。

---

## 3. 模块需求

### 3.1 IO 模块

**路径**：`exp_toolkit/io/`

**职责**：统一读取实验三元组（CSV + INI + JSON），返回结构化数据。IO 模块不依赖其他子模块。

#### 功能需求

| 功能 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `load_experiment()` | CSV/INI 路径（任一） | `Experiment` 数据类 | 自动找到同编号的三个文件并解析 |
| `load_csv_with_meta()` | CSV 路径 + INI 路径 | `np.ndarray` + 列元数据 | 从 INI 解析列标签 |
| `parse_ini_metadata()` | INI 路径 | `IniMeta` 数据类 | 提取 General + Independent + Dependent |
| `load_parameters()` | JSON 路径 | `ParamsSnapshot` 数据类 | 解析 qubits/couplers/lines/readout_IQ |

#### 约束

- 返回的 numpy 数组附带物理单位信息
- 支持 1D 和 2D 实验（通过 `General.independent` 动态适配）
- INI 解析应健壮处理变量数量的 Parameter 节
- 不在此层做数据筛选或拟合 — 只做读取和结构化

#### 数据类草稿

```python
@dataclass
class Experiment:
    exp_id: str              # "00747"
    title: str               # "T1_ground, Q16"
    timestamp: datetime
    independent_vars: list[ColumnMeta]
    dependent_vars: list[ColumnMeta]
    data: np.ndarray         # (n_rows, n_independent + n_dependent)
    params: ParamsSnapshot   # 来自 JSON
    settings: dict[str, Any] # 来自 INI Parameter 节

@dataclass
class ColumnMeta:
    label: str
    units: str
    category: str            # "Q16 P1", "Q07 IQ Amp"

@dataclass
class ParamsSnapshot:
    qubits: dict[str, QubitParams]
    couplers: dict[str, Any]
    readout_iq: dict[str, IQBlobs]
    lines: dict[str, dict[str, float]]

@dataclass
class QubitParams:
    f01: float           # GHz
    f12: float | None
    pi_amp: float
    pi_width: float      # ns
    readout_freq: float  # GHz
    readout_amp: float   # dBm

@dataclass
class IQBlobs:
    centers: list[complex]   # 2 或 3 个分类中心
    variance: float
    n_states: int            # 2 或 3
```

---

### 3.2 拟合模块

**路径**：`exp_toolkit/fitting/`

**职责**：提供量子计算实验常用物理模型的拟合工具。支持自动模式（按实验类型分发）和手动模式（用户选列+模型）。

#### 3.2.1 子模块结构

```
exp_toolkit/fitting/
├── __init__.py          # 暴露所有 fit_* 函数、fit()、FitResult、models
├── models.py            # 物理模型纯函数（前向计算，不调用 lmfit）
├── engine.py            # fit() 通用入口 + FitResult 数据类
├── guessers.py          # 参数自动猜测函数（每个模型一个）
├── experiments/         # 按实验类型组织的拟合入口
│   ├── _base.py         # _auto_fit() 公共辅助（列选择 + 模型分发）
│   ├── t1.py            # fit_t1()
│   ├── spectro.py       # fit_spectro(), fit_f01_dispersion()
│   ├── ramsey.py        # fit_ramsey()
│   ├── rabi.py          # fit_rabi()
│   └── rb.py            # fit_rb()
└── iq_analysis.py       # assignment_fidelity()
```

#### 3.2.2 两种使用模式

**自动模式（推荐）**— 按实验类型调用对应的 `fit_*()` 函数：

```python
from exp_toolkit.fitting import fit_t1, fit_spectro

# T1：自动选 (delay, Qxx P1) 列对 + ExponentialDecay
result = fit_t1(exp)

# 光谱 2D：自动选 (freq, IQ_Amp) 列对 + Lorentzian
result = fit_spectro(exp)

# f01 色散：沿 freq 轴每 zpa 切片拟合 Lorentzian → 再拟合 f01(zpa)
f01_range = fit_f01_dispersion(exp)
```

每个 `fit_*()` 函数接受 `x_col` / `y_col` 参数覆盖默认选列，以及该实验类型特有的可选参数。

**手动模式（回退）**— 用户直接控制列和模型：

```python
from exp_toolkit.fitting import fit, models

x = exp.data[:, 0]
y = exp.data[:, 3]   # 用户自行选择
result = fit(x, y, models.ExponentialDecay)
```

#### 3.2.3 `_auto_fit()` 分发逻辑

每个 `fit_*()` 函数内部调用 `_auto_fit()`，流程为：

```
Experiment
    │
    ▼
┌─────────────────────────────┐
│ 1. 列选择                    │
│    x_col="auto" → 从 INI     │
│    Independent 推断自变量列    │
│    y_col="auto" → 从          │
│    Dependent.category 匹配    │
│    qubit P1 / IQ Amp 等       │
└──────────┬──────────────────┘
           ▼
┌─────────────────────────────┐
│ 2. 模型 + 猜测器 绑定         │
│    由各 fit_* 函数硬编码指定   │
│    T1 → ExponentialDecay     │
│    Spectro → Lorentzian      │
└──────────┬──────────────────┘
           ▼
         fit() → FitResult
```

#### 3.2.4 已确认的实验型拟合函数

| 函数 | 适用实验 | 默认模型 | 特有参数 | 提取的参数 |
|------|---------|---------|---------|-----------|
| `fit_t1(exp, **)` | T1 | ExponentialDecay | — | T1, A, C |
| `fit_spectro(exp, **)` | 光谱（IQ/概率） | Lorentzian | `zpa_slice` | f01(per-zpa) |
| `fit_f01_dispersion(exp, **)` | 光谱 2D | Gaussian(f01 vs bias) | `fit_range` | f01::min, f01::max |
| `fit_ramsey(exp, **)` | T2* | DecayingSinusoid | — | T2*, Δf |
| `fit_rabi(exp, **)` | Rabi | RabiOscillation | `drive_var` | π 脉冲校准值 |
| `fit_rb(exp, **)` | RB | RBExponential | — | 门保真度 |

**f01 dispersion 拟合的专用说明**：

`fit_f01_dispersion()` 执行两步拟合：
1. 沿 freq 轴，对每个 zpa 切片调用 `fit_spectro()` 提取 `f01(zpa)` → 得到一组 `(zpa, f01)` 点
2. 对 `(zpa, f01)` 点拟合 `A·exp(-(zpa-center)²/(2σ²)) + offset`，得到 f01 的范围（offset = 最大值，offset - A ≈ 最小值，取决于 A 的符号）

返回 `F01Dispersion` 数据类，包含 `f01_min`, `f01_max`, `f01_vs_zpa` 曲线数据。

#### 3.2.5 物理模型

| 模型名 | 公式 | 参数 | 典型场景 |
|--------|------|------|---------|
| **ExponentialDecay** | `A·exp(-x/τ) + C` | A, τ, C | T1, T2_echo |
| **DecayingSinusoid** | `A·exp(-x/τ)·cos(2π·f·x + φ) + C` | A, τ, f, φ, C | T2* (Ramsey) |
| **RabiOscillation** | `A·exp(-x/τ)·cos(2π·Ω·x + φ) + C` | A, τ, Ω, φ, C | Rabi |
| **Lorentzian** | `A·(γ²)/((x-x₀)² + γ²) + C` | A, x₀, γ, C | 光谱 (spectroscopy) |
| **Gaussian** | `A·exp(-(x-x₀)²/(2σ²)) + C` | A, x₀, σ, C | f01 dispersion 拟合 |
| **RBExponential** | `A·p^N + B` | A, p, B | 随机基准测试 |

**建模约定**：
- 每个模型是纯函数：`(x: np.ndarray, **params) -> np.ndarray`
- 模型函数不调用 lmfit，只做前向计算
- 模型通过 `lmfit.Model` 包装后与引擎对接

#### 3.2.6 参数自动猜测

| 模型 | 猜测策略 |
|------|---------|
| ExponentialDecay | A = y.max() - y.min(), C = y.min(), τ = x_range/3 |
| DecayingSinusoid | FFT 找主频 → f；包络拟合 → τ |
| Lorentzian | x₀ = x[y.argmax()], γ = FWHM/2 估计, A = (y.max()-y.min())*γ |
| Gaussian | x₀ = x[y.argmax()], σ = FWHM/2.355 |
| RabiOscillation | FFT 找 Ω；包络拟合 → τ |

#### 3.2.7 FitResult

```python
@dataclass
class FitResult:
    model_name: str
    params: dict[str, float]        # 最佳拟合参数
    errors: dict[str, float]        # 标准误差（1σ）
    r_squared: float
    residuals: np.ndarray
    cov_matrix: np.ndarray | None
    red_chi2: float
    success: bool
    message: str
```

**注意**：FitResult 是内存对象，不持久化到文件。拟合结果由用户决定是否写入 `ChipState`（见 §3.4）。需要复现时，重新对原始数据运行拟合即可。

#### 3.2.8 读取保真度

```python
def assignment_fidelity(iq_blobs: IQBlobs) -> ReadoutFidelity:
    """从 IQ 分类中心计算读取保真度。
    
    2 态：从 2D Gaussian 重叠积分计算
    3 态：计算 pairwise 分类错误率的加权平均
    """

@dataclass
class ReadoutFidelity:
    fidelity_01: float          # |0⟩→|0⟩ 保真度
    fidelity_10: float          # |1⟩→|1⟩ 保真度
    avg_fidelity: float         # 平均读取保真度
    snr: float | None
    freq_GHz: float             # 测量时的读取频率
```

---

### 3.3 可视化模块

**路径**：`exp_toolkit/visualization/`

**职责**：芯片拓扑图和拟合结果图的绘制。

#### 3.3.1 芯片拓扑图

**核心需求**：
1. **自定义拓扑**：比特布局完全可配置，支持任意几何形状
2. **两种显示模式**：
   - **模式 A（测量覆盖图）**：有数据的比特高亮（彩色），无数据的灰色
   - **模式 B（参数色标图）**：每个比特用色标映射某个参数值
3. **标注**：每个比特上显示编号 + 关键参数（可配置显示哪些字段）
4. **连接/耦合线**：支持绘制比特间连接（可选），保留耦合器绘制功能
5. **SVG 输出**：适配 HTML 报告嵌入

**API 草稿**：

```python
class ChipTopology:
    """芯片拓扑描述"""
    
    def __init__(self, layout: dict[tuple[int,int], str | None]):
        """(row, col) → qubit_name，None 表示空缺"""
    
    @classmethod
    def from_grid(cls, rows: int, cols: int, 
                  numbering: str = "row-major", start: int = 1):
        """快速创建标准网格拓扑"""
    
    def add_coupler(self, q1: str, q2: str, **params): ...
    def get_neighbors(self, name: str) -> list[str]: ...


class ChipArtist:
    """芯片拓扑图绘制器"""
    
    def draw(self, ax=None) -> plt.Figure: ...
    def highlight_measured(self, measured_qubits: list[str]) -> None: ...
    def colormap_param(self, param_name, values: dict[str, float], cmap="viridis") -> None: ...
    def annotate(self, fields: list[str], values: dict[str, dict]) -> None: ...
    def save(self, path: str, format="svg"): ...
```

#### 3.3.2 拟合结果图

```python
def plot_fit_result(x, y, result: FitResult, title=None,
                    xlabel=None, ylabel=None, show_residuals=True) -> plt.Figure:
    """标准拟合结果图：数据点 + 拟合曲线 + 残差"""
```

#### 3.3.3 2D 光谱图

```python
def plot_spectroscopy_2d(exp: Experiment, z_slice=None) -> plt.Figure:
    """2D 光谱伪彩图 + 可选 1D 切片"""
```

#### 可视化约定

- 统一使用 matplotlib 面向对象 API（`fig, ax = plt.subplots()`）
- 所有绘图函数接受 `ax` 参数，不自行创建 Axes
- 色标使用 perceptually uniform colormap
- 不在绘图代码中硬编码比特坐标 — 拓扑来自 `ChipTopology`

---

### 3.4 State 模块

**路径**：`exp_toolkit/state/`

**职责**：管理累积的芯片参数状态（`chip_state.json`），提供读写和更新接口。拟合模块不直接写入 State — 用户手动控制何时保存。

#### 3.4.1 chip_state.json 结构

```json
{
  "chip_id": "5x5-chip-001",
  "topology": {
    "rows": 5,
    "cols": 5,
    "numbering": "row-major",
    "start": 1
  },
  "last_updated": "2026-06-17",
  "qubits": {
    "Q16": {
      "f01_GHz": {
        "min": 4.2,
        "max": 4.9,
        "source_exp": "00023"
      },

      "T1_us": [
        {
          "value": 45.2,
          "error": 1.3,
          "freq_GHz": 4.71,
          "timestamp": "2026-06-10",
          "source_exp": "00747"
        },
        {
          "value": 38.1,
          "error": 1.8,
          "freq_GHz": 4.85,
          "timestamp": "2026-06-15",
          "source_exp": "00789"
        }
      ],

      "T2star_us": [
        {
          "value": 12.3,
          "error": 0.5,
          "freq_GHz": 4.71,
          "timestamp": "2026-06-11",
          "source_exp": "00750"
        }
      ],

      "T2echo_us": [],

      "drive_efficiency": [
        {
          "pi_amp": 0.66,
          "pi_width_ns": 30,
          "product": 19.8,
          "freq_GHz": 4.71,
          "timestamp": "2026-06-10",
          "source_exp": "00747"
        }
      ],

      "readout_fidelity": [
        {
          "F0": 0.95,
          "F1": 0.92,
          "avg": 0.935,
          "freq_GHz": 6.237,
          "timestamp": "2026-06-10",
          "source_exp": "00747"
        }
      ]
    },

    "Q07": { "...": "..." }
  }
}
```

#### 3.4.2 设计要点

- **f01_GHz**：存 `min`/`max`（范围），从 f01 dispersion 拟合得到
- **T1_us / T2star_us / T2echo_us**：列表存所有历史测量值，每条记录含 `value`, `error`, `freq_GHz`（测量时比特频率）, `timestamp`, `source_exp`
- **drive_efficiency**：存 `pi_amp × pi_width(ns)` 的乘积，标注频率
- **readout_fidelity**：存 `F0`, `F1`, `avg`，标注读取频率
- **列表策略**：同参数多值保留全部历史；报告时按 `timestamp` 取最新值
- **写入控制**：用户手动调用 `.add_T1()` 等方法；不自动写入

#### 3.4.3 API 草稿

```python
@dataclass
class ParameterEntry:
    value: float
    error: float | None
    freq_GHz: float            # 测量时的比特（或读取）频率
    timestamp: str
    source_exp: str

@dataclass
class QubitState:
    f01_GHz: F01Range | None
    T1_us: list[ParameterEntry]
    T2star_us: list[ParameterEntry]
    T2echo_us: list[ParameterEntry]
    drive_efficiency: list[DriveEntry]
    readout_fidelity: list[ReadoutEntry]


class ChipState:
    """芯片参数累积状态"""

    @classmethod
    def new(cls, chip_id: str, topology: ChipTopology) -> "ChipState": ...
    @classmethod
    def load(cls, path: str) -> "ChipState": ...
    def save(self, path: str): ...

    # 添加参数（用户手动调用）
    def add_T1(self, qubit: str, value: float, error: float | None,
               freq_GHz: float, source_exp: str): ...
    def add_T2star(self, qubit: str, ...): ...
    def add_T2echo(self, qubit: str, ...): ...
    def add_f01_range(self, qubit: str, f01_min: float, f01_max: float,
                      source_exp: str): ...
    def add_drive_efficiency(self, qubit: str, pi_amp: float,
                             pi_width_ns: float, freq_GHz: float,
                             source_exp: str): ...
    def add_readout_fidelity(self, qubit: str, F0: float, F1: float,
                             avg: float, freq_GHz: float,
                             source_exp: str): ...

    # 查询
    def get_qubit(self, name: str) -> QubitState: ...
    def get_latest(self, name: str, param: str) -> ParameterEntry | None: ...
    def list_measured_qubits(self) -> list[str]: ...
```

---

### 3.5 报告模块

**路径**：`exp_toolkit/report/`

**职责**：从 `ChipState` + 拓扑数据生成芯片级 HTML 汇总报告。

#### 3.5.1 报告性质

- **芯片级汇总**（非单次实验报告）：展示整颗芯片所有已测量比特的参数
- **自包含 HTML**：内嵌 CSS + SVG，无外部依赖，可直接在浏览器打开
- **组会展示用途**：适合投影展示，信息密度高

#### 3.5.2 报告模板结构

```
┌─────────────────────────────────────────┐
│  5×5 芯片状态报告                       │
│  芯片 ID：5x5-chip-001                  │
│  更新日期：2026-06-17                    │
├─────────────────────────────────────────┤
│  ## 1. 芯片拓扑概览                      │
│                                         │
│  [参数色标图 SVG — 默认映射 f01 中值]     │
│  [可切换映射：T1 / T2* / 读取保真度...]   │
│                                         │
│  ## 2. 各比特详细参数                     │
│                                         │
│  ### 2.1 Q16                            │
│  | 参数 | 值 | 误差 | 测量频率 | 来源  |  │
│  | f01  | 4.2–4.9 GHz | — | — | 00023|  │
│  | T1   | 38.1 μs | ±1.8 | 4.85 GHz| 00789│
│  | T2*  | 12.3 μs | ±0.5 | 4.71 GHz| 00750│
│  | ...  | ... | ... | ... | ...   |     │
│                                         │
│  ### 2.2 Q15                            │
│  ...                                    │
│                                         │
│  ## 3. 未测量比特                        │
│  Q1, Q2, Q3, Q5, Q8, ...（灰色）        │
│                                         │
│  ## 4. 数据来源                          │
│  | 实验编号 | 日期 | 类型 | 比特 |      │
│  | 00747 | 06-10 | T1 | Q16 |          │
│  | 00023 | 06-16 | spectro | Q07 |     │
│  | ...   | ...  | ... | ... |          │
└─────────────────────────────────────────┘
```

#### 3.5.3 API 草稿

```python
class ReportGenerator:
    """芯片状态 HTML 报告生成器"""
    
    def __init__(self, state: ChipState, topology: ChipTopology):
        ...
    
    def generate(
        self,
        output_path: str,
        title: str = None,
        sections: list[str] = None,   # 可选：只包含指定节
        colormap_param: str = "f01",  # 拓扑图默认色标参数
    ) -> str:
        """生成自包含 HTML 文件，返回文件路径"""
```

#### 约束

- 生成单文件 HTML，无外部 CSS/JS 依赖
- 中文字体正常渲染
- 图表以 SVG 内嵌（清晰可缩放）
- 报告结构可配置（用户可选择包含/不包含某些节）
- 未测量比特用灰色显示，不展示参数表
- 有历史数据时默认显示最新值，可展开查看历史

---

## 4. 完整工作流

### 4.1 架构图

```
                         外部数据目录（用户指定路径，不随包分发）
                         ├── 00747 - T1_ground, Q16.{csv,ini}
                         ├── 00747 - parameters.json
                         ├── 00023 - spectro, Q07.{csv,ini}
                         ├── 00023 - parameters.json
                         └── ...
                                     │
                                     │ 用户调用 load_experiment()
                                     ▼
┌────────────────────────────────────────────────────────────────┐
│  exp_toolkit.io          ← 读取 CSV/INI/JSON → Experiment 对象  │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               │ 用户调用 fit_t1() / fit_spectro() 等
                               │ （自动模式）或 fit()（手动模式）
                               ▼
┌────────────────────────────────────────────────────────────────┐
│  exp_toolkit.fitting      ← fit → FitResult（纯内存，不持久化）   │
│                           ← assignment_fidelity() → 保真度      │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               │ 用户手动调用 state.add_*()
                               │ （拟合与持久化解耦）
                               ▼
┌────────────────────────────────────────────────────────────────┐
│  exp_toolkit.state        ← ChipState                          │
│                           ← .add_T1() / .add_f01_range() 等     │
│                           ← .save("chip_state.json")            │
│                           ← .load("chip_state.json")            │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               │ 任何时候用户调用 ReportGenerator
                               ▼
┌────────────────────────────────────────────────────────────────┐
│  exp_toolkit.report       ← ReportGenerator(state, topology)    │
│                           ← → report.html（芯片级汇总）          │
└────────────────────────────────────────────────────────────────┘
```

### 4.2 典型使用流程

```python
# ====== 场景：用户完成了一批实验，想更新芯片状态并出报告 ======

from exp_toolkit.io import load_experiment
from exp_toolkit.fitting import fit_t1, fit_spectro, fit_f01_dispersion
from exp_toolkit.fitting.iq_analysis import assignment_fidelity
from exp_toolkit.state import ChipState
from exp_toolkit.visualization import ChipTopology
from exp_toolkit.report import ReportGenerator

# === 0. 初始化拓扑和状态 ===
topo = ChipTopology.from_grid(5, 5, numbering="row-major")

# 首次使用：新建空状态
state = ChipState.new("5x5-chip-001", topo)

# 后续使用：加载已有状态
# state = ChipState.load("chip_state.json")

# === 1. 处理 T1 实验 00747 ===
exp_00747 = load_experiment("path/to/00747 - T1_ground, Q16.csv")
result_t1 = fit_t1(exp_00747)
print(f"T1 = {result_t1.params['tau']:.1f} ± {result_t1.errors['tau']:.1f} μs")

# 用户觉得结果可信 → 手动保存
state.add_T1("Q16", value=result_t1.params["tau"],
             error=result_t1.errors["tau"],
             freq_GHz=exp_00747.params.qubits["Q16"].f01,
             source_exp=exp_00747.exp_id)

# === 2. 处理光谱实验 00023 ===
exp_00023 = load_experiment("path/to/00023 - spectro, Q07.csv")
f01_disp = fit_f01_dispersion(exp_00023)
print(f"Q07 f01: {f01_disp.f01_min:.3f}–{f01_disp.f01_max:.3f} GHz")

state.add_f01_range("Q07", f01_disp.f01_min, f01_disp.f01_max,
                    source_exp=exp_00023.exp_id)

# === 3. 计算读取保真度 ===
iq_data = exp_00747.params.readout_iq.get("Q16_2")
if iq_data:
    fidelity = assignment_fidelity(iq_data)
    state.add_readout_fidelity("Q16", fidelity.fidelity_01,
                               fidelity.fidelity_10, fidelity.avg_fidelity,
                               freq_GHz=exp_00747.params.qubits["Q16"].readout_freq,
                               source_exp=exp_00747.exp_id)

# === 4. 持久化状态 ===
state.save("chip_state.json")

# === 5. 生成组会报告（任何时候都可以） ===
report = ReportGenerator(state, topo)
report.generate("report_2026-06-17.html", title="5×5 芯片状态 — 6月17日")
```

---

## 5. 实现优先级

### 阶段 1：数据 IO + 基础拟合（第一优先级）

- [ ] `exp_toolkit/io/readers.py` — `load_experiment()`, `parse_ini_metadata()`, `load_parameters()`
- [ ] `exp_toolkit/fitting/models.py` — ExponentialDecay, Lorentzian, Gaussian, DecayingSinusoid
- [ ] `exp_toolkit/fitting/guessers.py` — guess_exponential, guess_lorentzian, guess_gaussian
- [ ] `exp_toolkit/fitting/engine.py` — `fit()`, `FitResult`
- [ ] `exp_toolkit/fitting/experiments/_base.py` — `_auto_fit()`
- [ ] `exp_toolkit/fitting/experiments/t1.py` — `fit_t1()`
- [ ] `exp_toolkit/fitting/experiments/spectro.py` — `fit_spectro()`, `fit_f01_dispersion()`
- [ ] `tests/` — 合成数据验证每个模型能恢复已知参数

### 阶段 2：State 模块 + 芯片拓扑图（第二优先级）

- [ ] `exp_toolkit/state/` — `ChipState`, `QubitState`, `ParameterEntry`
- [ ] `exp_toolkit/visualization/chip_plot.py` — `ChipTopology`, `ChipArtist`
- [ ] `exp_toolkit/visualization/fit_plot.py` — `plot_fit_result()`
- [ ] 确认 chip_state.json 的读写和拓扑图效果

### 阶段 3：报告 + 读取保真度（第三优先级）

- [ ] `exp_toolkit/fitting/iq_analysis.py` — `assignment_fidelity()`
- [ ] `exp_toolkit/report/generator.py` — `ReportGenerator`，HTML 报告组装
- [ ] 端到端验证：原始数据 → 拟合 → chip_state.json → HTML 报告

### 阶段 4：扩展（未来）

- [ ] `fit_ramsey()`, `fit_rabi()`, `fit_rb()`
- [ ] 2D 数据拟合工具优化
- [ ] 更多芯片拓扑布局预设
- [ ] Jupyter notebook 集成工具

---

## 6. 开放问题

1. **命名格式解析**：不同实验的命名格式可能不同。当前方案从 INI `title` 字段推断实验类型，不从文件名解析。

2. **2D 拟合策略细节**：光谱 2D 数据沿 zpa 轴切片拟合时，zpa 的网格精度和频率范围的边界条件处理需在实际数据上测试确定。

3. **多比特批量拟合**：如果一次实验测量了多个比特，IO 模块通过 INI Dependent category 字段关联列到比特。`fit_*()` 默认选择第一个匹配的比特列。批量模式（一次 fit 所有比特）留待阶段 4。

4. **IQ 数据 vs 概率数据**：光谱实验有两种输出模式。拟合模块应兼容两种 — 在 `fit_spectro()` 内部根据列标签判断数据类型（`IQ Amp` vs `P1`），选择对应的 y 轴处理方式。

5. **比特编号与拓扑映射**：当芯片拓扑改变时，`ChipTopology.from_grid()` 的默认编号可能不适用。用户可用 `ChipTopology(layout=...)` 手动定义。

6. **报告可配置性**：HTML 报告中哪些节显示、色标默认参数、表头顺序等是否需要配置？当前设计通过 `generate(sections=..., colormap_param=...)` 提供基础配置，更多选项留待阶段 4。

7. **chip_state.json 版本管理**：当 JSON 结构迭代时，旧版本文件的迁移策略？当前方案：v1 阶段不做兼容性保证，手动重建。v2+ 考虑语义化版本号 + 迁移脚本。

---

## 7. 执行约定

> 本章节记录跨模块的工程决策，在实现各阶段中应统一遵守。与 §6（开放问题）不同，这些是**已确认的原则**，而非待解决的问题。

### 7.1 错误处理原则

**统一原则**：默认报错但不崩溃。所有异常通过 Python 异常机制抛出，附带清晰的错误消息，让用户在 notebook/脚本中能立即看到问题。静默降级比显式报错更危险。

| 场景 | 行为 | 示例消息 |
|------|------|---------|
| 文件不存在或损坏 | 抛出 `FileNotFoundError` / `ValueError` | `"无法读取 INI 文件：xxx.ini 不是合法的 INI 格式"` |
| INI 解析失败 | 抛出 `IOError`，附带文件路径和具体错误 | `"解析 INI 失败：缺少 [General] 节"` |
| 列名匹配失败 | `fit_*()` 抛出 `ValueError`，列出可用的列 | `"找不到 Q16 P1 列。可用列：['Q16 P0', 'Q16 P1 for \|0>', ...]"` |
| 拟合不收敛 | `FitResult(success=False, message=...)` 正常返回；`fit_*()` 打印红色警告 | `"[警告] fit_t1 拟合未收敛：Q16 | 约化卡方 = 142.3"` |
| 猜测器无法推断初值 | 抛出 `ValueError` | `"无法为 ExponentialDecay 猜测初值：y 值全为 NaN"` |
| 缺少 JSON 参数文件 | 警告，`Experiment.params = None` | `"[警告] 未找到 00747 - parameters.json，参数快照将为空"` |
| zpa 切片超出数据范围 | 抛出 `ValueError` | `"zpa_slice=-0.5 不在数据范围内 [0.0, 0.45]"` |

**实现约定**：
- 所有公共 API 必须对参数做输入校验（`assert` 或显式 `raise ValueError`）
- 错误消息使用英文（便于搜索引擎），用户交互层面可额外包装为中文
- 不在库代码中调用 `sys.exit()` — 始终抛异常，由调用者决定如何处理

### 7.2 JSON 参数验证标记

**问题**：`parameters.json` 是配置模板，包含所有可能被测量的比特的参数。某次实验（如 00747）可能只测量了 Q16，但 JSON 中 Q11-Q15 的参数是历史残留值，未在本次实验中验证。

**约定**：IO 模块根据 INI 的 `-qidxs` 或 `-ancilla_ouput` 参数，标记 JSON 中哪些比特的参数在本次实验中被确认有效。

**实现方式**：
- `ParamsSnapshot` 中的 `QubitParams` 增加字段 `verified: bool = False`
- `load_parameters()` 接受可选参数 `verified_qubits: list[str] | None`（由 `load_experiment()` 从 INI 提取后传入）
- 拟合模块在使用 `exp.params.qubits["Q16"].f01` 前检查 `verified` 标志
- 若 `verified=False` 且无其他来源，`fit_*()` 发出警告

```python
@dataclass
class QubitParams:
    f01: float
    f12: float | None
    pi_amp: float
    pi_width: float
    readout_freq: float
    readout_amp: float
    verified: bool = False   # ← 新增
    extras: dict[str, Any] = field(default_factory=dict)
```

### 7.3 测试数据策略

**两层测试数据**：

| 层级 | 位置 | 内容 | 用途 |
|------|------|------|------|
| **合成数据** | `tests/fixtures/` | 小型 CSV（~20 行）+ 最小 INI，参数已知 | CI 可跑，验证模型能恢复已知参数 |
| **真实数据** | `data/`（gitignore） | 完整实验文件（~KB–MB） | 手动测试，开发时验证与真实仪器输出兼容 |

**合成数据规范**：
- 每个模型一个 fixture 文件对（如 `t1_synthetic.csv` + `t1_synthetic.ini`）
- 参数为精确值（如 T1 = 50.0 μs），加适量 Gaussian 噪声
- 测试断言：拟合参数与真实值的偏差 ≤ 3σ（即拟合误差范围内）
- 不依赖外部文件路径 — 使用 `tmp_path` fixture 或 `StringIO`

**真实数据测试**：
- 在 `tests/manual/` 下放置交互式脚本（非 pytest）
- 开发者在实现新功能后用真实数据验证
- 真实数据文件不提交到 git

### 7.4 实验类型映射

**问题**：从 `Experiment.title`（如 `"T1_ground, Q16"`）推断实验类型需要规则。命名可能有变体（`T1_ground` vs `T1_excited` vs `T1_relaxation`）。

**约定**：使用配置文件显式定义映射，不使用硬编码字符串匹配。

**实现方式**：`exp_toolkit/fitting/experiment_types.yaml`

```yaml
# 实验类型 → 拟合函数分发表
# key: INI title 中用于匹配的关键词（不区分大小写）
# fit_func: 对应的拟合函数名
# description: 简短说明

T1:
  match_keywords: ["T1", "t1"]       # title 中包含任一关键词即匹配
  fit_func: fit_t1
  default_model: ExponentialDecay
  description: "T1 弛豫时间测量"

spectro:
  match_keywords: ["spectro", "spectroscopy"]
  fit_func: fit_spectro
  default_model: Lorentzian
  description: "单频/双频光谱测量"

ramsey:
  match_keywords: ["ramsey", "T2*", "t2star"]
  fit_func: fit_ramsey
  default_model: DecayingSinusoid
  description: "Ramsey 干涉测量（T2*）"

rabi:
  match_keywords: ["rabi"]
  fit_func: fit_rabi
  default_model: RabiOscillation
  description: "Rabi 振荡测量"

rb:
  match_keywords: ["RB", "randomized_benchmarking", "benchmarking"]
  fit_func: fit_rb
  default_model: RBExponential
  description: "随机基准测试"
```

**调度逻辑**（在 `_auto_fit()` 或顶层 dispatch 函数中）：

```python
import yaml
from pathlib import Path

def _load_type_registry():
    cfg_path = Path(__file__).parent / "experiment_types.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)

def _infer_experiment_type(title: str) -> str | None:
    """从实验标题推断实验类型。返回 None 表示无法推断。"""
    registry = _load_type_registry()
    title_lower = title.lower()
    for type_name, config in registry.items():
        for kw in config["match_keywords"]:
            if kw.lower() in title_lower:
                return type_name
    return None
```

**扩展方式**：用户或后续开发者在 `experiment_types.yaml` 中添加新条目即可支持新实验类型，无需修改 Python 代码。

### 7.5 执行中记录决策

**原则**：需求文档不应无限膨胀。执行过程中出现的、需求文档未覆盖的设计决策，记录在 `docs/` 下的阶段性笔记中。

**约定**：
- 每完成一个实现阶段，创建 `docs/phase-N-notes.md`（如 `phase-1-notes.md`）
- 内容格式自由，记录以下类型的信息：
  - 与需求文档不同的实现选择（及原因）
  - 新增的 API 细节
  - 发现的数据格式变体
  - 性能瓶颈及解决方案
- 下一阶段开始前，回顾上一阶段的笔记
- 如果一个决策影响后续阶段的设计，将其提升到 `requirements.md` 的正文或开放问题中

**示例结构**：
```
docs/
├── requirements.md              # 本文档（架构级，慎重修改）
├── phase-1-notes.md             # IO + 拟合实现记录
├── phase-2-notes.md             # State + 可视化实现记录
├── phase-3-notes.md             # 报告 + 读取保真度实现记录
└── ...
```

---

> **本文档版本**：v3（2026-06-17）  
> **v2 → v3 变更摘要**：
> - 新增 §7 执行约定：错误处理原则、JSON 参数验证标记（`verified` 字段）、测试数据分层策略、实验类型映射 YAML 配置、执行中记录决策的流程
> 
> **v1 → v2 变更摘要**（保留）：
> - 纠正文件命名规则描述（编号一致，非基名一致）
> - 拟合模块改为按实验类型分发的独立函数（方案 2）
> - 新增 fit_f01_dispersion() 用于 2D 光谱 f01 范围提取
> - 新增 §3.4 State 模块（chip_state.json 管理）
> - chip_state.json 结构更新：f01 存 min/max，T1/T2*/驱动效率/读取保真度标注频率，列表存历史
> - 报告模块改为芯片级汇总（非单次实验报告）
> - 重写 §4 工作流，拟合与持久化解耦
> - 更新实现优先级
> 
> **使用说明**：后续实现会话应参考本文档的 API 草稿和数据结构定义。如有新增需求或发现文档与实际情况不符，请更新本文档并标注版本。
