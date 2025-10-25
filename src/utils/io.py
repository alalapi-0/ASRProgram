"""提供跨平台目录管理与原子写入的工具函数。"""
# 导入 json 模块以便在原子写入函数中序列化数据结构。
import json
# 导入 os 模块以使用 replace 实现原子级文件替换。
import os
# 导入 pathlib.Path 以在函数内部统一处理路径对象。
from pathlib import Path
# 导入 typing.Any 用于对任意类型的 JSON 数据进行类型注释。
from typing import Any

# 定义安全创建目录的函数，确保重复调用也不会出错。
def safe_mkdirs(path: str | os.PathLike[str]) -> None:
    """创建目标目录及其父级目录，目录已存在时静默跳过。"""
    # 将输入路径统一转换为 Path 对象，支持字符串与 PathLike 类型。
    target = Path(path)
    # 调用 Path.mkdir 并启用 parents=True 以便同时创建父目录，exist_ok=True 避免目录存在时报错。
    target.mkdir(parents=True, exist_ok=True)

# 定义原子写入文本文件的函数，防止出现部分写入的中间状态。
def atomic_write_text(path: str | os.PathLike[str], text: str) -> None:
    """通过临时文件写入文本内容，并以原子方式替换目标文件。"""
    # 将目标路径转换为 Path 对象，便于后续获取父目录与构造临时文件路径。
    target_path = Path(path)
    # 计算目标文件所在的目录，后续需要在同一目录创建临时文件以保证 os.replace 的原子性。
    parent_dir = target_path.parent
    # 确保父目录存在；对于 dry-run 之外的场景允许重复调用。
    safe_mkdirs(parent_dir)
    # 构造临时文件路径，按照规范在原文件名后追加 .tmp 后缀。
    tmp_path = target_path.with_name(f"{target_path.name}.tmp")
    # 使用 try/except 包裹写入逻辑，确保在异常时清理临时文件。
    try:
        # 以 UTF-8 编码写入临时文件，使用 with 确保文件在退出时关闭。
        with open(tmp_path, "w", encoding="utf-8") as handle:
            # 将待写入的文本内容一次性写入临时文件。
            handle.write(text)
        # 使用 os.replace 将临时文件原子性地替换目标文件，可同时覆盖旧文件。
        os.replace(tmp_path, target_path)
    except Exception:  # noqa: BLE001
        # 若写入过程中出现异常且临时文件存在，则尝试删除临时文件避免遗留。
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        # 重新抛出异常，让调用者感知失败原因。
        raise

# 定义以 JSON 形式原子写入数据的函数，复用上面的文本写入逻辑。
def atomic_write_json(path: str | os.PathLike[str], data: Any) -> None:
    """将数据序列化为 JSON 文本后执行原子写入。"""
    # 使用 json.dumps 将 Python 对象转换为 JSON 字符串，保证可读性与非 ASCII 字符。
    json_text = json.dumps(data, ensure_ascii=False, indent=2)
    # 调用原子文本写入函数，将序列化结果落盘。
    atomic_write_text(path, json_text)

# 定义帮助函数去除路径中的扩展名，方便派生输出文件名。
def path_sans_ext(path: str | os.PathLike[str]) -> str:
    """返回不包含扩展名的路径字符串。"""
    # 使用 os.fspath 将 PathLike 对象转换为字符串表示，确保 splitext 可用。
    string_path = os.fspath(path)
    # 调用 os.path.splitext 分离扩展名，返回不含扩展名的部分。
    base, _ = os.path.splitext(string_path)
    # 返回去除扩展名的字符串，用于构造派生文件名。
    return base

# 定义简易的文件存在性检查函数，便于封装测试。
def file_exists(path: str | os.PathLike[str]) -> bool:
    """判断给定路径是否存在（文件或目录均可）。"""
    # 调用 os.path.exists 执行存在性检查，并直接返回布尔结果。
    return os.path.exists(path)
