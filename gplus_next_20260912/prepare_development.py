import json
from pathlib import Path

root=Path(__file__).resolve().parent
variants=[dict(name='Gplus',kind='Gplus'),dict(name='Optical',kind='Optical'),
          dict(name='RouteOrder',kind='Route'),dict(name='OpticalRoute',kind='OpticalRoute'),
          dict(name='OpticalTail',kind='Optical',extra=dict(optical_tail_weight=1)),
          dict(name='FutureAnchor',kind='Future',extra=dict(future_mode='anchor',future_budget_s=10))]
with (root/'development40.json').open('x',encoding='utf-8') as stream:
    json.dump(dict(phase='development40',workers=6,variants=variants,
                   cases=[dict(seed=i) for i in range(21101,21141)]),stream,indent=2)
