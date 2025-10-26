# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码，兼容中文注释与提示
"""
ASR QuickStart（固定大模型，中文转写）
-----------------------------------
- 固定后端：faster-whisper
- 固定语言：zh（中文）
- 固定模型：large-v3（不再提供 tiny/small 等选项）
- 只让用户输入：输入路径（文件或文件夹）和输出目录
- 自动下载模型（scripts/download_model.py）
- Windows / Linux(Ubuntu) 通用
"""

import os  # 导入 os 模块以便处理环境变量与路径展开等操作
import sys  # 导入 sys 模块以便获取当前 Python 解释器路径并执行退出
import subprocess  # 导入 subprocess 用于调用外部命令
from pathlib import Path  # 从 pathlib 导入 Path 以便进行路径操作

# 仓库根目录（tools/ 上一层）
REPO_ROOT = Path(__file__).resolve().parents[1]  # 计算项目根目录，便于定位脚本
# 默认模型缓存目录（与项目其他脚本一致）
DEFAULT_MODELS_DIR = os.path.expanduser("~/.cache/asrprogram/models")  # 设定模型缓存目录，支持用户覆写
# 默认输入/输出目录（可根据需要改成你的常用路径）
DEFAULT_INPUT_DIR = str((REPO_ROOT / "audio").resolve())  # 给出默认输入目录，帮助新用户快速上手
DEFAULT_OUTPUT_DIR = str((REPO_ROOT / "out").resolve())  # 给出默认输出目录，集中保存结果

# 固定使用大模型
FIXED_MODEL = "large-v3"  # 固定模型名称为 large-v3，满足需求
# 固定后端
FIXED_BACKEND = "faster-whisper"  # 固定后端为 faster-whisper，避免其它选项


def detect_hf_token() -> str:
    """读取 Hugging Face Token，优先 HUGGINGFACE_HUB_TOKEN，再 HF_TOKEN。"""

    return os.getenv("HUGGINGFACE_HUB_TOKEN") or os.getenv("HF_TOKEN") or ""


def mask_token(token: str) -> str:
    """仅保留 token 前后 3 位，中间使用 *** 保护。"""

    if len(token) <= 6:
        return "***"
    return f"{token[:3]}***{token[-3:]}"

def ask(prompt: str, default: str = "") -> str:
    """简单的交互输入：回车取默认值。"""
    s = input(f"{prompt}（回车默认：{default}）：").strip()  # 提示用户输入并移除首尾空白
    return s or default  # 若用户直接回车则返回默认值

def which(cmd: str):
    """跨平台查找命令是否在 PATH 内。"""
    from shutil import which as _which  # 延迟导入 shutil.which 函数
    return _which(cmd)  # 返回命令绝对路径，若不存在则返回 None

def need_ffmpeg_hint():
    """缺少 ffmpeg 时的友好提示。"""
    print("未检测到 ffmpeg/ffprobe。请先安装后再运行：")  # 输出缺少 ffmpeg 的提醒
    print(" - Windows: 安装 ffmpeg 并把 bin 加入 PATH")  # 提示 Windows 用户的安装方法
    print(" - Ubuntu:  sudo apt-get update && sudo apt-get install -y ffmpeg")  # 提示 Ubuntu 用户的安装方法

def run(cmd, env=None):
    """打印并执行命令，返回退出码。"""
    print("\n$ " + " ".join(cmd))  # 在执行前打印命令，方便用户查看
    return subprocess.call(cmd, env=env)  # 调用外部命令并返回退出码

def download_model(models_dir: str):
    """调用项目自带的下载器脚本，下载 large-v3 模型到指定目录。"""
    downloader = REPO_ROOT / "scripts" / "download_model.py"  # 构造下载脚本的路径
    if not downloader.exists():  # 检查下载脚本是否存在
        print("缺少 scripts/download_model.py，无法自动下载模型。请先补齐脚本。")  # 给出错误提示
        sys.exit(2)  # 退出程序，返回特定错误码
    token = detect_hf_token()
    if token:
        print(f">>> 检测到 Hugging Face Token：{mask_token(token)}")
    else:
        print(
            ">>> 未检测到 Hugging Face Token。若下载公开模型失败/返回 401，可参考下方提示配置 token。"
        )
    cmd = [
        sys.executable, str(downloader),  # 使用当前解释器执行下载脚本
        "--backend", FIXED_BACKEND,  # 指定后端为 faster-whisper
        "--model", FIXED_MODEL,  # 指定模型为 large-v3
        "--models-dir", models_dir  # 指定模型缓存目录
    ]
    if token:
        cmd.extend(["--hf-token", token])
    rc = run(cmd)  # 执行下载命令
    if rc != 0:  # 判断下载是否成功
        print("模型下载失败，请检查网络或稍后重试。")  # 输出失败提示
        if not token:
            print("如果看到 401/403 错误，请到 https://huggingface.co/settings/tokens 创建 Read token。")
            print("Windows: setx HUGGINGFACE_HUB_TOKEN \"hf_xxx\"")
            print("Linux/macOS: export HUGGINGFACE_HUB_TOKEN=hf_xxx")
            print("或执行：huggingface-cli login --token hf_xxx")
        sys.exit(rc)  # 以原退出码终止程序

def main():
    print("=== ASR QuickStart（中文词级转写｜固定 large-v3）===")  # 在启动时输出标题

    # 简单环境检查：ffmpeg/ffprobe 是否可用（缺失也允许继续）
    if not which("ffmpeg") or not which("ffprobe"):  # 检查 ffmpeg 和 ffprobe 是否都在 PATH 中
        need_ffmpeg_hint()  # 若缺失则输出提示
        proceed = input("继续运行也行，但可能影响时长探测。是否继续？(y/N)：").strip().lower()  # 询问用户是否继续
        if proceed not in ("y", "yes"):  # 若用户不同意继续
            sys.exit(1)  # 退出程序

    # 1) 输入/输出
    in_path = ask("输入 文件/文件夹 路径（中文音频所在处）", DEFAULT_INPUT_DIR)  # 询问音频输入路径
    out_dir = ask("输出目录（保存 JSON）", DEFAULT_OUTPUT_DIR)  # 询问输出目录
    Path(out_dir).mkdir(parents=True, exist_ok=True)  # 确保输出目录存在

    # 2) 模型缓存目录（一般保持默认即可）
    models_dir = ask("模型缓存目录", DEFAULT_MODELS_DIR)  # 询问模型缓存目录
    Path(models_dir).mkdir(parents=True, exist_ok=True)  # 确保模型目录存在

    # 3) 下载模型（若未下载过）
    print("\n>>> 检查/下载模型：", FIXED_MODEL)  # 提示用户即将检查并下载模型
    download_model(models_dir)  # 调用下载函数

    # 4) 开始转写（中文、段级+词级）
    print("\n>>> 开始转写（中文，large-v3） ...")  # 提示即将开始转写
    cmd = [
        sys.executable, "-m", "src.cli.main",  # 使用模块方式调用 CLI 主入口
        "--input", in_path,  # 设置输入路径
        "--out-dir", out_dir,  # 设置输出目录
        "--backend", FIXED_BACKEND,  # 指定后端
        "--language", "zh",          # 固定中文语言
        "--segments-json", "true",   # 启用段级 JSON 输出
        "--overwrite", "true",  # 允许覆盖现有文件
        "--num-workers", "1",        # 固定单线程执行
        "--verbose"  # 打印详细日志
        # 如果你的 CLI 支持，你可以在这里进一步固定设备/精度：
        #   CPU:  --device cpu --compute-type int8 或 int8_float16
        #   CUDA: --device cuda --compute-type float16
    ]

    # 通过环境变量把模型目录传给主程序（若主程序支持读取）
    env = os.environ.copy()  # 复制当前环境变量
    env["ASRPROGRAM_MODELS_DIR"] = models_dir  # 注入模型目录变量，供 CLI 使用

    rc = run(cmd, env=env)  # 执行转写命令

    if rc == 0:  # 判断转写是否成功
        print("\n✅ 完成。JSON 已保存到：", out_dir)  # 提示成功信息
        print("   - *.segments.json（段级时间轴）")  # 提醒段级输出
        print("   - *.words.json    （词级时间轴）")  # 提醒词级输出
    else:
        print("\n❌ 转写失败，请上滚查看报错信息。")  # 提示失败并引导查看日志

if __name__ == "__main__":  # 判断脚本是否直接运行
    try:
        main()  # 调用主函数
    except KeyboardInterrupt:
        print("\n已取消。")  # 捕获 Ctrl+C 并输出友好提示
