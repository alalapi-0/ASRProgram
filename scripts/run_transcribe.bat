@echo off & REM 关闭命令回显，保持输出整洁
REM 固定中文 + large-v3 的极简启动入口
REM 从仓库根目录双击可运行；或在命令行输入：scripts\run_transcribe.bat
python tools\asr_quickstart.py & REM 调用 Python 主脚本
REM 暂停窗口，方便查看执行结果
pause & REM 等待用户查看输出
