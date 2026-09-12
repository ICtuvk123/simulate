"""Prepare separate evaluator-owned pressure definitions, not policy inputs."""
import json,math
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[1]
    scenes={
        '430001':dict(scenario='boundary',orientation='outward',source_mix='mixed',count=16,reception='minimum',error_mode='plus_one'),
        '430002':dict(scenario='boundary',orientation='outward',source_mix='mixed',count=10,reception='maximum',error_mode='minus_one'),
        '430003':dict(scenario='clustered',source_mix='mixed',count=16,reception='minimum',error_mode='smooth'),
        '430004':dict(scenario='uniform',source_mix='mixed',count=10,reception='maximum',error_mode='smooth'),
        '430005':dict(scenario='boundary',orientation='angle_boundary',source_mix='mixed',count=16,reception='minimum',error_mode='fixed_hash'),
        '430006':dict(scenario='boundary',orientation='angle_boundary',source_mix='mixed',count=10,reception='maximum',error_mode='plus_one'),
        '430007':dict(scenario='clustered',source_mix='omni',count=10,reception='minimum'),
        '430008':dict(scenario='boundary',source_mix='omni',count=16,reception='maximum',error_mode='smooth'),
        '430009':dict(scenario='boundary',source_mix='directional',orientation='outward',count=16,reception='minimum',error_mode='plus_one'),
        '430010':dict(scenario='uniform',source_mix='directional',orientation='inward',count=10,reception='maximum',error_mode='minus_one'),
        '430011':dict(scenario='boundary',source_mix='directional',orientation='angle_boundary',count=16,reception='minimum',error_mode='fixed_hash'),
        '430012':dict(scenario='clustered',source_mix='directional',count=10,reception='maximum',error_mode='smooth'),
    }
    sources=[]
    for ch in range(1,11):
        a=ch*2*math.pi/10
        x,y=(4.,0.) if ch==1 else (600.,-.1) if ch==2 else (1700*math.cos(a),1700*math.sin(a))
        direction=180. if ch==1 else None if ch%2==0 else math.degrees(a)%360
        sources.append(dict(channel=ch,x=x,y=y,radius=1000. if ch%2 else 1500.,direction_deg=direction))
    scenes['430013']=dict(sources=sources,error_mode='plus_one')
    sources2=[dict(s) for s in sources];sources2[0].update(x=1800.,y=0.,direction_deg=0.)
    sources2[1].update(x=0.,y=1800.,direction_deg=90.)
    sources2[2].update(x=0.,y=0.,direction_deg=None)
    scenes['430014']=dict(sources=sources2,error_mode='minus_one')
    (root/'configs/PRESSURE_SCENES.json').write_text(json.dumps(scenes,indent=2),encoding='utf-8')
    (root/'reports/PRESSURE_PLAN.md').write_text('# 压力集预登记\n\n430001–430006：混合源，边界向外、角边界、聚集、10/16个、最小/最大半径与固定/平滑/极端误差。430007–430008：额外全向-only。430009–430012：额外定向-only。430013–430014：固定压力布局，近距离、跨0/360读数、精确1800米边界，仍只传入场景引擎。与主混合随机结果分别报告，不合并成主平均数。\n',encoding='utf-8')
    print('Registered 14 pressure scenes; none executed by this script.')


if __name__=='__main__':main()
