"""实现 Round 9 的并发批处理转写管线。"""  # 模块说明。
# 导入 errno 以根据错误码区分重试策略。 
import errno
# 导入 os 以检查输出目录写权限。 
import os
# 导入 time 以测量总耗时与单任务耗时。 
import time
# 导入 traceback 以在写入错误文件时记录堆栈。 
import traceback
# 导入 dataclasses 以定义任务与结果的结构化数据。 
from dataclasses import dataclass
# 导入 datetime/timezone 以在 JSON 中写入 UTC 时间。 
from datetime import datetime, timezone
# 导入 pathlib.Path 以统一路径处理。 
from pathlib import Path
# 导入 typing 中的 Any、Dict、Iterable、List、Tuple 进行类型注释。 
from typing import Any, Dict, List, Tuple

# 导入 create_transcriber 工厂以实例化后端。 
from src.asr.backends import create_transcriber
# 导入音频工具以筛选音频文件与探测时长。 
from src.utils.audio import is_audio_path, probe_duration
# 导入并发工具中的重试与线程池运行器。 
from src.utils.concurrency import RetryError, retry, run_with_threadpool
# 导入原子写入与路径辅助函数。 
from src.utils.io import atomic_write_json, atomic_write_text, file_exists, path_sans_ext, safe_mkdirs
# 导入日志工具以获取日志器、记录任务日志与进度。 
from src.utils.logging import ProgressPrinter, TaskLogger, get_logger

# 定义允许的音频扩展名列表，供扫描阶段过滤使用。 
ALLOWED_EXTENSIONS = [".wav", ".mp3", ".m4a", ".flac"]
# 定义词级与段级 JSON 的 schema 名称，保持版本一致性。 
WORD_SCHEMA = "asrprogram.wordset.v1"
SEGMENT_SCHEMA = "asrprogram.segmentset.v1"
# 定义单调性修正的微小阈值。 
EPSILON = 1e-3

# 定义可重试的异常类型，用于区分临时失败与致命错误。 
class TransientTaskError(RuntimeError):
    """表示可以通过重试恢复的暂时性任务错误。"""  # 类说明。


# 定义致命错误类型，用于立即放弃任务并避免重试。 
class FatalTaskError(RuntimeError):
    """表示无需重试的不可恢复错误。"""  # 类说明。


# 定义每个任务的输入结构，方便在线程之间传递上下文。 
@dataclass
class PipelineTask:
    """描述单个音频文件的处理目标。"""  # 类说明。

    input_path: Path  # 输入音频文件路径。
    words_path: Path  # 词级输出文件路径。
    segments_path: Path  # 段级输出文件路径。
    error_path: Path  # 错误信息文件路径。


# 定义任务结果结构，统一记录状态与统计信息。 
@dataclass
class TaskResult:
    """封装单个任务的执行结果。"""  # 类说明。

    input_path: Path  # 输入音频文件路径。
    status: str  # 任务状态 success/failed。
    attempts: int  # 实际执行次数。
    duration: float  # 单个任务耗时（秒）。
    outputs: List[str]  # 成功时生成的输出文件列表。
    error: str | None  # 失败原因描述。


# 定义任务执行上下文，包含共享资源与配置。 
@dataclass
class TaskContext:
    """为每个 worker 提供必要的共享信息。"""  # 类说明。

    backend: Any  # 后端实例，可跨线程复用。
    backend_name: str  # 后端名称，用于元信息写入。
    language: str  # 默认语言配置。
    segments_json: bool  # 是否输出段级 JSON。
    max_retries: int  # 允许的最大重试次数。
    task_logger: TaskLogger  # 任务级日志记录器。
    progress: ProgressPrinter  # 进度打印实例。


# 定义辅助函数，用于遍历输入路径并筛选音频文件。 
def _scan_audio_inputs(root: Path) -> List[Path]:
    """遍历输入路径并返回符合扩展名的音频文件列表。"""  # 函数说明。
    # 若输入路径不存在，视为致命错误，直接抛出异常。 
    if not root.exists():
        raise FileNotFoundError(f"Input path does not exist: {root}")
    # 若为目录，则递归扫描并按路径排序，保持处理顺序稳定。 
    if root.is_dir():
        candidates = sorted(path for path in root.rglob("*") if path.is_file())
    else:
        # 若为单个文件，则直接构造列表。 
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


# 定义辅助函数，构建词级与段级 JSON 载荷。 
def _build_payloads(
    audio_file: Path,
    transcription: Dict[str, Any],
    language: str,
    backend_name: str,
    segments_json: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any] | None, float]:
    """根据后端输出组装词级与段级 JSON 结构。"""  # 函数说明。
    # 拷贝后端返回的词数组以避免共享引用。 
    raw_words = [dict(word) for word in transcription.get("words", [])]
    # 执行单调性校验并统计修正次数。 
    fixed_words, adjustments = _ensure_word_monotonicity(raw_words)
    # 拷贝段级数组并确保内部 words 字段被替换。 
    segments_data = []
    for segment in transcription.get("segments", []):
        segment_copy = dict(segment)
        segment_copy["words"] = [dict(word) for word in segment_copy.get("words", [])]
        segments_data.append(segment_copy)
    # 将修正后的词重新分配回对应段落，并更新平均置信度。 
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
    # 获取时长信息，缺失时回退到 0.0，由上层再探测。 
    duration = float(transcription.get("duration_sec") or 0.0)
    # 拷贝元信息，写入修正统计与 schema。 
    meta = dict(transcription.get("meta", {}))
    if adjustments:
        meta.setdefault("postprocess", {})
        meta["postprocess"].setdefault("word_monotonicity_fixes", adjustments)
    meta.setdefault("schema_version", "round9")
    # 解析语言与后端信息，补全缺失字段。 
    resolved_language = transcription.get("language", language)
    backend_info = transcription.get("backend", {"name": backend_name})
    # 生成统一的生成时间戳。 
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    # 组装词级 JSON 结构。 
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
    # 根据配置决定是否返回段级 JSON。 
    segments_payload = None
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
    # 返回词级载荷、段级载荷与时长信息。 
    return words_payload, segments_payload, duration


# 定义核心任务函数，负责执行单个音频文件的转写与写入。 
def _transcribe_and_write_once(task: PipelineTask, context: TaskContext) -> Dict[str, Any]:
    """执行一次无重试的转写流程，失败时抛出异常。"""  # 函数说明。
    try:
        # 调用后端执行转写，可能抛出后端自定义异常。 
        transcription = context.backend.transcribe_file(str(task.input_path))
        # 根据后端输出构建词级与段级 JSON。 
        words_payload, segments_payload, duration = _build_payloads(
            task.input_path,
            transcription,
            context.language,
            context.backend_name,
            context.segments_json,
        )
        # 若后端未提供时长，则使用 ffprobe 探测补全。 
        if duration <= 0:
            duration = probe_duration(str(task.input_path))
            words_payload["audio"]["duration_sec"] = duration
            if segments_payload is not None:
                segments_payload["audio"]["duration_sec"] = duration
        # 在写入前确保错误文件被清理。 
        task.error_path.unlink(missing_ok=True)
        # 以原子方式写入词级 JSON。 
        atomic_write_json(task.words_path, words_payload)
        # 视情况写入段级 JSON。 
        if context.segments_json and segments_payload is not None:
            atomic_write_json(task.segments_path, segments_payload)
        # 返回本次写入的辅助信息，供统计使用。 
        return {
            "duration": duration,
            "outputs": [str(task.words_path)]
            + ([str(task.segments_path)] if context.segments_json and segments_payload is not None else []),
        }
    except TransientTaskError:
        # 已经被明确标记为可重试错误，直接抛出交由上层处理。 
        raise
    except FatalTaskError:
        # 已经被明确标记为致命错误，直接向上传递。 
        raise
    except OSError as exc:
        # 针对常见的可重试错误码（如 EAGAIN、EBUSY、EIO）做特殊处理。 
        if exc.errno in {errno.EAGAIN, errno.EBUSY, errno.EIO}:
            raise TransientTaskError(f"Transient I/O error: {exc}") from exc
        # 其余 OSError 多为权限或路径问题，视为致命错误。 
        raise FatalTaskError(f"Fatal I/O error: {exc}") from exc
    except Exception:
        # 未知异常保持原状交由重试装饰器分类。 
        raise


# 定义包裹重试与日志的任务执行函数。 
def _process_one(task: PipelineTask, context: TaskContext) -> TaskResult:
    """执行带重试的任务并返回结构化结果。"""  # 函数说明。
    # 记录开始日志并初始化耗时计算。 
    context.task_logger.start(str(task.input_path))
    start_time = time.monotonic()
    # 初始化尝试计数，借助列表实现可变闭包。 
    attempts = {"value": 0}
    # 定义重试回调，用于在每次失败时输出日志。 
    def _on_retry(attempt: int, exc: Exception) -> None:
        context.task_logger.retry(str(task.input_path), attempt, exc)
    # 装饰实际的执行函数以应用重试逻辑。 
    @retry(
        max_retries=max(context.max_retries, 0),
        backoff=2.0,
        jitter=True,
        retriable_exceptions=(TransientTaskError,),
        giveup_exceptions=(FatalTaskError,),
        on_retry=_on_retry,
    )
    def _execute() -> Dict[str, Any]:
        # 每次尝试前递增计数。 
        attempts["value"] += 1
        # 调用一次真正的写入逻辑。 
        return _transcribe_and_write_once(task, context)
    # 初始化状态消息，用于进度展示。 
    progress_message = "ok"
    try:
        # 在真正执行前再次校验输出目录的写权限。 
        if not os.access(task.words_path.parent, os.W_OK):
            raise FatalTaskError(f"Output directory not writable: {task.words_path.parent}")
        # 执行带重试的任务。 
        result = _execute()
        # 计算耗时。 
        duration = time.monotonic() - start_time
        # 输出成功日志。 
        context.task_logger.success(str(task.input_path), duration, attempts["value"], result["outputs"])
        # 返回成功结果。 
        return TaskResult(
            input_path=task.input_path,
            status="success",
            attempts=attempts["value"],
            duration=duration,
            outputs=result["outputs"],
            error=None,
        )
    except RetryError as exc:
        # 标记进度提示为失败。 
        progress_message = "fail"
        # 计算耗时。 
        duration = time.monotonic() - start_time
        # 记录失败日志，包含最后一次异常信息。 
        context.task_logger.failure(str(task.input_path), attempts["value"], exc.last_exception)
        # 准备错误信息文本。 
        reason = f"{exc.last_exception.__class__.__name__}: {exc.last_exception}"
        # 格式化原始堆栈信息。 
        traceback_text = "".join(
            traceback.format_exception(
                exc.last_exception.__class__, exc.last_exception, exc.last_exception.__traceback__
            )
        )
        # 写入错误文件。 
        atomic_write_text(task.error_path, f"{reason}\n{traceback_text}")
        # 返回失败结果。 
        return TaskResult(
            input_path=task.input_path,
            status="failed",
            attempts=attempts["value"],
            duration=duration,
            outputs=[],
            error=reason,
        )
    except FatalTaskError as exc:
        # 标记进度提示为失败。 
        progress_message = "fail"
        # 计算耗时。 
        duration = time.monotonic() - start_time
        # 输出失败日志。 
        context.task_logger.failure(str(task.input_path), attempts.get("value", 1) or 1, exc)
        # 写入错误文件。 
        atomic_write_text(task.error_path, f"FatalTaskError: {exc}\n")
        # 返回失败结果。 
        return TaskResult(
            input_path=task.input_path,
            status="failed",
            attempts=attempts.get("value", 1) or 1,
            duration=duration,
            outputs=[],
            error=f"FatalTaskError: {exc}",
        )
    except Exception as exc:  # noqa: BLE001
        # 标记进度提示为失败。 
        progress_message = "fail"
        # 计算耗时。 
        duration = time.monotonic() - start_time
        # 输出失败日志。 
        context.task_logger.failure(str(task.input_path), attempts.get("value", 1) or 1, exc)
        # 写入错误文件并包含堆栈。 
        traceback_text = traceback.format_exc()
        atomic_write_text(task.error_path, f"{exc.__class__.__name__}: {exc}\n{traceback_text}")
        # 对未知异常进行包装返回。 
        return TaskResult(
            input_path=task.input_path,
            status="failed",
            attempts=attempts.get("value", 1) or 1,
            duration=duration,
            outputs=[],
            error=f"{exc.__class__.__name__}: {exc}",
        )
    finally:
        # 在 finally 块中更新进度，无论成功或失败都会执行。 
        if context.progress is not None:
            context.progress.update(progress_message)


# 定义主运行函数，整合扫描、并发执行与统计逻辑。 
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
    num_workers: int = 1,
    max_retries: int = 1,
    rate_limit: float = 0.0,
    skip_done: bool = True,
    fail_fast: bool = False,
    **legacy_kwargs,
) -> dict:
    """执行批量音频转写并返回统计摘要。"""  # 函数说明。
    # 兼容旧参数名称 write_segments，若存在则覆盖 segments_json。 
    if "write_segments" in legacy_kwargs:
        segments_json = legacy_kwargs.pop("write_segments")
    # 兼容旧的 num_workers 参数（Round 8 前），直接丢弃避免冲突。 
    legacy_kwargs.pop("num_workers", None)
    # 若仍有未知参数，则抛出错误提示调用者更新调用方式。 
    if legacy_kwargs:
        unsupported = ", ".join(sorted(legacy_kwargs.keys()))
        raise TypeError(f"Unsupported arguments for pipeline.run: {unsupported}")
    # 获取项目统一的日志器，根据 verbose 控制输出级别。 
    logger = get_logger(verbose)
    # 在详细模式下打印当前配置，帮助调试。 
    if verbose:
        logger.debug(
            "Pipeline configuration input=%s out_dir=%s backend=%s workers=%d max_retries=%d rate_limit=%s skip_done=%s fail_fast=%s",
            input_path,
            out_dir,
            backend_name,
            num_workers,
            max_retries,
            rate_limit,
            skip_done,
            fail_fast,
        )
    # 将输入与输出路径转换为 Path 对象以便后续操作。 
    input_path_obj = Path(input_path)
    out_dir_obj = Path(out_dir)
    # 扫描输入路径并获取待处理音频列表。 
    audio_files = _scan_audio_inputs(input_path_obj)
    # 在详细模式下打印扫描到的文件列表。 
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
    # 使用工厂函数实例化后端，可能抛出更高层需要关注的错误。 
    backend = create_transcriber(backend_name, **backend_kwargs)
    # 创建任务级日志器。 
    task_logger = TaskLogger(logger, verbose)
    # 初始化跳过记录与任务列表。 
    skipped_items: List[dict] = []
    planned_count = 0
    tasks: List[PipelineTask] = []
    for audio_file in audio_files:
        # 生成基础名称用于拼接输出文件路径。 
        base_name = Path(path_sans_ext(audio_file)).name
        words_path = out_dir_obj / f"{base_name}.words.json"
        segments_path = out_dir_obj / f"{base_name}.segments.json"
        error_path = out_dir_obj / f"{base_name}.error.txt"
        # dry-run 模式仅记录计划并跳过实际执行。 
        if dry_run:
            task_logger.skipped(str(audio_file), "dry-run")
            planned_count += 1
            continue
        # 检查输出文件是否已存在，便于处理跳过或覆盖逻辑。 
        words_exists = file_exists(words_path)
        segments_exists = file_exists(segments_path) if segments_json else True
        outputs_ready = words_exists and segments_exists
        # skip_done 为 true 且输出完整时直接跳过。 
        if skip_done and outputs_ready and not overwrite:
            task_logger.skipped(str(audio_file), "completed")
            skipped_items.append({"input": str(audio_file), "reason": "completed"})
            error_path.unlink(missing_ok=True)
            continue
        # 即使 skip_done 为 false，只要禁止覆盖也不应重写已有结果。 
        if outputs_ready and not overwrite and not skip_done:
            task_logger.skipped(str(audio_file), "exists")
            skipped_items.append({"input": str(audio_file), "reason": "exists"})
            error_path.unlink(missing_ok=True)
            continue
        # 将任务加入待处理列表。 
        tasks.append(
            PipelineTask(
                input_path=audio_file,
                words_path=words_path,
                segments_path=segments_path,
                error_path=error_path,
            )
        )
    # 若任务列表为空，则直接返回跳过统计。 
    if dry_run and not tasks:
        return {
            "total": len(audio_files),
            "queued": 0,
            "processed": planned_count,
            "succeeded": planned_count,
            "failed": 0,
            "skipped": 0,
            "cancelled": 0,
            "retried_count": 0,
            "elapsed_sec": 0.0,
            "out_dir": str(out_dir_obj),
            "errors": [],
            "outputs": [],
            "skipped_items": [],
        }
    if not tasks:
        return {
            "total": len(audio_files),
            "queued": 0,
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": len(skipped_items),
            "cancelled": 0,
            "retried_count": 0,
            "elapsed_sec": 0.0,
            "out_dir": str(out_dir_obj),
            "errors": [],
            "outputs": [],
            "skipped_items": skipped_items,
        }
    # 创建进度打印器，verbose 模式下交由 TaskLogger 输出，仍保留进度条。 
    progress = ProgressPrinter(len(tasks), "processing", enabled=True)
    # 构造任务上下文。 
    context = TaskContext(
        backend=backend,
        backend_name=backend_name,
        language=language,
        segments_json=segments_json,
        max_retries=max_retries,
        task_logger=task_logger,
        progress=progress,
    )
    # 记录整体开始时间。 
    start_time = time.monotonic()
    # 定义 worker 函数以适配线程池接口。 
    def _worker(task: PipelineTask) -> TaskResult:
        return _process_one(task, context)
    # 使用线程池执行任务，应用限流与 fail-fast。 
    def _stop_condition(result: Any) -> bool:  # 定义 fail-fast 的停止条件。
        return isinstance(result, TaskResult) and result.status == "failed"  # 仅当任务失败时触发。
    results, submitted, _completed = run_with_threadpool(
        tasks,
        _worker,
        max_workers=max(1, num_workers),
        rate_limit=rate_limit if rate_limit > 0 else None,
        fail_fast=fail_fast,
        stop_condition=_stop_condition if fail_fast else None,
    )
    # 所有任务执行完毕后关闭进度条。 
    progress.close()
    # 计算总耗时。 
    elapsed = time.monotonic() - start_time
    # 初始化统计计数。 
    processed = 0
    succeeded = 0
    failed = 0
    retried_count = 0
    outputs: List[str] = []
    errors: List[dict] = []
    # 遍历结果列表并聚合统计。 
    for index, item in enumerate(results):
        if isinstance(item, TaskResult):
            processed += 1
            retried_count += max(0, item.attempts - 1)
            if item.status == "success":
                succeeded += 1
                outputs.extend(item.outputs)
            else:
                failed += 1
                errors.append(
                    {
                        "input": str(tasks[index].input_path),
                        "reason": item.error or "unknown",
                        "attempts": item.attempts,
                        "error_path": str(tasks[index].error_path),
                    }
                )
        elif isinstance(item, Exception):
            processed += 1
            failed += 1
            errors.append(
                {
                    "input": str(tasks[index].input_path),
                    "reason": f"Unhandled exception: {item}",
                    "attempts": 0,
                    "error_path": str(tasks[index].error_path),
                }
            )
        elif item is not None:
            # 理论上不会出现其他类型，如出现则视为失败。 
            processed += 1
            failed += 1
            errors.append(
                {
                    "input": str(tasks[index].input_path),
                    "reason": f"Unexpected result type: {type(item).__name__}",
                    "attempts": 0,
                    "error_path": str(tasks[index].error_path),
                }
            )
    # 计算取消数量（未提交或未处理的任务）。 
    cancelled = len(tasks) - submitted
    # 汇总统计信息。 
    summary = {
        "total": len(audio_files),
        "queued": len(tasks),
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": len(skipped_items),
        "cancelled": max(cancelled, 0),
        "retried_count": retried_count,
        "elapsed_sec": elapsed,
        "out_dir": str(out_dir_obj),
        "errors": errors,
        "outputs": outputs,
        "skipped_items": skipped_items,
    }
    # 返回最终汇总信息，供 CLI 或测试使用。 
    return summary
