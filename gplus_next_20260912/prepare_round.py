"""Preregister development-only screening, leaving 22001+ unseen for validation."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
variants=[dict(name='Gplus',kind='Gplus'),
          dict(name='Optical',kind='Optical'),
          dict(name='OpticalRisk',kind='Optical',extra=dict(optical_sequence_risk=.5)),
          dict(name='FutureAnchor',kind='Future',extra=dict(future_mode='anchor',future_budget_s=10)),
          dict(name='FutureRoute',kind='Future',extra=dict(future_mode='route',future_budget_s=10)),
          dict(name='RouteOrder',kind='Route')]
config=dict(phase='screen16',workers=6,variants=variants,cases=[dict(seed=i) for i in range(21001,21017)])
destination=ROOT/'screen16.json'
with destination.open('x',encoding='utf-8') as f:json.dump(config,f,indent=2)
print(destination)
