"""Select representative finished runs by an explicit, reproducible rule."""
import argparse,json,shutil,statistics
from pathlib import Path
from replay_html import create_replay
ROOT=Path(__file__).resolve().parents[1]


def gallery(phase,candidate):
    rows=[json.loads(s) for s in (ROOT/'reports'/phase/'runs.jsonl').read_text().splitlines()]
    selected=[r for r in rows if r['task']['variant']==candidate]
    if not all(r.get('metrics',{}).get('all_success') for r in selected):raise ValueError('Cannot hide failed cases in a success gallery')
    median=statistics.median(r['metrics']['total_time'] for r in selected)
    examples={'median':min(selected,key=lambda r:abs(r['metrics']['total_time']-median)),
              'worst':max(selected,key=lambda r:r['metrics']['total_time'])}
    fourteen=[r for r in selected if r['metrics']['engine_source_count']==14]
    if fourteen:
        mid=statistics.median(r['metrics']['total_time'] for r in fourteen)
        examples['fourteen_sources']=min(fourteen,key=lambda r:abs(r['metrics']['total_time']-mid))
    out=ROOT/'examples';out.mkdir(exist_ok=True);index={}
    for name,r in examples.items():
        source=create_replay(ROOT/'runs'/r['run_id']);target=out/(name+'.html');shutil.copyfile(source,target)
        index[name]=dict(seed=r['task']['seed'],run_id=r['run_id'],sources=r['metrics']['engine_source_count'],
                         total_time=r['metrics']['total_time'],file=target.name)
    (out/'SELECTION.json').write_text(json.dumps(dict(phase=phase,candidate=candidate,examples=index,
                                                    selection='nearest median, worst, and 14-source median; no speed cherry-picking'),indent=2),encoding='utf-8')
    links='\n'.join('<li><a href="'+v['file']+'">'+label+'</a> — '+str(v['sources'])+' sources, '+str(round(v['total_time'],2))+' s</li>' for label,v in index.items())
    (out/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Q4 本地过程回放</title><style>body{max-width:850px;margin:60px auto;font:18px/1.8 system-ui}a{color:#16746d}</style><h1>第四问本地过程回放</h1><p>从已完成测试中按整场中位时间、最坏时间，以及14源场景的中位时间选择。源真值默认隐藏，只在结束后回放中可查看，未提供给决策器。</p><ul>'+links+'</ul><p>本地实验假设，非官方演练或正式成绩。</p></html>',encoding='utf-8')
    return index


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase');p.add_argument('candidate');a=p.parse_args()
    print(json.dumps(gallery(a.phase,a.candidate),indent=2))
