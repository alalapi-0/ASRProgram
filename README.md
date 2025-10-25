# ASRProgram

## 项目简介
ASRProgram 是一个演示性项目，用于将输入音频文件的元信息转化为词级和段级 JSON 结构；在 Round 1 中，所有识别结果均由占位逻辑生成，仅用于打通扫描输入、模拟转写与落盘的完整流程。

## 快速开始
1. **创建虚拟环境**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows PowerShell 使用 .venv\\Scripts\\Activate.ps1
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
6. **正常运行（目录扫描，dummy 占位生成）**
   ```bash
   python -m src.cli.main --input ./samples --out-dir ./out --backend dummy --segments-json true
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
│   │       └── dummy.py       # Dummy 占位实现
│   ├── cli/
│   │   └── main.py            # CLI 入口
│   └── utils/
│       ├── audio.py           # 音频相关工具（占位探测）
│       ├── io.py              # 原子写入与 JSON 工具
│       └── logging.py         # 日志配置工具
├── tests/
│   └── test_dummy_backend.py  # pytest 用例
└── out/
    └── .gitkeep               # 输出目录占位，保持版本控制
```

## CLI 参数说明
| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--input` | 必填 | 单个音频文件或包含音频文件的目录，支持扩展名 `.wav,.mp3,.m4a,.flac` |
| `--out-dir` | `out` | 输出 JSON 文件所在目录 |
| `--backend` | `dummy` | 指定使用的转写后端，本轮仅提供 `dummy` |
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
  "metadata": {
    "language": "auto",
    "duration_sec": 0.0,
    "backend": {
      "name": "dummy",
      "version": "0.1.0"
    },
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
  "metadata": {
    "language": "auto",
    "duration_sec": 0.0,
    "backend": {
      "name": "dummy",
      "version": "0.1.0"
    },
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
1. **为何输出为占位文本？** Round 1 仅构建端到端骨架，后续轮次才会集成真实 ASR 模型。
2. **可以更换后端吗？** 当前仅提供 `dummy`，后续可按照 `ITranscriber` 接口扩展。
3. **输出文件是否可覆盖？** 默认不会覆盖，可通过 `--overwrite true` 开启。

## 后续计划
* Round 2 起将增加更完整的环境自检与依赖安装脚本。
* Round 5 计划接入真实音频探测工具（例如 `ffprobe`）。
* Round 7/8 目标接入 faster-whisper 并提供真实的词级时间戳。

