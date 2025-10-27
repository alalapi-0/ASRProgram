@echo off
REM === Whisper large-v2 中文转写自动脚本 ===
echo === Whisper large-v2 中文转写自动脚本 ===
REM 调用 Python 快速启动脚本并传入固定参数。
python tools\asr_quickstart.py ^
  --input ".\Audio" ^
  --out-dir ".\out" ^
  --models-dir "%USERPROFILE%\.cache\asrprogram\models" ^
  --download ^
  --no-prompt ^
  --num-workers 1 ^
  --tee-log "out\run_%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%.log"
pause
