<!-- Purpose: Document change history title -->
# 变更记录（CHANGELOG）
<!-- Purpose: Provide bilingual introduction -->
本文件记录 ASRProgram 的主要迭代里程碑，同时提供英文摘要方便国际贡献者参考。
This document captures the milestone releases of ASRProgram with concise English summaries for global collaborators.

<!-- Purpose: Note semantic versioning policy -->
> 版本号遵循语义化版本控制（Semantic Versioning），格式为 `主版本.次版本.修订版本`。

<!-- Purpose: Introduce v1.0.0 section -->
## v1.0.0（2025-10-26）
<!-- Purpose: Summarize release importance -->
- <!-- Purpose: Milestone note -->🎉 首个稳定版发布，流水线、配置与测试体系全面成熟。
- <!-- Purpose: Word timestamp feature -->支持词级时间戳 JSON 输出，涵盖置信度与哈希信息。
- <!-- Purpose: CLI + profiles -->整合 CLI、分层配置与 Profile 体系，实现一键批处理。
- <!-- Purpose: Logging -->日志系统支持 `human` / `jsonl` 模式，可输出指标文件。
- <!-- Purpose: Schema -->新增 JSON Schema 校验及 Manifest 审计，确保结果可追踪。
- <!-- Purpose: CI -->完善单元测试、冒烟脚本与轻量 CI 工作流，为发布打下基础。

<!-- Purpose: Introduce v0.9.0 section -->
## v0.9.0
<!-- Purpose: Summaries for v0.9.0 -->
- 引入结构化日志、指标采集与性能 Profiler，增强可观测性。
- 补全 TraceID 贯穿机制，为跨任务调试提供一致上下文。

<!-- Purpose: Introduce v0.8.0 section -->
## v0.8.0
<!-- Purpose: Summaries for v0.8.0 -->
- 完成分层配置与 Profile 系统的初版，实现 YAML/CLI 联动。
- 提供后端注册表机制，简化 faster-whisper 与 whisper.cpp 的切换。

<!-- Purpose: Introduce v0.7.0 section -->
## v0.7.0
<!-- Purpose: Summaries for v0.7.0 -->
- 重构 CLI 参数解析，增加批处理、并发与输出目录控制。
- 新增输入 Manifest 支持，记录任务状态与错误分类。

<!-- Purpose: Introduce v0.6.0 section -->
## v0.6.0
<!-- Purpose: Summaries for v0.6.0 -->
- 加入文件锁、断点续跑与临时文件清理策略，提升稳健性。
- 提供音频哈希校验，避免旧结果污染新转写。

<!-- Purpose: Introduce v0.5.0 section -->
## v0.5.0
<!-- Purpose: Summaries for v0.5.0 -->
- 发布安装脚本 `setup.sh/ps1`，支持虚拟环境与依赖安装。
- 初步整合 ffmpeg 探测逻辑，为后续音频预处理做准备。

<!-- Purpose: Introduce v0.4.0 section -->
## v0.4.0
<!-- Purpose: Summaries for v0.4.0 -->
- 添加冒烟测试脚本与基础单元测试，确保核心流程可回归。
- 构建占位后端模拟推理，验证流水线落盘正确性。

<!-- Purpose: Introduce v0.3.0 section -->
## v0.3.0
<!-- Purpose: Summaries for v0.3.0 -->
- 支持批量扫描输入目录并生成词级、段级 JSON 产物。
- 引入 Manifest 模板，为后续断点续跑打基础。

<!-- Purpose: Introduce v0.2.0 section -->
## v0.2.0
<!-- Purpose: Summaries for v0.2.0 -->
- 构建基础 CLI 骨架与配置系统雏形。
- 增加环境自检脚本，验证依赖与解释器版本。

<!-- Purpose: Introduce v0.1.0 section -->
## v0.1.0
<!-- Purpose: Summaries for v0.1.0 -->
- 完成最小可运行原型，支持单文件转写与 JSON 输出。
- 建立项目基础结构（src/config/tests），为后续扩展奠定基础。
