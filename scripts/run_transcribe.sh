#!/usr/bin/env bash  # 指定解释器为系统默认 bash
# 固定中文 + large-v3 的极简启动入口
# 首次使用请赋权：chmod +x scripts/run_transcribe.sh
python3 tools/asr_quickstart.py  # 调用 Python 主脚本
# 运行结束后可在终端查看输出日志
