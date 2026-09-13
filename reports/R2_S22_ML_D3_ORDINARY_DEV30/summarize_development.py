import json
from pathlib import Path
from summary_utility import main
p=Path(__file__).resolve().parent
reg=json.loads((p/'registration.json').read_text())
rows=[json.loads(l) for f in sorted(p.glob('worker*.jsonl')) for l in f.read_text().splitlines()]
assert len(rows)==60==len(reg['tasks'])
assert {(r['task']['seed'],r['task']['variant']) for r in rows}=={(r['seed'],r['variant']) for r in reg['tasks']}
rows.sort(key=lambda r:(r['task']['seed'],r['task']['variant']))
(p/'runs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
main(p,'S22ML')
import diagnose_development
