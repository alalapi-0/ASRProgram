# -*- coding: utf-8 -*-  # 指定文件编码为 UTF-8，兼容中文注释
"""
ASR QuickStart（固定大模型，中文转写）
-----------------------------------
- 固定后端：faster-whisper
- 固定语言：zh（中文）
- 固定模型：large-v3（不再提供 tiny/small 等选项）
- 只让用户输入：输入路径（文件或文件夹）和输出目录
- 自动下载模型（scripts/download_model.py）
- Windows / Linux(Ubuntu) 通用
"""  # 说明脚本用途与关键特性

import os  # 引入操作系统相关工具（环境变量、路径）
import sys  # 获取当前 Python 解释器路径等信息
import subprocess  # 用于调用外部命令
from pathlib import Path  # 更方便地处理跨平台路径

REPO_ROOT = Path(__file__).resolve().parents[1]  # 计算仓库根目录（tools/ 上一层）
DEFAULT_MODELS_DIR = os.path.expanduser("~/.cache/asrprogram/models")  # 默认模型缓存目录
DEFAULT_INPUT_DIR = str((REPO_ROOT / "audio").resolve())  # 默认输入路径（可自行调整）
DEFAULT_OUTPUT_DIR = str((REPO_ROOT / "out").resolve())  # 默认输出目录

FIXED_MODEL = "large-v3"  # 固定使用的大模型名称
FIXED_BACKEND = "faster-whisper"  # 固定后端类型


def ask(prompt: str, default: str = "") -> str:  # 封装用户输入逻辑
    """简单的交互输入：回车取默认值。"""  # 说明函数作用
    user_input = input(f"{prompt}（回车默认：{default}）：").strip()  # 提示用户输入并去除首尾空格
    return user_input or default  # 若用户未输入内容则返回默认值


def which(cmd: str):  # 判断命令是否在 PATH 中
    """跨平台查找命令是否存在于 PATH 中。"""  # 描述函数功能
    from shutil import which as _which  # 延迟导入以避免顶层命名冲突
    return _which(cmd)  # 返回命令所在路径或 None


def need_ffmpeg_hint():  # 打印缺少 ffmpeg 时的提示
    """缺少 ffmpeg 时输出友好提示。"""  # 告知函数用途
    print("未检测到 ffmpeg/ffprobe。请先安装后再运行：")  # 打印提示信息
    print(" - Windows: 安装 ffmpeg 并把 bin 加入 PATH")  # 给出 Windows 安装建议
    print(" - Ubuntu:  sudo apt-get update && sudo apt-get install -y ffmpeg")  # 给出 Ubuntu 安装建议


def run(cmd, env=None):  # 统一的命令执行函数
    """打印并执行命令，返回退出码。"""  # 说明函数功能
    print("\n$ " + " ".join(cmd))  # 显示即将执行的命令
    return subprocess.call(cmd, env=env)  # 调用子进程并返回其退出码


def download_model(models_dir: str):  # 负责调用下载脚本
    """调用项目自带的下载脚本，确保 large-v3 已就绪。"""  # 描述函数作用
    downloader = REPO_ROOT / "scripts" / "download_model.py"  # 构造下载脚本路径
    if not downloader.exists():  # 检查脚本是否存在
        print("缺少 scripts/download_model.py，无法自动下载模型。请先补齐脚本。")  # 提示缺失信息
        sys.exit(2)  # 返回非零退出码以指示错误
    cmd = [  # 准备下载命令参数列表
        sys.executable, str(downloader),  # 使用当前解释器执行下载脚本
        "--backend", FIXED_BACKEND,  # 指定固定后端
        "--model", FIXED_MODEL,  # 指定固定模型
        "--models-dir", models_dir,  # 指定模型缓存目录
    ]
    exit_code = run(cmd)  # 执行下载命令
    if exit_code != 0:  # 若返回码非零，说明下载失败
        print("模型下载失败，请检查网络或稍后重试。")  # 提示用户下载失败
        sys.exit(exit_code)  # 以下载返回码退出


def main():  # 主流程入口
    """脚本主入口，串联交互、下载与转写步骤。"""  # 概述主流程
    print("=== ASR QuickStart（中文词级转写｜固定 large-v3）===")  # 打印标题信息

    if not which("ffmpeg") or not which("ffprobe"):  # 检查 ffmpeg/ffprobe 是否在 PATH 中
        need_ffmpeg_hint()  # 输出安装提示
        proceed = input("继续运行也行，但可能影响时长探测。是否继续？(y/N)：").strip().lower()  # 询问用户是否继续
        if proceed not in ("y", "yes"):  # 若用户不确认继续
            sys.exit(1)  # 优雅退出

    input_path = ask("输入 文件/文件夹 路径（中文音频所在处）", DEFAULT_INPUT_DIR)  # 获取待转写路径
    output_dir = ask("输出目录（保存 JSON）", DEFAULT_OUTPUT_DIR)  # 获取输出目录
    Path(output_dir).mkdir(parents=True, exist_ok=True)  # 确保输出目录存在

    models_dir = ask("模型缓存目录", DEFAULT_MODELS_DIR)  # 允许用户调整模型缓存目录
    Path(models_dir).mkdir(parents=True, exist_ok=True)  # 确保模型缓存目录存在

    print("\n>>> 检查/下载模型：", FIXED_MODEL)  # 提示即将下载模型
    download_model(models_dir)  # 下载或检查大模型

    print("\n>>> 开始转写（中文，large-v3） ...")  # 打印转写开始提示
    command = [  # 构造 CLI 命令参数
        sys.executable, "-m", "src.cli.main",  # 使用模块形式调用项目 CLI
        "--input", input_path,  # 指定输入路径
        "--out-dir", output_dir,  # 指定输出目录
        "--backend", FIXED_BACKEND,  # 固定后端
        "--language", "zh",  # 固定中文语言
        "--segments-json", "true",  # 启用段级 JSON 输出
        "--overwrite", "true",  # 允许覆盖已有结果
        "--num-workers", "1",  # 固定单线程运行
        "--verbose",  # 输出详细日志
    ]

    env = os.environ.copy()  # 复制当前环境变量
    env["ASRPROGRAM_MODELS_DIR"] = models_dir  # 将模型目录传递给主程序

    result = run(command, env=env)  # 执行转写命令

    if result == 0:  # 判断是否成功
        print("\n✅ 完成。JSON 已保存到：", output_dir)  # 输出成功提示
        print("   - *.segments.json（段级时间轴）")  # 提示段级结果位置
        print("   - *.words.json    （词级时间轴）")  # 提示词级结果位置
    else:  # 失败时进入此分支
        print("\n❌ 转写失败，请上滚查看报错信息。")  # 输出失败提示


if __name__ == "__main__":  # 确保仅在直接运行时执行主流程
    try:  # 捕获键盘中断
        main()  # 执行主函数
    except KeyboardInterrupt:  # 用户使用 Ctrl+C 中断
        print("\n已取消。")  # 给出友好提示
