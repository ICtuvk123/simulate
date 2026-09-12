"""Vector experiment figures from completed paired runs, with source manifests."""
import argparse,csv,hashlib,json,math,statistics
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.colors import HexColor,Color
ROOT=Path(__file__).resolve().parents[1]
COLORS=['#4e6b83','#64a7ad','#dc8957','#9daac1','#7ba46c']


def setup_font():
    p=Path('C:/Windows/Fonts/simhei.ttf')
    if p.is_file():pdfmetrics.registerFont(TTFont('Q4Chinese',str(p)));return 'Q4Chinese'
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'));return 'STSong-Light'


FONT=None


def text(c,x,y,s,size=10,align='left',color='#283e4e'):
    c.setFont(FONT,size);c.setFillColor(HexColor(color))
    getattr(c,{'left':'drawString','right':'drawRightString','center':'drawCentredString'}[align])(x,y,str(s))


def axes(c,xlabel,ylabel,xmin,xmax,ymin,ymax,xticks,yticks):
    left,bottom,width,height=68,62,462,266
    X=lambda x:left+(x-xmin)/(xmax-xmin)*width
    Y=lambda y:bottom+(y-ymin)/(ymax-ymin)*height
    for y in yticks:
        c.setStrokeColor(HexColor('#e4ebef'));c.setLineWidth(.6);c.line(left,Y(y),left+width,Y(y))
        text(c,left-9,Y(y)-3,f'{y:g}',9,'right')
    for x in xticks:text(c,X(x),bottom-17,f'{x:g}',9,'center')
    c.setStrokeColor(HexColor('#526c7d'));c.setLineWidth(.8);c.line(left,bottom,left+width,bottom);c.line(left,bottom,left,bottom+height)
    text(c,left+width/2,22,xlabel,11,'center')
    c.saveState();c.translate(17,bottom+height/2);c.rotate(90);text(c,0,0,ylabel,11,'center');c.restoreState()
    return X,Y


def save_manifest(path,phase,rows,outputs):
    sources=ROOT/'reports'/phase/'runs.jsonl'
    manifest=dict(phase=phase,data_file=str(sources.relative_to(ROOT)),sha256=hashlib.sha256(sources.read_bytes()).hexdigest(),
                  outputs=[p.name for p in outputs],row_count=len(rows),all_registered_runs_included=True,
                  results_kind='local_simulator_only')
    (path/'SOURCES.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')


def make(phase,baseline,candidate,tag):
    global FONT
    FONT=setup_font();folder=ROOT/'reports'/phase
    rows=[json.loads(s) for s in (folder/'runs.jsonl').read_text().splitlines()]
    selected=[r for r in rows if r['task']['variant'] in (baseline,candidate)]
    if not selected or any('metrics' not in r for r in selected):raise ValueError('Missing run metrics; do not silently omit failed runs')
    data={name:sorted([r for r in selected if r['task']['variant']==name],key=lambda r:r['task']['seed']) for name in (baseline,candidate)}
    if [r['task']['seed'] for r in data[baseline]]!=[r['task']['seed'] for r in data[candidate]]:raise ValueError('Incomplete pairs')
    out=ROOT/'figures'/tag;out.mkdir(parents=True,exist_ok=True);outputs=[]
    summary=json.loads((folder/'summary.json').read_text())
    # Physical action-time partition: each second appears exactly once.
    p=out/'time_components.pdf';c=canvas.Canvas(str(p),pagesize=(560,380));outputs.append(p)
    fields=['move_time','RF_detection_time','channel_switch_time','optical_time','clear_time']
    labels=['移动','无线检测','切频','光学','清除']
    max_t=max(summary[n]['mean_total'] for n in data);top=math.ceil(max_t/1000)*1000
    X,Y=axes(c,'策略','平均整场虚拟时间 / s',-.6,1.6,0,top,[],range(0,top+1,1000))
    for i,name in enumerate(data):
        current=0
        for field,color in zip(fields,COLORS):
            value=summary[name]['mean_'+field];c.setFillColor(HexColor(color));c.rect(X(i)-50,Y(current),100,Y(current+value)-Y(current),fill=1,stroke=0);current+=value
        text(c,X(i),45,name,11,'center');text(c,X(i),Y(current)+8,f'{current:.1f}',10,'center')
    for i,(label,color) in enumerate(zip(labels,COLORS)):
        x=64+i*98;c.setFillColor(HexColor(color));c.rect(x,356,10,8,fill=1,stroke=0);text(c,x+15,355,label,9)
    c.save()
    # Paired whole-scene totals, including every registered run in this phase.
    p=out/'paired_total_times.pdf';c=canvas.Canvas(str(p),pagesize=(560,380));outputs.append(p)
    a=[r['metrics']['total_time'] for r in data[baseline]];b=[r['metrics']['total_time'] for r in data[candidate]]
    lo=math.floor(min(a+b)/1000)*1000;hi=math.ceil(max(a+b)/1000)*1000
    X,Y=axes(c,baseline+' 整场虚拟时间 / s',candidate+' 整场虚拟时间 / s',lo,hi,lo,hi,range(lo,hi+1,1000),range(lo,hi+1,1000))
    c.setDash(4,3);c.setStrokeColor(HexColor('#8ea2b1'));c.line(X(lo),Y(lo),X(hi),Y(hi));c.setDash()
    for x,y in zip(a,b):c.setFillColor(Color(.10,.46,.60,.68));c.circle(X(x),Y(y),2.8,fill=1,stroke=0)
    text(c,70,355,f'配对场景 n={len(a)}；虚線为相同总时间',10);c.save()
    # Empirical distribution of per-source time (different from P95 total).
    p=out/'per_source_distribution.pdf';c=canvas.Canvas(str(p),pagesize=(560,380));outputs.append(p)
    series={name:sorted(r['metrics']['mean_time_per_source'] for r in rr) for name,rr in data.items()}
    lo=math.floor(min(min(v) for v in series.values())/100)*100;hi=math.ceil(max(max(v) for v in series.values())/100)*100
    X,Y=axes(c,'逐场平均每源虚拟时间 / s','经验累积分布',lo,hi,0,1,range(lo,hi+1,100),[0,.2,.4,.6,.8,1])
    for i,(name,values) in enumerate(series.items()):
        c.setStrokeColor(HexColor(COLORS[i]));c.setLineWidth(1.8);path=c.beginPath();path.moveTo(X(lo),Y(0))
        for j,v in enumerate(values):path.lineTo(X(v),Y(j/len(values)));path.lineTo(X(v),Y((j+1)/len(values)))
        path.lineTo(X(hi),Y(1));c.drawPath(path);c.line(72+i*190,359,95+i*190,359);text(c,102+i*190,355,name,10)
    c.save()
    # Source-count stratification makes the 10/16 source effect visible.
    p=out/'source_count_strata.pdf';c=canvas.Canvas(str(p),pagesize=(560,380));outputs.append(p)
    groups={name:{n:[r['metrics']['mean_time_per_source'] for r in rr if r['metrics']['engine_source_count']==n] for n in range(10,17)} for name,rr in data.items()}
    top=math.ceil(max(statistics.mean(v) for g in groups.values() for v in g.values() if v)/100)*100
    X,Y=axes(c,'事后统计的实际源数','逐场平均每源时间的组均值 / s',9.5,16.5,0,top,range(10,17),range(0,top+1,100))
    strata=[]
    for i,(name,g) in enumerate(groups.items()):
        c.setStrokeColor(HexColor(COLORS[i]));c.setLineWidth(1.8);path=c.beginPath();first=True
        for n,values in g.items():
            if not values:continue
            mean=statistics.mean(values)
            if first:path.moveTo(X(n),Y(mean));first=False
            else:path.lineTo(X(n),Y(mean))
            c.setFillColor(HexColor(COLORS[i]));c.circle(X(n),Y(mean),3,fill=1,stroke=0)
            strata.append(dict(variant=name,source_count=n,n=len(values),mean_per_source=mean))
        c.drawPath(path);text(c,72+i*190,355,name,10,color=COLORS[i])
    c.save()
    with (out/'source_count_strata.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['variant','source_count','n','mean_per_source']);w.writeheader();w.writerows(strata)
    save_manifest(out,phase,selected,outputs)
    return [str(p) for p in outputs]


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase');p.add_argument('baseline');p.add_argument('candidate');p.add_argument('--tag',default='validation')
    a=p.parse_args();print(json.dumps(make(a.phase,a.baseline,a.candidate,a.tag),ensure_ascii=False))
