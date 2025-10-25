"""定义所有转写后端共同遵循的抽象接口。"""
# 导入 abc 模块中的 ABC 与 abstractmethod，用于声明抽象基类。
from abc import ABC, abstractmethod
# 导入 typing 的 Any 用于存储扩展参数。
from typing import Any, Dict

# 定义统一的抽象基类，所有具体后端都应继承该类。
class ITranscriber(ABC):
    """约定构造参数与文件级转写方法的抽象基类。"""

    # 定义初始化函数，统一保存模型、语言与额外配置。
    def __init__(
        self,
        model: str | None = None,
        language: str = "auto",
        **kwargs: Any,
    ) -> None:
        """存储后端实例初始化所需的公共属性。"""
        # 将模型名称保存到实例属性，供后续元数据记录。
        self.model_name: str | None = model
        # 将语言代码保存到实例属性，后续转写结果默认采用该值。
        self.language: str = language
        # 将额外的关键字参数保存为字典，便于下一轮扩展更多选项。
        self.extra_options: Dict[str, Any] = dict(kwargs)

    # 声明抽象方法，子类必须实现具体的音频文件转写逻辑。
    @abstractmethod
    def transcribe_file(self, input_path: str) -> dict:
        """给定音频文件路径，返回标准化的段级结果结构。"""
        # 抽象方法不提供实现，仅用于定义接口契约。
        raise NotImplementedError

