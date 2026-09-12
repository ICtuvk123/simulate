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


def postcheck(journal_path,evaluation):
    records=[json.loads(s) for s in Path(journal_path).read_text(encoding='utf-8').splitlines()]
    truth={s['channel']:(s['x'],s['y']) for s in evaluation['sources']}
    positive={};negative={};region_checks=0;witnesses=0;errors=[]
    for row in records:
        if row['event']=='response' and row['http_status']==200:
            response=json.loads(row['response_body'])
            if response.get('accepted') and row['path']=='/measure':
                ch=row['payload']['channel'];p=row['payload']['position'];q=(p['x'],p['y'])
                if response['measure_result']=='direction':positive.setdefault(ch,[]).append((q,response['svd_deg']))
                elif response['measure_result']=='no_signal':negative.setdefault(ch,[]).append(q)
        if row.get('reason')=='q4_paired_negative_clip':
            w=row['witness'];ch=w['channel'];s=w['station'];a=math.radians(w['bearing'])
            d=(math.cos(a),math.sin(a));n=(-d[1],d[0]);t=w['t'];b=w['b']
            ends=[tuple(s[k]+t*d[k]+sign*b*n[k] for k in (0,1)) for sign in (1,-1)]
            valid=(any(math.dist(p,s)<1e-9 and beta==w['bearing'] for p,beta in positive.get(ch,[]))
                   and t>=0 and b>=t*math.tan(ALPHA)+MARGIN
                   and all(math.dist(q,v)<=1000-MARGIN+1e-8 for q in ends for v in w['before_polygon'])
                   and all(any(math.dist(q,p)<1e-8 for p in negative.get(ch,[])) for q in ends)
                   and w.get('results')==['no_signal','no_signal'])
            if not valid:errors.append('invalid_pair_witness')
            witnesses+=1
        if row.get('reason') in ('q4_positive_region','q4_paired_negative_clip'):
            ch=row.get('channel',row.get('witness',{}).get('channel'))
            if ch not in truth or not contains(row['polygon'],truth[ch],tolerance=1e-3):
                errors.append('truth_excluded_channel_'+str(ch))
            region_checks+=1
    return dict(valid=not errors,errors=errors,region_checks=region_checks,paired_witnesses=witnesses)


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
