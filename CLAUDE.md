# ExpToolKit — 超导量子计算实验工具包

## 项目目的

为超导量子比特芯片的测量、数据分析与报告生成提供 Python 工具包。核心场景：通过微波信号测量量子比特参数，拟合实验数据，生成带芯片拓扑示意图的实验报告。

当前聚焦：
1. **数据拟合包** — 提供量子计算实验常用拟合模型（T1/T2*/Rabi/光谱等），统一接口，附带不确定度估计
2. **芯片拓扑可视化** — 根据 5×5 阵列拓扑绘制比特布局图，标注各比特的关键参数（频率、T1、T2*、门保真度等）
3. **实验报告生成** — 基于已有数据自动生成包含图表和分析的报告

## 技术约束

- 语言/运行时：Python >= 3.10
- 核心依赖：`numpy`, `scipy`, `matplotlib`, `lmfit`（拟合引擎）, `pyyaml`（配置解析）, `jupyter`
- 拟合引擎统一使用 `lmfit`，不混用 `scipy.optimize.curve_fit`（避免参数管理方式不一致）
- 可视化统一使用 `matplotlib` 面向对象 API（`fig, ax = plt.subplots()`），不用 pyplot 全局状态机
- 类型标注：公开 API 必须有完整类型标注（mypy strict 模式可检查）
- 数据 I/O：原始数据以 CSV 三元组（CSV+INI+JSON）为主；HDF5/NPZ 用于处理后数据的中间存储（Future）

## 项目结构（规划中）

```
ExpToolKit/
├── CLAUDE.md                # 本文件
├── exp_toolkit/             # 主包
│   ├── __init__.py
│   ├── fitting/             # 拟合子包
│   │   ├── __init__.py
│   │   ├── models.py        # 物理模型纯函数（Lorentzian, ExpDecay, Ramsey...）
│   │   ├── engine.py        # fit() 通用入口 + FitResult
│   │   ├── guessers.py      # 参数自动猜测
│   │   ├── experiments/     # 按实验类型分发的拟合函数
│   │   │   ├── _base.py     # _auto_fit() 公共辅助
│   │   │   ├── t1.py        # fit_t1()
│   │   │   ├── spectro.py   # fit_spectro(), fit_f01_dispersion()
│   │   │   ├── ramsey.py    # fit_ramsey()
│   │   │   ├── rabi.py      # fit_rabi()
│   │   │   └── rb.py        # fit_rb()
│   │   └── iq_analysis.py   # assignment_fidelity()
│   ├── state/               # 参数累积状态管理
│   │   ├── __init__.py
│   │   └── chip_state.py    # ChipState, QubitState, ParameterEntry
│   ├── visualization/       # 可视化子包
│   │   ├── __init__.py
│   │   ├── chip_plot.py     # ChipTopology + ChipArtist
│   │   └── fit_plot.py      # plot_fit_result()
│   ├── io/                  # 数据读写
│   │   ├── __init__.py
│   │   └── readers.py       # load_experiment(), 多格式读取器
│   └── report/              # 报告生成（芯片级汇总）
│       ├── __init__.py
│       └── generator.py     # ReportGenerator → 自包含 HTML
├── notebooks/               # 实验 Jupyter Notebook（按日期/实验编号组织）
├── tests/                   # 测试（与 exp_toolkit 镜像结构）
└── data/                    # 实验数据（gitignore，仅保留小样本用于测试）
```

## 架构约定

### 1. 拟合模型定义
- 每个物理模型是独立纯函数，签名 `(x: np.ndarray, **params) -> np.ndarray`
- 不包含拟合逻辑，不调用 lmfit
- **禁止**：在模型函数中调用任何 optimizer

### 2. 拟合分发
- 按实验类型提供独立 `fit_*()` 函数（`fit_t1`, `fit_spectro` 等），每个带专属参数
- 所有 `fit_*()` 内部通过 `_auto_fit()` 做列选择 + 模型分发，支持 `x_col`/`y_col` 覆盖
- 底层 `fit()` 作为手动回退入口
- **禁止**：用一个 `fit_experiment(exp_type=...)` 函数通过字符串参数分发所有实验类型

### 3. 拟合与持久化解耦
- `FitResult` 是纯内存对象，不自动写入文件
- 用户通过 `ChipState.add_*()` 手动控制哪些结果进入 `chip_state.json`
- 需复现时重新对原始数据运行拟合程序
- **禁止**：拟合模块自动持久化拟合结果

### 4. 芯片拓扑
- 拓扑用 `ChipTopology` 描述，可自定义任意布局
- 缺失比特用 `None` 占位
- 比特间连接（耦合器）作为可选层叠加
- **禁止**：在绘图代码中硬编码比特坐标或 5×5 假设

### 5. 参数状态
- 所有参数（T1/T2*/驱动效率/读取保真度）标注测量时的比特频率
- f01 存 min/max 范围（来自 f01 dispersion 拟合）
- 同类型多值保留全部历史，报告时按时间戳取最新
- **禁止**：用标量存参数值而不标注测量条件

## 与 Claude Code 协作约定

- 对话以中文为主
- 实现前先给出 API 设计草稿（函数签名 + 返回类型），简短确认后再写实现
- 拟合模型的新增必须附带——一个对应测试用例（用已知参数的合成数据验证拟合能恢复参数）
- 不确定的物理/领域知识标记 `TODO(DOMAIN)`，不猜测
- Notebook 只用于探索和可视化结果，核心逻辑必须放在 `exp_toolkit` 包中（可复用、可测试）
- 当用户说"supervisor 模式"或"你来监督"时，切换为审查者角色：不主动写实现代码，对照 `docs/requirements.md` 检查 API 一致性、边界情况、架构约束违反，推演设计决策的后果
- 每个 Phase 完成后必须产出：`docs/designs/phase-N-design.md` + `docs/reports/phase-N-report.md` + 更新 `docs/TASK.md` + 更新本文件"当前阶段"
- 新会话开始前必须阅读 `docs/requirements.md` 和 `docs/TASK.md`
- 文档产出前先读 `docs/README.md` 确认命名和位置规范

## 当前阶段

- [x] 需求讨论完成 → 详见 `docs/requirements.md`
- [x] 阶段 1：数据 IO + 基础拟合（T1/Lorentzian/DecayingSinusoid + 拟合引擎）
- [x] 阶段 2：芯片拓扑可视化（ChipTopology + ChipArtist） + State 模块
- [x] 阶段 3：HTML 报告生成 + 读取保真度计算
- [x] 阶段 4：更多拟合模型（fit_ramsey/fit_rabi/fit_rb）+ experiment_types.yaml 调度 + #002 P2-2 修复
- [x] 阶段 5：芯片拓扑增强 + State 扩展（extras）+ 报告改进
- [x] 阶段 6：报告增强 + 多图拓扑 + Extras 可视化
- [x] 阶段 7：chip_state.json 手动编辑支持
- [x] 阶段 8：Drive Efficiency 修正 + 列宽/表头修复
- [x] 阶段 9：良率数据集成 + 报告优化
- [x] 阶段 10：Chip Yield 固定渲染 + None 态支持
- [x] 阶段 11：Coherence 按频率分组 + DriveEntry.product 计算属性化

> ⚠️ 实现前请先阅读 `docs/requirements.md` 和 `docs/TASK.md`，前者包含完整的设计规格，后者追踪当前进度和关键决策。
