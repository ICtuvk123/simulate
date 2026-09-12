"""Paired route gallery with an explicit median and regression selection rule."""
import argparse,html,json,shutil,statistics
from pathlib import Path
from replay_html import create_replay
ROOT=Path(__file__).resolve().parents[1]


def build(phase,candidate,baseline='compact'):
    rows=[json.loads(s) for s in (ROOT/'reports'/phase/'runs.jsonl').read_text(encoding='utf-8').splitlines()]
    pairs={}
    for row in rows:
        if row['task']['variant'] in (candidate,baseline):pairs.setdefault(row['task']['seed'],{})[row['task']['variant']]=row
    if any(set(pair)!={candidate,baseline} or any(not r.get('metrics',{}).get('all_success') for r in pair.values()) for pair in pairs.values()):
        raise ValueError('This gallery requires complete registered pairs; do not hide failed scenes')
    gain=lambda s:pairs[s][baseline]['metrics']['total_time']-pairs[s][candidate]['metrics']['total_time']
    middle=statistics.median(gain(s) for s in pairs)
    chosen={'typical':min(pairs,key=lambda s:abs(gain(s)-middle)),
            'worst_difference':min(pairs,key=gain),'best_difference':max(pairs,key=gain)}
    directory=ROOT/'examples'/'r2'/phase;directory.mkdir(parents=True,exist_ok=True)
    selection=dict(phase=phase,candidate=candidate,baseline=baseline,selection_rule='median improvement, largest regression, largest improvement',cases={})
    content=['<!doctype html><meta charset="utf-8"><title>第四问动作优化·配对路线</title>',
             '<style>body{font:16px Microsoft YaHei,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;background:#f0f5f8;color:#223c49}p{line-height:1.8}section{background:white;border-radius:12px;padding:20px;margin:15px 0}a{display:inline-block;padding:12px;margin:8px;background:#e6f0f4;color:#075771;border-radius:8px}small{color:#657b86}</style>',
             '<h1>第四问动作优化 · 同场景路线对照</h1><p>所有路线来自实际本地反馈。真值默认关闭；选择典型差异、最大退步和最大改善三种案例，不能用最好一局代替整批结果。</p>',
             '<p>实验：'+html.escape(phase)+'；候选：'+html.escape(candidate)+'</p>']
    for label,seed in chosen.items():
        selection['cases'][label]=dict(seed=seed,gain_s=gain(seed),runs={})
        content.append('<section><b>'+{'typical':'典型差异','worst_difference':'最不利差异','best_difference':'最大改善'}[label]+f' · 场景 {seed}</b>')
        for variant in (baseline,candidate):
            row=pairs[seed][variant];metrics=row['metrics'];filename=f'{label}_{variant}.html'
            shutil.copy2(create_replay(ROOT/'runs'/row['run_id']),directory/filename)
            selection['cases'][label]['runs'][variant]=dict(run_id=row['run_id'],file=filename,
                         total_time_s=metrics['total_time'],sources=metrics['engine_source_count'])
            content.append(f'<a href="{filename}">{html.escape(variant)}：{metrics["total_time"]:.2f}秒 · {metrics["engine_source_count"]}源</a>')
        content.append(f'<p>本场差值（基线−候选）：{gain(seed):.2f}秒。</p></section>')
    content.append('<small>几何证书与配对全场指标见同名 reports 实验目录。正值表示候选更快，负值表示更慢。</small>')
    (directory/'index.html').write_text(''.join(content),encoding='utf-8')
    (directory/'SELECTION.json').write_text(json.dumps(selection,indent=2),encoding='utf-8')
    print(json.dumps(selection,indent=2));return directory


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase');p.add_argument('candidate');p.add_argument('--baseline',default='compact')
    a=p.parse_args();build(a.phase,a.candidate,a.baseline)
