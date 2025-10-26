"""通过 CLI 执行 dummy 后端的冒烟测试。"""
# 导入 json 以读取 CLI 生成的结果文件。
import json
# 导入 os 以操作环境变量（如 PYTHONPATH）。
import os
# 导入 subprocess 以运行 python -m 命令。
import subprocess
# 导入 sys 以获取当前解释器路径。
import sys
# 导入 pathlib.Path 以构造输入与输出目录。
from pathlib import Path

# 将仓库根目录加入 sys.path，确保可导入 src 包。
sys.path.append(str(Path(__file__).resolve().parents[1]))

# 从 schema 工具导入校验函数，复用 JSON Schema 验证逻辑。
from src.utils.schema import validate_segments, validate_words


# 定义辅助函数，包装对 CLI 的调用，减少重复样板代码。
def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """使用当前 Python 解释器运行 CLI 并返回进程结果。"""

    # 构造环境变量，显式设置 PYTHONPATH 指向仓库根目录。
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    # 组合命令行参数，使用 python -m src.cli.main 形式。
    command = [sys.executable, "-m", "src.cli.main", *args]
    # 执行子进程并捕获输出，便于调试失败信息。
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


# 定义冒烟测试，验证 CLI 能生成词级与段级 JSON。
def test_cli_dummy_produces_outputs(tmp_path) -> None:
    """运行 CLI 并确认 words/segments JSON 均通过校验。"""

    # 准备输入目录与占位音频文件。
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    fake_audio = input_dir / "case.wav"
    fake_audio.write_bytes(b"")
    # 定义输出目录用于存放生成的 JSON。
    out_dir = tmp_path / "out"
    # 调用 CLI 执行 dummy 后端。
    result = _run_cli(
        [
            "--input",
            str(input_dir),
            "--out-dir",
            str(out_dir),
            "--backend",
            "dummy",
            "--segments-json",
            "true",
            "--overwrite",
            "true",
            "--dry-run",
            "false",
        ],
        cwd=tmp_path,
    )
    # 确认进程成功退出并打印调试输出以便定位失败原因。
    assert result.returncode == 0, result.stderr
    # 加载 words.json 并进行 schema 校验。
    words_path = out_dir / "case.words.json"
    words_payload = json.loads(words_path.read_text(encoding="utf-8"))
    validate_words(words_payload)
    # 加载 segments.json 并进行 schema 校验。
    segments_path = out_dir / "case.segments.json"
    segments_payload = json.loads(segments_path.read_text(encoding="utf-8"))
    validate_segments(segments_payload)


# 定义测试，验证禁用段级输出时不会生成 segments.json。
def test_cli_disable_segments(tmp_path) -> None:
    """运行 CLI 时将 --segments-json 设为 false，应仅生成 words.json。"""

    # 准备输入文件。
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"")
    # 指定输出目录。
    out_dir = tmp_path / "out_segments_off"
    # 执行 CLI，禁用段级输出。
    result = _run_cli(
        [
            "--input",
            str(audio_path),
            "--out-dir",
            str(out_dir),
            "--backend",
            "dummy",
            "--segments-json",
            "false",
            "--overwrite",
            "true",
            "--dry-run",
            "false",
        ],
        cwd=tmp_path,
    )
    # 确认执行成功。
    assert result.returncode == 0, result.stderr
    # 验证词级文件存在并通过校验。
    words_path = out_dir / "audio.words.json"
    words_payload = json.loads(words_path.read_text(encoding="utf-8"))
    validate_words(words_payload)
    # 验证段级文件不存在。
    segments_path = out_dir / "audio.segments.json"
    assert not segments_path.exists()


# 定义测试，验证 dry-run 模式不会创建输出文件。
def test_cli_dry_run_skips_outputs(tmp_path) -> None:
    """当 --dry-run true 时，CLI 不应写出任何 JSON 文件。"""

    # 准备输入音频。
    audio_path = tmp_path / "dry.wav"
    audio_path.write_bytes(b"")
    # 指定输出目录。
    out_dir = tmp_path / "dry_out"
    # 执行 CLI 的 dry-run 模式。
    result = _run_cli(
        [
            "--input",
            str(audio_path),
            "--out-dir",
            str(out_dir),
            "--backend",
            "dummy",
            "--segments-json",
            "true",
            "--overwrite",
            "true",
            "--dry-run",
            "true",
        ],
        cwd=tmp_path,
    )
    # dry-run 也应成功退出。
    assert result.returncode == 0, result.stderr
    # dry-run 模式不应创建输出目录或 JSON 文件。
    assert not out_dir.exists()
