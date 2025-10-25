"""命令行入口，负责解析参数并调用 Round 4 管线。"""
# 导入 argparse 以解析命令行参数。
import argparse
# 导入 sys 以在脚本作为模块运行时返回退出码。
import sys
# 从管线模块导入 run 函数执行核心逻辑。
from src.asr.pipeline import run
# 导入日志工具以统一输出格式。
from src.utils.logging import get_logger

# 定义允许的后端名称集合，便于参数校验。
ALLOWED_BACKENDS = {"dummy", "faster-whisper"}

# 定义布尔参数解析函数，支持 true/false 字符串。
def parse_bool(value: str) -> bool:
    """将传入值解析为布尔类型，仅接受 true/false。"""
    # 如果调用方已经传入布尔值（例如默认值），直接返回。
    if isinstance(value, bool):
        return value
    # 将输入字符串统一转为小写，避免大小写影响判断。
    normalized = value.lower()
    # 匹配字符串 true。
    if normalized == "true":
        return True
    # 匹配字符串 false。
    if normalized == "false":
        return False
    # 其他取值均视为非法，交给 argparse 抛出错误。
    raise argparse.ArgumentTypeError("Expected 'true' or 'false'")

# 构建命令行解析器，保持与前几轮参数兼容。
def build_parser() -> argparse.ArgumentParser:
    """创建参数解析器并声明所有可用选项。"""
    # 初始化解析器对象并提供描述信息。
    parser = argparse.ArgumentParser(
        description="ASRProgram Round 4 placeholder transcription pipeline"
    )
    # 添加输入路径参数，支持文件或目录。
    parser.add_argument("--input", required=True, help="输入音频文件或目录")
    # 添加输出目录参数，默认值为 out。
    parser.add_argument("--out-dir", default="out", help="输出 JSON 所在目录")
    # 添加后端选择参数。
    parser.add_argument(
        "--backend",
        default="dummy",
        help="指定转写后端（dummy 或 faster-whisper，占位实现）",
    )
    # 添加语言参数，用于写入 JSON 元信息。
    parser.add_argument("--language", default="auto", help="指定语言占位信息")
    # 控制是否生成 segments.json。
    parser.add_argument(
        "--segments-json",
        type=parse_bool,
        default="true",
        help="是否输出 <name>.segments.json (true/false)",
    )
    # 控制是否覆盖已有结果。
    parser.add_argument(
        "--overwrite",
        type=parse_bool,
        default="false",
        help="是否覆盖已存在的输出 (true/false)",
    )
    # dry-run 模式仅打印计划。
    parser.add_argument(
        "--dry-run",
        type=parse_bool,
        default="false",
        help="只打印计划，不创建目录或文件 (true/false)",
    )
    # verbose 模式输出更详细的日志。
    parser.add_argument(
        "--verbose",
        type=parse_bool,
        default="false",
        help="输出详细日志 (true/false)",
    )
    # 返回配置好的解析器。
    return parser

# 定义主函数作为命令行程序入口。
def main(argv: list[str] | None = None) -> int:
    """解析参数并调用管线，返回退出状态码。"""
    # 构建解析器并解析命令行参数。
    parser = build_parser()
    args = parser.parse_args(argv)
    # 校验后端名称是否在允许集合中，非法时通过 parser.error 退出。
    if args.backend not in ALLOWED_BACKENDS:
        parser.error(
            f"Unsupported backend '{args.backend}'. Choose from: {', '.join(sorted(ALLOWED_BACKENDS))}"
        )
    # 初始化日志器，日志级别由 verbose 控制。
    logger = get_logger(args.verbose)
    # 在详细模式下打印解析到的参数摘要，便于追踪执行配置。
    if args.verbose:
        logger.debug(
            "CLI parsed arguments: input=%s out_dir=%s backend=%s language=%s segments_json=%s overwrite=%s dry_run=%s",
            args.input,
            args.out_dir,
            args.backend,
            args.language,
            args.segments_json,
            args.overwrite,
            args.dry_run,
        )
    # 尝试执行管线并捕获致命异常，确保 CLI 返回非零退出码。
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
        )
    except Exception as exc:  # noqa: BLE001
        # 记录致命错误并在详细模式下打印堆栈。
        logger.error("Fatal pipeline error: %s", exc)
        if args.verbose:
            logger.exception("Stack trace for fatal pipeline error")
        # 返回非零退出码以指示执行失败。
        return 1
    # 打印统一的汇总信息，帮助用户快速了解结果。
    logger.info(
        "Summary: total=%d processed=%d succeeded=%d failed=%d out_dir=%s",
        summary["total"],
        summary["processed"],
        summary["succeeded"],
        summary["failed"],
        summary["out_dir"],
    )
    # 如存在错误项，输出警告并在 verbose 模式下列出详细条目。
    if summary["errors"]:
        logger.warning("Encountered %d file errors; see *.error.txt for details", len(summary["errors"]))
        if args.verbose:
            for error in summary["errors"]:
                logger.warning(" - %s -> %s", error["input"], error["reason"])
    # 根据需求，无论是否存在错误文件，只要处理完成即返回 0。
    return 0

# 允许通过 python -m 调用模块。
if __name__ == "__main__":
    # 将 main 的返回值作为进程退出码。
    sys.exit(main())
