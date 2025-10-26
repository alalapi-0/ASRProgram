# 生成一段 1.5 秒的 440Hz 正弦波 WAV，用于 CI 烟雾测试
# 不需要提交音频文件到仓库，避免二进制污染。
import sys
from pathlib import Path
import math
import wave
import struct

def main(out_path: str, sr: int = 16000, freq: float = 440.0, seconds: float = 1.5):
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(sr * seconds)
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sr)
        for i in range(n_samples):
            t = i / sr
            val = 0.2 * math.sin(2 * math.pi * freq * t)  # 0.2 防止削波
            wf.writeframes(struct.pack("<h", int(val * 32767)))
    print(f"[gen_wav] wrote {out} ({seconds}s @ {sr}Hz)")

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "tmp_audio/beep.wav"
    main(path)
