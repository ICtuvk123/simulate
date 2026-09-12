"""Continuous geometry screen only; not whole-task speed evidence."""
import csv,json,time
from pathlib import Path
from directional_geometry import DirectionalCoverage,skeleton
ROOT=Path(__file__).resolve().parents[1]


def main():
    rows=[]
    for inner_count,outer_radius in ((8,1840),(8,1860),(7,1860),(7,1880)):
        for inner_radius in (800,825,850,875,900,925,950,975,995):
            started=time.perf_counter()
            cert=DirectionalCoverage().prove(skeleton(inner_count,2*inner_count,inner_radius,outer_radius))
            row=dict(inner_count=inner_count,outer_count=2*inner_count,inner_radius=inner_radius,outer_radius=outer_radius,
                     complete=cert['complete'],visited_cells=cert['visited_cells'],reason=cert['reason'],wall_s=time.perf_counter()-started)
            rows.append(row);print(json.dumps(row),flush=True)
    with (ROOT/'reports/inner_radius_geometry_screen.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


if __name__=='__main__':main()
