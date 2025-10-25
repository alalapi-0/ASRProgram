"""定义管线使用的错误类型与分类辅助函数。"""  # 模块说明。
# 导入 errno 以识别常见的 I/O 错误码。 
import errno

# 定义可重试错误类型，表示暂时性故障。 
class RetryableError(Exception):
    """表示可以通过重试恢复的暂时性错误。"""  # 类说明。

# 定义不可重试错误类型，表示应立即放弃的致命故障。 
class NonRetryableError(Exception):
    """表示无需重试的致命错误，例如配置或权限问题。"""  # 类说明。

# 定义异常分类函数，帮助决定是否重试或记录错误类型。 
def classify_exception(exc: Exception) -> str:
    """根据异常类型返回 retryable/non-retryable/unknown 标签。"""  # 函数说明。
    # 直接判断是否已是管线定义的错误类型。 
    if isinstance(exc, RetryableError):
        return "retryable"
    if isinstance(exc, NonRetryableError):
        return "non-retryable"
    # TimeoutError 常常属于暂时性问题，可重试。 
    if isinstance(exc, TimeoutError):
        return "retryable"
    # 连接相关错误大多为暂时问题，同样视为可重试。 
    if isinstance(exc, ConnectionError):
        return "retryable"
    # 文件不存在属于用户输入问题，视为不可重试。 
    if isinstance(exc, FileNotFoundError):
        return "non-retryable"
    # 权限拒绝通常需要手动干预，视为不可重试。 
    if isinstance(exc, PermissionError):
        return "non-retryable"
    # 针对通用的 OSError，根据 errno 进行进一步分类。 
    if isinstance(exc, OSError):
        if exc.errno in {errno.EAGAIN, errno.EWOULDBLOCK, errno.ETIMEDOUT, errno.EBUSY, errno.ENETUNREACH}:
            return "retryable"
        if exc.errno in {errno.EACCES, errno.ENOENT, errno.ENOTDIR, errno.EISDIR}:
            return "non-retryable"
    # 无法识别的异常返回 unknown，交由上层决定处理策略。 
    return "unknown"
