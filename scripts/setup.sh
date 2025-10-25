#!/usr/bin/env bash  # 指定脚本使用 bash 解释器执行。
set -euo pipefail  # 启用严格模式：遇到未定义变量或管道错误立即退出。
IFS=$'\n\t'  # 调整内部字段分隔符以避免空格导致的解析问题。
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)  # 解析脚本所在目录的绝对路径。
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)  # 计算仓库根目录，便于引用项目文件。
DEFAULT_CACHE_DIR="${REPO_ROOT}/.cache"  # 定义默认缓存目录为仓库根下的 .cache。
DEFAULT_VENV_DIR="${REPO_ROOT}/.venv"  # 定义默认虚拟环境目录。
CHECK_ONLY="false"  # 默认执行真实安装流程。
PYTHON_PATH=""  # 记录用户指定的 Python 可执行路径，默认留空表示自动检测。
USE_SYSTEM_FFMPEG="true"  # 默认尝试使用系统级 ffmpeg/ffprobe。
CACHE_DIR="${DEFAULT_CACHE_DIR}"  # 初始化缓存目录变量。
VENV_DIR="${DEFAULT_VENV_DIR}"  # 初始化虚拟环境目录变量。
EXTRA_INDEX_URL=""  # 允许用户自定义 pip 镜像。
REQUIREMENTS_FILE="${REPO_ROOT}/requirements.txt"  # 指定依赖清单文件。
FFMPEG_CACHE_ROOT=""  # 预留变量用于记录 ffmpeg 下载目录。
RESOLVED_PYTHON=""  # 记录解析出的 Python，可供其他函数复用。
print_help() {  # 定义帮助函数输出脚本参数说明。
  cat <<'USAGE'  # 使用 here-doc 打印多行帮助信息。
用法：bash scripts/setup.sh [参数]
  --check-only true|false        是否仅执行环境体检与计划展示（默认 false）。
  --python /path/to/python       指定 Python 可执行文件路径。
  --use-system-ffmpeg true|false 是否优先使用系统已安装的 ffmpeg/ffprobe（默认 true）。
  --cache-dir PATH               指定缓存目录，默认仓库根目录下的 .cache。
  --venv-dir PATH                指定虚拟环境目录，默认仓库根目录下的 .venv。
  --extra-index-url URL          为 pip 安装追加额外的索引源。
  --help                         查看帮助信息并退出。
USAGE
}  # 结束帮助函数定义。
while [[ $# -gt 0 ]]; do  # 开始解析命令行参数。
  case "$1" in  # 根据当前参数名称进行匹配。
    --check-only)  # 捕获 --check-only 参数。
      CHECK_ONLY="$2"  # 记录用户提供的布尔值。
      shift 2  # 跳过参数及其值。
      ;;
    --python)  # 捕获 --python 参数。
      PYTHON_PATH="$2"  # 存储用户指定的 Python 解释器。
      shift 2  # 跳过已处理的两个值。
      ;;
    --use-system-ffmpeg)  # 捕获 --use-system-ffmpeg 参数。
      USE_SYSTEM_FFMPEG="$2"  # 更新 ffmpeg 使用策略。
      shift 2  # 跳过选项和值。
      ;;
    --cache-dir)  # 捕获 --cache-dir 参数。
      CACHE_DIR="$2"  # 覆盖默认缓存路径。
      shift 2  # 向后移动两个参数位。
      ;;
    --venv-dir)  # 捕获 --venv-dir 参数。
      VENV_DIR="$2"  # 覆盖默认虚拟环境路径。
      shift 2  # 跳过该参数及其取值。
      ;;
    --extra-index-url)  # 捕获 --extra-index-url 参数。
      EXTRA_INDEX_URL="$2"  # 保存额外的 pip 索引地址。
      shift 2  # 跳过该参数与其值。
      ;;
    --help)  # 当用户请求帮助时。
      print_help  # 输出帮助说明。
      exit 0  # 打印后直接退出。
      ;;
    *)  # 捕获所有未识别的参数。
      echo "[WARN] 未识别的参数: $1"  # 提示用户参数无效。
      shift 1  # 忽略该参数并继续解析后续参数。
      ;;
  esac  # 结束 case 结构。
done  # 完成所有参数解析。
resolve_python() {  # 定义函数用于确定 Python 解释器。
  if [[ -n "${PYTHON_PATH}" ]]; then  # 若用户显式指定解释器。
    echo "${PYTHON_PATH}"  # 返回指定路径。
    return 0  # 成功结束函数。
  fi  # 未指定时继续自动检测。
  if command -v python3 >/dev/null 2>&1; then  # 首先尝试定位 python3。
    echo "python3"  # 返回可执行名称。
    return 0  # 成功结束函数。
  fi  # 未找到 python3 时继续寻找 python。
  if command -v python >/dev/null 2>&1; then  # 检查 python 是否存在。
    echo "python"  # 返回可执行名称。
    return 0  # 成功结束。
  fi  # 若系统中不存在可用 Python。
  echo ""  # 返回空字符串表示失败。
}  # 结束解释器解析函数。
print_parameters() {  # 定义函数打印解析后的参数信息。
  echo "---- 参数解析结果 ----"  # 输出标题。
  echo "check-only          : ${CHECK_ONLY}"  # 显示演练模式开关。
  echo "python              : ${PYTHON_PATH:-<自动检测>}"  # 显示 Python 路径或占位文字。
  echo "use-system-ffmpeg   : ${USE_SYSTEM_FFMPEG}"  # 显示 ffmpeg 使用策略。
  echo "cache-dir           : ${CACHE_DIR}"  # 显示缓存目录。
  echo "venv-dir            : ${VENV_DIR}"  # 显示虚拟环境目录。
  echo "extra-index-url     : ${EXTRA_INDEX_URL:-<未指定>}"  # 显示额外 pip 索引。
  echo "仓库根目录          : ${REPO_ROOT}"  # 显示仓库根目录路径。
  echo  # 输出空行分隔。
}  # 结束打印函数。
print_system_info() {  # 定义函数输出当前平台信息。
  echo "---- 系统信息 ----"  # 打印标题。
  uname -s 2>/dev/null || echo "[INFO] uname -s 不可用"  # 打印操作系统类型。
  uname -m 2>/dev/null || echo "[INFO] uname -m 不可用"  # 打印 CPU 架构。
  echo "Python (默认) 版本: $(python --version 2>/dev/null || echo 未检测到)"  # 显示默认 python 版本。
  echo "pip (默认) 版本   : $(pip --version 2>/dev/null || echo 未检测到)"  # 显示默认 pip 版本。
  echo  # 输出空行分隔。
}  # 结束系统信息函数。
ensure_directory() {  # 定义函数用于创建目录。
  local target_dir="$1"  # 接收函数参数作为目标目录。
  if [[ ! -d "${target_dir}" ]]; then  # 判断目录是否存在。
    mkdir -p "${target_dir}"  # 若不存在则创建目录。
  fi  # 目录存在时无需额外操作。
}  # 结束目录创建函数。
run_verify() {  # 定义函数执行环境体检脚本。
  local python_exec="$1"  # 接收用于运行体检的 Python 解释器。
  "${python_exec}" "${SCRIPT_DIR}/verify_env.py"  # 调用 verify_env.py 输出体检结果。
}  # 结束体检函数。
install_python_requirements() {  # 定义函数安装 Python 依赖。
  local python_exec="$1"  # 接收虚拟环境中的 Python。
  local pip_args=("-m" "pip" "install" "--upgrade" "pip")  # 组装升级 pip 的命令参数。
  if [[ -n "${EXTRA_INDEX_URL}" ]]; then  # 若用户指定额外索引。
    pip_args+=("--extra-index-url" "${EXTRA_INDEX_URL}")  # 将索引追加到命令中。
  fi  # 未指定索引时保持默认。
  "${python_exec}" "${pip_args[@]}"  # 执行 pip 升级操作。
  local install_args=("-m" "pip" "install" "-r" "${REQUIREMENTS_FILE}")  # 组装安装 requirements 的命令参数。
  if [[ -n "${EXTRA_INDEX_URL}" ]]; then  # 再次判断索引参数。
    install_args+=("--extra-index-url" "${EXTRA_INDEX_URL}")  # 加入额外索引。
  fi  # 未指定索引时不添加额外参数。
  "${python_exec}" "${install_args[@]}"  # 安装项目依赖。
}  # 结束依赖安装函数。
install_torch_cpu() {  # 定义函数尝试安装 CPU 版 torch。
  local python_exec="$1"  # 接收虚拟环境 Python。
  local torch_args=("-m" "pip" "install" "torch" "--index-url" "https://download.pytorch.org/whl/cpu")  # 构造安装命令。
  if [[ -n "${EXTRA_INDEX_URL}" ]]; then  # 若存在额外索引。
    torch_args+=("--extra-index-url" "${EXTRA_INDEX_URL}")  # 追加索引以兼容需要认证的私有仓库。
  fi  # 没有额外索引时保持默认命令。
  if "${python_exec}" "${torch_args[@]}"; then  # 执行安装并根据返回码判断成功与否。
    echo "[INFO] torch CPU 版安装成功。"  # 输出成功提示。
  else  # 当安装失败时。
    echo "[WARN] torch 安装失败，保留环境继续执行。"  # 提示失败但不中断流程。
    echo "[HINT] 请参考 README Round 5 章节手动安装适合平台的 torch 轮子。"  # 给出后续行动建议。
  fi  # 完成安装尝试。
}  # 结束 torch 安装函数。
append_path_once() {  # 定义函数将目录临时加入 PATH。
  local new_dir="$1"  # 接收需要加入 PATH 的目录。
  case ":${PATH}:" in  # 使用模式匹配避免重复添加。
    *":${new_dir}:"*) ;;  # 若已存在则不再添加。
    *) export PATH="${new_dir}:${PATH}" ;;  # 不存在时将目录追加到 PATH 开头。
  esac  # 完成 PATH 处理。
}  # 结束 PATH 操作函数。
detect_platform() {  # 定义函数返回平台标识。
  local kernel_name="$(uname -s 2>/dev/null || echo unknown)"  # 获取操作系统内核名称。
  case "${kernel_name}" in  # 根据内核名称分类。
    Linux) echo "linux" ;;  # 返回 linux。
    Darwin) echo "macos" ;;  # 返回 macOS。
    MINGW*|MSYS*|CYGWIN*) echo "windows" ;;  # 处理 Windows 子系统或 Git Bash。
    *) echo "unknown" ;;  # 未识别时返回 unknown。
  esac  # 结束平台检测。
}  # 结束平台函数。
download_ffmpeg() {  # 定义函数下载并解压 ffmpeg 静态构建。
  local platform="$1"  # 接收当前平台标识。
  local cache_root="$2"  # 接收缓存目录。
  ensure_directory "${cache_root}"  # 确保缓存目录存在。
  case "${platform}" in  # 根据平台选择下载源。
    linux)  # 针对 Linux 平台。
      local archive_url="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"  # 选择稳定的静态编译包链接。
      local archive_name="ffmpeg-release-amd64-static.tar.xz"  # 定义下载文件名。
      local target_dir="${cache_root}/ffmpeg-linux"  # 设置解压目标目录。
      fetch_and_extract_tar "${archive_url}" "${archive_name}" "${target_dir}"  # 调用辅助函数下载并解压。
      echo "${target_dir}/extracted/ffmpeg-*"  # 输出包含 ffmpeg 可执行文件的目录通配符。
      ;;
    macos)  # 针对 macOS 平台。
      local archive_url="https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-macos64-static.zip"  # 选择包含 ffmpeg/ffprobe 的静态构建。
      local archive_name="ffmpeg-macos.zip"  # 定义下载文件名。
      local target_dir="${cache_root}/ffmpeg-macos"  # 设置解压目录。
      fetch_and_extract_zip "${archive_url}" "${archive_name}" "${target_dir}"  # 调用 zip 解压函数。
      echo "${target_dir}/extracted/ffmpeg-master-latest-macos64-static/bin"  # 返回 bin 目录通配符。
      ;;
    windows)  # 针对 Windows 平台（Git Bash/PWSH 环境）。
      local archive_url="https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-git-essentials.7z"  # 使用 gyan.dev 的每日静态构建。
      local archive_name="ffmpeg-windows.7z"  # 下载文件名。
      local target_dir="${cache_root}/ffmpeg-windows"  # 解压目标目录。
      fetch_and_extract_7z "${archive_url}" "${archive_name}" "${target_dir}"  # 调用 7z 解压函数。
      echo "${target_dir}/extracted/ffmpeg-*/bin"  # 返回 bin 目录通配符。
      ;;
    *)  # 无法识别的平台。
      echo ""  # 返回空字符串。
      ;;
  esac  # 结束平台分支。
}  # 结束下载函数。
fetch_file() {  # 定义通用文件下载函数。
  local url="$1"  # 接收资源地址。
  local destination="$2"  # 接收输出文件路径。
  if command -v curl >/dev/null 2>&1; then  # 优先使用 curl。
    curl -L --fail --show-error --output "${destination}" "${url}"  # 使用 curl 下载文件并启用失败即报错。
  elif command -v wget >/dev/null 2>&1; then  # 若无 curl 则使用 wget。
    wget -O "${destination}" "${url}"  # 使用 wget 下载文件。
  else  # 两者都不可用。
    echo "[ERROR] 缺少 curl 或 wget，无法自动下载 ffmpeg。"  # 提示用户手动安装。
    return 1  # 返回非零状态指示失败。
  fi  # 结束下载方式选择。
  if [[ ! -s "${destination}" ]]; then  # 下载完成后检查文件大小是否非零。
    echo "[ERROR] 下载的文件为空，可能存在网络或代理问题：${url}"  # 输出错误提示。
    return 1  # 返回失败状态。
  fi  # 校验成功时继续。
}  # 结束通用下载函数。
fetch_and_extract_tar() {  # 定义函数下载并解压 tar.xz 包。
  local url="$1"  # 资源 URL。
  local filename="$2"  # 下载后文件名。
  local target_dir="$3"  # 解压目标目录。
  ensure_directory "${target_dir}"  # 创建目标目录。
  local archive_path="${target_dir}/${filename}"  # 构造完整下载路径。
  if [[ ! -f "${archive_path}" ]]; then  # 若文件尚未下载。
    echo "[INFO] 正在下载 ffmpeg 静态包: ${url}"  # 输出下载提示。
    fetch_file "${url}" "${archive_path}"  # 执行下载。
  else  # 已存在下载文件。
    echo "[INFO] 检测到已下载的 ffmpeg 包，跳过重新下载。"  # 输出提示。
  fi  # 下载结束。
  if [[ ! -d "${target_dir}/extracted" ]]; then  # 检查是否已解压。
    echo "[INFO] 正在解压 ffmpeg 包。"  # 输出解压提示。
    mkdir -p "${target_dir}/extracted"  # 创建临时解压目录。
    tar -xf "${archive_path}" -C "${target_dir}/extracted"  # 使用 tar 解压文件。
  else  # 已解压的情况。
    echo "[INFO] 已存在解压目录，保持幂等。"  # 输出提示。
  fi  # 解压结束。
}
fetch_and_extract_zip() {  # 定义函数下载并解压 zip 包。
  local url="$1"  # 资源 URL。
  local filename="$2"  # 下载后文件名。
  local target_dir="$3"  # 解压目标目录。
  ensure_directory "${target_dir}"  # 确保目录存在。
  local archive_path="${target_dir}/${filename}"  # 构造文件路径。
  if [[ ! -f "${archive_path}" ]]; then  # 判断是否需要下载。
    echo "[INFO] 正在下载 ffmpeg 静态包: ${url}"  # 输出下载提示。
    fetch_file "${url}" "${archive_path}"  # 执行下载。
  else  # 文件已存在。
    echo "[INFO] 检测到已下载的 ffmpeg 包，跳过重新下载。"  # 输出提示。
  fi  # 完成下载阶段。
  if [[ ! -d "${target_dir}/extracted" ]]; then  # 检查是否已解压。
    echo "[INFO] 正在解压 ffmpeg 包。"  # 提示用户正在解压。
    mkdir -p "${target_dir}/extracted"  # 创建解压目录。
    if command -v unzip >/dev/null 2>&1; then  # 使用 unzip 解压。
      unzip -o "${archive_path}" -d "${target_dir}/extracted"  # 解压内容。
    else  # 无 unzip 时尝试使用 python。
      local python_bin="${RESOLVED_PYTHON:-$(resolve_python)}"  # 优先使用已解析的 Python。
      if [[ -z "${python_bin}" ]]; then  # 若仍无法解析解释器。
        python_bin="python"  # 兜底使用 python 命令。
      fi  # 完成兜底逻辑。
      "${python_bin}" - "$archive_path" "${target_dir}/extracted" <<'PY'
import sys
import zipfile
archive_path = sys.argv[1]
dest_dir = sys.argv[2]
with zipfile.ZipFile(archive_path, "r") as zf:
    zf.extractall(dest_dir)
PY
    fi  # 完成解压。
  else  # 已解压的情况。
    echo "[INFO] 已存在解压目录，保持幂等。"  # 输出提示。
  fi  # 解压阶段结束。
}
fetch_and_extract_7z() {  # 定义函数下载并解压 7z 包。
  local url="$1"  # 资源 URL。
  local filename="$2"  # 下载后文件名。
  local target_dir="$3"  # 解压目录。
  ensure_directory "${target_dir}"  # 确保目标目录存在。
  local archive_path="${target_dir}/${filename}"  # 构造文件路径。
  if [[ ! -f "${archive_path}" ]]; then  # 判断是否需要下载。
    echo "[INFO] 正在下载 ffmpeg 静态包: ${url}"  # 输出下载提示。
    fetch_file "${url}" "${archive_path}"  # 执行下载。
  else  # 文件已存在。
    echo "[INFO] 检测到已下载的 ffmpeg 包，跳过重新下载。"  # 输出提示。
  fi  # 下载阶段结束。
  if [[ ! -d "${target_dir}/extracted" ]]; then  # 检查是否已解压。
    echo "[INFO] 正在解压 ffmpeg 包。"  # 提示用户正在解压。
    mkdir -p "${target_dir}/extracted"  # 创建解压目录。
    if command -v 7z >/dev/null 2>&1; then  # 若系统存在 7z 命令。
      7z x -y -o"${target_dir}/extracted" "${archive_path}" >/dev/null  # 使用 7z 解压到指定目录。
    else  # 系统缺少 7z。
      echo "[WARN] 未检测到 7z，可通过 choco/winget 安装，或手动解压 ${archive_path}。"  # 提示用户手动处理。
    fi  # 完成解压。
  else  # 已存在解压目录。
    echo "[INFO] 已存在解压目录，保持幂等。"  # 输出提示。
  fi  # 解压阶段结束。
}
locate_ffmpeg_binaries() {  # 定义函数查找解压后的 ffmpeg 可执行目录。
  local glob_pattern="$1"  # 接收通配模式。
  for candidate in ${glob_pattern}; do  # 遍历所有匹配的候选路径。
    if [[ -d "${candidate}" ]]; then  # 确认候选路径为目录。
      echo "${candidate}"  # 返回第一个有效目录。
      return 0  # 成功返回。
    fi  # 跳过无效目录。
  done  # 遍历结束。
  echo ""  # 未找到时返回空字符串。
}  # 结束查找函数。
prepare_ffmpeg() {  # 定义函数处理 ffmpeg 安装逻辑。
  local platform="$1"  # 接收平台标识。
  local cache_root="$2"  # 接收缓存目录。
  if [[ "${USE_SYSTEM_FFMPEG}" == "true" ]]; then  # 当用户选择使用系统 ffmpeg。
    if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then  # 检查系统工具是否存在。
      echo "[INFO] 已检测到系统 ffmpeg/ffprobe：$(command -v ffmpeg)"  # 输出确认信息。
      return 0  # 无需额外操作。
    fi  # 若系统缺少工具则继续尝试下载。
    echo "[WARN] 系统中未找到 ffmpeg/ffprobe，准备下载静态构建。"  # 提示即将下载。
  else  # 用户选择不使用系统 ffmpeg。
    echo "[INFO] 用户设置 use-system-ffmpeg=false，将下载静态构建。"  # 输出说明。
  fi  # 结束布尔判断。
  local glob_path="$(download_ffmpeg "${platform}" "${cache_root}")"  # 调用下载函数并获取可执行目录通配符。
  if [[ -z "${glob_path}" ]]; then  # 若返回空字符串说明平台未支持。
    echo "[ERROR] 未能为当前平台提供自动化的 ffmpeg 包，请参考 README 手动安装。"  # 输出错误提示。
    return 1  # 返回非零状态。
  fi  # 若成功获得路径模式。
  local ffmpeg_dir="$(locate_ffmpeg_binaries "${glob_path}")"  # 查找实际解压目录。
  if [[ -z "${ffmpeg_dir}" ]]; then  # 若仍未找到目录。
    echo "[ERROR] 解压后的 ffmpeg 目录未找到，请检查下载与解压步骤。"  # 输出错误提示。
    return 1  # 返回非零状态。
  fi  # 找到目录。
  append_path_once "${ffmpeg_dir}"  # 将该目录加入 PATH。
  echo "[INFO] 已将 ${ffmpeg_dir} 加入 PATH（仅当前会话有效）。"  # 提示用户 PATH 更新。
}  # 结束 ffmpeg 准备函数。
main() {  # 定义主流程函数。
  print_parameters  # 打印用户输入。
  print_system_info  # 输出系统信息。
  local python_exec="$(resolve_python)"  # 调用函数确定 Python 解释器。
  RESOLVED_PYTHON="${python_exec}"  # 将解析结果记录为全局变量以供后续使用。
  if [[ -z "${python_exec}" ]]; then  # 如果未能解析到 Python。
    echo "[ERROR] 未找到可用的 Python 解释器，请使用 --python 指定路径。"  # 提示用户提供解释器。
    exit 1  # 无法继续时退出脚本。
  fi  # 找到 Python 后继续。
  echo "[INFO] 将使用 Python 解释器：${python_exec}"  # 提示即将使用的解释器。
  if [[ "${CHECK_ONLY}" == "true" ]]; then  # 当用户选择仅检查。
    echo "[INFO] 处于 check-only 模式，仅执行 verify_env.py。"  # 输出模式说明。
    run_verify "${python_exec}"  # 调用体检脚本。
    return 0  # 结束主函数。
  fi  # 非 check-only 模式继续安装流程。
  ensure_directory "${CACHE_DIR}"  # 创建缓存目录。
  ensure_directory "${VENV_DIR}"  # 创建虚拟环境目录（若不存在）。
  if [[ ! -f "${VENV_DIR}/pyvenv.cfg" ]]; then  # 若虚拟环境尚未创建。
    echo "[INFO] 正在创建虚拟环境：${VENV_DIR}"  # 输出创建提示。
    "${python_exec}" -m venv "${VENV_DIR}"  # 创建虚拟环境。
  else  # 已存在虚拟环境。
    echo "[INFO] 检测到已存在的虚拟环境，跳过创建步骤。"  # 保持幂等性。
  fi  # 虚拟环境准备完成。
  local activate_script="${VENV_DIR}/bin/activate"  # 假设类 Unix 的激活脚本路径。
  local venv_python="${VENV_DIR}/bin/python"  # 默认的虚拟环境 Python 路径。
  if [[ -f "${VENV_DIR}/Scripts/activate" ]]; then  # 在 Windows 平台使用不同的目录结构。
    activate_script="${VENV_DIR}/Scripts/activate"  # 指向 Windows 激活脚本。
    if [[ -f "${VENV_DIR}/Scripts/python.exe" ]]; then  # 检查 Windows 下的 python.exe。
      venv_python="${VENV_DIR}/Scripts/python.exe"  # 使用带扩展名的解释器路径。
    else  # 兜底到无扩展名的 python。
      venv_python="${VENV_DIR}/Scripts/python"  # 以防某些发行版仅提供无扩展名可执行文件。
    fi  # 结束 Windows 路径检测。
  fi  # 完成针对平台的路径调整。
  # shellcheck disable=SC1091
  source "${activate_script}"  # 激活虚拟环境以便后续 pip 命令使用其中的解释器。
  install_python_requirements "${venv_python}"  # 安装项目依赖。
  install_torch_cpu "${venv_python}"  # 尝试安装 torch CPU 轮子。
  local platform="$(detect_platform)"  # 检测当前平台。
  FFMPEG_CACHE_ROOT="${CACHE_DIR}/ffmpeg"  # 设置 ffmpeg 缓存目录。
  ensure_directory "${FFMPEG_CACHE_ROOT}"  # 创建 ffmpeg 缓存目录。
  if ! prepare_ffmpeg "${platform}" "${FFMPEG_CACHE_ROOT}"; then  # 调用函数确保 ffmpeg 可用。
    echo "[WARN] 自动准备 ffmpeg 失败，请参阅 README 手动安装。"  # 输出警告但不中断流程。
  fi  # ffmpeg 准备完成或失败。
  echo "[INFO] 开始运行 verify_env.py 进行最终体检。"  # 提示即将执行环境检查。
  run_verify "${venv_python}"  # 使用虚拟环境解释器运行体检。
  echo  # 输出空行提升可读性。
  echo "[INFO] 安装流程完成。"  # 输出完成提示。
  echo "[NEXT] 激活虚拟环境后，可运行示例："  # 给出后续操作建议。
  echo "       source ${VENV_DIR}/bin/activate"  # 指导激活虚拟环境。
  echo "       python -m src.cli.main --help"  # 提供下一步命令示例。
}  # 结束主流程函数。
main  # 调用主函数执行脚本。
