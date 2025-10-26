#!/usr/bin/env python3
# 注释：使用当前环境中的 Python 解释器运行脚本
"""发布前检查脚本，确保仓库符合发行要求。"""  # 注释：模块文档字符串描述用途

import platform  # 注释：获取操作系统与 Python 版本信息
import subprocess  # 注释：调用外部命令读取 Git 信息
from pathlib import Path  # 注释：更方便地处理路径

# 注释：设定仓库根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# 注释：定义必需存在的目录列表
REQUIRED_DIRS = [PROJECT_ROOT / name for name in ("src", "schemas", "config")]
# 注释：设定禁用后缀，用于扫描潜在的二进制或模型文件
FORBIDDEN_SUFFIXES = {".wav", ".bin", ".model", ".gguf"}
# 注释：设定文件大小阈值（50MB）
SIZE_THRESHOLD = 50 * 1024 * 1024


def read_version() -> str:
    """读取版本号文件，返回第一段内容。"""  # 注释：函数目的
    version_path = PROJECT_ROOT / "VERSION"  # 注释：定位版本文件
    raw = version_path.read_text(encoding="utf-8").strip()  # 注释：读取并去除多余空白
    return raw.split()[0]  # 注释：返回首个标记作为版本号


def ensure_required_dirs() -> list[str]:
    """检查必需目录是否存在，返回缺失目录名称列表。"""  # 注释：函数用途
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in REQUIRED_DIRS if not path.exists()]  # 注释：记录缺失目录
    return missing  # 注释：返回缺失列表


def scan_forbidden_files() -> list[str]:
    """扫描禁用文件类型与超大文件，返回警告列表。"""  # 注释：函数用途
    warnings: list[str] = []  # 注释：初始化警告列表
    for path in PROJECT_ROOT.rglob("*"):  # 注释：遍历仓库内全部文件
        if not path.is_file():  # 注释：跳过目录
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:  # 注释：检测禁止后缀
            warnings.append(f"禁用文件类型：{path.relative_to(PROJECT_ROOT)}")  # 注释：记录警告
            continue
        if path.stat().st_size > SIZE_THRESHOLD:  # 注释：检查文件是否超过大小阈值
            warnings.append(f"文件过大（>{SIZE_THRESHOLD} bytes）：{path.relative_to(PROJECT_ROOT)}")  # 注释：记录警告
    return warnings  # 注释：返回扫描结果


def gather_dependency_summary() -> list[str]:
    """读取 requirements.txt 提供依赖摘要。"""  # 注释：函数用途
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()  # 注释：读取依赖文件
    summary = [line.strip() for line in requirements if line.strip() and not line.startswith("#")]  # 注释：移除空行与注释
    return summary  # 注释：返回整理后的依赖列表


def current_git_commit() -> str:
    """获取当前 Git 提交 ID。"""  # 注释：函数用途
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # 注释：Git 命令
            cwd=PROJECT_ROOT,  # 注释：在仓库根目录运行
            check=True,  # 注释：命令失败时抛出异常
            stdout=subprocess.PIPE,  # 注释：捕获标准输出
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip()  # 注释：返回提交哈希
    except Exception as exc:  # 注释：捕获异常
        return f"unknown ({exc})"  # 注释：无法获取时提供说明


def main() -> None:
    """执行发布前检查并打印结果。"""  # 注释：主函数说明
    version = read_version()  # 注释：获取版本号
    missing_dirs = ensure_required_dirs()  # 注释：检查目录存在性
    warnings = scan_forbidden_files()  # 注释：扫描禁用文件
    dependencies = gather_dependency_summary()  # 注释：整理依赖摘要
    commit_id = current_git_commit()  # 注释：获取当前提交哈希

    print("=== ASRProgram Release Checklist ===")  # 注释：打印标题
    print(f"Version: {version}")  # 注释：输出版本号
    print(f"Python: {platform.python_version()} ({platform.platform()})")  # 注释：输出 Python 与平台信息
    print(f"Git commit: {commit_id}")  # 注释：输出 Git 提交信息

    if missing_dirs:  # 注释：若存在缺失目录
        print("Missing directories:")  # 注释：提示缺失目录
        for name in missing_dirs:
            print(f"  - {name}")  # 注释：逐项列出
    else:
        print("Required directories are present.")  # 注释：全部存在时提示

    if warnings:  # 注释：若存在警告
        print("Warnings:")  # 注释：提示警告列表
        for item in warnings:
            print(f"  - {item}")  # 注释：逐项列出
    else:
        print("No forbidden or oversized files detected.")  # 注释：通过扫描

    print("Dependencies:")  # 注释：输出依赖摘要
    for dep in dependencies:
        print(f"  - {dep}")  # 注释：逐项列出依赖

    status = "BLOCKED" if missing_dirs or warnings else "READY"  # 注释：根据检查结果设置状态
    print(f"Status: {status}")  # 注释：输出总体状态
    if status == "READY":  # 注释：若准备就绪
        print(f"Ready to release v{version}")  # 注释：打印最终提示


if __name__ == "__main__":  # 注释：脚本入口
    main()  # 注释：调用主函数
