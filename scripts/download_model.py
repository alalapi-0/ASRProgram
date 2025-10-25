"""为 faster-whisper 与 whisper.cpp 准备模型下载流程。"""  # 文件文档字符串说明用途。
# 导入 argparse 解析命令行参数。
import argparse
# 导入 json 以序列化下载结果。
import json
# 导入 shutil 以执行临时文件原子移动。
import shutil
# 导入 sys 以便输出日志后退出。
import sys
# 导入 time 控制重试等待时间。
import time
# 导入 typing 中的 Dict、Iterable、List、Optional、Tuple 用于类型注释。
from typing import Dict, Iterable, List, Optional, Tuple
# 导入 pathlib.Path 统一管理文件系统路径。
from pathlib import Path

# 导入 requests 执行 HTTP 下载。
import requests  # noqa: DEP002  # 执行 HTTP 请求。
# 导入 yaml 读取默认配置。
import yaml  # 读取默认配置文件。

# faster-whisper 模型的必要元数据：仓库、文件列表与最小体积阈值。
FASTER_WHISPER_CATALOG: Dict[str, Dict[str, object]] = {
    "tiny": {  # tiny 规格模型。
        "repo": "guillaumekln/faster-whisper-tiny",  # 对应的 Hugging Face 仓库。
        "files": ["config.json", "model.bin", "tokenizer.json", "vocabulary.json"],  # 需要下载的文件列表。
        "min_bytes": 70 * 1024 * 1024,  # 最小体积阈值约 70MB。
    },
    "base": {  # base 规格模型。
        "repo": "guillaumekln/faster-whisper-base",  # 仓库名称。
        "files": ["config.json", "model.bin", "tokenizer.json", "vocabulary.json"],  # 文件列表。
        "min_bytes": 130 * 1024 * 1024,  # 最小体积约 130MB。
    },
    "small": {  # small 规格模型。
        "repo": "guillaumekln/faster-whisper-small",  # 仓库名称。
        "files": ["config.json", "model.bin", "tokenizer.json", "vocabulary.json"],  # 文件列表。
        "min_bytes": 430 * 1024 * 1024,  # 最小体积约 430MB。
    },
    "medium": {  # medium 规格模型。
        "repo": "guillaumekln/faster-whisper-medium",  # 仓库名称。
        "files": ["config.json", "model.bin", "tokenizer.json", "vocabulary.json"],  # 文件列表。
        "min_bytes": 1_400 * 1024 * 1024,  # 最小体积约 1.4GB。
    },
    "large-v3": {  # large-v3 规格模型。
        "repo": "guillaumekln/faster-whisper-large-v3",  # 仓库名称。
        "files": ["config.json", "model.bin", "tokenizer.json", "vocabulary.json"],  # 文件列表。
        "min_bytes": 3_000 * 1024 * 1024,  # 最小体积约 3GB。
    },
}

# whisper.cpp 常用 GGML/GGUF 模型映射：包含仓库、文件名与体积阈值。
WHISPER_CPP_CATALOG: Dict[str, Dict[str, object]] = {
    "tiny": {  # ggml tiny 模型。
        "repo": "ggerganov/whisper.cpp",  # 官方仓库包含 ggml-tiny.bin。
        "filename": "ggml-tiny.bin",  # 下载目标文件。
        "format": "ggml",  # 文件格式标记。
        "min_bytes": 77 * 1024 * 1024,  # 约 77MB。
    },
    "base": {  # ggml base 模型。
        "repo": "ggerganov/whisper.cpp",  # 仓库名称。
        "filename": "ggml-base.bin",  # 文件名。
        "format": "ggml",  # 文件格式。
        "min_bytes": 148 * 1024 * 1024,  # 约 148MB。
    },
    "small": {  # ggml small 模型。
        "repo": "ggerganov/whisper.cpp",  # 仓库名称。
        "filename": "ggml-small.bin",  # 文件名。
        "format": "ggml",  # 文件格式。
        "min_bytes": 488 * 1024 * 1024,  # 约 488MB。
    },
    "medium": {  # ggml medium 模型。
        "repo": "ggerganov/whisper.cpp",  # 仓库名称。
        "filename": "ggml-medium.bin",  # 文件名。
        "format": "ggml",  # 文件格式。
        "min_bytes": 1_540 * 1024 * 1024,  # 约 1.5GB。
    },
    "large-v3": {  # ggml large v3 模型。
        "repo": "ggerganov/whisper.cpp",  # 仓库名称。
        "filename": "ggml-large-v3.bin",  # 文件名。
        "format": "ggml",  # 文件格式。
        "min_bytes": 3_050 * 1024 * 1024,  # 约 3.05GB。
    },
    "small-q5_1-gguf": {  # 示例 GGUF 量化模型。
        "repo": "ggml-org/whisper-small-gguf",  # 官方 GGUF 仓库（需 Hugging Face 账户）。
        "filename": "whisper-small-q5_1.gguf",  # 文件名。
        "format": "gguf",  # 文件格式。
        "min_bytes": 240 * 1024 * 1024,  # 约 240MB。
    },
    "medium-q5_0-gguf": {  # 另一个 GGUF 量化模型。
        "repo": "ggml-org/whisper-medium-gguf",  # 仓库名称。
        "filename": "whisper-medium-q5_0.gguf",  # 文件名。
        "format": "gguf",  # 文件格式。
        "min_bytes": 780 * 1024 * 1024,  # 约 780MB。
    },
}

# 将所有支持的后端映射到各自的 catalog，便于统一处理。
SUPPORTED_CATALOGS: Dict[str, Dict[str, Dict[str, object]]] = {
    "faster-whisper": FASTER_WHISPER_CATALOG,
    "whisper.cpp": WHISPER_CPP_CATALOG,
}


# 读取仓库内的默认配置。
def load_default_config() -> Dict[str, object]:
    """读取 config/default.yaml，以便为脚本提供默认值。"""

    # 计算配置文件路径。
    config_path = Path(__file__).resolve().parent.parent / "config" / "default.yaml"
    # 打开并解析 YAML 文件。
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


# 创建命令行参数解析器。
def build_parser(defaults: Dict[str, object]) -> argparse.ArgumentParser:
    """创建命令行解析器，允许选择后端、模型与镜像。"""

    # 初始化解析器并添加描述。
    parser = argparse.ArgumentParser(description="下载 ASR 模型并写入缓存目录。")
    # 读取默认后端与模型配置。
    backend_default = defaults.get("backend", {}).get("default", "faster-whisper")
    model_default = defaults.get("model", {}).get("default", "medium")
    cache_default = defaults.get("cache_dir", ".cache/")
    models_default = defaults.get("models_dir", "~/.cache/asrprogram/models/")
    download_defaults = defaults.get("download", {})
    timeout_default = int(download_defaults.get("timeout_sec", 60))
    retries_default = int(download_defaults.get("retries", 3))
    # 计算所有模型名称列表以便提供 choices。
    all_models = sorted({*FASTER_WHISPER_CATALOG.keys(), *WHISPER_CPP_CATALOG.keys()})
    # 添加命令行参数。
    parser.add_argument("--backend", default=backend_default, choices=list(SUPPORTED_CATALOGS.keys()), help="目标后端。")
    parser.add_argument("--model", default=model_default, choices=all_models, help="需要下载的模型规格。")
    parser.add_argument("--models-dir", default=models_default, help="模型缓存主目录。")
    parser.add_argument("--cache-dir", default=cache_default, help="临时缓存目录。")
    parser.add_argument("--mirror", default=None, help="指定单个镜像源地址。")
    parser.add_argument("--force", action="store_true", help="强制重新下载，即使模型已存在。")
    parser.add_argument("--timeout", type=int, default=timeout_default, help="下载请求超时时长（秒）。")
    parser.add_argument("--retries", type=int, default=retries_default, help="单个文件最大重试次数。")
    parser.add_argument("--model-url", default=None, help="直接提供模型文件 URL（覆盖 catalog 配置）。")
    return parser


# 基于参数计算模型目录、缓存目录与临时目录。
def resolve_paths(models_dir: str, cache_dir: str, backend: str, model: str) -> Tuple[Path, Path, Path]:
    """返回模型根目录、目标目录与临时目录。"""

    # 展开用户目录并标准化路径。
    resolved_models = Path(models_dir).expanduser().resolve()
    resolved_cache = Path(cache_dir).expanduser().resolve()
    # 后端目录统一使用小写。
    backend_lower = backend.lower()
    # 模型存放在 models/<backend>/<model>/
    target_dir = resolved_models / backend_lower / model
    # 临时目录存放在 cache/tmp/<backend>/<model>/
    temp_dir = resolved_cache / "tmp" / backend_lower / model
    return resolved_models, target_dir, temp_dir


# 确保目录存在。
def ensure_directory(path: Path) -> None:
    """创建目标目录及其父目录。"""

    # 使用 mkdir 创建多级目录，若已存在则忽略。
    path.mkdir(parents=True, exist_ok=True)


# 针对 faster-whisper 判断模型是否已经就绪。
def model_ready_faster_whisper(target_dir: Path, metadata: Dict[str, object]) -> bool:
    """通过必需文件列表判断 faster-whisper 模型是否齐全。"""

    # 读取所需文件与体积阈值。
    required_files: Iterable[str] = metadata["files"]
    min_bytes: int = int(metadata["min_bytes"])
    # 收集实际文件大小。
    sizes: List[int] = []
    for filename in required_files:
        file_path = target_dir / filename
        if not file_path.exists():
            return False
        size = file_path.stat().st_size
        if size <= 0:
            return False
        sizes.append(size)
    # 计算总体积并与阈值比较。
    return sum(sizes) >= min_bytes


# 针对 whisper.cpp 判断模型文件是否就绪。
def model_ready_whisper_cpp(target_dir: Path, metadata: Dict[str, object]) -> bool:
    """检查单文件 GGML/GGUF 模型是否存在且体积合理。"""

    # 模型文件名保存在 filename 字段。
    filename = metadata["filename"]
    file_path = target_dir / filename
    if not file_path.exists():
        return False
    size = file_path.stat().st_size
    # TODO: 后续可追加哈希校验。
    return size >= int(metadata.get("min_bytes", 0))


# 根据镜像地址构造 Hugging Face 下载链接。
def build_candidate_urls(mirror: str, repo: str, filename: str) -> List[str]:
    """将镜像地址拼接为具体下载 URL。"""

    # 去除末尾斜杠以避免重复。
    normalized = mirror.rstrip("/")
    # huggingface 文件路径统一使用 /{repo}/resolve/main/{filename}
    return [f"{normalized}/{repo}/resolve/main/{filename}"]


# 执行具体的文件下载逻辑。
def download_file(urls: List[str], destination: Path, temp_dir: Path, timeout: int, retries: int) -> None:
    """尝试从候选 URL 下载文件，成功后原子移动到目标位置。"""

    # 确保临时目录存在。
    ensure_directory(temp_dir)
    # 构造临时文件路径。
    temp_path = temp_dir / f"{destination.name}.part"
    # 多次尝试下载。
    for attempt in range(1, retries + 1):
        for url in urls:
            print(f"[INFO] 下载 {destination.name} (尝试 {attempt}/{retries}) -> {url}")
            try:
                if temp_path.exists():
                    temp_path.unlink()
                with requests.get(url, stream=True, timeout=timeout) as response:
                    if response.status_code >= 400:
                        print(f"[WARN] HTTP {response.status_code} -> {response.text[:120]}")
                        continue
                    total = int(response.headers.get("Content-Length", "0"))
                    downloaded = 0
                    with temp_path.open("wb") as handle:
                        for chunk in response.iter_content(chunk_size=1_048_576):
                            if not chunk:
                                continue
                            handle.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                percent = downloaded / total * 100
                                sys.stdout.write(
                                    f"\r    已下载 {downloaded / (1024 * 1024):.1f}MB / {total / (1024 * 1024):.1f}MB ({percent:.1f}%)"
                                )
                                sys.stdout.flush()
                        sys.stdout.write("\n")
                    if destination.exists():
                        destination.unlink()
                    shutil.move(str(temp_path), str(destination))
                    return
            except requests.RequestException as error:
                print(f"[WARN] 下载失败：{error}")
                if temp_path.exists():
                    temp_path.unlink()
            except Exception as error:  # noqa: BLE001
                print(f"[WARN] 非预期错误：{error}")
                if temp_path.exists():
                    temp_path.unlink()
        print("[INFO] 等待 2 秒后重试...")
        time.sleep(2)
    raise RuntimeError(f"下载 {destination.name} 失败，请检查网络、代理或更换镜像。")


# 下载 faster-whisper 模型，返回结果字典。
def download_faster_whisper(
    model: str,
    models_root: Path,
    target_dir: Path,
    temp_dir: Path,
    mirrors: Iterable[str],
    mirror_override: Optional[str],
    timeout: int,
    retries: int,
    force: bool,
) -> Dict[str, object]:
    """下载 faster-whisper 所需的多个文件。"""

    # 获取模型元数据。
    metadata = FASTER_WHISPER_CATALOG.get(model)
    if metadata is None:
        raise ValueError(f"暂不支持模型 {model}，请编辑脚本补充映射。")
    # 创建目录。
    ensure_directory(models_root)
    ensure_directory(target_dir)
    # 若已就绪且不强制覆盖则直接返回。
    if not force and model_ready_faster_whisper(target_dir, metadata):
        print(f"[INFO] 模型已就绪，无需重新下载：{target_dir}")
        size_ready = sum((target_dir / name).stat().st_size for name in metadata["files"])
        return {"backend": "faster-whisper", "model": model, "path": str(target_dir), "size_bytes": size_ready}
    print(f"[INFO] 开始下载 faster-whisper/{model}，保存到 {target_dir}")
    candidate_mirrors = [mirror_override] if mirror_override else list(mirrors)
    if not candidate_mirrors:
        candidate_mirrors = ["https://huggingface.co"]
    for filename in metadata["files"]:
        destination = target_dir / filename
        urls: List[str] = []
        for base in candidate_mirrors:
            urls.extend(build_candidate_urls(base, metadata["repo"], filename))
        download_file(urls, destination, temp_dir, timeout, retries)
    if not model_ready_faster_whisper(target_dir, metadata):
        raise RuntimeError("模型文件校验失败，请确认磁盘空间或重试。")
    total_size = sum((target_dir / name).stat().st_size for name in metadata["files"])
    return {"backend": "faster-whisper", "model": model, "path": str(target_dir), "size_bytes": total_size}


# 下载 whisper.cpp 模型，返回模型文件路径。
def download_whisper_cpp(
    model: str,
    models_root: Path,
    target_dir: Path,
    temp_dir: Path,
    mirrors: Iterable[str],
    mirror_override: Optional[str],
    timeout: int,
    retries: int,
    force: bool,
    model_url: Optional[str],
) -> Dict[str, object]:
    """下载单文件 GGML/GGUF 模型。"""

    # 根据 catalog 获取元数据。
    metadata = WHISPER_CPP_CATALOG.get(model)
    if metadata is None and not model_url:
        raise ValueError(
            f"未找到模型 {model} 的默认配置，可使用 --model-url 手动指定 GGML/GGUF 文件。"
        )
    ensure_directory(models_root)
    ensure_directory(target_dir)
    # 当提供 model_url 时覆盖仓库/文件名。
    if model_url:
        filename = Path(model_url).name
        destination = target_dir / filename
        metadata_override = {
            "filename": filename,
            "format": Path(filename).suffix.lstrip("."),
            "min_bytes": metadata.get("min_bytes", 0) if metadata else 0,
        }
        metadata = metadata_override
        urls = [model_url]
    else:
        filename = metadata["filename"]
        destination = target_dir / filename
        urls = []
        candidate_mirrors = [mirror_override] if mirror_override else list(mirrors)
        if not candidate_mirrors:
            candidate_mirrors = ["https://huggingface.co"]
        for base in candidate_mirrors:
            urls.extend(build_candidate_urls(base, metadata["repo"], filename))
    if not force and model_ready_whisper_cpp(target_dir, metadata):
        print(f"[INFO] 模型已就绪，无需重新下载：{destination}")
        size_ready = (target_dir / metadata["filename"]).stat().st_size
        return {
            "backend": "whisper.cpp",
            "model": model,
            "path": str(destination),
            "size_bytes": size_ready,
            "format": metadata.get("format", "unknown"),
        }
    print(f"[INFO] 开始下载 whisper.cpp/{model} -> {destination}")
    download_file(urls, destination, temp_dir, timeout, retries)
    if not model_ready_whisper_cpp(target_dir, metadata):
        raise RuntimeError("模型文件校验失败，请确认磁盘空间或重试。")
    size_bytes = destination.stat().st_size
    return {
        "backend": "whisper.cpp",
        "model": model,
        "path": str(destination),
        "size_bytes": size_bytes,
        "format": metadata.get("format", "unknown"),
    }


# 根据后端调度相应的下载函数。
def download_model(
    backend: str,
    model: str,
    models_root: Path,
    target_dir: Path,
    temp_dir: Path,
    mirrors: Iterable[str],
    mirror_override: Optional[str],
    timeout: int,
    retries: int,
    force: bool,
    model_url: Optional[str],
) -> Dict[str, object]:
    """根据后端类型执行具体的下载逻辑。"""

    backend_lower = backend.lower()
    if backend_lower == "faster-whisper":
        return download_faster_whisper(
            model=model,
            models_root=models_root,
            target_dir=target_dir,
            temp_dir=temp_dir,
            mirrors=mirrors,
            mirror_override=mirror_override,
            timeout=timeout,
            retries=retries,
            force=force,
        )
    if backend_lower == "whisper.cpp":
        return download_whisper_cpp(
            model=model,
            models_root=models_root,
            target_dir=target_dir,
            temp_dir=temp_dir,
            mirrors=mirrors,
            mirror_override=mirror_override,
            timeout=timeout,
            retries=retries,
            force=force,
            model_url=model_url,
        )
    raise ValueError(f"未知后端: {backend}")


# 脚本主入口。
def main() -> None:
    """解析参数后启动下载流程。"""

    defaults = load_default_config()
    parser = build_parser(defaults)
    args = parser.parse_args()
    mirrors = defaults.get("download", {}).get("mirrors", [])
    models_root, target_dir, temp_dir = resolve_paths(args.models_dir, args.cache_dir, args.backend, args.model)
    try:
        info = download_model(
            backend=args.backend,
            model=args.model,
            models_root=models_root,
            target_dir=target_dir,
            temp_dir=temp_dir,
            mirrors=mirrors,
            mirror_override=args.mirror,
            timeout=args.timeout,
            retries=args.retries,
            force=args.force,
            model_url=args.model_url,
        )
    except Exception as error:  # noqa: BLE001
        print(f"[ERROR] 模型下载失败：{error}")
        print("[HINT] 请检查网络、代理设置或使用 --mirror/--model-url 指定备用来源。")
        print("[HINT] 某些 GGUF 仓库需要 Hugging Face 登录，可在环境变量中提供 token。")
        sys.exit(1)
    print(f"[INFO] 模型下载完成：{info['path']}")
    print(json.dumps(info, ensure_ascii=False))


# 确保脚本直接执行时运行主函数。
if __name__ == "__main__":
    main()
