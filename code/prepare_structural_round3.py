import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]/'local_simulator';sys.path.insert(0,str(ROOT/'code'))
from e_policy_presets import FROZEN_E_OPTIONS
base={**FROZEN_E_OPTIONS,'negative_halfplanes':True,'joint_history':True,'task_search':False,
      'tail_cost':False,'optical_exclusions':False,'safe_shared':False,'strip_fallback':True,
      'negative_disks':False,'flexible_search':False,'forecast_budget':False,'via_clear':False}
variants=[dict(name='frozen_E',strategy='E')]
for name,updates in [('budgeted_search',dict(task_search=True,flexible_search=True,forecast_budget=True)),
                    ('through_clear',dict(via_clear=True)),
                    ('through_negative',dict(via_clear=True,negative_disks=True,optical_exclusions=True)),
                    ('budgeted_through',dict(task_search=True,flexible_search=True,forecast_budget=True,via_clear=True))]:
    variants.append(dict(name=name,strategy='F',policy_options={**base,**updates}))
config=dict(cases=[dict(seed=s,scenario='uniform',reception='mixed',error_mode='fixed_hash') for s in range(7011,7023)],
            variants=variants,workers=4,holdout_seeds=list(range(8001,8101)))
path=ROOT/'reports'/'optimization'/'F_round3_config.json'
if path.exists():raise FileExistsError(path)
path.write_text(json.dumps(config,indent=2),encoding='utf-8');print(path)
