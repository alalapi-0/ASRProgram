#!/usr/bin/env bash
set -euo pipefail  # 遇到错误即退出，未定义变量视为错误，并在管道中保留错误。
echo "=== Whisper large-v2 中文转写自动脚本 ==="  # 打印脚本标题。
# 检查 ffmpeg 是否可用并给出友好提示。
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "⚠️ 未检测到 ffmpeg，可通过 sudo apt install ffmpeg 安装。"  # 提示用户安装 ffmpeg。
fi

# 调用 Python 快速启动脚本并传入固定参数。
python3 tools/asr_quickstart.py \
  --input "./Audio" \
  --out-dir "./out" \
  --models-dir "$HOME/.cache/asrprogram/models" \
  --download \
  --no-prompt \
  --num-workers 1 \
  --tee-log "out/run_$(date +%F_%H%M%S).log"
