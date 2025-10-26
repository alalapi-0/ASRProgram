## 项目简介
ASRProgram 是一个演示性项目，用于将输入音频文件的元信息转化为词级和段级 JSON 结构；在 Round 3 中，新增统一的后端接口
与 faster-whisper 占位实现，所有识别结果依旧由模拟逻辑生成，仅用于打通扫描输入、模拟转写与落盘的完整流程。

## 快速开始
1. **创建虚拟环境**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows PowerShell 使用 .venv\Scripts\Activate.ps1
   ```
2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```
3. **环境验证（可选）**
   ```bash
   python scripts/verify_env.py
   ```
4. **查看 CLI 帮助**
   ```bash
   python -m src.cli.main --help
   ```
5. **Dry Run 示例（不落盘）**
   ```bash
   python -m src.cli.main --input ./samples --dry-run true --verbose
   ```
6. **正常运行（目录扫描，占位生成）**
   ```bash
   python -m src.cli.main --input ./samples --out-dir ./out --backend dummy --segments-json true
   ```

## 一键安装与环境自检（Round 2）
本轮新增的 `scripts/setup.sh` 与 `scripts/setup.ps1` 均为**演练模式**脚本：无论 `--check-only` 取值为何，都只会打印未来计划，不会
创建虚拟环境、安装依赖或下载模型。脚本末尾会真实执行 `scripts/verify_env.py`，输出当前环境体检报告。

### 参数总览
| 参数 | 默认值 | 适用脚本 | 说明 |
| --- | --- | --- | --- |
| `--check-only` / `-check-only` | `true` | Bash / PowerShell | 是否仅演练安装步骤，本轮即使为 `false` 也不会执行真实动作 |
| `--backend` / `-backend` | `faster-whisper` | Bash / PowerShell | 计划使用的后端，用于展示未来将执行的模型准备流程 |
| `--model` / `-model` | `medium` | Bash / PowerShell | 计划下载的模型规格，仅用于打印提示 |
| `--use-system-ffmpeg` / `-use-system-ffmpeg` | `true` | Bash / PowerShell | 是否尝试复用系统 `ffmpeg`，当前仅检测 PATH |
| `--python` / `-python` | *未指定* | Bash / PowerShell | 指定未来用于创建虚拟环境的解释器路径，本轮仅校验是否可执行 |
| `--cache-dir` / `-cache-dir` | `.cache/` | Bash / PowerShell | 计划使用的缓存目录，仅检测是否已存在及可写 |

### 典型命令
```bash
# Bash（Mac/Linux）
bash scripts/setup.sh --check-only true --backend faster-whisper --model medium --use-system-ffmpeg true

# PowerShell（Windows / pwsh）
pwsh -File scripts/setup.ps1 -check-only true -backend faster-whisper -model medium -use-system-ffmpeg true

# 单独运行环境体检（真实执行）
python scripts/verify_env.py
```

### 预期输出片段
```
---- 计划步骤（仅打印，不执行） ----
当前为 check-only 演练模式，不会执行任何写操作。
1. 创建虚拟环境：python -m venv .venv
...
以下为真实探测结果：
ASRProgram 环境体检报告（Round 2 演练模式）
Python 解释器: /usr/bin/python3
```

> **提示**：Round 5 才会启用真实安装、模型下载与按平台分流的 `ffmpeg` 获取策略；当前轮次仅做准备与环境评估。

## Round 5：一键安装（实际执行）
Round 5 中，我们将演练脚本升级为**真实可执行的安装流程**，但仍坚持“不下载模型”的约束。`setup.sh`/`setup.ps1` 会完成虚拟环境创建、pip 依赖安装、尝试安装 CPU 版 `torch`，并自动准备系统或缓存中的 `ffmpeg/ffprobe`。脚本的末尾会运行增强版 `scripts/verify_env.py`，输出 Python 包与多媒体工具的版本信息。

### 新增依赖清单
`requirements.txt` 已更新为最小可用集：

```
faster-whisper>=1.0.0
numpy>=1.23
soundfile>=0.12
tqdm>=4.66
PyYAML>=6.0
requests>=2.31
```

`torch` 不在 requirements 中，由安装脚本根据平台尝试安装 CPU 轮子；若失败，脚本仅提示后续操作并继续执行。

### 安装脚本参数对照
| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--check-only true|false` / `-check-only true|false` | `false` | 是否仅执行计划与体检；`true` 时不会创建虚拟环境或下载 `ffmpeg` |
| `--python <path>` / `-python <path>` | 自动探测 | 指定用于创建虚拟环境的 Python，可用于选择特定版本 |
| `--use-system-ffmpeg true|false` / `-use-system-ffmpeg true|false` | `true` | `true` 时若系统已有 `ffmpeg`/`ffprobe` 将直接复用 |
| `--cache-dir <path>` / `-cache-dir <path>` | `.cache` | 下载静态 `ffmpeg` 时的缓存位置，同时用于后续模型缓存 |
| `--venv-dir <path>` / `-venv-dir <path>` | `.venv` | 虚拟环境所在目录，可按需放置在外部磁盘 |
| `--extra-index-url <url>` / `-extra-index-url <url>` | *未指定* | 附加 pip 镜像索引，适用于企业代理或国内镜像 |

### 典型命令
```bash
# Linux / macOS（Bash）
bash scripts/setup.sh \
  --python "$(which python3)" \
  --use-system-ffmpeg false \
  --cache-dir .cache \
  --venv-dir .venv

# Windows PowerShell（pwsh）
pwsh -File scripts/setup.ps1 `
  -python "C:\Python310\python.exe" `
  -use-system-ffmpeg false `
  -cache-dir ".cache" `
  -venv-dir ".venv"

# 仅体检（不做安装）
bash scripts/setup.sh --check-only true
pwsh -File scripts/setup.ps1 -check-only true
```

### ffmpeg/ffprobe 处理策略
1. **优先复用系统安装**：若 `which ffmpeg` 或 `Get-Command ffmpeg` 成功，脚本会直接使用现有二进制。
2. **下载静态构建（落地于 `.cache/ffmpeg/`）**：
   - Linux：使用 johnvansickle 提供的 `ffmpeg-release-amd64-static.tar.xz`。
   - macOS：使用 yt-dlp 团队维护的 `ffmpeg-master-latest-macos64-static` 压缩包。
   - Windows：使用 gyan.dev 的 `ffmpeg-git-essentials.7z`，需要系统具备 `7z` 命令（可通过 Chocolatey 或 winget 安装 7-Zip）。
3. **临时修改 PATH**：下载完成后仅在当前脚本会话内注入 `bin/` 目录，避免污染用户环境。

所有下载文件会放在 `.cache/ffmpeg/` 下，并已通过 `.gitignore` 排除，不会被提交到仓库。

### 样例输出片段
```
[INFO] 正在创建虚拟环境：/path/to/repo/.venv
... pip install 日志 ...
[INFO] torch CPU 版安装成功。
[INFO] 已检测到系统 ffmpeg/ffprobe：/usr/bin/ffmpeg
=== 核心依赖检测 ===
OK: faster-whisper 1.0.1
OK: numpy 1.26.4
=== 多媒体工具版本 ===
ffmpeg: ffmpeg version 6.1.1-static ...
ffprobe: ffprobe version 6.1.1-static ...
OK: 核心依赖已就绪。
```

### 常见问题排查
- **torch 安装失败**：
  - Linux/Windows CPU 环境：手动执行 `pip install torch --index-url https://download.pytorch.org/whl/cpu`。
  - Apple Silicon：使用 `pip install torch --extra-index-url https://download.pytorch.org/whl/cpu`，或参考 PyTorch 官方说明选择 nightly 轮子。
  - GPU 环境：根据 CUDA 版本选择合适的官方索引链接，确保仍在虚拟环境中安装。
- **ffmpeg 下载失败**：
  - Linux：`sudo apt install ffmpeg` 或 `sudo yum install ffmpeg`。
  - macOS：`brew install ffmpeg`。
  - Windows：`winget install --id Gyan.FFmpeg` 或 `choco install ffmpeg`。
  - 若网络受限，可离线下载压缩包后放置到 `.cache/ffmpeg/` 并手动解压。
- **企业代理或离线环境**：使用 `--extra-index-url https://mirrors.aliyun.com/pypi/simple/` 等镜像源，必要时结合 `pip config set global.trusted-host`。

### 下一步
Round 6 将聚焦模型下载与缓存策略：在 `.cache/models/` 下按后端与模型名存放权重，并补充下载进度条与断点续传能力。

## Round 9：目录批处理、并发与重试
随着音频数据集规模的增长，单线程串行处理难以满足效率需求。本轮我们为 `src/asr/pipeline.py` 引入了多文件目录扫描、任务队列与线程池调度，实现可控的并发批处理能力。在并发执行的同时，也新增了令牌桶限流、指数退避重试、任务级失败隔离以及汇总统计/进度展示，确保在大批量任务下仍能稳定运行。

### 核心能力
* **目录批处理**：当 `--input` 指向目录时会递归扫描音频文件（`.wav/.mp3/.m4a/.flac`），并按稳定顺序放入任务队列。
* **并发执行**：`--num-workers` 控制线程池并发度；每个任务在线程中调用后端识别、原子落盘并返回结构化结果。
* **失败隔离与重试**：对于 `TransientTaskError` 等可恢复异常，采用指数退避（带抖动）重试；最终失败的任务会写入 `<name>.error.txt`，但不会影响其他任务继续。
* **限流与 fail-fast**：`--rate-limit` 控制任务启动速率（任务/秒），适合受限资源环境；`--fail-fast` 在出现首个失败后停止提交新的任务，避免浪费资源。
* **进度与汇总**：在控制台展示实时进度条（若安装 `tqdm`）或简易进度行，任务完成后打印总览，包括成功/失败/跳过/取消数量、耗时、吞吐率以及失败样例。
* **跳过已完成文件**：默认 `--skip-done true`，在检测到对应 `*.words.json`（以及启用段级输出时的 `*.segments.json`）存在且未指定 `--overwrite true` 时，会直接跳过该文件，实现断点续跑。

### 新增 CLI 参数
| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--num-workers` | `1` | 线程池并发度，建议范围 1~8；CPU-only 环境可设 2~4，GPU 推理时 1~2 更稳。 |
| `--max-retries` | `1` | 单文件可重试次数，实际尝试次数为 `1 + max_retries`；建议 1~2。 |
| `--rate-limit` | `0.0` | 任务启动速率限制（任务/秒），0 表示不限速；远程服务或共享 GPU 时可设 0.5~1.0。 |
| `--skip-done` | `true` | 是否跳过已生成结果的文件；保持 `true` 可实现断点续跑。 |
| `--fail-fast` | `false` | 一旦出现失败是否停止提交新任务；适合对失败敏感或想尽快介入排查的场景。 |

### 使用示例
```bash
# 4 线程并发，失败自动重试一次，默认跳过已完成文件
python -m src.cli.main \
  --input ./audio_dir \
  --backend faster-whisper \
  --num-workers 4 \
  --max-retries 1 \
  --skip-done true \
  --segments-json true \
  --verbose
```

### 资源占用与调优建议
* **内存与 GPU 压力**：增加并发度会带来更高的显存/内存占用，建议在观察系统监控后逐步调大 `--num-workers`。
* **限流场景**：当调用远程推理服务或共享 GPU 资源时，可通过 `--rate-limit` 控制任务启动节奏，避免瞬时洪峰。
* **重试策略**：`--max-retries` 提供指数退避重试，可缓解临时 I/O、网络抖动；若失败多为数据质量问题，可将其设为 `0`。
* **fail-fast 使用**：在需要快速发现问题或避免队列堆积时开启 `--fail-fast`；已运行的任务不会被打断，剩余待提交任务会被标记为取消。

### 故障排查
* **大量失败**：检查 `*.error.txt` 中的堆栈，确认是否为权限、路径或后端模型问题；必要时降低 `--num-workers` 并开启 `--verbose`。
* **输出目录不可写**：管线会检测并立即报错；确认目录权限或切换到可写路径。

## Round 12：结构化日志与可观测性升级
为便于大规模跑批后的溯源与自动化分析，本轮引入结构化日志、指标导出、轻量 Profiler 以及 TraceID 贯穿机制。所有日志既可面向人类阅读，也可被机器消费；同时可将指标落盘为 CSV/JSONL，用于后续 BI 与监控系统接入。

### 快速体验：JSONL 日志 + 指标导出
```bash
python -m src.cli.main \
  --input ./samples \
  --backend faster-whisper \
  --log-format jsonl \
  --log-file logs/run.jsonl \
  --metrics-file logs/metrics.jsonl \
  --profile true \
  --verbose true
```

上述命令会生成结构化 JSONL 日志与指标文件，所有事件都附带同一个 `trace_id`，方便后续过滤与联调。

### 新增参数
| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--log-format` | `human` | 控制日志格式，可选 `human`（易读）或 `jsonl`（机器处理）。 |
| `--log-level` | `INFO` | 调整日志等级；配合 `--log-file` 可保留详细追踪。 |
| `--log-file` | `None` | 若设置，则以追加模式写入指定文件，同时仍可选择是否在控制台输出。 |
| `--log-sample-rate` | `1.0` | 针对 `INFO`/`DEBUG` 级别的采样率，降低跑批时的日志噪音。 |
| `--metrics-file` | `None` | 若提供，则在运行结束时将全局与任务级指标导出为 CSV 或 JSONL。 |
| `--profile` | `false` | 启用轻量级阶段 Profiler，额外记录 `scan`、`load_backend`、`transcribe`、`write_outputs` 的耗时拆分。 |
| `--quiet` | `false` | 静默模式，关闭控制台的 human 日志输出；仍会写入 `--log-file` 以及 JSONL。 |
| `--progress` | `true` | 是否显示进度条；当 `--log-format jsonl --quiet true` 时建议关闭以保持终端整洁。 |

### TraceID 与上下文绑定
每次调用 `pipeline.run` 会生成一个 12 字符的 TraceID，所有日志均自动附带。例如可以使用 `jq`/`rg` 按 TraceID 聚合排查：
```bash
rg 'trace="ab12cd34ef56"' logs/run.jsonl
```
同时每个任务的日志都包含 `task.index`、`task.input` 与 `task.basename`，方便定位单个文件的生命周期。

### 指标文件内容
指标导出包含以下核心字段：
* 计数器：`files_total`、`files_succeeded`、`files_failed`、`files_skipped`。
* 摘要：`elapsed_total_sec`、`avg_file_sec`、`throughput_files_per_min`。
* 阶段耗时（开启 `--profile true` 时）：`phase_scan_sec`、`phase_load_backend_sec`、`phase_transcribe_sec`、`phase_write_outputs_sec`。

CSV 与 JSONL 的差异：CSV 提供统一表头，便于导入 BI；JSONL 则保留字典结构，更适合直接被日志系统摄取。

### 日志采样与静默模式
当批量任务产生大量 `INFO` 日志时，可通过 `--log-sample-rate 0.2` 等设置保留 20% 信息级事件，`ERROR`/`WARNING` 永不被采样。若希望完全静默终端输出，可结合 `--quiet true --log-file run.jsonl`，同时禁用进度条：`--progress false`。

### 最佳实践
* **本地调试**：`--log-format human --log-level DEBUG --profile true --progress true`，实时查看控制台输出并观察阶段耗时。
* **机器跑批**：`--log-format jsonl --quiet true --progress false --metrics-file logs/metrics.jsonl --log-file logs/run.jsonl`，将日志与指标写入文件便于后续分析或监控平台消费。

通过本轮改进，可快速回答“某个 Trace 的吞吐如何”“某阶段是否异常慢”等问题，同时与现有的并发/重试机制无缝配合。

* **吞吐忽快忽慢**：可能由限流或后端冷启动导致，适当调整 `--rate-limit` 或增减并发度。
* **内存吃紧**：适当减小 `--num-workers`，或在测试阶段启用 `--skip-done true` + `--fail-fast true`，快速定位问题文件。

## Round 6：模型下载与缓存目录
在本轮中，ASRProgram 首次引入“模型真实下载”能力：我们提供跨平台的 Python 下载器，并在安装脚本中默认触发模型拉取。所有模型都会缓存在用户主目录（如 `~/.cache/asrprogram/models/`）或自定义缓存目录中，仓库内依旧不包含任何权重文件，从而避免 Git 体积膨胀并尊重相关许可。

### 为什么把模型放在缓存目录？
- **许可与合规**：大部分 ASR 模型遵循特殊许可协议，不宜直接随仓库分发。
- **体积与更新**：`faster-whisper` 的模型普遍超过数百 MB，放在用户缓存目录可以按需更新、也便于清理。
- **多后端兼容**：未来接入 `whisper.cpp` 时，可在同一目录树下按后端划分子目录，减少路径配置成本。

### 配置与参数
安装脚本会默认读取 `config/default.yaml` 中的模型与缓存配置，以下参数可按需覆盖：

| 参数 | 适用脚本 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--backend` / `-backend` | `download_model.py` / `setup.sh` / `setup.ps1` | `faster-whisper` | 指定模型后端，目前支持 faster-whisper |
| `--model` / `-model` | 同上 | `medium` | 选择模型规格，可选 `tiny` / `base` / `small` / `medium` / `large-v3` |
| `--models-dir` / `-models-dir` | 同上 | `~/.cache/asrprogram/models/` | 模型缓存主目录，目录结构会自动按后端与模型名划分 |
| `--cache-dir` / `-cache-dir` | 同上 | `.cache/` | 通用临时缓存目录，下载器会在其中创建 `tmp/` 以存放临时文件 |
| `--mirror` | `download_model.py` | *按配置遍历* | 指定单个镜像源（如 `https://hf-mirror.com`） |
| `--force` | `download_model.py` | `false` | 强制重新下载并覆盖已有模型 |

### 典型命令
```bash
# 仅下载模型（不会创建虚拟环境）
python scripts/download_model.py --backend faster-whisper --model medium --models-dir ~/.cache/asrprogram/models

# 一键安装并自动下载模型
bash scripts/setup.sh --check-only false --use-system-ffmpeg true --cache-dir .cache

# PowerShell 版本
pwsh -File scripts/setup.ps1 -check-only false -use-system-ffmpeg true -cache-dir .cache
```

下载器会按配置顺序尝试多个镜像，默认使用 Hugging Face 主站与备用镜像。下载过程中会显示每个文件的进度与重试次数，完成后输出 JSON：

```json
{"backend": "faster-whisper", "model": "medium", "path": "/home/user/.cache/asrprogram/models/faster-whisper/medium", "size_bytes": 1536496123}
```

### 模型体积参考
以下数值来自官方仓库，仅供估算磁盘占用：

| 模型 | 预估大小 | 说明 |
| --- | ---: | --- |
| tiny | ~ 75MB | 适合快速测试 |
| base | ~ 140MB | 更平衡的体积与准确率 |
| small | ~ 460MB | 折中方案 |
| medium | ~ 1.5GB | 推荐规格，准确率更高 |
| large-v3 | ~ 3GB+ | 最高准确率，资源占用大 |

### verify_env.py 的输出变化
`scripts/verify_env.py` 现已支持解析模型目录并判断模型是否就绪：

- `MODEL STATUS: READY`：目录存在、关键文件齐全且总体积达到预估值。
- `MODEL STATUS: MISSING/INCOMPLETE`：缺少文件或体积明显不足，会提示缺失列表与补救命令。
- 当后端未知或后续轮次新增时，会打印 `WARNING` 并提示当前脚本尚未覆盖该后端的校验逻辑。

### 常见问题排查
- **网络超时或下载失败**：
  - 使用 `--mirror https://hf-mirror.com` 或企业内部镜像源。
  - 配置代理后重试，或手动下载模型文件后放到目标目录。
- **磁盘空间不足**：检查 `models_dir` 所在分区是否留有足够空间，必要时切换到外部磁盘。
- **权限问题**：Windows 用户若路径包含空格/中文，建议将模型目录改到 `C:\asr-cache\models` 等简单路径；Linux/macOS 请确认目录对当前用户可写。
- **断点续传**：下载器默认会重试失败的请求并在 `.cache/tmp/` 中保留临时文件；若多次失败，可删除临时文件后重新执行。

### 下一步
Round 7/8 将让 faster-whisper 产生真实的转写结果，并在 JSON 输出中填充词级时间戳；Round 10 会补充 whisper.cpp 的 GGML/GGUF 模型下载与哈希校验。

## Round 7：启用 faster-whisper 真实段级推理
在完成 Round 6 的模型下载后，本轮正式启用 faster-whisper 的真实推理能力。管线会调用 `ffprobe` 探测音频时长、加载缓存中的 CTranslate2 模型并生成段级 `segments.json`。词级时间戳将在下一轮补齐，因此 `words.json` 中的 `words` 数组暂时为空，但依旧包含 schema、语言、后端元信息等结构，便于后续无缝衔接。

### 从模型到识别的最小流程
1. **准备环境与模型**（若尚未执行 Round 6 步骤）：
   ```bash
   # 安装依赖并下载模型（以 medium 为例）
   bash scripts/setup.sh --check-only false --use-system-ffmpeg true --cache-dir .cache
   python scripts/download_model.py --backend faster-whisper --model medium --models-dir ~/.cache/asrprogram/models
   ```
2. **运行环境体检**：
   ```bash
   python scripts/verify_env.py --backend faster-whisper --model medium
   ```
   输出中会新增 faster-whisper 版本信息，以及模型是否能够被轻量加载的检测项。
3. **执行真实段级识别**：
   ```bash
   python -m src.cli.main \
     --input ./samples \
     --backend faster-whisper \
     --language ja \
     --segments-json true \
     --verbose true
   ```

### 输出样例
`out/sample.segments.json` 的片段如下（`words` 暂为空数组）：

```json
{
  "schema": "asrprogram.segmentset.v1",
  "language": "ja",
  "duration_sec": 12.34,
  "backend": {
    "name": "faster-whisper",
    "version": "1.0.3",
    "model": "/home/user/.cache/asrprogram/models/faster-whisper/medium",
    "device": "cpu",
    "compute_type": "int8_float16"
  },
  "meta": {
    "decode_options": {
      "beam_size": 5,
      "temperature": 0.0,
      "vad_filter": false,
      "chunk_length_s": null,
      "best_of": null,
      "patience": null
    },
    "detected_language": "ja",
    "duration_from_probe": 12.34,
    "duration_source": "ffprobe",
    "schema_version": "round7"
  },
  "segments": [
    {
      "id": 0,
      "text": "これはサンプル音声です。",
      "start": 0.0,
      "end": 4.2,
      "avg_conf": null,
      "words": []
    }
  ]
}
```

对应的 `words.json` 会包含相同的 `backend`/`meta` 信息，仅 `words` 数组为空，为 Round 8 的逐词输出预留结构。

## Round 8：词级时间戳（Word Timestamps）
本轮在 faster-whisper 后端中启用了 `word_timestamps=True`，并实现了跨语言的逐词输出：

- `<name>.words.json` 现在携带真实的 `words` 数组，每个元素包含 `text/start/end/confidence/segment_id/index`。
- `<name>.segments.json` 的 `segments[*].words` 字段与词级结果同步，便于对照段落与词汇。
- 为中文、日文等无空格语言提供降级切分：当后端缺失词级信息时，会按照字符/长度比例划分段内时间。
- 对置信度字段执行兜底：优先使用词级概率，其次回退到段级平均值，最后置为 `null`。

## Round 13：配置分层、Profile 与配置快照
本轮聚焦“可维护、可审计、可覆写”的配置体系：引入分层合并、Profile 预设、环境变量覆盖与配置快照导出机制，方便在不同环境间快速切换。

### 分层与优先级
```
default.yaml  <  user.yaml  <  .env / ASRPROGRAM_*  <  CLI / --set
(最低)                                           (最高)
```
配置加载顺序固定：始终以仓库内置的 `config/default.yaml` 为基线，随后按顺序应用用户配置、`.env`/`ASRPROGRAM_*` 环境变量，最后由 CLI 显式参数与 `--set` 键值覆盖。深度合并策略确保仅修改必要字段，`None` 不会覆盖已有非空值，而空字符串被视为显式覆盖。

### Profile 预设示例
`default.yaml` 新增了 `cpu-fast`、`gpu-accurate`、`whispercpp-lite` 与 `balanced` 等预设，可通过 `--profile` 一键切换多项参数：

```bash
# 使用 GPU 高精度预设，再局部覆盖 compute_type
python -m src.cli.main --profile gpu-accurate --set runtime.compute_type=float16 --input ./samples
```

Profile 应用后仍可继续叠加环境变量、CLI 参数或 `--set`，最终生效的 profile 名称会写入 `config.meta.profile`，并在日志与摘要中输出。

### 环境变量与 .env
配置加载器会自动解析仓库根目录与用户配置目录下的 `.env` 文件，仅当键以 `ASRPROGRAM_` 开头时生效，双下划线 `__` 表示层级。例如：

```bash
export ASRPROGRAM_RUNTIME__DEVICE=cuda
export ASRPROGRAM_CACHE_DIR=/mnt/fast-cache
```

脚本运行时也会读取进程环境中的同名前缀变量，布尔与数字会自动转成合适的类型。

### 配置快照：--print-config / --save-config
新增的 CLI 选项可导出最终生效配置（附带来源注释），便于复现实验或上传到调度器：

```bash
# 打印最终配置并退出
python -m src.cli.main --input ./samples --profile balanced --print-config true

# 保存快照到指定文件（不会执行转写）
python -m src.cli.main --input ./samples --profile cpu-fast --save-config ./runs/cpu-fast.yaml
```

快照由 `src/utils/config.render_effective_config` 生成，可在 YAML 注释中看到每个字段的来源链路（默认配置/用户配置/环境/CLI）。

### 校验规则速览
新的轻量 schema 对关键字段做了严格检查：

- `runtime.backend` 仅允许 `faster-whisper` / `whisper.cpp` / `dummy`。
- `runtime.beam_size >= 1`，`runtime.temperature` 范围为 `[0, 1]`。
- `num_workers >= 1`、`max_retries >= 0`、`log_sample_rate` 位于 `(0, 1]`。
- 路径字段会自动展开 `~`、清理尾部斜杠，语言/后端/设备等字符串统一小写。

当配置非法时会抛出 `ConfigError` 并附带来源提示，例如 `Invalid value for runtime.beam_size ... source=user:config/user.yaml`，便于快速定位问题。

### 最佳实践
- **本地开发**：在 `config/user.yaml` 中记录个人默认值，配合少量 `--set` 进行临时覆盖。
- **云端跑批**：固定一个 profile，并使用 `--save-config` 导出的快照提交给调度系统，确保跨机器运行一致。
- **环境检查**：`scripts/verify_env.py` 会展示当前生效的 profile、缓存/模型路径以及 whisper.cpp 可执行路径，帮助排查环境差异。
- 所有时间戳经过单调性修正，确保 `start <= end` 且跨词递增；修正次数会写入 `meta.postprocess.word_monotonicity_fixes`。

### 运行命令
`word_timestamps` 默认开启，可直接复用上一轮的命令：

```bash
python -m src.cli.main \
  --input ./samples \
  --backend faster-whisper \
  --language auto \
  --segments-json true \
  --verbose
```

### words.json 结构示例
生成的 `out/sample.words.json` 片段如下（仅展示前 6 个词条）：

```json
{
  "schema": "asrprogram.wordset.v1",
  "audio": {
    "path": "./samples/jp.wav",
    "duration_sec": 12.34,
    "language": "ja"
  },
  "backend": {
    "name": "faster-whisper",
    "model": "medium",
    "version": "1.0.3"
  },
  "words": [
    {"text": "これ", "start": 0.00, "end": 0.42, "confidence": 0.88, "segment_id": 0, "index": 0},
    {"text": "は", "start": 0.42, "end": 0.63, "confidence": 0.91, "segment_id": 0, "index": 1},
    {"text": "サンプル", "start": 0.63, "end": 1.24, "confidence": 0.87, "segment_id": 0, "index": 2},
    {"text": "音声", "start": 1.24, "end": 1.78, "confidence": 0.84, "segment_id": 0, "index": 3},
    {"text": "です", "start": 1.78, "end": 2.21, "confidence": 0.83, "segment_id": 0, "index": 4},
    {"text": "。", "start": 2.21, "end": 2.21, "confidence": 0.65, "segment_id": 0, "index": 5}
  ],
  "generated_at": "2025-01-01T12:34:56Z"
}
```

### 语言与标点策略
- **英文及其他空格语言**：优先使用后端返回的词数组；若缺失则按空格切分，保留连字符与撇号。
- **中文/日文/韩文**：若后端无词级结果，则按字符拆分，同时合并连续的拉丁字母或数字，利用段长按比例分配时间。
- **标点处理**：当 faster-whisper 将标点单独返回时直接保留；若并入词内部，时间戳仍沿用模型给出的边界。

### 置信度与降级说明
- 首选 `word.probability`，该值通常介于 0 与 1 之间。
- 若缺失，则使用段级 `avg_logprob` 的指数转换作为近似。
- 仍缺失时将 `confidence` 置为 `null`，以便下游进行后续推断或忽略。
- 降级切分采用线性插值，无法保证与真实对齐完全一致；建议结合 VAD 或外部对齐器进一步优化。

### 验证与排错
- `words` 数组为空：检查 `scripts/verify_env.py` 输出中关于 `word_timestamps` 的提示，确认 faster-whisper 版本 ≥ 0.9 且模型支持词级输出。
- 时间戳出现逆序：在 `--verbose` 模式下查看 warning，同时检查 `words.json` 中 `meta.postprocess.word_monotonicity_fixes` 的值。
- 中文/日文词粒度过粗：这是降级策略的限制，可在后续集成更精细的分词器（如 MeCab、Jieba）或启用额外对齐工具。
- 再次运行 `python scripts/verify_env.py` 可看到 Round 8 增加的 `word_timestamps` 支持检测。

### 常用参数与调优建议
- `--model`：可选择 `tiny`/`base`/`small`/`medium`/`large-v3`，模型越大准确率越高、资源占用越大。
- `--compute-type`：
  - `int8_float16`：推荐在大多数 CPU/GPU 上使用，显著降低内存占用。
  - `int8`：适合 Windows CPU 或内存紧张的环境。
  - `float16`：Apple Silicon / GPU 环境速度较快。
  - `float32`：最稳妥但占用最大，仅在调试时使用。
- `--device`：`auto` 会优先选择 GPU，若需强制 CPU 可指定 `--device cpu`。
- `--beam-size`：减小到 1 可以大幅提速，代价是准确率下降。
- `--temperature`：保持 0.0 等价于纯 beam search，增大可提高多样性但速度略慢。
- `--vad-filter`：Round 7 仅记录该参数，实际 VAD 逻辑会在 Round 8/9 进一步增强。

以上参数既可通过 CLI 传递，也可在 `config/default.yaml` 的 `runtime` 区域设置默认值：

```yaml
runtime:
  backend: faster-whisper
  compute_type: int8_float16
  device: auto
  beam_size: 5
  temperature: 0.0
  vad_filter: false
  chunk_length_s: null
```

### 常见错误与排查
- **模型路径不存在或缺少文件**：重新执行 `scripts/download_model.py --backend faster-whisper --model <name>`；若使用自定义路径，请确认 CLI 与配置文件保持一致。
- **`ffprobe` 不可用**：
  - 运行 `scripts/setup.sh --use-system-ffmpeg false` 下载静态构建。
  - 或使用系统包管理器安装：`sudo apt install ffmpeg`、`brew install ffmpeg`、`winget install ffmpeg` 等。
- **内存不足/加载失败**：
  - 改用更小模型（如 `small` 或 `base`）。
  - 设置 `--compute-type int8` 并降低 `--beam-size`。
- **CPU 推理过慢**：
  - 将 `--beam-size` 调为 1，并保持 `--temperature 0`。
  - 在拥有 GPU 的环境安装 `torch` 以启用 GPU 路径。
- **`verify_env.py` 模型加载测试失败**：检查模型目录是否完整，或尝试删除后重新下载；若错误指向显卡/驱动，请切换为 `--device cpu` 并重新运行。

### 手动烟雾测试（推荐）
1. 准备 5~15 秒的短音频（可使用手机录制语音）。
2. 运行：
   ```bash
   python -m src.cli.main --input /path/to/audio.wav --backend faster-whisper --out-dir ./out --verbose true
   ```
3. 检查 `out/<name>.segments.json`：确认 `segments` 非空、时长与实际音频接近；`words.json` 应含有空数组但结构完整。
4. 若生成 `.error.txt`，打开文件查看提示并按上文排查。

## 后端架构与 Round 3 说明
Round 3 引入统一接口 `ITranscriber`，所有后端在构造时接受 `model`、`language` 与任意扩展参数，并实现 `transcribe_file` 方法返
回标准化的段级结构。`src/asr/backends/__init__.py` 维护了名称到实现的注册表，并提供 `create_transcriber` 工厂函数，未来新增的
`whisper.cpp` 等后端只需在该字典中注册即可。

当前注册的后端：
- **dummy**：沿用之前的占位实现，根据文件名生成词级与段级伪数据。
- **faster-whisper**：Round 7 起启用真实 CTranslate2 推理，生成段级结果并记录解码参数；`words` 数组暂为空，Round 8 将补齐词级时间戳。

管线 `src/asr/pipeline.py` 通过工厂创建后端，逐文件调用 `transcribe_file` 并落盘：
- `<name>.segments.json`：包含语言、占位时长、后端信息、meta 扩展与段级数组。
- `<name>.words.json`：保留同样的顶层信息，`words` 数组在 faster-whisper 占位实现中为空，为未来词级时间戳预留结构。
- 若单个文件失败，会生成 `<name>.error.txt` 保存错误详情，其他文件继续处理。

CLI 在 Round 3 中新增了对 `--backend` 的枚举校验，可在 verbose 模式下打印已选择的后端与语言配置。示例命令：
```bash
# 使用 dummy 后端（占位）
python -m src.cli.main --input ./samples --backend dummy --out-dir ./out --verbose

# 使用占位 faster-whisper 后端（不做真实识别）
python -m src.cli.main --input ./samples --backend faster-whisper --out-dir ./out --verbose

# 查看测试
pytest -q
```

## 目录结构
```
ASRProgram/
├── README.md                  # 项目说明文档
├── pyproject.toml             # 项目元数据与打包配置
├── requirements.txt           # Python 依赖列表
├── .gitignore                 # Git 忽略规则
├── config/
│   └── default.yaml           # CLI 默认配置示例
├── scripts/
│   ├── run.sh                 # Bash 快速启动脚本（逐行注释）
│   ├── run.ps1                # PowerShell 快速启动脚本（逐行注释）
│   └── verify_env.py          # 环境检查脚本（逐行注释）
├── src/
│   ├── asr/
│   │   ├── __init__.py        # ASR 子包初始化
│   │   ├── pipeline.py        # 执行主流程的管线逻辑
│   │   └── backends/
│   │       ├── __init__.py    # 后端注册表
│   │       ├── base.py        # 转写接口定义
│   │       ├── dummy.py       # Dummy 占位实现
│   │       └── faster_whisper_backend.py  # faster-whisper 占位实现
│   ├── cli/
│   │   └── main.py            # CLI 入口
│   └── utils/
│       ├── audio.py           # 音频相关工具（占位探测）
│       ├── io.py              # 原子写入与 JSON 工具
│       └── logging.py         # 日志配置工具
├── tests/
│   ├── test_backend_interface.py  # 验证统一接口结构
│   └── test_dummy_backend.py      # dummy 后端端到端测试
└── out/
    └── .gitkeep               # 输出目录占位，保持版本控制
```

## CLI 参数说明
| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--input` | 必填 | 单个音频文件或包含音频文件的目录，支持扩展名 `.wav,.mp3,.m4a,.flac` |
| `--out-dir` | `out` | 输出 JSON 文件所在目录 |
| `--backend` | `dummy` | 指定使用的转写后端，当前提供 `dummy` 与 `faster-whisper` 两种占位实现 |
| `--language` | `auto` | 转写语言占位信息，会写入输出 JSON |
| `--segments-json` | `true` | 是否写出段级 JSON 文件 |
| `--overwrite` | `false` | 是否覆盖已有输出文件 |
| `--num-workers` | `1` | 预留的并发参数，当前轮次串行执行 |
| `--dry-run` | `false` | 若为 `true`，仅打印计划，不生成文件 |
| `--verbose` | `false` | 控制日志输出级别 |

## 输出文件格式示例
`words.json` 片段：
```json
{
  "language": "auto",
  "duration_sec": 0.0,
  "backend": {
    "name": "dummy",
    "version": "0.1.0",
    "model": "synthetic"
  },
  "meta": {
    "note": "placeholder for round 3",
    "generated_at": "2024-01-01T00:00:00Z"
  },
  "words": [
    {
      "text": "sample",
      "start": 0.0,
      "end": 0.5,
      "confidence": 0.9,
      "segment_id": 0,
      "index": 0
    }
  ]
}
```

`segments.json` 片段：
```json
{
  "language": "auto",
  "duration_sec": 0.0,
  "backend": {
    "name": "dummy",
    "version": "0.1.0",
    "model": "synthetic"
  },
  "meta": {
    "note": "placeholder for round 3",
    "generated_at": "2024-01-01T00:00:00Z"
  },
  "segments": [
    {
      "id": 0,
      "text": "[DUMMY] sample segment",
      "start": 0.0,
      "end": 1.0,
      "avg_conf": 0.9,
      "words": [
        {
          "text": "sample",
          "start": 0.0,
          "end": 0.5,
          "confidence": 0.9,
          "segment_id": 0,
          "index": 0
        }
      ]
    }
  ]
}
```

## 不提交二进制策略
* `.gitignore` 排除了常见的缓存、虚拟环境与输出目录；`out/` 目录仅保存运行结果，不纳入版本控制，仅保留 `.gitkeep` 占位。
* 所有脚本与源码均为纯文本，严禁提交二进制文件或模型权重。

## 常见问题
1. **为何输出为占位文本？** Round 3 仍在搭建骨架，后续轮次才会集成真实 ASR 模型。
2. **可以更换后端吗？** 当前提供 `dummy` 与 `faster-whisper` 占位实现，可按照 `ITranscriber` 接口扩展更多后端。
3. **输出文件是否可覆盖？** 默认不会覆盖，可通过 `--overwrite true` 开启。

## 后续计划
* Round 5 起增加更完整的环境自检与依赖安装脚本。
* Round 7/8 目标接入 faster-whisper 的真实推理与词级时间戳。
* Round 9 探索多进程/多线程并发处理。

## Round 4：Pipeline 与落盘规则
Round 4 聚焦于让占位推理流程具备正式版的落盘行为与容错策略：扫描输入、筛选扩展名、原子写入、覆盖策略、错误旁路与 dry-run/verbose 行为全部统一。下图展示完整流程：
```
输入路径 → 递归扫描 → 过滤扩展名 → 顺序处理 →
  ├─(dry-run) 仅打印计划
  └─(正常) 调用后端 → 生成 words/segments 数据 → 原子写入 out/
                               └─若失败 → 写入 .error.txt → 继续下一个文件
最终汇总统计并打印 Summary
```

### 原子写入与覆盖策略
- **原子写入**：所有 JSON/文本结果都会先写入同目录的 `.tmp` 文件，随后通过 `os.replace` 原子替换，保证即使中途崩溃也不会留下半截文件。
- **覆盖策略**：默认 `--overwrite false`，若目标 `*.words.json` 或 `*.segments.json` 已存在则直接跳过并视为成功；只有显式指定 `--overwrite true` 才会重写。

### 错误旁路机制
- 单个文件处理失败时，会在 `out/<basename>.error.txt` 中记录异常摘要与可选的回溯，其他文件继续执行。
- CLI 汇总中的 `failed` 数量与 `errors` 列表会同步记录失败条目，便于自动化系统统计。
- 这类错误不会让进程返回非零退出码，确保批量任务不会被单个文件拖垮。

`.error.txt` 示例：
```
RuntimeError: synthetic failure
Traceback (most recent call last):
  ...
```

### 常用命令示例
```bash
# 扫描目录，生成 words/segments 占位 JSON
python -m src.cli.main --input ./samples --out-dir ./out --backend dummy

# 不落盘，仅演练
python -m src.cli.main --input ./samples --dry-run true --verbose

# 不覆盖已存在结果
python -m src.cli.main --input ./samples --overwrite false

# 强制覆盖（谨慎使用）
python -m src.cli.main --input ./samples --overwrite true
```

### 输出目录规范
执行成功后，`out/` 下至少包含 `*.words.json`（无论后端是否提供词级内容都会生成，占位时 words 数组为空），若 `--segments-json true` 则额外生成 `*.segments.json`。所有写入均在 `out/` 根目录完成，方便后续对接词级时间戳或其他后处理逻辑。

### dry-run / verbose 行为一致化
- `--dry-run true`：不创建输出目录、不落盘任何文件，只打印计划动作；`Summary` 中依旧会统计 `succeeded`，以便上层调度系统了解处理总量。
- `--verbose true`：打印扫描到的文件列表、目标输出路径、覆盖/跳过决策以及最终汇总详情，便于问题排查。


## Round 10：whisper.cpp 后端
whisper.cpp 提供高度可移植的 CPU 推理实现，适合以下场景：
* **资源受限**：在没有 GPU、内存有限或仅能使用老旧 CPU 的环境中，whisper.cpp 的量化模型（GGML/GGUF）能显著降低内存占用。
* **跨平台部署**：需要在 Windows/Mac/Linux 甚至 ARM 设备上分发独立可执行文件时，whisper.cpp 的单一二进制更易集成。
* **无外部依赖**：构建/下载后即可离线运行，适合内网或无法访问 Python 包镜像的场景。

### 安装方式
1. **一键脚本（推荐）**
   ```bash
   # Bash / zsh（macOS、Linux）
   bash scripts/setup.sh --with-whispercpp true --model medium

   # PowerShell / pwsh（Windows、跨平台）
   pwsh -File scripts/setup.ps1 -with-whispercpp true -model medium
   ```
   * `--with-whispercpp true` 会在 `.cache/whispercpp/` 下优先尝试下载预编译二进制，若失败自动回退到源码构建（需 `git`、`cmake` 与编译器）。
   * 成功后脚本会把可执行文件存放于 `<cache-dir>/whispercpp/bin/`，并将路径透传给 `scripts/verify_env.py` 进行体检。
   * `--model` 仍决定 faster-whisper 与 whisper.cpp 共用的模型规格；GGUF/GGML 会下载到 `<models-dir>/whisper.cpp/<model>/`。

2. **手动安装（备用）**
   ```bash
   git clone https://github.com/ggerganov/whisper.cpp.git
   cd whisper.cpp
   cmake -B build -DCMAKE_BUILD_TYPE=Release
   cmake --build build --config Release
   ./build/bin/main --help
   ```
   * 将生成的 `main`/`main.exe` 放入任意可写目录，并在 `config/default.yaml` 的 `runtime.whisper_cpp.executable_path` 中填写绝对路径。
   * 若需要自定义编译选项或交叉编译，请参考 whisper.cpp 官方 README。

### 模型准备
* **GGML vs GGUF**：GGML 为传统格式，GGUF 为新一代量化格式，两者都可被 whisper.cpp 加载；`scripts/download_model.py` 已预置常见映射，也可通过 `--model-url` 指定自定义权重。
* **存放位置**：推荐使用默认目录 `~/.cache/asrprogram/models/whisper.cpp/<model>/`，下载脚本会返回实际文件路径，安装脚本在成功后会打印总结。
* **大小建议**：若模型体积远小于以下值，通常意味着下载不完整（或选择了更高量化等级）：
  | 规格 | 参考大小 |
  | --- | --- |
  | tiny | ~75 MB |
  | base | ~145 MB |
  | small | ~480 MB |
  | medium | ~1.5 GB |
  | large-v3 | ~3.05 GB |

### 运行示例
```bash
# 启用 whisper.cpp 后端，自动生成词级时间戳与段级 JSON
python -m src.cli.main \
  --input ./samples \
  --backend whisper.cpp \
  --language ja \
  --segments-json true \
  --verbose
```
运行前请确保 `config/default.yaml`（或 CLI 参数）中已经填写 `runtime.whisper_cpp.executable_path` 与 `runtime.whisper_cpp.model_path`。

### 关键参数
以下参数既可在 `config/default.yaml` 中配置，也可通过 CLI（若后续轮次开放）覆盖：
* `threads`：CPU 线程数，设为物理核心数可提升吞吐；设为 0 由 whisper.cpp 自动决定。
* `beam_size`：解码候选宽度，1~3 更快但准确率略降；5 为兼容默认值。
* `temperature`：温度采样参数，建议保持 0.0 以复现 deterministic 行为。
* `max_len`：输出最大 token 数（整数），可防止异常长段。
* `prompt`：初始提示文本，适合热词或延续上下文。
* `print_progress`：是否输出进度条；在批量任务或日志敏感环境建议保持 `false`。
* `timeout_sec`：子进程执行超时（秒），设置后可在异常卡死时自动终止。

### 常见问题排查
* **找不到可执行文件**：
  - 确认安装脚本输出的路径是否存在；若自行下载，请执行 `chmod +x /path/to/main` 并在配置中写入绝对路径。
  - Windows 用户请避免路径中包含中文或空格，必要时将可执行文件放在 `C:\whispercpp\bin\` 等简短目录。
* **模型未检测到**：
  - 运行 `python scripts/verify_env.py --whispercpp-model /path/to/model.gguf` 查看报告；若提示体积不足，请重新下载或检查是否为量化版本。
  - 若使用私有仓库或需要鉴权的 GGUF 链接，可在 `download_model.py` 中通过 `--model-url` 指定完整 URL。
* **解析失败**：
  - 某些旧版本不支持 `--output-json`，安装脚本会自动回退到 TSV 解析；若出现格式差异，请更新至最新稳定版本或在命令中追加 `--output-json`。
* **缺失词置信度**：
  - 少数构建不会输出 `prob` 字段，解析逻辑会将词级置信度设为 `None`，并按段内平均置信度估算；需要精确置信度时建议升级可执行文件。
* **性能调优**：
  - 将 `threads` 设为物理核心数、`beam_size` 设为 1~3 可显著降低延迟。
  - 关闭 `print_progress` 以减少 IO 开销；批量任务可结合 Round 9 的 `--num-workers` 并发能力。


## Round 11：I/O 完整性、文件锁与断点续跑
在并发批处理的基础上，Round 11 聚焦“落盘可靠性”。本轮实现跨平台文件锁、输入哈希校验、部分产物识别与 Manifest 追踪，确保在并发、重跑、崩溃恢复等场景下仍能获得可信且可审计的结果。

### 为什么需要文件锁与哈希
* **跨进程/多线程安全**：`<name>.lock` 文件配合 `fcntl/msvcrt` 实现独占锁，同一音频在任意时刻只会被一个工作者处理，避免重复写入与竞争条件。
* **输入完整性保障**：在写入 `*.words.json` / `*.segments.json` 时记录 `audio.hash_sha256`，下次运行会重新计算哈希并比对，快速识别“陈旧”产物。
* **断点续跑有据可查**：即使执行中断，也能通过哈希与 Manifest 判断哪些文件已经安全落盘、哪些需要重试或强制覆盖。

### Manifest 的作用
* **统一追踪**：所有任务会在 `out/_manifest.jsonl` 追加 `started/succeeded/failed/skipped` 记录，包含输入路径、哈希值、耗时、输出文件与错误分类。
* **故障审计**：Manifest 会记录 `RetryableError`/`NonRetryableError`/`StaleResult` 等类型，便于区分临时性故障与需要人工介入的问题。
* **断点恢复**：结合 `load_index` 可快速加载最新状态，判断是否需要重跑或直接跳过，同时 `--force` 可强制忽略历史记录。

### 新增 CLI 参数
| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--integrity-check true|false` | `true` | 是否计算 SHA-256 并写入/比对 `audio.hash_sha256`。关闭后会跳过哈希计算以提升性能。 |
| `--lock-timeout <sec>` | `30` | 获取 `<name>.lock` 的超时时间（秒），超时会记录 `LockTimeout` 并跳过任务。 |
| `--cleanup-temp true|false` | `true` | 是否在持锁后清理历史 `.tmp/.partial/.lock` 残留，避免崩溃遗留半成品。 |
| `--manifest-path <path>` | `out/_manifest.jsonl` | 指定 Manifest 输出位置，可指向共享目录以跨进程统计。 |
| `--force true|false` | `false` | 忽略现有产物与 Manifest 记录，强制对所有输入重新转写。 |

### 示例命令
```bash
# 启用完整性校验与文件锁（默认即开启）
python -m src.cli.main \
  --input ./audio_dir \
  --backend faster-whisper \
  --num-workers 4 \
  --integrity-check true \
  --lock-timeout 30 \
  --segments-json true \
  --verbose
```

### 故障排查
* **一直等待锁**：检查是否有其它进程仍在处理同一文件，必要时增大 `--lock-timeout` 或主动终止僵尸进程。
* **“stale result; use --overwrite true to rebuild”**：输入文件内容已变更但未开启覆盖，使用 `--overwrite true` 或 `--force true` 重新生成。
* **残留 `.tmp/.partial` 文件**：确认 `--cleanup-temp true` 已开启，或手动删除输出目录中的临时文件后再运行。
* **Manifest 体积过大**：可定期将 `out/_manifest.jsonl` 归档至其它位置，并按日期切分；读取历史记录时利用 `load_index` 或按需 grep 指定日期。


## Round 14：测试与校验
本轮聚焦“可验证、可回归”的基础设施，引入 words/segments JSON Schema、完善测试体系，并提供轻量级 CI 工作流。

### Schema 校验
* `schemas/words.schema.json` 与 `schemas/segments.schema.json` 采用 JSON Schema 2020-12 草案，约束字段类型、必填项以及置信度/时间戳范围。
* 顶层 `schema` 字段分别固定为 `asrprogram.wordset.v1` 与 `asrprogram.segmentset.v1`，便于后续版本演进时明确兼容窗口。
* `src/utils/schema.py` 提供 `validate_words`/`validate_segments` 工具函数，会先执行 JSON Schema 校验，再补充检查 `end >= start` 等跨字段约束，并返回 `jsonschema.ValidationError` 以便测试捕获。

### 本地测试与冒烟
1. 安装开发测试依赖：
   ```bash
   pip install -r requirements-dev.txt
   ```
2. 运行单元/集成测试（默认跳过未来的 `@pytest.mark.slow`）：
   ```bash
   pytest -q
   ```
3. 执行一键冒烟（Bash 示例，PowerShell 亦提供 `scripts/smoke_test.ps1`）：
   ```bash
   bash scripts/smoke_test.sh
   ```
   脚本会创建临时目录、生成空白音频文件、调用 dummy 后端，并使用 `src.utils.schema` 对产物逐一校验，成功后打印 `OK` 提示。

### Schema 版本与兼容性策略
* `v1` 版本聚焦结构约束，允许在 `meta`、`backend` 等对象内追加新字段，同时保持 `additionalProperties: false` 对核心字段的约束。
* 未来若引入破坏性调整（如词条字段重命名），将递增 schema 名称（例如 `asrprogram.wordset.v2`），并在工具层实现向后兼容或迁移脚本。
* 测试覆盖了典型非法数据（负时间戳、`end < start`、缺字段），确保 schema 演进时不会回归。

### 轻量 CI 策略
* `.github/workflows/ci.yml` 仅执行 `pip install -r requirements-dev.txt` 与 `pytest -q --maxfail=1`，不触发模型下载或真实推理，保证云端运行速度。
* 需要真实后端/模型的测试请标记为 `@pytest.mark.slow`，默认不在 CI 中执行，可在自管 Runner 或本地按需运行。
* 冒烟脚本适合在发布前或部署后快速验收，结合 schema 校验确保 JSON 契约未被破坏。
