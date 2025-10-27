"""全自动中文 ASR 快速启动脚本，固定 faster-whisper large-v2 模型。"""  # 模块文档字符串说明脚本功能。

from __future__ import annotations  # 启用前向注解以增强类型提示兼容性。

import argparse  # 导入 argparse 用于处理命令行参数。
import os  # 导入 os 以管理环境变量与路径。
import subprocess  # 导入 subprocess 以调用项目 CLI。
import sys  # 导入 sys 以访问解释器路径与标准流。
from pathlib import Path  # 导入 Path 以进行路径拼接与遍历。
from typing import List, Optional  # 导入类型注解便于阅读与检查。

os.environ.setdefault("PYTHONUNBUFFERED", "1")  # 设置环境变量确保无缓冲输出。
try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]  # 尝试启用行缓冲输出。
except Exception:  # noqa: BLE001
    pass  # 某些运行时不支持 reconfigure，此时忽略即可。

AUDIO_EXTENSIONS = {".wav", ".flac", ".m4a", ".mp3", ".aac", ".ogg"}  # 允许处理的音频扩展名集合。
SCRIPT_ROOT = Path(__file__).resolve().parent.parent  # 推导项目根目录以便定位脚本。
DEFAULT_INPUT = (SCRIPT_ROOT / "Audio").resolve()  # 默认输入目录。
DEFAULT_OUTPUT = (SCRIPT_ROOT / "out").resolve()  # 默认输出目录。
DEFAULT_MODELS_DIR = Path(os.path.expanduser("~/.cache/asrprogram/models")).resolve()  # 默认模型缓存路径。
DOWNLOAD_SCRIPT = SCRIPT_ROOT / "scripts" / "download_model.py"  # 下载脚本路径。


class TeeStream:
    """简单的 tee 实现：将写入同时转发到控制台与日志文件。"""  # 类说明。

    def __init__(self, stream: object, log_path: Path) -> None:
        self._stream = stream  # 保存原始控制台流。
        self._log_path = log_path  # 保存日志文件路径。
        self._log_path.parent.mkdir(parents=True, exist_ok=True)  # 确保日志目录存在。
        self._log_file = open(self._log_path, "a", encoding="utf-8", buffering=1)  # 以行缓冲方式打开日志文件。

    def write(self, data: str) -> None:
        self._stream.write(data)  # 先写入原始流以保持即时输出。
        self._stream.flush()  # 立即刷新控制台缓冲。
        self._log_file.write(data)  # 再写入日志文件。
        self._log_file.flush()  # 保证日志文件实时更新。

    def flush(self) -> None:
        self._stream.flush()  # 刷新控制台流。
        self._log_file.flush()  # 刷新日志文件。

    def close(self) -> None:
        self._log_file.close()  # 关闭日志文件句柄。


def parse_args() -> argparse.Namespace:
    """定义并解析命令行参数。"""  # 函数说明。

    parser = argparse.ArgumentParser(description="Zero-interaction Chinese ASR quickstart")  # 创建解析器。
    parser.add_argument("--input", default=None, help="音频文件或文件夹路径，默认 ./Audio")  # 输入路径参数。
    parser.add_argument("--out-dir", default=None, help="输出目录，默认 ./out")  # 输出目录参数。
    parser.add_argument("--models-dir", default=None, help="模型缓存目录，默认 ~/.cache/asrprogram/models")  # 模型目录。
    parser.add_argument("--download", action="store_true", help="启动前自动检查并下载模型")  # 是否下载模型。
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        default=True,
        help="禁用所有交互式提问，全自动运行 (默认启用)",
    )  # 无交互标记，默认关闭交互。
    parser.add_argument(
        "--prompt",
        dest="no_prompt",
        action="store_false",
        help="启用交互式提问以覆盖默认路径",
    )  # 可选启用交互输入。
    parser.add_argument("--tee-log", default=None, help="将标准输出同时写入指定日志文件")  # tee 日志路径。
    parser.add_argument("--num-workers", type=int, default=1, help="传递给主 CLI 的并发 worker 数")  # worker 数量。
    parser.add_argument("--device", default=None, help="可选设备参数传递给主 CLI")  # 设备设置。
    parser.add_argument("--compute-type", default=None, help="可选精度参数传递给主 CLI")  # 精度设置。
    parser.add_argument("--hf-token", default=None, help="可选 Hugging Face token，传递给下载脚本")  # Token 覆盖。
    return parser.parse_args()  # 返回解析结果。


def prompt_value(current: Optional[str], default: Path, message: str, disabled: bool) -> Path:
    """根据 --no-prompt 设置决定是否交互获取路径。"""  # 函数说明。

    if current:  # 若命令行已提供参数。
        return Path(current).expanduser().resolve()  # 直接解析并返回。
    if disabled:  # 若禁用提示则使用默认值。
        return default  # 返回预设路径。
    user_input = input(f"{message} (默认: {default}): ").strip()  # 询问用户输入。
    return Path(user_input or str(default)).expanduser().resolve()  # 返回用户输入或默认值。


def discover_audio_files(target: Path) -> List[Path]:
    """递归扫描目标路径并返回按文件名排序的音频文件列表。"""  # 函数说明。

    if not target.exists():  # 若目标不存在。
        raise FileNotFoundError(f"输入路径不存在: {target}")  # 抛出错误提示。
    if target.is_file():  # 若目标是单个文件。
        files = [target]  # 构造单元素列表。
    else:
        files = [path for path in target.rglob("*") if path.is_file()]  # 递归收集所有文件。
    audio_files = [path for path in files if path.suffix.lower() in AUDIO_EXTENSIONS]  # 过滤音频扩展。
    audio_files.sort(key=lambda p: (p.name.lower(), str(p)))  # 按文件名排序，同时以完整路径稳定排序。
    return audio_files  # 返回有序列表。


def run_subprocess(command: List[str]) -> int:
    """执行子进程并返回退出码，同时保证实时输出。"""  # 函数说明。

    print("$ " + " ".join(command))  # 打印命令方便调试。
    return subprocess.call(command)  # 调用命令并返回退出状态。


def build_cli_command(audio_path: Path, out_dir: Path, models_dir: Path, args: argparse.Namespace) -> List[str]:
    """根据输入参数构造调用 src.cli.main 的命令列表。"""  # 函数说明。

    command: List[str] = [
        sys.executable,  # 使用当前 Python 解释器。
        "-m",
        "src.cli.main",  # 调用项目主 CLI。
        "--input",
        str(audio_path),  # 指定单个音频文件。
        "--out-dir",
        str(out_dir),  # 指定输出目录。
        "--backend",
        "faster-whisper",  # 固定后端。
        "--language",
        "zh",  # 固定语言。
        "--segments-json",
        "true",  # 始终生成段级 JSON。
        "--overwrite",
        "true",  # 允许覆盖旧结果。
        "--num-workers",
        str(max(1, args.num_workers)),  # 传递 worker 数，至少为 1。
        "--verbose",  # 启用详细日志，便于排查。
    ]
    model_root = (models_dir / "faster-whisper" / "large-v2").resolve()  # 解析固定模型的缓存目录。
    command.extend(["--set", f"runtime.model={model_root}"])  # 指定模型路径确保使用缓存。
    if args.device:  # 若用户指定设备。
        command.extend(["--set", f"runtime.device={args.device}"])  # 将设备参数传递给 CLI。
    if args.compute_type:  # 若用户指定精度。
        command.extend(["--set", f"runtime.compute_type={args.compute_type}"])  # 将精度参数传递给 CLI。
    if args.tee_log:  # 若启用 tee 日志。
        command.extend(["--tee-log", str(Path(args.tee_log).expanduser().resolve())])  # 传递给主 CLI 以同步日志文件。
    return command  # 返回命令列表。


def invoke_downloader(models_dir: Path, token: Optional[str]) -> None:
    """调用下载脚本确保模型存在。"""  # 函数说明。

    if not DOWNLOAD_SCRIPT.exists():  # 若下载脚本缺失。
        raise FileNotFoundError(f"缺少下载脚本: {DOWNLOAD_SCRIPT}")  # 提示错误。
    command = [
        sys.executable,  # 使用当前解释器。
        str(DOWNLOAD_SCRIPT),  # 下载脚本路径。
        "--backend",
        "faster-whisper",  # 固定后端。
        "--model",
        "large-v2",  # 固定模型。
        "--models-dir",
        str(models_dir),  # 指定模型目录。
    ]
    if token:  # 若提供 token。
        command.extend(["--hf-token", token])  # 将 token 传递给脚本。
    exit_code = run_subprocess(command)  # 执行下载命令。
    if exit_code != 0:  # 若下载失败。
        raise RuntimeError("模型下载失败，请检查日志后重试。")  # 抛出异常终止流程。


def ensure_model_cache(models_dir: Path, args: argparse.Namespace) -> Path:
    """确保 faster-whisper large-v2 模型已准备就绪，必要时自动下载。"""

    target_root = (models_dir / "faster-whisper" / "large-v2").resolve()
    model_files = list(target_root.glob("*.bin")) if target_root.exists() else []
    should_download = args.download or not model_files
    if should_download:
        print("[INFO] 正在检查并准备模型缓存…")
        token = args.hf_token or os.getenv("HUGGINGFACE_HUB_TOKEN") or os.getenv("HF_TOKEN")
        invoke_downloader(models_dir, token)
    return target_root


def print_token_hint() -> None:
    """输出当前 Hugging Face Token 状态并进行遮蔽。"""  # 函数说明。

    token = os.getenv("HUGGINGFACE_HUB_TOKEN") or os.getenv("HF_TOKEN")  # 读取环境变量。
    if token:  # 若 token 存在。
        masked = f"{token[:8]}***{token[-4:]}" if len(token) > 12 else "***"  # 脱敏 token。
        print(f"🔑 检测到 Hugging Face Token: {masked}")  # 输出提示。
    else:
        print("⚠️ 未检测到 Token，若模型受限可能导致 401/403。")  # 无 token 时提醒用户。


def main() -> int:
    """脚本主流程：解析参数、扫描音频并顺序转写。"""  # 函数说明。

    args = parse_args()  # 解析命令行。
    tee_stream: Optional[TeeStream] = None  # 初始化 tee 流引用。
    try:
        input_path = prompt_value(args.input, DEFAULT_INPUT, "请输入音频路径", args.no_prompt)  # 获取输入路径。
        output_dir = prompt_value(args.out_dir, DEFAULT_OUTPUT, "请输入输出目录", args.no_prompt)  # 获取输出目录。
        models_dir = prompt_value(args.models_dir, DEFAULT_MODELS_DIR, "请输入模型缓存目录", args.no_prompt)  # 获取模型目录。
        output_dir.mkdir(parents=True, exist_ok=True)  # 确保输出目录存在。
        models_dir.mkdir(parents=True, exist_ok=True)  # 确保模型目录存在。
        if args.tee_log:  # 若指定日志文件。
            tee_path = Path(args.tee_log).expanduser().resolve()  # 解析日志路径。
            tee_stream = TeeStream(sys.stdout, tee_path)  # 创建 tee 流。
            sys.stdout = tee_stream  # 将标准输出指向 tee。
        print("=== Whisper large-v2 中文转写自动流程 ===")  # 输出标题。
        print_token_hint()  # 输出 token 状态。
        model_root = ensure_model_cache(models_dir, args)
        print(f"[INFO] 模型缓存目录: {model_root}")
        audio_files = discover_audio_files(input_path)  # 扫描音频文件。
        if not audio_files:  # 若列表为空。
            print("⚠️ 未在输入路径下找到音频文件。支持扩展: " + ", ".join(sorted(AUDIO_EXTENSIONS)))  # 提示用户。
            return 0  # 不算错误。
        for index, audio_path in enumerate(audio_files, start=1):  # 逐个处理文件。
            print(f"\n[{index}/{len(audio_files)}] 处理: {audio_path}")  # 打印当前进度。
            command = build_cli_command(audio_path, output_dir, models_dir, args)  # 构建命令。
            exit_code = run_subprocess(command)  # 执行命令。
            if exit_code != 0:  # 若执行失败。
                raise RuntimeError(f"转写失败: {audio_path}")  # 抛出异常中断。
        print("\n✅ 所有文件转写完成。输出位于: " + str(output_dir))  # 输出完成提示。
        print("   - *.segments.json（段级时间轴）")  # 提醒段级文件。
        print("   - *.words.json    （词级时间轴）")  # 提醒词级文件。
        return 0  # 正常退出。
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 运行失败: {exc}")  # 打印错误信息。
        return 1  # 返回错误码。
    finally:
        if tee_stream:  # 若创建了 tee 流。
            tee_stream.flush()  # 刷新残留内容。
            tee_stream.close()  # 关闭日志文件。
            sys.stdout = tee_stream._stream  # type: ignore[attr-defined]  # 恢复原始 stdout。


if __name__ == "__main__":  # 当脚本直接运行时。
    sys.exit(main())  # 以主函数结果作为退出码。
