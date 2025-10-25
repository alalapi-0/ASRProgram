"""实现 Round 7 的真实转写管线：接入 faster-whisper、ffprobe 时长与改进日志。"""  # 文件说明。
# 导入 traceback 以在写 error.txt 时包含调用栈帮助排查。
import traceback
# 导入 pathlib.Path 以处理文件与目录路径。
from pathlib import Path
# 导入 typing.List 以描述音频文件列表类型。
from typing import List

# 导入 create_transcriber 工厂以实例化指定后端。
from src.asr.backends import create_transcriber
# 导入音频工具以过滤扩展名与在必要时重新探测时长。
from src.utils.audio import is_audio_path, probe_duration
# 导入原子写入与路径相关工具，确保落盘安全。
from src.utils.io import atomic_write_json, atomic_write_text, file_exists, path_sans_ext, safe_mkdirs
# 导入统一的日志获取函数以遵循项目日志格式。
from src.utils.logging import get_logger

# 定义允许的音频扩展名列表，供扫描阶段复用。
ALLOWED_EXTENSIONS = [".wav", ".mp3", ".m4a", ".flac"]
# 定义词级与段级 JSON 的 schema 名称，便于下游识别版本。
WORD_SCHEMA = "asrprogram.wordset.v1"
SEGMENT_SCHEMA = "asrprogram.segmentset.v1"


# 定义辅助函数，用于遍历输入路径并筛选音频文件。
def _scan_audio_inputs(root: Path) -> List[Path]:
    """遍历输入路径并返回符合扩展名的音频文件列表。"""
    # 若输入路径不存在，视为致命错误，直接抛出异常。
    if not root.exists():
        raise FileNotFoundError(f"Input path does not exist: {root}")
    # 若为目录，则递归扫描所有文件并排序，保持处理顺序稳定。
    if root.is_dir():
        candidates = sorted(path for path in root.rglob("*") if path.is_file())
    else:
        # 若为单个文件，则直接构造包含该文件的列表。
        candidates = [root]
    # 使用 is_audio_path 过滤掉非音频文件，仅保留允许的扩展名。
    return [path for path in candidates if is_audio_path(path, ALLOWED_EXTENSIONS)]


# 定义主运行函数，整合扫描、推理、写入与日志逻辑。
def run(
    input_path: str,
    out_dir: str,
    backend_name: str,
    language: str = "auto",
    segments_json: bool = True,
    overwrite: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    model: str | None = None,
    compute_type: str = "auto",
    device: str = "auto",
    beam_size: int = 5,
    temperature: float = 0.0,
    vad_filter: bool = False,
    chunk_length_s: float | None = None,
    best_of: int | None = None,
    patience: float | None = None,
    **legacy_kwargs,
) -> dict:
    """执行批量音频转写并返回统计摘要。"""
    # 兼容旧参数名称 write_segments，若存在则覆盖 segments_json。
    if "write_segments" in legacy_kwargs:
        segments_json = legacy_kwargs.pop("write_segments")
    # num_workers 已在前一轮废弃，此处静默移除保持兼容。
    legacy_kwargs.pop("num_workers", None)
    # 若仍有未知参数，则抛出错误提示调用者更新调用方式。
    if legacy_kwargs:
        unsupported = ", ".join(sorted(legacy_kwargs.keys()))
        raise TypeError(f"Unsupported arguments for pipeline.run: {unsupported}")
    # 获取项目统一的日志器，根据 verbose 控制输出级别。
    logger = get_logger(verbose)
    # 将输入与输出路径转换为 Path 对象以便后续操作。
    input_path_obj = Path(input_path)
    out_dir_obj = Path(out_dir)
    # 在详细模式下输出当前配置，包括后端与推理参数。
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
        logger.debug(
            "Backend runtime options model=%s compute_type=%s device=%s beam_size=%s temperature=%s vad_filter=%s chunk_length_s=%s",
            model,
            compute_type,
            device,
            beam_size,
            temperature,
            vad_filter,
            chunk_length_s,
        )
    # 扫描输入路径并获取待处理音频列表。
    audio_files = _scan_audio_inputs(input_path_obj)
    # 在详细模式下打印扫描到的文件数量及列表。
    if verbose:
        logger.debug("Scanned %d candidate audio files", len(audio_files))
        for path in audio_files:
            logger.debug(" - %s", path)
    # 非 dry-run 模式下，确保输出目录存在。
    if not dry_run:
        safe_mkdirs(out_dir_obj)
    # 构建传递给后端的参数字典，集中管理推理选项。
    backend_kwargs = {
        "model": model,
        "language": language,
        "compute_type": compute_type,
        "device": device,
        "beam_size": beam_size,
        "temperature": temperature,
        "vad_filter": vad_filter,
        "chunk_length_s": chunk_length_s,
        "best_of": best_of,
        "patience": patience,
    }
    # 使用工厂函数实例化后端，可能抛出更高层需要关注的错误（如模型缺失）。
    backend = create_transcriber(backend_name, **backend_kwargs)
    # 若开启 verbose，则输出后端实例的类型与关键属性。
    if verbose:
        logger.debug(
            "Using backend instance %s model=%s device=%s compute_type=%s beam_size=%s temperature=%s",
            backend.__class__.__name__,
            getattr(backend, "model_path_or_name", getattr(backend, "model_name", None)),
            getattr(backend, "device", None),
            getattr(backend, "compute_type", None),
            backend_kwargs.get("beam_size"),
            backend_kwargs.get("temperature"),
        )
    # 准备汇总信息，记录处理情况。
    summary = {
        "total": len(audio_files),
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "out_dir": str(out_dir_obj),
        "errors": [],
    }
    # 遍历每个音频文件执行推理与落盘。
    for audio_file in audio_files:
        # 更新处理计数。
        summary["processed"] += 1
        # 基础名称用于拼接输出文件路径。
        base_name = Path(path_sans_ext(audio_file)).name
        # 根据命名规则构建输出文件路径。
        words_path = out_dir_obj / f"{base_name}.words.json"
        segments_path = out_dir_obj / f"{base_name}.segments.json"
        error_path = out_dir_obj / f"{base_name}.error.txt"
        # dry-run 模式仅输出计划信息，不执行任何写操作。
        if dry_run:
            logger.info("[dry-run] would write %s", words_path)
            if segments_json:
                logger.info("[dry-run] would write %s", segments_path)
            summary["succeeded"] += 1
            continue
        # 处理覆盖策略：若文件存在且未允许覆盖，则直接跳过。
        if not overwrite:
            words_exists = file_exists(words_path)
            segments_exists = file_exists(segments_path)
            if words_exists or (segments_json and segments_exists):
                logger.info("Skipping %s because output exists", audio_file)
                error_path.unlink(missing_ok=True)
                summary["succeeded"] += 1
                continue
        try:
            # 调用后端执行真实推理，返回标准化的字典结构。
            transcription = backend.transcribe_file(str(audio_file))
            # 获取后端返回的时长，若缺失或为 0 则重新探测。
            duration = float(transcription.get("duration_sec") or 0.0)
            duration_source = "backend"
            if duration <= 0:
                duration = probe_duration(str(audio_file))
                duration_source = "ffprobe"
            # 拷贝元信息以避免在后端对象上产生副作用。
            meta = dict(transcription.get("meta", {}))
            meta.setdefault("duration_source", duration_source)
            meta.setdefault("schema_version", "round7")
            # 组装词级 JSON 结构，words 数组允许为空。
            words_payload = {
                "schema": WORD_SCHEMA,
                "language": transcription.get("language", language),
                "duration_sec": duration,
                "backend": transcription.get("backend", {"name": backend_name}),
                "meta": meta,
                "words": transcription.get("words", []),
            }
            # 如需输出段级 JSON，则构造相应结构。
            if segments_json:
                segments_payload = {
                    "schema": SEGMENT_SCHEMA,
                    "language": transcription.get("language", language),
                    "duration_sec": duration,
                    "backend": transcription.get("backend", {"name": backend_name}),
                    "meta": meta,
                    "segments": transcription.get("segments", []),
                }
            # 写入前清理可能存在的旧错误文件。
            error_path.unlink(missing_ok=True)
            # 以原子方式写入词级 JSON，确保结果一致性。
            atomic_write_json(words_path, words_payload)
            # 同样以原子方式写入段级 JSON（若启用）。
            if segments_json:
                atomic_write_json(segments_path, segments_payload)
            # 更新成功计数。
            summary["succeeded"] += 1
        except Exception as exc:  # noqa: BLE001
            # 捕获单文件错误并记录日志。
            logger.error("Failed to process %s: %s", audio_file, exc)
            summary["failed"] += 1
            error_message = f"{exc.__class__.__name__}: {exc}"
            summary["errors"].append({"input": str(audio_file), "reason": error_message})
            traceback_text = traceback.format_exc()
            atomic_write_text(error_path, f"{error_message}\n{traceback_text}")
    # 处理完全部文件后输出总结。
    logger.info(
        "Pipeline finished total=%d processed=%d succeeded=%d failed=%d",
        summary["total"],
        summary["processed"],
        summary["succeeded"],
        summary["failed"],
    )
    # 返回最终汇总信息，供 CLI 或测试使用。
    return summary
