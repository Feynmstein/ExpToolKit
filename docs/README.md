# ExpToolKit 文档导航

> 新会话第一件事：读 `requirements.md` + `TASK.md`。本文件帮你找到其余文档。

## 目录结构

```
docs/
├── README.md              # 本文件 — 导航索引
├── requirements.md        # 架构级设计文档（需求+API+约束）
├── TASK.md                # 当前进度 + 关键决策追踪
├── designs/               # 各阶段设计文档（Plan 产出）
│   └── phase-N-design.md
├── reports/               # 各阶段完成报告（Build 结束后产出）
│   └── phase-N-report.md
├── notes/                 # 实现笔记（可选，有值得记录的偏差时产出）
│   └── phase-N-notes.md
└── reviews/               # 审查报告（Supervisor 产出）
    └── NNN-phaseN-review.md
```

## 阅读顺序

| 场景 | 先读 | 再读 |
|------|------|------|
| **新会话接手** | `requirements.md` | `TASK.md` |
| **了解某个 Phase 的设计** | `designs/phase-N-design.md` | `reports/phase-N-report.md` |
| **了解当前进度** | `TASK.md` | `CLAUDE.md` §当前阶段 |
| **质量审查** | `reviews/` 目录（按编号从新到旧） | — |

## 文档约定

| 规则 | 说明 |
|------|------|
| 命名 | `phase-N-design.md` / `phase-N-report.md`，N 为阶段号 |
| 设计文档 ≤ 150 行 | Plan 阶段产出，含需求覆盖、方案设计、边界情况 |
| 报告 ≤ 150 行 | Build 完成后产出，含交付物、架构合规、测试、取舍、**文档合规自检** |
| 笔记按需产出 | 仅当实现与设计有明显偏差时写 `notes/phase-N-notes.md` |
| 更新 TASK.md | 每个 Phase 完成后同步更新 |

## 缺失文档

| Phase | 缺失 | 说明 |
|-------|------|------|
| Phase 7 | `reports/phase-7-report.md` ⚠️ | 有设计文档，无完成报告（历史遗留） |
| Phase 9 | `designs/phase-9-design.md` ⚠️ | 有完成报告，无设计文档（历史遗留） |

> 后续 Phase 不应产生新的缺失项。每个 Phase 完成后用"文档合规自检"确认。
