"""Second implementation of the exit proof, with no controller geometry import.

Reconstruct the actual accepted actions through the public protocol ledger, then
use a fresh quadtree and a separately written convex-hull test. No cached policy
state, proposed station or source truth is accepted as input.
"""
import argparse,hashlib,json,math,time
from pathlib import Path
from q3client import Ledger,decode_response


def orientation(a,b,p):
    return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])


def boundary(points):
    ordered=sorted(set(map(tuple,points)))
    if len(ordered)<3:return ordered
    lower=[];upper=[]
    for p in ordered:
        while len(lower)>1 and orientation(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    for p in reversed(ordered):
        while len(upper)>1 and orientation(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]


def cell_certificate(stations,max_depth=13,max_cells=250000,budget_s=30.):
    start=time.monotonic();stack=[(-1800.,-1800.,1800.,1800.,0)]
    visited=accepted=0;digest=hashlib.sha256()
    stations=sorted(set(map(tuple,stations)))
    while stack:
        if visited>=max_cells or time.monotonic()-start>budget_s:
            return dict(complete=False,reason='budget',visited=visited)
        x0,y0,x1,y1,depth=stack.pop();visited+=1
        dx=max(x0,0.,-x1);dy=max(y0,0.,-y1)
        if math.hypot(dx,dy)>1800.00001:continue
        vertices=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
        local=[]
        for s in stations:
            if all(math.dist(s,v)<=999.99999 for v in vertices):local.append(s)
        polygon=boundary(local)
        if len(polygon)>=3:
            edges=list(zip(polygon,polygon[1:]+polygon[:1]))
            if all(orientation(a,b,v)>=1e-8*math.dist(a,b) for a,b in edges for v in vertices):
                accepted+=1
                digest.update(json.dumps([x0,y0,x1,y1,polygon],separators=(',',':')).encode())
                continue
        if depth>=max_depth:
            return dict(complete=False,reason='unproved_cell',cell=[x0,y0,x1,y1],visited=visited)
        xm=(x0+x1)/2;ym=(y0+y1)/2;d=depth+1
        stack.extend([(x0,y0,xm,ym,d),(xm,y0,x1,ym,d),(xm,ym,x1,y1,d),(x0,ym,xm,y1,d)])
    return dict(complete=True,visited=visited,accepted_cells=accepted,
                leaf_proof_sha256=digest.hexdigest(),station_count=len(stations))


def verify(journal):
    ledger=Ledger();declared=None
    for line in Path(journal).read_text(encoding='utf-8').splitlines():
        r=decode_response(line)
        if r.get('reason')=='completion_proved':declared=r.get('certificate')
        if r.get('event')=='response':
            ledger.apply(r['path'],r['payload'],r['http_status'],decode_response(r['response_body']))
    clear=set(ledger.cleared);errors=[];proofs={};cache={}
    if not ledger.exited or not ledger.events or ledger.events[-1]['path']!='/exit':errors.append('not_exited')
    if not 10<=len(clear)<=16:errors.append('invalid_success_count')
    if ledger.accounting_warnings:errors.append('accounting_disagreement')
    if ledger.rejected_count:errors.append('rejected_response_in_run')
    if not declared or set(declared.get('cleared_channels',[]))!=clear:errors.append('declared_clear_partition')
    if len(clear)<16:
        if not declared or declared.get('kind')!='q4_actual_directional_local_hull':errors.append('invalid_proof_kind')
        missing=set(range(1,21))-clear
        if not declared or set(declared.get('empty_channels',[]))!=missing:errors.append('declared_empty_partition')
        for ch in sorted(missing):
            observations=[e for e in ledger.events if e['path']=='/measure' and e['channel']==ch]
            if any(e['result']!='no_signal' for e in observations):
                errors.append('known_uncleared_'+str(ch));continue
            stations=tuple(sorted(set(tuple(e['position']) for e in observations)))
            if stations not in cache:cache[stations]=cell_certificate(stations)
            proofs[ch]=cache[stations]
            if not proofs[ch]['complete']:errors.append('unproved_empty_'+str(ch))
    elif declared and declared.get('kind')!='q4_sixteen_actual_successes':errors.append('invalid_sixteen_kind')
    return dict(valid=not errors,errors=errors,clear_count=len(clear),total_time=ledger.virtual_time,
                actual_channel_proofs=proofs,truth_read=False,controller_geometry_imported=False,
                journal_sha256=hashlib.sha256(Path(journal).read_bytes()).hexdigest())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('journal');p.add_argument('--output');a=p.parse_args()
    result=verify(a.journal)
    if a.output:Path(a.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['valid'] else 1)
