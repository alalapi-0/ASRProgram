"""Round 13 配置系统的层级合并与校验测试集合。"""  # 模块说明。
from __future__ import annotations  # 启用前向注解支持类型提示。

from pathlib import Path  # 导入 Path 以构造临时配置文件与输出路径。

import sys  # 导入 sys 以动态调整模块搜索路径。

sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将仓库根目录加入 sys.path 以导入 src.* 模块。

import pytest  # 导入 pytest 以使用夹具与断言辅助。

from src.utils.config import (  # 导入配置工具函数以供测试使用。
    ConfigError,
    load_and_merge_config,
    parse_cli_set_items,
    render_effective_config,
    save_config,
)


def _write_yaml(path: Path, text: str) -> None:
    """辅助函数：将 YAML 字符串写入指定路径。"""  # 函数说明。
    path.write_text(text, encoding="utf-8")  # 以 UTF-8 写出文本。


def test_layer_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """验证默认→用户→ENV→CLI 的覆盖顺序。"""  # 测试说明。
    user_cfg = tmp_path / "user.yaml"  # 用户配置路径。
    _write_yaml(
        user_cfg,
        """runtime:
  backend: faster-whisper
  device: cpu
  beam_size: 2
out_dir: ./custom
""",
    )  # 写入用户层配置。
    monkeypatch.setenv("ASRPROGRAM_RUNTIME__DEVICE", "cuda")  # 环境层将 device 覆盖为 cuda。
    monkeypatch.setenv("ASRPROGRAM_RUNTIME__LANGUAGE", "ja")  # 环境层设置语言为 ja。
    cli_overrides = {"runtime": {"backend": "whisper.cpp"}}  # CLI 显式切换 backend。
    cli_sets = parse_cli_set_items(["runtime.beam_size=6", "skip_done=false"])  # --set 覆盖 beam_size 与 skip_done。
    bundle = load_and_merge_config(
        cli_overrides=cli_overrides,
        cli_set_overrides=cli_sets,
        config_path=str(user_cfg),
    )  # 加载并合并配置。
    runtime = bundle.config["runtime"]  # 读取运行时配置。
    assert runtime["backend"] == "whisper.cpp"  # CLI 覆盖最高优先级。
    assert runtime["device"] == "cuda"  # 环境变量覆盖用户配置。
    assert runtime["beam_size"] == 6  # --set 覆盖 env 与用户层。
    assert runtime["language"] == "ja"  # 环境变量覆盖默认 auto。
    assert bundle.config["skip_done"] is False  # --set 影响顶层布尔开关。
    assert bundle.config["out_dir"] == "./custom"  # 用户配置覆盖默认 out_dir。


def test_input_output_paths_forced_lowercase(tmp_path: Path) -> None:
    """输入与输出目录在规范化后应当被强制转为小写。"""  # 测试说明。
    user_cfg = tmp_path / "paths.yaml"  # 用户配置路径。
    _write_yaml(
        user_cfg,
        """input: ./SampleS
out_dir: ./OutputDir
""",
    )  # 写入包含大写字母的目录路径。
    bundle = load_and_merge_config(config_path=str(user_cfg))  # 加载配置执行规范化。
    assert bundle.config["input"] == "./samples"  # 输入路径被转换为小写。
    assert bundle.config["out_dir"] == "./outputdir"  # 输出目录同样被转换为小写。


def test_profile_application_and_override(tmp_path: Path) -> None:
    """验证 profile 预设能生效且后续 --set 可继续覆盖。"""  # 测试说明。
    bundle = load_and_merge_config(
        cli_set_overrides=parse_cli_set_items(["runtime.beam_size=2"]),
        profile_name="cpu-fast",
    )  # 选择 cpu-fast profile 并调整 beam_size。
    runtime = bundle.config["runtime"]  # 读取运行时配置。
    assert runtime["device"] == "cpu"  # profile 将 device 固定为 CPU。
    assert runtime["compute_type"] == "int8"  # profile 设置低精度。
    assert runtime["beam_size"] == 2  # --set 覆盖 profile 中的 beam_size。
    assert bundle.config["meta"]["profile"] == "cpu-fast"  # meta 中记录生效的 profile 名称。


def test_env_file_support(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """验证同目录 .env 会被解析并应用。"""  # 测试说明。
    config_dir = tmp_path / "cfg"  # 创建配置目录。
    config_dir.mkdir()  # 创建目录。
    user_cfg = config_dir / "user.yaml"  # 用户配置路径。
    _write_yaml(user_cfg, "runtime:\n  backend: faster-whisper\n")  # 写入最简配置。
    env_file = config_dir / ".env"  # 同目录 .env。
    env_file.write_text("ASRPROGRAM_RUNTIME__DEVICE=cpu\n", encoding="utf-8")  # 在 .env 指定 device。
    monkeypatch.delenv("ASRPROGRAM_RUNTIME__DEVICE", raising=False)  # 确保真实环境中无同名变量。
    bundle = load_and_merge_config(config_path=str(user_cfg))  # 加载配置。
    assert bundle.config["runtime"]["device"] == "cpu"  # .env 覆盖生效。


def test_validation_failure(tmp_path: Path) -> None:
    """非法取值应抛出 ConfigError 并包含信息。"""  # 测试说明。
    bad_cfg = tmp_path / "bad.yaml"  # 错误配置路径。
    _write_yaml(bad_cfg, "runtime:\n  beam_size: 0\n")  # 写入非法 beam_size。
    with pytest.raises(ConfigError) as exc:  # 期待抛出配置异常。
        load_and_merge_config(config_path=str(bad_cfg))  # 加载配置触发校验。
    assert "beam_size" in str(exc.value)  # 异常消息包含字段名。


def test_render_and_save_snapshot(tmp_path: Path) -> None:
    """render_effective_config 与 save_config 应生成 YAML 文本。"""  # 测试说明。
    bundle = load_and_merge_config(profile_name="balanced")  # 选择 balanced profile。
    snapshot = render_effective_config(bundle, include_sources=True)  # 渲染配置。
    assert "profile" in snapshot  # 输出包含 profile 字段。
    target_path = tmp_path / "snapshot.yaml"  # 快照文件路径。
    save_config(bundle, target_path)  # 保存配置快照。
    saved_text = target_path.read_text(encoding="utf-8")  # 读取文件内容。
    assert "profile" in saved_text  # 保存的文件同样包含 profile 字段。


def test_cli_backend_override() -> None:
    """验证 CLI 覆盖可切换后端名称。"""  # 测试说明。
    bundle = load_and_merge_config(cli_overrides={"runtime": {"backend": "whisper.cpp"}})  # CLI 强制选择 whisper.cpp。
    assert bundle.config["runtime"]["backend"] == "whisper.cpp"  # 覆盖生效。
