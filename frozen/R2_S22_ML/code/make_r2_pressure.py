"""Register evaluator-only round-two pressure cases; never call a policy."""
import json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def radial_sources(count,radius_fn,heading_fn,phase=0.):
    sources=[]
    for k in range(count):
        angle=phase+360*k/count;rad=math.radians(angle);radius=radius_fn(k)
        sources.append(dict(channel=k+1,x=radius*math.cos(rad),y=radius*math.sin(rad),
                            radius=1000. if k%2==0 else 1500.,direction_deg=heading_fn(k,angle)))
    return sources


def main():
    previous=json.loads((ROOT/'configs/PRESSURE_SCENES.json').read_text())
    scenes={str(int(seed)+100000):value for seed,value in previous.items()}
    scenes['530015']=dict(source_mix='directional',error_mode='plus_one',sources=
        radial_sources(16,lambda k:1600.,lambda k,a:(a+90+(1e-7 if k%2 else -1e-7))%360,phase=11.25))
    scenes['530016']=dict(source_mix='mixed',error_mode='minus_one',sources=
        radial_sources(10,lambda k:1000.+(-1e-6 if k%2 else 1e-6),lambda k,a:None if k%2 else (a+180)%360))
    scenes['530017']=dict(source_mix='mixed',error_mode='fixed_hash',sources=
        radial_sources(16,lambda k:1500.+(-1e-6 if k%2 else 1e-6),lambda k,a:None if k%2 else (a+180)%360,phase=.000001))
    scenes['530018']=dict(source_mix='mixed',error_mode='plus_one',sources=
        radial_sources(10,lambda k:5.+(-1e-6 if k%2 else 1e-6),lambda k,a:None if k%2 else (a+180)%360))
    scenes['530019']=dict(source_mix='directional',error_mode='minus_one',sources=
        radial_sources(16,lambda k:1800.-1e-6,lambda k,a:a,phase=180/13))
    scenes['530020']=dict(source_mix='directional',error_mode='smooth',sources=
        radial_sources(10,lambda k:1799.99999,lambda k,a:(a+90)%360,phase=360-.000001))
    scenes['530021']=dict(scenario='clustered',source_mix='omni',count=16,reception='maximum',error_mode='plus_one')
    scenes['530022']=dict(scenario='clustered',source_mix='directional',count=16,reception='minimum',error_mode='minus_one')
    (ROOT/'configs/R2_PRESSURE_SCENES.json').write_text(json.dumps(scenes,indent=2),encoding='utf-8')
    text='''# 第二轮压力集预登记

530001–530014复用第一轮的结构类别和两个固定布局，随机生成部分使用新种子。它们属于回归压力测试，不把复用的固定布局称作新的独立随机样本。包含边界向外、发射角边界、聚集、10/16源、1000/1500米半径、固定/平滑/极端误差、近距离、0/360读数与精确目标边界。

530015–530020补充发射角边界两侧1e-7度、接收1000/1500米边界两侧1e-6米、近距5米两侧、13外环站间方向的边界向外源、跨0/360切向源。530021–530022为全向聚集与定向聚集额外压力。混合、全向、定向分别统计，不混入主混合分布成绩。

完整源定义仅交给隔离的本地场景引擎。决策器仍只获取接口反馈；执行后的评估器可读取真值验证漏清。该脚本只登记，并未运行任何场景。
'''
    (ROOT/'reports/R2_PRESSURE_PLAN.md').write_text(text,encoding='utf-8')
    print('Registered 22 evaluator-owned pressure cases; no scenes executed.')


if __name__=='__main__':main()
