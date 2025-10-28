"""提供结构化日志、进度展示与汇总打印的工具集合。"""  # 模块文档说明，描述本文件的作用。
from __future__ import annotations  # 启用延迟求值的注解语义以支持联合类型语法。
import json  # 导入 json 以在 JSONL 格式下序列化日志记录。
import logging  # 导入 logging 以兼容旧接口并处理回退输出。
import os
import sys  # 导入 sys 以访问标准输出流对象。
import traceback
import uuid  # 导入 uuid 以生成高熵的 TraceID。
from datetime import datetime, timezone  # 导入 datetime 以生成 UTC 时间戳。
from pathlib import Path  # 导入 Path 便于处理日志文件路径。
from typing import Any, Dict, Iterable, Optional  # 导入类型注释以提升可读性。

from src.utils.io import jsonl_append, safe_mkdirs, with_file_lock  # 导入 I/O 工具用于安全追加。

try:  # 捕获 tqdm 的可选依赖导入失败。
    from tqdm import tqdm  # type: ignore  # 导入 tqdm 以在终端展示进度条。
except Exception:  # noqa: BLE001  # 广泛捕获异常以保持兼容性。
    tqdm = None  # 导入失败时将 tqdm 设为 None，后续逻辑将退化为手动模式。

_LEVELS = {  # 定义日志等级到数值的映射，兼容 logging 模块的约定。
    "DEBUG": 10,  # DEBUG 对应 10。
    "INFO": 20,  # INFO 对应 20。
    "WARNING": 30,  # WARNING 对应 30。
    "ERROR": 40,  # ERROR 对应 40。
    "CRITICAL": 50,  # CRITICAL 对应 50。
}


def new_trace_id() -> str:
    """生成 12 字符长度的短 TraceID，用于贯穿一次批处理。"""  # 函数说明。
    return uuid.uuid4().hex[:12]  # 使用 uuid4 的十六进制表示并截断以保持简洁。


def _normalize_level(level: str) -> str:
    """将外部传入的日志等级规范化为大写并验证合法性。"""  # 函数说明。
    upper = level.upper()  # 转换为大写方便匹配字典键。
    if upper not in _LEVELS:  # 检查是否为已知等级。
        raise ValueError(f"Unsupported log level: {level}")  # 不支持的等级直接抛出异常。
    return upper  # 返回规范化后的等级字符串。


def _append_text_atomic(path: Path, text: str, *, force_flush: bool = False) -> None:
    """以锁保护的方式向纯文本日志追加一行，避免并发写入冲突。"""  # 函数说明。
    safe_mkdirs(path.parent)  # 确保日志目录存在。
    lock_path = path.with_suffix(path.suffix + ".lock")  # 为该文件生成锁文件路径。
    with with_file_lock(lock_path, timeout_sec=30):  # 使用文件锁保护写入区域。
        with path.open("a", encoding="utf-8") as handle:  # 以追加模式打开日志文件。
            handle.write(text)  # 写入日志文本内容。
            handle.write("\n")  # 追加换行保持一行一条日志。
            handle.flush()  # 确保刷新到内核缓冲区。
            if force_flush:
                try:
                    os.fsync(handle.fileno())
                except OSError:  # noqa: PERF203
                    pass


class _LoggerCore:
    """封装日志格式化与写入细节的内部核心类。"""  # 类说明。

    def __init__(
        self,
        log_format: str,
        level: str,
        log_file: str | None,
        sample_rate: float,
        quiet: bool,
        *,
        force_flush: bool = False,
    ) -> None:
        """初始化日志核心，保存格式、等级与输出目标。"""  # 方法说明。
        normalized = log_format.lower()  # 统一格式字符串大小写。
        if normalized not in {"human", "jsonl"}:  # 校验格式是否受支持。
            raise ValueError(f"Unsupported log format: {log_format}")  # 不支持的格式抛出异常。
        self.format = normalized  # 保存规范化后的格式。
        self.level = _LEVELS[_normalize_level(level)]  # 将等级转换为数值阈值。
        self.log_file = Path(log_file) if log_file else None  # 将日志文件路径转换为 Path。
        self.sample_rate = max(min(sample_rate, 1.0), 0.0)  # 对采样率进行截断，确保在 [0,1] 内。
        self.quiet = quiet  # 保存静默模式标志。
        self._sample_counter = 0  # 初始化采样计数器，用于确定是否输出。
        self._console = sys.stdout  # 保存标准输出流句柄。
        self._force_flush = force_flush
        if self.log_file is not None:  # 若需要写入文件则确保目录存在。
            safe_mkdirs(self.log_file.parent)  # 调用工具函数创建目录。

    def _should_emit(self, level_value: int) -> bool:
        """根据等级与采样策略判断是否输出日志。"""  # 方法说明。
        if level_value < self.level:  # 若日志级别低于阈值则直接丢弃。
            return False  # 返回 False 表示不记录。
        if level_value <= _LEVELS["INFO"] and self.sample_rate < 1.0:  # 对 INFO 以下日志应用采样。
            period = max(1, int(round(1.0 / self.sample_rate)))  # 根据采样率计算周期。
            keep = self._sample_counter % period == 0  # 仅在周期的第一个事件保留日志。
            self._sample_counter += 1  # 增加计数器以推进周期。
            if not keep:  # 若本次不保留则立即返回 False。
                return False  # 返回 False 表示丢弃该日志。
        return True  # 满足条件则记录日志。

    def _timestamp(self) -> str:
        """返回带毫秒精度的 UTC ISO8601 时间戳。"""  # 方法说明。
        now = datetime.now(timezone.utc)  # 获取当前 UTC 时间。
        return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")  # 格式化并替换结尾。

    def _render_human(self, record: Dict[str, Any]) -> str:
        """将日志记录渲染为人类易读的字符串。"""  # 方法说明。
        parts = [f"[{record['level']}]" ]  # 初始部分包含等级标签。
        parts.append(record["ts"])  # 追加时间戳。
        trace_id = record.get("trace_id")  # 读取 TraceID 字段。
        if trace_id:  # 若存在 TraceID 则在消息前附加。
            parts.append(f"trace={trace_id}")  # 添加 TraceID 信息。
        task = record.get("task")  # 读取任务上下文字段。
        if isinstance(task, dict):  # 确认 task 字段为字典。
            descriptor = task.get("basename") or task.get("input")  # 从任务中选择描述。
            if descriptor:  # 若找到了描述则写入。
                parts.append(f"task={descriptor}")  # 添加任务标识。
        parts.append(record["msg"])  # 最后追加原始消息文本。
        base = " ".join(parts)  # 使用空格拼接所有片段生成基础行。

        # 若存在错误字段，则在基础行后追加详细信息，便于快速定位问题。
        extra_lines: list[str] = []
        error_fields: list[str] = []
        error_type = record.get("error_type") or record.get("errorType")
        if error_type:
            error_fields.append(f"error_type={error_type}")
        error_message = record.get("error")
        if error_message:
            error_fields.append(f"error={error_message}")
        if error_fields:
            extra_lines.append("    " + " ".join(error_fields))

        trace_text = record.get("trace")
        if isinstance(trace_text, str) and trace_text.strip():
            for line in trace_text.rstrip().splitlines():
                extra_lines.append("    " + line)

        if extra_lines:
            return "\n".join([base, *extra_lines])
        return base  # 当无额外字段时返回单行日志。

    def _render_json(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """在 JSONL 模式下直接返回字典，便于后续序列化。"""  # 方法说明。
        return record  # JSONL 格式直接使用字典表示。

    def emit(self, level: str, message: str, fields: Dict[str, Any]) -> None:
        """根据配置输出一条日志记录。"""  # 方法说明。
        normalized = _normalize_level(level)  # 将等级字符串转换为标准形式。
        level_value = _LEVELS[normalized]  # 获取对应的数值等级。
        if not self._should_emit(level_value):  # 检查是否应当输出。
            return  # 若不输出则直接返回。
        record: Dict[str, Any] = {  # 构建基础日志记录字典。
            "ts": self._timestamp(),  # 写入标准化的时间戳。
            "level": normalized,  # 写入日志等级。
            "msg": message,  # 写入消息文本。
        }
        record.update(fields)  # 合并调用方提供的扩展字段。
        if self.format == "human":  # 根据格式决定渲染策略。
            rendered = self._render_human(record)  # 将记录转为人类可读文本。
            if not self.quiet:  # 若未启用静默模式则输出到控制台。
                self._console.write(rendered + "\n")  # 写入文本并换行。
                self._console.flush()  # 立即刷新输出。
            if self.log_file is not None:  # 若指定了日志文件则同步写入。
                _append_text_atomic(self.log_file, rendered, force_flush=self._force_flush)  # 使用锁保护的方式追加文本。
        else:  # JSONL 模式下直接写入结构化数据。
            payload = self._render_json(record)  # 获取 JSONL 结构。
            if not self.quiet:  # 控制台输出 JSON 字符串。
                json.dump(payload, self._console, ensure_ascii=False)  # 序列化到标准输出。
                self._console.write("\n")  # 输出换行符。
                self._console.flush()  # 刷新标准输出。
            if self.log_file is not None:  # 若配置了文件则使用 jsonl_append 追加。
                jsonl_append(str(self.log_file), payload, force_flush=self._force_flush)  # 追加到 JSONL 文件。

    def human(self, record: Dict[str, Any]) -> str:
        """公开人类可读渲染方法，便于测试或复用。"""  # 方法说明。
        return self._render_human(record)  # 直接调用内部实现。

    def jsonl(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """公开 JSON 渲染方法，返回原始字典。"""  # 方法说明。
        return self._render_json(record)  # 直接返回记录。


class StructuredLogger:
    """对外暴露的结构化日志器，支持上下文绑定与多格式输出。"""  # 类说明。

    def __init__(self, core: _LoggerCore, context: Optional[Dict[str, Any]] = None, parent: "StructuredLogger" | None = None) -> None:
        """创建日志器实例，可选地继承父级上下文。"""  # 方法说明。
        self._core = core  # 保存内部核心引用。
        self._context = context or {}  # 存储当前实例的额外字段。
        self._parent = parent  # 保存父级日志器以便递归合并上下文。

    def _collect_context(self) -> Dict[str, Any]:
        """递归合并父级上下文并返回总上下文字典。"""  # 方法说明。
        aggregated: Dict[str, Any] = {}  # 初始化结果字典。
        if self._parent is not None:  # 若存在父级则首先获取父级上下文。
            aggregated.update(self._parent._collect_context())  # 递归合并父级上下文。
        aggregated.update(self._context)  # 合并当前实例的上下文。
        return aggregated  # 返回合并结果。

    def bind(self, **kwargs: Any) -> "StructuredLogger":
        """基于当前实例追加上下文字段并返回新的子日志器。"""  # 方法说明。
        return StructuredLogger(self._core, context=kwargs, parent=self)  # 创建新的上下文日志器。

    def log(self, level: str, message: str, **fields: Any) -> None:
        """记录一条带指定等级的日志，可附带额外字段。"""  # 方法说明。
        payload = self._collect_context()  # 收集层级上下文。
        payload.update(fields)  # 合并调用方传入的字段。
        self._core.emit(level, message, payload)  # 调用核心对象实际写入日志。

    def debug(self, message: str, **fields: Any) -> None:
        """输出 DEBUG 级日志。"""  # 方法说明。
        self.log("DEBUG", message, **fields)  # 调用通用 log 方法。

    def info(self, message: str, **fields: Any) -> None:
        """输出 INFO 级日志。"""  # 方法说明。
        self.log("INFO", message, **fields)  # 调用通用 log 方法。

    def warning(self, message: str, **fields: Any) -> None:
        """输出 WARNING 级日志。"""  # 方法说明。
        self.log("WARNING", message, **fields)  # 调用通用 log 方法。

    def error(self, message: str, **fields: Any) -> None:
        """输出 ERROR 级日志。"""  # 方法说明。
        self.log("ERROR", message, **fields)  # 调用通用 log 方法。

    def exception(self, message: str, exc: BaseException | None = None, **fields: Any) -> None:
        """输出包含异常堆栈的 ERROR 级日志。"""  # 方法说明。
        exception_obj = exc
        if exception_obj is None:
            _, exception_obj, _ = sys.exc_info()
        if exception_obj is not None:
            fields.setdefault("error", str(exception_obj))
            fields.setdefault("error_type", exception_obj.__class__.__name__)
            trace_text = "".join(
                traceback.format_exception(
                    exception_obj.__class__, exception_obj, exception_obj.__traceback__
                )
            )
            fields.setdefault("trace", trace_text)
        else:
            trace_text = traceback.format_exc()
            if trace_text.strip():
                fields.setdefault("trace", trace_text)
        self.log("ERROR", message, **fields)

    def human(self, record: Dict[str, Any]) -> str:
        """委托核心生成 human 格式字符串。"""  # 方法说明。
        return self._core.human(record)  # 调用内部核心。

    def jsonl(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """委托核心返回 JSON 字典。"""  # 方法说明。
        return self._core.jsonl(record)  # 调用内部核心。


def get_logger(
    format: str = "human",
    level: str = "INFO",
    log_file: str | None = None,
    sample_rate: float = 1.0,
    quiet: bool = False,
    *,
    force_flush: bool = False,
    file_path: str | None = None,
) -> StructuredLogger:
    """创建并返回结构化日志器，支持 human/jsonl 两种模式。"""  # 函数说明。
    target_file = file_path or log_file
    core = _LoggerCore(
        format,
        level,
        target_file,
        sample_rate,
        quiet,
        force_flush=force_flush,
    )  # 初始化核心组件。
    return StructuredLogger(core)  # 返回不带额外上下文的基础日志器。


def bind_context(logger: StructuredLogger, **kwargs: Any) -> StructuredLogger:
    """为现有日志器绑定额外上下文并返回新的实例。"""  # 函数说明。
    return logger.bind(**kwargs)  # 直接调用结构化日志器的 bind 方法。


class ProgressPrinter:
    """封装 tqdm 或退化日志方式的进度展示工具。"""  # 类说明。

    def __init__(
        self,
        total: int,
        description: str,
        enabled: bool,
        logger: StructuredLogger | None = None,
        *,
        disable_animation: bool | None = None,
        is_tty: bool | None = None,
    ) -> None:
        """初始化进度打印器，可配置是否启用以及输出目标。"""  # 方法说明。
        tty_status = is_tty
        if tty_status is None:
            try:
                tty_status = sys.stdout.isatty()
            except Exception:  # noqa: BLE001
                tty_status = False
        disable_flag = disable_animation if disable_animation is not None else not bool(tty_status)
        self.enabled = enabled and total > 0  # 仅当启用且总数大于零时才真正显示进度。
        self.description = description  # 保存描述文本。
        self.total = total  # 保存任务总数。
        self.count = 0  # 初始化当前完成数量。
        self.logger = logger  # 保存可选的结构化日志器。
        self._bar = None
        if self.enabled and tqdm is not None and not disable_flag:  # 若 tqdm 可用则构建进度条实例。
            self._bar = tqdm(total=total, desc=description, leave=False, disable=False)  # 创建 tqdm 进度条。
        self._disable_animation = disable_flag

    def update(self, message: str | None = None) -> None:
        """递增进度计数并可选输出附加消息。"""  # 方法说明。
        if not self.enabled:  # 若未启用则直接返回。
            return  # 不执行任何操作。
        if self._bar is not None:  # 在 tqdm 模式下更新进度条。
            self._bar.update(1)  # 累加一个单位。
            if message:  # 若提供附加消息则更新 postfix。
                self._bar.set_postfix_str(message, refresh=False)  # 使用 postfix 展示附加信息。
            self._bar.refresh()
            return  # tqdm 模式下不再额外记录日志。
        self.count += 1  # 手动模式下递增计数。
        percent = (self.count / self.total) * 100 if self.total else 0.0  # 计算完成百分比。
        if self.logger is not None:  # 若提供了日志器则输出结构化日志。
            self.logger.info(
                "progress",
                progress={"completed": self.count, "total": self.total, "percent": percent, "message": message},
            )
        else:  # 没有日志器时回退到标准 logging。
            logging.info(
                "%s %d/%d (%.1f%%)%s",
                self.description,
                self.count,
                self.total,
                percent,
                f" - {message}" if message else "",
            )

    def close(self) -> None:
        """关闭进度条并在 tqdm 模式下恢复终端状态。"""  # 方法说明。
        if self._bar is not None:  # 仅在 tqdm 模式下执行关闭。
            self._bar.close()  # 关闭进度条实例。


class TaskLogger:
    """为单个任务提供结构化的生命周期日志接口。"""  # 类说明。

    def __init__(self, logger: StructuredLogger, verbose: bool) -> None:
        """保存日志器引用并记录是否输出调试信息。"""  # 方法说明。
        self.logger = logger  # 保存结构化日志器实例。
        self.verbose = verbose  # 保存是否输出详细信息的标志。

    def start(self, path: str) -> None:
        """记录任务开始处理的日志。"""  # 方法说明。
        if self.verbose:  # 仅在详细模式下输出。
            self.logger.debug("task started", task_path=path)  # 输出 DEBUG 日志并附带路径。

    def retry(self, path: str, attempt: int, exc: Exception) -> None:
        """记录任务重试事件，包含失败原因。"""  # 方法说明。
        if self.verbose:  # 仅详细模式输出重试信息。
            self.logger.warning("task retry", task_path=path, attempt=attempt, error=str(exc))  # 输出 WARNING 日志。

    def success(self, path: str, duration: float, attempts: int, outputs: Iterable[str]) -> None:
        """记录任务成功完成的摘要。"""  # 方法说明。
        if self.verbose:  # 仅详细模式输出成功详情。
            self.logger.debug(
                "task success",
                task_path=path,
                duration_sec=duration,
                attempts=attempts,
                outputs=list(outputs),
            )
        else:
            self.logger.info(
                "task finished",
                task_path=path,
                duration_sec=duration,
                attempts=attempts,
                outputs=list(outputs),
            )

    def failure(self, path: str, attempts: int, exc: Exception) -> None:
        """记录任务失败事件，包含错误详情。"""  # 方法说明。
        self.logger.exception(
            "task failed",
            exc=exc,
            task_path=path,
            attempts=attempts,
        )

    def skipped(self, path: str, reason: str) -> None:
        """记录任务被跳过的情况。"""  # 方法说明。
        if self.verbose:  # 仅详细模式下输出。
            self.logger.info("task skipped", task_path=path, reason=reason)  # 输出 INFO 日志。


def print_summary(summary: dict, logger: StructuredLogger | logging.Logger | None = None) -> None:
    """输出批处理汇总信息，既支持结构化日志也兼容旧版 logging。"""  # 函数说明。
    total = summary.get("total", 0)  # 读取处理总数。
    processed = summary.get("processed", 0)  # 读取已处理数量。
    succeeded = summary.get("succeeded", 0)  # 读取成功数量。
    failed = summary.get("failed", 0)  # 读取失败数量。
    skipped = summary.get("skipped", 0)  # 读取跳过数量。
    elapsed = float(summary.get("elapsed_sec", 0.0))  # 读取耗时并转换为浮点数。
    avg_latency = elapsed / processed if processed else 0.0  # 计算平均单文件耗时。
    throughput = (succeeded / elapsed * 60.0) if elapsed > 0 else 0.0  # 计算每分钟吞吐量。
    payload = {  # 构建结构化摘要字典。
        "total": total,
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "elapsed_sec": elapsed,
        "avg_file_sec": avg_latency,
        "throughput_files_per_min": throughput,
    }
    message = (
        "Summary total={total} processed={processed} succeeded={succeeded} failed={failed} "
        "skipped={skipped} elapsed={elapsed:.2f}s throughput={throughput:.2f}/min"
    ).format(
        total=total,
        processed=processed,
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        elapsed=elapsed,
        throughput=throughput,
    )  # 使用 format 构建可读字符串。
    if isinstance(logger, StructuredLogger):  # 针对结构化日志器调用 info。
        logger.info("pipeline summary", summary=payload, text=message)  # 输出摘要并附带原始字符串。
    elif isinstance(logger, logging.Logger):  # 对传统 logger 保持兼容。
        logger.info(message)  # 输出人类可读字符串。
    else:  # 未提供 logger 时退化为模块级 logging。
        logging.getLogger("ASRProgram").info(message)  # 使用模块级日志器输出。
