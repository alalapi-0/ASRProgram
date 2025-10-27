"""验证 CLI 在远程/非交互环境下的实时日志特性。"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cli.main import main  # noqa: E402  # 延迟导入以确保 sys.path 已更新。


def test_cli_teelog_flushes_immediately(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """调用 CLI 打印配置时，应同时刷新 stdout 与 tee 日志文件。"""

    tee_log = tmp_path / "run.log"
    exit_code = main(
        [
            "--input",
            str(tmp_path),
            "--print-config",
            "true",
            "--tee-log",
            str(tee_log),
            "--force-flush",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "effective config snapshot" in captured.out
    assert tee_log.exists()
    assert "effective config snapshot" in tee_log.read_text(encoding="utf-8")
