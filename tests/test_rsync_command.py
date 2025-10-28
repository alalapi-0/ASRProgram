"""Tests for the rsync command helper utilities."""

from pathlib import Path

from src.utils.rsync import build_rsync_download_command


def test_build_rsync_download_command_includes_json_patterns() -> None:
    """The generated command should always include the ``*.json`` pattern."""

    cmd = build_rsync_download_command(
        rsync_executable="C:/tools/msys64/usr/bin/rsync.EXE",
        ssh_executable="ssh",
        identity_file=Path(r"C:/Users/ASUS/.ssh/id_ed25519"),
        remote_user="root",
        remote_host="198.13.46.63",
        remote_dir="/home/ubuntu/asr_program/output",
        local_dir=Path(r"E:/VULTRagent/results/18fea68d-6e7e-485d-b4c9-f7be19605dc0/20251028-050330"),
    )

    assert "--include" in cmd
    assert "*.json" in cmd
    assert "_manifest.txt" in cmd
    assert cmd[-2] == "root@198.13.46.63:/home/ubuntu/asr_program/output/"
    assert cmd[-1].endswith("20251028-050330")


def test_custom_include_patterns_are_preserved() -> None:
    """Caller supplied include patterns should be appended without duplication."""

    cmd = build_rsync_download_command(
        rsync_executable="rsync",
        remote_user="ubuntu",
        remote_host="example.com",
        remote_dir="/tmp/out",
        local_dir="./local",
        include_patterns=["custom.bin"],
    )

    # Collect all include arguments in insertion order.
    include_values = [value for idx, value in enumerate(cmd) if cmd[idx - 1] == "--include"]

    assert "custom.bin" in include_values
    assert include_values.count("*.json") == 1
    assert include_values.count("_manifest.txt") == 1
