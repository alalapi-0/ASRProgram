"""提供轻量级的阶段性能计时工具。"""  # 模块文档说明，概述功能。
import time  # 导入 time 以测量阶段耗时。
from typing import Any, Dict  # 导入类型注释提升可读性。

from src.utils.metrics import MetricsSink  # 引入指标收集器以汇报结果。


class PhaseTimer:
    """用于在 with 语句中测量单个阶段耗时并上报指标。"""  # 类说明。

    def __init__(
        self,
        metrics: MetricsSink,
        phase: str,
        labels: Dict[str, Any] | None = None,
        enabled: bool = False,
    ) -> None:
        """保存上下文信息并在需要时启用计时。"""  # 方法说明。
        self.metrics = metrics  # 保存指标收集器引用。
        self.phase = phase  # 保存阶段名称。
        self.labels = labels or {}  # 保存标签字典。
        self.enabled = enabled  # 保存是否启用计时的标志。
        self._start: float | None = None  # 初始化起始时间。
        self.elapsed: float | None = None  # 初始化耗时结果。

    def __enter__(self) -> "PhaseTimer":
        """记录进入时间并返回自身供 with 语句使用。"""  # 方法说明。
        if self.enabled:  # 仅在启用时记录时间。
            self._start = time.perf_counter()  # 使用高精度计时器记录起点。
        return self  # 返回自身供外部使用。

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, D401
        """退出上下文时计算耗时并写入指标。"""  # 方法说明。
        if not self.enabled:  # 若未启用则不执行任何操作。
            return  # 直接返回。
        if self._start is None:  # 若进入阶段失败则跳过。
            return  # 避免对 None 做减法。
        self.elapsed = time.perf_counter() - self._start  # 计算阶段耗时。
        metric_name = f"phase_{self.phase}_sec"  # 构造指标名称。
        self.metrics.observe(metric_name, self.elapsed, labels=self.labels)  # 将耗时写入指标收集器。
        self._start = None  # 清理起始时间以防重复使用。
