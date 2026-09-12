"""Keep mixed, omni-only, and directional-only stress results separate."""
import argparse,csv,json
from pathlib import Path
from experiment import summarize
ROOT=Path(__file__).resolve().parents[1]


def report(phase):
    folder=ROOT/'reports'/phase;rows=[json.loads(s) for s in (folder/'runs.jsonl').read_text().splitlines()]
    groups={}
    for row in rows:
        scene=row['task']['scene'];group=scene.get('source_mix','mixed')
        groups.setdefault(group,[]).append(row)
    stats={name:summarize(items) for name,items in groups.items()}
    (folder/'pressure_groups.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
    text=['# 压力测试（与主混合随机成绩分开）','', '| 类型 | 方案 | 完整成功 | 平均每源 / s | 平均总时间 / s | P95 / s | 最坏 / s | 平均后备次数 | 平均现实耗时 / s |','|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for group,variants in stats.items():
        for name,m in variants.items():
            text.append(f"| {group} | {name} | {m['complete']}/{m['n']} | {m['mean_per_source']:.3f} | {m['mean_total']:.3f} | {m['p95']:.3f} | {m['worst']:.3f} | {m['mean_fallback_count']:.3f} | {m['mean_wall']:.3f} |")
    text+=['','覆盖范围见 registration.json 中逐场配置。每个场景与对照使用完全相同的源、半径、发射朝向和空间误差场。原始动作与独立核验保存在 paired_results.csv 对应的 run_id 目录。']
    (folder/'PRESSURE_REPORT.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    return stats


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase');a=p.parse_args();print(json.dumps(report(a.phase),indent=2))
