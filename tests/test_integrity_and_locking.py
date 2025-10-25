"""验证文件锁、哈希校验、临时文件清理与 Manifest 一致性。"""  # 模块说明。
# 导入 json 以解析 Manifest 记录。 
import json
# 导入 threading 以并行触发同一输入的处理流程。 
import threading
# 导入 time 以在伪后端中注入延时。 
import time
# 导入 pathlib.Path 以构造测试用的临时路径。 
from pathlib import Path

# 导入管线 run 函数以便直接调用。 
from src.asr.pipeline import run
# 导入 dummy 后端模块以便 monkeypatch 添加延迟。 
from src.asr.backends import dummy as dummy_backend
# 导入 Manifest 工具以便在断言阶段读取索引。 
from src.utils.manifest import load_index
# 导入 I/O 工具中的哈希函数用于验证哈希写入正确。 
from src.utils.io import sha256_file

# 定义测试，覆盖文件锁争用、哈希失效检测与临时文件清理。 
def test_integrity_lock_and_manifest(tmp_path: Path, monkeypatch) -> None:
    """综合验证锁、哈希、清理与 Manifest 统计。"""  # 函数说明。
    input_dir = tmp_path / "inputs"  # 构造输入目录路径。
    input_dir.mkdir(parents=True, exist_ok=True)  # 创建输入目录。
    audio_path = input_dir / "clip.wav"  # 定义测试音频路径。
    audio_path.write_bytes(b"original audio payload")  # 写入初始内容以生成稳定哈希。
    out_dir = tmp_path / "out"  # 定义输出目录。
    manifest_path = out_dir / "_manifest.jsonl"  # 默认 Manifest 路径。

    original_transcribe = dummy_backend.DummyTranscriber.transcribe_file  # 备份原实现。

    def _slow_transcribe(self, input_path: str) -> dict:
        """在 dummy 后端中注入延时以制造锁竞争。"""  # 内部函数说明。
        time.sleep(0.3)  # 人为延时确保另一线程在锁上等待。
        return original_transcribe(self, input_path)  # 调用原始实现生成结果。

    monkeypatch.setattr(dummy_backend.DummyTranscriber, "transcribe_file", _slow_transcribe)  # 应用补丁。

    summaries: list[dict] = []  # 用于收集并行运行结果。

    def _worker() -> None:
        """在线程中执行一次管线运行并收集摘要。"""  # 内部函数说明。
        summary = run(
            input_path=str(audio_path),
            out_dir=str(out_dir),
            backend_name="dummy",
            segments_json=True,
            overwrite=False,
            dry_run=False,
            verbose=False,
            num_workers=1,
            max_retries=1,
            rate_limit=0.0,
            skip_done=True,
            fail_fast=False,
            integrity_check=True,
            lock_timeout=0.5,
            cleanup_temp=True,
            manifest_path=str(manifest_path),
            force=False,
        )
        summaries.append(summary)  # 记录运行结果。

    threads = [threading.Thread(target=_worker) for _ in range(2)]  # 创建两个并行线程。
    for thread in threads:  # 启动线程。
        thread.start()
    for thread in threads:  # 等待线程完成。
        thread.join()

    assert len(summaries) == 2  # 确认两个线程均已运行完成。
    succeeded_total = sum(item["succeeded"] for item in summaries)  # 统计成功次数。
    skipped_total = sum(item["skipped"] for item in summaries)  # 统计跳过次数。
    assert succeeded_total == 1  # 仅允许一个线程完成转写。
    assert skipped_total >= 1  # 至少一个线程因锁或结果存在而跳过。

    manifest_records = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]  # 解析 Manifest。
    statuses = [record["status"] for record in manifest_records]  # 收集状态字段。
    assert statuses.count("succeeded") == 1  # 确认仅有一条成功记录。
    assert statuses.count("skipped") >= 1  # 另一个线程应记录为跳过。

    audio_path.write_bytes(b"modified audio payload")  # 修改输入文件以触发哈希变化。
    summary_stale = run(  # 在 overwrite=false 下重新运行。
        input_path=str(audio_path),
        out_dir=str(out_dir),
        backend_name="dummy",
        segments_json=True,
        overwrite=False,
        dry_run=False,
        verbose=False,
        num_workers=1,
        max_retries=1,
        rate_limit=0.0,
        skip_done=True,
        fail_fast=False,
        integrity_check=True,
        lock_timeout=0.5,
        cleanup_temp=True,
        manifest_path=str(manifest_path),
        force=False,
    )
    assert summary_stale["skipped"] == 1  # 本次应整体跳过。
    assert summary_stale.get("skipped_stale", 0) == 1  # 且原因是陈旧结果。
    manifest_records = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]  # 重新读取 Manifest。
    assert manifest_records[-1]["status"] == "skipped"  # 最新记录应为跳过。
    assert manifest_records[-1].get("error", {}).get("type") == "StaleResult"  # 并且标记为陈旧结果。

    summary_overwrite = run(  # 启用覆盖重新生成输出。
        input_path=str(audio_path),
        out_dir=str(out_dir),
        backend_name="dummy",
        segments_json=True,
        overwrite=True,
        dry_run=False,
        verbose=False,
        num_workers=1,
        max_retries=1,
        rate_limit=0.0,
        skip_done=True,
        fail_fast=False,
        integrity_check=True,
        lock_timeout=0.5,
        cleanup_temp=True,
        manifest_path=str(manifest_path),
        force=False,
    )
    assert summary_overwrite["succeeded"] == 1  # 覆盖后应重新生成成功。
    manifest_records = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]  # 再次读取 Manifest。
    assert manifest_records[-1]["status"] == "succeeded"  # 最新记录应为成功。

    tmp_words = out_dir / "clip.words.json.tmp"  # 构造残留临时文件路径。
    tmp_words.write_text("partial", encoding="utf-8")  # 人为生成临时文件。
    summary_cleanup = run(  # 再次运行以触发清理逻辑。
        input_path=str(audio_path),
        out_dir=str(out_dir),
        backend_name="dummy",
        segments_json=True,
        overwrite=True,
        dry_run=False,
        verbose=False,
        num_workers=1,
        max_retries=1,
        rate_limit=0.0,
        skip_done=True,
        fail_fast=False,
        integrity_check=True,
        lock_timeout=0.5,
        cleanup_temp=True,
        manifest_path=str(manifest_path),
        force=False,
    )
    assert summary_cleanup["succeeded"] == 1  # 清理后仍应成功完成。
    assert not tmp_words.exists()  # 临时文件应被删除。

    index = load_index(manifest_path)  # 读取 Manifest 索引。
    latest_record = index[str(audio_path)]  # 获取目标音频的最新记录。
    assert latest_record["status"] == "succeeded"  # 最新状态必须为成功。
    assert latest_record["input_hash_sha256"] == sha256_file(audio_path)  # 哈希应与当前文件匹配。
