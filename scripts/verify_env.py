#!/usr/bin/env python3  # 指定解释器为 Python 3，方便跨平台执行。
"""逐行注释的环境体检脚本，Round 10 增强 whisper.cpp 检测。"""  # 描述脚本用途。
import argparse  # 解析命令行参数。
import platform  # 获取平台与 Python 版本信息。
import inspect  # 检查 faster-whisper API 是否支持词级参数。
import subprocess  # 调用外部命令读取工具版本。
import sys  # 控制脚本退出码并访问解释器信息。
from pathlib import Path  # 优雅地处理路径。
from typing import Dict, Iterable, List, Optional, Tuple  # 提供类型注解。

import yaml  # 读取默认配置文件。
from src.utils.config import load_and_merge_config  # 导入配置加载器以输出 profile 与路径概览。

REQUIRED_PACKAGES = [  # 定义必须存在的 Python 包。
    ("faster_whisper", "faster-whisper"),  # faster-whisper 是核心依赖。
    ("numpy", "numpy"),  # 数值运算库。
    ("soundfile", "soundfile"),  # 音频读写库。
    ("tqdm", "tqdm"),  # 进度条库。
    ("yaml", "PyYAML"),  # 配置解析库。
    ("requests", "requests"),  # HTTP 请求库。
]  # 必需包列表结束。
OPTIONAL_PACKAGES = [  # 可选包列表。
    ("torch", "torch"),  # faster-whisper 可结合 torch 使用 GPU。
]  # 可选包列表结束。
FASTER_WHISPER_FILES = ["config.json", "model.bin", "tokenizer.json", "vocabulary.json"]  # faster-whisper 所需文件名。
FASTER_WHISPER_SIZE_HINT = {  # 不同规格模型的预估总大小（字节）。
    "tiny": 70 * 1024 * 1024,  # 约 70MB。
    "base": 130 * 1024 * 1024,  # 约 130MB。
    "small": 430 * 1024 * 1024,  # 约 430MB。
    "medium": 1_400 * 1024 * 1024,  # 约 1.4GB。
    "large-v3": 3_000 * 1024 * 1024,  # 约 3GB。
}  # 大小参考结束。
WHISPER_CPP_SIZE_HINT = {  # whisper.cpp 常见模型的体积预估。
    "tiny": 75 * 1024 * 1024,  # ggml-tiny 约 75MB。
    "base": 145 * 1024 * 1024,  # ggml-base 约 145MB。
    "small": 480 * 1024 * 1024,  # ggml-small 约 480MB。
    "medium": 1_500 * 1024 * 1024,  # ggml-medium 约 1.5GB。
    "large-v3": 3_050 * 1024 * 1024,  # ggml-large-v3 约 3.05GB。
}  # whisper.cpp 体积参考结束。


def print_section(title: str) -> None:
    """打印带分隔线的章节标题。"""  # 函数说明。
    print()  # 输出空行分隔章节。
    print(f"=== {title} ===")  # 输出标题文本。


def print_kv(label: str, value: str) -> None:
    """统一格式输出键值对。"""  # 函数说明。
    print(f"{label}: {value}")  # 使用 f-string 打印。


def load_defaults() -> Dict[str, object]:
    """从 config/default.yaml 读取默认配置。"""  # 函数说明。
    config_path = Path(__file__).resolve().parent.parent / "config" / "default.yaml"  # 计算配置文件路径。
    with config_path.open("r", encoding="utf-8") as handle:  # 打开配置文件。
        return yaml.safe_load(handle)  # 解析 YAML 并返回字典。


def build_parser(defaults: Dict[str, object]) -> argparse.ArgumentParser:
    """创建命令行解析器以支持自定义模型参数。"""  # 函数说明。
    parser = argparse.ArgumentParser(description="检查依赖、模型缓存与 faster-whisper/whisper.cpp 可用性。")  # 创建解析器并设置描述。
    backend_default = defaults.get("backend", {}).get("default", "faster-whisper")  # 读取后端默认值。
    model_default = defaults.get("model", {}).get("default", "medium")  # 读取模型默认值。
    cache_default = defaults.get("cache_dir", ".cache/")  # 读取缓存目录默认值。
    models_default = defaults.get("models_dir", "~/.cache/asrprogram/models/")  # 读取模型目录默认值。
    whisper_defaults = defaults.get("runtime", {}).get("whisper_cpp", {})  # 读取 whisper.cpp 默认配置。
    profile_default = defaults.get("meta", {}).get("profile")  # 读取默认 profile，用于配置概览。
    parser.add_argument("--backend", default=backend_default, help="目标模型后端。")  # 后端参数。
    parser.add_argument("--model", default=model_default, help="目标模型规格。")  # 模型参数。
    parser.add_argument("--models-dir", default=models_default, help="模型缓存主目录。")  # 模型目录参数。
    parser.add_argument("--cache-dir", default=cache_default, help="通用缓存目录。")  # 缓存目录参数。
    parser.add_argument("--whispercpp-exe", default=whisper_defaults.get("executable_path", ""), help="whisper.cpp 可执行文件路径。")  # 可执行参数。
    parser.add_argument("--whispercpp-model", default=whisper_defaults.get("model_path", ""), help="whisper.cpp GGML/GGUF 模型路径。")  # 模型路径参数。
    parser.add_argument("--profile", default=profile_default, help="可选 profile 名称，用于演示配置覆盖效果。")  # 新增 profile 参数。
    return parser  # 返回解析器。


def evaluate_python_version() -> Tuple[str, str]:
    """返回 Python 版本状态与建议。"""  # 函数说明。
    version = platform.python_version()  # 获取 Python 版本字符串。
    status = "良好"  # 默认状态。
    advice = f"当前 Python 版本为 {version}，满足 3.10+ 要求。"  # 默认建议。
    if sys.version_info < (3, 10):  # 若版本过低。
        status = "需升级"  # 更新状态。
        advice = f"检测到 Python {version} 低于 3.10，建议升级。"  # 更新建议。
    return status, advice  # 返回结果。


def read_package_version(module_name: str) -> Optional[str]:
    """尝试导入模块并返回版本号，失败时返回 None。"""  # 函数说明。
    try:  # 捕获导入异常。
        module = __import__(module_name)  # 动态导入模块。
    except Exception:  # 导入失败时。
        return None  # 返回 None。
    version = getattr(module, "__version__", None)  # 读取 __version__ 属性。
    if version is None and module_name == "yaml":  # 针对 PyYAML 的兼容逻辑。
        version = getattr(module, "__version__", None)  # 再次尝试读取版本。
    return str(version) if version is not None else "已安装，版本未知"  # 格式化返回值。


def evaluate_packages(packages: Iterable[Tuple[str, str]]) -> List[str]:
    """检查包是否已安装并返回状态字符串。"""  # 函数说明。
    reports: List[str] = []  # 初始化结果列表。
    for module_name, display_name in packages:  # 遍历包列表。
        version = read_package_version(module_name)  # 获取版本。
        if version is None:  # 未安装时。
            reports.append(f"WARNING: {display_name} 未安装")  # 添加警告。
        else:  # 已安装时。
            reports.append(f"OK: {display_name} {version}")  # 添加成功信息。
    return reports  # 返回列表。


def run_command(command: List[str]) -> Tuple[int, str]:
    """执行外部命令并返回状态码与首行输出。"""  # 函数说明。
    try:  # 捕获命令执行异常。
        completed = subprocess.run(  # 调用 subprocess。
            command,  # 命令列表。
            check=False,  # 不在失败时抛异常。
            stdout=subprocess.PIPE,  # 捕获标准输出。
            stderr=subprocess.STDOUT,  # 合并标准错误。
            text=True,  # 文本模式。
        )  # run 调用结束。
    except FileNotFoundError:  # 未找到命令时。
        return 127, "命令不存在"  # 返回特殊状态。
    output_line = completed.stdout.splitlines()[0] if completed.stdout else "无输出"  # 读取首行。
    return completed.returncode, output_line  # 返回状态码与输出。


def check_tool_version(tool_name: str) -> str:
    """获取工具版本信息。"""  # 函数说明。
    status, line = run_command([tool_name, "-version"])  # 执行工具的 -version。
    if status == 0:  # 成功时。
        return line  # 返回输出。
    if status == 127:  # 未找到命令时。
        return f"WARNING: 未检测到 {tool_name}"  # 返回警告。
    return f"WARNING: 无法获取 {tool_name} 版本（退出码 {status}）"  # 返回其他错误信息。


def os_access_write(path: Path) -> bool:
    """判断当前用户对目录是否可写。"""  # 函数说明。
    import os  # 延迟导入 os 模块。
    return os.access(path, os.W_OK)  # 返回可写性判断。


def evaluate_directory(path: Path) -> Tuple[str, str]:
    """返回目录状态与建议。"""  # 函数说明。
    if path.exists():  # 若路径存在。
        if path.is_dir():  # 且为目录。
            if os_access_write(path):  # 若可写。
                return "存在且可写", "无需操作"  # 返回正常状态。
            return "存在但不可写", "WARNING: 请调整权限"  # 返回警告。
        return "路径存在但非目录", "WARNING: 请删除后重新创建"  # 类型异常。
    return "未找到", "执行安装脚本时将自动创建"  # 不存在时提示。


def check_model_status(
    backend: str,
    model: str,
    models_dir: Path,
    whisper_model_override: Optional[str] = None,
) -> Tuple[str, Path, int, List[str]]:
    """检查指定后端模型是否就绪，返回状态字符串、路径、大小和缺失文件列表。"""  # 函数说明。
    backend_lower = backend.lower()  # 统一用小写目录名。
    target_dir = models_dir / backend_lower / model  # 计算模型目录。
    missing: List[str] = []  # 初始化缺失文件列表。
    total_size = 0  # 初始化总体积。
    if backend_lower == "whisper.cpp":  # 当目标为 whisper.cpp 时。
        if whisper_model_override:  # 若提供了直接的模型文件路径。
            override_path = Path(whisper_model_override).expanduser()  # 展开路径。
            if not override_path.exists():  # 文件不存在。
                return "MISSING", override_path, 0, []  # 返回缺失状态。
            if not override_path.is_file():  # 不是文件。
                return "INVALID", override_path, 0, []  # 返回无效状态。
            size = override_path.stat().st_size  # 读取文件大小。
            hint = WHISPER_CPP_SIZE_HINT.get(model, 0)  # 获取体积参考。
            if hint and size < hint * 0.6:  # 当体积明显小于预期。
                return "SMALL", override_path, size, []  # 返回过小状态。
            return "READY", override_path, size, []  # 返回就绪。
        filename_hint = {
            "tiny": "ggml-tiny.bin",
            "base": "ggml-base.bin",
            "small": "ggml-small.bin",
            "medium": "ggml-medium.bin",
            "large-v3": "ggml-large-v3.bin",
        }.get(model, "")  # 根据模型名称推断文件名。
        if filename_hint:
            file_path = target_dir / filename_hint  # 拼接默认路径。
            if not file_path.exists():  # 文件缺失。
                return "MISSING", file_path, 0, []  # 返回缺失状态。
            size = file_path.stat().st_size  # 读取大小。
            hint = WHISPER_CPP_SIZE_HINT.get(model, 0)  # 获取体积参考。
            if hint and size < hint * 0.6:  # 小于预期体积。
                return "SMALL", file_path, size, []  # 返回过小状态。
            return "READY", file_path, size, []  # 返回就绪状态。
        return "UNKNOWN BACKEND", target_dir, 0, []  # 未知模型名称。
    if backend_lower != "faster-whisper":  # 对其他后端暂未实现。
        return "UNKNOWN BACKEND", target_dir, total_size, missing  # 返回占位状态。
    for filename in FASTER_WHISPER_FILES:  # 遍历必需文件。
        file_path = target_dir / filename  # 构造文件路径。
        if not file_path.exists():  # 若文件缺失。
            missing.append(filename)  # 记录缺失文件。
            continue  # 检查下一个文件。
        total_size += file_path.stat().st_size  # 累加文件大小。
    expected_size = FASTER_WHISPER_SIZE_HINT.get(model, 0)  # 获取预估体积。
    if missing:  # 若存在缺失文件。
        return "MISSING", target_dir, total_size, missing  # 返回缺失状态。
    if total_size < expected_size:  # 若总体积低于预期。
        return "INCOMPLETE", target_dir, total_size, []  # 返回未完成状态。
    return "READY", target_dir, total_size, []  # 所有条件满足时返回就绪。


def format_bytes(size: int) -> str:
    """将字节数格式化为易读文本。"""  # 函数说明。
    if size <= 0:  # 非正值直接返回。
        return "0B"  # 返回 0B。
    units = ["B", "KB", "MB", "GB", "TB"]  # 定义单位列表。
    value = float(size)  # 将数值转为浮点数。
    for unit in units:  # 遍历单位。
        if value < 1024 or unit == units[-1]:  # 当值小于 1024 或到达最后单位。
            return f"{value:.2f}{unit}"  # 返回格式化字符串。
        value /= 1024  # 否则继续换算。
    return f"{value:.2f}TB"  # 理论上不会达到此行。


def import_faster_whisper() -> Tuple[Optional[object], Optional[str]]:
    """尝试导入 faster_whisper 并返回模块与版本。"""  # 函数说明。
    try:  # 捕获导入异常。
        import faster_whisper  # type: ignore  # 导入模块。
    except Exception:  # 导入失败时。
        return None, None  # 返回空值。
    version = getattr(faster_whisper, "__version__", "未知版本")  # 读取版本。
    return faster_whisper, str(version)  # 返回模块对象与版本字符串。


def try_lightweight_model_load(module: object, model_path: Path) -> Tuple[bool, str]:
    """若模型存在则尝试快速构造 WhisperModel，用于验证可加载性。"""  # 函数说明。
    try:  # 捕获潜在加载异常。
        WhisperModel = getattr(module, "WhisperModel")  # 从模块获取 WhisperModel 类。
    except AttributeError:  # 模块不含 WhisperModel。
        return False, "faster_whisper 缺少 WhisperModel 类"  # 返回失败信息。
    try:  # 尝试实例化模型。
        model = WhisperModel(str(model_path), device="auto", compute_type="auto")  # 轻量加载模型。
        del model  # 立即释放对象，避免占用显存或内存。
    except Exception as exc:  # noqa: BLE001
        return False, f"WARNING: 模型加载失败 -> {exc}"  # 返回失败原因。
    return True, "OK: 模型加载测试通过"  # 返回成功信息。


def check_word_timestamp_support(module: object) -> str:
    """检测 faster-whisper 是否接受 word_timestamps 参数并返回说明文本。"""  # 函数说明。
    try:  # 捕获属性缺失或签名解析异常。
        WhisperModel = getattr(module, "WhisperModel")  # 获取模型类。
        signature = inspect.signature(WhisperModel.transcribe)  # 读取 transcribe 的参数签名。
    except Exception:  # 任意异常均视为未知状态。
        return "WARNING: 无法判断 word_timestamps 支持，请手动查阅 faster-whisper 版本。"  # 返回警告。
    if "word_timestamps" in signature.parameters:  # 若签名包含目标参数。
        return "OK: faster-whisper 支持 word_timestamps，词级时间戳已启用。"  # 返回肯定信息。
    return "WARNING: 当前 faster-whisper 不接受 word_timestamps，请升级至 0.9+。"  # 返回缺失提示。


def evaluate_whispercpp_executable(path_str: str) -> Tuple[str, str, str, str]:
    """评估 whisper.cpp 可执行文件状态并返回状态、建议、版本与路径。"""  # 函数说明。
    if not path_str:  # 未提供路径时。
        return "MISSING", "WARNING: 未提供 whisper.cpp 可执行文件路径。", "unknown", ""  # 返回缺失状态。
    exe_path = Path(path_str).expanduser()  # 展开用户目录。
    if not exe_path.exists():  # 文件不存在时。
        return "MISSING", f"WARNING: 未找到 whisper.cpp 可执行文件: {exe_path}", "unknown", str(exe_path)  # 返回缺失。
    if not exe_path.is_file():  # 指定路径不是普通文件。
        return "INVALID", f"WARNING: 指定路径不是可执行文件: {exe_path}", "unknown", str(exe_path)  # 返回无效状态。
    import os  # 延迟导入 os 检查执行权限。

    if not os.access(exe_path, os.X_OK):  # 缺少执行权限时。
        return "NO PERMISSION", f"WARNING: whisper.cpp 可执行文件缺少执行权限: {exe_path}", "unknown", str(exe_path)  # 返回权限警告。
    version_line = "unknown"  # 默认版本信息。
    advice = "WARNING: 无法通过 --version/-h 获取版本，请手动执行检查。"  # 默认建议。
    for flag in ("--version", "-h"):  # 依次尝试常见参数。
        status, line = run_command([str(exe_path), flag])  # 执行命令。
        if status == 0 and line:  # 成功获取输出。
            version_line = line.strip()  # 记录首行。
            advice = "OK: whisper.cpp 可执行文件可用。"  # 更新建议。
            break  # 结束循环。
    return "READY", advice, version_line, str(exe_path)  # 返回评估结果。


def evaluate_whispercpp_model(path_str: str, model_name: str) -> Tuple[str, str, str, int]:
    """评估 whisper.cpp 模型文件状态并返回状态、建议、路径与大小。"""  # 函数说明。
    if not path_str:  # 未提供模型路径时。
        return "MISSING", "INFO: 未提供 whisper.cpp 模型路径，可在需要时补充。", "", 0  # 返回缺失状态。
    model_path = Path(path_str).expanduser()  # 展开路径。
    if not model_path.exists():  # 文件不存在。
        return "MISSING", f"WARNING: 未找到 whisper.cpp 模型文件: {model_path}", str(model_path), 0  # 返回缺失状态。
    if not model_path.is_file():  # 指定路径不是文件。
        return "INVALID", f"WARNING: 指定路径不是模型文件: {model_path}", str(model_path), 0  # 返回无效状态。
    size = model_path.stat().st_size  # 读取文件大小。
    hint = WHISPER_CPP_SIZE_HINT.get(model_name, 0)  # 获取参考体积。
    if hint and size < hint * 0.6:  # 当体积明显小于参考值。
        reference = format_bytes(hint)  # 计算参考体积文本。
        return "SMALL", f"WARNING: 模型体积 {format_bytes(size)} 明显小于参考值 {reference}，请确认是否为量化或下载完整。", str(model_path), size  # 返回警告。
    return "READY", "OK: whisper.cpp 模型文件可用。", str(model_path), size  # 返回成功状态。


def main() -> None:
    """脚本主入口，输出完整体检报告。"""  # 函数说明。
    defaults = load_defaults()  # 读取默认配置。
    parser = build_parser(defaults)  # 构建解析器。
    args = parser.parse_args()  # 解析命令行参数。
    models_dir = Path(args.models_dir).expanduser().resolve()  # 解析模型目录。
    cache_dir = Path(args.cache_dir).expanduser().resolve()  # 解析缓存目录。
    cli_overrides: Dict[str, object] = {  # 构造传入配置加载器的覆盖层。
        "models_dir": str(models_dir),  # 将模型目录写入配置树。
        "cache_dir": str(cache_dir),  # 将缓存目录写入配置树。
    }
    runtime_overrides: Dict[str, object] = {}  # 初始化运行时覆盖字典。
    if args.backend:  # 若提供后端参数。
        runtime_overrides["backend"] = args.backend  # 将后端写入 runtime。
    whisper_overrides: Dict[str, object] = {}  # 构造 whisper.cpp 子配置覆盖。
    if args.whispercpp_exe:  # 若提供可执行路径。
        whisper_overrides["executable_path"] = args.whispercpp_exe  # 写入可执行路径。
    if args.whispercpp_model:  # 若提供模型路径。
        whisper_overrides["model_path"] = args.whispercpp_model  # 写入模型路径。
    if whisper_overrides:  # 当存在 whisper.cpp 覆盖时。
        runtime_overrides["whisper_cpp"] = whisper_overrides  # 嵌入到 runtime。
    if runtime_overrides:  # 若 runtime 覆盖非空。
        cli_overrides["runtime"] = runtime_overrides  # 写入顶层覆盖。
    try:  # 尝试加载并合并配置。
        bundle = load_and_merge_config(
            cli_overrides=cli_overrides,  # 注入 CLI 覆盖。
            profile_name=args.profile,  # 应用用户选择的 profile。
        )
    except Exception as exc:  # noqa: BLE001  # 捕获配置加载期间的任何异常。
        bundle = None  # 若失败则置空。
        print_section("配置快照")  # 提示配置概览章节。
        print(f"WARNING: 无法解析配置 -> {exc}")  # 输出错误信息。
    else:  # 配置加载成功。
        print_section("配置快照")  # 打印配置概览标题。
        runtime_cfg = bundle.config.get("runtime", {}) if isinstance(bundle.config, dict) else {}  # 读取运行时配置。
        whisper_cfg = runtime_cfg.get("whisper_cpp", {}) if isinstance(runtime_cfg, dict) else {}  # 读取 whisper.cpp 子树。
        print_kv("PROFILE", bundle.profile or "<default>")  # 输出当前 profile。
        print_kv("BACKEND", runtime_cfg.get("backend", "unknown"))  # 输出运行时后端。
        print_kv("DEVICE", runtime_cfg.get("device", "auto"))  # 输出设备信息。
        print_kv("CACHE DIR", bundle.config.get("cache_dir", ""))  # 输出缓存目录。
        print_kv("MODELS DIR", bundle.config.get("models_dir", ""))  # 输出模型目录。
        print_kv("WHISPER.EXE", whisper_cfg.get("executable_path", ""))  # 输出 whisper.cpp 可执行路径。
        print_kv("WHISPER.MODEL", whisper_cfg.get("model_path", ""))  # 输出 whisper.cpp 模型路径。
    print("ASRProgram 环境体检报告（Round 10）")  # 打印标题。
    print_kv("Python 解释器", sys.executable)  # 输出解释器路径。
    print_kv("Python 版本", platform.python_version())  # 输出 Python 版本。
    py_status, py_advice = evaluate_python_version()  # 获取 Python 状态。
    print_kv("Python 状态", py_status)  # 输出状态。
    print_kv("Python 建议", py_advice)  # 输出建议。
    print_section("核心依赖检测")  # 打印依赖检测标题。
    required_reports = evaluate_packages(REQUIRED_PACKAGES)  # 检查必需包。
    for report in required_reports:  # 遍历结果。
        print(report)  # 输出每项。
    print_section("可选组件检测")  # 打印可选组件标题。
    optional_reports = evaluate_packages(OPTIONAL_PACKAGES)  # 检查可选包。
    for report in optional_reports:  # 遍历结果。
        print(report)  # 输出每项。
    module, fw_version = import_faster_whisper()  # 试图导入 faster-whisper。
    print_section("faster-whisper 状态")  # 打印 faster-whisper 信息标题。
    if module is None:  # 导入失败时。
        print("WARNING: 无法导入 faster-whisper，请运行 scripts/setup.sh")  # 提示安装依赖。
    else:  # 导入成功时。
        print_kv("faster-whisper 版本", fw_version or "未知")  # 输出版本。
        print(check_word_timestamp_support(module))  # 输出词级时间戳支持状态。
    print_section("多媒体工具版本")  # 打印工具检测标题。
    print_kv("ffmpeg", check_tool_version("ffmpeg"))  # 输出 ffmpeg 版本。
    print_kv("ffprobe", check_tool_version("ffprobe"))  # 输出 ffprobe 版本。
    print_section("目录可写性")  # 打印目录可写性标题。
    directories = [Path("out"), Path(".cache"), cache_dir, models_dir]  # 汇总需要关注的目录。
    seen: set[Path] = set()  # 使用集合去重。
    for directory in directories:  # 遍历目录。
        normalized = directory  # 暂存标准化路径。
        if normalized in seen:  # 若已处理则跳过。
            continue  # 继续下一个。
        seen.add(normalized)  # 记录已处理。
        status, advice = evaluate_directory(normalized)  # 获取状态。
        print_kv(f"{normalized} 状态", status)  # 输出状态。
        print_kv(f"{normalized} 建议", advice)  # 输出建议。
    print_section("模型缓存状态")  # 打印模型状态标题。
    override_path = args.whispercpp_model if args.backend.lower() == "whisper.cpp" else None  # 针对 whisper.cpp 的直接模型路径。
    model_status, model_path, model_size, missing_files = check_model_status(
        args.backend,
        args.model,
        models_dir,
        whisper_model_override=override_path,
    )  # 检查模型。
    print_kv("模型后端", args.backend)  # 输出后端名称。
    print_kv("模型名称", args.model)  # 输出模型名称。
    print_kv("目标路径", str(model_path))  # 输出模型目录。
    if model_status == "READY":  # 模型就绪时。
        print_kv("MODEL STATUS", "READY")  # 输出就绪状态。
        print_kv("SIZE", format_bytes(model_size))  # 输出模型大小。
        if module is not None:  # 若 faster-whisper 可导入。
            ok, message = try_lightweight_model_load(module, model_path)  # 进行轻量加载测试。
            print(message)  # 输出加载结果。
        else:  # 模块缺失无法测试。
            print("WARNING: faster-whisper 未安装，跳过模型加载测试。")  # 输出警告。
    elif model_status == "UNKNOWN BACKEND":  # 未知后端时。
        print_kv("MODEL STATUS", "UNKNOWN")  # 输出未知状态。
        print("WARNING: verify_env.py 暂未内置该后端的完整校验逻辑。")  # 打印警告。
    else:  # 模型缺失或不完整。
        print_kv("MODEL STATUS", model_status)  # 输出状态。
        print_kv("SIZE", format_bytes(model_size))  # 输出已存在大小。
        if missing_files:  # 若有缺失文件。
            print(f"WARNING: 缺失文件 {', '.join(missing_files)}")  # 输出缺失列表。
        else:  # 文件齐全但体积不足。
            print("WARNING: 模型体积低于预估值，可能下载不完整，建议重新执行下载脚本。")  # 输出提示。
        print("HINT: 可运行 scripts/download_model.py --force 重新下载，或手动放置文件后再次验证。")  # 提供提示。
    print_section("whisper.cpp 状态")  # 打印 whisper.cpp 体检标题。
    exec_status, exec_advice, exec_version, exec_path = evaluate_whispercpp_executable(args.whispercpp_exe)  # 评估可执行文件。
    model_status_cpp, model_advice, model_path_cpp, model_size_cpp = evaluate_whispercpp_model(args.whispercpp_model, args.model)  # 评估模型文件。
    print_kv("whisper.cpp 可执行", exec_path or "<未提供>")  # 输出可执行路径。
    print_kv("EXEC STATUS", exec_status)  # 输出状态。
    print_kv("EXEC VERSION", exec_version)  # 输出版本。
    if exec_advice:  # 若存在建议文本。
        print(exec_advice)  # 输出建议。
    print_kv("whisper.cpp 模型", model_path_cpp or "<未提供>")  # 输出模型路径。
    print_kv("MODEL STATUS", model_status_cpp)  # 输出模型状态。
    if model_size_cpp:  # 当存在文件大小时。
        print_kv("MODEL SIZE", format_bytes(model_size_cpp))  # 输出格式化大小。
    if model_advice:  # 若存在建议文本。
        print(model_advice)  # 输出建议。
    print_section("环境小结")  # 打印总结标题。
    if any(report.startswith("WARNING") for report in required_reports):  # 判断必需包是否缺失。
        print("WARNING: 仍有必需依赖缺失，请重新运行安装脚本。")  # 输出警告。
    else:  # 所有必需包已就绪。
        print("OK: 核心依赖已就绪。")  # 输出成功。
    if any(report.startswith("WARNING") for report in optional_reports):  # 判断可选包状态。
        print("INFO: 可选组件缺失不会阻塞流程，但建议参考文档补齐。")  # 输出提示。
    else:  # 可选包也已安装。
        print("OK: 可选组件可用。")  # 输出成功。
    if model_status != "READY":  # 若模型未就绪。
        print("WARNING: 模型尚未准备完成，后续运行前请先补齐。")  # 输出警告。
    else:  # 模型就绪。
        print("OK: 模型缓存就绪。")  # 输出确认。
    if exec_status != "READY":  # 当 whisper.cpp 可执行未就绪。
        print("INFO: whisper.cpp 可执行文件未通过检查，仅在需要该后端时需处理。")  # 输出提示。
    else:  # 可执行准备完成。
        print("OK: whisper.cpp 可执行文件可用。")  # 输出确认。
    if model_status_cpp != "READY":  # 当 whisper.cpp 模型未就绪。
        print("INFO: whisper.cpp 模型未就绪，若计划使用该后端请先下载 GGUF/GGML。")  # 输出提示。
    else:  # 模型就绪。
        print("OK: whisper.cpp 模型文件可用。")  # 输出确认。
    print("OK: 验证结束，退出码始终为 0。")  # 提醒脚本会以 0 退出。


if __name__ == "__main__":  # 当脚本直接执行时。
    main()  # 运行主函数。
    sys.exit(0)  # 显式以 0 退出。
