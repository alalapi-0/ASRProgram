#!/usr/bin/env bash
# 注释：使用 env 查找 bash 解释器并保持跨平台兼容
set -euo pipefail  # 注释：遇到错误即退出，禁止未定义变量

# 注释：定位到仓库根目录，确保脚本在任意位置执行
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# 注释：定义版本文件路径
VERSION_FILE="${PROJECT_ROOT}/VERSION"
# 注释：读取版本号，忽略注释部分
PROJECT_VERSION="$(awk '{print $1}' "${VERSION_FILE}")"
# 注释：定义输出目录
DIST_DIR="${PROJECT_ROOT}/dist"
# 注释：设定归档文件名称
ARCHIVE_NAME="ASRProgram_v${PROJECT_VERSION}.tar.gz"
# 注释：设定归档完整路径
ARCHIVE_PATH="${DIST_DIR}/${ARCHIVE_NAME}"

# 注释：列出需要纳入归档的路径
INCLUDE_PATHS=(
  "README.md"
  "CHANGELOG.md"
  "LICENSE"
  "VERSION"
  "requirements.txt"
  "src"
  "config"
  "schemas"
  "scripts"
)

# 注释：创建 dist 目录以存放归档
mkdir -p "${DIST_DIR}"
# 注释：清理旧的归档文件，避免混淆
rm -f "${ARCHIVE_PATH}"

# 注释：检查是否存在禁止打包的二进制或模型文件
if find "${PROJECT_ROOT}" -type f \( -name '*.wav' -o -name '*.bin' -o -name '*.model' -o -name '*.gguf' \) | grep -q .; then
  echo "检测到禁止打包的二进制或模型文件，请先清理后再执行。" >&2  # 注释：提示用户清理禁用文件
  exit 1  # 注释：终止脚本执行
fi

# 注释：使用 tar 创建轻量发行包
(
  cd "${PROJECT_ROOT}"  # 注释：切换至项目根目录，保持归档结构相对路径
  tar -czf "${ARCHIVE_PATH}" "${INCLUDE_PATHS[@]}"  # 注释：压缩并打包指定路径
)

# 注释：输出归档结果供用户确认
cat <<MSG
发行包已生成：${ARCHIVE_PATH}
包含版本：${PROJECT_VERSION}
MSG
