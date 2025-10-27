"""命令行入口，负责解析参数并调用并发管线。"""  # 模块说明。
import os
import argparse  # 导入 argparse 以解析命令行参数。
import logging
import sys  # 导入 sys 以支持通过 python -m 调用。
from pathlib import Path  # 导入 Path 以构造清单默认路径。

os.environ.setdefault("PYTHONUNBUFFERED", "1")
try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    pass

from src.asr.pipeline import run  # 导入 pipeline.run 执行核心逻辑。
from src.utils.config import (  # 导入配置工具以支持分层加载与快照。
    load_and_merge_config,
    parse_cli_set_items,
    render_effective_config,
    save_config,
)
from src.utils.logging import get_logger  # 导入日志工具创建结构化日志器。

ALLOWED_BACKENDS = {"dummy", "faster-whisper", "whisper.cpp"}  # 支持的后端列表。


def parse_bool(value: str) -> bool:
    """将传入值解析为布尔类型，仅接受 true/false。"""  # 函数说明。

    if isinstance(value, bool):  # 若已是布尔值直接返回。
        return value
    normalized = value.lower()  # 统一转换为小写。
    if normalized == "true":  # 匹配 true。
        return True
    if normalized == "false":  # 匹配 false。
        return False
    raise argparse.ArgumentTypeError("Expected 'true' or 'false'")  # 其他值抛出错误。


def build_parser() -> argparse.ArgumentParser:
    """创建参数解析器并声明所有可用选项。"""  # 函数说明。

    parser = argparse.ArgumentParser(
        description="ASRProgram Round 13 transcription pipeline",
    )  # 初始化解析器。
    parser.add_argument("--config", default=None, help="可选用户配置 YAML 路径，默认查找 config/user.yaml")
    parser.add_argument("--profile", dest="profile_name", default=None, help="选择预设 profile 名称")
    parser.add_argument(
        "--set",
        dest="set_items",
        action="append",
        default=[],
        help="通过 KEY=VALUE 覆盖任意配置，可重复使用",
    )
    parser.add_argument(
        "--print-config",
        type=parse_bool,
        default="false",
        help="打印最终配置快照后退出 (true/false)",
    )
    parser.add_argument("--save-config", default=None, help="保存最终配置快照到指定路径后退出")
    parser.add_argument("--input", required=True, help="输入音频文件或目录")
    parser.add_argument("--out-dir", default=None, help="输出目录，留空使用配置文件值")
    parser.add_argument(
        "--backend",
        choices=sorted(ALLOWED_BACKENDS),
        default=None,
        help="转写后端，允许 dummy/faster-whisper/whisper.cpp",
    )
    parser.add_argument("--language", default=None, help="显式指定语言代码，如 en/ja/zh")
    parser.add_argument(
        "--segments-json",
        type=parse_bool,
        default=None,
        help="是否输出 <name>.segments.json (true/false)",
    )
    parser.add_argument(
        "--overwrite",
        type=parse_bool,
        default=None,
        help="是否覆盖已存在的输出 (true/false)",
    )
    parser.add_argument(
        "--dry-run",
        type=parse_bool,
        default=None,
        help="只打印计划，不创建目录或文件 (true/false)",
    )
    parser.add_argument(
        "--verbose",
        type=parse_bool,
        nargs="?",
        const=True,
        default=None,
        help="输出详细日志 (可省略值以启用 true/false)",
    )
    parser.add_argument(
        "--log-format",
        choices=["human", "jsonl"],
        default=None,
        help="日志格式，human 适合调试，jsonl 适合机器消费",
    )
    parser.add_argument("--log-level", default=None, help="日志等级（DEBUG/INFO/WARNING/ERROR）")
    parser.add_argument("--log-file", default=None, help="可选日志文件路径，追加写入")
    parser.add_argument(
        "--tee-log",
        dest="tee_log",
        default=None,
        help="将控制台日志同时写入该文件（追加写入）",
    )
    parser.add_argument(
        "--log-sample-rate",
        type=float,
        default=None,
        help="信息级日志采样率 (0-1]",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="关闭进度动画，始终使用结构化日志展示进度",
    )
    parser.add_argument(
        "--force-flush",
        action="store_true",
        help="强制每条日志立即 flush，适合重定向或远程查看",
    )
    parser.add_argument("--metrics-file", default=None, help="若提供则导出指标到指定 CSV/JSONL")
    parser.add_argument(
        "--enable-profiler",
        type=parse_bool,
        default=None,
        help="是否启用阶段耗时分析 (true/false)",
    )
    parser.add_argument(
        "--quiet",
        type=parse_bool,
        default=None,
        help="静默模式，控制台不输出 human 日志 (true/false)",
    )
    parser.add_argument(
        "--progress",
        type=parse_bool,
        default=None,
        help="是否显示进度条 (true/false)",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=None,
        help="并发 worker 数量 (1-8 建议)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="单文件失败后的最大重试次数",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=None,
        help="任务启动速率 (任务/秒，0 表示不限)",
    )
    parser.add_argument(
        "--skip-done",
        type=parse_bool,
        default=None,
        help="是否跳过已完成文件 (true/false)",
    )
    parser.add_argument(
        "--fail-fast",
        type=parse_bool,
        default=None,
        help="出现失败时是否立即停止提交剩余任务 (true/false)",
    )
    parser.add_argument(
        "--integrity-check",
        type=parse_bool,
        default=None,
        help="是否计算并比对输入文件 SHA-256 (true/false)",
    )
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=None,
        help="获取文件锁的超时时间（秒）",
    )
    parser.add_argument(
        "--cleanup-temp",
        type=parse_bool,
        default=None,
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
        default=None,
        help="忽略已有产物强制重跑 (true/false)",
    )
    return parser


def _build_cli_overrides(args: argparse.Namespace) -> dict:
    """根据解析结果构造 CLI 覆盖字典，仅包含显式传入的键。"""  # 工具函数说明。

    overrides: dict[str, object] = {"input": args.input}  # input 为必填参数，直接写入。
    if args.out_dir is not None:  # 仅在用户提供时覆盖。
        overrides["out_dir"] = args.out_dir
    if args.dry_run is not None:
        overrides["dry_run"] = args.dry_run
    if args.verbose is not None:
        overrides["verbose"] = args.verbose
    if args.log_format is not None:
        overrides["log_format"] = args.log_format
    if args.log_level is not None:
        overrides["log_level"] = args.log_level
    if args.log_file is not None:
        overrides["log_file"] = args.log_file
    if args.log_sample_rate is not None:
        clamped = max(min(float(args.log_sample_rate), 1.0), 1e-6)  # 将采样率限制在合法区间。
        overrides["log_sample_rate"] = clamped
    if args.tee_log is not None:
        overrides["log_file"] = args.tee_log
    if args.metrics_file is not None:
        overrides["metrics_file"] = args.metrics_file
    if args.quiet is not None:
        overrides["quiet"] = args.quiet
    if args.progress is not None:
        overrides["progress"] = args.progress
    if args.no_progress:
        overrides["progress"] = False
    if args.force_flush:
        overrides["force_flush"] = True
    if args.num_workers is not None:
        overrides["num_workers"] = max(1, args.num_workers)
    if args.max_retries is not None:
        overrides["max_retries"] = max(0, args.max_retries)
    if args.rate_limit is not None:
        overrides["rate_limit"] = max(0.0, args.rate_limit)
    if args.skip_done is not None:
        overrides["skip_done"] = args.skip_done
    if args.fail_fast is not None:
        overrides["fail_fast"] = args.fail_fast
    if args.integrity_check is not None:
        overrides["integrity_check"] = args.integrity_check
    if args.lock_timeout is not None:
        overrides["lock_timeout"] = max(0.0, args.lock_timeout)
    if args.cleanup_temp is not None:
        overrides["cleanup_temp"] = args.cleanup_temp
    if args.manifest_path is not None:
        overrides["manifest_path"] = args.manifest_path
    if args.force is not None:
        overrides["force"] = args.force
    profiling_overrides: dict[str, object] = {}  # 收集 profiling 子配置。
    if args.enable_profiler is not None:
        profiling_overrides["enabled"] = args.enable_profiler
    if profiling_overrides:
        overrides["profiling"] = profiling_overrides
    runtime_overrides: dict[str, object] = {}  # 收集 runtime 子配置。
    if args.backend is not None:
        runtime_overrides["backend"] = args.backend
    if args.language is not None:
        runtime_overrides["language"] = args.language
    if args.segments_json is not None:
        runtime_overrides["segments_json"] = args.segments_json
    if args.overwrite is not None:
        runtime_overrides["overwrite"] = args.overwrite
    if runtime_overrides:
        overrides["runtime"] = runtime_overrides
    return overrides


def main(argv: list[str] | None = None) -> int:
    """解析参数并调用管线，返回退出状态码。"""  # 函数说明。

    parser = build_parser()  # 构建解析器。
    args = parser.parse_args(argv)  # 解析命令行参数。
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    tee_path: Path | None = None
    if args.tee_log:
        tee_path = Path(args.tee_log)
        tee_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(tee_path, mode="a", encoding="utf-8"))
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    for handler in handlers:
        handler.setFormatter(formatter)
        if args.force_flush:
            original_flush = handler.flush

            def _flush(h: logging.Handler = handler, func=original_flush) -> None:
                try:
                    func()
                finally:
                    stream = getattr(h, "stream", None)
                    if stream is not None:
                        try:
                            stream.flush()
                        except Exception:  # noqa: BLE001
                            pass

            handler.flush = _flush  # type: ignore[assignment]
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
    cli_logger = logging.getLogger("src.cli.main")
    if args.backend is not None and args.backend not in ALLOWED_BACKENDS:  # 若用户提供了非法后端。
        parser.error(
            f"Unsupported backend '{args.backend}'. Choose from: {', '.join(sorted(ALLOWED_BACKENDS))}"
        )  # 输出错误信息。
    cli_overrides = _build_cli_overrides(args)  # 根据 CLI 构造覆盖层。
    cli_set_overrides = parse_cli_set_items(args.set_items) if args.set_items else {}  # 解析 --set 列表。
    bundle = load_and_merge_config(
        cli_overrides=cli_overrides,
        cli_set_overrides=cli_set_overrides,
        config_path=args.config,
        profile_name=args.profile_name,
    )  # 执行分层配置加载。
    config = bundle.config  # 读取最终配置字典。
    if args.print_config:  # 若用户请求打印配置。
        cli_logger.info("effective config snapshot:\n%s", render_effective_config(bundle, include_sources=True))
        if args.save_config:  # 同时指定保存时一并处理。
            save_config(bundle, args.save_config)
        return 0  # 打印/保存后直接退出。
    if args.save_config:  # 仅保存配置时也需要提前退出。
        save_config(bundle, args.save_config)
        cli_logger.info("configuration saved", path=args.save_config)
        return 0
    sample_rate = float(config.get("log_sample_rate", 1.0))  # 读取归一化后的日志采样率。
    force_flush = bool(config.get("force_flush", False) or args.force_flush)
    tee_target = config.get("log_file") or (str(tee_path) if tee_path else None)
    logger = get_logger(  # 根据最终配置创建结构化日志器。
        format=config.get("log_format", "human"),
        level=config.get("log_level", "INFO"),
        log_file=tee_target,
        sample_rate=sample_rate,
        quiet=bool(config.get("quiet", False)),
        force_flush=force_flush,
    )
    if config.get("verbose"):  # 在 verbose 模式下打印关键配置。
        runtime_cfg = config.get("runtime", {})
        logger.debug(
            "effective profile",
            profile=bundle.profile or "default",
            backend=runtime_cfg.get("backend"),
            device=runtime_cfg.get("device"),
            compute_type=runtime_cfg.get("compute_type"),
            beam_size=runtime_cfg.get("beam_size"),
        )
    manifest_path = config.get("manifest_path")  # 读取清单路径。
    if not manifest_path:  # 若未显式指定则使用 out_dir/_manifest.jsonl。
        manifest_path = str(Path(config["out_dir"]) / "_manifest.jsonl")
    config["manifest_path"] = manifest_path  # 将推导结果写入配置传递给管线。
    try:
        run(config=config, logger=logger)  # 调用管线执行核心流程。
        return 0  # 正常运行即返回 0。
    except Exception:  # noqa: BLE001
        logger.exception("fatal pipeline error")
        return 1  # 非零退出表示失败。


if __name__ == "__main__":  # 允许脚本直接运行。
    sys.exit(main())  # 将返回值作为进程退出码。
