#!/usr/bin/env pwsh
# 启用严格模式并在出现未捕获错误时终止脚本。
Set-StrictMode -Version Latest
# 将错误处理策略设置为终止，避免忽略异常。
$ErrorActionPreference = 'Stop'
# 计算脚本所在目录，以便定位仓库根路径。
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# 解析仓库根目录，假定脚本位于 scripts/ 子目录。
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir '..')).Path
# 创建临时目录用于输入与输出文件。
$WorkDir = Join-Path ([System.IO.Path]::GetTempPath()) ("asr-smoke-" + [System.Guid]::NewGuid().ToString('N'))
# 创建实际目录结构。
New-Item -ItemType Directory -Path $WorkDir | Out-Null
try {
    # 在临时目录下创建 inputs 与 out 子目录。
    $InputDir = Join-Path $WorkDir 'inputs'
    $OutDir = Join-Path $WorkDir 'out'
    New-Item -ItemType Directory -Path $InputDir | Out-Null
    New-Item -ItemType Directory -Path $OutDir | Out-Null
    # 创建两个空白音频文件，用于触发 dummy 逻辑。
    New-Item -ItemType File -Path (Join-Path $InputDir 'alpha.wav') | Out-Null
    New-Item -ItemType File -Path (Join-Path $InputDir 'beta.wav') | Out-Null
    # 打印提示信息，便于在 CI 日志中定位步骤。
    Write-Host "[smoke] running dummy backend against $InputDir"
    # 将仓库根目录加入 PYTHONPATH，确保 python 可以导入 src 包。
    $env:PYTHONPATH = if ($env:PYTHONPATH) {"$RepoRoot$([System.IO.Path]::PathSeparator)$($env:PYTHONPATH)"} else {$RepoRoot}
    # 调用 CLI 执行 dummy 后端，开启段级输出并覆盖历史文件。
    & python -m src.cli.main --input $InputDir --out-dir $OutDir --backend dummy --segments-json true --overwrite true --dry-run false
    # 构造验证脚本，读取所有 JSON 并执行 schema 校验。
    $ValidationCode = @"
import json
from pathlib import Path
from src.utils.schema import validate_segments, validate_words
output_dir = Path(r"""$OutDir""")
words_files = sorted(output_dir.glob("*.words.json"))
segments_files = sorted(output_dir.glob("*.segments.json"))
for path in words_files:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_words(payload)
for path in segments_files:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_segments(payload)
print(f"OK: validated {len(words_files)} words JSON and {len(segments_files)} segments JSON")
"@
    # 运行验证脚本，若失败将抛出异常终止流程。
    & python -c $ValidationCode
    # 打印成功消息，包含输出目录位置。
    Write-Host "[smoke] success - artifacts stored in $OutDir"
}
finally {
    # 在 finally 中清理临时目录，避免残留文件。
    if (Test-Path $WorkDir) {
        Remove-Item -Recurse -Force $WorkDir
    }
}
