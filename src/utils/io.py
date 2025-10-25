"""提供跨平台的 I/O 工具，包括原子写入、哈希与文件锁。"""  # 模块说明。 
# 导入 hashlib 以计算 SHA-256 哈希校验值。 
import hashlib
# 导入 json 以支持 JSON 序列化。 
import json
# 导入 os 模块以执行文件系统操作与原子替换。 
import os
# 导入 stat 用于设置锁文件权限（可选优化）。 
import stat
# 导入 time 以在等待文件锁时休眠与处理超时逻辑。 
import time
# 导入 contextlib.contextmanager 以实现 with 语句上下文管理器。 
from contextlib import contextmanager
# 导入 pathlib.Path 统一处理路径对象。 
from pathlib import Path
# 导入 typing.Any 以在 JSON 写入函数中进行类型注释。 
from typing import Any, Iterator

# 尝试导入 fcntl 以在 POSIX 系统上实现文件锁。 
try:
    import fcntl  # type: ignore
except Exception:  # noqa: BLE001
    fcntl = None  # 若导入失败则后续退化到基于文件创建的锁。

# 尝试导入 msvcrt 以在 Windows 系统上实现锁。 
try:
    import msvcrt  # type: ignore
except Exception:  # noqa: BLE001
    msvcrt = None  # 若导入失败则使用退化锁方案。

# 定义安全创建目录的函数，确保重复调用也不会抛异常。 
def safe_mkdirs(path: str | os.PathLike[str]) -> None:
    """创建目标目录及其父级目录，目录已存在时静默跳过。"""  # 函数说明。
    # 将输入路径转换为 Path 对象以便后续调用 mkdir。 
    target = Path(path)
    # 调用 mkdir 并启用 parents/exist_ok，保证并发场景也安全。 
    target.mkdir(parents=True, exist_ok=True)

# 定义以原子方式写入文本的函数。 
def atomic_write_text(path: str | os.PathLike[str], text: str) -> None:
    """通过临时文件写入文本内容，并以原子方式替换目标文件。"""  # 函数说明。
    # 将目标路径转换为 Path 对象，便于处理父目录与临时文件。 
    target_path = Path(path)
    # 获取父目录并确保其存在。 
    parent_dir = target_path.parent
    safe_mkdirs(parent_dir)
    # 构造临时文件路径，追加 .tmp 后缀以便后续清理。 
    tmp_path = target_path.with_name(f"{target_path.name}.tmp")
    # 使用 try/finally 确保临时文件在异常时被删除。 
    try:
        # 以 UTF-8 打开临时文件并写入完整文本。 
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        # 调用 atomic_replace 将临时文件原子替换为目标文件。 
        atomic_replace(tmp_path, target_path)
    finally:
        # 如果临时文件仍然存在（替换失败），进行清理。 
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

# 定义以 JSON 形式原子写入数据的函数。 
def atomic_write_json(path: str | os.PathLike[str], data: Any) -> None:
    """将数据序列化为 JSON 文本后执行原子写入。"""  # 函数说明。
    # 将 Python 对象转换为格式化 JSON 字符串。 
    json_text = json.dumps(data, ensure_ascii=False, indent=2)
    # 调用文本写入函数以原子方式落盘。 
    atomic_write_text(path, json_text)

# 定义原子替换函数，封装 os.replace 并确保目录存在。 
def atomic_replace(tmp_path: str | os.PathLike[str], final_path: str | os.PathLike[str]) -> None:
    """使用 os.replace 将临时文件移动到目标位置，确保父目录存在。"""  # 函数说明。
    # 将输入转换为 Path 对象。 
    tmp = Path(tmp_path)
    final = Path(final_path)
    # 在替换前确保目标父目录存在。 
    safe_mkdirs(final.parent)
    # 调用 os.replace 完成原子替换，可覆盖旧文件。 
    os.replace(tmp, final)

# 定义计算文件 SHA-256 哈希的函数。 
def sha256_file(path: str | os.PathLike[str], bufsize: int = 1024 * 1024) -> str:
    """读取文件内容并返回十六进制的 SHA-256 哈希值。"""  # 函数说明。
    # 初始化 SHA-256 哈希对象。 
    digest = hashlib.sha256()
    # 以二进制模式打开文件，逐块读取避免占用过多内存。 
    with open(path, "rb") as handle:
        while True:
            # 按照缓冲区大小读取一块数据。 
            chunk = handle.read(bufsize)
            # 如果读到空字节则代表结束。 
            if not chunk:
                break
            # 将数据块更新到哈希对象中。 
            digest.update(chunk)
    # 返回十六进制字符串。 
    return digest.hexdigest()

# 定义移除与基名相关联的临时/部分文件的函数。
def cleanup_partials(out_dir: str | os.PathLike[str], basename: str) -> list[str]:
    """删除与给定基名相关的 .tmp/.partial/.lock 残留文件并返回删除列表。"""  # 函数说明。
    # 将输出目录与基名组合成 Path 对象。
    directory = Path(out_dir)
    # 若目录不存在则直接返回空列表。
    if not directory.exists():
        return []
    # 定义需要匹配的后缀集合。
    suffixes = [".tmp", ".partial", ".lock"]
    # 初始化删除结果列表。
    removed: list[str] = []
    # 遍历目录下的所有文件，过滤出与基名匹配且具备指定后缀的项。
    for candidate in directory.iterdir():
        # 仅处理文件而忽略目录。
        if not candidate.is_file():
            continue
        # 检查文件名是否以基名开头并以指定后缀结尾。
        if not candidate.name.startswith(basename):
            continue
        if not any(candidate.name.endswith(suffix) for suffix in suffixes):
            continue
        # 针对锁文件，尝试通过锁上下文安全地删除。
        if candidate.name.endswith(".lock"):
            try:
                with with_file_lock(candidate, timeout_sec=0.1):
                    pass
                removed.append(str(candidate))
            except TimeoutError:
                continue
            continue
        # 其他类型文件直接删除并记录。
        candidate.unlink(missing_ok=True)
        removed.append(str(candidate))
    # 返回删除列表，便于测试验证。
    return removed

# 定义跨平台文件锁的上下文管理器。 
@contextmanager
def with_file_lock(lock_path: str | os.PathLike[str], timeout_sec: float) -> Iterator[None]:
    """尝试在指定路径创建独占文件锁，超时则抛出 TimeoutError。"""  # 函数说明。
    # 将路径转换为 Path 对象并确保父目录存在。 
    path = Path(lock_path)
    safe_mkdirs(path.parent)
    # 记录开始时间以便计算剩余时间。 
    start = time.monotonic()
    # 定义轮询间隔，选用较小值以平衡响应与资源占用。 
    interval = 0.2
    # 准备占位变量保存文件对象或文件描述符。 
    file_obj = None
    fd: int | None = None
    # 使用 while 循环持续尝试获取锁直到成功或超时。 
    while True:
        try:
            # 针对支持 fcntl 的平台。 
            if fcntl is not None:
                # 以读写模式打开锁文件，若不存在则创建。 
                fd = os.open(path, os.O_RDWR | os.O_CREAT, mode=stat.S_IRUSR | stat.S_IWUSR)
                try:
                    # 申请非阻塞的独占锁。 
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break  # 获取成功直接跳出循环。
                except BlockingIOError:
                    # 若锁被占用则关闭文件描述符并继续重试。 
                    os.close(fd)
                    fd = None
            # 针对 Windows 平台的 msvcrt.locking。 
            elif msvcrt is not None:
                # 以文本模式打开文件对象，便于调用 locking。 
                file_obj = open(path, "a+")
                try:
                    # 调用非阻塞锁定，长度至少为 1 字节。 
                    msvcrt.locking(file_obj.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    # 失败时关闭文件对象并准备重试。 
                    file_obj.close()
                    file_obj = None
            else:
                # 无系统级锁支持时，使用 O_EXCL 创建文件实现自旋锁。 
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                break
        except FileExistsError:
            # O_EXCL 模式下若文件已存在则表示锁被占用，继续等待。 
            fd = None
        # 检查是否已经超过超时时间。 
        elapsed = time.monotonic() - start
        if elapsed >= timeout_sec:
            raise TimeoutError(f"Timed out acquiring lock: {path}")
        # 若仍未超时则休眠一段时间再重试。 
        time.sleep(interval)
    try:
        # 进入上下文时不需要执行额外操作，仅等待 with 体完成。 
        yield
    finally:
        # 退出时根据所用实现释放锁并清理文件。 
        try:
            if fcntl is not None and fd is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
                fd = None
            elif msvcrt is not None and file_obj is not None:
                try:
                    msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
                finally:
                    file_obj.close()
                    file_obj = None
            elif fd is not None:
                os.close(fd)
                fd = None
        finally:
            # 无论哪种实现都尽量删除锁文件，容忍异常以避免影响流程。 
            path.unlink(missing_ok=True)

# 定义追加 JSON 行到 JSONL 文件的函数。 
def jsonl_append(path: str | os.PathLike[str], record: dict) -> None:
    """以原子方式向 JSONL 文件追加一行记录。"""  # 函数说明。
    # 将路径转换为 Path 对象并确保父目录存在。 
    target = Path(path)
    safe_mkdirs(target.parent)
    # 为 JSONL 文件单独创建锁文件避免并发写入。 
    lock_path = target.with_suffix(target.suffix + ".lock")
    # 在锁的保护下执行打开与追加。 
    with with_file_lock(lock_path, timeout_sec=30):
        # 以追加模式打开文件并写入 JSON 序列化后的记录。 
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")

# 定义去除扩展名的辅助函数。 
def path_sans_ext(path: str | os.PathLike[str]) -> str:
    """返回不包含扩展名的路径字符串。"""  # 函数说明。
    # 使用 os.fspath 将 PathLike 转换为字符串。 
    string_path = os.fspath(path)
    # 利用 os.path.splitext 分离扩展名并返回主干部分。 
    base, _ = os.path.splitext(string_path)
    return base

# 定义简易的文件存在性检查函数。 
def file_exists(path: str | os.PathLike[str]) -> bool:
    """判断给定路径是否存在（文件或目录均可）。"""  # 函数说明。
    # 直接调用 os.path.exists 并返回结果。 
    return os.path.exists(path)
