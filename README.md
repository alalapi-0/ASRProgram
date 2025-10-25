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

