"""提供 whisper.cpp 后端的真实执行与输出解析能力。"""  # 文件文档字符串描述模块职责。
# 导入 json 模块用于解析 whisper.cpp 生成的 JSON 输出。
import json
# 导入 logging 以记录命令执行与降级过程中的调试信息。
import logging
# 导入 os 模块以便进行权限校验和路径字符串转换。
import os
# 导入 shlex 以生成安全的命令调试字符串。
import shlex
# 导入 subprocess 以执行 whisper.cpp 可执行文件。
import subprocess
# 导入 dataclasses 中的 dataclass 便于描述解析结果的中间结构。
from dataclasses import dataclass
# 导入 pathlib.Path 统一管理跨平台路径处理。
from pathlib import Path
# 导入 typing 所需的类型别名以提升可读性。
from typing import List, Optional, Tuple

# 导入音频工具函数用于校验输入文件与获取时长信息。
from src.utils.audio import is_audio_path, probe_duration
# 导入文本工具以便在缺失词级输出时进行简单切词兜底。
from src.utils.textnorm import normalize_punct, split_words_for_lang
# 导入接口基类确保与其他后端保持一致的 API。
from .base import ITranscriber

# 初始化模块级日志记录器，便于在 verbose 模式下调试命令执行流程。
LOGGER = logging.getLogger(__name__)
# 定义浮点修正阈值，用于校验时间戳的单调性。
EPSILON = 1e-3


# 定义自定义异常，便于上层捕获 whisper.cpp 运行时的错误并输出提示。
class WhisperCppBackendError(RuntimeError):
    """包装 whisper.cpp 命令执行失败或输出无法解析的情况。"""


# 使用 dataclass 记录解析过程中产生的词级信息，便于重建段结构。
@dataclass
class ParsedWord:
    """保存单个词条的文本、时间与置信度信息。"""

    # 词语内容。
    text: str
    # 起始时间。
    start: float
    # 结束时间。
    end: float
    # 置信度，允许为空表示缺失。
    confidence: Optional[float]
    # 所属段编号，便于后续聚合。
    segment_id: int
    # 在所属段内的索引。
    index: int


# 定义帮助函数用于安全地转换字符串为浮点数。
def _safe_float(value: object, default: float = 0.0) -> float:
    """尝试将输入转换为 float，失败时返回默认值。"""

    # 当值已为 float 或 int 时直接返回 float 形式。
    if isinstance(value, (int, float)):
        return float(value)
    # 当值为字符串时尝试去除空白并解析。
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    # 其他类型直接返回默认值。
    return default


# 定义帮助函数用于安全地解析置信度。
def _safe_confidence(value: object) -> Optional[float]:
    """将多样化字段转换为 0~1 范围的置信度，失败时返回 None。"""

    # None 直接返回以表示缺失。
    if value is None:
        return None
    # 可直接转换为 float 的类型进行解析。
    if isinstance(value, (int, float)):
        return float(value)
    # 字符串尝试剥离空白并转换。
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    # 其他类型视为缺失。
    return None


# 定义帮助函数，确保词级时间戳在段内单调且位于段界范围。
def _enforce_time_monotonic(words: List[ParsedWord], seg_start: float, seg_end: float) -> None:
    """对词级时间戳进行修正，避免出现逆序或越界。"""

    # 初始化上一词的结束时间，初始值使用段起点。
    last_end = seg_start
    # 遍历所有词条逐一修正。
    for word in words:
        # 若词开始时间早于段起点则裁剪。
        if word.start < seg_start - EPSILON:
            word.start = seg_start
        # 若词开始时间小于上一词结束时间则推进到上一词结束。
        if word.start < last_end - EPSILON:
            word.start = last_end
        # 若词结束时间早于起始则对齐起始时间。
        if word.end < word.start:
            word.end = word.start
        # 若词结束时间超过段终点则裁剪。
        if word.end > seg_end + EPSILON:
            word.end = seg_end
        # 将上一词结束时间更新为当前词结束，确保后续单调。
        last_end = word.end
    # 若最后一个词结束时间与段终点存在较大差距，可在此保留差异供上层处理。


# 定义帮助函数，用于在缺失词级输出时基于段文本生成占位词。
def _fallback_words_from_segment(seg_id: int, text: str, start: float, end: float, lang: str) -> List[ParsedWord]:
    """当 whisper.cpp 未返回 words 字段时，基于文本生成兜底词条。"""

    # 先执行简单的标点规范化，避免字符串中包含不可见字符。
    normalized = normalize_punct(text)
    # 使用语言相关的分词策略拆分文本。
    tokens = split_words_for_lang(normalized, lang)
    # 若拆分结果为空则退回一个整体词条。
    if not tokens:
        tokens = [normalized] if normalized else []
    # 若仍为空，返回空列表表示无词条。
    if not tokens:
        return []
    # 根据词数量在段内平均分配时间。
    duration = max(end - start, 0.0)
    step = duration / max(len(tokens), 1)
    # 初始化词集合。
    words: List[ParsedWord] = []
    # 遍历 tokens 构造词条。
    for index, token in enumerate(tokens):
        token_start = start + step * index
        token_end = start + step * (index + 1) if index < len(tokens) - 1 else end
        words.append(ParsedWord(text=token, start=token_start, end=token_end, confidence=None, segment_id=seg_id, index=index))
    # 返回构造好的词列表。
    return words


# 定义解析 JSON 输出的函数，供主流程和单测调用。
def parse_whisper_cpp_json_output(raw: str, language_hint: str = "auto") -> Tuple[List[dict], str, dict]:
    """解析 whisper.cpp --output-json 输出为标准段结构。"""

    # 尝试找到第一个 "{" 与最后一个 "}" 以应对日志前缀。
    start_idx = raw.find("{")
    end_idx = raw.rfind("}")
    # 若无法找到 JSON 包裹符号则抛出异常。
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise WhisperCppBackendError("whisper.cpp JSON 输出缺少对象包裹结构。")
    # 截取可能包含 JSON 的子串。
    json_payload = raw[start_idx : end_idx + 1]
    # 解析 JSON，失败时转换为异常供上层捕获。
    try:
        data = json.loads(json_payload)
    except json.JSONDecodeError as exc:  # noqa: F841
        raise WhisperCppBackendError("无法解析 whisper.cpp JSON 输出，请检查版本是否支持 --output-json。") from exc
    # whisper.cpp 可能输出对象或数组，这里统一转换为 segments 列表。
    if isinstance(data, dict):
        segments_raw = data.get("segments", [])
        detected_lang = data.get("language", language_hint)
    elif isinstance(data, list):
        segments_raw = data
        detected_lang = language_hint
    else:
        raise WhisperCppBackendError("未识别的 JSON 结构，应为对象或数组。")
    # 初始化标准段列表。
    segments: List[dict] = []
    # 遍历每个 segment 对象并进行标准化。
    for seg_index, seg in enumerate(segments_raw):
        # 读取段文本与时间戳。
        seg_text = seg.get("text", "") if isinstance(seg, dict) else ""
        seg_start = _safe_float(seg.get("start"), 0.0) if isinstance(seg, dict) else 0.0
        seg_end = _safe_float(seg.get("end"), seg_start) if isinstance(seg, dict) else seg_start
        # 初始化词级数据容器。
        words: List[ParsedWord] = []
        # 当段中包含 words 列表时进行详细解析。
        if isinstance(seg, dict) and isinstance(seg.get("words"), list):
            for word_index, word in enumerate(seg["words"]):
                if not isinstance(word, dict):
                    continue
                raw_text = word.get("word") or word.get("text") or word.get("token") or ""
                cleaned_text = normalize_punct(str(raw_text).strip())
                if not cleaned_text:
                    continue
                word_start = _safe_float(word.get("start"), seg_start)
                word_end = _safe_float(word.get("end"), seg_end)
                confidence = _safe_confidence(
                    word.get("probability")
                    or word.get("prob")
                    or word.get("p")
                    or word.get("confidence")
                )
                words.append(
                    ParsedWord(
                        text=cleaned_text,
                        start=word_start,
                        end=word_end,
                        confidence=confidence,
                        segment_id=seg_index,
                        index=len(words),
                    )
                )
        # 若 words 为空则回退到文本分词策略。
        if not words:
            words = _fallback_words_from_segment(seg_index, seg_text, seg_start, seg_end, detected_lang)
        # 确保时间戳合理。
        _enforce_time_monotonic(words, seg_start, seg_end)
        # 计算段级平均置信度。
        confidences = [w.confidence for w in words if w.confidence is not None]
        avg_conf = sum(confidences) / len(confidences) if confidences else None
        # 构造段级字典并追加到结果列表。
        segments.append(
            {
                "id": seg_index,
                "text": seg_text.strip(),
                "start": seg_start,
                "end": seg_end,
                "avg_conf": avg_conf,
                "words": [
                    {
                        "text": word.text,
                        "start": word.start,
                        "end": word.end,
                        "confidence": word.confidence,
                        "segment_id": word.segment_id,
                        "index": word.index,
                    }
                    for word in words
                ],
            }
        )
    # 返回解析完成的段列表、检测到的语言以及 meta 附加信息。
    return segments, detected_lang, {"raw_format": "json", "notes": "parsed-from-json"}


# 定义解析 TSV 输出的函数，兼容 --output-word-tsv 等模式。
def parse_whisper_cpp_tsv_output(raw: str, language_hint: str = "auto") -> Tuple[List[dict], str, dict]:
    """解析 whisper.cpp 生成的 TSV 文本。"""

    # 将文本拆分为行并过滤掉空行。
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    # 若无有效内容则抛出异常。
    if not lines:
        raise WhisperCppBackendError("TSV 输出为空。")
    # 定位第一行表头：若以 # 开头则去除前缀。
    header_tokens = []
    data_lines: List[List[str]] = []
    header_found = False
    for line in lines:
        if not header_found:
            candidate = line.lstrip("# ")
            parts = candidate.split("\t")
            if any(token.lower() in {"start", "end", "text", "word", "segment", "segment_id"} for token in parts):
                header_tokens = [token.strip().lower() for token in parts]
                header_found = True
                continue
        data_lines.append(line.split("\t"))
    # 若仍未找到表头则假设标准列顺序。
    if not header_tokens:
        header_tokens = ["start", "end", "word", "probability", "segment"]
    # 将表头映射为索引字典。
    column_index = {name: idx for idx, name in enumerate(header_tokens)}
    # 判定当前 TSV 是段级还是词级模式。
    mode = "word" if "word" in column_index or "token" in column_index else "segment"
    # 初始化段容器。
    segments: dict[int, dict] = {}
    # 初始化语言回退值。
    detected_lang = language_hint
    # 当 TSV 为段级模式时，直接根据每行构造段。
    if mode == "segment":
        for seg_index, parts in enumerate(data_lines):
            seg_start = _safe_float(parts[column_index.get("start", 0)] if len(parts) > column_index.get("start", 0) else 0.0)
            seg_end = _safe_float(parts[column_index.get("end", 1)] if len(parts) > column_index.get("end", 1) else seg_start)
            seg_text = parts[column_index.get("text", 2)] if len(parts) > column_index.get("text", 2) else ""
            seg_text = normalize_punct(seg_text)
            words = _fallback_words_from_segment(seg_index, seg_text, seg_start, seg_end, detected_lang)
            _enforce_time_monotonic(words, seg_start, seg_end)
            confidences = [w.confidence for w in words if w.confidence is not None]
            avg_conf = sum(confidences) / len(confidences) if confidences else None
            segments[seg_index] = {
                "id": seg_index,
                "text": seg_text.strip(),
                "start": seg_start,
                "end": seg_end,
                "avg_conf": avg_conf,
                "words": [
                    {
                        "text": word.text,
                        "start": word.start,
                        "end": word.end,
                        "confidence": word.confidence,
                        "segment_id": word.segment_id,
                        "index": word.index,
                    }
                    for word in words
                ],
            }
    else:
        # 对于词级 TSV，按 segment 列进行分组。
        for row_index, parts in enumerate(data_lines):
            if not parts:
                continue
            seg_id_token = None
            if "segment" in column_index and len(parts) > column_index["segment"]:
                seg_id_token = parts[column_index["segment"]]
            elif "segment_id" in column_index and len(parts) > column_index["segment_id"]:
                seg_id_token = parts[column_index["segment_id"]]
            seg_id = int(_safe_float(seg_id_token, default=row_index)) if seg_id_token is not None else row_index
            seg_entry = segments.setdefault(
                seg_id,
                {
                    "id": seg_id,
                    "text": "",
                    "start": None,
                    "end": None,
                    "words": [],
                },
            )
            word_token = ""
            if "word" in column_index and len(parts) > column_index["word"]:
                word_token = parts[column_index["word"]]
            elif "token" in column_index and len(parts) > column_index["token"]:
                word_token = parts[column_index["token"]]
            cleaned_text = normalize_punct(word_token.strip())
            if not cleaned_text:
                continue
            word_start = _safe_float(parts[column_index.get("start", 0)] if len(parts) > column_index.get("start", 0) else 0.0)
            word_end = _safe_float(parts[column_index.get("end", 1)] if len(parts) > column_index.get("end", 1) else word_start)
            confidence = None
            for key in ("probability", "prob", "p", "confidence"):
                if key in column_index and len(parts) > column_index[key]:
                    confidence = _safe_confidence(parts[column_index[key]])
                    if confidence is not None:
                        break
            seg_entry["words"].append(
                ParsedWord(
                    text=cleaned_text,
                    start=word_start,
                    end=word_end,
                    confidence=confidence,
                    segment_id=seg_id,
                    index=len(seg_entry["words"]),
                )
            )
            seg_entry_start = seg_entry.get("start")
            seg_entry_end = seg_entry.get("end")
            seg_entry["start"] = word_start if seg_entry_start is None else min(seg_entry_start, word_start)
            seg_entry["end"] = word_end if seg_entry_end is None else max(seg_entry_end, word_end)
            seg_entry_text = seg_entry.get("text", "")
            seg_entry["text"] = (seg_entry_text + (" " if seg_entry_text else "") + cleaned_text).strip()
        # 遍历所有段进行时间与置信度修正。
        for seg_id, seg_entry in segments.items():
            seg_start = float(seg_entry.get("start") or 0.0)
            seg_end = float(seg_entry.get("end") or seg_start)
            words: List[ParsedWord] = seg_entry["words"]
            _enforce_time_monotonic(words, seg_start, seg_end)
            confidences = [w.confidence for w in words if w.confidence is not None]
            avg_conf = sum(confidences) / len(confidences) if confidences else None
            seg_entry["avg_conf"] = avg_conf
            seg_entry["words"] = [
                {
                    "text": word.text,
                    "start": word.start,
                    "end": word.end,
                    "confidence": word.confidence,
                    "segment_id": word.segment_id,
                    "index": word.index,
                }
                for word in words
            ]
            seg_entry.setdefault("text", "")
            seg_entry["id"] = seg_id
            seg_entry["start"] = seg_start
            seg_entry["end"] = seg_end
    # 将 segments 字典转换为按 id 排序的列表。
    ordered_segments = [segments[idx] for idx in sorted(segments.keys())]
    # 确保每个段都具备 avg_conf 字段。
    for seg in ordered_segments:
        if "avg_conf" not in seg:
            confidences = [word["confidence"] for word in seg.get("words", []) if word.get("confidence") is not None]
            seg["avg_conf"] = sum(confidences) / len(confidences) if confidences else None
    # 返回段列表、语言及 meta 信息。
    return ordered_segments, detected_lang, {"raw_format": "tsv", "notes": "parsed-from-tsv"}


# 定义主类，实现命令调用与结果解析。
class WhisperCppTranscriber(ITranscriber):
    """封装 whisper.cpp 可执行文件的调用与输出解析流程。"""

    # 初始化函数接收所有运行所需的配置参数。
    def __init__(
        self,
        executable_path: str,
        model_path: str,
        language: str = "auto",
        threads: int = 0,
        beam_size: int = 5,
        temperature: float = 0.0,
        max_len: Optional[int] = None,
        prompt: Optional[str] = None,
        print_progress: bool = False,
        word_timestamps: bool = True,
        timeout_sec: Optional[float] = None,
        **kwargs,
    ) -> None:
        """保存配置并检查可执行文件/模型路径。"""

        # 调用父类构造函数记录模型标识与语言。
        super().__init__(model=model_path, language=language, **kwargs)
        # 将可执行文件路径标准化为 Path 对象。
        self.executable_path = Path(executable_path).expanduser()
        # 将模型路径标准化为 Path 对象。
        self.model_path = Path(model_path).expanduser()
        # 记录线程数配置，0 代表由 whisper.cpp 自动选择。
        self.threads = threads
        # 记录 beam search 宽度。
        self.beam_size = beam_size
        # 记录温度参数。
        self.temperature = temperature
        # 记录最大输出长度。
        self.max_len = max_len
        # 记录初始提示词。
        self.prompt = prompt
        # 记录是否打印进度条。
        self.print_progress = print_progress
        # 记录是否请求词级时间戳。
        self.word_timestamps = word_timestamps
        # 记录命令执行超时时间。
        self.timeout_sec = timeout_sec
        # 初始化版本信息缓存，避免重复执行 --version。
        self._cached_version: Optional[str] = None
        # 校验可执行文件是否存在且可执行。
        if not self.executable_path.is_file():
            raise WhisperCppBackendError(f"whisper.cpp 可执行文件不存在: {self.executable_path}")
        if not os.access(self.executable_path, os.X_OK):
            raise WhisperCppBackendError(
                f"whisper.cpp 可执行文件缺少执行权限: {self.executable_path}. 请运行 chmod +x"
            )
        # 校验模型文件是否存在。
        if not self.model_path.is_file():
            raise WhisperCppBackendError(f"whisper.cpp 模型文件不存在: {self.model_path}")

    # 定义内部函数用于获取 whisper.cpp 版本号。
    def _detect_version(self) -> str:
        """通过执行 --version 或 -h 捕获版本字符串。"""

        # 若已缓存版本，则直接返回。
        if self._cached_version is not None:
            return self._cached_version
        # 构造候选参数列表。
        candidates = [[str(self.executable_path), "--version"], [str(self.executable_path), "-h"]]
        # 遍历候选命令尝试执行。
        for command in candidates:
            try:
                completed = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            except Exception:  # noqa: BLE001
                continue
            if completed.stdout:
                first_line = completed.stdout.strip().splitlines()[0]
                if first_line:
                    self._cached_version = first_line.strip()
                    return self._cached_version
        # 若无法识别，返回 unknown。
        self._cached_version = "unknown"
        return self._cached_version

    # 定义内部函数，用于根据配置构造命令行参数。
    def _build_command(self, audio_path: Path) -> List[str]:
        """根据当前配置生成 whisper.cpp 命令列表。"""

        # 构造基础命令，包括可执行路径、模型与输入音频。
        command: List[str] = [
            str(self.executable_path),
            "-m",
            str(self.model_path),
            "-f",
            str(audio_path),
            "--language",
            self.language,
            "--word_timestamps",
            "true" if self.word_timestamps else "false",
            "--output-json",
            "--print_progress",
            "true" if self.print_progress else "false",
            "--beam_size",
            str(self.beam_size),
            "--temperature",
            str(self.temperature),
            "--threads",
            str(self.threads),
        ]
        # 当 threads 为 0 时，whisper.cpp 会自动处理，因此保留该值。
        # 当配置了最大长度时追加对应参数。
        if self.max_len is not None:
            command.extend(["--max_len", str(self.max_len)])
        # 当提供 prompt 时追加参数。
        if self.prompt:
            command.extend(["--prompt", self.prompt])
        # 返回生成的命令列表。
        return command

    # 定义内部函数，负责执行命令并捕获输出。
    def _run_command(self, command: List[str]) -> subprocess.CompletedProcess[str]:
        """执行 whisper.cpp 命令并返回 CompletedProcess。"""

        # 在日志中记录即将执行的命令。
        LOGGER.debug("执行 whisper.cpp 命令: %s", shlex.join(command))
        # 调用 subprocess.run 捕获标准输出与错误输出。
        completed = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=self.timeout_sec)
        # 当返回码非零时抛出异常并附带 stderr 信息。
        if completed.returncode != 0:
            raise WhisperCppBackendError(
                "whisper.cpp 执行失败，stderr=\n" + (completed.stderr or "<empty>")
            )
        # 返回执行结果供后续解析。
        return completed

    # 定义公共方法，实现音频文件的转写流程。
    def transcribe_file(self, input_path: str) -> dict:
        """执行 whisper.cpp 命令并将输出解析为统一结构。"""

        # 将输入路径转换为 Path 对象。
        audio_path = Path(input_path).expanduser()
        # 校验文件是否存在。
        if not audio_path.is_file():
            raise WhisperCppBackendError(f"音频文件不存在: {audio_path}")
        # 校验扩展名是否属于支持列表。
        if not is_audio_path(audio_path):
            raise WhisperCppBackendError(f"不支持的音频格式: {audio_path}")
        # 构造命令。
        command = self._build_command(audio_path)
        # 执行命令并捕获输出。
        completed = self._run_command(command)
        # 首选解析 JSON 输出，失败时回退至 TSV。
        parse_meta = {}
        try:
            segments, detected_language, meta = parse_whisper_cpp_json_output(completed.stdout, self.language)
        except WhisperCppBackendError:
            segments, detected_language, meta = parse_whisper_cpp_tsv_output(completed.stdout, self.language)
        parse_meta = meta
        # 补充 meta 中的命令信息。
        parse_meta["cmdline"] = command
        # 获取音频时长。
        duration = probe_duration(audio_path)
        # 若探测失败则尝试从 meta 中获取。
        if not duration:
            duration = max((segment.get("end", 0.0) for segment in segments), default=0.0)
        # 整理结果结构。
        result = {
            "language": detected_language or self.language,
            "duration_sec": duration,
            "backend": {
                "name": "whisper.cpp",
                "version": self._detect_version(),
                "model": str(self.model_path),
            },
            "segments": segments,
            "meta": parse_meta,
        }
        # 返回标准化结果。
        return result


# 定义对外暴露的名称以便单测直接引用解析函数。
__all__ = [
    "WhisperCppTranscriber",
    "WhisperCppBackendError",
    "parse_whisper_cpp_json_output",
    "parse_whisper_cpp_tsv_output",
]
