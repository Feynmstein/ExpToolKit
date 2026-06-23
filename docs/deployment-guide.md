# ExpToolKit 生产部署与需求演进流程

> **版本**：v1（2026-06-23）  
> **受众**：项目维护者、实验科学家  
> **前置阅读**：`docs/requirements.md`、`docs/TASK.md`

---

## 目录

1. [环境划分](#1-环境划分)
2. [Git 分支与版本策略](#2-git-分支与版本策略)
3. [测试分层策略](#3-测试分层策略)
4. [需求演进闭环](#4-需求演进闭环)
5. [Claude Code 角色配置](#5-claude-code-角色配置)
6. [数据流转方案](#6-数据流转方案)
7. [版本发布 Checklist](#7-版本发布-checklist)
8. [应急回滚](#8-应急回滚)

---

## 1. 环境划分

三类环境，职责严格隔离：

```
┌─────────────────────────────────────────────────────────────────┐
│  实验电脑 (Production)                                          │
│  - 稳定版 ExpToolKit（pip install exp-toolkit==x.y.z）          │
│  - Claude Code 角色：诊断+记录，不修改源码                        │
│  - 产生真实实验数据 + chip_state.json                            │
│  - 禁止在此环境修改 ExpToolKit 源码                              │
├─────────────────────────────────────────────────────────────────┤
│  开发电脑 (Development)                                         │
│  - 开发版 ExpToolKit（pip install -e .）                        │
│  - Claude Code 全能力：设计、实现、测试、审查                     │
│  - 从实验电脑同步来的样本数据用于复现和测试                        │
├─────────────────────────────────────────────────────────────────┤
│  数据中转区 (Git LFS / NAS / 移动硬盘)                           │
│  - 实验数据的脱敏副本                                            │
│  - 用于开发环境复现 bug、验证新功能                               │
└─────────────────────────────────────────────────────────────────┘
```

| 环境 | 位置 | 谁操作 | Claude Code 角色 | 能否改源码 |
|------|------|--------|-----------------|-----------|
| 实验电脑 | 实验室 | 科学家 + Claude | 诊断助手 | ❌ 禁止 |
| 开发电脑 | 开发者机器 | 开发者 + Claude | 全能力 | ✅ 允许 |
| 中转区 | NAS/Git LFS | 双方 | — | — |

---

## 2. Git 分支与版本策略

### 2.1 分支模型

```
master (稳定版 — 始终可部署)
  │
  ├── develop (集成开发)
  │     │
  │     ├── feat/new-experiment-type    # 新实验类型支持
  │     ├── fix/t1-convergence          # bug 修复
  │     └── exp/2026-06-23-q16-issue    # 实验中发现的问题
  │
  └── tag: v0.1.0                       # 发布标签
  └── tag: v0.2.0
```

| 分支 | 用途 | 合并到 | 触发条件 |
|------|------|--------|---------|
| `master` | 稳定发布版 | — | release 分支合并 |
| `develop` | 日常开发集成 | `master` (via release) | feature/fix 分支合并 |
| `feat/*` | 新功能开发 | `develop` | 需求评审通过 |
| `fix/*` | bug 修复 | `develop` (cherry-pick to master if urgent) | 生产环境发现 bug |
| `exp/*` | 实验性探索 | 不合并，产出需求卡片 | 实验诊断 |

### 2.2 语义化版本号

与 `chip_state.json` 的可复现性关联：

| 版本 | 含义 | 示例触发 |
|------|------|---------|
| `0.1.x` | 补丁：bug 修复、数据格式兼容变更 | 低 SNR 拟合不收敛修复 |
| `0.x.0` | 小版本：新拟合模型、新可视化功能 | 新增 T2 Echo 支持 |
| `x.0.0` | 大版本：API 不兼容变更、架构重构 | 拟合引擎切换 |

### 2.3 chip_state.json 版本追踪

`ChipState.save()` 必须写入 `"toolkit_version"` 字段：

```json
{
  "chip_id": "5x5-chip-001",
  "toolkit_version": "0.1.0",
  "last_updated": "2026-06-23",
  "qubits": { "...": "..." }
}
```

**原则**："同样的数据 + 同样的 toolkit 版本 = 同样的拟合结果"。  
当怀疑某个历史结果时，用该版本重新跑拟合即可复现。这是科学计算可复现性的底线保障。

---

## 3. 测试分层策略

```
Layer 0: 合成数据测试 (已有)
  ├── 用途：验证公式正确性、参数恢复能力
  ├── 位置：tests/test_*.py
  ├── 运行：每次 commit / push（CI 可跑）
  └── 当前状态：264 passed, 0 regression

Layer 1: 真实数据回归测试 (新增)
  ├── 用途：验证代码变更不破坏已有实验结果
  ├── 位置：tests/regression/
  ├── 数据：从实验电脑同步的代表性样本（5-10 个实验）
  ├── 形式：快照测试（拟合结果与上次版本对比，容差 1%）
  └── 运行：每次 push / 发布前（本地运行，数据不入 git）

Layer 2: 交互式验证脚本 (已有)
  ├── 用途：新功能在真实数据上的首次验证
  ├── 位置：tests/manual/verify_*.py
  └── 运行：开发者手动执行

Layer 3: 生产环境冒烟测试 (新增)
  ├── 用途：部署后确认包可导入、关键函数可运行
  ├── 位置：scripts/smoke_test.py（随包分发）
  └── 运行：pip install 后立即执行
```

### 3.1 Layer 1 快照测试实现

```
tests/regression/
├── data/                    # gitignore — 真实数据样本
│   ├── 00747/               # T1 实验
│   │   ├── 00747 - T1_ground, Q16.csv
│   │   ├── 00747 - T1_ground, Q16.ini
│   │   └── 00747 - parameters.json
│   └── 00023/               # 光谱实验
│       ├── 00023 - spectro, Q07.csv
│       ├── 00023 - spectro, Q07.ini
│       └── 00023 - parameters.json
├── snapshots/               # git tracked — JSON 快照
│   ├── 00747_T1.json        # {"tau": 45.2, "error_tau": 1.3, ...}
│   └── 00023_f01.json       # {"f01_min": 4.2, "f01_max": 4.9, ...}
├── conftest.py              # pytest 配置（skip_if_no_data）
└── test_snapshot.py
```

```python
# tests/regression/test_snapshot.py 草稿
import json
from pathlib import Path
import pytest
from exp_toolkit.io import load_experiment
from exp_toolkit.fitting import fit_t1, fit_spectro, fit_f01_dispersion

DATA_DIR = Path(__file__).parent / "data"
SNAPSHOT_DIR = Path(__file__).parent / "snapshots"

def _require_data(exp_id: str) -> Path:
    exp_dir = DATA_DIR / exp_id
    if not exp_dir.exists():
        pytest.skip(f"真实数据 {exp_id} 未同步到测试环境")
    return exp_dir

@pytest.mark.regression
def test_00747_t1_regression():
    exp_dir = _require_data("00747")
    csv_path = next(exp_dir.glob("*.csv"))
    exp = load_experiment(str(csv_path))
    result = fit_t1(exp)
    snapshot = json.load(open(SNAPSHOT_DIR / "00747_T1.json"))
    tau, tau_err = result.params["tau"], result.errors["tau"]
    # 拟合结果与快照的偏差在 3σ + 1% 容差内
    assert abs(tau - snapshot["tau"]) < max(3 * tau_err, 0.01 * snapshot["tau"])

@pytest.mark.regression
def test_00023_f01_regression():
    exp_dir = _require_data("00023")
    csv_path = next(exp_dir.glob("*.csv"))
    exp = load_experiment(str(csv_path))
    result = fit_f01_dispersion(exp)
    snapshot = json.load(open(SNAPSHOT_DIR / "00023_f01.json"))
    assert abs(result.f01_min - snapshot["f01_min"]) < 0.01
    assert abs(result.f01_max - snapshot["f01_max"]) < 0.01
```

### 3.2 Layer 3 冒烟测试

```python
# scripts/smoke_test.py — 部署后验证，只用标准库 + exp_toolkit
"""ExpToolKit 冒烟测试：确认包安装正确、关键模块可导入、基本功能可用。"""
import sys

def test_imports():
    import exp_toolkit
    from exp_toolkit.io import load_experiment
    from exp_toolkit.fitting import fit_t1, fit, models
    from exp_toolkit.state import ChipState
    from exp_toolkit.visualization import ChipTopology
    from exp_toolkit.report import ReportGenerator
    print("[PASS] 全部模块导入成功")

def test_synthetic_fit():
    import numpy as np
    from exp_toolkit.fitting import fit, models
    x = np.linspace(0, 100, 50)
    y = 0.8 * np.exp(-x / 40.0) + 0.2 + np.random.default_rng(0).normal(0, 0.01, 50)
    result = fit(x, y, models.ExponentialDecay)
    assert result.success, f"合成数据拟合失败: {result.message}"
    assert 30 < result.params["tau"] < 55, f"tau 超出合理范围: {result.params['tau']}"
    print(f"[PASS] 合成 T1 拟合成功: tau={result.params['tau']:.1f}±{result.errors['tau']:.1f}")

if __name__ == "__main__":
    test_imports()
    test_synthetic_fit()
    print("\n冒烟测试全部通过 ✅")
```

---

## 4. 需求演进闭环

从"在实验中发现需求"到"功能上线"的完整流程，六个阶段：

```
┌─────────────────────────────────────────────────────────────────────┐
│                        需求演进闭环                                  │
│                                                                     │
│  实验电脑 (Production)                开发电脑 (Development)         │
│  ┌──────────────────┐                ┌──────────────────┐          │
│  │ ① 运行实验        │                │ ③ 需求评审       │          │
│  │ ② 数据分析        │   需求卡片     │ ④ Plan 设计     │          │
│  │ ③ Claude 诊断     │──────────────→│ ⑤ 编码+测试     │          │
│  │ ④ 产出需求卡片    │   (Git/NAS)    │ ⑥ Code Review   │          │
│  │                   │                │ ⑦ 版本发布       │          │
│  └──────────────────┘                └────────┬─────────┘          │
│          ▲                                    │                     │
│          │        pip install v0.2.0          │                     │
│          └────────────────────────────────────┘                     │
│  ⑧ 冒烟测试                                                        │
│  ⑨ 用原始数据复现验证                                               │
│  ⑩ 确认需求关闭                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 阶段 ①：需求捕获（实验电脑）

**触发条件**：
- 拟合失败或不收敛
- 数据格式与预期不符
- 需要新的分析功能
- 可视化效果不满足需求
- 性能问题（大数据集拟合太慢）

**产物**：需求卡片（统一 Markdown 格式），存放在 `docs/requirements/inbox/`。

**需求卡片模板**：

```markdown
---
id: REQ-YYYY-MMDD-NNN
title: <一句话描述>
source: <实验电脑 | 开发电脑>
date: YYYY-MM-DD
priority: high | medium | low
type: bug | feature | enhancement
tags: [qubit, experiment_type, module]
---

## 现象（bug）/ 动机（feature）

<描述发生了什么，或为什么需要这个功能>

## 复现条件（bug）/ 预期行为（feature）

<如何复现该问题，或新功能的行为描述>

## 涉及数据

| 文件 | 路径 |
|------|------|
| CSV | `data/00812 - T1_ground, Q03.csv` |
| INI | `data/00812 - T1_ground, Q03.ini` |
| JSON | `data/00812 - parameters.json` |

## 附件

- 截图/日志/错误消息

## 初步诊断（Claude Code 产出）

<Claude Code 的初步分析结论，不确定的标 TODO(DOMAIN)>
```

**示例**：

```markdown
---
id: REQ-2026-0623-001
title: fit_t1 对 Q03 低信噪比数据不收敛
source: 实验电脑
date: 2026-06-23
priority: high
type: bug
tags: [Q03, T1, fitting]
---

## 现象

对 Q03 的 T1 实验（00812）运行 fit_t1()，返回 `success=False`，
`red_chi2=847`，拟合曲线明显偏离数据。

## 复现条件

```python
exp = load_experiment("00812 - T1_ground, Q03.csv")
result = fit_t1(exp)  # success=False
```

## 涉及数据

| 文件 | 路径 |
|------|------|
| CSV | `00812 - T1_ground, Q03.csv` |
| INI | `00812 - T1_ground, Q03.ini` |

## 初步诊断

Q03 的 T1 特别短（视觉估计 ~3 μs），信号衰减很快，
最后几个数据点完全在噪声中。猜测器 `guess_exp_decay()` 
用 x_range/3 估计 τ ≈ 33 μs，与实际值相差 ~10×，
导致 lmfit 收敛到局部极小值。
```

### 阶段 ②：需求评审与排序（开发电脑）

**产出**：更新 `docs/TASK.md` 的需求队列：

```markdown
## 需求队列

| ID | 标题 | 优先级 | 目标版本 | 状态 |
|----|------|--------|---------|------|
| REQ-001 | Q03 低 SNR T1 不收敛 | high | 0.1.1 | todo |
| REQ-002 | 支持 T2 Echo 实验 | medium | 0.2.0 | todo |
| REQ-003 | chip_state 增加 coupler 参数 | low | backlog | todo |
```

**评审维度**：

| 维度 | 问题 |
|------|------|
| 影响范围 | 修改多少模块？是否破坏向后兼容？ |
| 数据依赖性 | 是否需要真实数据验证？数据是否已同步？ |
| 紧迫性 | 是否阻塞实验进程？ |
| 实现复杂度 | 预计多少代码改动？几天完成？ |

### 阶段 ③：设计（开发电脑）

每个需求（或批次）在开发电脑上走 Plan 模式：

1. 阅读需求卡片 + 相关源码
2. 产出 `docs/designs/req-NNN-design.md`（精简版，≤ 100 行）
3. 确认 API 变更影响范围
4. 列出测试计划

### 阶段 ④：实现 + 测试（开发电脑）

遵循项目现有约定：
- 先写测试（合成数据 / 同步来的真实数据样本）
- 实现代码
- `pytest` 全量通过，零回归
- `mypy --strict` 无新增错误
- Claude Code supervisor 模式审查

### 阶段 ⑤：生产验证（实验电脑）

```
# 在实验电脑上执行
pip install --upgrade exp-toolkit==0.1.1
python scripts/smoke_test.py

# 用之前出问题的数据重新运行
python -c "
from exp_toolkit.io import load_experiment
from exp_toolkit.fitting import fit_t1
exp = load_experiment('00812 - T1_ground, Q03.csv')
result = fit_t1(exp)
print(f'T1 = {result.params[\"tau\"]:.1f} ± {result.errors[\"tau\"]:.1f}, success={result.success}')
"
```

**验证标准**：
- 冒烟测试通过
- 原始问题数据的拟合结果符合预期
- 已有 `chip_state.json` 可正常加载

### 阶段 ⑥：闭环归档

- 需求卡片从 `inbox/` 移到 `docs/requirements/done/REQ-*.md`
- 更新 `docs/TASK.md`（需求队列状态变更）
- 如有架构级影响，更新 `docs/requirements.md`
- Git commit 关联需求 ID（commit message: `fix: REQ-2026-0623-001`）
- 打版本 tag

---

## 5. Claude Code 角色配置

### 5.1 实验电脑（诊断角色）

`.claude/settings.local.json`：

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Grep",
      "Glob",
      "WebSearch",
      "WebFetch"
    ],
    "deny": [
      "Edit",
      "Write",
      "Bash(git push*)",
      "Bash(pip install*)",
      "Bash(rm *)",
      "Bash(del *)"
    ],
    "ask": [
      "Bash(python*)",
      "Bash(pytest*)",
      "Bash(git status)",
      "Bash(git diff*)",
      "Bash(git log*)"
    ]
  }
}
```

`CLAUDE.md` 追加内容：

```markdown
## 实验电脑特殊约定

### 角色
- 你是诊断助手，协助科学家分析实验数据、定位问题
- **禁止修改 ExpToolKit 源码**（所有代码变更在开发电脑上完成）
- **禁止 pip install / uninstall**（版本升级需人工确认）

### 发现问题时的流程
1. 用 Read/Grep 探索相关代码，理解预期行为
2. 诊断问题根因（是数据问题还是代码 bug）
3. 产出需求卡片：`docs/requirements/inbox/REQ-YYYY-MMDD-NNN.md`
4. 如有不确定的物理知识，标记 `TODO(DOMAIN)`

### 需求卡片格式
见 `docs/deployment-guide.md` §4 阶段① 的模板。

### 允许的操作
- 运行 Python 分析脚本（Bash(python...)）
- 运行测试（Bash(pytest...)）
- 查看 git 状态/日志/diff
- Web 搜索领域知识
```

### 5.2 开发电脑（全能力）

保持现有 `CLAUDE.md` 和权限配置不变。开发电脑上的 Claude Code 拥有完整编辑、测试、Git 操作权限，负责：
- 设计新功能的 Plan
- 实现代码
- 编写和运行测试
- 代码审查（supervisor 模式）
- 版本发布准备

---

## 6. 数据流转方案

### 6.1 传输方式（按推荐度排序）

| 方式 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| **Git LFS**（推荐） | 数据 < 1 GB | 版本追踪、增量传输、与代码关联 | 需配置 LFS 服务端 |
| NAS 共享目录 | 实验室内网 | 零配置传输 | 需网络、无版本 |
| 移动硬盘 + rsync | 离线/首次传输 | 简单可靠 | 手动操作、易遗漏 |

### 6.2 数据筛选原则

**不需要同步所有原始数据**。只同步：

| 数据类型 | 用途 | 同步频率 | 数量 |
|---------|------|---------|------|
| 代表性样本 | 回归测试快照 | 版本发布前 | 5-10 个实验 |
| 问题数据 | bug 复现 | 按需 | 每个 bug 1-3 个 |
| 新实验类型样本 | 新 feature 开发 | 开发前 | 1-2 个实验 |

### 6.3 Git LFS 配置

```bash
# 在开发电脑上（首次）
git lfs track "tests/regression/data/**/*.csv"
git lfs track "tests/regression/data/**/*.ini"
git lfs track "tests/regression/data/**/*.json"
git add .gitattributes
git commit -m "chore: configure Git LFS for regression test data"

# 实验电脑 → 开发电脑（同步特定数据）
# 实验电脑上：
cd /path/to/experiment/data
git add 00812*/
git commit -m "data: add 00812 T1 Q03 for bug REQ-001"
git push

# 开发电脑上：
git pull
git lfs pull
```

---

## 7. 版本发布 Checklist

### 发布 vX.Y.Z

#### 代码质量

- [ ] `pytest` 全量通过（零回归）
- [ ] `mypy --strict` 无新增错误
- [ ] Claude Code 审查通过（无 P0/P1 阻塞项）
- [ ] Layer 1 快照回归测试通过（如有真实数据）

#### 文档

- [ ] `CHANGELOG.md` 更新（记录本次所有变更）
- [ ] `docs/TASK.md` 更新（需求队列状态、当前版本）
- [ ] `CLAUDE.md` "当前阶段" 更新
- [ ] 如有 API 变更，`docs/requirements.md` 相关章节更新

#### 兼容性

- [ ] 旧版 `chip_state.json` 可正常加载（`ChipState.load()` 不报错）
- [ ] 快照测试结果与上一版本一致（差异在容差内）
- [ ] 公开 API 签名无破坏性变更（或已在 CHANGELOG 标注）

#### 版本标签

```bash
git tag -a v0.2.0 -m "feat: add T2 Echo support; fix low-SNR T1 convergence"
git push origin v0.2.0
```

#### 部署

```bash
# 在实验电脑上
pip install --upgrade exp-toolkit==0.2.0
python scripts/smoke_test.py
```

#### 验证

- [ ] 冒烟测试通过
- [ ] 用上次验证的数据重新运行，结果在可接受范围内
- [ ] 相关需求卡片的原始问题数据复测通过

---

## 8. 应急回滚

### 回滚流程

```bash
# 步骤 1：确认上一版本可用
git tag -l "v*"  # 确认 tag 存在

# 步骤 2：实验电脑回滚
pip install exp-toolkit==0.1.0  # 替换为上一稳定版本

# 步骤 3：验证
python scripts/smoke_test.py

# 步骤 4：用上次正常的数据验证
python -c "
from exp_toolkit.io import load_experiment
from exp_toolkit.fitting import fit_t1
exp = load_experiment('data/00747 - T1_ground, Q16.csv')
result = fit_t1(exp)
print(f'T1 = {result.params[\"tau\"]:.1f} ± {result.errors[\"tau\"]:.1f}')
"
```

### 回滚决策标准

| 情况 | 操作 |
|------|------|
| 冒烟测试失败 | **立即回滚**，排查后打补丁 |
| 拟合结果与上一版本差异 > 5% | 评估是修复还是回归；如果是回归，回滚 |
| chip_state.json 加载失败 | **立即回滚**，检查序列化兼容性 |
| 非关键功能异常 | 不阻塞回滚/不回滚，记录 bug 排入下版本 |

### 预防措施

- 每次发布前确认上一个版本的 tag 存在且可 `pip install`
- `chip_state.json` 不原地覆盖，每次 `save()` 保留备份：`chip_state_2026-06-23.json`
- 实验电脑上保留最近 3 个版本的 wheel：`pip download exp-toolkit==0.1.0 -d backups/`

---

## 附录 A：目录结构（新增文件）

```
ExpToolKit/
├── CHANGELOG.md                          # 新增：版本变更记录
├── scripts/
│   └── smoke_test.py                     # 新增：生产环境冒烟测试
├── tests/
│   └── regression/                       # 新增：真实数据回归测试
│       ├── conftest.py
│       ├── test_snapshot.py
│       ├── data/                         # gitignore + Git LFS
│       │   ├── 00747/
│       │   └── 00023/
│       └── snapshots/                    # git tracked
│           ├── 00747_T1.json
│           └── 00023_f01.json
├── docs/
│   ├── deployment-guide.md               # 本文件
│   └── requirements/
│       ├── inbox/                        # 待处理需求卡片
│       │   └── .gitkeep
│       └── done/                         # 已闭环需求卡片
│           └── .gitkeep
└── .claude/
    └── settings.local.json               # 实验电脑用：限制权限
```

---

## 附录 B：首个生产部署步骤

按以下顺序初始化实验电脑环境：

```bash
# 1. 安装 ExpToolKit
pip install exp-toolkit==0.1.0

# 2. 运行冒烟测试
python scripts/smoke_test.py

# 3. 配置 Claude Code（实验电脑角色）
# 将 .claude/settings.local.json 写入上述限制配置
# 将 CLI.md 末尾追加实验电脑特殊约定

# 4. 初始化需求卡片目录
mkdir -p docs/requirements/inbox docs/requirements/done

# 5. 首次运行：用已有数据跑一遍流程
python -c "
from exp_toolkit.io import load_experiment
from exp_toolkit.fitting import fit_t1
from exp_toolkit.state import ChipState
from exp_toolkit.visualization import ChipTopology
from exp_toolkit.report import ReportGenerator

# 加载一个已知实验
exp = load_experiment('data/00747 - T1_ground, Q16.csv')
result = fit_t1(exp)
print(f'T1 = {result.params[\"tau\"]:.1f} ± {result.errors[\"tau\"]:.1f} μs')

# 初始化状态
topo = ChipTopology.from_grid(5, 5)
state = ChipState.new('5x5-chip-001', topo)
state.add_T1('Q16', result.params['tau'], result.errors['tau'],
             freq_GHz=exp.params.qubits['Q16'].f01, source_exp='00747')
state.save('chip_state.json')

# 生成报告
report = ReportGenerator(state, topo)
report.generate('report.html')
print('Done — 打开 report.html 确认')
"
```

---

> **本文档维护约定**：
> - 流程变更时更新本文档，同步更新 `docs/README.md` 导航
> - 版本号与 ExpToolKit 版本号**独立**——文档有自己的修订版本
> - 附录内容（示例脚本、JSON 配置）在发布前验证可运行
