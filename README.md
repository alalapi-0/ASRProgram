<!-- Purpose: Provide bilingual project title with emoji to convey ASR focus -->
# ASRProgram 🗣️ 词级时间戳转写程序
<!-- Purpose: Deliver concise tagline describing system scope -->
一个轻量、可扩展、可云端运行的自动语音识别（ASR）转写系统。

<!-- Purpose: Separate header visually using thematic break -->
---

<!-- Purpose: Introduce project overview section -->
## 🧠 项目简介 / Project Overview
<!-- Purpose: Explain pipeline and backend coverage in Chinese -->
ASRProgram 提供从音频到词级时间戳 JSON 的完整流水线，支持 faster-whisper 与 whisper.cpp，可在本地或云端批处理运行。
<!-- Purpose: Provide English summary for global contributors -->
ASRProgram delivers an end-to-end pipeline that converts audio inputs into word-level timestamp JSON, offering interchangeable faster-whisper and whisper.cpp backends suitable for local batches or cloud workers.

<!-- Purpose: Highlight key differentiators as bullet list -->
- <!-- Purpose: Bullet 1 Chinese -->支持配置驱动的流水线，结合 YAML、环境变量与 CLI，灵活适配不同部署场景。
- <!-- Purpose: Bullet 2 Chinese -->内置 JSON Schema 校验与 Manifest 追踪，确保每个结果可追溯、可重复。
- <!-- Purpose: Bullet 3 Chinese -->提供可拓展的后端接口，便于接入自定义推理服务或云端 API。
- <!-- Purpose: Bullet 4 English -->Includes reproducible smoke tests and metrics-ready logging, enabling fast validation in CI/CD pipelines.

<!-- Purpose: Outline quickstart section -->
## 🚀 快速开始 / Quick Start
<!-- Purpose: Guide installation step heading -->
### 1. 安装依赖 / Install Dependencies
<!-- Purpose: Provide commands for dependency installation -->
```bash
pip install -r requirements.txt
```

<!-- Purpose: Provide run instructions heading -->
### 2. 运行示例 / Run a Transcription Job
<!-- Purpose: Provide CLI usage example with bilingual inline comments -->
```bash
python -m src.cli.main \
  --input ./samples \
  --backend faster-whisper \
  --profile cpu-fast \
  --segments-json true \
  --verbose
```

<!-- Purpose: Highlight expected outputs heading -->
### 3. 输出结果 / Output Artifacts
<!-- Purpose: Detail output files for user awareness -->
- <!-- Purpose: Word JSON explanation -->`out/*.words.json`：词级时间戳及置信度。
- <!-- Purpose: Segment JSON explanation -->`out/*.segments.json`：段级转写（可选）。
- <!-- Purpose: Manifest explanation -->`out/_manifest.jsonl`：处理记录、哈希与性能信息。

<!-- Purpose: Provide python API sample heading -->
### 4. Python API 示例 / Python API Usage
<!-- Purpose: Show how to use library programmatically -->
```python
from src.pipeline.runner import TranscriptionRunner  # 加载核心流水线

runner = TranscriptionRunner.from_profile("cpu-fast")  # 使用预设 profile
result = runner.run_file("./samples/demo.wav", segments_json=True)  # 执行单文件转写
print(result.words[0])  # 打印首个词条的时间戳与置信度
```

<!-- Purpose: Provide cloud invocation example heading -->
### 5. 云端调用示例 / Cloud Invocation Example
<!-- Purpose: Show example for remote execution -->
```bash
curl -X POST https://example.com/asrprogram/api/transcribe \
  -H "Content-Type: application/json" \
  -d '{"input_url": "https://cdn.example.com/audio/demo.wav", "profile": "gpu-accurate"}'
```
<!-- Purpose: Explain cloud example context -->
> 以上示例展示如何通过自建 HTTP 服务包装 ASRProgram，将云端对象存储中的音频交给后端工作者处理。

<!-- Purpose: Introduce configuration section -->
## ⚙️ 配置与运行环境 / Configuration & Runtime
<!-- Purpose: Summarize layered config approach -->
ASRProgram 采用“YAML 默认 + 用户覆盖 + 环境变量 + CLI”四层配置模型，配置加载顺序如下（后者覆盖前者）：
<!-- Purpose: Show layered list -->
1. <!-- Purpose: Base config explanation -->`config/default.yaml`：基础默认值。
2. <!-- Purpose: User override explanation -->`config/user.yaml`（可选）：团队或个人覆写。
3. <!-- Purpose: Environment variables explanation -->环境变量：以 `ASRPROGRAM_` 前缀识别。
4. <!-- Purpose: CLI explanation -->命令行参数：最终覆盖并支持临时实验。

<!-- Purpose: Provide profile table heading -->
### Profiles / 预设运行档
<!-- Purpose: Explain available profiles table -->
| Profile | 描述 Description | 典型场景 Typical Use |
| --- | --- | --- |
| `cpu-fast` | <!-- Purpose: cpu-fast description -->低算力快速转写，启用动态分段和轻量模型。 | <!-- Purpose: cpu-fast use case -->本地开发、CI 验证 |
| `gpu-accurate` | <!-- Purpose: gpu-accurate description -->利用 GPU 模型提升准确率与并行度。 | <!-- Purpose: gpu-accurate use case -->云端批量转写、长音频 |
| `whispercpp-lite` | <!-- Purpose: whispercpp-lite description -->基于 whisper.cpp 的纯 CPU 极简模式。 | <!-- Purpose: whispercpp-lite use case -->资源受限的边缘节点 |

<!-- Purpose: Provide configuration file reference -->
> 所有 Profile 定义位于 `config/profiles/`，可复制后调整推理参数与后端配置。

<!-- Purpose: Introduce logging section -->
## 🪵 日志与监控 / Logging & Observability
<!-- Purpose: Explain logging modes in Chinese and English -->
系统支持两种日志模式：`human`（彩色本地调试）与 `jsonl`（机器可读，便于云端采集）。
For observability pipelines, enable JSONL mode to stream structured records into systems like Loki or BigQuery.

<!-- Purpose: Explain outputs -->
- <!-- Purpose: Metrics file explanation -->可选输出指标（CSV / JSONL），用于统计词数、耗时与错误率。
- <!-- Purpose: Trace explanation -->通过 TraceID 贯穿多阶段任务，便于跨服务追踪。

<!-- Purpose: Provide example configuration snippet heading -->
```yaml
logging:
  mode: jsonl  # 使用结构化日志，便于集中采集
  metrics_path: out/metrics.csv  # 可选指标导出位置
  trace_id: auto  # 自动生成 TraceID
```

<!-- Purpose: Introduce testing section -->
## 🧪 测试与验证 / Testing & Verification
<!-- Purpose: Provide commands for tests -->
```bash
pytest -q
bash scripts/smoke_test.sh
```
<!-- Purpose: Explain schema validation -->
所有输出 JSON 均通过 `schemas/*.json` 自动校验，确保结构兼容与时间戳单调性。

<!-- Purpose: Introduce troubleshooting FAQ heading -->
## 💡 常见问题 / FAQ
<!-- Purpose: Provide question-answer pairs -->
**Q: 模型太大怎么办？ / The models are too large.**
A: 使用 `--profile whispercpp-lite` 即可启用轻量 GGUF 模型并自动降级线程数。

**Q: 如何在云端运行？ / How can I deploy in the cloud?**
A: 在 VPS 或 Docker 中运行 CLI 即可，日志模式推荐设为 `jsonl` 便于收集。

**Q: 如何自定义后端？ / How do I plug in a custom backend?**
A: 参考 `src/backends/base.py` 接口并实现 `transcribe_batch`，再在配置文件中声明新的 backend 名称即可被 CLI 发现。

<!-- Purpose: Introduce directory layout section -->
## 🧰 目录结构 / Repository Layout
<!-- Purpose: Provide tree structure for orientation -->
```
ASRProgram/
├── src/                 # 主源码，含 CLI、后端与流水线
├── config/              # 默认配置、Profile 与运行参数
├── schemas/             # 输出 JSON Schema 定义
├── tests/               # 单元与集成测试
├── scripts/             # 运维、安装与发行脚本
├── .github/workflows/   # CI 自动化配置
├── README.md            # 项目说明文档
├── CHANGELOG.md         # 版本更新记录
├── LICENSE              # 开源协议
└── VERSION              # 当前版本号
```

<!-- Purpose: Introduce release section -->
## 📦 发行与版本 / Release & Versioning
<!-- Purpose: Provide version info -->
当前版本：`v1.0.0`，遵循语义化版本控制。
<!-- Purpose: Provide packaging command -->
```bash
bash scripts/package_release.sh
```
<!-- Purpose: Explain packaging output -->
执行后将在 `dist/` 目录生成 `ASRProgram_v1.0.0.tar.gz`，包含源码、配置、Schema、脚本与文档。
<!-- Purpose: Mention verification script -->
发布前建议运行 `python scripts/verify_before_release.py` 确认环境、禁项与依赖摘要。

<!-- Purpose: Introduce roadmap section -->
## 🔭 未来计划 / Roadmap
<!-- Purpose: Provide future work items -->
- <!-- Purpose: Streaming support -->支持实时流式转写，降低延迟。
- <!-- Purpose: Audio segmentation -->集成能量阈值与 VAD，自动切分长音频。
- <!-- Purpose: Web viewer -->提供 Web 前端查看与标注功能。
- <!-- Purpose: Cloud queue -->对接云端任务队列与指标监控。

<!-- Purpose: Introduce contribution guidance section -->
## 🤝 贡献指南 / Contributing
<!-- Purpose: Provide steps to contribute -->
1. <!-- Purpose: Fork repo -->Fork 仓库并创建特性分支。
2. <!-- Purpose: Install dev deps -->安装开发依赖：`pip install -r requirements-dev.txt`。
3. <!-- Purpose: Run tests -->提交前运行 `pytest -q` 与 `bash scripts/smoke_test.sh`。
4. <!-- Purpose: Follow style -->遵循 `src/` 内的类型注释、文档字符串与 logging 约定。

<!-- Purpose: Introduce contact section -->
## 📫 联系方式 / Contact
<!-- Purpose: Provide placeholder contact info -->
如需商业支持或合作，请发送邮件至 `support@asrprogram.example`。
For community questions, open an issue or discussion in the repository.

<!-- Purpose: Introduce license section -->
## 🪪 License / 授权协议
<!-- Purpose: Provide license summary -->
本项目采用 MIT License，详见 `LICENSE` 文件。欢迎在商业或开源项目中使用，需保留版权声明与许可文本。

<!-- Purpose: Closing remark -->
感谢使用 ASRProgram，期待社区贡献与反馈！

☁️ 云端/CI 真实转写（自动下载模型）

本项目提供一套 GitHub Actions 工作流，会在云端 runner 上完成以下步骤：
	1.	安装 Python 3.10 与 ffmpeg；
	2.	安装项目依赖；
	3.	下载 faster-whisper 模型（tiny） 到缓存目录（~/.cache/asrprogram/models）；
	4.	动态合成一段 1.5 秒 WAV 音频（无需提交音频样本）；
	5.	运行 CLI，生成 段级 与 词级 JSON；
	6.	校验输出结构并上传产物作为 Artifact。

	•	工作流文件：.github/workflows/asr_full.yml
	•	模型缓存：actions/cache 已启用；后续运行会复用模型，加速 CI。
	•	若你想在 CI 中切换模型，可在 asr_full.yml 的“Download tiny model”步骤，将 --model tiny 改为 small|base|...（注意 CI 时长）。

本地一键运行（含自动下载 tiny 模型）

# 一次性准备（需要 ffmpeg；若没有，请用系统包管理器安装）
python -m pip install -U pip
pip install -r requirements.txt

# 下载 tiny 模型到本地缓存（默认 ~/.cache/asrprogram/models）
python scripts/download_model.py --backend faster-whisper --model tiny

# 生成一个测试音频并跑 CLI
python .github/scripts/gen_sine_wav.py tmp_audio/beep.wav
python -m src.cli.main \
  --input tmp_audio \
  --out-dir out \
  --backend faster-whisper \
  --language auto \
  --segments-json true \
  --overwrite true \
  --verbose

产物位置：out/*.words.json 与 out/*.segments.json。

🛠 GitHub Actions 手动设置要点
	1.	进入仓库 Settings → Actions → General：
		•	Actions permissions 请选择 “Allow all actions”。
	2.	如组织策略限制第三方 Actions，请把下面两个加入允许列表：
		•	actions/checkout@v4
		•	actions/setup-python@v5
	3.	（可选）分支保护：若启用，请将 Full ASR (words.json) 设为必需检查。
	4.	本工作流 不需要任何 Secrets。
	5.	若 CI 仍超时：
		•	保持 --model tiny；
		•	确保模型缓存命中（查看 “Cache ASR models” 步骤日志）；
		•	机器繁忙时可重复触发 Re-run all jobs。
