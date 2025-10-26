"""下载并缓存 ASR 模型。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Optional

from huggingface_hub import HfHubHTTPError, snapshot_download


ModelConfig = Dict[str, object]


REPO_MAP: Dict[str, Dict[str, ModelConfig]] = {
    "faster-whisper": {
        "tiny": {"repo_id": "guillaumekln/faster-whisper-tiny"},
        "base": {"repo_id": "guillaumekln/faster-whisper-base"},
        "small": {"repo_id": "guillaumekln/faster-whisper-small"},
        "medium": {"repo_id": "guillaumekln/faster-whisper-medium"},
        "large-v1": {"repo_id": "guillaumekln/faster-whisper-large-v1"},
        "large-v2": {"repo_id": "guillaumekln/faster-whisper-large-v2"},
        "large-v3": {"repo_id": "guillaumekln/faster-whisper-large-v3"},
    },
    "whisper.cpp": {
        "tiny": {
            "repo_id": "ggerganov/whisper.cpp",
            "allow_patterns": ["ggml-tiny.bin"],
        },
        "base": {
            "repo_id": "ggerganov/whisper.cpp",
            "allow_patterns": ["ggml-base.bin"],
        },
        "small": {
            "repo_id": "ggerganov/whisper.cpp",
            "allow_patterns": ["ggml-small.bin"],
        },
        "medium": {
            "repo_id": "ggerganov/whisper.cpp",
            "allow_patterns": ["ggml-medium.bin"],
        },
        "large-v3": {
            "repo_id": "ggerganov/whisper.cpp",
            "allow_patterns": ["ggml-large-v3.bin"],
        },
        "small-q5_1-gguf": {
            "repo_id": "ggml-org/whisper-small-gguf",
            "allow_patterns": ["whisper-small-q5_1.gguf"],
        },
        "medium-q5_0-gguf": {
            "repo_id": "ggml-org/whisper-medium-gguf",
            "allow_patterns": ["whisper-medium-q5_0.gguf"],
        },
    },
}


def get_token(cli_token: Optional[str] = None) -> Optional[str]:
    """Return the first non-empty token from CLI args or environment."""

    if cli_token:
        return cli_token
    return os.getenv("HUGGINGFACE_HUB_TOKEN") or os.getenv("HF_TOKEN")


def resolve_models_dir(models_dir_arg: Optional[str]) -> Path:
    """Resolve the models directory according to CLI args and env vars."""

    if models_dir_arg:
        base = models_dir_arg
    else:
        base = os.getenv("ASRPROGRAM_MODELS_DIR", os.path.expanduser("~/.cache/asrprogram/models"))
    return Path(base).expanduser().resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download ASR models via Hugging Face Hub")
    parser.add_argument("--backend", default="faster-whisper", help="模型后端名称")
    parser.add_argument("--model", required=True, help="模型规格名称")
    parser.add_argument(
        "--models-dir",
        default=None,
        help="模型存放目录，默认读取 ASRPROGRAM_MODELS_DIR 或 ~/.cache/asrprogram/models",
    )
    parser.add_argument(
        "--hf-token",
        default=None,
        help="Hugging Face token；也可用环境变量 HUGGINGFACE_HUB_TOKEN/HF_TOKEN",
    )
    return parser.parse_args()


def snapshot_model(target_dir: Path, config: ModelConfig, token: Optional[str]) -> str:
    return snapshot_download(
        repo_id=config["repo_id"],
        local_dir=target_dir,
        local_dir_use_symlinks=False,
        token=token,
        resume_download=True,
        allow_patterns=config.get("allow_patterns"),
    )


def main() -> None:
    args = parse_args()

    backend_configs = REPO_MAP.get(args.backend)
    if not backend_configs:
        print(f"[ERROR] 不支持的后端: {args.backend}")
        sys.exit(2)

    config = backend_configs.get(args.model)
    if not config:
        print(f"[ERROR] 不支持的模型: {args.backend}/{args.model}")
        sys.exit(2)

    models_dir = resolve_models_dir(args.models_dir)
    target_dir = models_dir / args.backend / args.model
    target_dir.mkdir(parents=True, exist_ok=True)

    token = get_token(args.hf_token)

    try:
        local_dir = snapshot_model(target_dir, config, token)
        print(f"[OK] 模型已就绪: {local_dir}")
    except HfHubHTTPError as exc:
        print(f"[ERROR] 下载失败: {exc}")
        message = str(exc)
        if "401" in message or "403" in message:
            print("[HINT] 需要有效的 Hugging Face Token。")
            print("[HINT] 打开 https://huggingface.co/settings/tokens 新建 Read token，")
            print("[HINT] 然后设置环境变量：Windows: setx HUGGINGFACE_HUB_TOKEN \"hf_xxx\"；Linux: export HUGGINGFACE_HUB_TOKEN=hf_xxx")
            print("[HINT] 或执行：huggingface-cli login --token hf_xxx")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] 其它异常: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
