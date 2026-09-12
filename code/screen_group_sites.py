"""Continuous screening of joint outer-station removal and neighbor relocation."""
import json,math,time
from pathlib import Path
from directional_geometry import skeleton,DirectionalCoverage
ROOT=Path(__file__).resolve().parents[1]


def screen():
    result=[];start=time.monotonic()
    for ni,no,outer,removed_sets in [(8,16,1840,[(0,),(0,8)]),(7,14,1860,[(0,),(0,6)])]:
        for removed in removed_sets:
            moved=sorted({(j+side)%no for j in removed for side in (-1,1)})
            for radius in (1950.,2000.,2050.,2100.,2200.,2300.):
                original=skeleton(inner_count=ni,outer_count=no,outer_radius=outer);sites=original[:1+ni]
                for j in range(no):
                    if j in removed:continue
                    r=radius if j in moved else outer;a=2*math.pi*j/no
                    sites.append((r*math.cos(a),r*math.sin(a)))
                proof=DirectionalCoverage(max_depth=14,time_budget=4.).prove(sites)
                row=dict(inner=ni,outer_before=no,removed=list(removed),moved=moved,moved_radius=radius,
                         count=len(sites),proof=proof,sites=sites if proof['complete'] else None)
                result.append(row)
                print(json.dumps({k:v for k,v in row.items() if k!='sites'}),flush=True)
    path=ROOT/'reports/group_station_geometry_screen.json'
    path.write_text(json.dumps(dict(elapsed_s=time.monotonic()-start,candidates=result),indent=2),encoding='utf-8')


if __name__=='__main__':screen()
