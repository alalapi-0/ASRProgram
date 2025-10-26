# 只做结构级校验：确保 out/ 下至少有一个 *.words.json 与 *.segments.json
# 并检查关键字段存在即可；不检查语义与非空词数（因为合成哔声可能识别为空）。
import json
import sys
from pathlib import Path

def check_json_has_keys(p: Path, must_keys):
    obj = json.loads(p.read_text(encoding="utf-8"))
    for k in must_keys:
        if k not in obj:
            raise SystemExit(f"[validate] {p} missing key: {k}")

def main(out_dir: str):
    out = Path(out_dir)
    if not out.exists():
        raise SystemExit(f"[validate] out dir not found: {out}")
    words = sorted(out.rglob("*.words.json"))
    segs = sorted(out.rglob("*.segments.json"))
    if not words:
        raise SystemExit("[validate] no *.words.json produced")
    if not segs:
        raise SystemExit("[validate] no *.segments.json produced")

    # 取第一个文件做最小字段校验
    check_json_has_keys(words[0], ["schema", "audio", "backend", "words", "generated_at"])
    check_json_has_keys(segs[0], ["language", "duration_sec", "backend", "segments"])
    print(f"[validate] OK: {len(words)} words.json, {len(segs)} segments.json")

if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "out"
    main(d)
