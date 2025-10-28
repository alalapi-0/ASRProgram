"""Helper utilities for constructing cross-platform ``rsync`` commands."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Iterable, Sequence


def _build_ssh_transport_command(ssh_executable: str, identity_file: Path | None) -> str:
    """Return the quoted SSH transport string passed to ``rsync -e``."""

    parts: list[str] = [ssh_executable, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null"]
    if identity_file is not None:
        parts.extend(["-i", str(identity_file)])
    return " ".join(shlex.quote(part) for part in parts)


def build_rsync_download_command(
    *,
    rsync_executable: str,
    ssh_executable: str = "ssh",
    identity_file: str | Path | None = None,
    remote_user: str,
    remote_host: str,
    remote_dir: str | Path,
    local_dir: str | Path,
    include_patterns: Iterable[str] | None = None,
    extra_args: Sequence[str] | None = None,
) -> list[str]:
    """Create a robust ``rsync`` command list that only downloads JSON artifacts."""

    identity_path = Path(identity_file).expanduser().resolve(strict=False) if identity_file else None
    command: list[str] = [
        rsync_executable,
        "-avz",
        "--partial",
        "--inplace",
        "--progress",
        "-e",
        _build_ssh_transport_command(ssh_executable, identity_path),
    ]

    patterns = list(include_patterns or [])
    if "*.json" not in patterns:
        patterns.append("*.json")
    if "_manifest.txt" not in patterns:
        patterns.append("_manifest.txt")

    command.extend(["--include", "*/"])
    for pattern in patterns:
        command.extend(["--include", pattern])
    command.extend(["--exclude", "*"])

    if extra_args:
        command.extend(extra_args)

    remote_path = Path(remote_dir)
    normalized_remote = remote_path.as_posix().rstrip("/") + "/"
    destination = Path(local_dir)

    command.append(f"{remote_user}@{remote_host}:{normalized_remote}")
    command.append(str(destination))

    return command


__all__ = ["build_rsync_download_command"]
