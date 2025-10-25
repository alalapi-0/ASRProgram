#!/usr/bin/env python3  # 指定脚本使用 Python 3 解释器执行。
"""统一的 ASR 模型下载脚本，支持 faster-whisper 权重缓存。"""  # 模块文档字符串描述用途。
import argparse  # 解析命令行参数。
import json  # 输出最终结果时使用 JSON 编码。
import shutil  # 处理文件移动等操作。
import sys  # 访问标准输出并控制退出码。
import time  # 在重试时添加等待。
from pathlib import Path  # 优雅地操作路径。
from typing import Dict, Iterable, List, Optional, Tuple  # 提供类型注解增强可读性。

import requests  # 执行 HTTP 请求。
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


def load_default_config() -> Dict[str, object]:
    """读取仓库内的默认配置。"""  # 函数说明。
    config_path = Path(__file__).resolve().parent.parent / "config" / "default.yaml"  # 计算配置文件路径。
    with config_path.open("r", encoding="utf-8") as handle:  # 打开文件。
        return yaml.safe_load(handle)  # 解析 YAML 并返回字典。


def build_parser(defaults: Dict[str, object]) -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""  # 函数说明。
    parser = argparse.ArgumentParser(description="下载 ASR 模型并写入缓存目录。")  # 创建解析器并提供描述。
    backend_default = defaults.get("backend", {}).get("default", "faster-whisper")  # 读取默认后端。
    model_default = defaults.get("model", {}).get("default", "medium")  # 读取默认模型规格。
    cache_default = defaults.get("cache_dir", ".cache/")  # 读取缓存目录默认值。
    models_default = defaults.get("models_dir", "~/.cache/asrprogram/models/")  # 读取模型目录默认值。
    download_defaults = defaults.get("download", {})  # 读取下载相关配置。
    timeout_default = int(download_defaults.get("timeout_sec", 60))  # 默认超时时长。
    retries_default = int(download_defaults.get("retries", 3))  # 默认重试次数。
    parser.add_argument("--backend", default=backend_default, help="目标后端，例如 faster-whisper。")  # 后端参数。
    parser.add_argument("--model", default=model_default, choices=list(FASTER_WHISPER_CATALOG.keys()), help="需要下载的模型规格。")  # 模型参数。
    parser.add_argument("--models-dir", default=models_default, help="模型缓存主目录。")  # 模型目录参数。
    parser.add_argument("--cache-dir", default=cache_default, help="临时缓存目录。")  # 缓存目录参数。
    parser.add_argument("--mirror", default=None, help="指定单个镜像源地址。")  # 镜像参数。
    parser.add_argument("--force", action="store_true", help="强制重新下载，即使模型已存在。")  # 强制刷新开关。
    parser.add_argument("--timeout", type=int, default=timeout_default, help="下载请求的超时时长（秒）。")  # 超时参数。
    parser.add_argument("--retries", type=int, default=retries_default, help="单个文件的最大重试次数。")  # 重试参数。
    return parser  # 返回解析器实例。


def resolve_paths(models_dir: str, cache_dir: str, backend: str, model: str) -> Tuple[Path, Path, Path]:
    """基于参数计算模型目录、缓存目录与临时目录。"""  # 函数说明。
    resolved_models = Path(models_dir).expanduser().resolve()  # 展开用户目录并标准化模型目录。
    resolved_cache = Path(cache_dir).expanduser().resolve()  # 展开用户目录并标准化缓存目录。
    backend_lower = backend.lower()  # 目录名统一使用小写。
    target_dir = resolved_models / backend_lower / model  # 模型最终目录。
    temp_dir = resolved_cache / "tmp" / backend_lower / model  # 临时文件目录。
    return resolved_models, target_dir, temp_dir  # 返回三个路径。


def ensure_directory(path: Path) -> None:
    """确保目录存在。"""  # 函数说明。
    path.mkdir(parents=True, exist_ok=True)  # 创建目录及父目录，若已存在则忽略。


def model_ready(target_dir: Path, metadata: Dict[str, object]) -> bool:
    """根据必需文件与体积快速判断模型是否就绪。"""  # 函数说明。
    required_files: Iterable[str] = metadata["files"]  # 获取需要的文件。
    min_bytes: int = int(metadata["min_bytes"])  # 读取体积阈值。
    existing_sizes: List[int] = []  # 用于记录实际文件大小。
    for filename in required_files:  # 遍历每个文件。
        file_path = target_dir / filename  # 拼接文件路径。
        if not file_path.exists():  # 如果文件不存在。
            return False  # 判定为未就绪。
        size = file_path.stat().st_size  # 获取文件大小。
        if size <= 0:  # 如果大小异常。
            return False  # 判定为未就绪。
        existing_sizes.append(size)  # 记录文件大小。
    total_size = sum(existing_sizes)  # 计算总体积。
    return total_size >= min_bytes  # 与阈值比较并返回布尔值。


def build_candidate_urls(mirror: str, repo: str, filename: str) -> List[str]:
    """根据镜像地址构造下载链接。"""  # 函数说明。
    normalized_base = mirror.rstrip("/")  # 去掉结尾的斜杠。
    return [f"{normalized_base}/{repo}/resolve/main/{filename}"]  # 返回标准化 URL。


def download_file(urls: List[str], destination: Path, temp_dir: Path, timeout: int, retries: int) -> None:
    """从候选 URL 下载单个文件，成功后原子移动到目标路径。"""  # 函数说明。
    ensure_directory(temp_dir)  # 创建临时目录。
    temp_path = temp_dir / f"{destination.name}.part"  # 生成临时文件路径。
    for attempt in range(1, retries + 1):  # 按重试次数循环。
        for url in urls:  # 遍历候选地址。
            print(f"[INFO] 下载 {destination.name} (尝试 {attempt}/{retries}) -> {url}")  # 打印下载提示。
            try:  # 捕获可能的异常。
                if temp_path.exists():  # 若存在残留的临时文件。
                    temp_path.unlink()  # 在新尝试前删除临时文件。
                with requests.get(url, stream=True, timeout=timeout) as response:  # 发起流式请求。
                    if response.status_code >= 400:  # 检查状态码。
                        print(f"[WARN] 响应异常：HTTP {response.status_code}")  # 输出警告。
                        continue  # 尝试下一个 URL。
                    total = int(response.headers.get("Content-Length", "0"))  # 读取响应体积。
                    downloaded = 0  # 已下载字节数。
                    with temp_path.open("wb") as handle:  # 打开临时文件。
                        for chunk in response.iter_content(chunk_size=1_048_576):  # 按 1MB 分块写入。
                            if not chunk:  # 跳过空数据块。
                                continue  # 进入下一个块。
                            handle.write(chunk)  # 写入磁盘。
                            downloaded += len(chunk)  # 更新统计。
                            if total:  # 若已知总体积。
                                percent = downloaded / total * 100  # 计算百分比。
                                sys.stdout.write(
                                    f"\r    已下载 {downloaded / (1024 * 1024):.1f}MB / {total / (1024 * 1024):.1f}MB ({percent:.1f}%)"
                                )  # 输出进度。
                                sys.stdout.flush()  # 刷新缓冲。
                        sys.stdout.write("\n")  # 文件写入完成后换行。
                    if destination.exists():  # 若目标文件已存在。
                        destination.unlink()  # 删除旧文件以保证原子覆盖。
                    shutil.move(str(temp_path), str(destination))  # 将临时文件移动到目标路径。
                    return  # 成功则结束函数。
            except requests.RequestException as error:  # 捕获请求异常。
                print(f"[WARN] 下载失败：{error}")  # 提示网络异常。
                if temp_path.exists():  # 若存在临时文件。
                    temp_path.unlink()  # 删除不完整的文件。
            except Exception as error:  # 捕获其他异常。
                print(f"[WARN] 非预期错误：{error}")  # 输出错误详情。
                if temp_path.exists():  # 若存在临时文件。
                    temp_path.unlink()  # 删除不完整的文件。
        print("[INFO] 等待 2 秒后重试...")  # 提示重试等待。
        time.sleep(2)  # 暂停片刻再重试。
    raise RuntimeError(f"下载 {destination.name} 失败，请检查网络或更换镜像。")  # 多次尝试失败后抛出异常。


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
) -> Dict[str, object]:
    """执行模型下载并返回结果元数据。"""  # 函数说明。
    backend_lower = backend.lower()  # 规范化后端名称。
    metadata = FASTER_WHISPER_CATALOG.get(model)  # 获取模型元数据。
    if metadata is None:  # 如果未定义该模型。
        raise ValueError(f"暂不支持模型 {model}，请编辑脚本补充映射。")  # 抛出友好错误。
    ensure_directory(models_root)  # 创建模型根目录。
    ensure_directory(target_dir)  # 创建目标目录。
    if not force and model_ready(target_dir, metadata):  # 如果模型已就绪且不强制重新下载。
        print(f"[INFO] 模型已就绪，无需重新下载：{target_dir}")  # 输出提示。
        size_ready = sum((target_dir / name).stat().st_size for name in metadata["files"])  # 统计现有体积。
        return {"backend": backend_lower, "model": model, "path": str(target_dir), "size_bytes": size_ready}  # 返回现有信息。
    print(f"[INFO] 开始下载 {backend_lower}/{model}，保存到 {target_dir}")  # 打印下载开始信息。
    candidate_mirrors = [mirror_override] if mirror_override else list(mirrors)  # 构造镜像列表。
    if not candidate_mirrors:  # 若列表为空。
        candidate_mirrors = ["https://huggingface.co"]  # 回退到默认主仓库。
    for filename in metadata["files"]:  # 遍历模型文件。
        destination = target_dir / filename  # 目标文件路径。
        mirror_urls: List[str] = []  # 初始化候选 URL 列表。
        for base in candidate_mirrors:  # 遍历镜像。
            mirror_urls.extend(build_candidate_urls(base, metadata["repo"], filename))  # 添加 URL。
        download_file(mirror_urls, destination, temp_dir, timeout, retries)  # 下载单个文件。
    if not model_ready(target_dir, metadata):  # 下载完成后再次校验。
        raise RuntimeError("模型文件校验失败，请确认磁盘空间或重试。")  # 如未通过校验则报错。
    total_size = sum((target_dir / name).stat().st_size for name in metadata["files"])  # 计算总大小。
    return {"backend": backend_lower, "model": model, "path": str(target_dir), "size_bytes": total_size}  # 返回结果信息。


def main() -> None:
    """脚本主入口。"""  # 函数说明。
    defaults = load_default_config()  # 读取默认配置。
    parser = build_parser(defaults)  # 构建解析器。
    args = parser.parse_args()  # 解析参数。
    mirrors = defaults.get("download", {}).get("mirrors", [])  # 获取配置中的镜像列表。
    models_root, target_dir, temp_dir = resolve_paths(args.models_dir, args.cache_dir, args.backend, args.model)  # 解析路径。
    try:  # 捕获运行过程中可能的异常。
        info = download_model(  # 执行下载。
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
        )
    except Exception as error:  # 捕获所有异常。
        print(f"[ERROR] 模型下载失败：{error}")  # 输出错误信息。
        print("[HINT] 请检查网络、代理设置或改用 --mirror 指定备用镜像。")  # 提供提示。
        print("[HINT] 也可手动下载文件后放置到目标目录。")  # 提供手动方案。
        sys.exit(1)  # 以非零状态退出。
    print(f"[INFO] 模型下载完成：{info['path']}")  # 输出成功信息。
    print(json.dumps(info, ensure_ascii=False))  # 以 JSON 格式输出结果。


if __name__ == "__main__":  # 确保脚本直接执行时运行主函数。
    main()  # 调用主函数。
