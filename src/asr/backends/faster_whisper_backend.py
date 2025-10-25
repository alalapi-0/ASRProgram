"""提供 Round 7 的 faster-whisper 真实推理实现（段级输出，词级下一轮接入）。"""  # 文件顶层说明。
# 导入 dataclasses.asdict 以在记录解码参数时生成字典副本。
from dataclasses import asdict
# 导入 dataclasses.dataclass 用于声明轻量数据类。
from dataclasses import dataclass
# 导入 logging 以输出调试与性能建议。
import logging
# 导入 pathlib.Path 统一处理路径解析。
from pathlib import Path
# 导入 typing 中的 Dict、List、Optional 作为类型注释辅助。
from typing import Dict, List, Optional

# 导入音频工具，以复用扩展名校验与时长探测。
from src.utils.audio import is_audio_path, probe_duration
# 导入统一的接口基类，确保与其他后端的 API 一致。
from .base import ITranscriber

# 初始化模块级日志器，便于在 verbose 模式下输出信息。
LOGGER = logging.getLogger(__name__)


# 使用 dataclass 封装推理时传入的关键参数，方便写入 meta。
@dataclass
class DecodeOptions:
    """保存传给 faster-whisper 的主要解码设置。"""

    # beam search 的宽度，影响精度与速度。
    beam_size: int
    # 温度参数，控制采样多样性（当前默认 0）。
    temperature: float
    # 是否启用 VAD 过滤（本轮仅记录）。
    vad_filter: bool
    # 分块长度（秒），None 表示采用默认值。
    chunk_length_s: Optional[float]
    # best_of 参数用于采样模式的候选数量，此处仅保留占位。
    best_of: Optional[int]
    # patience 参数用于 beam search 的提前停止阈值，占位记录。
    patience: Optional[float]


# 定义专用异常，帮助上层区分 faster-whisper 的输入或加载问题。
class FasterWhisperBackendError(RuntimeError):
    """在 faster-whisper 初始化或推理阶段出现的可恢复错误。"""


# 声明核心转写器，实现真实的 faster-whisper 推理流程。
class FasterWhisperTranscriber(ITranscriber):
    """封装模型加载、音频校验与段级结果生成。"""

    # 在构造阶段初始化模型与推理参数。
    def __init__(
        self,
        model: str | None = None,
        language: str = "auto",
        compute_type: str = "auto",
        device: str = "auto",
        beam_size: int = 5,
        temperature: float = 0.0,
        vad_filter: bool = False,
        chunk_length_s: float | None = None,
        best_of: int | None = None,
        patience: float | None = None,
        **kwargs,
    ) -> None:
        """导入 faster-whisper、加载模型并记录推理选项。"""
        # 调用父类构造函数保存公共字段及额外参数。
        super().__init__(model=model, language=language, compute_type=compute_type, device=device, **kwargs)
        # 延迟导入 faster_whisper，以便捕获 ImportError 并提示用户安装依赖。
        try:
            from faster_whisper import WhisperModel, __version__ as fw_version  # type: ignore
        except ImportError as exc:  # noqa: F401
            # 抛出带指引的异常，引导用户执行 Round 5 的安装脚本或手动安装依赖。
            raise FasterWhisperBackendError(
                "未检测到 faster-whisper，请运行 scripts/setup.sh 或 pip install -r requirements.txt"
            ) from exc
        # 将 faster-whisper 版本保存到实例属性，以便输出到 JSON 元信息中。
        self.faster_whisper_version: str = fw_version
        # 记录 compute_type，便于 verbose 日志与元信息展示。
        self.compute_type: str = compute_type
        # 记录设备配置，允许 auto/cpu/cuda 等取值。
        self.device: str = device
        # 若未指定模型名称，则回退到 medium（与默认配置一致）。
        if self.model_name is None:
            self.model_name = "medium"
        # 解析模型名称或路径，优先返回本地目录的绝对路径。
        resolved_model = self._resolve_model_path(self.model_name)
        # 将核心解码参数封装成数据类，后续写入 meta 供审计。
        self.decode_options = DecodeOptions(
            beam_size=beam_size,
            temperature=temperature,
            vad_filter=vad_filter,
            chunk_length_s=chunk_length_s,
            best_of=best_of,
            patience=patience,
        )
        # 预构建传递给 transcribe() 的参数字典，过滤 None 以避免覆盖默认行为。
        self._transcribe_kwargs = {
            "beam_size": beam_size,
            "temperature": temperature,
            "vad_filter": vad_filter,
            "vad_parameters": None,  # Round 7 暂未开放自定义 VAD 细节。
            "chunk_length": chunk_length_s,
            "best_of": best_of,
            "patience": patience,
            "condition_on_previous_text": True,  # 保持跨段上下文一致性。
        }
        # 尝试构造 WhisperModel，如失败则给出模型路径与 compute_type 的排障建议。
        try:
            self._model = WhisperModel(
                resolved_model,
                device=device,
                compute_type=compute_type,
            )
        except Exception as exc:  # noqa: BLE001
            # 提供友好的错误提示，提醒用户重新下载或调整 compute_type/device。
            raise FasterWhisperBackendError(
                "无法加载 faster-whisper 模型，请确认路径存在且 compute_type/device 组合受支持。"
                " 如有需要，可重新执行 scripts/download_model.py --force"
            ) from exc
        # 记录实际使用的模型标识（可能是绝对路径或模型名）。
        self.model_path_or_name = str(resolved_model)
        # 在详细日志模式下给出性能调优建议，帮助用户选择合适的 compute_type。
        LOGGER.debug(
            "FasterWhisper 模型加载完成 model=%s device=%s compute_type=%s", self.model_path_or_name, device, compute_type
        )
        LOGGER.debug("提示: compute_type='int8_float16' 能显著降低内存占用；Apple Silicon 可尝试 'float16'。")
        LOGGER.debug("如在 Windows CPU 上速度较慢，可将 compute_type 设为 'int8' 并将 beam_size 调小。")

    # 提供内部辅助函数，用于判断模型名称是否指向本地路径。
    def _resolve_model_path(self, model_name: str) -> str:
        """返回 WhisperModel 可接受的模型名称或绝对路径。"""
        # 将模型名转换为 Path 并展开用户目录，以兼容 ~ 前缀。
        candidate_path = Path(model_name).expanduser()
        # 若路径存在（目录或文件），返回其绝对路径。
        if candidate_path.exists():
            return str(candidate_path.resolve())
        # 若路径不存在，则视为官方预置模型名称。
        return model_name

    # 实现 ITranscriber 约定的文件转写逻辑，输出段级结构。
    def transcribe_file(self, input_path: str) -> Dict[str, object]:
        """调用 faster-whisper 对音频文件进行转写并生成段级 JSON 结构。"""
        # 将字符串路径包装为 Path 对象以执行常规校验。
        file_path = Path(input_path)
        # 如果文件不存在，则抛出明确错误，由上层写入 error.txt。
        if not file_path.exists():
            raise FasterWhisperBackendError(f"音频文件不存在: {file_path}")
        # 通过工具函数校验扩展名，避免非音频文件导致推理异常。
        if not is_audio_path(file_path):
            raise FasterWhisperBackendError(f"不支持的音频扩展名: {file_path.suffix}")
        # 通过 ffprobe 探测真实时长，若失败将返回 0.0 并在日志中提示。
        duration = probe_duration(file_path)
        # 处理语言参数：auto/空字符串代表交由模型自动检测。
        language_arg = None if self.language in (None, "", "auto") else self.language
        # 调用 faster-whisper 执行推理，本轮暂未启用词级时间戳。
        segments_iter, info = self._model.transcribe(
            str(file_path),
            language=language_arg,
            **{k: v for k, v in self._transcribe_kwargs.items() if v is not None},
        )
        # 将生成器转换为列表，便于多次遍历并序列化为 JSON。
        segments = list(segments_iter)
        # 遍历模型返回的 Segment 对象，转换为标准的字典结构。
        normalized_segments: List[Dict[str, object]] = []
        for segment in segments:
            # faster-whisper 未提供显式置信度，这里将 avg_conf 设为 None 并在下一轮考虑替代指标。
            normalized_segments.append(
                {
                    "id": segment.id,
                    "text": segment.text.strip(),
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "avg_conf": None,
                    "words": [],
                }
            )
        # 构建后端信息字典，写入名称、版本、模型路径、设备与精度设置。
        backend_info = {
            "name": "faster-whisper",
            "version": self.faster_whisper_version,
            "model": self.model_path_or_name,
            "device": self.device,
            "compute_type": self.compute_type,
        }
        # 组装元数据：包含检测到的语言、探测时长与解码参数。
        meta = {
            "decode_options": asdict(self.decode_options),
            "detected_language": getattr(info, "language", None),
            "duration_from_probe": duration,
            "note": "generated by faster-whisper round7",
        }
        # 返回统一结构，供 pipeline 落盘使用；words 暂为空数组。
        return {
            "language": getattr(info, "language", None) or self.language,
            "duration_sec": duration,
            "backend": backend_info,
            "segments": normalized_segments,
            "words": [],
            "meta": meta,
        }
