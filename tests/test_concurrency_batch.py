"""针对 Round 9 并发批处理特性的集成测试。"""  # 模块说明。
# 导入 json 用于读取输出文件验证内容。 
import json  # 导入 json 模块以解析输出文件。
# 导入 pathlib.Path 以便在测试中构造文件路径。 
from pathlib import Path  # 提供路径拼接工具。
# 导入 typing 中的 Dict 与 List 用于类型注释。 
from typing import Dict, List  # 便于描述计划字典结构。

# 导入 pytest 以使用 fixture 与断言辅助。 
import pytest  # 测试框架。

# 从管线模块导入运行函数与异常类型，便于模拟后端行为。 
from src.asr import pipeline  # 导入待测试的管线与异常。


# 定义测试专用的占位后端，用于模拟成功、可重试与致命失败。 
class StubTranscriber:
    """根据预设计划返回占位识别结果或抛出异常。"""  # 类说明。

    def __init__(self, plan: Dict[str, List[str]]):
        """保存每个文件的执行计划并初始化调用计数。"""  # 方法说明。
        self.plan = plan  # 保存计划字典。
        self.calls: Dict[str, int] = {}  # 跟踪每个文件已执行次数。

    def transcribe_file(self, input_path: str) -> dict:
        """根据计划返回占位结果或抛出异常。"""  # 方法说明。
        normalized = str(Path(input_path))  # 标准化路径字符串。
        index = self.calls.get(normalized, 0)  # 获取当前调用索引。
        self.calls[normalized] = index + 1  # 递增调用次数。
        actions = self.plan.get(normalized, ["success"])  # 读取动作序列。
        action = actions[index] if index < len(actions) else actions[-1]  # 选择当前动作。
        if action == "transient":  # 判断是否为可重试错误。
            raise pipeline.TransientTaskError("temporary glitch")
        if action == "fatal":  # 判断是否为致命错误。
            raise pipeline.FatalTaskError("irrecoverable failure")
        stem = Path(input_path).stem  # 提取文件名用于生成占位文本。
        words = [  # 构造三个占位词条。
            {
                "text": f"{stem}-w{idx}",  # 词内容。
                "start": float(idx) * 0.5,  # 起始时间。
                "end": float(idx) * 0.5 + 0.5,  # 结束时间。
                "confidence": 0.9,  # 置信度占位值。
                "segment_id": 0,  # 所属段编号。
                "index": idx,  # 词序号。
            }
            for idx in range(3)
        ]
        return {
            "language": "en",  # 返回语言。
            "duration_sec": 1.5,  # 返回固定时长避免探测。
            "segments": [
                {
                    "id": 0,  # 段 ID。
                    "text": f"segment-{stem}",  # 段文本。
                    "start": 0.0,  # 段起始时间。
                    "end": 1.5,  # 段结束时间。
                    "avg_conf": 0.9,  # 平均置信度。
                    "words": words,  # 嵌入词级数组。
                }
            ],
            "words": words,  # 词级数组。
            "backend": {"name": "stub", "version": "test"},  # 后端信息。
            "meta": {},  # 空元信息。
        }


# 定义辅助函数，用于批量创建伪音频文件并返回路径列表。 
def create_audio_files(base_dir: Path, count: int) -> List[Path]:
    """在 base_dir 下创建指定数量的伪音频文件。"""  # 函数说明。
    base_dir.mkdir(parents=True, exist_ok=True)  # 确保目录存在。
    paths: List[Path] = []  # 初始化返回列表。
    for index in range(count):  # 遍历需要创建的文件数量。
        path = base_dir / f"sample_{index}.wav"  # 拼接文件路径。
        path.write_text("stub")  # 写入占位内容以确保文件存在。
        paths.append(path)  # 将路径加入列表。
    return paths  # 返回创建的文件路径集合。


# 定义 fixture，针对每次测试提供干净的输出目录。 
@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """返回 tests 专用的输出目录。"""  # 函数说明。
    out = tmp_path / "out"  # 构造输出目录路径。
    out.mkdir()  # 创建目录。
    return out  # 返回目录路径。


def test_concurrent_processing_with_retries_and_statistics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output_dir: Path
) -> None:
    """验证并发执行、重试统计与失败隔离。"""  # 用例说明。
    inputs = create_audio_files(tmp_path / "inputs", 6)  # 创建 6 个输入文件。
    plan = {  # 定义执行计划：混合成功与失败。
        str(inputs[0]): ["success"],  # 文件 0 一次成功。
        str(inputs[1]): ["transient", "success"],  # 文件 1 首次失败后成功。
        str(inputs[2]): ["fatal"],  # 文件 2 致命失败。
        str(inputs[3]): ["transient", "transient", "transient"],  # 文件 3 多次重试仍失败。
        str(inputs[4]): ["success"],  # 文件 4 成功。
        str(inputs[5]): ["transient", "success"],  # 文件 5 首次失败后成功。
    }
    monkeypatch.setattr(  # 替换工厂函数以返回测试后端。
        pipeline,
        "create_transcriber",
        lambda name, **kwargs: StubTranscriber(plan),
    )
    summary = pipeline.run(  # 执行管线。
        input_path=str(tmp_path / "inputs"),
        out_dir=str(output_dir),
        backend_name="stub",
        language="en",
        segments_json=True,
        overwrite=False,
        dry_run=False,
        verbose=False,
        num_workers=3,
        max_retries=2,
        rate_limit=0.0,
        skip_done=True,
        fail_fast=False,
    )
    assert summary["total"] == 6  # 校验总数。
    assert summary["queued"] == 6  # 校验排队数量。
    assert summary["processed"] == summary["succeeded"] + summary["failed"]  # 成功+失败=处理数。
    assert summary["succeeded"] == 4  # 成功数量应为 4。
    assert summary["failed"] == 2  # 失败数量应为 2。
    assert summary["retried_count"] == 4  # 重试统计为 4 次。
    failed_inputs = {item["input"] for item in summary["errors"]}  # 收集失败文件。
    assert str(inputs[2]) in failed_inputs  # 文件 2 应失败。
    assert str(inputs[3]) in failed_inputs  # 文件 3 应失败。
    for path in inputs:  # 遍历所有文件检查输出。
        base = Path(path).with_suffix("")  # 去除扩展名。
        words_path = output_dir / f"{base.name}.words.json"  # 对应的词级文件路径。
        if str(path) in failed_inputs:  # 失败文件不应生成词级输出。
            assert not words_path.exists()
        else:  # 成功文件应生成有效 JSON。
            assert words_path.exists()
            payload = json.loads(words_path.read_text())  # 读取 JSON。
            assert payload["schema"] == pipeline.WORD_SCHEMA  # 校验 schema。


def test_skip_done_reprocesses_failed_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output_dir: Path
) -> None:
    """验证 skip-done 默认行为：仅跳过已成功的文件。"""  # 用例说明。
    inputs = create_audio_files(tmp_path / "inputs2", 4)  # 创建 4 个输入文件。
    plan_first = {  # 首轮执行计划：两个成功两个失败。
        str(inputs[0]): ["success"],
        str(inputs[1]): ["success"],
        str(inputs[2]): ["fatal"],
        str(inputs[3]): ["transient", "transient", "transient"],
    }
    monkeypatch.setattr(  # 使用首轮计划替换工厂。
        pipeline,
        "create_transcriber",
        lambda name, **kwargs: StubTranscriber(plan_first),
    )
    first_summary = pipeline.run(  # 运行首轮。
        input_path=str(tmp_path / "inputs2"),
        out_dir=str(output_dir),
        backend_name="stub",
        segments_json=True,
        num_workers=2,
        max_retries=2,
        skip_done=True,
        fail_fast=False,
    )
    assert first_summary["succeeded"] == 2  # 首轮成功数。
    assert first_summary["failed"] == 2  # 首轮失败数。
    plan_second = {  # 次轮计划仅针对失败文件。
        str(inputs[2]): ["success"],
        str(inputs[3]): ["success"],
    }
    monkeypatch.setattr(  # 替换为次轮计划。
        pipeline,
        "create_transcriber",
        lambda name, **kwargs: StubTranscriber(plan_second),
    )
    second_summary = pipeline.run(  # 运行次轮。
        input_path=str(tmp_path / "inputs2"),
        out_dir=str(output_dir),
        backend_name="stub",
        segments_json=True,
        num_workers=2,
        max_retries=1,
        skip_done=True,
        fail_fast=False,
    )
    assert second_summary["queued"] == 2  # 仅失败文件被重新排队。
    assert second_summary["succeeded"] == 2  # 次轮成功完成。
    assert second_summary["skipped"] == 2  # 已成功文件被跳过。
    assert second_summary["failed"] == 0  # 次轮没有失败。
    for path in inputs:  # 所有文件最终都应生成词级输出。
        words_path = output_dir / f"{Path(path).stem}.words.json"
        assert words_path.exists()


def test_fail_fast_stops_submission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output_dir: Path
) -> None:
    """验证 fail-fast 模式会在失败后停止提交新任务。"""  # 用例说明。
    inputs = create_audio_files(tmp_path / "inputs_ff", 5)  # 创建 5 个输入文件。
    plan = {  # 定义计划：首个失败，其余成功。
        str(inputs[0]): ["fatal"],
        str(inputs[1]): ["success"],
        str(inputs[2]): ["success"],
        str(inputs[3]): ["success"],
        str(inputs[4]): ["success"],
    }
    monkeypatch.setattr(  # 替换工厂函数。
        pipeline,
        "create_transcriber",
        lambda name, **kwargs: StubTranscriber(plan),
    )
    summary = pipeline.run(  # 执行 fail-fast 模式。
        input_path=str(tmp_path / "inputs_ff"),
        out_dir=str(output_dir),
        backend_name="stub",
        segments_json=True,
        num_workers=2,
        max_retries=0,
        skip_done=True,
        fail_fast=True,
    )
    assert summary["failed"] >= 1  # 至少有一个失败。
    assert summary["cancelled"] >= 1  # 应取消部分任务提交。
    assert summary["processed"] + summary["cancelled"] == summary["queued"]  # processed+cancelled=queued。
