"""针对 Round 8 词级时间戳与降级逻辑的单元测试。"""  # 模块说明。
# 导入 json 以读取写入的 JSON 文件内容。
import json  # noqa: F401
# 导入 pathlib.Path 方便处理临时目录。
from pathlib import Path  # noqa: F401

# 导入 pytest 以使用断言与夹具。
import pytest  # noqa: F401

# 从管线模块导入 run 函数与内部工具以便测试单调性逻辑。
from src.asr import pipeline  # noqa: F401
# 导入 faster-whisper 后端类以测试降级分词函数。
from src.asr.backends.faster_whisper_backend import FasterWhisperTranscriber  # noqa: F401


class DummyBackend:  # noqa: D401
    """伪造的后端实现，返回预定义的转写结果。"""  # 类说明。

    def transcribe_file(self, input_path: str) -> dict:
        """返回包含段级与词级信息的模拟结构。"""  # 方法说明。
        # 构造段级结构，第一段包含词数组，第二段保留空词用于验证重建逻辑。
        segments = [
            {
                "id": 0,
                "text": "hello world.",
                "start": 0.0,
                "end": 1.5,
                "avg_conf": 0.8,
                "words": [
                    {"text": "hello", "start": 0.0, "end": 0.6, "confidence": 0.9, "segment_id": 0, "index": 0},
                    {"text": "world", "start": 0.55, "end": 1.2, "confidence": 0.8, "segment_id": 0, "index": 1},
                    {"text": ".", "start": 1.2, "end": 1.2, "confidence": None, "segment_id": 0, "index": 2},
                ],
            },
            {
                "id": 1,
                "text": "テスト",
                "start": 1.5,
                "end": 2.5,
                "avg_conf": None,
                "words": [],
            },
        ]
        # 构造词级数组，第二段故意缺失以模拟后端未提供词数据的情形。
        words = [
            {"text": "hello", "start": 0.0, "end": 0.6, "confidence": 0.9, "segment_id": 0, "index": 0},
            {"text": "world", "start": 0.55, "end": 1.2, "confidence": 0.8, "segment_id": 0, "index": 1},
            {"text": ".", "start": 1.2, "end": 1.2, "confidence": None, "segment_id": 0, "index": 2},
            {"text": "テ", "start": 1.5, "end": 2.0, "confidence": 0.6, "segment_id": 1, "index": 0},
            {"text": "スト", "start": 1.9, "end": 2.5, "confidence": 0.6, "segment_id": 1, "index": 1},
        ]
        # 返回模拟的后端响应结构。
        return {
            "language": "en",
            "duration_sec": 2.5,
            "backend": {"name": "dummy", "version": "0.0", "model": "unit-test"},
            "segments": segments,
            "words": words,
            "meta": {"detected_language": "en"},
        }


@pytest.fixture
def dummy_backend(monkeypatch):
    """将 create_transcriber 替换为返回 DummyBackend 实例。"""  # 夹具说明。
    monkeypatch.setattr(pipeline, "create_transcriber", lambda *args, **kwargs: DummyBackend())
    # 将 probe_duration 固定为常数，避免依赖外部工具。
    monkeypatch.setattr(pipeline, "probe_duration", lambda path: 2.5)
    return DummyBackend()


def test_pipeline_generates_words_json(tmp_path: Path, dummy_backend):
    """验证管线输出 words.json，并校验词级时间戳与段信息。"""  # 测试说明。
    # 创建临时音频目录与空白 wav 文件，满足扫描逻辑。
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    audio_path = input_dir / "sample.wav"
    audio_path.write_bytes(b"fake")
    # 运行管线，要求同时生成 segments.json。
    output_dir = tmp_path / "outputs"
    summary = pipeline.run(
        input_path=str(input_dir),
        out_dir=str(output_dir),
        backend_name="dummy",
        segments_json=True,
        overwrite=True,
    )
    # 确认处理成功且未出现失败项。
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0
    # 读取生成的词级 JSON 文件。
    words_path = output_dir / "sample.words.json"
    payload = json.loads(words_path.read_text())
    # 校验基础字段存在且生成时间为 ISO 格式字符串。
    assert payload["schema"] == pipeline.WORD_SCHEMA
    assert payload["audio"]["path"].endswith("sample.wav")
    assert payload["generated_at"].endswith("Z")
    # 提取词数组并验证单调性修正生效。
    words = payload["words"]
    assert len(words) >= 3
    for idx in range(1, len(words)):
        assert words[idx]["start"] >= words[idx - 1]["end"]
    # 校验词条携带 segment_id 且索引连续。
    segment_map = {}
    for word in words:
        segment_map.setdefault(word["segment_id"], []).append(word["index"])
    for indexes in segment_map.values():
        assert indexes == list(range(len(indexes)))
    # 读取段级文件并确认第二段已被填充降级生成的词。
    segments_path = output_dir / "sample.segments.json"
    segments_payload = json.loads(segments_path.read_text())
    second_segment = next(seg for seg in segments_payload["segments"] if seg["id"] == 1)
    assert second_segment["words"], "降级词数组应非空"


def test_fallback_for_cjk_characters():
    """直接调用后端降级逻辑，验证中日文文本可拆分为最小单元。"""  # 测试说明。
    # 构造伪实例以调用受保护方法。
    backend_stub = object.__new__(FasterWhisperTranscriber)
    # 执行降级函数，传入中文文本与 2 秒时长。
    words, clipped = FasterWhisperTranscriber._fallback_words_for_segment(  # type: ignore[attr-defined]
        backend_stub,
        "你好世界",
        0.0,
        2.0,
        3,
        "zh",
        None,
    )
    # 验证输出词数量等于字符数，且时间覆盖段界。
    assert len(words) == 4
    assert pytest.approx(words[0]["start"], abs=1e-6) == 0.0
    assert pytest.approx(words[-1]["end"], abs=1e-6) == 2.0
    assert clipped is False
