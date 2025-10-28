"""实现 Round 11 的并发批处理转写管线，强化锁与完整性校验。"""  # 模块说明。
# 导入 errno 以识别常见 I/O 错误码并辅助错误分类。 
import copy  # 导入 copy 以在配置模式下安全地复制字典。
import errno
# 导入 json 以读取已有 words.json 用于哈希比对。 
import json
# 导入 os 以检查目录权限等。 
import os
import sys
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
from src.utils.logging import (  # 导入日志工具集以支持结构化日志。
    ProgressPrinter,  # 导入进度打印器以展示任务进度。
    StructuredLogger,  # 导入结构化日志器类型以便类型注释。
    TaskLogger,  # 导入任务级日志辅助类。
    bind_context,  # 导入上下文绑定函数以注入 trace_id 等字段。
    get_logger,  # 导入工厂函数以创建日志器实例。
    new_trace_id,  # 导入 TraceID 生成工具。
    print_summary,  # 导入汇总打印函数用于统一输出。
)
from src.utils.metrics import MetricsSink  # 导入指标收集器以统计运行数据。
from src.utils.profiling import PhaseTimer  # 导入阶段计时器实现轻量级 Profiler。
# 导入 Manifest 工具以在处理各阶段记录状态。 
from src.utils.manifest import append_record as manifest_append_record, load_index as manifest_load_index

# 定义允许的音频扩展名集合。 
ALLOWED_EXTENSIONS = [".wav", ".mp3", ".m4a", ".flac"]
# 定义词级与段级 JSON 的 schema 标识。 
WORD_SCHEMA = "asrprogram.wordset.v1"
SEGMENT_SCHEMA = "asrprogram.segmentset.v1"
_UNSET = object()  # 配置哨兵，用于判断调用方是否显式传入覆盖值。
# 定义修正逆序时间的微小阈值。 
EPSILON = 1e-3

# 定义任务结构体，集中存储单个音频文件的所有派生路径。 
@dataclass
class PipelineTask:
    """描述单个音频文件需要的输出路径与锁路径。"""  # 类说明。

    index: int  # 任务在批处理队列中的序号。
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
    logger: StructuredLogger  # 运行级结构化日志器。
    verbose: bool  # 是否输出详细日志。
    metrics: MetricsSink  # 共享指标收集器。
    profile_enabled: bool  # 是否启用阶段级 Profiling。
    metrics_labels: Dict[str, Any]  # 用于全局指标的标签快照。
    trace_id: str  # 当前批次的 TraceID。
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
) -> Tuple[Dict[str, Any], Dict[str, Any] | None, float, int, int]:
    """依据后端结果构建 words/segments JSON 结构并返回统计信息。"""  # 函数说明。
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
    return words_payload, segments_payload, duration, len(fixed_words), len(segments_data)  # 返回构造的载荷与统计。


# 定义辅助函数：读取现有 words.json 的音频元数据。 
def _load_existing_audio_info(words_path: Path) -> Tuple[str | None, float | None]:
    """尝试读取已有 words.json 的音频哈希与时长。"""  # 函数说明。
    if not words_path.exists():
        return None, None
    try:  # 捕获内部实现抛出的异常。
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
        phase_labels = {
            **context.metrics_labels,
            "trace_id": context.trace_id,
            "input": str(task.input_path),
            "basename": task.base_name,
        }  # 构造用于指标的标签字典。
        with PhaseTimer(context.metrics, "transcribe", labels=phase_labels, enabled=context.profile_enabled):
            transcription = context.backend.transcribe_file(str(task.input_path))  # 调用后端完成转写并测量耗时。
        words_payload, segments_payload, duration, words_count, segments_count = _build_payloads(
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
        with PhaseTimer(context.metrics, "write_outputs", labels=phase_labels, enabled=context.profile_enabled):
            atomic_write_json(task.words_path, words_payload)  # 原子写入词级 JSON。
            outputs = [str(task.words_path)]  # 初始化输出列表。
            if context.segments_json and segments_payload is not None:
                atomic_write_json(task.segments_path, segments_payload)
                outputs.append(str(task.segments_path))
        return {
            "duration": duration,
            "outputs": outputs,
            "segments": segments_count,
            "words": words_count,
        }  # 返回写入结果及统计数据供上层使用。
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
    task_logger = TaskLogger(  # 根据任务上下文创建日志器。
        bind_context(
            context.logger,
            task={"index": task.index, "input": str(task.input_path), "basename": task.base_name},
        ),
        context.verbose,
    )
    metrics = context.metrics  # 引用共享指标收集器。
    task_metric_labels = {
        **context.metrics_labels,
        "trace_id": context.trace_id,
        "input": str(task.input_path),
        "basename": task.base_name,
        "index": task.index,
    }  # 构造任务级指标标签。
    task_logger.start(str(task.input_path))  # 输出开始日志。
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
            metrics.inc("files_failed", 1, labels=context.metrics_labels)  # 记录失败计数。
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
                task_logger.skipped(str(task.input_path), skip_reason)
                task.error_path.unlink(missing_ok=True)
                error_payload = (
                    {"type": "StaleResult", "message": "stale result; use --overwrite true to rebuild"}
                    if stale
                    else {"type": "Skip", "message": skip_reason}
                )
                skip_duration = time.monotonic() - start_time  # 计算跳过耗时。
                metrics.inc("files_skipped", 1, labels=context.metrics_labels)  # 记录跳过计数。
                metrics.observe("task_elapsed_sec", skip_duration, labels=task_metric_labels)  # 记录跳过耗时。
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
                        "elapsed_sec": skip_duration,
                        "error": error_payload,
                    },
                )
                message = "stale" if stale else skip_reason
                context.progress.update(message)
                return TaskResult(
                    input_path=task.input_path,
                    status="skipped",
                    attempts=0,
                    duration=skip_duration,
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
                task_logger.retry(str(task.input_path), attempt, exc)
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
                task_logger.success(str(task.input_path), duration, attempts["value"], result["outputs"])
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
                metrics.inc("files_succeeded", 1, labels=context.metrics_labels)  # 记录成功计数。
                metrics.observe("task_elapsed_sec", duration, labels=task_metric_labels)  # 记录任务耗时。
                metrics.observe("task_num_segments", float(result.get("segments", 0)), labels=task_metric_labels)  # 记录段数。
                metrics.observe("task_num_words", float(result.get("words", 0)), labels=task_metric_labels)  # 记录词数。
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
                task_logger.failure(str(task.input_path), attempts["value"], exc.last_exception)
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
                metrics.inc("files_failed", 1, labels=context.metrics_labels)  # 记录失败计数。
                metrics.observe("task_elapsed_sec", duration, labels=task_metric_labels)  # 记录失败耗时。
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
                task_logger.failure(str(task.input_path), attempts.get("value", 1), exc)
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
                metrics.inc("files_failed", 1, labels=context.metrics_labels)  # 将不可重试错误计入失败。
                metrics.observe("task_elapsed_sec", duration, labels=task_metric_labels)  # 记录耗时。
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
                task_logger.failure(str(task.input_path), attempts.get("value", 1), exc)
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
                metrics.inc("files_failed", 1, labels=context.metrics_labels)  # 将未知异常计入失败。
                metrics.observe("task_elapsed_sec", duration, labels=task_metric_labels)  # 记录失败耗时。
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
        task_logger.skipped(str(task.input_path), "lock-timeout")
        lock_duration = time.monotonic() - start_time  # 计算锁等待耗时。
        metrics.inc("files_skipped", 1, labels=context.metrics_labels)  # 将锁超时计入跳过计数。
        metrics.observe("task_elapsed_sec", lock_duration, labels=task_metric_labels)  # 记录耗时。
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
                "elapsed_sec": lock_duration,
                "error": {"type": "LockTimeout", "message": str(exc)},
            },
        )
        context.progress.update("lock")
        return TaskResult(
            input_path=task.input_path,
            status="skipped",
            attempts=0,
            duration=lock_duration,
            outputs=[],
            error=None,
            skipped_reason="lock-timeout",
            hash_value=audio_hash,
        )


# 定义主运行函数，协调扫描、并发执行与 Manifest。 
def _run_impl(
    config: dict | None = None,
    *,
    input_path: str | None = None,
    out_dir: str | None = None,
    backend_name: str | None = None,
    language: str | object = _UNSET,
    segments_json: bool | object = _UNSET,
    overwrite: bool | object = _UNSET,
    dry_run: bool | object = _UNSET,
    verbose: bool | object = _UNSET,
    log_format: str | object = _UNSET,
    log_level: str | object = _UNSET,
    log_file: str | object = _UNSET,
    log_sample_rate: float | object = _UNSET,
    quiet: bool | object = _UNSET,
    metrics_file: str | object = _UNSET,
    profile: bool | object = _UNSET,
    progress: bool | object = _UNSET,
    disable_progress: bool | object = _UNSET,  # CLI 禁用进度条标志。
    model: str | object = _UNSET,
    compute_type: str | object = _UNSET,
    device: str | object = _UNSET,
    beam_size: int | object = _UNSET,
    temperature: float | object = _UNSET,
    vad_filter: bool | object = _UNSET,
    chunk_length_s: float | object = _UNSET,
    best_of: int | object = _UNSET,
    patience: float | object = _UNSET,
    num_workers: int | object = _UNSET,
    max_retries: int | object = _UNSET,
    rate_limit: float | object = _UNSET,
    skip_done: bool | object = _UNSET,
    fail_fast: bool | object = _UNSET,
    force_flush: bool | object = _UNSET,
    integrity_check: bool | object = _UNSET,
    lock_timeout: float | object = _UNSET,
    cleanup_temp: bool | object = _UNSET,
    manifest_path: str | object = _UNSET,
    force: bool | object = _UNSET,
    logger: StructuredLogger | None = None,
    **legacy_kwargs,
) -> dict:
    """执行批量音频转写并返回统计摘要。"""  # 函数说明。

    if "write_segments" in legacy_kwargs:  # 兼容旧版参数名。
        segments_json = legacy_kwargs.pop("write_segments")
    legacy_kwargs.pop("num_workers", None)  # 兼容历史冗余参数。
    if legacy_kwargs:  # 若仍有未知参数则直接提示。
        unsupported = ", ".join(sorted(legacy_kwargs.keys()))
        raise TypeError(f"Unsupported arguments for pipeline.run: {unsupported}")
    cfg = copy.deepcopy(config) if config is not None else {}  # 拷贝配置避免外部引用受影响。
    if not isinstance(cfg, dict):  # 基础类型检查，确保传入结构合法。
        raise TypeError("config must be a dict when provided")
    runtime_cfg = cfg.get("runtime")  # 读取运行时子树。
    if not isinstance(runtime_cfg, dict):  # 若缺失则初始化。
        runtime_cfg = {}
    cfg["runtime"] = runtime_cfg  # 写回规范化后的 runtime。
    profiling_cfg = cfg.get("profiling")  # 读取 profiling 配置。
    if not isinstance(profiling_cfg, dict):  # 若缺失则初始化空字典。
        profiling_cfg = {}
    cfg["profiling"] = profiling_cfg  # 确保 profiling 键存在。
    if input_path is not None:  # CLI 或调用方可直接覆盖输入路径。
        cfg["input"] = input_path
    if out_dir is not None:  # 同理允许覆盖输出目录。
        cfg["out_dir"] = out_dir
    top_overrides = {  # 收集顶层可能的覆盖值。
        "dry_run": dry_run,
        "verbose": verbose,
        "log_format": log_format,
        "log_level": log_level,
        "log_file": log_file,
        "log_sample_rate": log_sample_rate,
        "quiet": quiet,
        "metrics_file": metrics_file,
        "progress": progress,
        "disable_progress": disable_progress,  # CLI 禁用进度条标志覆盖值。
        "num_workers": num_workers,
        "max_retries": max_retries,
        "rate_limit": rate_limit,
        "skip_done": skip_done,
        "fail_fast": fail_fast,
        "force_flush": force_flush,
        "integrity_check": integrity_check,
        "lock_timeout": lock_timeout,
        "cleanup_temp": cleanup_temp,
        "manifest_path": manifest_path,
        "force": force,
    }
    for key, value in top_overrides.items():  # 仅当调用方显式提供时才覆盖。
        if value is not _UNSET:
            cfg[key] = value
    top_defaults = {  # 顶层默认值集合，用于填补缺省。
        "dry_run": False,
        "verbose": False,
        "log_format": "human",
        "log_level": "INFO",
        "log_file": None,
        "log_sample_rate": 1.0,
        "quiet": False,
        "metrics_file": None,
        "progress": True,
        "disable_progress": False,  # 默认允许进度条。
        "num_workers": 1,
        "max_retries": 1,
        "rate_limit": 0.0,
        "skip_done": True,
        "fail_fast": False,
        "force_flush": False,
        "integrity_check": True,
        "lock_timeout": 30.0,
        "cleanup_temp": True,
        "manifest_path": None,
        "force": False,
    }
    for key, default_value in top_defaults.items():  # 逐项填充默认值。
        if key not in cfg or cfg[key] is None:
            cfg[key] = default_value
    runtime_overrides = {  # 收集 runtime 层的显式覆盖。
        "language": language,
        "segments_json": segments_json,
        "overwrite": overwrite,
        "model": model,
        "compute_type": compute_type,
        "device": device,
        "beam_size": beam_size,
        "temperature": temperature,
        "vad_filter": vad_filter,
        "chunk_length_s": chunk_length_s,
        "best_of": best_of,
        "patience": patience,
    }
    for key, value in runtime_overrides.items():  # 同样只在显式提供时才覆盖。
        if value is not _UNSET:
            runtime_cfg[key] = value
    if backend_name is not None:  # 后端名称优先使用显式参数。
        runtime_cfg["backend"] = backend_name
    if "backend" not in runtime_cfg or not runtime_cfg["backend"]:  # 后端为必填项。
        raise ValueError("Runtime backend must be specified via config or parameters")
    runtime_defaults = {  # runtime 层默认值集合。
        "language": "auto",
        "segments_json": True,
        "overwrite": False,
        "model": None,
        "compute_type": "auto",
        "device": "auto",
        "beam_size": 5,
        "temperature": 0.0,
        "vad_filter": False,
        "chunk_length_s": None,
        "best_of": None,
        "patience": None,
    }
    for key, default_value in runtime_defaults.items():  # 逐项补齐默认值。
        if key not in runtime_cfg or runtime_cfg[key] is None:
            runtime_cfg[key] = default_value
    if profile is not _UNSET:  # 兼容旧版 profile 布尔开关。
        profiling_cfg["enabled"] = profile
    elif "enabled" not in profiling_cfg:  # 若配置未指定则默认关闭。
        profiling_cfg["enabled"] = False
    if "input" not in cfg or not cfg["input"]:  # 输入路径最终仍为必填。
        raise ValueError("Input path must be provided via config or arguments")
    if "out_dir" not in cfg or not cfg["out_dir"]:  # 输出目录同理。
        raise ValueError("Output directory must be provided via config or arguments")
    input_path = str(cfg["input"])  # 规范化输入路径为字符串。
    out_dir = str(cfg["out_dir"])  # 规范化输出目录。
    backend_name = runtime_cfg["backend"]  # 读取最终后端。
    language = runtime_cfg.get("language")  # 读取语言参数。
    segments_json = bool(runtime_cfg.get("segments_json"))  # 是否输出段级 JSON。
    overwrite = bool(runtime_cfg.get("overwrite"))  # 是否覆盖已有文件。
    model = runtime_cfg.get("model")  # 运行时模型参数。
    compute_type = runtime_cfg.get("compute_type")  # 精度设置。
    device = runtime_cfg.get("device")  # 设备选择。
    beam_size = max(1, int(runtime_cfg.get("beam_size") or 1))  # beam 宽度至少为 1。
    temperature_value = runtime_cfg.get("temperature")  # 温度原始值。
    temperature = float(temperature_value if temperature_value is not None else 0.0)  # 归一化温度。
    vad_filter = bool(runtime_cfg.get("vad_filter"))  # VAD 开关。
    chunk_value = runtime_cfg.get("chunk_length_s")  # 分段长度。
    chunk_length_s = float(chunk_value) if chunk_value is not None else None  # 归一化为浮点数。
    best_of_value = runtime_cfg.get("best_of")  # 采样候选数。
    best_of = int(best_of_value) if best_of_value is not None else None  # 转换为整数或 None。
    patience_value = runtime_cfg.get("patience")  # 提前停止阈值。
    patience = float(patience_value) if patience_value is not None else None  # 转换为浮点或 None。
    dry_run = bool(cfg.get("dry_run"))  # 读取最终 dry-run 开关。
    verbose = bool(cfg.get("verbose"))  # 读取 verbose 开关。
    log_format = cfg.get("log_format") or "human"  # 日志格式默认 human。
    log_level = cfg.get("log_level") or "INFO"  # 日志等级默认 INFO。
    log_file = cfg.get("log_file") or None  # 日志文件可为空。
    log_sample_rate_value = cfg.get("log_sample_rate")  # 采样率原始值。
    log_sample_rate = float(log_sample_rate_value if log_sample_rate_value is not None else 1.0)  # 归一化采样率。
    log_sample_rate = max(min(log_sample_rate, 1.0), 1e-6)  # 裁剪至合法区间。
    quiet = bool(cfg.get("quiet"))  # 静默模式。
    metrics_file = cfg.get("metrics_file") or None  # 指标导出路径。
    progress = bool(cfg.get("progress"))  # 进度条开关。
    num_workers_value = cfg.get("num_workers")  # 并发 worker 数。
    num_workers = max(1, int(num_workers_value if num_workers_value is not None else 1))  # 至少为 1。
    max_retries_value = cfg.get("max_retries")  # 最大重试次数。
    max_retries = max(0, int(max_retries_value if max_retries_value is not None else 0))  # 不得为负。
    rate_limit_value = cfg.get("rate_limit")  # 速率限制。
    rate_limit = max(0.0, float(rate_limit_value if rate_limit_value is not None else 0.0))  # 不小于 0。
    skip_done = bool(cfg.get("skip_done"))  # 跳过已完成文件。
    fail_fast = bool(cfg.get("fail_fast"))  # 失败即停。
    integrity_check = bool(cfg.get("integrity_check"))  # 完整性校验。
    lock_timeout_value = cfg.get("lock_timeout")  # 锁超时原始值。
    lock_timeout = max(0.0, float(lock_timeout_value if lock_timeout_value is not None else 0.0))  # 不小于 0。
    cleanup_temp = bool(cfg.get("cleanup_temp"))  # 清理临时文件。
    manifest_path_value = cfg.get("manifest_path")  # 清单路径。
    manifest_path = str(manifest_path_value) if manifest_path_value else None  # 归一化为字符串或 None。
    force = bool(cfg.get("force"))  # 强制重跑开关。
    force_flush_flag = bool(cfg.get("force_flush"))  # 是否强制立即刷新日志。
    profiling_enabled = bool(profiling_cfg.get("enabled"))  # Profiling 开关最终值。
    profile = profiling_enabled  # 重用原变量以兼容后续逻辑。
    active_profile = cfg.get("meta", {}).get("profile")  # 记录生效的 profile 名称。
    cfg["manifest_path"] = manifest_path  # 将推导后的 manifest 写回配置。
    effective_level = log_level.upper() if log_level else "INFO"  # 规范化日志等级。
    if verbose and effective_level == "INFO":  # 在 verbose 模式下自动提升等级。
        effective_level = "DEBUG"
    base_logger = logger or get_logger(  # 创建或复用结构化日志器。
        format=log_format,
        level=effective_level,
        log_file=log_file,
        sample_rate=log_sample_rate,
        quiet=quiet,
        force_flush=force_flush_flag,
    )
    trace_id = new_trace_id()  # 为本次运行生成 TraceID。
    run_logger = bind_context(base_logger, trace_id=trace_id)  # 绑定 TraceID 形成运行级日志器。
    if verbose:  # 在详细模式下输出配置摘要。
        run_logger.debug(
            "pipeline configuration",
            config={
                "input": input_path,
                "out_dir": out_dir,
                "backend": backend_name,
                "workers": num_workers,
                "max_retries": max_retries,
                "rate_limit": rate_limit,
                "skip_done": skip_done,
                "fail_fast": fail_fast,
            },
        )
    metrics = MetricsSink()  # 初始化指标收集器。
    metrics_labels = {
        "backend": backend_name,
        "model": model or "auto",
        "compute_type": compute_type,
    }  # 构造全局标签快照。
    phase_labels = {**metrics_labels, "trace_id": trace_id}  # 构造用于阶段指标的标签。
    input_path_obj = Path(input_path)
    out_dir_obj = Path(out_dir)
    manifest_path_obj = Path(manifest_path) if manifest_path else out_dir_obj / "_manifest.jsonl"
    with PhaseTimer(metrics, "scan", labels=phase_labels, enabled=profile):
        audio_files = _scan_audio_inputs(input_path_obj)
    metrics.inc("files_total", float(len(audio_files)), labels=metrics_labels)  # 记录扫描到的音频文件数。
    if verbose:
        run_logger.debug("scan completed", files=len(audio_files))
        for path in audio_files:
            run_logger.debug("scan candidate", file=str(path))
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
    with PhaseTimer(metrics, "load_backend", labels=phase_labels, enabled=profile):
        backend = create_transcriber(backend_name, **backend_kwargs)
    if verbose:
        run_logger.debug("backend initialized", backend=backend_name)
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
            dry_logger = TaskLogger(
                bind_context(
                    run_logger,
                    task={
                        "index": planned_count,
                        "input": str(audio_file),
                        "basename": base_name,
                    },
                ),
                verbose,
            )
            dry_logger.skipped(str(audio_file), "dry-run")
            planned_count += 1
            continue
        task_index = len(tasks)
        tasks.append(
            PipelineTask(
                index=task_index,
                input_path=audio_file,
                base_name=base_name,
                words_path=words_path,
                segments_path=segments_path,
                error_path=error_path,
                lock_path=lock_path,
            )
        )
    def _export_metrics_file(elapsed: float) -> None:
        """在需要时导出指标文件并记录耗时指标。"""  # 内部辅助函数说明。
        metrics.observe("elapsed_total_sec", elapsed, labels=metrics_labels)  # 记录整体耗时。
        snapshot = metrics.summary(labels=metrics_labels)  # 计算派生指标供导出使用。
        metrics.observe("avg_file_sec", snapshot.get("avg_file_sec", 0.0), labels=metrics_labels)  # 记录平均耗时。
        metrics.observe(
            "throughput_files_per_min",
            snapshot.get("throughput_files_per_min", 0.0),
            labels=metrics_labels,
        )  # 记录吞吐量。
        if not metrics_file:  # 未指定输出文件则直接返回。
            return
        metrics_path = Path(metrics_file)  # 将路径转换为 Path 便于解析后缀。
        if metrics_path.suffix.lower() == ".csv":  # 根据后缀选择导出格式。
            metrics.export_csv(str(metrics_path))
        else:
            metrics.export_jsonl(str(metrics_path))
        run_logger.info("metrics exported", path=str(metrics_path), format=metrics_path.suffix.lower().lstrip("."))

    def _finalize(summary: dict) -> dict:
        """统一处理摘要日志、指标导出与补充提示。"""  # 内部辅助函数说明。
        _export_metrics_file(float(summary.get("elapsed_sec", 0.0)))  # 导出指标并记录总耗时。
        print_summary(summary, logger=run_logger)  # 输出结构化汇总。
        manifest_location = summary.get("manifest_path")  # 读取 Manifest 路径。
        if manifest_location:
            run_logger.info("manifest updated", path=manifest_location)  # 提示 Manifest 更新位置。
        stale_skips = summary.get("skipped_stale", 0)  # 读取陈旧跳过数量。
        if stale_skips:
            run_logger.info("stale results skipped", count=stale_skips)
        lock_conflicts = summary.get("lock_conflicts", 0)  # 读取锁冲突数量。
        if lock_conflicts:
            run_logger.info("lock conflicts", count=lock_conflicts)
        return summary  # 返回摘要供上层使用。
    if dry_run:
        summary = {
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
            "config": {
                "profile": active_profile,
                "backend": backend_name,
                "device": device,
                "compute_type": compute_type,
                "beam_size": beam_size,
                "profiling_enabled": profile,
            },
        }
        return _finalize(summary)
    if not tasks:
        summary = {
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
            "config": {
                "profile": active_profile,
                "backend": backend_name,
                "device": device,
                "compute_type": compute_type,
                "beam_size": beam_size,
                "profiling_enabled": profile,
            },
        }
        return _finalize(summary)
    try:
        stdout_is_tty = sys.stdout.isatty()
    except Exception:  # noqa: BLE001
        stdout_is_tty = False
    disable_progress_flag = bool(cfg.get("disable_progress", False))  # 读取禁用进度标记。
    progress_requested = progress and not quiet and not disable_progress_flag  # 仅在允许进度且未禁用时启用。
    progress_animation_allowed = progress_requested and stdout_is_tty
    if log_format.lower() == "jsonl" and quiet:
        progress_animation_allowed = False  # 在 JSONL+静默模式下关闭进度动画以避免干扰。
    progress = ProgressPrinter(
        len(tasks),
        "processing",
        enabled=progress_requested,
        logger=run_logger,
        disable_animation=not progress_animation_allowed,
        is_tty=stdout_is_tty,
    )
    context = TaskContext(
        backend=backend,
        backend_name=backend_name,
        language=language,
        segments_json=segments_json,
        max_retries=max_retries,
        logger=run_logger,
        verbose=verbose,
        metrics=metrics,
        profile_enabled=profile,
        metrics_labels=metrics_labels,
        trace_id=trace_id,
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
            try:
                sys.stdout.flush()  # 每处理完一个任务刷新 stdout，确保远程终端即时显示。
            except Exception:  # noqa: BLE001
                pass  # 某些环境可能不支持 flush，安全忽略。
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
        "config": {
            "profile": active_profile,
            "backend": backend_name,
            "device": device,
            "compute_type": compute_type,
            "beam_size": beam_size,
            "profiling_enabled": profile,
        },
    }
    return _finalize(summary)

def run(
    config: dict | None = None,  # 外部配置字典。
    *,
    input_path: str | None = None,  # CLI 覆盖的输入路径。
    out_dir: str | None = None,  # CLI 覆盖的输出目录。
    backend_name: str | None = None,  # CLI 覆盖的后端名称。
    language: str | object = _UNSET,  # CLI 覆盖的语言。
    segments_json: bool | object = _UNSET,  # CLI 覆盖的段级 JSON 选项。
    overwrite: bool | object = _UNSET,  # CLI 覆盖的覆盖策略。
    dry_run: bool | object = _UNSET,  # CLI 覆盖的干跑选项。
    verbose: bool | object = _UNSET,  # CLI 覆盖的详细日志开关。
    log_format: str | object = _UNSET,  # CLI 覆盖的日志格式。
    log_level: str | object = _UNSET,  # CLI 覆盖的日志等级。
    log_file: str | object = _UNSET,  # CLI 覆盖的日志文件。
    log_sample_rate: float | object = _UNSET,  # CLI 覆盖的日志采样率。
    quiet: bool | object = _UNSET,  # CLI 覆盖的静默模式。
    metrics_file: str | object = _UNSET,  # CLI 覆盖的指标文件。
    profile: bool | object = _UNSET,  # CLI 覆盖的性能分析开关。
    progress: bool | object = _UNSET,  # CLI 覆盖的进度开关。
    disable_progress: bool | object = _UNSET,  # CLI 覆盖的禁用进度标志。
    model: str | object = _UNSET,  # CLI 覆盖的模型路径。
    compute_type: str | object = _UNSET,  # CLI 覆盖的计算精度。
    device: str | object = _UNSET,  # CLI 覆盖的设备参数。
    beam_size: int | object = _UNSET,  # CLI 覆盖的 beam_size。
    temperature: float | object = _UNSET,  # CLI 覆盖的温度参数。
    vad_filter: bool | object = _UNSET,  # CLI 覆盖的 VAD 选项。
    chunk_length_s: float | object = _UNSET,  # CLI 覆盖的切块长度。
    best_of: int | object = _UNSET,  # CLI 覆盖的 best_of。
    patience: float | object = _UNSET,  # CLI 覆盖的 patience。
    num_workers: int | object = _UNSET,  # CLI 覆盖的 worker 数量。
    max_retries: int | object = _UNSET,  # CLI 覆盖的重试次数。
    rate_limit: float | object = _UNSET,  # CLI 覆盖的速率限制。
    skip_done: bool | object = _UNSET,  # CLI 覆盖的跳过已完成选项。
    fail_fast: bool | object = _UNSET,  # CLI 覆盖的快速失败选项。
    force_flush: bool | object = _UNSET,  # CLI 覆盖的强制刷新选项。
    integrity_check: bool | object = _UNSET,  # CLI 覆盖的完整性校验。
    lock_timeout: float | object = _UNSET,  # CLI 覆盖的锁超时。
    cleanup_temp: bool | object = _UNSET,  # CLI 覆盖的临时文件清理。
    manifest_path: str | object = _UNSET,  # CLI 覆盖的 Manifest 路径。
    force: bool | object = _UNSET,  # CLI 覆盖的强制重跑。
    logger: StructuredLogger | None = None,  # 可选的结构化日志器。
    **legacy_kwargs,  # 接收兼容的旧参数。
) -> dict:
    """包装 _run_impl，捕获异常后记录日志并退出。"""  # 函数说明。

    try:
        return _run_impl(  # 委托内部实现并返回结果。
            config=config,  # 传递配置对象。
            input_path=input_path,  # 指定输入路径覆盖值。
            out_dir=out_dir,  # 指定输出目录覆盖值。
            backend_name=backend_name,  # 指定后端名称覆盖值。
            language=language,  # 指定语言参数覆盖值。
            segments_json=segments_json,  # 指定段级 JSON 标志。
            overwrite=overwrite,  # 指定覆盖行为。
            dry_run=dry_run,  # 指定是否只做干跑。
            verbose=verbose,  # 指定详细日志开关。
            log_format=log_format,  # 指定日志格式。
            log_level=log_level,  # 指定日志等级。
            log_file=log_file,  # 指定日志文件路径。
            log_sample_rate=log_sample_rate,  # 指定日志采样率。
            quiet=quiet,  # 指定静默模式开关。
            metrics_file=metrics_file,  # 指定指标输出路径。
            profile=profile,  # 指定性能分析开关。
            progress=progress,  # 指定进度开关。
            disable_progress=disable_progress,  # 指定禁用进度条标志。
            model=model,  # 指定模型路径覆盖值。
            compute_type=compute_type,  # 指定精度类型。
            device=device,  # 指定设备。
            beam_size=beam_size,  # 指定 beam_size 覆盖值。
            temperature=temperature,  # 指定解码温度。
            vad_filter=vad_filter,  # 指定 VAD 过滤开关。
            chunk_length_s=chunk_length_s,  # 指定切块长度。
            best_of=best_of,  # 指定 best_of 覆盖值。
            patience=patience,  # 指定 patience 覆盖值。
            num_workers=num_workers,  # 指定并发 worker 数。
            max_retries=max_retries,  # 指定最大重试次数。
            rate_limit=rate_limit,  # 指定速率限制。
            skip_done=skip_done,  # 指定跳过已完成。
            fail_fast=fail_fast,  # 指定快速失败。
            force_flush=force_flush,  # 指定强制刷新。
            integrity_check=integrity_check,  # 指定完整性校验开关。
            lock_timeout=lock_timeout,  # 指定锁超时时间。
            cleanup_temp=cleanup_temp,  # 指定清理临时文件开关。
            manifest_path=manifest_path,  # 指定 Manifest 覆盖值。
            force=force,  # 指定强制重跑标志。
            logger=logger,  # 传递现有结构化日志器。
            **legacy_kwargs,  # 传递其余兼容参数。
        )
    except Exception as exc:  # noqa: BLE001
        target_logger = logger or get_logger()  # 若外部未提供结构化日志器则创建默认实例。
        target_logger.exception("pipeline execution failed", exc=exc)  # 记录异常堆栈。
        sys.exit(1)  # 以状态码 1 退出进程。
