"""命令行入口，负责解析参数并调用并发管线。"""  # 模块说明。
# 导入 argparse 以解析命令行参数。 
import argparse
# 导入 sys 以在脚本作为模块运行时返回退出码。 
import sys
import traceback  # 导入 traceback 以在 verbose 模式下输出堆栈。
# 导入 Path 以在默认 manifest 路径中复用。 
from pathlib import Path
# 从管线模块导入 run 函数执行核心逻辑。 
from src.asr.pipeline import run
# 导入日志工具以统一输出格式与打印汇总。 
from src.utils.logging import get_logger

# 定义允许的后端名称集合，便于参数校验。 
ALLOWED_BACKENDS = {"dummy", "faster-whisper"}

# 定义布尔参数解析函数，支持 true/false 字符串。 
def parse_bool(value: str) -> bool:
    """将传入值解析为布尔类型，仅接受 true/false。"""  # 函数说明。
    if isinstance(value, bool):  # 若已是布尔值则直接返回。
        return value
    normalized = value.lower()  # 统一转换为小写。
    if normalized == "true":  # 匹配 true。
        return True
    if normalized == "false":  # 匹配 false。
        return False
    raise argparse.ArgumentTypeError("Expected 'true' or 'false'")  # 其他值抛出错误。

# 构建命令行解析器，保持与前几轮参数兼容并新增 Round11 选项。 
def build_parser() -> argparse.ArgumentParser:
    """创建参数解析器并声明所有可用选项。"""  # 函数说明。
    parser = argparse.ArgumentParser(
        description="ASRProgram Round 12 transcription pipeline",
    )
    parser.add_argument("--input", required=True, help="输入音频文件或目录")
    parser.add_argument("--out-dir", default="out", help="输出 JSON 所在目录")
    parser.add_argument(
        "--backend",
        default="dummy",
        help="指定转写后端（dummy 或 faster-whisper，占位实现）",
    )
    parser.add_argument("--language", default="auto", help="指定语言占位信息")
    parser.add_argument(
        "--segments-json",
        type=parse_bool,
        default="true",
        help="是否输出 <name>.segments.json (true/false)",
    )
    parser.add_argument(
        "--overwrite",
        type=parse_bool,
        default="false",
        help="是否覆盖已存在的输出 (true/false)",
    )
    parser.add_argument(
        "--dry-run",
        type=parse_bool,
        default="false",
        help="只打印计划，不创建目录或文件 (true/false)",
    )
    parser.add_argument(
        "--verbose",
        type=parse_bool,
        default="false",
        help="输出详细日志 (true/false)",
    )
    parser.add_argument(
        "--log-format",
        choices=["human", "jsonl"],
        default="human",
        help="日志格式，human 适合调试，jsonl 适合机器消费",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="日志等级（DEBUG/INFO/WARNING/ERROR）",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="可选日志文件路径，追加写入",
    )
    parser.add_argument(
        "--log-sample-rate",
        type=float,
        default=1.0,
        help="信息级日志采样率 (0-1]",
    )
    parser.add_argument(
        "--metrics-file",
        default=None,
        help="若提供则导出指标到指定 CSV/JSONL",
    )
    parser.add_argument(
        "--profile",
        type=parse_bool,
        default="false",
        help="是否启用阶段耗时分析 (true/false)",
    )
    parser.add_argument(
        "--quiet",
        type=parse_bool,
        default="false",
        help="静默模式，控制台不输出 human 日志",
    )
    parser.add_argument(
        "--progress",
        type=parse_bool,
        default="true",
        help="是否显示进度条 (true/false)",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=1,
        help="并发 worker 数量 (1-8 建议)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="单文件失败后的最大重试次数",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.0,
        help="任务启动速率 (任务/秒，0 表示不限)",
    )
    parser.add_argument(
        "--skip-done",
        type=parse_bool,
        default="true",
        help="是否跳过已完成文件 (true/false)",
    )
    parser.add_argument(
        "--fail-fast",
        type=parse_bool,
        default="false",
        help="出现失败时是否立即停止提交剩余任务 (true/false)",
    )
    parser.add_argument(
        "--integrity-check",
        type=parse_bool,
        default="true",
        help="是否计算并比对输入文件 SHA-256 (true/false)",
    )
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=30.0,
        help="获取文件锁的超时时间（秒）",
    )
    parser.add_argument(
        "--cleanup-temp",
        type=parse_bool,
        default="true",
        help="是否清理历史 .tmp/.partial/.lock 残留 (true/false)",
    )
    parser.add_argument(
        "--manifest-path",
        default=None,
        help="自定义 Manifest JSONL 路径，默认写入输出目录 _manifest.jsonl",
    )
    parser.add_argument(
        "--force",
        type=parse_bool,
        default="false",
        help="忽略已有产物强制重跑 (true/false)",
    )
    return parser

# 定义主函数作为命令行程序入口。 
def main(argv: list[str] | None = None) -> int:
    """解析参数并调用管线，返回退出状态码。"""  # 函数说明。
    parser = build_parser()  # 构建解析器。
    args = parser.parse_args(argv)  # 解析命令行参数。
    if args.backend not in ALLOWED_BACKENDS:  # 校验后端名称是否支持。
        parser.error(
            f"Unsupported backend '{args.backend}'. Choose from: {', '.join(sorted(ALLOWED_BACKENDS))}"
        )
    sample_rate = max(min(args.log_sample_rate, 1.0), 1e-6)  # 对采样率进行截断避免非法值。
    logger = get_logger(  # 根据 CLI 参数创建结构化日志器。
        format=args.log_format,
        level=args.log_level,
        log_file=args.log_file,
        sample_rate=sample_rate,
        quiet=args.quiet,
    )
    if args.verbose:  # 在详细模式下输出解析后的参数。
        logger.debug("cli arguments", arguments=vars(args))
    manifest_path = args.manifest_path or str(Path(args.out_dir) / "_manifest.jsonl")
    try:
        summary = run(
            input_path=args.input,
            out_dir=args.out_dir,
            backend_name=args.backend,
            language=args.language,
            segments_json=args.segments_json,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            verbose=args.verbose,
            log_format=args.log_format,
            log_level=args.log_level,
            log_file=args.log_file,
            log_sample_rate=sample_rate,
            quiet=args.quiet,
            metrics_file=args.metrics_file,
            profile=args.profile,
            progress=args.progress,
            num_workers=max(1, args.num_workers),
            max_retries=max(0, args.max_retries),
            rate_limit=max(0.0, args.rate_limit),
            skip_done=args.skip_done,
            fail_fast=args.fail_fast,
            integrity_check=args.integrity_check,
            lock_timeout=max(0.0, args.lock_timeout),
            cleanup_temp=args.cleanup_temp,
            manifest_path=manifest_path,
            force=args.force,
            logger=logger,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("fatal pipeline error", error=str(exc))
        if args.verbose:
            logger.error("pipeline stack trace", trace=traceback.format_exc())
        return 1
    return 0

# 允许通过 python -m 调用模块。 
if __name__ == "__main__":
    sys.exit(main())
