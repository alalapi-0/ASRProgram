"""提供线程并发、重试与限流等通用工具。"""  # 模块文档字符串。
# 导入 concurrent.futures 以使用线程池执行器。
import concurrent.futures  # noqa: ICN001
# 导入 random 用于在重试延迟中引入抖动避免同步风暴。
import random
# 导入 threading 以使用 Event 控制定向取消行为。
import threading
# 导入 time 以便在限流与重试之间进行休眠。
import time
# 导入 typing 中的 Any、Callable、Iterable、List、Optional、Tuple、TypeVar 以注解函数签名。
from typing import Any, Callable, Iterable, List, Optional, Tuple, TypeVar

# 声明两个泛型 TypeVar，分别表示任务输入与任务输出类型。
T = TypeVar("T")  # 输入类型变量。
R = TypeVar("R")  # 输出类型变量。

# 定义自定义异常类用于在重试耗尽后携带上下文信息。
class RetryError(Exception):
    """在超过允许的重试次数后抛出的异常类型。"""  # 类说明。

    # 初始化函数记录最后一次异常与尝试次数。
    def __init__(self, last_exception: Exception, attempts: int, history: List[Exception]):
        """保存最终异常、已执行的尝试次数与历史异常列表。"""  # 方法说明。
        # 调用基类构造函数，使用最后一次异常的字符串表示作为消息。
        super().__init__(str(last_exception))
        # 保存最终异常实例以便调用方进一步分析。
        self.last_exception = last_exception
        # 保存累计的尝试次数（包含首次尝试）。
        self.attempts = attempts
        # 保存每次失败时捕获的异常列表，便于调试。
        self.history = history

# 定义重试装饰器，用于在函数抛出可重试异常时自动重新执行。
def retry(
    max_retries: int,
    backoff: float = 1.0,
    jitter: bool = False,
    retriable_exceptions: Tuple[type[BaseException], ...] = (Exception,),
    giveup_exceptions: Tuple[type[BaseException], ...] = (),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """返回一个装饰器，在捕获指定异常时执行指数退避重试。"""  # 函数说明。

    # 内部装饰器函数真正接受被装饰的可调用对象。
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        """包装原始函数以添加重试逻辑。"""  # 内部函数说明。

        # 定义实际执行函数的包装器。
        def wrapper(*args: Any, **kwargs: Any) -> R:
            """执行函数并在遇到暂时性错误时按需重试。"""  # 包装器说明。
            # 记录已经执行的失败次数（对应已经发生的异常次数）。
            failures = 0
            # 维护一个列表保存每次失败的异常，便于最终汇报。
            history: List[Exception] = []
            # 初始化当前延迟时间，默认为 1 秒，可被 backoff 放大。
            delay = 1.0
            # 使用无限循环，根据条件决定何时跳出。
            while True:
                try:
                    # 调用被装饰的函数，将返回值直接交还给调用方。
                    return func(*args, **kwargs)
                except giveup_exceptions:
                    # 对于显式标记为不可重试的异常，直接向上传播。
                    raise
                except retriable_exceptions as exc:  # type: ignore[misc]
                    # 捕获可重试异常后记录失败次数。
                    failures += 1
                    # 将异常保存到历史列表中，用于最终构建 RetryError。
                    history.append(exc)
                    # 若失败次数已经超过允许的重试次数，则终止循环抛出 RetryError。
                    if failures > max_retries:
                        # 抛出自定义异常并附带最后一次异常与累计信息。
                        raise RetryError(exc, failures, history) from exc
                    # 如指定了 on_retry 回调，则在休眠前通知调用方当前失败情况。
                    if on_retry is not None:
                        on_retry(failures, exc)
                    # 计算本次休眠时间，基于当前 delay 并可选择引入抖动。
                    sleep_for = delay if not jitter else random.uniform(0, delay)
                    # 若指定了正向 backoff，则为下一轮尝试放大延迟。
                    if backoff > 0:
                        delay *= backoff
                    # 当 sleep_for 为正时执行休眠，防止频繁重试导致资源抢占。
                    if sleep_for > 0:
                        time.sleep(sleep_for)
                except Exception:
                    # 遇到非指定的异常类型时直接向上传播，由调用方决定处理策略。
                    raise

        # 返回包装后的函数。
        return wrapper

    # 返回装饰器函数。
    return decorator

# 定义令牌桶风格的限流器类，限制任务提交速率。
class RateLimiter:
    """按照指定速率控制任务启动频率。"""  # 类说明。

    # 初始化函数接收每秒允许的任务数量。
    def __init__(self, rate: float):
        """创建速率限制器，rate<=0 时视为禁用。"""  # 方法说明。
        # 保存速率值，确保非正值在后续逻辑中判定为禁用。
        self.rate = rate
        # 记录上一次授予令牌的时间戳，初始为当前时间。
        self._last = time.monotonic()
        # 为简单起见，令牌桶容量固定为 1。
        self._tokens = 1.0

    # 定义阻塞式获取令牌的方法。
    def acquire(self) -> None:
        """在需要时阻塞直到可以启动下一个任务。"""  # 方法说明。
        # 若速率非正则立即返回视为未启用限流。
        if self.rate <= 0:
            return
        # 进入循环，不断累积令牌直至满足条件。
        while True:
            # 获取当前时间戳以计算增量。
            now = time.monotonic()
            # 根据时间差增加令牌数量，最大不超过 1。
            elapsed = now - self._last
            self._last = now
            self._tokens = min(1.0, self._tokens + elapsed * self.rate)
            # 若桶中至少有 1 个令牌则消耗并返回。
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            # 若不足则休眠剩余时间，避免忙等。
            deficit = (1.0 - self._tokens) / self.rate
            time.sleep(max(deficit, 0.0))

# 定义线程池执行器的包装函数，统一处理限流与 fail-fast 行为。
def run_with_threadpool(
    tasks: Iterable[T],
    worker_fn: Callable[[T], R],
    *,
    max_workers: int,
    rate_limit: float | None = None,
    fail_fast: bool = False,
    stop_condition: Optional[Callable[[Any], bool]] = None,  # 可选回调在结果中触发停止。
) -> Tuple[List[Any], int, int]:
    """以线程池方式执行任务并返回结果列表、提交数量与完成数量。"""  # 函数说明。

    # 将任务迭代器转换为列表以便多次遍历与索引。
    task_list = list(tasks)
    # 初始化结果列表，预先填充 None 表示尚未完成。
    results: List[Any] = [None] * len(task_list)
    # 创建限流器实例，rate_limit 为空或 <=0 时可安全禁用。
    limiter = RateLimiter(rate_limit or 0.0)
    # 使用线程事件在 fail-fast 模式下通知停止提交新任务。
    stop_event = threading.Event()
    # 记录已提交与已完成的任务数量。
    submitted = 0
    completed = 0
    # 创建线程池执行器，确保使用 with 自动回收资源。
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 维护映射关系，用于根据 future 找回任务索引。
        in_flight: dict[concurrent.futures.Future[Any], int] = {}
        # 循环条件：只要还有任务待提交或仍有未完成的 future。
        while submitted < len(task_list) or in_flight:
            # 在有空闲 worker 且允许提交的前提下批量提交任务。
            while (
                submitted < len(task_list)
                and len(in_flight) < max_workers
                and (not fail_fast or not stop_event.is_set())
            ):
                # 若启用了限流则阻塞直到允许提交。
                limiter.acquire()
                # 取出当前索引对应的任务对象。
                task = task_list[submitted]
                # 提交任务给线程池并记录其 future。
                future = executor.submit(worker_fn, task)
                in_flight[future] = submitted
                # 提交计数加一。
                submitted += 1
            # 若当前没有任何运行中的任务，直接跳出循环。
            if not in_flight:
                break
            # 等待任意一个任务完成，以便及时处理结果与失败。
            done, _ = concurrent.futures.wait(
                in_flight.keys(),
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            # 遍历所有已完成的 future。
            for future in done:
                # 根据 future 找回原始任务索引。
                index = in_flight.pop(future)
                try:
                    # 获取任务执行结果并写入结果列表。
                    results[index] = future.result()  # 成功获取任务结果。
                    if fail_fast and stop_condition is not None:  # 在 fail-fast 下检查是否需要停止提交。
                        try:
                            if stop_condition(results[index]):  # 若回调判定应停止，设置事件。
                                stop_event.set()
                        except Exception:  # noqa: BLE001
                            stop_event.set()  # 回调异常同样触发停止以避免继续提交。
                except Exception as exc:  # noqa: BLE001
                    # 若任务抛出异常则将异常对象记录下来。
                    results[index] = exc
                    # 在 fail-fast 模式下，收到失败即触发停止提交。
                    if fail_fast:
                        stop_event.set()
                # 更新完成计数。
                completed += 1
    # 返回结果列表、提交数与完成数，供调用方汇总。
    return results, submitted, completed
