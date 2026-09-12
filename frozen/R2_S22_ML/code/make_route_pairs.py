"""Offline route pairs: typical improvement and largest regression."""
import json,shutil,statistics
from pathlib import Path
from replay_html import create_replay
ROOT=Path(__file__).resolve().parents[1]


def build():
    phase='C_task_routes_fixed_dev30'
    rows=[json.loads(s) for s in (ROOT/'reports'/phase/'runs.jsonl').read_text().splitlines()]
    pairs={}
    for r in rows:
        if r['task']['variant'] in ('compact','centroid'):
            assert r['metrics']['all_success']
            pairs.setdefault(r['task']['seed'],{})[r['task']['variant']]=r
    def gain(s):return pairs[s]['compact']['metrics']['total_time']-pairs[s]['centroid']['metrics']['total_time']
    mid=statistics.median(gain(s) for s in pairs)
    selected={'typical':min(pairs,key=lambda s:abs(gain(s)-mid)),'regression':min(pairs,key=gain)}
    result={};out=ROOT/'examples';out.mkdir(exist_ok=True)
    html=['<!doctype html><meta charset="utf-8"><title>路线优化配对回放</title><style>body{font-family:Microsoft YaHei,sans-serif;max-width:1000px;margin:40px auto;color:#203c46;background:#f1f6f8}a{display:inline-block;padding:16px;background:white;margin:10px;border-radius:12px;color:#147589}p{line-height:1.8}</style><h1>路线优化 · 同场景配对回放</h1><p>两个方案使用相同本地场景和固定空间误差；真值默认关闭。选择改善量最接近中位数的一对，以及退步最多的一对，避免只展示最好的一局。</p>']
    for label,seed in selected.items():
        result[label]={'seed':seed}
        html.append('<h2>'+('典型改善' if label=='typical' else '最大退步')+f' · 本地场景 {seed}</h2>')
        for variant in ('compact','centroid'):
            r=pairs[seed][variant];rid=r['run_id'];target=out/f'route_{label}_{variant}.html'
            shutil.copy2(create_replay(ROOT/'runs'/rid),target)
            result[label][variant]=dict(run_id=rid,file=target.name,total=r['metrics']['total_time'],sources=r['metrics']['engine_source_count'])
            html.append(f'<a href="{target.name}">'+('原D_COMPACT' if variant=='compact' else '面积重心候选')+f'：{r["metrics"]["total_time"]:.2f}秒 · {r["metrics"]["engine_source_count"]}源</a>')
    html.append('<p>以上是30场开发集的回放；完整开发、独立验证和最终保留测试结果见结果报告，不以单场轨迹替代整体计时。</p>')
    (out/'route_comparison.html').write_text(''.join(html),encoding='utf-8')
    (out/'ROUTE_PAIR_SELECTION.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':print(json.dumps(build(),indent=2))
