"""针对 whisper.cpp 输出解析函数的单元测试，逐行注释说明。"""  # 文件文档字符串说明用途。
# 导入 math 库用于浮点比较中的误差处理。
import math
# 导入 sys 用于在运行时修改模块搜索路径。
import sys
# 导入 typing 中的 List 类型用于类型注解和静态分析提示。
from typing import List
# 导入 pathlib.Path 以便构造仓库根目录路径。
from pathlib import Path
# 将仓库根目录加入 sys.path，确保测试可导入 src 包。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# 从后端实现中导入需要测试的解析函数。
from src.asr.backends.whisper_cpp_backend import parse_whisper_cpp_json_output, parse_whisper_cpp_tsv_output

# 构造一个示例 JSON 输出字符串，模拟 whisper.cpp 带有词级时间戳的情况。
JSON_SAMPLE = """
{
  "language": "en",
  "segments": [
    {
      "text": "Hello world.",
      "start": 0.0,
      "end": 2.0,
      "words": [
        {"word": "Hello", "start": 0.0, "end": 0.8, "prob": 0.92},
        {"word": "world", "start": 0.8, "end": 1.6, "prob": 0.88},
        {"word": ".", "start": 1.6, "end": 2.0, "prob": 0.50}
      ]
    },
    {
      "text": "This is a test.",
      "start": 2.0,
      "end": 5.5,
      "words": [
        {"word": "This", "start": 2.0, "end": 2.5, "prob": 0.90},
        {"word": "is", "start": 2.5, "end": 3.0, "prob": 0.95},
        {"word": "a", "start": 3.0, "end": 3.3, "prob": 0.80},
        {"word": "test", "start": 3.3, "end": 4.9, "prob": 0.85},
        {"word": ".", "start": 4.9, "end": 5.5, "prob": 0.55}
      ]
    }
  ]
}
"""  # JSON 示例结束。

# 构造一个示例 TSV 输出字符串，模拟 --output-word-tsv 的常见格式。
TSV_SAMPLE = """
# start\tend\tword\tprobability\tsegment
0.00\t0.70\tHello\t0.90\t0
0.70\t1.40\tworld\t0.85\t0
1.40\t1.80\t!\t0.30\t0
1.80\t2.20\tThis\t0.91\t1
2.20\t2.50\tis\t0.93\t1
2.50\t2.80\ta\t0.70\t1
2.80\t3.50\ttest\t0.88\t1
"""  # TSV 示例结束。

# 定义辅助函数确保词列表的 segment_id 与 index 单调递增。
def assert_word_monotonic(words: List[dict]) -> None:
    """检查词条的段编号与索引是否单调递增，同时验证时间戳不倒退。"""  # 函数说明。
    last_segment = -1  # 初始化上一段编号。
    last_index = -1  # 初始化段内索引。
    last_end = 0.0  # 初始化上一词的结束时间。
    for word in words:  # 遍历所有词条。
        assert word["segment_id"] >= last_segment  # 段编号应当非递减。
        if word["segment_id"] == last_segment:  # 若处于同一段。
            assert word["index"] > last_index  # 索引需递增。
        else:  # 进入新段时。
            last_segment = word["segment_id"]  # 更新段编号。
            last_index = -1  # 重置索引。
        last_index = word["index"]  # 更新上一索引。
        assert word["start"] - 1e-6 >= last_end - 1e-6  # 起始时间不应小于上一词结束时间。
        assert word["end"] + 1e-6 >= word["start"]  # 结束时间不应早于开始时间。
        last_end = word["end"]  # 更新上一词结束时间。

# 针对 JSON 输出的解析测试。
def test_parse_whisper_cpp_json_output() -> None:
    """验证 parse_whisper_cpp_json_output 能正确解析段与词结构。"""  # 测试说明。
    segments, language, meta = parse_whisper_cpp_json_output(JSON_SAMPLE, "auto")  # 执行解析。
    assert language == "en"  # 应从 JSON 中解析出语言代码。
    assert meta["raw_format"] == "json"  # meta 标记应指示来源格式。
    assert len(segments) == 2  # 示例中包含两个段。
    for segment in segments:  # 遍历段集合。
        assert "words" in segment  # 每个段都应包含词列表。
        assert segment["start"] <= segment["end"]  # 段的开始时间不应大于结束时间。
        assert_word_monotonic(segment["words"])  # 校验词级单调性。
        confidences = [w["confidence"] for w in segment["words"] if w["confidence"] is not None]  # 收集置信度。
        if confidences:  # 当存在置信度时。
            avg_conf = sum(confidences) / len(confidences)  # 计算平均值。
            if segment["avg_conf"] is not None:  # 当段级置信度存在时。
                assert math.isclose(segment["avg_conf"], avg_conf, rel_tol=1e-3)  # 验证段级均值。

# 针对 TSV 输出的解析测试。
def test_parse_whisper_cpp_tsv_output() -> None:
    """验证 parse_whisper_cpp_tsv_output 能从词级 TSV 构建段结构。"""  # 测试说明。
    segments, language, meta = parse_whisper_cpp_tsv_output(TSV_SAMPLE, "en")  # 执行解析。
    assert language == "en"  # 语言提示应被回传。
    assert meta["raw_format"] == "tsv"  # meta 标记应指示 TSV 来源。
    assert len(segments) == 2  # 预期生成两个段。
    total_words = sum(len(segment["words"]) for segment in segments)  # 统计总词数。
    assert total_words == 7  # 示例数据共七个词条。
    for segment in segments:  # 遍历段集合。
        assert_word_monotonic(segment["words"])  # 校验词级单调性。
        assert segment["start"] <= segment["end"]  # 确保时间范围有效。
        if segment["avg_conf"] is not None:  # 若存在平均置信度。
            assert 0.0 <= segment["avg_conf"] <= 1.0  # 平均置信度应位于合法范围。
