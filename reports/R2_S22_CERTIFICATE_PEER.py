"""Independent high-precision audit of one ACTUAL S22 empty-channel station set.

Enumerate the finite quadtree using floating geometry, then independently
recheck every accepted cell with Decimal arithmetic on the exact binary
coordinates accepted by the API. No source truths or engine state are read.
"""
import argparse,hashlib,json,math,sys,time
from decimal import Decimal,localcontext
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code'))
from directional_geometry import hull,in_hull,corners,box_distance,DirectionalCoverage
from independent_exit import cell_certificate
from coverage import validate_completion


def actual_empty_stations(phase):
    rows=[json.loads(line) for line in (phase/'runs.jsonl').read_text().splitlines()]
    for row in rows:
        if row['task']['variant']!='s22':continue
        journal=Path(row['directory'])/'requests.jsonl'
        records=[json.loads(line) for line in journal.read_text().splitlines()]
        certificate=next(r['certificate'] for r in reversed(records) if r.get('reason')=='completion_proved')
        if certificate['kind']!='q4_actual_directional_local_hull':continue
        ch=certificate['empty_channels'][0];stations=[];seen=set()
        for r in records:
            if r.get('event')!='response' or r['path']!='/measure' or r.get('http_status')!=200:continue
            payload=r['payload'];response=json.loads(r['response_body'])
            if payload['channel']!=ch or response.get('accepted') is not True:continue
            if payload['request_id'] in seen:continue
            seen.add(payload['request_id']);assert response['measure_result']=='no_signal'
            point=payload['position'];stations.append((point['x'],point['y']))
        return journal,ch,sorted(set(stations))
    raise ValueError('No completed S22 actual empty-channel history')


def decimal_certificate(stations):
    pending=[((-1800.,-1800.,1800.,1800.),0)];visited=accepted=0
    minimum_range_slack=Decimal('Infinity');minimum_hull_distance=Decimal('Infinity')
    digest=hashlib.sha256()
    with localcontext() as context:
        context.prec=60
        dec=lambda p:tuple(Decimal.from_float(float(v)) for v in p)
        for_cell_radius=Decimal('999.99999')**2
        while pending:
            box,depth=pending.pop();visited+=1
            if box_distance((0.,0.),box)>1800.00001:
                x0,y0,x1,y1=map(Decimal.from_float,box)
                dx=max(x0,Decimal(0),-x1);dy=max(y0,Decimal(0),-y1)
                assert dx*dx+dy*dy>Decimal(1800)**2
                continue
            cs=corners(box)
            near=[s for s in stations if all(math.dist(s,c)<=999.99999 for c in cs)]
            h=hull(near)
            if len(h)>=3 and all(in_hull(h,c,1e-8) for c in cs):
                dc=list(map(dec,cs));dn=list(map(dec,near));dh=list(map(dec,h))
                for p in dn:
                    for q in dc:
                        squared=sum((p[k]-q[k])**2 for k in (0,1))
                        assert squared<=for_cell_radius
                        minimum_range_slack=min(minimum_range_slack,Decimal(1000)-squared.sqrt())
                for a,b in zip(dh,dh[1:]+dh[:1]):
                    ex,ey=b[0]-a[0],b[1]-a[1];edge=(ex*ex+ey*ey).sqrt()
                    assert edge>0
                    for q in dc:
                        product=ex*(q[1]-a[1])-ey*(q[0]-a[0])
                        assert product>=Decimal('0.00000001')*edge
                        minimum_hull_distance=min(minimum_hull_distance,product/edge)
                accepted+=1;digest.update(json.dumps([box,h],separators=(',',':')).encode())
                continue
            assert depth<13,'Unproved cell at maximum depth'
            x0,y0,x1,y1=box;x=(x0+x1)/2;y=(y0+y1)/2
            pending.extend((child,depth+1) for child in [(x0,y0,x,y),(x,y0,x1,y),(x,y,x1,y1),(x0,y,x,y1)])
    return dict(complete=True,visited_cells=visited,accepted_cells=accepted,
                minimum_actual_range_slack_m=str(minimum_range_slack),
                minimum_actual_hull_boundary_distance_m=str(minimum_hull_distance),
                accepted_leaf_hash=digest.hexdigest(),decimal_precision=60)


def faulty_exit_checks(stations):
    cleared=set(range(1,11));unknown=set(range(11,21))
    certificate=dict(kind='q4_actual_directional_local_hull',cleared_channels=sorted(cleared),empty_channels=sorted(unknown))
    successes=[dict(path='/clear',channel=ch,result='success') for ch in cleared]
    def events(omit=None,positive=False):
        scans=[dict(path='/measure',channel=ch,result='no_signal',position=s)
               for ch in unknown for s in stations if not(ch==11 and s==omit)]
        if positive:scans.append(dict(path='/measure',channel=11,result='direction',position=(0.,0.)))
        return successes+scans+[dict(path='/exit')]
    assert validate_completion(events(),certificate)[0]
    checker=DirectionalCoverage(time_budget=float('inf'))
    assert checker.prove(stations)['complete'] # Deliberately pre-cache the whole PLAN.
    for missing in stations:
        subset=[p for p in stations if p!=missing]
        assert not checker.prove(subset)['complete']
        assert not cell_certificate(subset,budget_s=30.)['complete']
        assert not validate_completion(events(missing),certificate)[0]
    assert not validate_completion(events(positive=True),certificate)[0]
    bad=dict(certificate,kind='q4_sixteen_actual_successes')
    assert not validate_completion(events(),bad)[0]
    for depth,cells in ((0,250000),(13,1)):
        assert not DirectionalCoverage(max_depth=depth,max_cells=cells,time_budget=float('inf')).prove(stations)['complete']
    return dict(full_actual_partition_accepted=True,all_single_missing_station_partitions_rejected=len(stations),
                cached_plan_cannot_certify_actual_subset=True,known_uncleared_rejected=True,
                false_sixteen_rejected=True,exhausted_geometry_budgets_unproved=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();started=time.perf_counter()
    journal,ch,stations=actual_empty_stations(a.phase);assert len(stations)==22
    geometry=decimal_certificate(stations);faults=faulty_exit_checks(stations)
    # Conservative rectangle around the full first 1.01-degree positive sector.
    height=1500*math.tan(math.radians(1.01));max_dy=max(12.5,height-25)
    fallback_bound=math.hypot(12.5,max_dy);assert fallback_bound<20
    result=dict(journal=str(journal),journal_sha256=hashlib.sha256(journal.read_bytes()).hexdigest(),
                actual_empty_channel=ch,actual_stations=stations,high_precision_geometry=geometry,
                adversarial_certificate_checks=faults,optical_fallback=dict(unique_points=183,
                    sector_rect_y_bound_m=height,continuous_max_nearest_point_distance_m=fallback_bound,
                    proof='Nearest x of 0:25:1500 is <=12.5m; nearest y of -25,0,25 is <=12.5m over the entire 1.01-degree sector rectangle'),
                max_source_localize_calls=16*11,max_search_tasks_after_initial=21,
                combined_task_bound=16*11+21,controller_decision_guard=500,
                root_controller_source_hash=hashlib.sha256((a.phase.parents[1]/'code/q4controller.py').read_bytes()).hexdigest(),
                wall_time_s=time.perf_counter()-started,scene_or_official_test_run=False,engine_truth_read=False)
    a.output.write_bytes(json.dumps(result,indent=2).encode())
    print(json.dumps({k:v for k,v in result.items() if k!='actual_stations'},indent=2))


if __name__=='__main__':main()
