"""提供 faster-whisper 后端的占位实现，不执行真实推理。"""
# 导入 pathlib.Path 以校验输入文件路径。
from pathlib import Path
# 从 datetime 导入 datetime 生成占位时间戳。
from datetime import datetime, timezone
# 从 typing 导入 Dict 以描述返回结构。
from typing import Dict
# 导入统一的接口基类以继承。
from .base import ITranscriber

# 定义占位实现的名称常量。
FASTER_WHIPER_NAME = "faster-whisper"
# 定义占位实现的版本号常量。
FASTER_WHIPER_VERSION = "0.0.0-mock"
# 定义允许的音频扩展名集合，用于最小输入校验。
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac"}

# 定义自定义异常，便于调用方区分输入问题与其他错误。
class FasterWhisperBackendError(RuntimeError):
    """在占位实现中表示输入无效或执行失败的异常。"""


# 定义实际的占位转写器类。
class FasterWhisperTranscriber(ITranscriber):
    """构造后端元数据并返回模拟的段级结构。"""

    # 覆写构造函数以记录额外参数，但保持父类逻辑。
    def __init__(
        self,
        model: str | None = None,
        language: str = "auto",
        compute_type: str = "float32",
        device: str = "cpu",
        **kwargs,
    ) -> None:
        """保存初始化时提供的参数信息。"""
        # 调用父类构造函数保存模型、语言与额外参数。
        super().__init__(model=model, language=language, compute_type=compute_type, device=device, **kwargs)
        # 将计算精度设置为实例属性，仅用于记录。
        self.compute_type = compute_type
        # 将设备信息保存，后续轮次可用于真正的模型加载。
        self.device = device
        # 若调用方未指定模型，设置默认的占位模型名称。
        if self.model_name is None:
            self.model_name = "medium"

    # 实现文件转写方法，返回标准占位结果。
    def transcribe_file(self, input_path: str) -> Dict[str, object]:
        """校验输入后生成单段的占位转写结果。"""
        # 将输入路径转换为 Path 对象以执行存在性检查。
        file_path = Path(input_path)
        # 如果文件不存在，则抛出自定义异常提示调用方。
        if not file_path.exists():
            raise FasterWhisperBackendError(f"Input file does not exist: {file_path}")
        # 如果扩展名不在支持列表中，同样抛出异常提示。
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise FasterWhisperBackendError(
                f"Unsupported audio extension '{file_path.suffix}' for faster-whisper placeholder"
            )
        # 组装段级结构，使用文件名构建占位文本。
        segments = [
            {
                "id": 0,
                "text": f"[FAKE-{FASTER_WHIPER_NAME}] {file_path.stem}",
                "start": 0.0,
                "end": 0.0,
                "avg_conf": 0.0,
                "words": [],
            }
        ]
        # 组装后端描述信息，记录模型、版本与构造参数。
        backend_info = {
            "name": FASTER_WHIPER_NAME,
            "version": FASTER_WHIPER_VERSION,
            "model": self.model_name,
            "device": self.device,
            "compute_type": self.compute_type,
        }
        # 组装额外的元信息，注明当前轮次仅返回占位结果。
        meta = {
            "note": "placeholder for round 3",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "word_timestamps": "planned for round 7/8",
        }
        # 返回符合统一接口的字典。
        return {
            "language": self.language,
            "duration_sec": 0.0,
            "backend": backend_info,
            "segments": segments,
            "words": [],
            "meta": meta,
        }

