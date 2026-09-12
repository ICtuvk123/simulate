"""Continuous geometry screening only; no scenario or task-time claims."""
import csv,json,time
from pathlib import Path
from directional_geometry import DirectionalCoverage,skeleton


def main():
    root=Path(__file__).resolve().parents[1];rows=[]
    for inner_count in (6,7,8):
        outer_count=2*inner_count
        for outer_radius in (1820.,1840.,1860.,1880.,1900.,1940.):
            for phase in (0.,180/outer_count):
                options=dict(inner_count=inner_count,outer_count=outer_count,inner_radius=995.,outer_radius=outer_radius,inner_phase=0.,outer_phase=phase)
                start=time.perf_counter();proof=DirectionalCoverage(time_budget=2.).prove(skeleton(**options))
                row={**options,'stations':1+inner_count+outer_count,'complete':proof['complete'],'visited':proof['visited_cells'],'wall_s':time.perf_counter()-start}
                rows.append(row)
    p=root/'reports/skeleton_geometry_screen.csv'
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print(json.dumps({'screened':len(rows),'certified':[r for r in rows if r['complete']]},indent=2))


if __name__=='__main__':main()
