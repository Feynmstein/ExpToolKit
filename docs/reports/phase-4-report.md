# Phase 4 工作报告 — 更多拟合模型 + 实验类型调度

**报告日期**：2026-06-18  
**执行会话**：2026-06-18（同日完成）  
**总耗时代码量**：~250 行核心 + 380 行测试  
**最终测试**：197 passed / 197 collected（累计 Phase 1+2+3+4）

---

## 一、交付物清单

### 1.1 新增模型 (`models.py`)

| 模型 | 公式 | 参数 | 场景 |
|------|------|------|------|
| `rb_exp` | A·p^N + B | amplitude, p, offset | 随机基准测试 (RB) |

Rabi 复用已有 `decaying_sinusoid`（数学形式相同）。

### 1.2 新增猜测器 (`guessers.py`)

| 猜测器 | 策略 |
|--------|------|
| `guess_rb_exp` | log-linear fit 估计 p，y[0]-y[-1] 估计 amplitude，y[-1] 估计 offset |

### 1.3 新实验拟合函数

| 函数 | 文件 | 默认模型 | 提取参数 |
|------|------|---------|---------|
| `fit_ramsey(exp)` | `experiments/ramsey.py` | DecayingSinusoid | T2* (=tau), Δf (=frequency) |
| `fit_rabi(exp, *, drive_var)` | `experiments/rabi.py` | DecayingSinusoid | Ω (=frequency), π-pulse = 1/(2Ω) |
| `fit_rb(exp)` | `experiments/rb.py` | rb_exp | p, F_gate = 1-(1-p)/2 |

### 1.4 实验类型调度 (`experiment_types.yaml` + `_base.py`)

```yaml
# 5 种实验类型的关键词匹配规则
T1:        ["T1", "t1"]
spectro:   ["spectro", "spectroscopy"]
ramsey:    ["ramsey", "T2*", "t2star"]
rabi:      ["rabi"]
rb:        ["RB", "randomized_benchmarking", "benchmarking"]
```

新增函数：
- `infer_experiment_type(title) -> str | None` — 从标题推断类型
- `get_fit_function(exp_type) -> Callable | None` — 获取对应 fit_*()

### 1.5 #002 P2-2 修复 (`spectro.py`)

f01 dispersion 负幅度 Gaussian 边界处理：
- min/max 逻辑已正确处理正/负 amplitude（peak vs dip）
- 新增 guard：Gaussian 拟合外推超过经验数据 ±30% 时回退到经验范围，并发出 Warning

### 1.6 测试 (`tests/test_phase4.py`)

| 测试类 | 用例数 | 覆盖 |
|--------|--------|------|
| `TestRbExpModel` | 5 | 前向计算、p=1、p→0、形状、单调性 |
| `TestGuessRbExp` | 3 | 典型数据猜测、点不足、全NaN |
| `TestFitRamsey` | 6 | T2*恢复、Δf恢复、FitResult类型、参数完整性、列匹配失败、params_hint |
| `TestFitRabi` | 5 | Ω恢复、π脉冲计算、drive_var切换、非法drive_var |
| `TestFitRb` | 6 | p恢复、门保真度、FitResult类型、参数完整性、p范围校验、列匹配失败 |
| `TestExperimentTypeDispatch` | 10 | 5种类型推断、未匹配返回None、大小写不敏感、get_fit_function、roundtrip |
| `TestF01DispersionNegativeAmplitude` | 3 | 正幅度、负幅度dip、偏差过大回退 |

---

## 二、架构合规性

| # | 约定 | 合规 |
|---|------|------|
| 1 | 模型纯函数，不调用 lmfit | ✅ `rb_exp(x, amplitude, p, offset)` |
| 2 | 按实验类型独立 `fit_*()` | ✅ `fit_ramsey`, `fit_rabi`, `fit_rb` 各自独立 |
| — | 禁止 `fit_experiment(exp_type=...)` 分发 | ✅ 自动推断通过 `experiment_types.yaml`，非硬编码 |
| 3 | 拟合与持久化解耦 | ✅ 所有 fit_*() 返回 FitResult，不写文件 |
| — | 类型标注完整 | ✅ 所有新函数有完整类型标注 |
| — | 每模型一测试 | ✅ rb_exp 等有合成数据参数恢复测试 |

---

## 三、已知局限

1. **RB 模型仅支持单比特**：公式 A·p^N+B 假设单比特门。双比特 RB 需扩展。
2. **Rabi 复用 decaying_sinusoid**：数学形式相同，但物理上 Rabi 的 τ 表征驱动退相干（非 T2*）。参数名一致，语义由上下文区分。
3. **实验类型推断依赖 title**：YAML 关键词匹配。若 INI title 命名不规范（如缩写），会返回 None。用户可通过 `params_hint` 手动调用 fit_*()。
4. **2D 拟合未扩展**：`fit_f01_dispersion()` 已支持 2D→1D 切片。通用 2D 拟合（Rabi Chevron 等）留待后续。

---

## 四、累计测试

```
197 passed in 3.79s (+38 Phase 4)
  ├── tests/test_io.py ........... 44  (IO 模块)
  ├── tests/test_fitting.py ...... 36  (拟合模块)
  ├── tests/test_phase2.py ....... 57  (State + 可视化)
  ├── tests/test_phase3.py ....... 22  (IQ 保真度 + HTML 报告)
  └── tests/test_phase4.py ....... 38  (Phase 4 全部)
```

---

---

## 五、审查记录

### 5.1 Phase 4 完成审查（2026-06-18）

> **审查报告**：[`docs/reviews/005-phase4-review.md`](../reviews/005-phase4-review.md)  
> **总体判定**：Phase 4 可以验收。无 P1 阻塞项。1 个 P2（陈旧 YAML 副本）+ 2 个 P3。  
> **#004 P2/P3 修复核验**：5/5 全部通过（T2echo sources、artist.ax、last_updated、math.sqrt(2)、import io）。  
> **#002 遗留修复核验**：P2-2（f01 dispersion 负幅度 + guard）✅、P2-3（YAML 接线）✅。  
> **架构合规**：全部通过。Phase 1–4 累计 197 tests，4 次审查闭环。  

---

> **关联文档**：[[requirements.md]] | [[phase-3-report]] | [[005-phase4-review]](../reviews/005-phase4-review.md)  
> **项目状态**：Phase 1–4 全部完成，骨架完整。
