"""At most 270 s of regular-ring geometry screening, never a scene run."""
import json,math,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code'))
from directional_geometry import skeleton,hull,in_hull,DirectionalCoverage


def main():
    started=time.perf_counter();deadline=started+270.
    points=[(0.,0.)]+[(r*math.cos(2*math.pi*k/96),r*math.sin(2*math.pi*k/96))
        for r in (200.,400.,600.,800.,950.,1100.,1400.,1799.99) for k in range(96)]
    prover=DirectionalCoverage(max_depth=13,max_cells=18000,time_budget=.7)
    configurations=[dict(inner_count=8,outer_count=13,inner_radius=995.,outer_radius=1860.,outer_phase=0.,control=True),
                    dict(inner_count=7,outer_count=14,inner_radius=995.,outer_radius=1860.,outer_phase=0.,control=True)]
    for inner,outer in ((8,12),(7,13),(6,14),(7,14)):
        minimum=1800/math.cos(math.pi/outer)
        radii=list(dict.fromkeys([float(math.ceil(minimum+delta)) for delta in (5,15,25,40,60)]+([1860.] if minimum<1860 else [1870.])))
        period=360/math.lcm(inner,outer)
        for ri in (995.,975.,950.,925.,900.,985.,999.):
            for ro in radii:
                for phase in (0.,period/4,period/2):
                    configurations.append(dict(inner_count=inner,outer_count=outer,inner_radius=ri,outer_radius=ro,outer_phase=phase,control=False))
    results=[];seen=set()
    for config in configurations:
        if time.perf_counter()>=deadline:break
        key=tuple(config[k] for k in ('inner_count','outer_count','inner_radius','outer_radius','outer_phase'))
        if key in seen:continue
        seen.add(key);params={k:v for k,v in config.items() if k!='control'}
        stations=skeleton(**params);gap=config['outer_radius']*math.cos(math.pi/config['outer_count'])-1800
        if gap<=1e-5:
            result=dict(complete=False,reason='outer_hull_cannot_contain_target_circle_with_margin')
        else:
            rejected=None
            for x in points:
                near=[s for s in stations if math.dist(s,x)<=1000.]
                if not in_hull(hull(near),x,-1e-7):rejected=x;break
            result=(dict(complete=False,reason='uncovered_local_hull_witness',witness=rejected) if rejected is not None
                    else prover.prove(stations))
        row=dict(parameters=params,station_count=len(stations),control=config['control'],outer_hull_inradius_slack_m=gap,result=result)
        results.append(row)
        if result['complete']:print('PASS',row,flush=True)
    passed=[r for r in results if r['result']['complete']]
    summary=dict(registered_configurations=len(configurations),unique_checked=len(results),
                 continuous_passed=len(passed),new_21_station_passed=sum(r['station_count']==21 for r in passed),
                 wall_time_s=time.perf_counter()-started,budget_s=270.,budget_exhausted=len(seen)<len({tuple(c[k] for k in ('inner_count','outer_count','inner_radius','outer_radius','outer_phase')) for c in configurations}),
                 actual_scene_runs=0,geometric_proofs_only=True,
                 source_hash=hashlib.sha256((ROOT/'code/directional_geometry.py').read_bytes()).hexdigest())
    output=ROOT/'reports/R2_SMALL_SKELETON_SCREEN.json'
    output.write_bytes(json.dumps(dict(summary=summary,passed=passed,results=results),indent=2).encode())
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
