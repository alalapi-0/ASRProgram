"""验证结构化日志与指标导出功能的单元测试。"""  # 模块说明，解释测试目标。
import json  # 导入 json 以解析 JSONL 日志与指标文件。
import sys  # 导入 sys 以在测试中调整模块搜索路径。
from pathlib import Path  # 导入 Path 以便构造临时文件路径。

ROOT = Path(__file__).resolve().parents[1]  # 计算仓库根目录路径。
if str(ROOT) not in sys.path:  # 若根目录未在 sys.path 中。
    sys.path.insert(0, str(ROOT))  # 将其加入模块搜索路径以支持 from src 导入。

from src.asr.pipeline import run  # 导入管线以执行端到端流程。
from src.utils.logging import get_logger  # 导入日志工厂以测试采样行为。


def _read_json_lines(path: Path) -> list[dict]:
    """读取 JSONL 文件并返回字典列表。"""  # 辅助函数说明。
    lines: list[dict] = []  # 初始化结果列表。
    with path.open("r", encoding="utf-8") as handle:  # 以文本模式打开文件。
        for raw in handle:  # 遍历每一行原始文本。
            raw = raw.strip()  # 去除首尾空白字符。
            if not raw:  # 跳过空行。
                continue  # 空字符串直接忽略。
            lines.append(json.loads(raw))  # 解析 JSON 并追加到结果。
    return lines  # 返回解析结果。


def test_pipeline_writes_jsonl_logs_and_metrics(tmp_path: Path) -> None:
    """运行一次最小任务并断言日志与指标格式正确。"""  # 测试说明。
    input_dir = tmp_path / "inputs"  # 构造输入目录路径。
    input_dir.mkdir(parents=True, exist_ok=True)  # 创建输入目录。
    audio_file = input_dir / "sample.wav"  # 构造占位音频文件路径。
    audio_file.write_bytes(b"\x00\x00")  # 写入少量字节构成伪音频文件。
    out_dir = tmp_path / "out"  # 构造输出目录。
    log_file = tmp_path / "run.log"  # 构造日志输出文件路径。
    metrics_file = tmp_path / "metrics.jsonl"  # 构造指标输出文件路径。
    summary = run(  # 调用管线执行最小任务。
        input_path=str(input_dir),
        out_dir=str(out_dir),
        backend_name="dummy",
        language="auto",
        segments_json=True,
        overwrite=True,
        dry_run=False,
        verbose=False,
        log_format="jsonl",
        log_level="INFO",
        log_file=str(log_file),
        log_sample_rate=1.0,
        quiet=True,
        metrics_file=str(metrics_file),
        profile=True,
        progress=False,
        num_workers=1,
        max_retries=0,
        rate_limit=0.0,
        skip_done=False,
        fail_fast=False,
        integrity_check=True,
        lock_timeout=1.0,
        cleanup_temp=True,
        force=True,
    )
    assert summary["succeeded"] == 1  # 确认任务成功执行。
    assert log_file.exists()  # 日志文件应已生成。
    log_records = _read_json_lines(log_file)  # 读取日志记录。
    assert log_records, "expected non-empty log records"  # 至少存在一条日志。
    trace_ids = {record["trace_id"] for record in log_records if "trace_id" in record}  # 收集 TraceID。
    assert len(trace_ids) == 1  # 所有日志应共享同一 TraceID。
    for record in log_records:  # 遍历每条日志进行字段校验。
        assert "ts" in record  # 日志应包含时间戳。
        assert "level" in record  # 日志应包含等级字段。
        assert "msg" in record  # 日志应包含消息字段。
        assert "trace_id" in record  # 日志应包含 TraceID。
    assert any(record["msg"] in {"task finished", "task success"} for record in log_records)  # 应至少包含任务完成日志。
    assert metrics_file.exists()  # 指标文件应已生成。
    metrics_records = _read_json_lines(metrics_file)  # 读取指标记录。
    assert any(rec.get("metric") == "files_total" and rec.get("value") >= 1 for rec in metrics_records)  # 存在总文件计数。
    assert any(rec.get("metric") == "files_succeeded" and rec.get("value") >= 1 for rec in metrics_records)  # 存在成功计数。
    assert any(rec.get("metric") == "throughput_files_per_min" for rec in metrics_records)  # 吞吐量指标应被导出。


def test_logging_sampling_respects_rate(tmp_path: Path) -> None:
    """验证日志采样对信息级日志生效而错误级别不受影响。"""  # 测试说明。
    log_path = tmp_path / "sample.log"  # 构造日志文件路径。
    logger = get_logger(  # 创建启用采样的日志器。
        format="jsonl",
        level="INFO",
        log_file=str(log_path),
        sample_rate=0.1,
        quiet=True,
    )
    for index in range(50):  # 连续写入 50 条信息级日志。
        logger.info("info message", index=index)  # 写入信息级日志。
    for index in range(5):  # 写入 5 条错误日志。
        logger.error("error message", index=index)  # 写入错误级日志。
    records = _read_json_lines(log_path)  # 读取日志文件。
    info_logs = [record for record in records if record.get("level") == "INFO"]  # 统计信息级日志数量。
    error_logs = [record for record in records if record.get("level") == "ERROR"]  # 统计错误日志数量。
    assert len(info_logs) < 50  # 采样应减少信息级日志数量。
    assert len(info_logs) > 0  # 仍应保留部分信息级日志。
    assert len(error_logs) == 5  # 错误日志不应被采样。
