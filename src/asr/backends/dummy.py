"""提供一个仅生成占位文本的转写后端实现。"""
# 导入 datetime 以生成 UTC 时间戳。
from datetime import datetime, timezone
# 导入 pathlib.Path 便于处理文件路径。
from pathlib import Path
# 导入 typing 的 List 类型以进行类型注释。
from typing import List
# 从同目录的 base 模块导入接口基类。
from .base import ITranscriber

# 定义占位后端的常量名称。
DUMMY_NAME = "dummy"
# 定义占位后端的版本号。
DUMMY_VERSION = "0.1.0"

# 定义实际的转写器类，继承抽象基类。
class DummyTranscriber(ITranscriber):
    """返回基于文件名生成的段级与词级占位结构。"""

    # 实现抽象方法 transcribe_file。
    def transcribe_file(self, input_path: str) -> dict:
        """根据输入文件名构造模拟的转写结果。"""
        # 使用 Path 提取文件名主体部分。
        file_path = Path(input_path)
        # 获取不含扩展名的基本名称。
        basename = file_path.stem
        # 将文件名中的分隔符替换为空格以便拆分词语。
        normalized = basename.replace("_", " ").replace("-", " ")
        # 将名称按空格拆分，过滤空白片段。
        tokens: List[str] = [part for part in normalized.split() if part]
        # 如果拆分结果不足两个词，补充占位词保证 2~3 个。
        if len(tokens) < 2:
            # 若完全没有词，使用 generic 作为占位。
            if not tokens:
                tokens = ["generic", "sample"]
            else:
                # 若只有一个词，则复制并添加 suffix。
                tokens.append(f"{tokens[0]}-tail")
        # 若词语数量超过三，截断为前三个以保持简洁。
        tokens = tokens[:3]
        # 准备词级结果列表。
        word_items: List[dict] = []
        # 遍历 tokens，为每个词生成递增的时间戳。
        for index, token in enumerate(tokens):
            # 每个词的起始时间按索引乘以 0.5 秒。
            start_time = round(index * 0.5, 2)
            # 每个词持续 0.5 秒。
            end_time = round(start_time + 0.5, 2)
            # 构造词级字典并附带置信度与所属段信息。
            word_items.append(
                {
                    "text": token,
                    "start": start_time,
                    "end": end_time,
                    "confidence": 0.9,
                    "segment_id": 0,
                    "index": index,
                }
            )
        # 构造段级结构，将词列表嵌入。
        segments = [
            {
                "id": 0,
                "text": f"[DUMMY] {basename} segment",
                "start": 0.0,
                "end": 1.0,
                "avg_conf": 0.9,
                "words": word_items,
            }
        ]
        # 构造顶层元数据，包含语言、时长与后端信息。
        metadata = {
            "language": self.language,
            "duration_sec": 0.0,
            "backend": {
                "name": DUMMY_NAME,
                "version": DUMMY_VERSION,
                "model": self.model_name or "synthetic",
            },
            "meta": {
                "note": "placeholder for round 3",
                "generated_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            },
        }
        # 返回符合统一接口的占位结果结构。
        return {
            "language": metadata["language"],
            "duration_sec": metadata["duration_sec"],
            "backend": metadata["backend"],
            "segments": segments,
            "words": word_items,
            "meta": metadata["meta"],
        }

