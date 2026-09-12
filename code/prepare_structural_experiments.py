"""Prepare local structural ablations without executing an environment."""
import csv
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]/'local_simulator'
sys.path.insert(0,str(ROOT/'code'))
from e_policy_presets import FROZEN_E_OPTIONS


def main():
    dest=ROOT/'reports'/'optimization'
    rows=list(csv.DictReader((dest/'E_validation100_runs.csv').open(encoding='utf-8-sig')))
    values=[]
    for name in ('frozen_D','frozen_E'):
        group=[r for r in rows if r['variant']==name]
        values.append(dict(strategy=name,n=len(group),mean_total_s=statistics.mean(float(r['total_time']) for r in group),
                           mean_per_case_s_per_source=statistics.mean(float(r['total_time'])/int(r['clear_count']) for r in group),
                           pooled_s_per_source=sum(float(r['total_time']) for r in group)/sum(int(r['clear_count']) for r in group),
                           min_source_count=min(int(r['clear_count']) for r in group),
                           max_source_count=max(int(r['clear_count']) for r in group)))
    (dest/'F_metric_correction.json').write_text(json.dumps(values,indent=2),encoding='utf-8')
    options={**FROZEN_E_OPTIONS,'negative_halfplanes':False,'joint_history':False,
             'task_search':False,'tail_cost':False,'optical_exclusions':False,'safe_shared':False,'strip_fallback':True}
    def variant(name,**updates):
        return dict(name=name,strategy='F',policy_options={**options,**updates})
    info=dict(negative_halfplanes=True,joint_history=True)
    variants=[dict(name='frozen_E',strategy='E'),variant('negative_only',negative_halfplanes=True),
              variant('joint_only',joint_history=True),variant('information',**info),
              variant('task_search',**info,task_search=True),
              variant('task_tail',**info,task_search=True,tail_cost=True),
              variant('task_optical',**info,task_search=True,optical_exclusions=True),
              variant('task_safe_shared',**info,task_search=True,safe_shared=True)]
    setup=dict(cases=[dict(seed=s,scenario='uniform',reception='mixed',error_mode='fixed_hash') for s in range(7001,7009)],
               variants=variants,workers=4,holdout_seeds=list(range(8001,8101)))
    target=dest/'F_round1_config.json'
    if target.exists():
        raise FileExistsError(target)
    target.write_text(json.dumps(setup,indent=2),encoding='utf-8')
    print(json.dumps(values,indent=2))
    print(str(target))


if __name__=='__main__':
    main()
