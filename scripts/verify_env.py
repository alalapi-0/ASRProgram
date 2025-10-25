"""环境自检脚本，确保运行 ASRProgram 所需的最小依赖与 Python 版本。"""
# 导入 sys 模块以检查 Python 版本。
import sys
# 导入 importlib.util 用于检测依赖是否可被导入。
import importlib.util
# 定义主函数，提供清晰的入口。
def main() -> int:
    """检查 Python 版本并验证核心依赖是否已安装。"""
    # 准备一个列表，用于收集检测到的问题。
    issues: list[str] = []
    # 检查 Python 主版本是否满足 3.10 及以上。
    if sys.version_info < (3, 10):
        # 如果版本过低，将错误信息记录到 issues。
        issues.append(
            f"Python 3.10+ is required, but detected {sys.version}"
        )
    # 定义必须安装的依赖名称列表。
    required_packages = ["pyyaml"]
    # 遍历依赖名称，逐个检查是否可导入。
    for package in required_packages:
        # 使用 importlib.util.find_spec 判断模块可见性。
        if importlib.util.find_spec(package) is None:
            # 若找不到模块，将信息加入 issues。
            issues.append(f"Missing required package: {package}")
    # 根据是否存在问题输出结果。
    if issues:
        # 打印发现的问题，逐条输出。
        print("Environment verification failed:")
        for issue in issues:
            # 将每条问题信息打印到标准输出。
            print(f" - {issue}")
        # 返回非零状态码，表示检测失败。
        return 1
    # 如果没有问题，则输出成功信息。
    print("Environment verification passed. Python version and dependencies look good.")
    # 返回零状态码，表示成功。
    return 0
# 仅当脚本作为主程序执行时才运行 main 函数。
if __name__ == "__main__":
    # 调用 main 并将其返回值作为进程退出码。
    sys.exit(main())
