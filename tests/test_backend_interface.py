"""验证后端接口实现返回统一结构的最小测试。"""
# 导入 pathlib.Path 以便创建临时文件路径。
from pathlib import Path
# 导入 sys 以将仓库根目录加入模块搜索路径。
import sys
# 将仓库根目录添加到 sys.path，确保可以导入 src 包。
sys.path.append(str(Path(__file__).resolve().parents[1]))
# 从后端注册工厂导入 create_transcriber 函数。
from src.asr.backends import create_transcriber

# 定义辅助函数，校验返回结构是否满足约定。
def assert_standard_structure(result: dict, expected_backend: str) -> None:
    """断言转写结果符合统一字段约定。"""
    # language 字段应为字符串。
    assert isinstance(result["language"], str)
    # duration_sec 字段应为浮点数。
    assert isinstance(result["duration_sec"], float)
    # backend 信息应为字典并包含名称与模型字段。
    assert result["backend"]["name"] == expected_backend
    assert "model" in result["backend"]
    # segments 应为列表，内部元素包含必需字段。
    assert isinstance(result["segments"], list)
    assert result["segments"]
    first_segment = result["segments"][0]
    assert {"id", "text", "start", "end", "avg_conf", "words"}.issubset(first_segment.keys())
    # words 字段应为列表（可为空，但类型必须正确）。
    assert isinstance(result["words"], list)
    # meta 字段应存在以预留扩展信息。
    assert "note" in result["meta"]

# 定义针对 dummy 与 faster-whisper 的集成测试。
def test_registered_backends_return_standard_structure(tmp_path):
    """实例化两个后端并验证输出结构一致。"""
    # 创建一个临时文件作为输入音频占位符。
    fake_audio = tmp_path / "placeholder.wav"
    fake_audio.write_text("")
    # 创建 dummy 后端并执行转写。
    dummy = create_transcriber("dummy", language="en")
    dummy_result = dummy.transcribe_file(str(fake_audio))
    assert_standard_structure(dummy_result, "dummy")
    # 创建 faster-whisper 占位后端并执行转写。
    faster = create_transcriber("faster-whisper", language="en")
    faster_result = faster.transcribe_file(str(fake_audio))
    assert_standard_structure(faster_result, "faster-whisper")
    # faster-whisper 本轮不返回词级时间戳，因此 words 应为空列表。
    assert faster_result["words"] == []

