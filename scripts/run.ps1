#!/usr/bin/env pwsh
# 切换到脚本所在目录的上级，即仓库根目录。
Set-Location -Path (Join-Path -Path $PSScriptRoot -ChildPath "..")
# 输出提示信息，说明脚本正在调用的命令。
Write-Host "[ASRProgram] Running dummy pipeline via python -m src.cli.main"
# 调用 Python 模块作为 CLI，传递所有用户参数。
python -m src.cli.main @Args
