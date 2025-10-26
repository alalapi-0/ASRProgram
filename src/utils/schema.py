"""提供 JSON Schema 加载、缓存与补充校验的工具函数。"""  # 模块文档说明。
# 导入 json 以解析 schema 文件内容。
import json
# 导入 collections.deque 以构造 ValidationError 的路径信息。
from collections import deque
# 导入 pathlib.Path 以定位仓库中的 schemas 目录。
from pathlib import Path
# 导入 typing.Dict 以标注缓存字典类型。
from typing import Dict

# 从 jsonschema 导入校验器、格式检查器与异常类型。
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

# 预先解析 schema 目录，避免每次调用都重新计算。
SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"
# 定义支持的 schema 名称到文件名的映射，便于统一管理。
SCHEMA_FILES = {
    "words": "words.schema.json",
    "segments": "segments.schema.json",
}
# 使用字典缓存已加载的 schema，避免重复读取磁盘。
_SCHEMA_CACHE: Dict[str, dict] = {}
# 缓存编译后的 jsonschema 校验器，进一步减少初始化开销。
_VALIDATOR_CACHE: Dict[str, Draft202012Validator] = {}
# 初始化格式检查器，用于处理 date-time 等内置格式校验。
_FORMAT_CHECKER = FormatChecker()


def load_schema(name: str) -> dict:
    """加载指定名称的 JSON Schema，并在内存中缓存。"""  # 函数文档说明。

    # 标准化 schema 名称，确保调用方使用 words/segments 等关键字。
    key = name.strip().lower()
    # 确认名称受支持，否则抛出直观的错误提示。
    if key not in SCHEMA_FILES:
        raise KeyError(f"Unknown schema: {name}")
    # 若缓存已存在则直接返回，避免重复读取文件。
    if key in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[key]
    # 拼接 schema 文件的绝对路径。
    schema_path = SCHEMA_DIR / SCHEMA_FILES[key]
    # 读取 JSON 并解析为字典。
    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    # 将解析结果写入缓存，供后续复用。
    _SCHEMA_CACHE[key] = schema
    # 返回 schema 字典给调用方。
    return schema


def _get_validator(name: str) -> Draft202012Validator:
    """获取编译后的 Draft2020-12 校验器实例并缓存。"""  # 内部工具函数说明。

    # 标准化名称并确保存在对应文件。
    key = name.strip().lower()
    load_schema(key)
    # 若缓存中已有校验器则直接返回。
    if key in _VALIDATOR_CACHE:
        return _VALIDATOR_CACHE[key]
    # 创建新的校验器对象，启用格式检查器以验证 date-time。
    validator = Draft202012Validator(_SCHEMA_CACHE[key], format_checker=_FORMAT_CHECKER)
    # 将校验器写入缓存，供后续调用使用。
    _VALIDATOR_CACHE[key] = validator
    # 返回校验器实例。
    return validator


def _enforce_word_timings(words: list, path_prefix: tuple[str, ...]) -> None:
    """补充验证词级时间戳，确保 end 不早于 start。"""  # 内部工具函数说明。

    # 遍历词条列表并逐一检验时间戳关系。
    for index, entry in enumerate(words):
        # 提取 start 与 end，缺失时跳过，由 schema 负责 required 校验。
        start = entry.get("start")
        end = entry.get("end")
        # 仅在两个值都存在的情况下执行比较。
        if start is None or end is None:
            continue
        # 若结束时间早于起始时间，构造携带路径的 ValidationError。
        if end < start:
            raise ValidationError(
                "word timing end is earlier than start",
                path=deque((*path_prefix, index, "end")),
            )


def _enforce_segment_timings(segments: list) -> None:
    """补充验证段级时间戳，并校验嵌套词数组。"""  # 内部工具函数说明。

    # 遍历段数组，检查段级时间戳并复用词级检查函数。
    for index, segment in enumerate(segments):
        # 提取段起止时间，用于关系比较。
        start = segment.get("start")
        end = segment.get("end")
        # 若字段缺失则跳过，让 schema 的 required 规则处理。
        if start is not None and end is not None and end < start:
            raise ValidationError(
                "segment timing end is earlier than start",
                path=deque(("segments", index, "end")),
            )
        # 读取嵌套的词条数组，默认使用空列表以避免 TypeError。
        words = segment.get("words", [])
        # 调用词级校验，传递段级路径前缀，便于错误定位。
        _enforce_word_timings(words, ("segments", index, "words"))


def validate_words(payload: dict) -> None:
    """校验词级 JSON 结构并在需要时抛出 ValidationError。"""  # 函数文档说明。

    # 使用缓存的 schema 校验器执行结构验证与格式检查。
    validator = _get_validator("words")
    validator.validate(payload)
    # 执行补充的时间戳约束，提供更易读的错误信息。
    _enforce_word_timings(payload.get("words", []), ("words",))


def validate_segments(payload: dict) -> None:
    """校验段级 JSON 结构并检查嵌套词条。"""  # 函数文档说明。

    # 使用缓存校验器验证段级顶层结构。
    validator = _get_validator("segments")
    validator.validate(payload)
    # 补充段级时间戳与内部词条的关系校验。
    _enforce_segment_timings(payload.get("segments", []))
