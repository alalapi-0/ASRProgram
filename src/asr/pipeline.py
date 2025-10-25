"""实现 Round 8 的转写管线：写入词级 JSON、保持单调性与元信息。"""  # 模块说明。
# 导入 datetime/timezone 以记录 UTC 生成时间。
from datetime import datetime, timezone  # noqa: F401
# 导入 traceback 以在写 error.txt 时包含调用栈帮助排查。
import traceback  # noqa: F401
# 导入 pathlib.Path 以处理文件与目录路径。
from pathlib import Path  # noqa: F401
# 导入 typing.List、Tuple 以描述音频文件列表与返回值类型。
from typing import List, Tuple  # noqa: F401

# 导入 create_transcriber 工厂以实例化指定后端。
from src.asr.backends import create_transcriber  # noqa: F401
# 导入音频工具以过滤扩展名与在必要时重新探测时长。
from src.utils.audio import is_audio_path, probe_duration  # noqa: F401
# 导入原子写入与路径相关工具，确保落盘安全。
from src.utils.io import atomic_write_json, atomic_write_text, file_exists, path_sans_ext, safe_mkdirs  # noqa: F401
# 导入统一的日志获取函数以遵循项目日志格式。
from src.utils.logging import get_logger  # noqa: F401

# 定义允许的音频扩展名列表，供扫描阶段复用。
ALLOWED_EXTENSIONS = [".wav", ".mp3", ".m4a", ".flac"]
# 定义词级与段级 JSON 的 schema 名称，便于下游识别版本。
WORD_SCHEMA = "asrprogram.wordset.v1"
SEGMENT_SCHEMA = "asrprogram.segmentset.v1"
# 定义时间修正阈值，用于单调性检查。
EPSILON = 1e-3


# 定义辅助函数，用于遍历输入路径并筛选音频文件。
def _scan_audio_inputs(root: Path) -> List[Path]:
    """遍历输入路径并返回符合扩展名的音频文件列表。"""  # 函数说明。
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


# 定义辅助函数，对词级数组执行单调性校验与必要的修正。
def _ensure_word_monotonicity(words: List[dict]) -> Tuple[List[dict], int]:
    """扫描词级结果，修复逆序时间并统计修复次数。"""  # 函数说明。
    # 创建新的列表，避免直接修改输入引用。
    fixed_words: List[dict] = []
    # 记录发生调整的词条数量。
    adjusted = 0
    # 初始化上一词结束时间。
    last_end = 0.0
    for word in words:
        # 拷贝词条以避免污染原数据。
        entry = dict(word)
        # 读取起止时间，缺失时回退到上一结束时间。
        start = float(entry.get("start", last_end))
        end = float(entry.get("end", start))
        # 若起点小于上一结束时间，则将其提升并计数。
        if start < last_end - EPSILON:
            start = last_end
            adjusted += 1
        # 若终点早于起点，则拉齐到起点位置。
        if end < start:
            end = start
            adjusted += 1
        # 更新词条中的时间字段。
        entry["start"] = start
        entry["end"] = end
        # 追加到修复后的列表。
        fixed_words.append(entry)
        # 更新上一结束时间。
        last_end = end
    # 返回修复后的词数组与调整次数。
    return fixed_words, adjusted


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
    """执行批量音频转写并返回统计摘要。"""  # 函数说明。
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
            meta.setdefault("schema_version", "round8")
            # 读取语言与后端信息，保持向后兼容。
            resolved_language = transcription.get("language", language)
            backend_info = transcription.get("backend", {"name": backend_name})
            # 拷贝段级数组，确保后续调整不会影响原始引用。
            segments_data = []
            for segment in transcription.get("segments", []):
                segment_copy = dict(segment)
                segment_copy["words"] = [dict(word) for word in segment_copy.get("words", [])]
                segments_data.append(segment_copy)
            # 从后端获取词数组，并执行单调性检查。
            raw_words = [dict(word) for word in transcription.get("words", [])]
            fixed_words, adjustments = _ensure_word_monotonicity(raw_words)
            if adjustments and verbose:
                logger.warning("Adjusted %d word timestamps for %s", adjustments, audio_file)
            # 将调整统计写回元信息，便于排查。
            if adjustments:
                meta.setdefault("postprocess", {})
                meta["postprocess"].setdefault("word_monotonicity_fixes", adjustments)
            # 根据修正后的词重新整理段内结构，确保 words.json 与 segments.json 对齐。
            segment_lookup = {segment.get("id"): segment for segment in segments_data}
            for segment in segments_data:
                segment["words"] = []
            for word in fixed_words:
                segment = segment_lookup.get(word.get("segment_id"))
                if segment is None:
                    continue
                segment["words"].append(word)
            for segment in segments_data:
                confidences = [w.get("confidence") for w in segment.get("words", []) if w.get("confidence") is not None]
                if confidences:
                    segment["avg_conf"] = sum(confidences) / len(confidences)
            # 组装词级 JSON 结构，包含音频、后端与生成时间。
            generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            words_payload = {
                "schema": WORD_SCHEMA,
                "language": resolved_language,
                "audio": {
                    "path": str(audio_file),
                    "duration_sec": duration,
                    "language": resolved_language,
                },
                "backend": backend_info,
                "meta": meta,
                "words": fixed_words,
                "generated_at": generated_at,
            }
            # 如需输出段级 JSON，则构造相应结构并嵌入最新词数组。
            if segments_json:
                segments_payload = {
                    "schema": SEGMENT_SCHEMA,
                    "language": resolved_language,
                    "audio": {
                        "path": str(audio_file),
                        "duration_sec": duration,
                        "language": resolved_language,
                    },
                    "backend": backend_info,
                    "meta": meta,
                    "segments": segments_data,
                    "generated_at": generated_at,
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
