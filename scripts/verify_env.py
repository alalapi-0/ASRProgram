#!/usr/bin/env python3
"""逐行注释的环境自检脚本，输出当前系统的可读体检报告。"""
# 导入 sys 模块以获取 Python 版本与解释器路径。
import sys
# 导入 platform 模块以输出系统与架构信息。
import platform
# 导入 shutil 模块用于在 PATH 中寻找可执行文件。
import shutil
# 导入 pathlib.Path 方便处理路径与可写性检查。
from pathlib import Path
# 定义常量，描述需要重点检查的目录名称。
IMPORTANT_DIRECTORIES = ["out", ".cache"]  # 需要重点检查的目录列表。
# 定义函数格式化标题，方便在输出时突出每个检查项。
def print_section(title: str) -> None:
    """打印带有分隔线的标题，提升可读性。"""
    # 打印空行用于分隔前后内容。
    print()  # 输出空行用于分隔标题与前一个模块。
    # 打印标题本身，让用户知道接下来是哪个模块的结果。
    print(f"=== {title} ===")  # 输出标题并带上分隔标识。
# 定义函数用于打印键值对形式的检查结果。
def print_item(label: str, value: str) -> None:
    """统一格式输出检查项内容。"""
    # 使用 f-string 打印，例如 "Python 版本: 3.11.4"。
    print(f"{label}: {value}")  # 输出格式化后的键值对。
# 定义函数检查 Python 版本是否满足最低要求。
def evaluate_python_version() -> tuple[str, str]:
    """返回版本状态与建议信息。"""
    # 从 sys.version_info 中组合出主版本与次版本信息。
    version_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"  # 拼接当前 Python 版本号。
    # 默认标记为通过，建议为空。
    status = "良好"  # 默认状态为良好。
    recommendation = f"已满足最低版本要求（当前 {version_str}）。"  # 默认建议为无需操作。
    # 如果主版本小于 3 或次版本小于 10，则视为需升级。
    if sys.version_info < (3, 10):
        # 更新状态为需升级。
        status = "需升级"  # 若版本低于阈值则标记为需升级。
        # 给出明确建议，提示用户未来需要升级。
        recommendation = f"检测到 Python {version_str} 低于 3.10，建议升级到 3.10+。"  # 输出升级建议。
    # 返回组装好的元组，供后续打印。
    return status, recommendation
# 定义函数检查 pip 是否可用，并返回版本信息。
def evaluate_pip() -> str:
    """尝试导入 pip 并获取版本号，若失败则提示未找到。"""
    # 使用 try/except 捕获导入失败的情况。
    try:
        # 延迟导入 pip 以避免在缺失时抛出异常。
        import pip  # type: ignore
        # 成功导入则返回版本号。
        return pip.__version__  # type: ignore[attr-defined]
    except Exception:
        # 若导入失败则返回友好提示。
        return "未检测到 pip 模块"
# 定义函数检查 PATH 中是否存在给定工具。
def evaluate_tool(tool_name: str) -> str:
    """返回工具的首个命中路径或未找到提示。"""
    # 使用 shutil.which 在 PATH 中查找工具。
    tool_path = shutil.which(tool_name)  # 在 PATH 中查找工具。
    # 如果找到则返回具体路径。
    if tool_path:  # 检测到有效路径。
        return tool_path  # 返回命中路径。
    # 若未找到则返回提示信息。
    return "未找到"  # 返回未找到的提示文本。
# 定义函数检查目录存在与可写性。
def evaluate_directory(path: Path) -> tuple[str, str]:
    """返回目录状态与建议。"""
    # 如果目录存在。
    if path.exists():
        # 若目录存在但不可写，给出需调整权限的建议。
        if not os_access_write(path):
            return "存在但不可写", "请调整权限以确保后续流程可写入。"
        # 否则表示正常。
        return "存在且可写", "无需操作。"
    # 若目录不存在，则提示未来会自动创建。
    return "未找到", "未来执行安装脚本时将自动创建。"
# 定义辅助函数，使用 os.access 检查可写性。
def os_access_write(path: Path) -> bool:
    """判断当前用户对指定路径是否具备写权限。"""
    # 使用 path.resolve() 获取绝对路径后调用 os.access。
    return path.resolve().exists() and path.resolve().is_dir() and os_access(path.resolve())  # 综合判断目录存在性与写权限。
# 定义实际调用 os.access 的函数，以保持逐行注释结构。
def os_access(path: Path) -> bool:
    """封装 os.access 调用逻辑。"""
    # 延迟导入 os 模块以靠近实际使用位置。
    import os
    # 使用 os.access 判断是否可写。
    return os.access(path, os.W_OK)  # 返回是否拥有写权限。
# 定义主函数，组织整体输出流程。
def main() -> None:
    """执行环境体检并输出人类可读的报告。"""
    # 打印总标题，提醒用户这是 Round 2 的体检输出。
    print("ASRProgram 环境体检报告（Round 2 演练模式）")
    # 打印 Python 解释器路径。
    print_item("Python 解释器", sys.executable)
    # 打印 Python 版本字符串。
    print_item("Python 版本", platform.python_version())
    # 调用 evaluate_python_version 获取状态与建议。
    py_status, py_recommendation = evaluate_python_version()
    # 打印 Python 状态。
    print_item("Python 状态", py_status)
    # 打印 Python 建议。
    print_item("Python 建议", py_recommendation)
    # 打印空行用于分隔。
    print()
    # 打印 pip 版本信息。
    print_item("pip 版本", evaluate_pip())
    # 打印平台信息标题。
    print_section("平台信息")
    # 打印系统类型。
    print_item("操作系统", platform.system())
    # 打印系统版本。
    print_item("系统版本", platform.version())
    # 打印架构。
    print_item("处理器架构", platform.machine())
    # 打印工具检测标题。
    print_section("多媒体工具检测")
    # 打印 ffmpeg 路径或未找到。
    print_item("ffmpeg", evaluate_tool("ffmpeg"))
    # 打印 ffprobe 路径或未找到。
    print_item("ffprobe", evaluate_tool("ffprobe"))
    # 打印目录检查标题。
    print_section("目录可写性")
    # 遍历关键目录列表进行检查。
    for directory in IMPORTANT_DIRECTORIES:
        # 将字符串转换为 Path 对象。
        path = Path(directory)
        # 获取状态与建议。
        status, recommendation = evaluate_directory(path)
        # 打印目录状态。
        print_item(f"{directory} 状态", status)
        # 打印建议内容。
        print_item(f"{directory} 建议", recommendation)
    # 打印下一步建议标题。
    print_section("下一步建议")
    # 根据 ffmpeg 检测结果给出提示。
    if evaluate_tool("ffmpeg") == "未找到":
        print("- 未找到 ffmpeg：后续可将 use-system-ffmpeg 设为 false，由脚本按平台下载。")
    else:
        print("- 已检测到 ffmpeg：后续安装可复用现有系统版本。")
    # 如果 Python 状态需要升级，则强调提醒。
    if py_status == "需升级":
        print("- 重要提示：请尽快升级 Python 至 3.10 或更高版本。")
    else:
        print("- Python 版本符合要求，可直接继续后续轮次的真实安装。")
    # 在建议结尾提供通用说明。
    print("- 本轮脚本为演练模式，不执行任何真实安装或下载操作。")
# 在作为脚本直接运行时执行 main 函数。
if __name__ == "__main__":
    # 调用 main 函数执行体检。
    main()
    # 始终以状态码 0 结束，确保不阻塞后续流程。
    sys.exit(0)
