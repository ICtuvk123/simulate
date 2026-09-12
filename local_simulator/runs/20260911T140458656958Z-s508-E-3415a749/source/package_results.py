"""Create portable replay, transparent validation report and data-driven PDFs."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    paired = list(csv.DictReader((ROOT / "reports" / "paired_runs.csv").open(encoding="utf-8-sig")))
    records = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "runs").glob("*/result.json"))]
    repeats = [r for r in records if r["metadata"]["seed"] == 101
               and r["metadata"]["policy_configuration"]["strategy"] == "B"
               and r["metadata"]["configuration"]["scenario"] == "uniform"]
    def stable_events(record):
        events = json.loads(json.dumps(record["evaluation"]["events"]))
        for e in events:
            e["response"].pop("real_timestamp_ms", None)
        return json.dumps(events, sort_keys=True, separators=(",", ":"))
    hashes = [hashlib.sha256(stable_events(r).encode()).hexdigest() for r in repeats]
    same_sources = True
    for seed in {int(row["seed"]) for row in paired}:
        selected = [r["evaluation"]["sources"] for r in records if r["metadata"]["seed"] == seed]
        same_sources &= all(s == selected[0] for s in selected)
    audit = {"same_scene_sources_across_strategies": same_sources,
             "repeat_seed": 101, "repeat_strategy": "B", "repeated_runs": len(repeats),
             "action_and_feedback_sha256": hashes,
             "exact_action_and_virtual_feedback_reproduction": len(hashes) >= 2 and len(set(hashes)) == 1,
             "all_paired_clear_ratios_one": all(float(r["clear_ratio"]) == 1 for r in paired),
             "all_paired_completion_certificates": all(r["completion_proved"] == "True" for r in paired),
             "all_paired_accounting_warnings_empty": all(not r["metrics"]["accounting_warnings"] for r in records),
             "ui_checks": ["start_local_run", "step_forward", "play", "pause", "jump_to_end",
                            "truth_hidden_until_end", "console_no_errors", "standalone_embedded_replay",
                            "export_html_saved_to_run_directory"]}
    (ROOT / "reports" / "reproducibility.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    demo = repeats[-1]
    serialized = json.dumps(demo, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    html = html.replace("const EMBEDDED = null;", "const EMBEDDED = " + serialized + ";", 1)
    (ROOT / "reports" / "demo_replay.html").write_text(html, encoding="utf-8")
    summary = json.loads((ROOT / "reports" / "benchmark_summary.json").read_text(encoding="utf-8"))
    table = "\n".join(f"| {r['strategy']} | {r['mean_total_time']:.2f} | {r['mean_move_time']:.2f} | {r['mean_RF_detection_time']:.2f} | {r['mean_channel_switch_time']:.2f} | {r['mean_optical_time']:.2f} | {r['mean_clear_time']:.2f} |" for r in summary if r["split"] == "all")
    text = """# 本地模拟器计算与验收结果

## 运行环境

Windows，Python 3.12.14。模拟器、策略、界面服务全部使用Python标准库。报告图表另用现有reportlab；运行与查看回放无需安装此库。未调用官方模拟器。

## 规则测试

19项单元测试通过，含附件199秒例、1000米接收边界、5米near、20米清除、clear不切RF频道、同点误差固定、舍入误差界、幂等、无效输入无状态变化、25/20分钟预算、虚拟超时和真值读取时序。

## 配对实验

预先列明12个场景：训练101–104，验证501–504，压力901–904；每个场景运行A/B/C，共36次，全部100%清除，且全部通过独立完成证书。压力场景包含边界分布、1000米最小接收半径、±1°极端偏差和平滑误差。

以下均为12个场景的均值，单位秒。数据来源 `paired_runs.csv`，分组统计见 `leaderboard.csv`。

| 策略 | 总时间 | 移动 | 测向 | 切频 | 光学 | 清除 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
""" + table + """

B在该配对集合的均值最低。C比B少走路，但增加测向与切频，平均总时间反而多24.69秒（约0.57%）。因此界面默认B，并保留C继续研究。此小样本结果不宣称总体统计优势，更不构成0.5%优化平台期证据。

验证组B均值4372.58秒，C均值4521.54秒；没有把训练组C较快当作已经验证的改进。中位数、P90、P95、最坏时间及分项统计已保存在CSV和JSON中。

## 重复运行与界面

通过网页再次启动场景101策略B，16/16清除，总时间4222.454847秒，与此前相同场景B结果一致。完整动作位置、频道、反馈与虚拟时间去除现实时间戳后逐项比较，并记录SHA-256。不同策略的隐藏源集合相同。

页面已验证本地开始、前进一步、播放、暂停、跳到结束、结束前禁止真实位置显示，未见控制台错误。`demo_replay.html` 是含完整日志和观测定位区域的单文件回放。

## 下界

场景101策略B的结束后下界由自建真实坐标计算，结果在该运行的 `metrics.json` 中。下界使用清除圆之间最短距离的独立边权松弛，不是已经实现的最优TSPN路线。

## 图表

`figures/time_components.pdf`：配对场景平均总时间及分项。

`figures/paired_times.pdf`：各相同场景中B与C总时间散点，包含等时线。

## 限制与下一步

场景随机分布和固定误差函数为公开记录的本地选择，并非官方内部实现。只保证题面可核实规则的一致性，不能据此冒充官方成绩。程序未读取、运行或操纵官方模拟器。

本次已完成自建环境、测试和可视化的交付；第二问新候选点算法仍需接入并在更多独立种子上优化。现有Goal处于暂停状态，尚未宣告原持续优化目标完成。
"""
    (ROOT / "reports" / "RESULTS_REPORT.md").write_text(text, encoding="utf-8")
    make_figures(summary, paired)
    print(json.dumps(audit, indent=2))


def make_figures(summary, paired):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.colors import HexColor
    pdfmetrics.registerFont(TTFont("LocalCJK", "C:/Windows/Fonts/simhei.ttf"))
    folder = ROOT / "figures"
    folder.mkdir(exist_ok=True)
    c = canvas.Canvas(str(folder / "time_components.pdf"), pagesize=(560, 340))
    c.setFont("LocalCJK", 10)
    for t in range(0, 6001, 1000):
        x = 85 + t / 6000 * 410
        c.setStrokeColor(HexColor("#e6eaf0")); c.line(x, 65, x, 282)
        c.setFillColor(HexColor("#425268")); c.drawCentredString(x, 48, str(t))
    parts = [("mean_move_time", "移动", "#2464eb"), ("mean_RF_detection_time", "测向", "#83a6ec"),
             ("mean_channel_switch_time", "切频", "#b9a2df"), ("mean_optical_time", "光学", "#e6ab60"),
             ("mean_clear_time", "清除", "#159977")]
    for i, row in enumerate(r for r in summary if r["split"] == "all"):
        y = 245 - 70 * i; x = 85
        c.setFillColor(HexColor("#24384e")); c.drawString(32, y + 8, "策略 " + row["strategy"])
        for key, _, color in parts:
            width = row[key] / 6000 * 410
            c.setFillColor(HexColor(color)); c.rect(x, y, width, 28, stroke=0, fill=1); x += width
        c.setFillColor(HexColor("#24384e")); c.drawString(x + 7, y + 8, f"{row['mean_total_time']:.1f}")
    for i, (_, label, color) in enumerate(parts):
        x = 85 + i * 79
        c.setFillColor(HexColor(color)); c.rect(x, 306, 10, 7, stroke=0, fill=1)
        c.setFillColor(HexColor("#24384e")); c.drawString(x + 15, 304, label)
    c.drawCentredString(285, 20, "平均总行动时间（秒）"); c.save()
    c = canvas.Canvas(str(folder / "paired_times.pdf"), pagesize=(440, 420))
    c.setFont("LocalCJK", 10)
    def xy(x, y): return 65 + (x - 2000) / 4000 * 320, 65 + (y - 2000) / 4000 * 300
    c.setStrokeColor(HexColor("#bdc8d5")); c.setDash(4, 3); c.line(*xy(2000, 2000), *xy(6000, 6000)); c.setDash()
    for t in range(2000, 6001, 1000):
        x, y = xy(t, t); c.setFillColor(HexColor("#546478")); c.drawCentredString(x, 47, str(t)); c.drawRightString(55, y - 3, str(t))
    colors = {"train": "#2464eb", "validation": "#159977", "stress": "#dc9440"}
    for seed in sorted({r["seed"] for r in paired}):
        group = {r["strategy"]: r for r in paired if r["seed"] == seed}
        x, y = xy(float(group["B"]["total_time"]), float(group["C"]["total_time"]))
        c.setFillColor(HexColor(colors[group["B"]["split"]])); c.circle(x, y, 4, stroke=0, fill=1)
        c.setFont("Helvetica", 8); c.drawString(x + 5, y + 5, seed); c.setFont("LocalCJK", 10)
    c.setFillColor(HexColor("#24384e")); c.drawCentredString(220, 24, "策略 B 总时间（秒）")
    c.saveState(); c.translate(18, 230); c.rotate(90); c.drawCentredString(0, 0, "策略 C 总时间（秒）"); c.restoreState()
    for i, (split, label) in enumerate((("train", "训练"), ("validation", "验证"), ("stress", "压力"))):
        c.setFillColor(HexColor(colors[split])); c.circle(110 + i * 95, 391, 3, stroke=0, fill=1)
        c.setFillColor(HexColor("#24384e")); c.drawString(120 + i * 95, 387, label)
    c.save()


if __name__ == "__main__":
    main()
