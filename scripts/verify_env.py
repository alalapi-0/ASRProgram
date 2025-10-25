#!/usr/bin/env python3  # 指定解释器为 Python 3，方便跨平台执行。
"""逐行注释的环境体检脚本，确保关键依赖与工具可用。"""  # 描述脚本用途。
import sys  # 导入 sys 以获取版本信息与退出脚本。
import platform  # 导入 platform 以打印操作系统与架构信息。
import subprocess  # 导入 subprocess 用于调用外部命令。
from pathlib import Path  # 导入 Path 以便进行路径处理。
from typing import Iterable, Optional  # 导入类型注解提升可读性。
REQUIRED_PACKAGES = [  # 定义需要检测的核心 Python 包列表。
    ("faster_whisper", "faster-whisper"),  # 映射模块名与人类可读名称。
    ("numpy", "numpy"),  # numpy 模块。
    ("soundfile", "soundfile"),  # soundfile 模块。
    ("tqdm", "tqdm"),  # tqdm 模块。
    ("yaml", "PyYAML"),  # PyYAML 模块。
    ("requests", "requests"),  # requests 模块。
]  # 列表定义结束。
OPTIONAL_PACKAGES = [  # 定义可选包列表。
    ("torch", "torch"),  # torch 模块可选。
]  # 列表定义结束。
IMPORTANT_DIRECTORIES = [Path("out"), Path(".cache")]  # 需要关注的目录集合。
def print_section(title: str) -> None:
    """打印带分隔线的章节标题。"""  # 描述函数行为。
    print()  # 输出空行以分隔前后内容。
    print(f"=== {title} ===")  # 输出实际标题。
def print_kv(label: str, value: str) -> None:
    """统一格式输出键值对。"""  # 说明函数作用。
    print(f"{label}: {value}")  # 使用 f-string 打印结果。
def evaluate_python_version() -> tuple[str, str]:
    """返回 Python 版本状态与建议。"""  # 函数文档字符串。
    version = platform.python_version()  # 获取当前 Python 版本字符串。
    status = "良好"  # 默认状态为良好。
    advice = f"当前 Python 版本为 {version}，满足 3.10+ 要求。"  # 默认建议。
    if sys.version_info < (3, 10):  # 检查版本是否低于要求。
        status = "需升级"  # 更新状态。
        advice = f"检测到 Python {version} 低于 3.10，建议升级。"  # 更新建议。
    return status, advice  # 返回状态与建议。
def read_package_version(module_name: str) -> Optional[str]:
    """尝试导入模块并返回版本号，失败时返回 None。"""  # 描述函数。
    try:  # 使用 try 捕获 ImportError。
        module = __import__(module_name)  # 动态导入模块。
    except Exception:  # 捕获任何导入失败。
        return None  # 未安装则返回 None。
    version = getattr(module, "__version__", None)  # 读取 __version__ 属性。
    if version is None and module_name == "yaml":  # PyYAML 将版本信息存储在特殊位置。
        version = getattr(module, "__version__", None)  # 再次尝试读取。
    return str(version) if version is not None else "已安装，版本未知"  # 返回格式化结果。
def evaluate_packages(packages: Iterable[tuple[str, str]]) -> list[str]:
    """返回关于包状态的字符串列表。"""  # 描述函数。
    reports: list[str] = []  # 初始化结果列表。
    for module_name, display_name in packages:  # 遍历包列表。
        version = read_package_version(module_name)  # 尝试读取版本。
        if version is None:  # 若包未安装。
            reports.append(f"WARNING: {display_name} 未安装")  # 记录警告。
        else:  # 包已安装。
            reports.append(f"OK: {display_name} {version}")  # 记录成功。
    return reports  # 返回汇总列表。
def run_command(command: list[str]) -> tuple[int, str]:
    """执行外部命令并返回状态码与标准输出首行。"""  # 函数描述。
    try:  # 捕获调用异常。
        completed = subprocess.run(  # 调用 subprocess.run 执行命令。
            command,  # 传入命令列表。
            check=False,  # 不在失败时抛异常。
            stdout=subprocess.PIPE,  # 捕获标准输出。
            stderr=subprocess.STDOUT,  # 合并标准错误。
            text=True,  # 以文本模式读取输出。
        )  # run 调用结束。
    except FileNotFoundError:  # 未找到命令时。
        return 127, "命令不存在"  # 返回特殊状态。
    output_line = completed.stdout.splitlines()[0] if completed.stdout else "无输出"  # 读取首行。
    return completed.returncode, output_line  # 返回状态码与输出。
def check_tool_version(tool_name: str) -> str:
    """获取工具版本首行，若不可用则返回警告。"""  # 函数说明。
    status, line = run_command([tool_name, "-version"])  # 调用工具的 -version。
    if status == 0:  # 成功时。
        return line  # 返回首行。
    if status == 127:  # 命令不存在。
        return f"WARNING: 未检测到 {tool_name}"  # 返回警告。
    return f"WARNING: 无法获取 {tool_name} 版本（退出码 {status}）"  # 其他错误情况。
def evaluate_directory(path: Path) -> tuple[str, str]:
    """返回目录状态与建议。"""  # 函数说明。
    if path.exists():  # 若目录存在。
        if path.is_dir():  # 确认路径为目录。
            if os_access_write(path):  # 检查是否可写。
                return "存在且可写", "无需操作"  # 返回正常状态。
            return "存在但不可写", "WARNING: 请调整权限"  # 返回警告状态。
        return "路径存在但非目录", "WARNING: 请删除后重新创建"  # 路径类型异常。
    return "未找到", "执行安装脚本时将自动创建"  # 目录不存在的情况。
def os_access_write(path: Path) -> bool:
    """判断当前用户对目录是否拥有写权限。"""  # 函数说明。
    import os  # 延迟导入 os 以减少脚本加载开销。
    return os.access(path, os.W_OK)  # 使用 os.access 判断可写性。
def main() -> None:
    """脚本主入口，按章节输出环境体检结果。"""  # 函数说明。
    print("ASRProgram 环境体检报告（Round 5）")  # 打印总标题。
    print_kv("Python 解释器", sys.executable)  # 输出解释器路径。
    print_kv("Python 版本", platform.python_version())  # 输出 Python 版本。
    py_status, py_advice = evaluate_python_version()  # 调用函数获取 Python 状态。
    print_kv("Python 状态", py_status)  # 打印状态。
    print_kv("Python 建议", py_advice)  # 打印建议。
    print_section("核心依赖检测")  # 打印核心依赖标题。
    for report in evaluate_packages(REQUIRED_PACKAGES):  # 遍历检测结果。
        print(report)  # 输出每一项。
    print_section("可选组件检测")  # 打印可选组件标题。
    for report in evaluate_packages(OPTIONAL_PACKAGES):  # 遍历可选包。
        print(report)  # 输出结果。
    print_section("多媒体工具版本")  # 打印工具检测标题。
    print_kv("ffmpeg", check_tool_version("ffmpeg"))  # 输出 ffmpeg 版本信息。
    print_kv("ffprobe", check_tool_version("ffprobe"))  # 输出 ffprobe 版本信息。
    print_section("目录可写性")  # 打印目录检查标题。
    for directory in IMPORTANT_DIRECTORIES:  # 遍历目录列表。
        status, advice = evaluate_directory(directory)  # 获取目录状态。
        print_kv(f"{directory} 状态", status)  # 输出状态。
        print_kv(f"{directory} 建议", advice)  # 输出建议。
    print_section("环境小结")  # 打印总结标题。
    if any(report.startswith("WARNING") for report in evaluate_packages(REQUIRED_PACKAGES)):
        print("WARNING: 仍有必需依赖缺失，请重新运行安装脚本。")  # 若有必需依赖缺失则警告。
    else:
        print("OK: 核心依赖已就绪。")  # 所有必需依赖已安装。
    optional_reports = evaluate_packages(OPTIONAL_PACKAGES)  # 再次检查可选包。
    if any(report.startswith("WARNING") for report in optional_reports):  # 若可选包缺失。
        print("INFO: 可选组件缺失不会阻塞流程，但建议参考文档补齐。")  # 输出提示。
    else:
        print("OK: 可选组件可用。")  # 所有可选组件就绪。
    print("OK: 验证结束，退出码始终为 0。")  # 提醒脚本会以 0 退出。
if __name__ == "__main__":  # 当脚本以主程序运行时。
    main()  # 调用主函数。
    sys.exit(0)  # 明确以 0 退出。
