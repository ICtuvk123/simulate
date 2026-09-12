"""Post-run checks and pure-feedback reproduction. The policy never sees truth."""
import json,math,sys
from pathlib import Path
from geometry import contains
from directional_geometry import ALPHA,MARGIN
from q4controller import Q4Controller
from q3client import Client

GUARDED=False


def hook(event,args):
    if GUARDED and event in ('open','os.listdir','os.scandir','socket.connect','socket.getaddrinfo','subprocess.Popen'):
        raise RuntimeError('Forbidden decision I/O: '+event)


sys.addaudithook(hook)


def audit_pair_witness(w,positive,negative):
    """Independent reconstruction from accepted chronological observations.

    Deliberately does not call paired_probe/verify_paired_geometry, nor trust
    geometry_valid or the recorded squared gap. Future/planned stations cannot
    supply either the positive reception premise or the two negative endpoints.
    """
    try:
        ch=w['channel'];s=w['station'];angle=math.radians(w['bearing'])
        d=(math.cos(angle),math.sin(angle));n=(-d[1],d[0]);t=w['t'];b=w['b']
        if not all(math.isfinite(v) for v in [*s,angle,t,b]):return False
        ends=[tuple(s[k]+t*d[k]+sign*b*n[k] for k in (0,1)) for sign in (1,-1)]
        geometry=(t>=0 and b>=t*math.tan(ALPHA)+MARGIN and bool(w['before_polygon'])
                  and math.dist(w['d'],d)<=1e-9 and math.dist(w['n'],n)<=1e-9
                  and math.dist(w['plus'],ends[0])<=1e-8 and math.dist(w['minus'],ends[1])<=1e-8)
        kind=w.get('radius_witness','minimum_radius_all_region')
        if kind=='positive_station_radius':
            geometry=geometry and t>0 and b*b+2*t*b*math.tan(ALPHA)<=t*t-MARGIN
        elif kind=='minimum_radius_all_region':
            geometry=geometry and all(math.dist(q,v)<=1000-MARGIN+1e-8 for q in ends for v in w['before_polygon'])
        else:return False
        return (geometry and any(math.dist(p,s)<1e-9 and beta==w['bearing'] for p,beta in positive.get(ch,[]))
                and all(any(math.dist(q,p)<1e-8 for p in negative.get(ch,[])) for q in ends)
                and w.get('results')==['no_signal','no_signal'])
    except (KeyError,ValueError,TypeError,OverflowError):return False


def postcheck(journal_path,evaluation):
    records=[json.loads(s) for s in Path(journal_path).read_text(encoding='utf-8').splitlines()]
    truth={s['channel']:(s['x'],s['y']) for s in evaluation['sources']}
    positive={};negative={};region_checks=0;witnesses=0;optical_covers=0;errors=[]
    for row in records:
        if row['event']=='response' and row['http_status']==200:
            response=json.loads(row['response_body'])
            if response.get('accepted') and row['path']=='/measure':
                ch=row['payload']['channel'];p=row['payload']['position'];q=(p['x'],p['y'])
                if response['measure_result']=='direction':positive.setdefault(ch,[]).append((q,response['svd_deg']))
                elif response['measure_result']=='no_signal':negative.setdefault(ch,[]).append(q)
        if row.get('reason')=='q4_paired_negative_clip':
            w=row['witness'];valid=audit_pair_witness(w,positive,negative)
            if not valid:errors.append('invalid_pair_witness')
            witnesses+=1
        if row.get('reason')=='q4_compact_optical_cover':
            w=row['witness'];d=w['d'];n=w['n'];x0,y0,x1,y1=w['bounds'];nx=w['nx'];ny=w['ny']
            contained=all(x0<=sum(p[k]*d[k] for k in (0,1))<=x1 and
                          y0<=sum(p[k]*n[k] for k in (0,1))<=y1 for p in w['before_polygon'])
            centers=[tuple((x0+(i+.5)*(x1-x0)/nx)*d[k]+(y0+(j+.5)*(y1-y0)/ny)*n[k] for k in (0,1))
                     for j in range(ny) for i in range(nx)]
            valid=(contained and nx>0 and ny>0 and len(row['points'])==nx*ny
                   and abs(math.hypot(*d)-1)<1e-10 and abs(math.hypot(*n)-1)<1e-10
                   and abs(sum(d[k]*n[k] for k in (0,1)))<1e-10
                   and math.hypot((x1-x0)/(2*nx),(y1-y0)/(2*ny))<=20-1e-5+1e-10
                   and all(any(math.dist(a,b)<=1e-8 for b in row['points']) for a in centers)
                   and contains(w['before_polygon'],truth[row['channel']],tolerance=1e-3))
            if not valid:errors.append('invalid_compact_optical_cover')
            optical_covers+=1
        if row.get('reason') in ('q4_positive_region','q4_paired_negative_clip'):
            ch=row.get('channel',row.get('witness',{}).get('channel'))
            if ch not in truth or not contains(row['polygon'],truth[ch],tolerance=1e-3):
                errors.append('truth_excluded_channel_'+str(ch))
            region_checks+=1
    return dict(valid=not errors,errors=errors,region_checks=region_checks,paired_witnesses=witnesses,compact_optical_covers=optical_covers)


class MemoryJournal:
    def append(self,event):pass


def replay(journal_path):
    global GUARDED
    assert 'q4engine' not in sys.modules
    records=[json.loads(s) for s in Path(journal_path).read_text(encoding='utf-8').splitlines()]
    options=next(r for r in records if r['event']=='metadata')['policy_options']
    replies=[r for r in records if r['event']=='response'];position=0
    del records
    def action(p):return {k:v for k,v in p.items() if k not in ('request_id','robot_id')}
    def transport(path,body,timeout):
        nonlocal position
        recorded=replies[position]
        assert path==recorded['path'] and action(json.loads(body))==action(recorded['payload']),position
        position+=1
        return recorded['http_status'],recorded['response_body']
    client=Client('local-robot',MemoryJournal(),transport=transport)
    GUARDED=True
    try:Q4Controller(client,options).run()
    finally:GUARDED=False
    assert position==len(replies) and client.ledger.exited
    return dict(valid=True,actions=position,engine_imported=False,truth_read=False,seed_received=False)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('journal');args=p.parse_args()
    print(json.dumps(replay(args.journal)))
