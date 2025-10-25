"""实现 Round 11 的并发批处理转写管线，强化锁与完整性校验。"""  # 模块说明。
# 导入 errno 以识别常见 I/O 错误码并辅助错误分类。 
import errno
# 导入 json 以读取已有 words.json 用于哈希比对。 
import json
# 导入 os 以检查目录权限等。 
import os
# 导入 time 以测量耗时与控制重试。 
import time
# 导入 traceback 以在错误文件中写入堆栈信息。 
import traceback
# 导入 dataclass 用于结构化任务与结果。 
from dataclasses import dataclass
# 导入 datetime 与 timezone 以生成 UTC 时间戳。 
from datetime import datetime, timezone
# 导入 pathlib.Path 统一路径处理。 
from pathlib import Path
# 导入 typing 类型注释。 
from typing import Any, Dict, List, Tuple

# 导入后端工厂以实例化转写器。 
from src.asr.backends import create_transcriber
# 导入音频工具以筛选文件与探测时长。 
from src.utils.audio import is_audio_path, probe_duration
# 导入并发工具的重试装饰器与线程池运行器。 
from src.utils.concurrency import RetryError, retry, run_with_threadpool
# 导入错误类型与分类工具。 
from src.utils.errors import NonRetryableError, RetryableError, classify_exception
# 导入 I/O 工具以执行原子写入、清理与锁定。 
from src.utils.io import (
    atomic_write_json,
    atomic_write_text,
    cleanup_partials,
    file_exists,
    path_sans_ext,
    safe_mkdirs,
    sha256_file,
    with_file_lock,
)
# 导入日志工具用于打印细粒度日志与进度。 
from src.utils.logging import ProgressPrinter, TaskLogger, get_logger
# 导入 Manifest 工具以在处理各阶段记录状态。 
from src.utils.manifest import append_record as manifest_append_record, load_index as manifest_load_index

# 定义允许的音频扩展名集合。 
ALLOWED_EXTENSIONS = [".wav", ".mp3", ".m4a", ".flac"]
# 定义词级与段级 JSON 的 schema 标识。 
WORD_SCHEMA = "asrprogram.wordset.v1"
SEGMENT_SCHEMA = "asrprogram.segmentset.v1"
# 定义修正逆序时间的微小阈值。 
EPSILON = 1e-3

# 定义任务结构体，集中存储单个音频文件的所有派生路径。 
@dataclass
class PipelineTask:
    """描述单个音频文件需要的输出路径与锁路径。"""  # 类说明。

    input_path: Path  # 输入音频文件路径。
    base_name: str  # 去除扩展名后的基名，复用以构造输出文件。
    words_path: Path  # 词级输出文件路径。
    segments_path: Path  # 段级输出文件路径。
    error_path: Path  # 错误文本输出路径。
    lock_path: Path  # 与该输入绑定的锁文件路径。


# 定义任务结果结构，便于聚合统计。 
@dataclass
class TaskResult:
    """封装任务执行后的状态、耗时与附加信息。"""  # 类说明。

    input_path: Path  # 输入文件路径。
    status: str  # success/failed/skipped。
    attempts: int  # 实际尝试次数。
    duration: float  # 任务耗时（秒）。
    outputs: List[str]  # 成功生成的文件列表。
    error: str | None  # 失败原因文本。
    skipped_reason: str | None = None  # 跳过原因描述。
    stale: bool = False  # 是否因哈希失配被判定为陈旧。
    hash_value: str | None = None  # 最新计算的音频哈希。


# 定义任务上下文结构，包含共享资源与配置。 
@dataclass
class TaskContext:
    """封装 worker 执行单个任务时需要的共享状态。"""  # 类说明。

    backend: Any  # 后端实例。
    backend_name: str  # 后端名称，用于 Manifest 与 JSON。
    language: str  # 语言参数。
    segments_json: bool  # 是否输出段级 JSON。
    max_retries: int  # 最大重试次数。
    task_logger: TaskLogger  # 任务级日志器。
    progress: ProgressPrinter  # 进度打印器。
    skip_done: bool  # 是否跳过已完成任务。
    overwrite: bool  # 是否覆盖已有结果。
    force: bool  # 是否强制重跑。
    integrity_check: bool  # 是否启用 SHA-256 校验。
    lock_timeout: float  # 文件锁超时时间。
    cleanup_temp: bool  # 是否清理历史临时文件。
    manifest_path: Path  # Manifest 文件路径。
    manifest_index: Dict[str, Dict[str, Any]]  # 运行前加载的 Manifest 索引。
    out_dir: Path  # 输出目录路径。


# 定义兼容旧版测试的异常别名。
class TransientTaskError(RetryableError):
    """兼容 Round 9 测试的可重试异常别名。"""  # 类说明。


class FatalTaskError(NonRetryableError):
    """兼容 Round 9 测试的致命异常别名。"""  # 类说明。


# 定义辅助函数：遍历输入路径并筛选音频文件。 
def _scan_audio_inputs(root: Path) -> List[Path]:
    """遍历输入路径并返回符合音频扩展名的文件列表。"""  # 函数说明。
    # 若输入路径不存在则直接抛出异常。 
    if not root.exists():
        raise FileNotFoundError(f"Input path does not exist: {root}")
    # 若为目录则递归遍历并过滤文件。 
    if root.is_dir():
        candidates = sorted(path for path in root.rglob("*") if path.is_file())
    else:
        # 单文件输入直接形成列表。 
        candidates = [root]
    # 使用 is_audio_path 过滤出合法音频文件。 
    return [path for path in candidates if is_audio_path(path, ALLOWED_EXTENSIONS)]


# 定义辅助函数：修正词级结果的时间逆序问题。 
def _ensure_word_monotonicity(words: List[dict]) -> Tuple[List[dict], int]:
    """确保词级时间单调递增，并统计修正次数。"""  # 函数说明。
    fixed_words: List[dict] = []  # 用于存放修正后的词数组。
    adjusted = 0  # 记录需要调整的词条数量。
    last_end = 0.0  # 记录上一词的结束时间。
    for word in words:
        entry = dict(word)  # 拷贝词条避免修改原数据。
        start = float(entry.get("start", last_end))  # 读取起始时间。
        end = float(entry.get("end", start))  # 读取结束时间。
        if start < last_end - EPSILON:  # 若起点逆序则抬升到上一结束。
            start = last_end
            adjusted += 1
        if end < start:  # 若终点早于起点则同步到起点。
            end = start
            adjusted += 1
        entry["start"] = start  # 写回修正后的起点。
        entry["end"] = end  # 写回修正后的终点。
        fixed_words.append(entry)  # 追加到新数组。
        last_end = end  # 更新上一词结束时间。
    return fixed_words, adjusted  # 返回修正结果与次数。


# 定义辅助函数：根据后端输出构建词级与段级 JSON。 
def _build_payloads(
    audio_file: Path,
    transcription: Dict[str, Any],
    language: str,
    backend_name: str,
    segments_json: bool,
    audio_hash: str | None,
) -> Tuple[Dict[str, Any], Dict[str, Any] | None, float]:
    """依据后端结果构建 words/segments JSON 结构并返回时长。"""  # 函数说明。
    raw_words = [dict(word) for word in transcription.get("words", [])]  # 拷贝词数组。
    fixed_words, adjustments = _ensure_word_monotonicity(raw_words)  # 修正逆序时间。
    segments_data = []  # 初始化段级数据容器。
    for segment in transcription.get("segments", []):
        segment_copy = dict(segment)  # 拷贝段数据。
        segment_copy["words"] = [dict(word) for word in segment_copy.get("words", [])]  # 深拷贝子词条。
        segments_data.append(segment_copy)  # 添加到列表。
    segment_lookup = {segment.get("id"): segment for segment in segments_data}  # 建立段 id 索引。
    for segment in segments_data:
        segment["words"] = []  # 预先清空 words 字段。
    for word in fixed_words:
        segment = segment_lookup.get(word.get("segment_id"))  # 查找词所属段。
        if segment is None:
            continue
        segment["words"].append(word)  # 将词附加到对应段落。
    for segment in segments_data:
        confidences = [w.get("confidence") for w in segment.get("words", []) if w.get("confidence") is not None]
        if confidences:
            segment["avg_conf"] = sum(confidences) / len(confidences)  # 计算平均置信度。
    duration = float(transcription.get("duration_sec") or 0.0)  # 读取后端返回的时长。
    meta = dict(transcription.get("meta", {}))  # 拷贝元信息。
    if adjustments:  # 若发生时间修正则写入统计信息。
        meta.setdefault("postprocess", {})
        meta["postprocess"].setdefault("word_monotonicity_fixes", adjustments)
    meta.setdefault("schema_version", "round11")  # 更新 schema 版本标签。
    resolved_language = transcription.get("language", language)  # 解析语言字段。
    backend_info = transcription.get("backend", {"name": backend_name})  # 补全后端信息。
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")  # 生成 UTC 时间戳。
    words_payload = {
        "schema": WORD_SCHEMA,
        "language": resolved_language,
        "audio": {
            "path": str(audio_file),
            "duration_sec": duration,
            "language": resolved_language,
            "hash_sha256": audio_hash,
        },
        "backend": backend_info,
        "meta": meta,
        "words": fixed_words,
        "generated_at": generated_at,
    }
    segments_payload = None  # 默认不输出段级。
    if segments_json:
        segments_payload = {
            "schema": SEGMENT_SCHEMA,
            "language": resolved_language,
            "audio": {
                "path": str(audio_file),
                "duration_sec": duration,
                "language": resolved_language,
                "hash_sha256": audio_hash,
            },
            "backend": backend_info,
            "meta": meta,
            "segments": segments_data,
            "generated_at": generated_at,
        }
    return words_payload, segments_payload, duration  # 返回构造的载荷与时长。


# 定义辅助函数：读取现有 words.json 的音频元数据。 
def _load_existing_audio_info(words_path: Path) -> Tuple[str | None, float | None]:
    """尝试读取已有 words.json 的音频哈希与时长。"""  # 函数说明。
    if not words_path.exists():
        return None, None
    try:
        with words_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:  # noqa: BLE001
        return None, None
    audio = data.get("audio", {})
    hash_value = audio.get("hash_sha256")
    duration = audio.get("duration_sec")
    return (str(hash_value) if hash_value else None, float(duration) if duration is not None else None)


# 定义辅助函数：生成 Manifest 时间戳。 
def _manifest_timestamp() -> str:
    """返回当前 UTC 时间戳的 ISO8601 字符串。"""  # 函数说明。
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# 定义执行一次转写与写入的函数。 
def _transcribe_and_write_once(
    task: PipelineTask,
    context: TaskContext,
    audio_hash: str | None,
) -> Dict[str, Any]:
    """执行一次转写调用并落盘，失败时抛出异常。"""  # 函数说明。
    try:
        transcription = context.backend.transcribe_file(str(task.input_path))  # 调用后端完成转写。
        words_payload, segments_payload, duration = _build_payloads(
            task.input_path,
            transcription,
            context.language,
            context.backend_name,
            context.segments_json,
            audio_hash,
        )
        if duration <= 0:  # 若后端未返回时长则调用 probe_duration 探测。
            duration = probe_duration(str(task.input_path))
            words_payload["audio"]["duration_sec"] = duration
            if segments_payload is not None:
                segments_payload["audio"]["duration_sec"] = duration
        task.error_path.unlink(missing_ok=True)  # 在写入前移除旧的错误文件。
        atomic_write_json(task.words_path, words_payload)  # 原子写入词级 JSON。
        outputs = [str(task.words_path)]  # 初始化输出列表。
        if context.segments_json and segments_payload is not None:
            atomic_write_json(task.segments_path, segments_payload)
            outputs.append(str(task.segments_path))
        return {"duration": duration, "outputs": outputs}  # 返回写入结果供统计使用。
    except RetryableError:
        raise  # 已有明确分类的可重试错误直接抛出。
    except NonRetryableError:
        raise  # 不可重试错误直接抛出给上层。
    except OSError as exc:
        if exc.errno in {errno.EAGAIN, errno.EBUSY, errno.EIO, errno.ETIMEDOUT}:  # 常见的暂时性 I/O 错误。
            raise TransientTaskError(f"Transient I/O error: {exc}") from exc
        raise FatalTaskError(f"Fatal I/O error: {exc}") from exc  # 其他 I/O 错误视为不可重试。
    except Exception as exc:  # noqa: BLE001
        raise TransientTaskError(f"Unknown backend error: {exc}") from exc  # 默认回退为可重试错误。


# 定义任务执行函数，负责锁定、哈希校验与 Manifest 记录。 
def _process_one(task: PipelineTask, context: TaskContext) -> TaskResult:
    """执行单个任务的完整生命周期并返回结果。"""  # 函数说明。
    context.task_logger.start(str(task.input_path))  # 输出开始日志。
    start_time = time.monotonic()  # 记录起始时间。
    attempts = {"value": 0}  # 可变字典用于记录尝试次数。
    # 根据配置计算音频哈希，缺失时置为 None。 
    audio_hash: str | None = None
    if context.integrity_check:
        try:
            audio_hash = sha256_file(task.input_path)
        except FileNotFoundError as exc:
            reason = f"NonRetryableError: {exc}"
            atomic_write_text(task.error_path, f"{reason}\n")
            manifest_append_record(
                context.manifest_path,
                {
                    "ts": _manifest_timestamp(),
                    "input": str(task.input_path),
                    "input_hash_sha256": None,
                    "status": "failed",
                    "backend": context.backend_name,
                    "out": {},
                    "duration_sec": 0.0,
                    "elapsed_sec": 0.0,
                    "error": {"type": "NonRetryableError", "message": str(exc)},
                },
            )
            return TaskResult(
                input_path=task.input_path,
                status="failed",
                attempts=0,
                duration=0.0,
                outputs=[],
                error=reason,
            )
    # 若需要清理残留临时文件，可在加锁后执行。 
    try:
        with with_file_lock(task.lock_path, context.lock_timeout):
            if context.cleanup_temp:
                cleanup_partials(context.out_dir, task.base_name)
            words_exists = file_exists(task.words_path)
            segments_exists = file_exists(task.segments_path) if context.segments_json else True
            outputs_ready = words_exists and segments_exists
            existing_hash, existing_duration = _load_existing_audio_info(task.words_path)
            skip_reason = None
            stale = False
            if not context.force and outputs_ready:
                if context.integrity_check and audio_hash and existing_hash:
                    if existing_hash == audio_hash and context.skip_done and not context.overwrite:
                        skip_reason = "completed"
                    elif existing_hash != audio_hash and not context.overwrite:
                        skip_reason = "stale"
                        stale = True
                if skip_reason is None and not context.overwrite:
                    if context.skip_done:
                        skip_reason = "completed"
                    else:
                        skip_reason = "exists"
            if skip_reason is not None:
                context.task_logger.skipped(str(task.input_path), skip_reason)
                task.error_path.unlink(missing_ok=True)
                error_payload = (
                    {"type": "StaleResult", "message": "stale result; use --overwrite true to rebuild"}
                    if stale
                    else {"type": "Skip", "message": skip_reason}
                )
                manifest_append_record(
                    context.manifest_path,
                    {
                        "ts": _manifest_timestamp(),
                        "input": str(task.input_path),
                        "input_hash_sha256": audio_hash or existing_hash,
                        "status": "skipped",
                        "backend": context.backend_name,
                        "out": {
                            "words": str(task.words_path) if words_exists else None,
                            "segments": str(task.segments_path) if segments_exists and context.segments_json else None,
                        },
                        "duration_sec": existing_duration or 0.0,
                        "elapsed_sec": time.monotonic() - start_time,
                        "error": error_payload,
                    },
                )
                message = "stale" if stale else skip_reason
                context.progress.update(message)
                return TaskResult(
                    input_path=task.input_path,
                    status="skipped",
                    attempts=0,
                    duration=time.monotonic() - start_time,
                    outputs=[str(task.words_path)] if words_exists else [],
                    error=None,
                    skipped_reason=skip_reason,
                    stale=stale,
                    hash_value=audio_hash or existing_hash,
                )
            task.error_path.unlink(missing_ok=True)
            manifest_append_record(
                context.manifest_path,
                {
                    "ts": _manifest_timestamp(),
                    "input": str(task.input_path),
                    "input_hash_sha256": audio_hash,
                    "status": "started",
                    "backend": context.backend_name,
                    "out": {},
                    "duration_sec": 0.0,
                    "elapsed_sec": 0.0,
                    "error": None,
                },
            )
            def _on_retry(attempt: int, exc: Exception) -> None:
                context.task_logger.retry(str(task.input_path), attempt, exc)
            @retry(
                max_retries=max(context.max_retries, 0),
                backoff=2.0,
                jitter=True,
                retriable_exceptions=(RetryableError,),
                giveup_exceptions=(NonRetryableError,),
                on_retry=_on_retry,
            )
            def _execute() -> Dict[str, Any]:
                attempts["value"] += 1
                return _transcribe_and_write_once(task, context, audio_hash)
            try:
                result = _execute()
                duration = time.monotonic() - start_time
                context.task_logger.success(str(task.input_path), duration, attempts["value"], result["outputs"])
                manifest_append_record(
                    context.manifest_path,
                    {
                        "ts": _manifest_timestamp(),
                        "input": str(task.input_path),
                        "input_hash_sha256": audio_hash,
                        "status": "succeeded",
                        "backend": context.backend_name,
                        "out": {
                            "words": str(task.words_path),
                            "segments": str(task.segments_path) if context.segments_json else None,
                        },
                        "duration_sec": result.get("duration", 0.0),
                        "elapsed_sec": duration,
                        "error": None,
                    },
                )
                context.progress.update("ok")
                return TaskResult(
                    input_path=task.input_path,
                    status="success",
                    attempts=attempts["value"],
                    duration=duration,
                    outputs=result["outputs"],
                    error=None,
                    hash_value=audio_hash,
                )
            except RetryError as exc:
                duration = time.monotonic() - start_time
                context.task_logger.failure(str(task.input_path), attempts["value"], exc.last_exception)
                reason = f"{exc.last_exception.__class__.__name__}: {exc.last_exception}"
                traceback_text = "".join(
                    traceback.format_exception(
                        exc.last_exception.__class__, exc.last_exception, exc.last_exception.__traceback__
                    )
                )
                atomic_write_text(task.error_path, f"{reason}\n{traceback_text}")
                manifest_append_record(
                    context.manifest_path,
                    {
                        "ts": _manifest_timestamp(),
                        "input": str(task.input_path),
                        "input_hash_sha256": audio_hash,
                        "status": "failed",
                        "backend": context.backend_name,
                        "out": {},
                        "duration_sec": 0.0,
                        "elapsed_sec": duration,
                        "error": {
                            "type": classify_exception(exc.last_exception),
                            "message": reason,
                        },
                    },
                )
                if context.cleanup_temp:
                    cleanup_partials(context.out_dir, task.base_name)
                context.progress.update("fail")
                return TaskResult(
                    input_path=task.input_path,
                    status="failed",
                    attempts=attempts["value"],
                    duration=duration,
                    outputs=[],
                    error=reason,
                    hash_value=audio_hash,
                )
            except NonRetryableError as exc:
                duration = time.monotonic() - start_time
                context.task_logger.failure(str(task.input_path), attempts.get("value", 1), exc)
                atomic_write_text(task.error_path, f"NonRetryableError: {exc}\n")
                manifest_append_record(
                    context.manifest_path,
                    {
                        "ts": _manifest_timestamp(),
                        "input": str(task.input_path),
                        "input_hash_sha256": audio_hash,
                        "status": "failed",
                        "backend": context.backend_name,
                        "out": {},
                        "duration_sec": 0.0,
                        "elapsed_sec": duration,
                        "error": {"type": "non-retryable", "message": str(exc)},
                    },
                )
                if context.cleanup_temp:
                    cleanup_partials(context.out_dir, task.base_name)
                context.progress.update("fail")
                return TaskResult(
                    input_path=task.input_path,
                    status="failed",
                    attempts=attempts.get("value", 1),
                    duration=duration,
                    outputs=[],
                    error=str(exc),
                    hash_value=audio_hash,
                )
            except Exception as exc:  # noqa: BLE001
                duration = time.monotonic() - start_time
                context.task_logger.failure(str(task.input_path), attempts.get("value", 1), exc)
                traceback_text = traceback.format_exc()
                atomic_write_text(task.error_path, f"{exc.__class__.__name__}: {exc}\n{traceback_text}")
                manifest_append_record(
                    context.manifest_path,
                    {
                        "ts": _manifest_timestamp(),
                        "input": str(task.input_path),
                        "input_hash_sha256": audio_hash,
                        "status": "failed",
                        "backend": context.backend_name,
                        "out": {},
                        "duration_sec": 0.0,
                        "elapsed_sec": duration,
                        "error": {"type": "unknown", "message": str(exc)},
                    },
                )
                if context.cleanup_temp:
                    cleanup_partials(context.out_dir, task.base_name)
                context.progress.update("fail")
                return TaskResult(
                    input_path=task.input_path,
                    status="failed",
                    attempts=attempts.get("value", 1),
                    duration=duration,
                    outputs=[],
                    error=f"{exc.__class__.__name__}: {exc}",
                    hash_value=audio_hash,
                )
    except TimeoutError as exc:
        context.task_logger.skipped(str(task.input_path), "lock-timeout")
        manifest_append_record(
            context.manifest_path,
            {
                "ts": _manifest_timestamp(),
                "input": str(task.input_path),
                "input_hash_sha256": audio_hash,
                "status": "skipped",
                "backend": context.backend_name,
                "out": {},
                "duration_sec": 0.0,
                "elapsed_sec": time.monotonic() - start_time,
                "error": {"type": "LockTimeout", "message": str(exc)},
            },
        )
        context.progress.update("lock")
        return TaskResult(
            input_path=task.input_path,
            status="skipped",
            attempts=0,
            duration=time.monotonic() - start_time,
            outputs=[],
            error=None,
            skipped_reason="lock-timeout",
            hash_value=audio_hash,
        )


# 定义主运行函数，协调扫描、并发执行与 Manifest。 
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
    integrity_check: bool = True,
    lock_timeout: float = 30.0,
    cleanup_temp: bool = True,
    manifest_path: str | None = None,
    force: bool = False,
    **legacy_kwargs,
) -> dict:
    """执行批量音频转写并返回统计摘要。"""  # 函数说明。
    if "write_segments" in legacy_kwargs:
        segments_json = legacy_kwargs.pop("write_segments")
    legacy_kwargs.pop("num_workers", None)
    if legacy_kwargs:
        unsupported = ", ".join(sorted(legacy_kwargs.keys()))
        raise TypeError(f"Unsupported arguments for pipeline.run: {unsupported}")
    logger = get_logger(verbose)
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
    input_path_obj = Path(input_path)
    out_dir_obj = Path(out_dir)
    manifest_path_obj = Path(manifest_path) if manifest_path else out_dir_obj / "_manifest.jsonl"
    audio_files = _scan_audio_inputs(input_path_obj)
    if verbose:
        logger.debug("Scanned %d candidate audio files", len(audio_files))
        for path in audio_files:
            logger.debug(" - %s", path)
    if not dry_run:
        safe_mkdirs(out_dir_obj)
        safe_mkdirs(manifest_path_obj.parent)
    manifest_index = manifest_load_index(manifest_path_obj) if manifest_path_obj.exists() else {}
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
    backend = create_transcriber(backend_name, **backend_kwargs)
    task_logger = TaskLogger(logger, verbose)
    skipped_items: List[dict] = []
    planned_count = 0
    tasks: List[PipelineTask] = []
    for audio_file in audio_files:
        base_name = Path(path_sans_ext(audio_file)).name
        words_path = out_dir_obj / f"{base_name}.words.json"
        segments_path = out_dir_obj / f"{base_name}.segments.json"
        error_path = out_dir_obj / f"{base_name}.error.txt"
        lock_path = out_dir_obj / f"{base_name}.lock"
        if dry_run:
            task_logger.skipped(str(audio_file), "dry-run")
            planned_count += 1
            continue
        tasks.append(
            PipelineTask(
                input_path=audio_file,
                base_name=base_name,
                words_path=words_path,
                segments_path=segments_path,
                error_path=error_path,
                lock_path=lock_path,
            )
        )
    if dry_run:
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
            "manifest_path": str(manifest_path_obj),
            "errors": [],
            "outputs": [],
            "skipped_items": skipped_items,
            "skipped_stale": 0,
            "lock_conflicts": 0,
        }
    if not tasks:
        return {
            "total": len(audio_files),
            "queued": 0,
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "cancelled": 0,
            "retried_count": 0,
            "elapsed_sec": 0.0,
            "out_dir": str(out_dir_obj),
            "manifest_path": str(manifest_path_obj),
            "errors": [],
            "outputs": [],
            "skipped_items": skipped_items,
            "skipped_stale": 0,
            "lock_conflicts": 0,
        }
    progress = ProgressPrinter(len(tasks), "processing", enabled=True)
    context = TaskContext(
        backend=backend,
        backend_name=backend_name,
        language=language,
        segments_json=segments_json,
        max_retries=max_retries,
        task_logger=task_logger,
        progress=progress,
        skip_done=skip_done,
        overwrite=overwrite,
        force=force,
        integrity_check=integrity_check,
        lock_timeout=lock_timeout,
        cleanup_temp=cleanup_temp,
        manifest_path=manifest_path_obj,
        manifest_index=manifest_index,
        out_dir=out_dir_obj,
    )
    start_time = time.monotonic()
    def _worker(task_item: PipelineTask) -> TaskResult:
        return _process_one(task_item, context)
    def _stop_condition(result: Any) -> bool:
        return isinstance(result, TaskResult) and result.status == "failed"
    results, submitted, _completed = run_with_threadpool(
        tasks,
        _worker,
        max_workers=max(1, num_workers),
        rate_limit=rate_limit if rate_limit > 0 else None,
        fail_fast=fail_fast,
        stop_condition=_stop_condition if fail_fast else None,
    )
    progress.close()
    elapsed = time.monotonic() - start_time
    processed = 0
    succeeded = 0
    failed = 0
    retried_count = 0
    outputs: List[str] = []
    errors: List[dict] = []
    skipped_count = 0
    skipped_stale = 0
    lock_conflicts = 0
    for index, item in enumerate(results):
        if isinstance(item, TaskResult):
            if item.status == "success":
                processed += 1
                succeeded += 1
                retried_count += max(0, item.attempts - 1)
                outputs.extend(item.outputs)
            elif item.status == "failed":
                processed += 1
                failed += 1
                retried_count += max(0, item.attempts - 1)
                errors.append(
                    {
                        "input": str(tasks[index].input_path),
                        "reason": item.error or "unknown",
                        "attempts": item.attempts,
                        "error_path": str(tasks[index].error_path),
                    }
                )
            elif item.status == "skipped":
                skipped_count += 1
                reason = item.skipped_reason or "skipped"
                if item.stale:
                    skipped_stale += 1
                if reason == "lock-timeout":
                    lock_conflicts += 1
                skipped_items.append({"input": str(tasks[index].input_path), "reason": reason})
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
    cancelled = len(tasks) - submitted
    queued = processed + max(cancelled, 0)
    summary = {
        "total": len(audio_files),
        "queued": queued,
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped_count,
        "cancelled": max(cancelled, 0),
        "retried_count": retried_count,
        "elapsed_sec": elapsed,
        "out_dir": str(out_dir_obj),
        "manifest_path": str(manifest_path_obj),
        "errors": errors,
        "outputs": outputs,
        "skipped_items": skipped_items,
        "skipped_stale": skipped_stale,
        "lock_conflicts": lock_conflicts,
    }
    return summary
