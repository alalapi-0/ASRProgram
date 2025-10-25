"""实现 Round 4 规范化的扫描与落盘管线。"""
# 导入 traceback 以在错误旁路时记录调用栈。
import traceback
# 导入 pathlib.Path 处理输入与输出路径。
from pathlib import Path
# 导入 typing.List 以对文件列表进行类型注释。
from typing import List
# 导入后端工厂以实例化占位转写器。
from src.asr.backends import create_transcriber
# 导入音频工具函数用于过滤文件与占位时长。
from src.utils.audio import is_audio_path, probe_duration
# 导入 IO 工具以进行目录创建、原子写入及辅助判断。
from src.utils.io import atomic_write_json, atomic_write_text, file_exists, path_sans_ext, safe_mkdirs
# 导入日志工具获取统一格式的日志器。
from src.utils.logging import get_logger

# 定义允许的音频扩展名列表，便于在扫描阶段复用。
ALLOWED_EXTENSIONS = [".wav", ".mp3", ".m4a", ".flac"]

# 定义辅助函数，负责根据输入路径收集所有待处理的音频文件。
def _scan_audio_inputs(root: Path) -> List[Path]:
    """遍历输入路径，返回符合扩展名要求的音频文件列表。"""
    # 如果路径不存在，直接抛出异常交由调用者处理（被视为致命错误）。
    if not root.exists():
        raise FileNotFoundError(f"Input path does not exist: {root}")
    # 如果是目录则递归遍历其下文件。
    if root.is_dir():
        # 使用 rglob 遍历全部文件，并按路径排序保证输出稳定。
        candidates = sorted(path for path in root.rglob("*") if path.is_file())
    else:
        # 若为单个文件则直接放入列表以统一处理。
        candidates = [root]
    # 使用音频工具函数过滤，确保只保留允许的扩展名。
    return [path for path in candidates if is_audio_path(path, ALLOWED_EXTENSIONS)]

# 定义主运行函数，负责 orchestrate 扫描、转写、落盘与汇总。
def run(
    input_path: str,
    out_dir: str,
    backend_name: str,
    language: str = "auto",
    segments_json: bool = True,
    overwrite: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    **legacy_kwargs,
) -> dict:
    """执行音频转写流程并返回统计汇总。"""
    # 兼容早期调用方使用的参数名称，例如 write_segments 与 num_workers。
    if "write_segments" in legacy_kwargs:
        segments_json = legacy_kwargs.pop("write_segments")
    # num_workers 在占位实现中未使用，仅为保持兼容而丢弃。
    legacy_kwargs.pop("num_workers", None)
    # 如果仍存在未知的关键字参数，则提示调用者以避免静默忽略潜在配置。
    if legacy_kwargs:
        unsupported = ", ".join(sorted(legacy_kwargs.keys()))
        raise TypeError(f"Unsupported arguments for pipeline.run: {unsupported}")
    # 获取日志器并根据 verbose 设置级别。
    logger = get_logger(verbose)
    # 将输入与输出路径转换为 Path 对象，后续统一处理。
    input_path_obj = Path(input_path)
    out_dir_obj = Path(out_dir)
    # 在详细模式下输出当前配置，便于调试与审计。
    if verbose:
        logger.debug(
            "Pipeline configuration input=%s out_dir=%s backend=%s language=%s segments_json=%s overwrite=%s dry_run=%s",
            input_path_obj,
            out_dir_obj,
            backend_name,
            language,
            segments_json,
            overwrite,
            dry_run,
        )
    # 扫描输入路径，收集所有符合扩展名的音频文件。
    audio_files = _scan_audio_inputs(input_path_obj)
    # 在详细模式下输出扫描结果数量以及每个文件的路径。
    if verbose:
        logger.debug("Scanned %d candidate audio files", len(audio_files))
        for path in audio_files:
            logger.debug(" - %s", path)
    # 若不是 dry-run，则提前创建输出目录，确保后续写入不会因目录缺失而失败。
    if not dry_run:
        safe_mkdirs(out_dir_obj)
    # 通过工厂函数实例化后端，占位实现仍然不会触发真实推理。
    backend = create_transcriber(backend_name, language=language)
    # 准备汇总字典，跟踪处理的文件数量与错误信息。
    summary = {
        "total": len(audio_files),
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "out_dir": str(out_dir_obj),
        "errors": [],
    }
    # 遍历每一个音频文件执行处理逻辑。
    for audio_file in audio_files:
        # 记录开始处理，processed 统计包含所有尝试的文件。
        summary["processed"] += 1
        # 计算基础名称，后续用于派生 words/segments/error 文件名。
        base_name = Path(path_sans_ext(audio_file)).name
        # 根据统一规则拼接输出文件路径。
        words_path = out_dir_obj / f"{base_name}.words.json"
        segments_path = out_dir_obj / f"{base_name}.segments.json"
        error_path = out_dir_obj / f"{base_name}.error.txt"
        # 若启用 dry-run，仅打印计划信息并跳过任何写操作。
        if dry_run:
            logger.info("[dry-run] would write %s", words_path)
            if segments_json:
                logger.info("[dry-run] would write %s", segments_path)
            # dry-run 视为成功处理，用于统计与上层汇报。
            summary["succeeded"] += 1
            # 继续处理下一个文件。
            continue
        # 处理覆盖策略：如果目标文件已存在且未允许覆盖，则跳过写入。
        if not overwrite:
            words_exists = file_exists(words_path)
            segments_exists = file_exists(segments_path)
            if words_exists or (segments_json and segments_exists):
                logger.info("Skipping %s because output exists", audio_file)
                # 清理潜在的遗留错误文件，避免误判。
                error_path.unlink(missing_ok=True)
                # 视为成功完成（结果已存在）。
                summary["succeeded"] += 1
                # 跳过后续写入逻辑。
                continue
        try:
            # 调用后端执行占位转写，返回统一结构的字典。
            transcription = backend.transcribe_file(str(audio_file))
            # 使用占位的探测函数获取时长，后续轮次会替换为真实实现。
            duration = probe_duration(str(audio_file))
            # 构造词级 JSON 数据结构，保证字段与后端对齐。
            words_payload = {
                "language": transcription.get("language", language),
                "duration_sec": duration,
                "backend": transcription.get("backend", {"name": backend_name}),
                "meta": transcription.get("meta", {}),
                "words": transcription.get("words", []),
            }
            # 若需要输出段级文件，则构造对应结构。
            if segments_json:
                segments_payload = {
                    "language": transcription.get("language", language),
                    "duration_sec": duration,
                    "backend": transcription.get("backend", {"name": backend_name}),
                    "meta": transcription.get("meta", {}),
                    "segments": transcription.get("segments", []),
                }
            # 若存在之前生成的错误文件，成功写入前将其删除。
            error_path.unlink(missing_ok=True)
            # 原子写入词级 JSON，确保不会留下半成品。
            atomic_write_json(words_path, words_payload)
            # 如需段级文件，则同样以原子写入方式保存。
            if segments_json:
                atomic_write_json(segments_path, segments_payload)
            # 统计成功数量。
            summary["succeeded"] += 1
        except Exception as exc:  # noqa: BLE001
            # 捕获单文件错误，确保其他文件继续执行。
            logger.error("Failed to process %s: %s", audio_file, exc)
            # 记录失败计数并准备错误摘要。
            summary["failed"] += 1
            error_message = f"{exc.__class__.__name__}: {exc}"
            summary["errors"].append({"input": str(audio_file), "reason": error_message})
            # 拼接带调用栈的完整错误文本写入 .error.txt。
            traceback_text = traceback.format_exc()
            atomic_write_text(error_path, f"{error_message}\n{traceback_text}")
    # 处理结束后输出汇总信息，普通模式下依旧保持简洁。
    logger.info(
        "Pipeline finished total=%d processed=%d succeeded=%d failed=%d",
        summary["total"],
        summary["processed"],
        summary["succeeded"],
        summary["failed"],
    )
    # 返回汇总字典供 CLI 或测试使用。
    return summary
