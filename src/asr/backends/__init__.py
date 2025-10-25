"""后端注册表，用于根据名称返回具体实现。"""
# 导入 typing.TYPE_CHECKING 用于仅在类型检查时导入接口。
from typing import TYPE_CHECKING, Dict, Type
# 导入 dummy 后端以注册。
from .dummy import DummyTranscriber
# 导入 faster-whisper 后端以注册。
from .faster_whisper_backend import FasterWhisperTranscriber
# 如果处于类型检查阶段，导入接口定义以提供准确提示。
if TYPE_CHECKING:
    from .base import ITranscriber

# 定义一个字典，映射后端名称到具体类，后续新增后端时在此注册。
BACKENDS: Dict[str, Type["ITranscriber"]] = {
    # dummy 名称对应 DummyTranscriber 类。
    "dummy": DummyTranscriber,
    # faster-whisper 名称对应真实的 faster-whisper 实现。
    "faster-whisper": FasterWhisperTranscriber,
}

# 提供工厂函数，根据名称创建后端实例并透传额外参数。
def create_transcriber(name: str, **kwargs) -> "ITranscriber":
    """根据后端名称返回对应的转写器实例。"""
    # 尝试在注册表中查找给定名称。
    if name not in BACKENDS:
        # 若不存在，抛出带详细信息的错误，提示如何扩展。
        raise ValueError(
            f"Unsupported backend '{name}'. Available options: {', '.join(BACKENDS)}"
        )
    # 找到对应类后实例化并返回，kwargs 可包含语言、模型等配置。
    return BACKENDS[name](**kwargs)

