"""命令行入口，负责解析参数并调用转写管线。"""
# 导入 argparse 以解析命令行参数。
import argparse
# 导入 pathlib.Path 以处理路径参数。
from pathlib import Path
# 导入 sys 以设置退出状态码。
import sys
# 从管线模块导入 run 函数。
from src.asr.pipeline import run
# 从日志工具导入获取日志器的函数。
from src.utils.logging import get_logger

# 定义布尔参数解析器，将字符串转换为布尔值。
def parse_bool(value: str) -> bool:
    """将字符串形式的 true/false 转换为布尔类型。"""
    # 若传入的已经是布尔值（例如默认值），直接返回。
    if isinstance(value, bool):
        return value
    # 将输入字符串统一转为小写便于比较。
    normalized = value.lower()
    # 如果字符串为 true，返回 True。
    if normalized == "true":
        return True
    # 如果字符串为 false，返回 False。
    if normalized == "false":
        return False
    # 其他取值视为非法，抛出错误提示。
    raise argparse.ArgumentTypeError("Expected 'true' or 'false'")

# 定义主函数作为 CLI 入口。
def build_parser() -> argparse.ArgumentParser:
    """创建并返回参数解析器实例。"""
    # 初始化解析器并提供描述信息。
    parser = argparse.ArgumentParser(
        description="ASRProgram Round 1 dummy transcription pipeline"
    )
    # 添加 input 参数，指向单个文件或目录。
    parser.add_argument(
        "--input",
        required=True,
        help="输入的音频文件或目录路径",
    )
    # 添加输出目录参数，默认使用 out。
    parser.add_argument(
        "--out-dir",
        default="out",
        help="输出 JSON 文件目录，默认 out",
    )
    # 添加 backend 参数，本轮默认 dummy。
    parser.add_argument(
        "--backend",
        default="dummy",
        help="选择转写后端，当前仅支持 dummy",
    )
    # 添加语言参数，用于写入元数据。
    parser.add_argument(
        "--language",
        default="auto",
        help="指定语言占位信息，默认 auto",
    )
    # 添加控制段级 JSON 输出的布尔参数。
    parser.add_argument(
        "--segments-json",
        type=parse_bool,
        default="true",
        help="是否生成段级 JSON 文件 (true/false)",
    )
    # 添加覆盖标志参数。
    parser.add_argument(
        "--overwrite",
        type=parse_bool,
        default="false",
        help="是否覆盖已存在的输出文件 (true/false)",
    )
    # 添加预留的工作线程数参数。
    parser.add_argument(
        "--num-workers",
        type=int,
        default=1,
        help="预留的并行工作线程数，当前轮次忽略",
    )
    # 添加 dry-run 参数。
    parser.add_argument(
        "--dry-run",
        type=parse_bool,
        default="false",
        help="仅打印计划而不落盘 (true/false)",
    )
    # 添加 verbose 参数控制日志等级。
    parser.add_argument(
        "--verbose",
        type=parse_bool,
        default="false",
        help="输出更详细的日志 (true/false)",
    )
    # 返回配置完毕的解析器。
    return parser

# 定义主执行函数。
def main(argv: list[str] | None = None) -> int:
    """解析参数并调用转写管线，返回退出状态码。"""
    # 构建解析器。
    parser = build_parser()
    # 解析命令行参数。
    args = parser.parse_args(argv)
    # 将输出目录与输入路径转换为 Path 对象。
    input_path = Path(args.input)
    out_dir = Path(args.out_dir)
    # 初始化日志器以便 CLI 也能输出信息。
    logger = get_logger(args.verbose)
    # 记录即将启动管线的信息。
    logger.info("Starting pipeline with backend %s", args.backend)
    # 调用管线并获取结果摘要。
    result = run(
        input_path=input_path,
        out_dir=out_dir,
        backend_name=args.backend,
        language=args.language,
        write_segments=args.segments_json,
        overwrite=args.overwrite,
        num_workers=args.num_workers,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    # 输出处理统计信息。
    logger.info(
        "Finished. processed=%d skipped=%d errors=%d",
        len(result["processed"]),
        len(result["skipped"]),
        len(result["errors"]),
    )
    # 如果存在错误，则返回 1 作为退出码。
    if result["errors"]:
        logger.error("Some files failed to process. See logs above for details.")
        return 1
    # 否则返回 0 表示成功。
    return 0

# 支持通过 python -m 调用脚本。
if __name__ == "__main__":
    # 执行 main 并使用返回值作为进程退出码。
    sys.exit(main())
