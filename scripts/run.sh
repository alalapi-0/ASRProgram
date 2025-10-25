#!/usr/bin/env bash
# 设置严格模式，以便在出现错误或未定义变量时立即退出。
set -euo pipefail
# 切换到仓库根目录，确保脚本从正确位置执行。
cd "$(dirname "$0")/.."
# 提示当前正在执行的命令，便于用户了解流程。
echo "[ASRProgram] Running dummy pipeline via python -m src.cli.main"
# 调用 Python CLI，默认扫描 ./samples 目录，可通过传入参数覆盖。
python -m src.cli.main "$@"
