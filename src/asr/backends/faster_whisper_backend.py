# noqa: D205,D400
"""提供 Round 8 的 faster-whisper 推理实现：生成段级与词级结果。"""  # 文件顶层说明。
# 导入 dataclasses.asdict 以便将解码选项转换为字典写入元信息。 
from dataclasses import asdict  # noqa: F401
# 导入 dataclasses.dataclass 用于声明轻量配置数据结构。 
from dataclasses import dataclass  # noqa: F401
# 导入 logging 以输出调试日志与降级提示。 
import logging  # noqa: F401
# 导入 math 以在置信度降级时执行指数运算。 
import math  # noqa: F401
# 导入 pathlib.Path 统一处理文件路径。 
from pathlib import Path  # noqa: F401
# 导入 typing 中的 Dict、List、Optional 以提供清晰的类型注释。 
from typing import Dict, List, Optional  # noqa: F401

# 导入音频工具函数，复用扩展名校验与时长探测逻辑。 
from src.utils.audio import is_audio_path, probe_duration  # noqa: F401
# 导入文本规范化与切分工具，用于词级降级策略。 
from src.utils.textnorm import normalize_punct, reconcile_tokens_to_words, split_words_for_lang  # noqa: F401
# 导入统一的接口基类，保证与其他后端兼容。 
from .base import ITranscriber  # noqa: F401

# 初始化模块级日志器，方便 verbose 模式记录额外信息。 
LOGGER = logging.getLogger(__name__)
# 定义浮点误差上限，在修正时间戳时复用。 
EPSILON = 1e-3


# 使用 dataclass 封装推理参数，便于序列化存档。 
@dataclass
class DecodeOptions:
    """保存传给 faster-whisper 的主要解码设置。"""  # 数据类说明。

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


# 定义专用异常，帮助上层区分 faster-whisper 的初始化或推理问题。 
class FasterWhisperBackendError(RuntimeError):
    """在 faster-whisper 初始化或推理阶段出现的可恢复错误。"""  # 异常说明。


# 声明核心转写器，实现真实的 faster-whisper 推理流程。 
class FasterWhisperTranscriber(ITranscriber):
    """封装模型加载、音频校验与段/词级结果生成。"""  # 类说明。

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
        """导入 faster-whisper、加载模型并记录推理选项。"""  # 构造函数说明。
        # 调用父类构造函数保存公共字段及额外参数。
        super().__init__(model=model, language=language, compute_type=compute_type, device=device, **kwargs)
        # 延迟导入 faster_whisper，以便捕获 ImportError 并提示用户安装依赖。
        try:
            from faster_whisper import WhisperModel, __version__ as fw_version  # type: ignore[attr-defined]
        except ImportError as exc:  # noqa: F401
            # 抛出带指引的异常，引导用户执行安装脚本或手动安装依赖。
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
            "vad_parameters": None,  # Round 8 仍未开放自定义 VAD 细节。
            "chunk_length": chunk_length_s,
            "best_of": best_of,
            "patience": patience,
            "condition_on_previous_text": True,  # 保持跨段上下文一致性。
            "word_timestamps": True,  # 关键设置：启用词级时间戳。
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
        """返回 WhisperModel 可接受的模型名称或绝对路径。"""  # 函数说明。
        # 将模型名转换为 Path 并展开用户目录，以兼容 ~ 前缀。
        candidate_path = Path(model_name).expanduser()
        # 若路径存在（目录或文件），返回其绝对路径。
        if candidate_path.exists():
            return str(candidate_path.resolve())
        # 若路径不存在，则视为官方预置模型名称。
        return model_name

    # 将 faster-whisper 提供的词对象转换为标准字典结构。
    def _normalize_word(
        self,
        word_obj,
        segment_start: float,
        segment_end: float,
        segment_id: int,
        index: int,
        fallback_conf: Optional[float],
        language: str,
        last_end: float,
    ) -> tuple[Optional[dict], float, bool, bool]:
        """处理单个词并返回标准化结果与状态标记。"""  # 函数说明。
        # 初始化状态标记：用于记录是否发生时间裁剪或附着标点。
        clipped = False
        merged_into_previous = False
        # 从 word 对象读取原始文本，faster-whisper 默认在前面携带空格。
        raw_text = getattr(word_obj, "word", "") or ""
        # 去除换行并执行标点规范化，避免混合宽度导致判断失败。
        normalized_text = normalize_punct(raw_text.replace("\n", " ").strip())
        # 若文本为空则直接跳过（例如仅包含空格或控制字符）。
        if not normalized_text:
            return None, last_end, clipped, merged_into_previous
        # 尝试从词对象读取起止时间，若缺失则使用段时间作为兜底。
        start = getattr(word_obj, "start", None)
        end = getattr(word_obj, "end", None)
        # 将缺失的时间替换为段界，保证结果存在。
        if start is None:
            start = segment_start
        if end is None:
            end = segment_end
        # 将时间转换为 float，确保可序列化为 JSON。
        start_f = float(start)
        end_f = float(end)
        # 如果时间超出段界，则裁剪并记录状态。
        if start_f < segment_start - EPSILON:
            start_f = segment_start
            clipped = True
        if end_f > segment_end + EPSILON:
            end_f = segment_end
            clipped = True
        # 若起止时间逆序，进行最小修正。
        if end_f < start_f:
            end_f = start_f
        # 确保与上一词单调递增，必要时将起点推至 last_end。
        if start_f < last_end - EPSILON:
            start_f = last_end
            if end_f < start_f:
                end_f = start_f
            clipped = True
        # 读取概率值作为置信度，若缺失则使用段级兜底。
        confidence = getattr(word_obj, "probability", None)
        if confidence is None and fallback_conf is not None:
            confidence = fallback_conf
        # 组装词级条目。
        word_entry = {
            "text": normalized_text,
            "start": start_f,
            "end": end_f,
            "confidence": confidence,
            "segment_id": segment_id,
            "index": index,
        }
        # 返回条目、新的 last_end 以及状态标记。
        return word_entry, end_f, clipped, merged_into_previous

    # 在缺失词级信息时，根据文本内容生成近似的词级切分。
    def _fallback_words_for_segment(
        self,
        segment_text: str,
        segment_start: float,
        segment_end: float,
        segment_id: int,
        language: str,
        fallback_conf: Optional[float],
    ) -> tuple[List[dict], bool]:
        """通过文本切分与线性插值构造词级条目。"""  # 函数说明。
        # 先规范化文本，减少全角符号干扰。
        normalized_text = normalize_punct(segment_text.strip())
        # 调用语言相关的切分函数获取候选词列表。
        tokens = split_words_for_lang(normalized_text, language or "")
        # 若切分结果为空，则使用完整文本作为唯一词单元。
        if not tokens and normalized_text:
            tokens = [normalized_text]
        # 再通过 reconcile_tokens_to_words 预留未来的子词合并能力。
        words = reconcile_tokens_to_words(tokens, language or "")
        # 若仍为空，则直接返回空列表并声明未裁剪。
        if not words:
            return [], False
        # 计算总时长，并避免出现负值。
        duration = max(segment_end - segment_start, 0.0)
        # 若时长为 0，则所有词使用相同的时间戳。
        if duration <= 0:
            generated = []
            for idx, token in enumerate(words):
                generated.append(
                    {
                        "text": token,
                        "start": segment_start,
                        "end": segment_start,
                        "confidence": fallback_conf,
                        "segment_id": segment_id,
                        "index": idx,
                    }
                )
            return generated, False
        # 根据词的长度按比例分配时间片，字符越多占比越大。
        lengths = [max(len(token), 1) for token in words]
        total = float(sum(lengths))
        # 避免除零错误，如总长度为 0 则等分时间。
        if total <= 0:
            total = float(len(words))
            lengths = [1.0] * len(words)
        # 构建累计时间，确保单调。
        generated_words: List[dict] = []
        cursor = segment_start
        clipped = False
        for idx, (token, length) in enumerate(zip(words, lengths)):
            # 计算该词占用的时间比例。
            proportion = float(length) / total
            # 对最后一个词强制对齐段末，以避免浮点累计误差。
            if idx == len(words) - 1:
                start_time = cursor
                end_time = segment_end
            else:
                span = duration * proportion
                start_time = cursor
                end_time = min(segment_end, cursor + span)
            # 若出现数值误差导致起点超过终点，则进行修正。
            if end_time < start_time:
                end_time = start_time
                clipped = True
            # 将当前词写入结果列表。
            generated_words.append(
                {
                    "text": token,
                    "start": start_time,
                    "end": end_time,
                    "confidence": fallback_conf,
                    "segment_id": segment_id,
                    "index": idx,
                }
            )
            # 更新游标，确保下一词时间递增。
            cursor = end_time
        # 返回生成的词列表以及是否发生裁剪。
        return generated_words, clipped

    # 实现 ITranscriber 约定的文件转写逻辑，输出段级结构。
    def transcribe_file(self, input_path: str) -> Dict[str, object]:
        """调用 faster-whisper 对音频文件进行写并生成段/词级 JSON 结构。"""  # 函数说明。
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
        # 调用 faster-whisper 执行推理，启用 word_timestamps 获取词级结果。
        segments_iter, info = self._model.transcribe(
            str(file_path),
            language=language_arg,
            **{k: v for k, v in self._transcribe_kwargs.items() if v is not None},
        )
        # 将生成器转换为列表，便于多次遍历并序列化为 JSON。
        segments = list(segments_iter)
        # 推断语言：优先使用模型检测结果，其次使用手动指定。
        detected_language = getattr(info, "language", None) or self.language
        # 准备收集所有段级结构与词级结构。
        normalized_segments: List[Dict[str, object]] = []
        all_words: List[Dict[str, object]] = []
        # 记录是否出现词时间被裁剪或使用降级策略，便于写入 meta。
        clipped_segments: List[int] = []
        fallback_segments: List[int] = []
        # 遍历每个段对象，转换为统一结构。
        for segment in segments:
            # 解析段级字段并确保类型统一。
            segment_id = int(getattr(segment, "id", len(normalized_segments)))
            segment_start = float(getattr(segment, "start", 0.0) or 0.0)
            segment_end = float(getattr(segment, "end", segment_start) or segment_start)
            segment_text = str(getattr(segment, "text", ""))
            # 估计段级置信度，优先使用 avg_logprob 将其指数化至 (0,1)。
            avg_logprob = getattr(segment, "avg_logprob", None)
            segment_confidence = None
            if avg_logprob is not None:
                segment_confidence = math.exp(float(avg_logprob))
            # 尝试从 faster-whisper 的词结果构建词级数组。
            segment_words_raw = getattr(segment, "words", None) or []
            segment_words: List[Dict[str, object]] = []
            last_end = segment_start
            # 标记当前段是否需要降级。
            used_fallback = False
            # 遍历词对象并规范化。
            for idx, word_obj in enumerate(segment_words_raw):
                normalized_word, last_end, clipped, _ = self._normalize_word(
                    word_obj,
                    segment_start,
                    segment_end,
                    segment_id,
                    idx,
                    segment_confidence,
                    detected_language,
                    last_end,
                )
                if normalized_word is None:
                    continue
                if clipped:
                    clipped_segments.append(segment_id)
                segment_words.append(normalized_word)
            # 若模型未返回词级结果，则执行降级切分。
            if not segment_words:
                fallback_words, clipped = self._fallback_words_for_segment(
                    segment_text,
                    segment_start,
                    segment_end,
                    segment_id,
                    detected_language,
                    segment_confidence,
                )
                if fallback_words:
                    segment_words = fallback_words
                    used_fallback = True
                    if clipped:
                        clipped_segments.append(segment_id)
                if used_fallback:
                    fallback_segments.append(segment_id)
            # 在词数组存在时校验单调性并做微调。
            if segment_words:
                previous_end = segment_start
                for word in segment_words:
                    if word["start"] < previous_end - EPSILON:
                        word["start"] = previous_end
                    if word["end"] < word["start"]:
                        word["end"] = word["start"]
                    previous_end = word["end"]
            # 更新词索引，使其在段内连续且自 0 起步。
            for new_idx, word in enumerate(segment_words):
                word["index"] = new_idx
            # 将段内词汇追加到总词表中。
            all_words.extend(segment_words)
            # 计算段级平均置信度，若词级存在则取均值。
            confidences = [w["confidence"] for w in segment_words if w.get("confidence") is not None]
            avg_conf = None
            if confidences:
                avg_conf = sum(confidences) / len(confidences)
            elif segment_confidence is not None:
                avg_conf = segment_confidence
            # 将段对象转换为字典并附带词数组。
            normalized_segments.append(
                {
                    "id": segment_id,
                    "text": segment_text.strip(),
                    "start": segment_start,
                    "end": segment_end,
                    "avg_conf": avg_conf,
                    "words": segment_words,
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
        # 组装元数据：包含检测到的语言、探测时长与解码参数以及词级状态。
        meta = {
            "decode_options": asdict(self.decode_options),
            "detected_language": getattr(info, "language", None),
            "duration_from_probe": duration,
            "note": "generated by faster-whisper round8",
            "word_time_clipped_segments": sorted(set(clipped_segments)),
            "word_fallback_segments": sorted(set(fallback_segments)),
        }
        # 返回统一结构，供 pipeline 落盘使用；包含段级与词级数组。
        return {
            "language": detected_language,
            "duration_sec": duration,
            "backend": backend_info,
            "segments": normalized_segments,
            "words": all_words,
            "meta": meta,
        }
