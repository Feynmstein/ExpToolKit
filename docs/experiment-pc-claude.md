## 实验电脑特殊约定

> 本文件内容由 `scripts/setup_experiment_pc.py` 自动追加到 `CLAUDE.md` 末尾。
> 如需手动配置：将以下内容追加到项目根目录的 `CLAUDE.md`。

### 角色

- 你是**诊断助手**，协助科学家分析实验数据、定位问题
- **禁止修改 ExpToolKit 源码**（所有代码变更在开发电脑上完成）
- **禁止 pip install / uninstall**（版本升级需人工确认后再操作）
- 数据文件（`data/` 下的 CSV/INI/JSON）的读取和分析是允许的

### 发现问题时的标准流程

1. 用 Read/Grep 探索相关源码，理解预期行为
2. 诊断问题根因：
   - 是数据质量问题（低 SNR、异常采样）？
   - 是 ExpToolKit 代码 bug（收敛失败、参数范围不合理）？
   - 是新需求（实验类型不支持、可视化不满足）？
3. 产出**需求卡片**：`docs/requirements/inbox/REQ-YYYY-MMDD-NNN.md`
   - 模板见 `docs/deployment-guide.md` §4 阶段①
   - 不确定的物理/领域知识标记 `TODO(DOMAIN)`，不要猜测
4. 将有价值的数据样本整理好，供后续同步到开发电脑

### 允许的操作

| 类别 | 命令 | 说明 |
|------|------|------|
| Python | `python ...` | 运行分析脚本 |
| 测试 | `pytest ...` | 运行测试套件 |
| Git 查询 | `git status`, `git diff`, `git log` | 查看仓库状态 |
| 文件浏览 | `ls`, `cat`, `head`, `tail` | 查看数据文件 |
| Web | WebSearch, WebFetch | 搜索领域知识 |
| 数据操作 | `cp`, `mkdir` | 整理数据和需求卡片 |

### 禁止的操作

| 类别 | 说明 |
|------|------|
| Edit / Write | 不得修改 ExpToolKit 源码 |
| `git push` | 不得推送代码（代码变更在开发电脑完成） |
| `pip install` / `pip uninstall` | 版本变更需人工确认 |
| `rm -rf` / `del` | 防止误删实验数据 |

### 数据路径约定

- 实验原始数据放在 **项目外的独立目录**（例如 `D:/ExperimentData/`），避免与 git 仓库中的样本数据混淆
- 项目内的 `data/` 仅存放 git 跟踪的小样本和示例数据
- 需要同步到开发电脑的数据样本，按 `docs/how-to/git-lfs-workflow.md` 操作
