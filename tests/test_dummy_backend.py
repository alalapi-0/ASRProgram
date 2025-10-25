"""针对 dummy 后端的最小单元测试，验证输出文件结构。"""
# 导入 json 以解析生成的文件。
import json
# 导入 pathlib.Path 以便操作路径并修改 sys.path。
from pathlib import Path
# 导入 sys 以将项目根目录加入模块搜索路径。
import sys
# 将仓库根目录添加到 sys.path，确保可以导入 src 包。
sys.path.append(str(Path(__file__).resolve().parents[1]))
# 从管线模块导入 run 函数以便调用。
from src.asr.pipeline import run

# 定义测试函数，pytest 会自动识别。
def test_dummy_backend_generates_outputs(tmp_path):
    """验证 dummy 后端能生成词级与段级 JSON 文件。"""
    # 创建临时输入目录。
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    # 创建一个空的模拟音频文件。
    fake_audio = input_dir / "sample_audio.wav"
    fake_audio.write_text("")
    # 定义输出目录。
    out_dir = tmp_path / "out"
    # 调用管线执行处理。
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
    # 断言没有错误发生。
    assert not result["errors"]
    # 构造词级与段级文件路径。
    words_path = out_dir / "sample_audio.words.json"
    segments_path = out_dir / "sample_audio.segments.json"
    # 确认文件已经生成。
    assert words_path.exists()
    assert segments_path.exists()
    # 读取词级文件并验证关键字段。
    words_data = json.loads(words_path.read_text(encoding="utf-8"))
    assert words_data["language"] == "auto"
    assert isinstance(words_data["backend"], dict)
    assert isinstance(words_data["words"], list)
    # 读取段级文件并验证关键字段。
    segments_data = json.loads(segments_path.read_text(encoding="utf-8"))
    assert segments_data["language"] == "auto"
    assert isinstance(segments_data["segments"], list)
    assert segments_data["backend"]["name"] == "dummy"

