"""验证 JSON Schema 工具对词级与段级结构的校验能力。"""
# 导入 json 以解析落盘文件内容。
import json
# 导入 pathlib.Path 以计算仓库根目录。
from pathlib import Path
# 导入 sys 以追加仓库根目录到模块搜索路径。
import sys

# 导入 pytest 以使用断言与异常检查辅助。
import pytest
# 从 jsonschema 导入 ValidationError 以匹配异常类型。
from jsonschema import ValidationError

# 将仓库根目录加入 sys.path，确保测试能导入 src 包。
sys.path.append(str(Path(__file__).resolve().parents[1]))

# 导入管线 run 函数以执行端到端流程。
from src.asr.pipeline import run
# 导入 schema 校验工具以对内存结构进行验证。
from src.utils.schema import validate_segments, validate_words


# 定义辅助函数，构造最小合法的词级与段级样例。
def _build_sample_payloads() -> tuple[dict, dict]:
    """返回用于单元测试的最小 words/segments 样例。"""

    # 构造共享的词条列表，确保时间戳单调递增。
    words = [
        {
            "text": "hello",
            "start": 0.0,
            "end": 0.5,
            "confidence": 0.9,
            "segment_id": 0,
            "index": 0,
        }
    ]
    # 构造词级顶层结构，涵盖 schema、音频、后端与生成时间等字段。
    words_payload = {
        "schema": "asrprogram.wordset.v1",
        "language": "en",
        "audio": {
            "path": "/tmp/sample.wav",
            "duration_sec": 1.0,
            "language": "en",
            "hash_sha256": None,
        },
        "backend": {
            "name": "dummy",
            "model": "synthetic",
            "version": "0.1.0",
        },
        "meta": {
            "schema_version": "round14-test",
        },
        "words": words,
        "generated_at": "2024-01-01T00:00:00Z",
    }
    # 构造段级结构，复用词条并补充段落字段。
    segments_payload = {
        "schema": "asrprogram.segmentset.v1",
        "language": "en",
        "audio": {
            "path": "/tmp/sample.wav",
            "duration_sec": 1.0,
            "language": "en",
            "hash_sha256": None,
        },
        "backend": {
            "name": "dummy",
            "model": "synthetic",
            "version": "0.1.0",
        },
        "meta": {
            "schema_version": "round14-test",
        },
        "segments": [
            {
                "id": 0,
                "text": "hello",
                "start": 0.0,
                "end": 0.5,
                "avg_conf": 0.9,
                "words": words,
            }
        ],
        "generated_at": "2024-01-01T00:00:00Z",
    }
    # 返回词级与段级样例。
    return words_payload, segments_payload


# 定义测试用例，验证最小样例可以通过校验。
def test_manual_samples_pass_validation() -> None:
    """确保手工构造的最小结构符合 schema。"""

    # 获取预设的样例结构。
    words_payload, segments_payload = _build_sample_payloads()
    # 执行词级校验，若抛错测试将失败。
    validate_words(words_payload)
    # 执行段级校验，若抛错测试将失败。
    validate_segments(segments_payload)


# 定义测试用例，执行 dummy 管线并校验落盘文件。
def test_pipeline_outputs_match_schema(tmp_path) -> None:
    """验证 dummy 后端端到端产物可以通过 schema 校验。"""

    # 创建输入目录并写入空白音频文件。
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    fake_audio = input_dir / "demo.wav"
    fake_audio.write_bytes(b"")
    # 定义输出目录并执行管线。
    out_dir = tmp_path / "out"
    result = run(
        input_path=input_dir,
        out_dir=out_dir,
        backend_name="dummy",
        language="auto",
        write_segments=True,
        overwrite=True,
        num_workers=1,
        dry_run=False,
        verbose=False,
    )
    # 确认运行未记录错误。
    assert not result["errors"]
    # 读取生成的 words.json 并执行校验。
    words_path = out_dir / "demo.words.json"
    words_payload = json.loads(words_path.read_text(encoding="utf-8"))
    validate_words(words_payload)
    # 读取生成的 segments.json 并执行校验。
    segments_path = out_dir / "demo.segments.json"
    segments_payload = json.loads(segments_path.read_text(encoding="utf-8"))
    validate_segments(segments_payload)


# 定义测试用例，验证非法结构会触发 ValidationError。
def test_invalid_samples_raise_errors() -> None:
    """确保典型非法字段能够被捕获并抛出 ValidationError。"""

    # 获取基础样例并拷贝为后续修改的模板。
    words_payload, segments_payload = _build_sample_payloads()
    # 构造起始时间为负数的非法词条。
    bad_words = words_payload.copy()
    bad_words["words"] = [dict(words_payload["words"][0], start=-0.1)]
    with pytest.raises(ValidationError):
        validate_words(bad_words)
    # 构造 end 早于 start 的词条，触发附加的时间关系校验。
    overlap_words = words_payload.copy()
    overlap_words["words"] = [dict(words_payload["words"][0], start=0.5, end=0.4)]
    with pytest.raises(ValidationError):
        validate_words(overlap_words)
    # 构造缺失必填字段的段级结构，验证 schema 的 required 规则。
    bad_segments = segments_payload.copy()
    bad_segment_entry = dict(segments_payload["segments"][0])
    bad_segment_entry.pop("text")
    bad_segments["segments"] = [bad_segment_entry]
    with pytest.raises(ValidationError):
        validate_segments(bad_segments)
