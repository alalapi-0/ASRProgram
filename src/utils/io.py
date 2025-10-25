"""提供目录创建与原子写入的辅助工具。"""
# 导入 json 模块以处理 JSON 序列化。
import json
# 导入 os 模块以执行原子重命名。
import os
# 导入 pathlib.Path 以便处理路径对象。
from pathlib import Path
# 导入 tempfile 模块创建临时文件。
import tempfile
# 导入 typing.Any 以标注任意类型数据。
from typing import Any

# 定义辅助函数，确保目录存在。
def ensure_directory(path: Path) -> None:
    """创建目标目录及父级目录（若尚不存在）。"""
    # 使用 Path.mkdir 创建目录，exist_ok=True 表示已存在时不报错。
    path.mkdir(parents=True, exist_ok=True)

# 定义原子写入文本文件的函数。
def atomic_write_text(target_path: Path, text: str) -> None:
    """将文本内容通过临时文件写入后再原子替换目标文件。"""
    # 确保目标目录已存在，避免写入失败。
    ensure_directory(target_path.parent)
    # 使用 NamedTemporaryFile 在同一目录创建临时文件。
    with tempfile.NamedTemporaryFile("w", delete=False, dir=target_path.parent, encoding="utf-8") as tmp_file:
        # 将文本写入临时文件。
        tmp_file.write(text)
        # 保存临时文件路径以便稍后替换。
        temp_path = Path(tmp_file.name)
    # 使用 os.replace 进行原子级别的替换操作。
    os.replace(temp_path, target_path)

# 定义写入 JSON 文件的便捷函数。
def write_json_atomic(target_path: Path, data: Any) -> None:
    """以 JSON 格式序列化数据并进行原子写入。"""
    # 使用 json.dumps 格式化数据，确保输出包含缩进便于阅读。
    json_text = json.dumps(data, ensure_ascii=False, indent=2)
    # 调用前面的 atomic_write_text 复用原子写入逻辑。
    atomic_write_text(target_path, json_text)

# 定义读取 JSON 文件的便捷函数。
def read_json(path: Path) -> Any:
    """读取 JSON 文件并返回解析后的数据结构。"""
    # 打开文件并读取所有文本内容。
    with path.open("r", encoding="utf-8") as handle:
        # 使用 json.load 将文本解析为 Python 对象。
        return json.load(handle)
