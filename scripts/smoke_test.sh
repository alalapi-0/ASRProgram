#!/usr/bin/env bash
# 启用严格模式，遇到错误立即退出并传播未定义变量。
set -euo pipefail
# 记录当前脚本所在目录，便于定位仓库根路径。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 计算仓库根目录，假定脚本位于 scripts/ 子目录。
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
# 创建临时工作目录，用于放置输入与输出文件。
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/asr-smoke-XXXXXX")"
# 注册清理函数，确保脚本结束后删除临时目录。
cleanup() {
  # 删除临时目录中的所有内容。
  rm -rf "${WORK_DIR}"
}
# 捕获 EXIT 信号执行清理逻辑。
trap cleanup EXIT
# 创建输入与输出目录结构。
INPUT_DIR="${WORK_DIR}/inputs"
OUT_DIR="${WORK_DIR}/out"
mkdir -p "${INPUT_DIR}" "${OUT_DIR}"
# 创建两个空白音频文件，模拟批量输入。
: > "${INPUT_DIR}/alpha.wav"
: > "${INPUT_DIR}/beta.wav"
# 提示用户当前正在运行的测试信息。
echo "[smoke] running dummy backend against ${INPUT_DIR}"
# 设置 PYTHONPATH 以便脚本直接导入 src 包。
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH+:${PYTHONPATH}}"
# 调用 CLI 执行 dummy 后端，启用段级输出并覆盖历史文件。
python -m src.cli.main \
  --input "${INPUT_DIR}" \
  --out-dir "${OUT_DIR}" \
  --backend dummy \
  --segments-json true \
  --overwrite true \
  --dry-run false
# 使用 Python 一行脚本加载 words.json 并执行 schema 校验。
python - <<'PY'
from pathlib import Path  # 导入 Path 以遍历输出目录。
import json  # 导入 json 以解析结果文件。
from src.utils.schema import validate_segments, validate_words  # 导入校验函数。
output_dir = Path("$OUT_DIR")  # 解析环境变量中的输出路径。
words_files = sorted(output_dir.glob("*.words.json"))  # 搜索词级文件。
segments_files = sorted(output_dir.glob("*.segments.json"))  # 搜索段级文件。
for path in words_files:  # 遍历词级文件并逐个校验。
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_words(payload)
for path in segments_files:  # 遍历段级文件并逐个校验。
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_segments(payload)
print(f"OK: validated {len(words_files)} words JSON and {len(segments_files)} segments JSON")  # 输出成功提示。
PY
# 打印最终成功消息，包括输出目录位置。
echo "[smoke] success - artifacts stored in ${OUT_DIR}"
