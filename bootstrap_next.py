from pathlib import Path
import shutil
import hashlib
import json

project=Path(__file__).resolve().parent
old=project/'time_push_20260912'; new=project/'gplus_next_20260912'
new.mkdir(exist_ok=True)
for name in ('code','tests','reports','figures'):(new/name).mkdir(exist_ok=True)
freeze=json.loads((old/'FREEZE.json').read_text(encoding='utf-8'))
for source in (old/'code').glob('*.py'):
    assert hashlib.sha256(source.read_bytes()).hexdigest()==freeze['experiment_files_sha256'][source.name]
    destination=new/'code'/source.name
    if destination.exists():assert destination.read_bytes()==source.read_bytes()
    else:shutil.copy2(source,destination)
for name in ('candidate.json','FREEZE.json'):
    shutil.copy2(old/name,new/('BASELINE_'+name))
shutil.copy2(old/'compare.py',new/'compare.py')
print(str(new))
