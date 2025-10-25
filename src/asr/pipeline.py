"""实现扫描输入、调用后端与写出结果的核心流程。"""
# 导入 pathlib.Path 处理路径。
from pathlib import Path
# 导入 typing 模块以提供类型注释。
from typing import Dict, List
# 导入后端注册表工厂函数。
from .backends import create_backend
# 导入音频工具以获取占位时长。
from src.utils.audio import probe_duration
# 导入 IO 工具以执行原子写入。
from src.utils.io import ensure_directory, write_json_atomic
# 导入日志工具以输出调试信息。
from src.utils.logging import get_logger

# 定义允许扫描的音频扩展名集合。
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac"}

# 定义运行结果的返回类型别名。
PipelineResult = Dict[str, List[Dict[str, str]]]

# 定义辅助函数，收集输入路径下的所有音频文件。
def collect_input_files(input_path: Path) -> List[Path]:
    """根据输入路径收集所有符合扩展名的音频文件。"""
    # 如果给定路径是目录，则递归遍历。
    if input_path.is_dir():
        # 使用 rglob 遍历所有文件。
        return [
            path
            for path in input_path.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
    # 如果是文件且扩展名匹配，则返回单元素列表。
    if input_path.is_file() and input_path.suffix.lower() in SUPPORTED_EXTENSIONS:
        return [input_path]
    # 其他情况返回空列表，表示未找到有效文件。
    return []

# 定义主运行函数，封装整个转写流程。
def run(
    input_path: Path,
    out_dir: Path,
    backend_name: str,
    language: str,
    write_segments: bool,
    overwrite: bool,
    num_workers: int,
    dry_run: bool,
    verbose: bool,
) -> PipelineResult:
    """执行转写管线并返回处理结果摘要。"""
    # 获取日志器以便输出运行信息。
    logger = get_logger(verbose)
    # 输出即将使用的参数信息。
    logger.debug(
        "Pipeline configuration: input=%s, out_dir=%s, backend=%s, language=%s, "
        "segments=%s, overwrite=%s, workers=%s, dry_run=%s",
        input_path,
        out_dir,
        backend_name,
        language,
        write_segments,
        overwrite,
        num_workers,
        dry_run,
    )
    # 创建后端实例以处理音频。
    backend = create_backend(backend_name)
    # 收集输入文件列表。
    input_files = collect_input_files(input_path)
    # 如果未找到任何文件，记录信息并返回空结果。
    if not input_files:
        logger.warning("No input files found for path: %s", input_path)
    # 确保输出目录存在。
    ensure_directory(out_dir)
    # 初始化结果结构体，用于记录处理、跳过与错误。
    result: PipelineResult = {
        "processed": [],
        "skipped": [],
        "errors": [],
    }
    # 遍历每一个待处理的音频文件。
    for audio_file in input_files:
        # 记录当前处理的文件。
        logger.info("Processing %s", audio_file)
        # 准备文件的基础名称，用于拼接输出文件名。
        basename = audio_file.stem
        # 构造词级与段级输出文件路径。
        words_path = out_dir / f"{basename}.words.json"
        segments_path = out_dir / f"{basename}.segments.json"
        # 处理 dry-run 情况：仅打印计划，不调用后端和写文件。
        if dry_run:
            # 记录 dry-run 提示信息。
            logger.info("Dry run: would generate %s and %s", words_path, segments_path)
            # 将条目加入 processed 列表，标记为 dry-run。
            result["processed"].append({"path": str(audio_file), "status": "dry-run"})
            # 跳过实际处理。
            continue
        # 检查是否需要覆盖已有文件。
        if not overwrite and (
            words_path.exists() or (write_segments and segments_path.exists())
        ):
            # 输出跳过信息。
            logger.info("Skipping %s because output already exists", audio_file)
            # 记录到 skipped 列表。
            result["skipped"].append({"path": str(audio_file), "reason": "exists"})
            # 继续处理下一个文件。
            continue
        try:
            # 调用后端执行转写。
            transcription = backend.transcribe_file(str(audio_file), language)
            # 获取词级与段级数据以便写入。
            words_data = {
                "metadata": transcription["metadata"],
                "words": transcription["words"],
            }
            # 若需要输出段级文件，则准备段级数据。
            if write_segments:
                segments_data = {
                    "metadata": transcription["metadata"],
                    "segments": transcription["segments"],
                }
            # 更新元数据中的 duration 字段，使用占位探测结果。
            words_data["metadata"]["duration_sec"] = probe_duration(str(audio_file))
            # 将词级 JSON 写入磁盘。
            write_json_atomic(words_path, words_data)
            # 如需写段级文件，执行写入操作。
            if write_segments:
                write_json_atomic(segments_path, segments_data)
            # 记录成功处理的文件路径。
            result["processed"].append({"path": str(audio_file), "status": "written"})
        except Exception as exc:  # noqa: BLE001
            # 捕获异常并记录错误。
            logger.error("Failed to process %s: %s", audio_file, exc)
            # 将错误信息加入结果。
            result["errors"].append({"path": str(audio_file), "error": str(exc)})
    # 返回最终的结果摘要。
    return result
