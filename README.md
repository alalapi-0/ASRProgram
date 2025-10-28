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
<!-- Purpose: Provide zero-to-one prerequisites for beginners -->
### 0. 环境准备 / Prepare Your Environment
<!-- Purpose: Detail prerequisites for novice users -->
1. 安装 [Python 3.10+](https://www.python.org/downloads/)（Windows 用户安装时勾选 “Add Python to PATH”）。
2. （可选）安装 [Git](https://git-scm.com/downloads) 以便拉取更新。
3. 在终端/命令提示符中克隆或解压本项目：
   ```bash
   git clone https://github.com/your-org/ASRProgram.git
   cd ASRProgram
   ```
4. 建议创建虚拟环境，避免与系统 Python 冲突：
   ```bash
   python -m venv .venv
   # Windows PowerShell
   .venv\Scripts\activate
   # macOS / Linux
   source .venv/bin/activate
   ```

<!-- Purpose: Guide installation step heading -->
### 1. 安装依赖 / Install Dependencies
<!-- Purpose: Provide commands for dependency installation -->
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

<!-- Purpose: Document environment verification command for easy diagnosis -->
### 2. 环境检测 / Verify the Setup
<!-- Purpose: Explain usage of verify_env script -->
运行自检脚本，自动检查 Python 版本、依赖、模型缓存目录以及 faster-whisper / whisper.cpp 相关配置：
```bash
python scripts/verify_env.py --backend faster-whisper --model base
```
> 若脚本输出 `WARNING`，请根据提示安装缺失依赖或调整目录权限。完整参数说明可通过 `-h/--help` 查看。

<!-- Purpose: Provide run instructions heading -->
### 3. 运行示例 / Run a Transcription Job
<!-- Purpose: Provide CLI usage example with bilingual inline comments -->
```bash
python -m src.cli.main \
  --input ./samples \
  --backend faster-whisper \
  --profile ubuntu-cpu-quality \
  --segments-json true \
  --verbose
```

> Linux/Ubuntu 环境下若未显式指定 `--profile`，CLI 会自动套用 `ubuntu-cpu-quality`，以 large-v2 + CPU/int8 组合优先保证词级质量。

<!-- Purpose: Highlight expected outputs heading -->
### 4. 输出结果 / Output Artifacts
<!-- Purpose: Detail output files for user awareness -->
- <!-- Purpose: Word JSON explanation -->`out/*.words.json`：词级时间戳及置信度。
- <!-- Purpose: Segment JSON explanation -->`out/*.segments.json`：段级转写（可选）。
- <!-- Purpose: Manifest explanation -->`out/_manifest.jsonl`：处理记录、哈希与性能信息。

<!-- Purpose: Introduce dedicated large-v2 workflow section -->
## 🎯 Whisper large-v2 中文零交互流程
<!-- Purpose: Provide concise summary bullets -->
- 模型固定为 `faster-whisper/large-v2`，语言固定中文（`zh`），默认输出段级与词级时间轴。
- 使用 Hugging Face Hub 自动断点续传下载，缓存目录默认为 `~/.cache/asrprogram/models/faster-whisper/large-v2`。
- 新增 `tools/asr_quickstart.py` 提供零交互主入口，搭配 `--no-prompt` 可一键执行；在 Linux/Ubuntu 上会自动启用 `ubuntu-cpu-quality` profile（CPU + int8 + large-v2）。
- 支持 `--tee-log` 双通道日志，远程终端亦可实时查看输出。

<!-- Purpose: Document one-click scripts -->
### 🔘 一键运行脚本
- **Ubuntu / macOS / WSL**
  ```bash
  chmod +x scripts/auto_transcribe.sh
  ./scripts/auto_transcribe.sh
  ```
- **Windows**
  ```bat
  scripts\auto_transcribe.bat
  ```

运行脚本后，将自动：检查 `ffmpeg`、下载模型（如缺失）、遍历 `./Audio` 目录下的音频文件并顺序生成 JSON 结果。

<!-- Purpose: Describe output artifacts -->
### 📦 输出文件
- `out/<filename>.segments.json`：段级时间轴（包含平均置信度、词列表）。
- `out/<filename>.words.json`：词级时间轴（包含起止时间、置信度、段编号）。

<!-- Purpose: Mention cache location -->
### 📁 模型缓存目录
默认缓存路径为：`~/.cache/asrprogram/models/faster-whisper/large-v2`。可通过 `--models-dir` 覆写（Linux/macOS 使用 `~/path`，Windows 支持 `%USERPROFILE%\path`）。

<!-- Purpose: Document token guidance -->
### 🔐 Hugging Face Token（401/403 解决）
1. 前往 [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) 创建 **Read** 权限的 Token。
2. **Linux / macOS** 永久配置：
   ```bash
   echo 'export HF_TOKEN="hf_xxx"' >> ~/.bashrc
   echo 'export HUGGINGFACE_HUB_TOKEN="hf_xxx"' >> ~/.bashrc
   source ~/.bashrc
   ```
3. **Windows** 永久配置：
   ```powershell
   setx HF_TOKEN "hf_xxx"
   setx HUGGINGFACE_HUB_TOKEN "hf_xxx"
   ```
4. 或使用 CLI 登录缓存：
   ```bash
   huggingface-cli login --token hf_xxx
   ```

> `scripts/setup.sh` 会在 Ubuntu VPS 中检测缺失的 `ffmpeg` 并尝试通过 `apt-get` 自动安装，若安装失败请手动执行 `sudo apt-get install ffmpeg`。

<!-- Purpose: Provide python API sample heading -->
### 5. Python API 示例 / Python API Usage
<!-- Purpose: Show how to use library programmatically -->
```python
from src.pipeline.runner import TranscriptionRunner  # 加载核心流水线

runner = TranscriptionRunner.from_profile("ubuntu-cpu-quality")  # 使用针对 Ubuntu 的高质量 CPU profile
result = runner.run_file("./samples/demo.wav", segments_json=True)  # 执行单文件转写
print(result.words[0])  # 打印首个词条的时间戳与置信度
```

<!-- Purpose: Provide cloud invocation example heading -->
### 6. 云端调用示例 / Cloud Invocation Example
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
| `ubuntu-cpu-quality` | <!-- Purpose: ubuntu profile description -->large-v2 + CPU/int8，附带段/词级 JSON。 | <!-- Purpose: ubuntu profile use case -->无 GPU 的 Ubuntu VPS、高质量词级转写 |

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

<!-- Purpose: Introduce remote monitoring section -->
## 🌐 远程实时监控与日志 / Remote Live Monitoring
<!-- Purpose: Describe SSH usage -->
1. **SSH 直连实时查看 / Live over SSH**
   ```bash
   ssh -t ubuntu@<IP> 'cd /home/ubuntu/asr_program && PYTHONUNBUFFERED=1 python3 -u tools/asr_quickstart.py --no-prompt --download --tee-log out/run_$(date +%F_%H%M%S).log'
   ```
   上述命令结合 `PYTHONUNBUFFERED=1` 与 `--tee-log`，在交互终端实时刷出日志的同时，将内容追加到带时间戳的文件中。

<!-- Purpose: Describe tmux usage -->
2. **后台运行（tmux） / Background with tmux**
   ```bash
   tmux new -s asr -d 'cd /home/ubuntu/asr_program && PYTHONUNBUFFERED=1 python3 -u tools/asr_quickstart.py --no-prompt --download --tee-log out/run.log'
   tmux attach -t asr
   ```
   通过 `tmux` 将任务留在远端后台运行，重连会话即可继续查看实时输出。

<!-- Purpose: Describe systemd usage -->
3. **systemd 服务示例 / systemd Unit Example**
   ```ini
   [Service]
   WorkingDirectory=/home/ubuntu/asr_program
   ExecStart=/usr/bin/python3 -u -m src.cli.main ... --tee-log /var/log/asr/run.log
   Environment=PYTHONUNBUFFERED=1
   StandardOutput=journal+console
   StandardError=journal+console
   ```
   将服务 stdout/stderr 同时写入控制台与 systemd journal，配合 `--tee-log` 便于集中收集历史日志。

<!-- Purpose: Explain CLI switches -->
`--tee-log <FILE>` 会将所有日志同时写入控制台与指定文件；`--force-flush` 强制每条日志即时刷新到终端和磁盘，适合 tail/SSH 监控；`--no-progress` 可在脚本化环境完全关闭进度条。若未显式关闭进度条，程序会在非 TTY 环境（如重定向或 systemd）自动禁用动画，仅输出结构化进度日志，避免噪音。

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

## 🇨🇳 固定大模型中文转写（Windows & Ubuntu）

本项目提供一个**超简入口**，固定使用 `faster-whisper` 的 **large-v3** 大模型，语言固定为中文（`--language zh`）。  
你只需要输入「音频路径」与「输出目录」，其余流程自动处理（含**自动下载模型**）。

### 快速开始

#### Windows
1. 安装 Python 3.10+ 与 ffmpeg，并将 ffmpeg 的 `bin` 加入 `PATH`。  
2. 安装依赖：
   ```bash
   python -m pip install -U pip
   pip install -r requirements.txt
   ```

3. 运行一键脚本或主入口：

   ```bash
   scripts\run_transcribe.bat
   # 或
   python tools\asr_quickstart.py
   ```

#### Ubuntu（VPS 常见系统：Ubuntu 就是 Linux 的一种发行版）

1. 安装系统依赖：

   ```bash
   sudo apt-get update
   sudo apt-get install -y ffmpeg python3-pip
   ```
2. 安装 Python 依赖：

   ```bash
   python3 -m pip install -U pip
   pip3 install -r requirements.txt
   ```
3. 运行一键脚本或主入口：

   ```bash
   chmod +x scripts/run_transcribe.sh
   ./scripts/run_transcribe.sh
   # 或
   python3 tools/asr_quickstart.py
   ```

### 运行流程

1. 程序会提示你输入：

   * **输入路径**：可以是单个音频文件或一个包含音频的文件夹；
   * **输出目录**：`*.segments.json`（段级）与 `*.words.json`（词级）会保存到这里。
2. 程序自动调用 `scripts/download_model.py` 下载 **large-v3** 模型（落在 `~/.cache/asrprogram/models`，可自定义）。
3. 程序自动运行转写（`--language zh`），并在输出目录生成 JSON 文件。

#### Hugging Face Token（下载受限/403/401 时）

部分模型仓库需要登录凭据，即便是公开模型也可能因为频率限制导致 401/403。可以按以下步骤配置 Token：

1. 打开 [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)，创建一个 **Read** 权限的 Token（或细粒度 Token，仅勾选最小下载权限）。
2. 配置环境变量（任选其一）：
   * **Windows**（命令提示符）：`setx HUGGINGFACE_HUB_TOKEN "hf_xxx"`
   * **Linux/macOS**：`export HUGGINGFACE_HUB_TOKEN=hf_xxx`
3. 亦可使用 `huggingface-cli login --token hf_xxx` 保存到本机凭据。
4. 验证环境变量：

   ```bash
   python -c "import os; print(os.getenv('HUGGINGFACE_HUB_TOKEN'))"
   ```

> 备注：
>
> * 使用大模型在 **CPU** 环境下会较慢，建议 VPS 具备较充足的内存（≥16GB）；
> * 若你的 CLI 支持 `--device` / `--compute-type` 参数，CPU 环境可考虑 `int8` / `int8_float16` 节省内存；CUDA 环境可用 `float16`。

### 常见问题

* **Ubuntu 是 Linux 吗？** 是的，Ubuntu 是最常见的 Linux 发行版之一。
* **为什么不提供 tiny/small 选项？** 你的目标是生成高质量的**词级时间戳**，大模型在对齐与鲁棒性上更稳定，所以入口已固定为 `large-v3`。
* **模型下载失败？** 请检查网络或重试；也可提前在本地下载好模型并把模型目录传给程序（默认 `~/.cache/asrprogram/models`）。
