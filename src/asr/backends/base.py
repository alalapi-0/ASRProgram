"""定义转写后端必须实现的接口。"""
# 导入 abc 模块以创建抽象基类。
from abc import ABC, abstractmethod

# 定义抽象基类，约束后端需要实现的行为。
class ITranscriber(ABC):
    """所有转写后端都必须提供文件级转写能力。"""

    # 声明抽象方法，子类必须实现具体逻辑。
    @abstractmethod
    def transcribe_file(self, input_path: str, language: str) -> dict:
        """将给定路径的音频文件转写为标准化数据结构。"""
        # 抽象方法无需实现，子类必须提供返回值。
        raise NotImplementedError
