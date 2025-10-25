"""实现简易的指标收集、汇总与导出工具。"""  # 模块文档说明，描述功能定位。
import csv  # 导入 csv 以便导出表格格式指标。
import io  # 导入 io 以创建内存中的字符串缓冲区。
import json  # 导入 json 以导出 JSONL 指标。
from dataclasses import dataclass  # 导入 dataclass 简化统计结构定义。
from pathlib import Path  # 导入 Path 处理文件路径。
from typing import Any, Dict, Iterable, Tuple  # 导入类型注释提高可读性。

from src.utils.io import atomic_write_text, jsonl_append, safe_mkdirs  # 复用已有 I/O 工具。


@dataclass
class _SummaryStats:
    """用于观测指标的摘要统计结构。"""  # 类说明。

    count: int = 0  # 记录观测次数。
    total: float = 0.0  # 记录观测值总和。
    minimum: float | None = None  # 记录最小值。
    maximum: float | None = None  # 记录最大值。

    def update(self, value: float) -> None:
        """使用新的观测值更新统计信息。"""  # 方法说明。
        self.count += 1  # 增加样本数量。
        self.total += value  # 累加总和。
        self.minimum = value if self.minimum is None else min(self.minimum, value)  # 更新最小值。
        self.maximum = value if self.maximum is None else max(self.maximum, value)  # 更新最大值。

    def as_record(self) -> Dict[str, Any]:
        """将摘要统计转换为导出友好的字典。"""  # 方法说明。
        average = self.total / self.count if self.count else 0.0  # 计算平均值。
        return {  # 构建包含核心统计量的字典。
            "count": self.count,
            "sum": self.total,
            "min": self.minimum,
            "max": self.maximum,
            "avg": average,
        }


class MetricsSink:
    """收集计数器与观测值，并支持导出到 CSV/JSONL。"""  # 类说明。

    def __init__(self) -> None:
        """初始化内部数据结构。"""  # 方法说明。
        self._counters: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], float] = {}  # 存储计数器值。
        self._summaries: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], _SummaryStats] = {}  # 存储观测统计。

    @staticmethod
    def _normalize_labels(labels: Dict[str, Any] | None) -> Tuple[Tuple[str, Any], ...]:
        """将标签字典转换为排序后的不可变元组，便于用作字典键。"""  # 方法说明。
        if not labels:  # 若标签为空或 None。
            return tuple()  # 返回空元组。
        return tuple(sorted((str(key), labels[key]) for key in labels))  # 按键排序并返回元组。

    def inc(self, name: str, value: float = 1.0, labels: Dict[str, Any] | None = None) -> None:
        """将指定计数器增加给定数值。"""  # 方法说明。
        key = (name, self._normalize_labels(labels))  # 组合指标名称与标签作为键。
        previous = self._counters.get(key, 0.0)  # 读取当前累计值，默认为 0。
        self._counters[key] = previous + value  # 累加新的计数值。

    def observe(self, name: str, value: float, labels: Dict[str, Any] | None = None) -> None:
        """记录一个观测指标的数值。"""  # 方法说明。
        key = (name, self._normalize_labels(labels))  # 构造键。
        stats = self._summaries.setdefault(key, _SummaryStats())  # 获取或创建统计对象。
        stats.update(value)  # 更新统计信息。

    def _iter_counters(self) -> Iterable[Dict[str, Any]]:
        """生成所有计数器的导出记录。"""  # 方法说明。
        for (name, labels), value in self._counters.items():  # 遍历计数器字典。
            yield {
                "type": "counter",
                "metric": name,
                "value": value,
                "labels": dict(labels),
            }  # 产出标准化记录。

    def _iter_summaries(self) -> Iterable[Dict[str, Any]]:
        """生成所有观测指标的导出记录。"""  # 方法说明。
        for (name, labels), stats in self._summaries.items():  # 遍历摘要统计。
            record = {
                "type": "summary",
                "metric": name,
                "labels": dict(labels),
            }  # 构建基础结构。
            record.update(stats.as_record())  # 合并统计数据。
            yield record  # 产出记录。

    def export_jsonl(self, path: str) -> None:
        """将所有指标以 JSONL 格式追加到指定文件。"""  # 方法说明。
        target = Path(path)  # 将路径转换为 Path 对象。
        safe_mkdirs(target.parent)  # 确保父目录存在。
        target.unlink(missing_ok=True)  # 为避免重复内容，先删除旧文件。
        for record in list(self._iter_counters()) + list(self._iter_summaries()):  # 遍历所有记录。
            jsonl_append(path, record)  # 使用原子追加写入 JSON 行。

    def export_csv(self, path: str) -> None:
        """将指标导出为 CSV 文件。"""  # 方法说明。
        buffer = io.StringIO()  # 创建内存缓冲区收集 CSV 内容。
        fieldnames = [
            "type",
            "metric",
            "value",
            "count",
            "sum",
            "min",
            "max",
            "avg",
            "labels",
        ]  # 定义 CSV 表头。
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)  # 创建字典写入器。
        writer.writeheader()  # 写入表头行。
        for record in self._iter_counters():  # 写入计数器记录。
            writer.writerow({
                "type": record["type"],
                "metric": record["metric"],
                "value": record["value"],
                "labels": json.dumps(record["labels"], ensure_ascii=False),
            })
        for record in self._iter_summaries():  # 写入观测记录。
            writer.writerow({
                "type": record.get("type"),
                "metric": record.get("metric"),
                "count": record.get("count"),
                "sum": record.get("sum"),
                "min": record.get("min"),
                "max": record.get("max"),
                "avg": record.get("avg"),
                "labels": json.dumps(record.get("labels", {}), ensure_ascii=False),
            })
        atomic_write_text(path, buffer.getvalue())  # 使用原子写入落盘。

    def get_counter(self, name: str, labels: Dict[str, Any] | None = None) -> float:
        """读取指定计数器的累计值，若不存在则返回 0。"""  # 方法说明。
        key = (name, self._normalize_labels(labels))  # 构造键。
        return self._counters.get(key, 0.0)  # 返回累计值。

    def summary(self, labels: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """生成概览性指标摘要，供人类阅读或日志打印。"""  # 方法说明。
        base_labels = self._normalize_labels(labels)  # 正常化标签。
        label_dict = dict(base_labels)  # 转换为字典以复用。
        total = self.get_counter("files_total", label_dict)  # 读取总文件数。
        succeeded = self.get_counter("files_succeeded", label_dict)  # 读取成功数量。
        failed = self.get_counter("files_failed", label_dict)  # 读取失败数量。
        skipped = self.get_counter("files_skipped", label_dict)  # 读取跳过数量。
        elapsed_stats = self._summaries.get(("elapsed_total_sec", base_labels))  # 获取整体耗时摘要。
        elapsed = elapsed_stats.total if elapsed_stats else 0.0  # 若存在则读取总耗时。
        avg_file_sec = elapsed / total if total else 0.0  # 计算平均耗时。
        throughput = (succeeded / elapsed * 60.0) if elapsed > 0 else 0.0  # 计算吞吐量。
        return {
            "files_total": total,
            "files_succeeded": succeeded,
            "files_failed": failed,
            "files_skipped": skipped,
            "elapsed_total_sec": elapsed,
            "avg_file_sec": avg_file_sec,
            "throughput_files_per_min": throughput,
        }  # 返回结构化摘要。
