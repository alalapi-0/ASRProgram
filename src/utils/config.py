"""Round 13 配置系统：分层加载、Profile、校验与快照导出工具集合。"""  # 模块说明。
from __future__ import annotations  # 启用前向注解以提升类型兼容性。

import copy  # 导入 copy 以执行深拷贝避免引用共享。
import os  # 导入 os 以访问环境变量与路径扩展。
from dataclasses import dataclass  # 导入 dataclass 以封装结果结构。
from datetime import datetime, timezone  # 导入 datetime 用于生成时间戳。
from pathlib import Path  # 导入 Path 统一路径处理。
from typing import Any, Dict, Iterable, Mapping  # 导入类型注解辅助代码可读性。

import yaml  # 导入 PyYAML 以读取/写出 YAML 文件。

from src.utils.io import atomic_write_text  # 复用原子写入工具以保存配置快照。

ENV_PREFIX = "ASRPROGRAM_"  # 所有环境变量需以此前缀开头才会被解析。


@dataclass
class ConfigBundle:
    """封装配置加载结果，包含配置体、来源映射与激活的 Profile。"""  # 数据类说明。

    config: Dict[str, Any]  # 最终合并并经过规范化的配置字典。
    sources: Dict[str, Any]  # 与 config 对应的来源追踪树，叶子为字符串。
    profile: str | None  # 当前生效的 profile 名称，若未选择则为 None。
    profile_source: str | None  # profile 由哪一层触发，例如 "cli:--profile"。


class ConfigError(ValueError):
    """对外统一的配置异常类型，包含来源链路信息。"""  # 自定义异常说明。


def _project_root() -> Path:
    """返回仓库根目录，基于当前文件路径推断。"""  # 工具函数说明。

    return Path(__file__).resolve().parents[2]  # config.py 位于 src/utils，下两级即仓库根。


def _load_yaml(path: Path) -> Dict[str, Any]:
    """读取 YAML 文件并返回字典结构，若为空则返回空字典。"""  # 工具函数说明。

    with path.open("r", encoding="utf-8") as handle:  # 打开文件读取 UTF-8 文本。
        data = yaml.safe_load(handle)  # 使用 safe_load 避免执行任意代码。
    return data or {}  # 若文件为空则返回空字典以便后续处理。


def _initialize_sources(node: Any, label: str) -> Any:
    """基于给定标签初始化与配置同结构的来源树。"""  # 工具函数说明。

    if isinstance(node, dict):  # 若节点是字典则递归为每个键赋值。
        return {key: _initialize_sources(value, label) for key, value in node.items()}  # 递归处理。
    return label  # 非字典节点直接标记为当前标签。


def _build_source_tree(node: Any, label: str) -> Any:
    """根据数据结构构造来源树，用于深度合并时携带来源信息。"""  # 工具函数说明。

    if isinstance(node, dict):  # 对字典逐键生成嵌套来源。
        return {key: _build_source_tree(value, label) for key, value in node.items()}  # 递归构造。
    return label  # 标量直接返回标签。


def _deep_merge(base: Dict[str, Any], incoming: Dict[str, Any], sources: Dict[str, Any], incoming_sources: Dict[str, Any]) -> None:
    """递归地将 incoming 合并进 base，并同步更新来源信息。"""  # 工具函数说明。

    for key, value in incoming.items():  # 遍历待合并的键值对。
        source_info = incoming_sources.get(key) if isinstance(incoming_sources, dict) else incoming_sources  # 获取对应的来源标签或子树。
        if isinstance(value, dict):  # 若值为字典需要递归处理。
            base_child = base.get(key)  # 读取基准中的旧值。
            source_child = sources.get(key) if isinstance(sources, dict) else None  # 读取来源子树。
            if not isinstance(base_child, dict):  # 若旧值不是字典则直接替换为新字典。
                base_child = {}
            if not isinstance(source_child, dict):  # 若来源不是字典则初始化新字典。
                source_child = {}
            base[key] = base_child  # 将合并结果写回。
            sources[key] = source_child  # 同步来源树。
            if isinstance(source_info, str):  # 若来源只是标签需扩展为整棵树。
                source_info = _build_source_tree(value, source_info)  # 构造与值同结构的来源树。
            _deep_merge(base_child, value, source_child, source_info)  # 递归合并子结构。
            continue  # 完成当前键处理。
        if value is None and key in base and base[key] is not None:  # None 不会覆盖已有非空值。
            continue  # 跳过此次赋值保持原值。
        base[key] = copy.deepcopy(value)  # 对标量/列表执行深拷贝后写入。
        sources[key] = source_info  # 记录来源标签。


def deep_merge_dicts(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """对外暴露的深度合并助手，仅返回新的合并结果。"""  # 公共函数说明。

    result = copy.deepcopy(base)  # 拷贝基准避免修改原数据。
    sources_stub = _initialize_sources(result, "base")  # 构造占位来源，外部通常不会读取。
    incoming_sources = _build_source_tree(incoming, "incoming")  # 为来稿构建统一来源标签。
    _deep_merge(result, incoming, sources_stub, incoming_sources)  # 执行合并逻辑。
    return result  # 返回新字典。


def _parse_scalar(value: str) -> Any:
    """将字符串尝试解析为布尔、整数或浮点类型，失败时返回原字符串。"""  # 工具函数说明。

    lowered = value.strip().lower()  # 预先裁剪并统一小写。
    if lowered in {"true", "false"}:  # 识别布尔文本。
        return lowered == "true"  # 返回布尔值。
    if lowered == "null" or lowered == "none":  # 支持 null/none 表达空值。
        return None  # 返回 None 以遵循覆盖规则。
    try:
        if lowered.startswith("0") and lowered not in {"0", "0.0"}:  # 以 0 开头的字符串保持原样避免八进制误判。
            raise ValueError  # 手动触发 except 分支保留原字符串。
        return int(lowered)  # 优先尝试整数转换。
    except ValueError:
        try:
            return float(lowered)  # 再尝试浮点转换。
        except ValueError:
            return value.strip()  # 均失败则返回去除首尾空格后的原字符串。


def _keypath_to_tree(keypath: Iterable[str], value: Any) -> Dict[str, Any]:
    """根据层级列表生成嵌套字典，用于 --set 与环境变量合并。"""  # 工具函数说明。

    result: Dict[str, Any] = {}  # 初始化结果字典。
    cursor = result  # 游标指向当前层级。
    components = list(keypath)  # 将迭代器转为列表以便索引。
    for index, part in enumerate(components):  # 遍历层级组件。
        if index == len(components) - 1:  # 末尾键直接赋值。
            cursor[part] = value  # 写入最终值。
        else:
            cursor = cursor.setdefault(part, {})  # 逐层创建嵌套字典。
    return result  # 返回构建好的树。


def _collect_env_from_mapping(env: Mapping[str, str], source_prefix: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """从映射中提取 ASRPROGRAM_* 变量并构造值树与来源树。"""  # 工具函数说明。

    values: Dict[str, Any] = {}  # 存放解析后的值。
    value_sources: Dict[str, Any] = {}  # 存放对应的来源描述。
    for key, raw_value in env.items():  # 遍历全部环境变量。
        if not key.startswith(ENV_PREFIX):  # 过滤非指定前缀。
            continue  # 跳过无关变量。
        trimmed = key[len(ENV_PREFIX) :]  # 去除前缀获得层级表达。
        path = [segment.lower() for segment in trimmed.split("__") if segment]  # 双下划线表示层级，统一转小写。
        if not path:  # 若未解析出有效键则忽略。
            continue  # 继续处理下一个变量。
        value = _parse_scalar(raw_value)  # 对值执行类型推断。
        tree = _keypath_to_tree(path, value)  # 构造嵌套字典。
        source_tree = _keypath_to_tree(path, f"env:{source_prefix}{key}")  # 记录来源信息。
        _deep_merge(values, tree, value_sources, source_tree)  # 合并当前环境变量。
    return values, value_sources  # 返回解析结果。


def _parse_dotenv_file(path: Path) -> Dict[str, str]:
    """解析 .env 文件，仅返回键值对字典。"""  # 工具函数说明。

    result: Dict[str, str] = {}  # 初始化结果容器。
    if not path.exists():  # 若文件不存在直接返回空字典。
        return result  # 返回空集。
    with path.open("r", encoding="utf-8") as handle:  # 打开文件读取文本。
        for line in handle:  # 逐行读取。
            stripped = line.strip()  # 去除首尾空白。
            if not stripped or stripped.startswith("#"):  # 跳过空行与注释。
                continue  # 处理下一行。
            if "=" not in stripped:  # 若缺少等号则忽略。
                continue  # 避免错误格式。
            key, _, raw_value = stripped.partition("=")  # 拆分键与值。
            value = raw_value.strip().strip("\"'")  # 去除周围空白与包裹的引号。
            result[key.strip()] = value  # 写入解析结果。
    return result  # 返回从文件解析的键值对。


def _normalize_path(value: str) -> str:
    """展开用户目录并清理尾部斜杠，保持平台兼容。"""  # 工具函数说明。

    expanded = os.path.expanduser(os.path.expandvars(value.strip()))  # 展开 ~ 及环境变量。
    if expanded not in {"/", ""}:  # 避免对根目录或空串进行裁剪。
        expanded = expanded.rstrip("/\\")  # 移除尾部斜杠保持一致。
    return expanded  # 返回规范化后的路径字符串。


def _normalize_config(config: Dict[str, Any]) -> None:
    """对配置进行就地规范化，例如统一大小写与路径形态。"""  # 工具函数说明。

    runtime = config.setdefault("runtime", {})  # 确保 runtime 节点存在。
    backend = runtime.get("backend")  # 读取后端名称。
    if isinstance(backend, str):  # 若为字符串则统一小写并去除空白。
        runtime["backend"] = backend.strip().lower()  # 标准化后写回。
    language = runtime.get("language")  # 读取语言代码。
    if isinstance(language, str):  # 语言也统一小写。
        runtime["language"] = language.strip().lower()  # 写回语言码。
    device = runtime.get("device")  # 读取设备名称。
    if isinstance(device, str):  # 对设备字符串执行标准化。
        runtime["device"] = device.strip().lower()  # 写回。
    compute_type = runtime.get("compute_type")  # 读取精度参数。
    if isinstance(compute_type, str):  # 若为字符串则统一小写。
        runtime["compute_type"] = compute_type.strip().lower()  # 写回。
    for key in ["model", "backend_cli_default"]:  # 遍历需小写化的顶层键。
        value = config.get(key)  # 读取键值。
        if isinstance(value, str):  # 若为字符串则小写化。
            config[key] = value.strip().lower()  # 写回标准化值。
    path_like_keys = [  # 构造需要执行路径规范化的键路径。
        ["input"],
        ["out_dir"],
        ["cache_dir"],
        ["models_dir"],
        ["log_file"],
        ["metrics_file"],
        ["manifest_path"],
        ["runtime", "whisper_cpp", "executable_path"],
        ["runtime", "whisper_cpp", "model_path"],
    ]  # 关键路径字段列表。
    lowercase_path_keys = {("input",), ("out_dir",)}  # 需要额外执行小写化的路径键集合。
    for path in path_like_keys:  # 遍历每个路径键。
        parent = config  # 从根节点开始。
        for part in path[:-1]:  # 定位到父级字典。
            node = parent.get(part)
            if not isinstance(node, dict):  # 若路径不存在则跳过。
                parent = None
                break
            parent = node
        if not parent:  # 未成功定位父级则跳过。
            continue
        leaf = path[-1]  # 末级键名。
        value = parent.get(leaf)  # 读取当前值。
        if isinstance(value, str) and value.strip():  # 对非空字符串进行规范化。
            normalized = _normalize_path(value)  # 先执行通用规范化。
            if tuple(path) in lowercase_path_keys:  # 针对输入/输出目录强制转为小写。
                normalized = normalized.lower()
            parent[leaf] = normalized  # 写回处理后的路径。
    log_sample = config.get("log_sample_rate")  # 读取日志采样率。
    if isinstance(log_sample, (int, float)):  # 若为数字类型则执行截断。
        config["log_sample_rate"] = max(min(float(log_sample), 1.0), 1e-6)  # 限制在 (0,1] 范围。
    num_workers = config.get("num_workers")  # 读取并发数量。
    if isinstance(num_workers, int):  # 若为整数则确保最小值为 1。
        config["num_workers"] = max(1, num_workers)  # 写回裁剪后的值。
    max_retries = config.get("max_retries")  # 读取最大重试次数。
    if isinstance(max_retries, int):  # 若为整数则不小于 0。
        config["max_retries"] = max(0, max_retries)  # 写回。
    rate_limit = config.get("rate_limit")  # 读取速率限制。
    if isinstance(rate_limit, (int, float)):  # 若为数值则不小于 0。
        config["rate_limit"] = max(0.0, float(rate_limit))  # 写回。
    lock_timeout = config.get("lock_timeout")  # 读取锁超时。
    if isinstance(lock_timeout, (int, float)):  # 若为数值则不小于 0。
        config["lock_timeout"] = max(0.0, float(lock_timeout))  # 写回。


def _source_for_path(path: Iterable[str], sources: Dict[str, Any]) -> str:
    """根据键路径在来源树中查找对应标签。"""  # 工具函数说明。

    cursor: Any = sources  # 从根开始遍历。
    for part in path:  # 顺序访问每一级键。
        if not isinstance(cursor, dict):  # 若当前节点不是字典则无法继续。
            return "unknown"  # 返回未知来源。
        cursor = cursor.get(part)  # 进入子节点。
        if cursor is None:  # 缺少对应键时返回未知。
            return "unknown"
    if isinstance(cursor, str):  # 找到叶子标签时直接返回。
        return cursor
    return "unknown"  # 若最终仍为字典则返回未知。


def _assert_condition(condition: bool, path: Iterable[str], message: str, value: Any, sources: Dict[str, Any]) -> None:
    """若条件不成立则抛出包含来源信息的配置异常。"""  # 工具函数说明。

    if condition:  # 条件满足则无需处理。
        return
    dotted = ".".join(path)  # 将路径转为点分字符串。
    origin = _source_for_path(path, sources)  # 查找来源标签。
    raise ConfigError(f"Invalid value for {dotted}: {message} (value={value!r}, source={origin})")  # 抛出异常。


def _validate_config(config: Dict[str, Any], sources: Dict[str, Any]) -> None:
    """执行语义校验，确保关键字段满足约束。"""  # 工具函数说明。

    runtime = config.get("runtime", {})  # 读取运行时配置。
    backend = runtime.get("backend")  # 提取后端名称。
    _assert_condition(
        backend in {"faster-whisper", "whisper.cpp", "dummy"},  # 允许的后端列表。
        ["runtime", "backend"],
        "backend must be one of {'faster-whisper','whisper.cpp','dummy'}",
        backend,
        sources,
    )  # 校验后端合法性。
    beam_size = runtime.get("beam_size")  # 读取 beam 宽度。
    if beam_size is not None:  # 允许 None 时跳过。
        _assert_condition(
            isinstance(beam_size, int) and beam_size >= 1,  # 必须为正整数。
            ["runtime", "beam_size"],
            "beam_size must be >= 1",
            beam_size,
            sources,
        )
    temperature = runtime.get("temperature")  # 读取温度。
    if temperature is not None:  # 允许空值。
        _assert_condition(
            isinstance(temperature, (int, float)) and 0.0 <= float(temperature) <= 1.0,  # 限制范围。
            ["runtime", "temperature"],
            "temperature must be within [0, 1]",
            temperature,
            sources,
        )
    threads = runtime.get("whisper_cpp", {}).get("threads")  # 读取 whisper.cpp 线程数。
    if threads is not None:  # 允许空值。
        _assert_condition(
            isinstance(threads, int) and threads >= 0,  # 必须为非负整数。
            ["runtime", "whisper_cpp", "threads"],
            "threads must be non-negative integer",
            threads,
            sources,
        )
    num_workers = config.get("num_workers")  # 读取 worker 数量。
    _assert_condition(
        isinstance(num_workers, int) and num_workers >= 1,
        ["num_workers"],
        "num_workers must be >= 1",
        num_workers,
        sources,
    )  # 校验 worker 数。
    max_retries = config.get("max_retries")  # 读取重试次数。
    _assert_condition(
        isinstance(max_retries, int) and max_retries >= 0,
        ["max_retries"],
        "max_retries must be >= 0",
        max_retries,
        sources,
    )  # 校验重试数。
    log_sample = config.get("log_sample_rate")  # 读取日志采样率。
    _assert_condition(
        isinstance(log_sample, (int, float)) and 0.0 < float(log_sample) <= 1.0,
        ["log_sample_rate"],
        "log_sample_rate must be within (0, 1]",
        log_sample,
        sources,
    )  # 校验采样率。


def parse_cli_set_items(items: Iterable[str]) -> Dict[str, Any]:
    """将 --set KEY=VALUE 形式的列表解析为嵌套字典。"""  # 公共函数说明。

    overrides: Dict[str, Any] = {}  # 初始化结果。
    for raw in items:  # 遍历每个原始字符串。
        if "=" not in raw:  # 若缺少等号则抛出错误提示。
            raise ConfigError(f"Invalid --set entry '{raw}', expected KEY=VALUE")  # 报错提醒用户。
        key, value = raw.split("=", 1)  # 仅拆分首个等号以允许值中包含等号。
        path = [segment.strip().lower() for segment in key.split(".") if segment.strip()]  # 使用点分表示层级。
        if not path:  # 若没有有效键则继续。
            continue
        parsed_value = _parse_scalar(value)  # 将值解析为适当类型。
        tree = _keypath_to_tree(path, parsed_value)  # 构造嵌套字典。
        _deep_merge(overrides, tree, overrides, tree)  # 直接复用 _deep_merge 进行累积。
    return overrides  # 返回解析结果。


def load_and_merge_config(
    cli_overrides: Dict[str, Any] | None = None,
    cli_set_overrides: Dict[str, Any] | None = None,
    config_path: str | None = None,
    profile_name: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> ConfigBundle:
    """按照默认→用户→profile→环境→CLI 顺序加载配置并返回结果。"""  # 主函数说明。

    root = _project_root()  # 解析仓库根路径。
    default_path = root / "config" / "default.yaml"  # 构造默认配置路径。
    if not default_path.exists():  # 若默认文件缺失则立刻报错。
        raise FileNotFoundError(f"Default config not found: {default_path}")  # 抛出异常提醒缺失。
    base_config = _load_yaml(default_path)  # 读取默认配置。
    config = copy.deepcopy(base_config)  # 拷贝初始配置以便后续层叠覆盖。
    sources = _initialize_sources(config, f"default:{default_path}")  # 初始化来源树。
    user_path = Path(config_path) if config_path else root / "config" / "user.yaml"  # 推导用户配置路径。
    user_config = {}  # 初始化用户配置字典。
    if user_path.exists():  # 若用户配置存在则读取。
        user_config = _load_yaml(user_path)  # 读取用户层。
        _deep_merge(config, user_config, sources, _build_source_tree(user_config, f"user:{user_path}"))  # 合并用户层。
    effective_profile = profile_name or user_config.get("meta", {}).get("profile") or config.get("meta", {}).get("profile")  # 计算待应用的 profile 名称。
    profile_source = None  # 初始化 profile 来源记录。
    profiles = config.get("profiles", {})  # 读取全部 profile 预设。
    if effective_profile:  # 若选择了 profile。
        profile_data = profiles.get(effective_profile)  # 获取对应预设。
        if profile_data is None:  # 未找到则抛出配置异常。
            raise ConfigError(f"Unknown profile '{effective_profile}'")  # 报错提示。
        profile_source = f"profile:{effective_profile}"  # 记录 profile 来源。
        _deep_merge(config, profile_data, sources, _build_source_tree(profile_data, profile_source))  # 合并 profile。
    environ = environ or os.environ  # 若未提供环境映射则使用系统环境。
    env_layers: list[tuple[Dict[str, Any], Dict[str, Any]]] = []  # 存放各来源的解析结果。
    dotenv_candidates = [root / ".env"]  # 默认在仓库根查找 .env。
    if user_path and user_path.exists():  # 若用户配置存在则尝试其所在目录。
        dotenv_candidates.append(user_path.parent / ".env")  # 追加该目录。
    for dotenv_path in dotenv_candidates:  # 遍历候选 .env。
        env_map = _parse_dotenv_file(dotenv_path)  # 解析文件。
        if not env_map:  # 若无相关键则跳过。
            continue
        layer = _collect_env_from_mapping(env_map, f"{dotenv_path}:")  # 构造值树与来源树。
        env_layers.append(layer)  # 记录解析结果。
    env_layers.append(_collect_env_from_mapping(environ, ""))  # 最后附加真实环境变量。
    for values, source_tree in env_layers:  # 按顺序应用环境覆盖。
        if not values:
            continue
        _deep_merge(config, values, sources, source_tree)  # 合并环境层。
    cli_overrides = cli_overrides or {}  # 若 CLI 未提供显式覆盖则使用空字典。
    if cli_overrides:  # 应用 CLI 指定参数。
        _deep_merge(config, cli_overrides, sources, _build_source_tree(cli_overrides, "cli:args"))  # 合并 CLI 参数。
    cli_set_overrides = cli_set_overrides or {}  # 处理 --set 组合覆盖。
    if cli_set_overrides:
        _deep_merge(config, cli_set_overrides, sources, _build_source_tree(cli_set_overrides, "cli:set"))  # 合并 --set。
    _normalize_config(config)  # 对合并结果执行规范化。
    _validate_config(config, sources)  # 校验规范化后的配置。
    meta = config.setdefault("meta", {})  # 确保 meta 字段存在。
    meta_sources = sources.setdefault("meta", {}) if isinstance(sources, dict) else {}  # 定位 meta 的来源树。
    if not isinstance(meta_sources, dict):  # 若来源结构异常则重建。
        meta_sources = {}
        if isinstance(sources, dict):  # 仅当来源为字典时写回。
            sources["meta"] = meta_sources
    meta["profile"] = effective_profile  # 记录生效的 profile。
    if effective_profile is not None:  # 仅在选择了 profile 时更新来源标签。
        meta_sources["profile"] = profile_source or meta_sources.get("profile", "profile:derived")  # 记录来源。
    meta["config_generated_at"] = datetime.now(timezone.utc).isoformat()  # 写入生成时间戳。
    meta_sources["config_generated_at"] = "runtime:generated"  # 标记时间戳来源于运行时生成。
    return ConfigBundle(config=config, sources=sources, profile=effective_profile, profile_source=profile_source)  # 封装结果返回。


def render_effective_config(bundle: ConfigBundle, include_sources: bool = True) -> str:
    """将配置与来源以 YAML 文本渲染，可附带来源注释。"""  # 导出函数说明。

    def _render(node: Any, source_node: Any, indent: int) -> list[str]:  # 定义内部递归渲染函数。
        lines: list[str] = []  # 当前层级的输出行集合。
        if isinstance(node, dict):  # 字典需要逐键展开。
            for key in sorted(node.keys()):  # 排序以稳定输出。
                value = node[key]  # 读取值。
                child_source = source_node.get(key) if isinstance(source_node, dict) else source_node  # 查找对应来源。
                prefix = " " * indent  # 根据缩进生成前缀空格。
                if isinstance(value, dict):  # 嵌套字典需要递归渲染。
                    header = f"{prefix}{key}:"  # 构造键行。
                    if include_sources and isinstance(child_source, str):  # 若需要显示来源且为叶子标签。
                        header += f"  # {child_source}"  # 附加注释。
                    lines.append(header)  # 写入当前键。
                    lines.extend(_render(value, child_source, indent + 2))  # 递归追加子层输出。
                else:
                    rendered = yaml.safe_dump(value, default_flow_style=True).strip()  # 使用 PyYAML 渲染标量或列表。
                    line = f"{prefix}{key}: {rendered}"  # 构造完整行。
                    if include_sources and isinstance(child_source, str):  # 根据需要附加来源注释。
                        line += f"  # {child_source}"  # 加注释。
                    lines.append(line)  # 记录行文本。
        else:  # 标量根节点的兜底分支（通常不会触发）。
            rendered = yaml.safe_dump(node, default_flow_style=True).strip()  # 渲染值。
            line = (" " * indent) + rendered  # 构造行。
            if include_sources and isinstance(source_node, str):  # 若存在来源则附加。
                line += f"  # {source_node}"  # 添加注释。
            lines.append(line)  # 记录。
        return lines  # 返回当前层级的行列表。

    rendered_lines = _render(bundle.config, bundle.sources, 0)  # 调用递归渲染整个配置。
    return "\n".join(rendered_lines) + "\n"  # 拼接为文本并确保末尾换行。


def save_config(bundle: ConfigBundle, path: str | os.PathLike[str], include_sources: bool = True) -> None:
    """将配置快照写入目标路径，使用原子写入避免半成品。"""  # 导出函数说明。

    text = render_effective_config(bundle, include_sources=include_sources)  # 先渲染为 YAML 文本。
    atomic_write_text(path, text)  # 使用原子写入保障一致性。
