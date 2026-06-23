# Git LFS 实操指南：实验数据从采集到回归测试

> **前置**：开发电脑和实验电脑均已安装 Git LFS（`git lfs install`）。
> GitHub 免费 LFS 配额：1 GB 存储 + 1 GB 带宽/月（超出需购买）。

---

## 1. 概念区分

在开始之前，理解三种数据的不同位置和用途：

```
实验电脑                              开发电脑
┌─────────────────────┐              ┌──────────────────────────────┐
│ D:/ExperimentData/   │              │ ExpToolKit/                   │
│ ├── 00812/           │  筛选样本    │ ├── tests/regression/data/    │
│ │   ├── *.csv        │────────────→│ │   ├── 00812/   ← Git LFS   │
│ │   ├── *.ini        │  Git LFS    │ │   │   ├── *.csv              │
│ │   └── *.json       │             │ │   │   ├── *.ini              │
│ ├── 00747/           │             │ │   │   └── *.json             │
│ └── ...              │             │ │   └── 00747/                 │
└─────────────────────┘              │ ├── snapshots/   ← git tracked│
                                     │ │   ├── 00747_T1.json         │
       实验原始数据                   │ │   └── 00812_T1.json         │
       (不在 git 中)                  │ └── test_snapshot.py           │
                                     └──────────────────────────────┘

                                          回归测试数据 + 快照
                                          (Git LFS + git tracked)
```

| 数据层级 | 位置 | 存储方式 | 用途 |
|---------|------|---------|------|
| 实验原始数据 | 实验电脑 `D:/ExperimentData/` | 不在 git | 日常实验记录 |
| 回归测试数据 | 开发电脑 `tests/regression/data/` | Git LFS | 回归测试输入 |
| 快照文件 | 开发电脑 `tests/regression/snapshots/` | 普通 git | 回归测试期望值 |

---

## 2. 初始配置（仅一次）

### 2.1 两台电脑都安装 Git LFS

```bash
# 下载安装：https://git-lfs.com/
# 安装后初始化（每台电脑一次）：
git lfs install
# 输出：Git LFS initialized.
```

### 2.2 确认 .gitattributes 已生效

在开发电脑上（本项目已完成此配置）：

```bash
cat .gitattributes
# 应输出：
# tests/regression/data/**/*.csv filter=lfs diff=lfs merge=lfs -text
# tests/regression/data/**/*.ini filter=lfs diff=lfs merge=lfs -text
# tests/regression/data/**/*.json filter=lfs diff=lfs merge=lfs -text
```

### 2.3 实验电脑配置 Git remote

```bash
# 在实验电脑上，ExpToolKit 仓库内：
git remote -v
# 应显示：origin  https://github.com/Feynmstein/ExpToolKit.git

# 如果未配置（首次 clone 后自动配置），跳过此步
```

---

## 3. 数据同步工作流

### 场景 A：同步问题数据（bug 复现）

**背景**：实验电脑上 Q03 的 T1 拟合失败（REQ-2026-0623-001），需要把相关数据发给开发电脑复现。

#### 步骤 1：在实验电脑上筛选数据

```bash
# 将需要同步的数据复制到回归测试目录
# 源：实验原始数据目录（项目外）
# 目标：仓库内的回归测试数据目录

SOURCE="D:/ExperimentData/00812 - T1_ground, Q03"
DEST="tests/regression/data/00812"

mkdir -p "$DEST"
cp "$SOURCE/"*.csv "$DEST/"
cp "$SOURCE/"*.ini "$DEST/"
cp "$SOURCE/"*parameters*.json "$DEST/"
```

#### 步骤 2：提交到 Git LFS

```bash
# 在实验电脑的 ExpToolKit 仓库内
git add tests/regression/data/00812/
git status
# 应显示 LFS 跟踪的文件（csv/ini/json）前面有 "LFS" 标记

git commit -m "data: add 00812 T1 Q03 sample for REQ-2026-0623-001"
git push origin master
```

> **注意**：实验电脑上 git push 需要 Claude Code 权限允许，或由人工执行。
> 如果 Claude Code 被配置为 deny git push，请在终端中手动运行 push。

#### 步骤 3：在开发电脑上拉取

```bash
# 在开发电脑上
git pull origin master
git lfs pull
# 验证文件已下载（不是指针文件）
ls -la tests/regression/data/00812/
# CSV 文件应该有实际大小（几十 KB 到几 MB），不是 130 字节
```

#### 步骤 4：生成回归快照

```bash
# 在开发电脑上，用拉取到的数据跑拟合，生成期望快照
python -c "
from pathlib import Path
import json
from exp_toolkit.io import load_experiment
from exp_toolkit.fitting import fit_t1

exp_dir = Path('tests/regression/data/00812')
csv_path = next(exp_dir.glob('*.csv'))
exp = load_experiment(str(csv_path))
result = fit_t1(exp)

snapshot = {
    'tau': result.params['tau'],
    'error_tau': result.errors.get('tau'),
    'toolkit_version': '0.1.0',
    'qubit': exp.active_qubit,
}
snapshot_dir = Path('tests/regression/snapshots')
snapshot_dir.mkdir(exist_ok=True)
json.dump(snapshot, open(snapshot_dir / '00812_T1.json', 'w'), indent=2)
print(f'Snapshot saved: tau={snapshot[\"tau\"]:.1f} +/- {snapshot[\"error_tau\"]:.1f}')
"
```

#### 步骤 5：提交快照 + 跑回归测试

```bash
git add tests/regression/snapshots/00812_T1.json
git commit -m "test: add regression snapshot for 00812 T1 Q03"
pytest tests/regression/ -v
```

---

### 场景 B：批量同步代表性样本（发布前）

**背景**：版本发布前，从实验电脑的多个实验中各取 1-2 个代表性样本，确保新版不改坏旧结果。

```bash
# 在实验电脑上，批量复制
# 选取 5-10 个代表性实验（覆盖 T1/T2*/Rabi/Ramsey/Spectro）
EXPERIMENTS=(
  "00747 - T1_ground, Q16"
  "00732 - spectro, Q15"
  "00023 - spectro, Q07"
  # ... 按需添加
)

for EXP in "${EXPERIMENTS[@]}"; do
  EXP_ID=$(echo "$EXP" | sed 's/ .*//')
  mkdir -p "tests/regression/data/$EXP_ID"
  cp "D:/ExperimentData/$EXP/"*.csv "tests/regression/data/$EXP_ID/"
  cp "D:/ExperimentData/$EXP/"*.ini "tests/regression/data/$EXP_ID/"
  cp "D:/ExperimentData/$EXP/"*parameters*.json "tests/regression/data/$EXP_ID/"
done

git add tests/regression/data/
git commit -m "data: sync representative samples for v0.2.0 regression testing"
git push origin master
```

---

## 4. 常见问题

### Q1: `git lfs pull` 后文件只有 130 字节？

```bash
# 检查是否为 LFS 指针文件
head -c 200 tests/regression/data/00812/some_file.csv
# 如果输出类似 "version https://git-lfs.github.com/spec/v1" → 是指针
# 说明 LFS 没有正确拉取

# 解决：
git lfs install --force
git lfs pull
```

### Q2: 不小心把大文件用普通 git 提交了？

```bash
# 1. 先配置 LFS 追踪
git lfs track "tests/regression/data/**/*.csv"

# 2. 迁移已有文件到 LFS
git lfs migrate import --include="tests/regression/data/**/*.csv"
git push --force origin master
```

### Q3: GitHub LFS 配额超了怎么办？

| 方案 | 说明 |
|------|------|
| 购买更多额度 | GitHub → Settings → Billing → Git LFS Data |
| 清理旧版本 | `git lfs prune` 删除本地缓存 |
| 减少同步的数据量 | 只同步问题数据和版本发布快照数据，不批量同步 |
| 改用 NAS | 大量数据走 NAS/移动硬盘，Git LFS 仅用于关键样本 |

### Q4: 实验电脑没有 Git LFS 怎么办？

如果实验电脑无法安装 Git LFS（例如受 IT 策略限制），走 NAS/移动硬盘中转：

```bash
# 实验电脑 → NAS/移动硬盘
cp -r D:/ExperimentData/00812/ N:/ExpToolKit-sync/00812/

# 开发电脑 ← NAS/移动硬盘
cp -r N:/ExpToolKit-sync/00812/ tests/regression/data/00812/

# 然后在开发电脑上用 Git LFS 提交
cd ExpToolKit
git add tests/regression/data/00812/
git commit -m "data: add 00812 via NAS sync"
git push origin master
```

---

## 5. 快速参考

```bash
# --- 实验电脑 ---
# 筛选数据 → 复制 → 提交 → 推送
cp -r D:/ExperimentData/<exp_id>/ tests/regression/data/<exp_id>/
git add tests/regression/data/<exp_id>/
git commit -m "data: add <exp_id> for <reason>"
git push origin master

# --- 开发电脑 ---
# 拉取 → 跑回归 → 提交快照
git pull origin master && git lfs pull
python scripts/generate_snapshots.py   # 或手动跑拟合
pytest tests/regression/ -v
git add tests/regression/snapshots/ && git commit -m "test: update snapshots"
git push origin master
```

---

> **相关文档**：
> - 部署流程：[docs/deployment-guide.md](../deployment-guide.md)
> - 快照测试：`tests/regression/test_snapshot.py`
> - LFS 官方文档：https://git-lfs.com/
