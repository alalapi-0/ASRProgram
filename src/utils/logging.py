"""封装日志配置，提供统一的日志器创建函数。"""
# 导入 logging 模块以配置日志输出。
import logging
# 定义获取日志器的辅助函数。
def get_logger(verbose: bool) -> logging.Logger:
    """根据 verbose 标志返回配置好的日志器实例。"""
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
