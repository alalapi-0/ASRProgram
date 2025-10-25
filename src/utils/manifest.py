"""提供 JSONL Manifest 的写入与查询工具函数。"""  # 模块说明。
# 导入 json 以解析与序列化记录。 
import json
# 导入 pathlib.Path 统一处理路径对象。 
from pathlib import Path
# 导入 typing.Any, Dict 以进行类型注释。 
from typing import Any, Dict

# 从 I/O 模块导入 jsonl_append 复用原子追加逻辑。 
from src.utils.io import jsonl_append

# 定义追加记录到 Manifest 的函数。 
def append_record(manifest_path: str | Path, record: Dict[str, Any]) -> None:
    """向指定的 JSONL Manifest 追加一条记录。"""  # 函数说明。
    # 直接调用 jsonl_append，内部会负责加锁与创建目录。 
    jsonl_append(str(manifest_path), record)

# 定义加载 Manifest 索引的函数。 
def load_index(manifest_path: str | Path) -> Dict[str, Dict[str, Any]]:
    """读取 Manifest 并返回以输入路径为键的最新记录索引。"""  # 函数说明。
    # 将路径转换为 Path 对象，便于检测文件是否存在。 
    path = Path(manifest_path)
    # 若 Manifest 不存在则返回空字典。 
    if not path.exists():
        return {}
    # 初始化结果索引，键为字符串形式的输入路径。 
    index: Dict[str, Dict[str, Any]] = {}
    # 逐行读取 JSONL 文件，保留每个输入的最后一条记录。 
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            # 去除换行符并跳过空行。 
            payload = line.strip()
            if not payload:
                continue
            try:
                # 将 JSON 字符串解析为 Python 字典。 
                data = json.loads(payload)
            except json.JSONDecodeError:
                # 若某行损坏则忽略继续处理后续数据。 
                continue
            # 读取输入路径字段并转换为字符串。 
            input_path = data.get("input")
            if not input_path:
                continue
            # 使用 str(Path(...)) 统一路径格式，确保重复键覆盖为最新记录。 
            index[str(Path(input_path))] = data
    # 返回构建好的索引。 
    return index

# 定义根据输入路径查找最近记录的函数。 
def find_by_input(manifest_path: str | Path, input_path: str | Path) -> Dict[str, Any] | None:
    """在 Manifest 中查找指定输入路径的最新记录。"""  # 函数说明。
    # 将 Manifest 与目标路径均转换为 Path 对象确保一致性。 
    path = Path(manifest_path)
    target = str(Path(input_path))
    # 若 Manifest 不存在则直接返回 None。 
    if not path.exists():
        return None
    # 初始化结果变量，遍历过程中随时更新。 
    result: Dict[str, Any] | None = None
    # 逐行读取以获取最新匹配记录。 
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            # 去除尾部空白并跳过空行。 
            payload = line.strip()
            if not payload:
                continue
            try:
                # 解析 JSON 行。 
                data = json.loads(payload)
            except json.JSONDecodeError:
                # 对损坏行容错，继续扫描下一行。 
                continue
            # 判断当前行是否对应目标输入路径。 
            if str(Path(data.get("input", ""))) == target:
                result = data
    # 返回最后一次匹配到的记录（若不存在则为 None）。 
    return result
