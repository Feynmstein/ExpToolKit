# Changelog

All notable changes to ExpToolKit will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.1.0] — 2026-06-19

### Added
- **IO 模块**：CSV+INI+JSON 三元组读取，6 数据类 + 4 公共函数
- **拟合模块**：6 个物理模型（ExponentialDecay, DecayingSinusoid, RabiOscillation, Lorentzian, Gaussian, RBExponential）
- **拟合分发**：6 个 `fit_*()` 函数（fit_t1, fit_spectro, fit_f01_dispersion, fit_ramsey, fit_rabi, fit_rb）
- **YAML 调度**：`experiment_types.yaml` 实验类型映射
- **State 模块**：ChipState 参数累积管理，6 个 `add_*()` 方法
- **可视化模块**：ChipTopology + ChipArtist 芯片拓扑绘制，fit_plot 拟合结果图
- **报告模块**：ReportGenerator → 自包含 HTML 芯片级报告
- **读取保真度**：assignment_fidelity() 从 IQ blob 计算
- **良率可视化**：categorical_param 渲染，含 None 态支持
- **Coherence 按频率分组**：CoherenceGroup 数据类

### Tests
- 264 passed / 264 collected（合成数据全覆盖）
- 10 份审查报告（#001–#010），零 P0/P1 阻塞项

---

## [Unreleased]

### Planned
- Layer 1 真实数据回归测试框架
- 生产环境冒烟测试脚本
- 需求卡片收件箱流程启用
