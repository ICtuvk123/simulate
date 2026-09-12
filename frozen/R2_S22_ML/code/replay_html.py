"""Offline post-run visualization. Never imported by the decision controller."""
import argparse,json
from pathlib import Path


def create_replay(directory):
    directory=Path(directory)
    records=[json.loads(s) for s in (directory/'requests.jsonl').read_text(encoding='utf-8').splitlines()]
    evaluation=json.loads((directory/'evaluation.json').read_text(encoding='utf-8'))
    metrics=json.loads((directory/'metrics.json').read_text(encoding='utf-8'))
    frames=[];seen=set();role='';regions={};last=(0.,0.);distance=0.;rf=optical=switch=success=0;channel=1
    for row in records:
        if row.get('reason')=='q4_action_role':role=row['role']
        if row.get('reason') in ('q4_positive_region','q4_paired_negative_clip','q4_negative_history_clip','q4_reused_negative_clip'):
            ch=row.get('channel',row.get('witness',{}).get('channel'));regions[ch]=row['polygon']
            if frames:frames[-1]['regions']=dict(regions)
        if row.get('event')!='response' or row['http_status']!=200:continue
        response=json.loads(row['response_body']);payload=row['payload'];rid=payload['request_id']
        if not response.get('accepted') or rid in seen:continue
        seen.add(rid);path=row['path'];ch=payload.get('channel');point=payload.get('position',dict(x=last[0],y=last[1]));point=(point['x'],point['y'])
        step=((point[0]-last[0])**2+(point[1]-last[1])**2)**.5;distance+=step
        if path=='/measure':rf+=1;switch+=int(ch!=channel);channel=ch
        if path=='/clear':
            optical+=1
            if response['clear_result']=='success':success+=1;regions.pop(ch,None)
        frames.append(dict(path=path,point=point,ch=ch,result=response.get('measure_result',response.get('clear_result',response.get('exit_reason','entered'))),
                           bearing=response.get('svd_deg'),time=response['virtual_time_s'],role=role if path in ('/measure','/clear') else '',regions=dict(regions),distance=distance,
                           rf=rf,switch=switch,optical=optical,success=success))
        last=point
    data=dict(frames=frames,sources=evaluation['sources'],summary={k:metrics[k] for k in ['version','all_success','total_time','mean_time_per_source','policy_wall_time_s','fallback_count']})
    template=(Path(__file__).parent/'replay_template.html').read_text(encoding='utf-8')
    content=template.replace('__Q4_DATA__',json.dumps(data,ensure_ascii=False).replace('</','<\\/'))
    path=directory/'replay.html';path.write_text(content,encoding='utf-8');return path


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');a=p.parse_args();print(create_replay(a.directory))
