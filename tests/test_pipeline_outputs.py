"""验证 Round 4 管线的落盘规则与容错行为。"""
# 导入 json 以读取生成的 JSON 文件验证内容。 
import json
# 导入 pathlib.Path 方便构造临时文件路径。
from pathlib import Path
# 导入 pytest 以使用测试与 monkeypatch 功能。
import pytest
# 从管线模块导入 run 函数以便直接调用。
from src.asr import pipeline

# 定义辅助函数，用于在临时目录中创建伪音频文件。
def _touch_audio(tmp_dir: Path, name: str) -> Path:
    """在指定目录创建空文件，并返回文件路径。"""
    # 构造目标路径并确保父目录存在。
    path = tmp_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    # 使用 touch 创建空文件，模拟音频占位。
    path.touch()
    # 返回创建好的路径供测试使用。
    return path

# 定义辅助函数读取 JSON 并返回解析后的对象。
def _read_json(path: Path) -> dict:
    """读取 JSON 文件并返回 Python 对象。"""
    # 打开文件并用 utf-8 解码读取后解析。
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)

# 定义测试，验证正常情况下 words/segments 均被生成。
def test_pipeline_generates_expected_outputs(tmp_path: Path) -> None:
    """处理含两段音频文件的目录时应生成完整 JSON。"""
    # 创建输入与输出目录。
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "out"
    # 创建两个合法音频文件以及一个非法扩展名文件。
    good_a = _touch_audio(input_dir, "clip_a.wav")
    good_b = _touch_audio(input_dir, "clip_b.MP3")
    _touch_audio(input_dir, "ignore.txt")
    # 调用管线执行处理，segments_json 设为 True 以生成段级文件。
    summary = pipeline.run(
        input_path=str(input_dir),
        out_dir=str(output_dir),
        backend_name="dummy",
        language="auto",
        segments_json=True,
        overwrite=False,
        dry_run=False,
        verbose=False,
    )
    # 验证扫描总数只包含合法音频文件。
    assert summary["total"] == 2
    # 确认所有文件均计为 processed 且没有失败。
    assert summary["processed"] == 2
    assert summary["succeeded"] == 2
    assert summary["failed"] == 0
    # 验证 words.json 与 segments.json 均存在且可解析。
    for source in (good_a, good_b):
        base = source.stem
        words_file = output_dir / f"{base}.words.json"
        segments_file = output_dir / f"{base}.segments.json"
        assert words_file.exists()
        assert segments_file.exists()
        # 确认 JSON 可解析且 words 字段存在。
        words_data = _read_json(words_file)
        assert "words" in words_data
        # 确认段级文件同样合法。
        segments_data = _read_json(segments_file)
        assert "segments" in segments_data
        # 检查未留下 .tmp 临时文件，确保原子写入完成。
        assert not (output_dir / f"{base}.words.json.tmp").exists()
        assert not (output_dir / f"{base}.segments.json.tmp").exists()

# 定义测试，验证覆盖策略：默认不覆盖，显式允许时可恢复。
def test_pipeline_overwrite_behavior(tmp_path: Path) -> None:
    """重复运行时应遵守覆盖策略并保持原有内容。"""
    # 准备输入音频与输出目录。
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "out"
    _touch_audio(input_dir, "voice.wav")
    # 首次运行生成输出文件。
    pipeline.run(
        input_path=str(input_dir),
        out_dir=str(output_dir),
        backend_name="dummy",
        segments_json=True,
    )
    # 记录初次生成的 words.json 内容。
    words_file = output_dir / "voice.words.json"
    original_snapshot = _read_json(words_file)
    # 修改文件内容以模拟外部改动。
    words_file.write_text("{\"altered\": true}\n", encoding="utf-8")
    # 再次运行，未开启 overwrite，应保留修改后的文本。
    pipeline.run(
        input_path=str(input_dir),
        out_dir=str(output_dir),
        backend_name="dummy",
        segments_json=True,
        overwrite=False,
    )
    assert words_file.read_text(encoding="utf-8") == "{\"altered\": true}\n"
    # 第三次运行启用 overwrite，应恢复为标准结构。
    pipeline.run(
        input_path=str(input_dir),
        out_dir=str(output_dir),
        backend_name="dummy",
        segments_json=True,
        overwrite=True,
    )
    # 再次读取 JSON，确认文件已被覆盖且结构完整。
    restored_data = _read_json(words_file)
    assert restored_data.get("words") == original_snapshot.get("words")
    assert restored_data.get("backend", {}).get("name") == "dummy"
    assert words_file.read_text(encoding="utf-8") != "{\"altered\": true}\n"

# 定义测试，验证 dry-run 模式不会创建输出目录或文件。
def test_pipeline_dry_run_skips_writes(tmp_path: Path) -> None:
    """dry-run 模式只打印计划，不生成任何文件。"""
    # 创建单个音频文件用于测试。
    audio_path = _touch_audio(tmp_path, "sample.wav")
    # 定义输出目录但不期望被创建。
    output_dir = tmp_path / "out"
    # 执行 dry-run。
    summary = pipeline.run(
        input_path=str(audio_path),
        out_dir=str(output_dir),
        backend_name="dummy",
        dry_run=True,
    )
    # dry-run 统计应视为成功但不落盘。
    assert summary["total"] == 1
    assert summary["processed"] == 1
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0
    # 输出目录应不存在，确保未进行写操作。
    assert not output_dir.exists()

# 定义测试，验证错误旁路：单个文件失败时产生 error.txt 并继续执行。
def test_pipeline_error_bypass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """部分文件失败时应生成错误文件并记录错误摘要。"""
    # 创建输入目录与两段音频，其中一段将触发错误。
    input_dir = tmp_path / "inputs"
    bad_file = _touch_audio(input_dir, "bad.wav")
    good_file = _touch_audio(input_dir, "good.wav")
    output_dir = tmp_path / "out"

    # 定义自定义的转写器，其中 bad.wav 会抛出异常。
    class FaultyTranscriber:
        """仅对指定文件抛出异常的占位转写器。"""

        # 初始化函数保持与工厂调用兼容。
        def __init__(self, *args, **kwargs) -> None:  # noqa: D401
            # 该占位实现无需保存任何状态。
            pass

        # 定义转写函数：bad.wav 抛出错误，其余返回空结构。
        def transcribe_file(self, input_path: str) -> dict:
            """对 bad.wav 抛出异常，其余路径返回最小结构。"""
            if input_path.endswith("bad.wav"):
                raise RuntimeError("synthetic failure")
            return {
                "language": "auto",
                "backend": {"name": "dummy"},
                "meta": {},
                "words": [],
                "segments": [],
            }

    # 使用 monkeypatch 将 create_transcriber 指向自定义实现。
    monkeypatch.setattr(pipeline, "create_transcriber", lambda *args, **kwargs: FaultyTranscriber())
    # 执行管线，segments_json 默认为 True。
    summary = pipeline.run(
        input_path=str(input_dir),
        out_dir=str(output_dir),
        backend_name="dummy",
        segments_json=True,
        overwrite=True,
    )
    # 总数应包含两个音频文件。
    assert summary["total"] == 2
    # processed 应等于总数，failed 仅有一个。
    assert summary["processed"] == 2
    assert summary["failed"] == 1
    assert len(summary["errors"]) == 1
    # 错误条目应指向 bad.wav。
    assert summary["errors"][0]["input"].endswith("bad.wav")
    # bad.wav 应生成 error.txt 文件。
    error_file = output_dir / "bad.error.txt"
    assert error_file.exists()
    assert "synthetic failure" in error_file.read_text(encoding="utf-8")
    # good.wav 应仍然生成正常输出。
    words_file = output_dir / "good.words.json"
    segments_file = output_dir / "good.segments.json"
    assert words_file.exists()
    assert segments_file.exists()
