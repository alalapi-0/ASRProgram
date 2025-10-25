"""音频相关的占位工具函数，负责路径筛选与时长探测。"""
# 导入 os 模块以便读取文件扩展名。
import os

# 定义音频路径判定函数，默认使用项目约定的扩展名集合。
def is_audio_path(path: str | os.PathLike[str], allowed_exts: list[str] | None = None) -> bool:
    """判断给定路径是否具有允许的音频扩展名。"""
    # 若未显式提供扩展名列表，则使用项目约定的四种常见格式。
    allowed = allowed_exts or [".wav", ".mp3", ".m4a", ".flac"]
    # 将允许的扩展名统一转换为小写集合，便于后续快速匹配。
    allowed_set = {item.lower() for item in allowed}
    # 将路径转换为字符串以便拆分扩展名。
    string_path = os.fspath(path)
    # 使用 os.path.splitext 拆分扩展名，统一转换为小写以忽略大小写差异。
    _, ext = os.path.splitext(string_path)
    # 返回扩展名是否存在且位于允许列表中。
    return bool(ext) and ext.lower() in allowed_set

# 定义时长探测函数，在本轮依旧返回占位值。
def probe_duration(path: str | os.PathLike[str]) -> float:
    """返回音频文件的持续时间，占位实现始终为 0.0 秒。"""
    # Round 4 仍未集成 ffprobe，保持占位实现，后续轮次会替换为真实探测。
    return 0.0
