"""封装日志、进度与汇总打印的辅助函数。"""  # 模块文档字符串。
# 导入 logging 模块用于创建统一的日志器。 
import logging
# 尝试导入 tqdm 以在环境可用时展示进度条。 
try:
    from tqdm import tqdm  # type: ignore
except Exception:  # noqa: BLE001
    tqdm = None  # 若导入失败则回退到手写进度逻辑。

# 定义获取日志器的辅助函数。 
def get_logger(verbose: bool) -> logging.Logger:
    """根据 verbose 标志返回配置好的日志器实例。"""  # 函数说明。
    # 获取名为 ASRProgram 的日志器。 
    logger = logging.getLogger("ASRProgram")
    # 若日志器尚未配置处理器，则进行初始化。 
    if not logger.handlers:
        # 创建一个流式处理器，将日志输出到标准输出。 
        handler = logging.StreamHandler()
        # 设置简洁的日志格式，包含等级与消息。 
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        # 将格式应用到处理器。 
        handler.setFormatter(formatter)
        # 将处理器添加到日志器。 
        logger.addHandler(handler)
    # 根据 verbose 参数调整日志等级。 
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    # 返回配置好的日志器。 
    return logger

# 定义简单的进度打印类，封装 tqdm 与手动输出。 
class ProgressPrinter:
    """根据是否可用 tqdm 选择最佳的进度展示方式。"""  # 类说明。

    # 初始化函数接收总任务数、描述信息与是否启用。 
    def __init__(self, total: int, description: str, enabled: bool) -> None:
        """创建进度对象，total<=0 或未启用时将退化为空操作。"""  # 方法说明。
        # 保存启用标志，以便后续快速返回。 
        self.enabled = enabled and total > 0
        # 保存描述文本，用于手动模式时打印。 
        self.description = description
        # 初始化当前进度计数。 
        self.count = 0
        # 根据环境是否存在 tqdm 来决定使用哪种实现。 
        if self.enabled and tqdm is not None:
            # tqdm 模式下创建进度条并保存引用。 
            self._bar = tqdm(total=total, desc=description, leave=False)
        else:
            # 否则退化为 None，后续使用手动日志。 
            self._bar = None
        # 记录总任务数以便计算百分比。 
        self.total = total

    # 定义更新进度的方法，可附带状态提示。 
    def update(self, message: str | None = None) -> None:
        """推进一个单位的进度并可选打印附加消息。"""  # 方法说明。
        # 若未启用则直接返回。 
        if not self.enabled:
            return
        # 若使用 tqdm，则调用其 update API。 
        if self._bar is not None:
            self._bar.update(1)
            # tqdm 支持 postfix 字符串，用于展示最近状态。 
            if message:
                self._bar.set_postfix_str(message, refresh=False)
        else:
            # 手动模式下递增计数并计算完成百分比。 
            self.count += 1
            percent = (self.count / self.total) * 100 if self.total else 0
            # 直接使用 logging.info 打印单行概要。 
            logging.info("%s %d/%d (%.1f%%)%s", self.description, self.count, self.total, percent, f" - {message}" if message else "")

    # 定义关闭方法，在 tqdm 模式下清理资源。 
    def close(self) -> None:
        """结束进度展示，确保 tqdm 光标复位。"""  # 方法说明。
        # tqdm 模式下关闭进度条。 
        if self._bar is not None:
            self._bar.close()

# 定义每个文件任务日志的辅助类，集中管理输出格式。 
class TaskLogger:
    """在 verbose 模式下输出细粒度的任务状态日志。"""  # 类说明。

    # 初始化函数保存日志器与开关。 
    def __init__(self, logger: logging.Logger, verbose: bool) -> None:
        """记录日志器引用与是否启用详细输出。"""  # 方法说明。
        # 保存日志器，后续所有输出复用同一实例。 
        self.logger = logger
        # 保存 verbose 标志，避免重复判断。 
        self.verbose = verbose

    # 定义任务开始时的日志输出。 
    def start(self, path: str) -> None:
        """记录任务开始执行的提示信息。"""  # 方法说明。
        # 仅在 verbose 模式下输出详细日志。 
        if self.verbose:
            self.logger.debug("Start processing %s", path)

    # 定义重试提示，包含失败次数与原因。 
    def retry(self, path: str, attempt: int, exc: Exception) -> None:
        """在捕获可重试异常后记录警告日志。"""  # 方法说明。
        # 仅在 verbose 模式下输出重试信息，避免噪音。 
        if self.verbose:
            self.logger.warning("Retry %d for %s due to %s", attempt, path, exc)

    # 定义成功完成时的日志输出。 
    def success(self, path: str, duration: float, attempts: int, outputs: list[str]) -> None:
        """记录任务完成、耗时与输出路径。"""  # 方法说明。
        # 仅在 verbose 模式下输出详细成功日志。 
        if self.verbose:
            self.logger.debug(
                "Success %s attempts=%d duration=%.2fs outputs=%s",
                path,
                attempts,
                duration,
                ", ".join(outputs),
            )

    # 定义失败日志，包含尝试次数与错误原因。 
    def failure(self, path: str, attempts: int, exc: Exception) -> None:
        """记录任务最终失败的错误信息。"""  # 方法说明。
        # 无论是否 verbose 都打印错误，以便用户感知问题。 
        self.logger.error("Failed %s after %d attempts: %s", path, attempts, exc)

    # 定义跳过日志，用于 skip-done 或 dry-run。 
    def skipped(self, path: str, reason: str) -> None:
        """记录任务被跳过的原因。"""  # 方法说明。
        # 在 verbose 模式下输出详细的跳过信息。 
        if self.verbose:
            self.logger.info("Skipped %s (%s)", path, reason)

# 定义打印统计汇总的辅助函数。 
def print_summary(summary: dict, logger: logging.Logger | None = None) -> None:
    """以结构化格式输出批处理的统计信息。"""  # 函数说明。
    # 若未提供日志器则使用模块级 logger。 
    active_logger = logger or logging.getLogger("ASRProgram")
    # 构建若干基础指标并确保缺失字段拥有默认值。 
    total = summary.get("total", 0)
    processed = summary.get("processed", 0)
    succeeded = summary.get("succeeded", 0)
    failed = summary.get("failed", 0)
    skipped = summary.get("skipped", 0)
    cancelled = summary.get("cancelled", 0)
    retried = summary.get("retried_count", 0)
    elapsed = summary.get("elapsed_sec", 0.0)
    # 计算平均耗时与吞吐量，避免除以零。 
    avg_latency = elapsed / processed if processed else 0.0
    throughput = (succeeded / elapsed * 60.0) if elapsed > 0 else 0.0
    # 打印整体计数信息。 
    active_logger.info(
        "Summary: total=%d queued=%d processed=%d succeeded=%d failed=%d skipped=%d cancelled=%d", 
        total,
        summary.get("queued", processed + skipped + cancelled),
        processed,
        succeeded,
        failed,
        skipped,
        cancelled,
    )
    # 打印耗时与吞吐量指标。 
    active_logger.info(
        "Timing: elapsed=%.2fs avg_latency=%.2fs throughput=%.2f files/min", 
        elapsed,
        avg_latency,
        throughput,
    )
    # 打印重试统计，帮助判断稳定性。 
    active_logger.info("Retries: retried_total=%d", retried)
    # 若存在失败项则输出前几条详情。 
    errors = summary.get("errors", [])
    if errors:
        sample = errors[:3]
        active_logger.warning("Failures (%d shown of %d):", len(sample), len(errors))
        for item in sample:
            active_logger.warning(" - %s -> %s", item.get("input"), item.get("reason"))
    # 若存在跳过记录且 verbose 用户可能关注，则打印前几条。 
    skipped_items = summary.get("skipped_items", [])
    if skipped_items:
        sample = skipped_items[:3]
        active_logger.info("Skipped samples (%d shown of %d):", len(sample), len(skipped_items))
        for item in sample:
            active_logger.info(" - %s (%s)", item.get("input"), item.get("reason"))
    # 打印输出目录，帮助定位结果。 
    if "out_dir" in summary:
        active_logger.info("Outputs stored in %s", summary["out_dir"])
