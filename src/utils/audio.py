"""提供音频路径筛选与 ffprobe 时长探测工具函数。"""  # 文件说明。
# 导入 os 模块以处理跨平台路径与扩展名。
import os
# 导入 subprocess 以调用外部 ffprobe 命令获取音频时长。
import subprocess
# 导入 typing.Optional 作为类型注释，便于返回类型说明。
from typing import Optional

# 定义默认支持的音频扩展名列表，便于统一维护。
DEFAULT_AUDIO_EXTS = [".wav", ".mp3", ".m4a", ".flac"]


# 定义音频路径判定函数，复用之前轮次的逻辑。
def is_audio_path(path: str | os.PathLike[str], allowed_exts: Optional[list[str]] = None) -> bool:
    """判断给定路径是否属于受支持的音频类型。"""
    # 若未指定扩展名列表，则使用默认集合。
    allowed = allowed_exts or DEFAULT_AUDIO_EXTS
    # 将允许的扩展名统一转换为小写集合，便于快速查找。
    allowed_set = {item.lower() for item in allowed}
    # 将输入路径转换为字符串以避免 Path/str 差异。
    string_path = os.fspath(path)
    # 通过 os.path.splitext 拆分扩展名，并转换为小写忽略大小写差异。
    _, ext = os.path.splitext(string_path)
    # 仅在扩展名存在且位于允许集合中时返回 True。
    return bool(ext) and ext.lower() in allowed_set


# 定义通过 ffprobe 探测音频时长的函数。
def probe_duration(path: str | os.PathLike[str]) -> float:
    """调用 ffprobe 获取音频持续时间（单位：秒）。"""
    # 将路径转换为字符串，确保 ffprobe 能处理包含空格或非 ASCII 的路径。
    string_path = os.fspath(path)
    # 构造 ffprobe 命令：只输出 duration 字段，避免冗余日志。
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nw=1:nk=1",
        string_path,
    ]
    try:
        # 调用 subprocess.run 执行命令，捕获标准输出。
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        # 当系统缺少 ffprobe 时返回 0.0，并提示用户安装。
        return 0.0
    # 若命令执行失败或无输出，同样返回 0.0，后续由调用方决定是否告警。
    if completed.returncode != 0 or not completed.stdout:
        return 0.0
    # 读取输出并去除首尾空白，解析为浮点数。
    output = completed.stdout.strip()
    try:
        # 若解析成功则返回真实时长。
        return float(output)
    except ValueError:
        # 若输出非数字（如旧版 ffprobe），则返回 0.0 作为保守值。
        return 0.0
