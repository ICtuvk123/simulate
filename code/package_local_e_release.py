"""Package the local-only E simulator and completed evidence for sharing."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
LOCAL = PROJECT / "local_simulator"
RELEASE = PROJECT / "release"
NAME = "问题三自建模拟器_E优化版_20260911"

README = """# 问题三自建模拟器 E 优化版

先把整个压缩包解压到一个普通文件夹。

## 直接查看过程（不需要 Python）

双击 local_simulator/reports/optimization/E_replay.html，用浏览器打开。
可播放、暂停、逐步前进后退、拖动时间轴，观察检测、移动与清除过程。
这是独立验证组中时间接近中位数的案例：15 个源全部清除，整局 2997.04 秒。

## 自己运行新场景

电脑需要 Python 3.10 或以上。双击 local_simulator/start_local_simulator.cmd，
然后用浏览器打开 http://127.0.0.1:8768 。默认策略为 E，可与 A/B/C/D 比较。
核心运行只使用 Python 标准库。若找不到 Python，安装时勾选 Add Python to PATH。
请勿在压缩包预览窗口里直接运行脚本。

## 本轮结果

追加 508 次本地完整运行。100 个新场景的配对验证：
D 平均 3111.70 秒，E 平均 3002.14 秒，节省 109.56 秒（3.52%）；均 100/100 全清。
E 在 88 场更快，配对改善的 95% 区间为 2.84%–4.24%。
控制器只用普通动作反馈；100 局 E 的 12,287 个动作通过纯反馈一致性重放。
200–300 秒的整局目标仍未达到，已有物理下界说明此前普通验证场景无法达到该目标。

## 文件位置

- local_simulator/README.md：使用方法、题面规则和本地假设。
- local_simulator/code/：策略、独立环境、计时、实验与重放审计代码。
- local_simulator/reports/optimization/CONTINUATION_RESULTS.md：最新完整报告。
- local_simulator/reports/optimization/E_validation_paired.csv：100 个场景逐局对比。
- local_simulator/reports/optimization/E_MODEL_NOTES.md：算法与几何证明。
- local_simulator/figures/E_validation_comparison.pdf：可用于论文的对比图。
- local_simulator/runs/：保留的本地原始动作日志、事后评估和运行时源码快照。
- FILE_MANIFEST.json：各文件 SHA-256，可检查文件是否改变。

历史报告和运行记录一并保留，请以 CONTINUATION_RESULTS.md 为最新结论。
code/finalize_local_continuation.py 用于重新生成追加实验报告；重新绘制 PDF 另需
reportlab 和 Windows 黑体字体，正常运行模拟器、查看现成 PDF 和动画均不需要它。

本包只包含自建本地环境，不包含官方模拟器、账号资料、官方演练日志或连接脚本。
运行本包不需要官方登录，不会进入官方演练或正式测试。本地场景分布属于工作假设，
不能把本地数据冒充官方成绩。运行期间策略不能获得真值；结束后日志中的真值仅用于评估和回放。
"""


def main():
    assert LOCAL.is_dir()
    RELEASE.mkdir(exist_ok=True)
    destination = RELEASE / (NAME + ".zip")
    if destination.exists():
        raise FileExistsError(destination)
    files = []
    for path in sorted(LOCAL.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(PROJECT)
        if "__pycache__" in relative.parts or path.suffix.lower() in {".pyc", ".pyo", ".log"}:
            continue
        if any(part in {".git", ".codex", ".agents"} for part in relative.parts):
            continue
        files.append((path, relative.as_posix()))
    helper = PROJECT / "code" / "finalize_local_continuation.py"
    files.append((helper, helper.relative_to(PROJECT).as_posix()))
    entries = []
    expected = {
        "local_simulator/code/replanning.py", "local_simulator/code/reception_geometry.py",
        "local_simulator/code/e_policy_presets.py", "local_simulator/code/engine.py",
        "local_simulator/tests/test_simulator.py", "local_simulator/tests/test_optimization.py",
        "local_simulator/reports/optimization/E_validation_paired.csv",
        "local_simulator/reports/optimization/E_replay.html",
        "local_simulator/reports/optimization/E_feedback_only_audit.json",
    }
    assert expected.issubset({relative for _, relative in files})
    # Local files should not contain the official team identity or launch adapter.
    forbidden = (b"202617201735", b"run_official_practice_d.py")
    for path, relative in files:
        data = path.read_bytes()
        if any(value in data for value in forbidden):
            raise ValueError("Official-only material found in " + relative)
        entries.append({"path": relative, "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()})
    print(json.dumps({"stage": "checked", "files": len(entries),
                      "raw_bytes": sum(e["size"] for e in entries)}, ensure_ascii=False), flush=True)
    with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr(NAME + "/先读我.md", README)
        for (path, relative), entry in zip(files, entries):
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise RuntimeError("File changed during packaging: " + relative)
            archive.writestr(NAME + "/" + relative, data)
        manifest = {"created_utc": datetime.now(timezone.utc).isoformat(),
                    "scope": "self-built local simulator only", "files": entries}
        archive.writestr(NAME + "/FILE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(destination) as archive:
        failed = archive.testzip()
        assert failed is None, failed
        names = archive.namelist()
        assert len(names) == len(entries) + 2
        assert all(".." not in Path(name).parts for name in names)
    receipt = {"zip": str(destination), "bytes": destination.stat().st_size,
               "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
               "archived_files": len(entries) + 2, "crc_verified": True,
               "local_only_content_verified": True}
    (RELEASE / (NAME + ".verification.json")).write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
