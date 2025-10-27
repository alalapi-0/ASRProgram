"""使用 Hugging Face Hub 下载并缓存指定的 ASR 模型。"""  # 模块文档字符串说明脚本用途。

from __future__ import annotations  # 启用前向注解以便类型提示互引用。

import argparse  # 导入 argparse 以解析命令行参数。
import os  # 导入 os 以读取环境变量并处理路径。
import sys  # 导入 sys 以支持自定义退出状态与错误输出。
from pathlib import Path  # 导入 Path 方便地处理路径拼接与创建目录。
from typing import Optional  # 导入 Optional 用于类型注解。

from huggingface_hub import HfApi, snapshot_download  # 导入 snapshot_download 完成断点下载，HfApi 检查凭证。
from huggingface_hub.errors import HfHubHTTPError  # 导入 HfHubHTTPError 用于捕获 HTTP 层错误。


DEFAULT_BACKEND = "faster-whisper"  # 默认后端名称，满足需求固定值。
DEFAULT_MODEL = "large-v2"  # 默认模型名称，为中文场景推荐规格。
DEFAULT_MODELS_DIR = os.path.expanduser("~/.cache/asrprogram/models")  # 默认模型缓存目录。


def parse_args() -> argparse.Namespace:
    """解析命令行参数并返回命名空间对象。"""  # 函数文档字符串解释用途。

    parser = argparse.ArgumentParser(description="Download ASR models from Hugging Face Hub")  # 创建解析器并设置描述。
    parser.add_argument("--backend", default=DEFAULT_BACKEND, help="后端名称，默认 faster-whisper")  # 添加后端参数。
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型规格，默认 large-v2")  # 添加模型参数。
    parser.add_argument(
        "--models-dir",
        default=DEFAULT_MODELS_DIR,
        help="模型缓存目录，默认为 ~/.cache/asrprogram/models",
    )  # 添加缓存目录参数并给出默认值。
    parser.add_argument(
        "--hf-token",
        default=None,
        help="可选 Hugging Face token，若未提供则回退到环境变量或本地登录缓存",
    )  # 添加 token 参数。
    return parser.parse_args()  # 返回解析结果供主函数使用。


def resolve_repo_id(backend: str, model: str) -> str:
    """根据后端与模型名称推导 Hugging Face 仓库标识。"""  # 说明函数职责。

    if backend != "faster-whisper":  # 检查是否支持的后端。
        raise ValueError(f"暂不支持的后端: {backend}")  # 抛出错误以提醒用户。
    repo_id = f"guillaumekln/{backend}-{model}"  # faster-whisper 仓库命名为 faster-whisper-<model>。
    return repo_id  # 返回推导出的仓库名称。


def pick_token(cli_token: Optional[str]) -> Optional[str]:
    """按照优先级选择 Hugging Face token。"""  # 函数说明。

    if cli_token:  # 首先检查命令行是否显式提供。
        return cli_token  # 若提供则直接返回。
    env_token = os.getenv("HUGGINGFACE_HUB_TOKEN") or os.getenv("HF_TOKEN")  # 尝试读取两个常见环境变量。
    if env_token:  # 若环境变量存在。
        return env_token  # 返回环境变量值。
    try:
        stored_token = HfApi().get_token()  # 调用 HfApi 读取本地登录缓存。
        return stored_token  # 返回缓存 token，若不存在则为 None。
    except Exception:  # noqa: BLE001
        return None  # 若访问缓存失败则返回 None。


def format_token_hint(token: Optional[str]) -> str:
    """生成脱敏后的 token 提示字符串。"""  # 函数说明。

    if not token:  # 若 token 为空。
        return "⚠️ 未检测到 Hugging Face Token，若模型受限将导致 401/403。"  # 返回缺失提示。
    masked = f"{token[:8]}***{token[-4:]}" if len(token) > 12 else "***"  # 根据长度对 token 进行遮蔽。
    return f"🔑 使用 Hugging Face Token: {masked}"  # 返回格式化提示。


def ensure_directory(path: Path) -> None:
    """确保目标目录存在。"""  # 函数说明。

    path.mkdir(parents=True, exist_ok=True)  # 创建目录并允许已存在。


def main() -> int:
    """脚本主入口：解析参数、下载模型并处理异常。"""  # 函数说明。

    args = parse_args()  # 解析命令行输入。
    try:
        repo_id = resolve_repo_id(args.backend, args.model)  # 根据参数推导 Hugging Face 仓库。
    except ValueError as exc:  # 捕获不支持的后端错误。
        print(f"[ERROR] {exc}")  # 打印错误提示。
        return 2  # 返回特定退出码。
    models_root = Path(args.models_dir).expanduser().resolve()  # 解析模型缓存根目录。
    target_dir = models_root / args.backend / args.model  # 拼接具体模型目录。
    ensure_directory(target_dir)  # 确保缓存目录存在。
    token = pick_token(args.hf_token)  # 根据优先级选择 token。
    print(format_token_hint(token))  # 输出 token 状态提示。
    try:
        local_dir = snapshot_download(
            repo_id=repo_id,  # 指定模型仓库。
            local_dir=str(target_dir),  # 指定本地缓存目录。
            local_dir_use_symlinks=False,  # 禁用符号链接以兼容 Windows。
            token=token,  # 传入 token（可为 None）。
            resume_download=True,  # 启用断点续传。
        )  # 执行下载。
        print(f"[OK] 模型已就绪: {local_dir}")  # 下载成功后输出缓存路径。
        return 0  # 正常退出。
    except HfHubHTTPError as exc:  # 捕获 HTTP 层异常。
        status = getattr(exc.response, "status_code", None)  # 尝试读取状态码。
        print(f"[ERROR] 下载失败: {exc}")  # 输出基础错误信息。
        if status in {401, 403}:  # 对 401/403 提供额外说明。
            print("[HINT] 需要在 https://huggingface.co/settings/tokens 创建 Read token 并配置环境变量。")  # 提示创建 token。
            print("[HINT] Linux/macOS: export HUGGINGFACE_HUB_TOKEN='hf_xxx'")  # 提示类 Unix 系统配置方式。
            print("[HINT] Windows:    setx HUGGINGFACE_HUB_TOKEN hf_xxx")  # 提示 Windows 配置方式。
            print("[HINT] 或执行 huggingface-cli login --token hf_xxx 完成持久化登录。")  # 提示登录命令。
        else:  # 其他状态码通常为网络波动。
            print("[HINT] 请检查网络连接，或稍后重试并确保已登录 Hugging Face。")  # 给出重试建议。
        return 1  # 异常退出。
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] 未知异常: {exc}")  # 捕获其他异常并输出。
        print("[HINT] 可尝试重新运行命令，或在网络稳定后再试。")  # 提示重试建议。
        return 1  # 返回通用失败码。


if __name__ == "__main__":  # 检查脚本是否被直接执行。
    sys.exit(main())  # 将主函数返回值作为进程退出码。
