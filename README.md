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

## 后端架构与 Round 3 说明
Round 3 引入统一接口 `ITranscriber`，所有后端在构造时接受 `model`、`language` 与任意扩展参数，并实现 `transcribe_file` 方法返
回标准化的段级结构。`src/asr/backends/__init__.py` 维护了名称到实现的注册表，并提供 `create_transcriber` 工厂函数，未来新增的
`whisper.cpp` 等后端只需在该字典中注册即可。

当前注册的后端：
- **dummy**：沿用之前的占位实现，根据文件名生成词级与段级伪数据。
- **faster-whisper**：全新占位实现，不导入真实库，仅校验输入路径与扩展名，返回单段结果，`words` 暂为空数组，并在元信息中说明
  Round 7/8 才会启用真实推理与词级时间戳。

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

