"""Publication vector figures from registered, completed local Q4 experiments.

No simulator/policy imports. ReportLab creates both PDF and SVG from the same
Drawing. CSV and registration are independently reconciled with summary and
comparison reports; failed scenes are retained, never filtered for speed.
"""
import argparse
import csv
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from reportlab.graphics.shapes import Drawing, String, Rect, Line, Circle
from reportlab.graphics import renderPDF, renderSVG
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROLES = {'development':'开发集', 'validation':'验证集', 'holdout':'最终保留测试集',
         'final':'最终保留测试集', 'final_holdout':'最终保留测试集',
         'stress':'压力测试', 'smoke':'开发冒烟', 'integration':'开发集成测试'}
DEFAULT_LABELS = {'compact':'D', 'stable':'L', 'single':'M', 'single_stable':'M+L',
                  'S22':'S22', 'scan_commit':'S22+O'}
COMPONENTS = [('mean_move_time','移动','#4c7898'),('mean_RF_detection_time','无线检测','#58a5a2'),
              ('mean_channel_switch_time','切频','#e2aa63'),('mean_optical_time','光学','#a595b5'),
              ('mean_clear_time','成功清除','#86a06b')]
FONT = 'Helvetica'


def fail(message): raise ValueError(message)


def read_json(path): return json.loads(path.read_text(encoding='utf-8-sig'))


def close(actual, expected, label, tolerance=1e-4):
    if not (math.isfinite(actual) and math.isfinite(expected)) or abs(actual-expected)>tolerance:
        fail(f'{label}: CSV={actual}, report={expected}')


def quantile(values, fraction):
    values=sorted(values); index=(len(values)-1)*fraction; low=int(index); high=min(low+1,len(values)-1)
    return values[low]+(values[high]-values[low])*(index-low)


def load_phase(folder, baseline=None, candidate=None, labels=None):
    folder=Path(folder).resolve(); reg=read_json(folder/'registration.json')
    role=reg.get('role')
    if role not in ROLES: fail(f'Unrecognized registered role {role!r}; do not infer role from a filename')
    variants=list(reg['variants']); seeds=list(reg['seeds'])
    if not seeds or len(set(seeds))!=len(seeds): fail('Registration contains no seeds or duplicate seeds')
    tasks=reg.get('tasks',[]); registered={v:[t['seed'] for t in tasks if t['variant']==v] for v in variants}
    for v in variants:
        if len(registered[v])!=len(seeds) or set(registered[v])!=set(seeds): fail(f'{v}: registration is not a complete unique seed set')
    summary=read_json(folder/'summary.json'); summary=summary.get('summary',summary)
    with (folder/'paired_results.csv').open(encoding='utf-8-sig',newline='') as file: rows=list(csv.DictReader(file))
    data={v:{} for v in variants}
    for row in rows:
        variant=row['variant']; seed=int(row['seed'])
        if variant not in data: fail(f'Unregistered CSV variant {variant}')
        if seed not in seeds or seed in data[variant]: fail(f'Unregistered/duplicate CSV seed {variant}/{seed}')
        for key in ('total_time','mean_time_per_source','policy_wall_time_s'):
            row[key]=float(row[key])
            if not math.isfinite(row[key]) or row[key]<0: fail(f'Invalid {key}: {variant}/{seed}')
        if row['all_success'] not in ('True','False','true','false'): fail('Invalid success field')
        row['all_success']=row['all_success'].lower()=='true'; row['seed']=seed
        data[variant][seed]=row
    for v in variants:
        if set(data[v])!=set(seeds): fail(f'{v}: missing registered scenes; no silent success-only plot')
        s=summary[v]; n=len(seeds); selected=[data[v][seed] for seed in seeds]
        if s['n']!=n: fail(f'{v}: summary sample size differs from registration')
        if (s['complete']!=sum(r['all_success'] for r in selected)
            or s['all_success']!=all(r['all_success'] for r in selected)): fail(f'{v}: success count differs from CSV')
        totals=[r['total_time'] for r in selected]
        for key,value in [('mean_total',statistics.mean(totals)),('p95',quantile(totals,.95)),
                          ('worst',max(totals)),('mean_per_source',statistics.mean(r['mean_time_per_source'] for r in selected)),
                          ('mean_wall',statistics.mean(r['policy_wall_time_s'] for r in selected))]: close(value,s[key],v+'/'+key)
        close(sum(s[key] for key,_,_ in COMPONENTS),s['mean_total'],v+'/action accounting',1e-3)
    comparisons=[]; source_files=[folder/n for n in ('registration.json','paired_results.csv','summary.json')]
    for file in sorted(folder.glob('comparison*.json')):
        comp=read_json(file); a=comp.get('baseline'); b=comp.get('candidate')
        if a not in variants or b not in variants: continue
        if baseline is not None and (a!=baseline or b!=candidate): continue
        n=len(seeds)
        if (comp.get('pairs')!=n or comp.get('all_registered_pairs_present') is not True
            or type(comp.get('identical_worlds_verified')) is not int or comp['identical_worlds_verified']!=n):
            fail(f'{file.name}: missing complete same-world pairing verification')
        for name,key in [(a,'mean_per_source_baseline'),(b,'mean_per_source_candidate')]: close(summary[name]['mean_per_source'],comp[key],file.name+'/'+key)
        close(comp['p95_baseline'],summary[a]['p95'],file.name+'/p95 baseline')
        close(comp['p95_candidate'],summary[b]['p95'],file.name+'/p95 candidate')
        close(100*(1-summary[b]['mean_per_source']/summary[a]['mean_per_source']),comp['improvement_percent'],file.name+'/improvement')
        if comp['all_success']!=all(data[v][seed]['all_success'] for v in (a,b) for seed in seeds):
            fail(f'{file.name}: complete-clear status differs from CSV')
        differences=[data[b][seed]['total_time']-data[a][seed]['total_time'] for seed in seeds]
        comp=dict(comp,differences=differences,file=file.name)
        comparisons.append(comp); source_files.append(file)
    if not comparisons: fail('No matching audited comparison reports; refusing to label unrelated runs as paired')
    if baseline is not None:
        if baseline==candidate: fail('Baseline and candidate must differ')
        variants=[baseline,candidate]
    display=dict(DEFAULT_LABELS); display.update(labels or {})
    return dict(folder=folder,registration=reg,role=role,seeds=seeds,variants=variants,summary=summary,
                data=data,comparisons=comparisons,files=source_files,labels={v:display.get(v,v) for v in variants})


def text(d,x,y,value,size=10,anchor='start',color='#233e4b'):
    d.add(String(x,y,str(value),fontName=FONT,fontSize=size,textAnchor=anchor,fillColor=HexColor(color)))


def rect(d,x,y,w,h,color): d.add(Rect(x,y,w,h,fillColor=HexColor(color),strokeColor=None))


def line(d,x1,y1,x2,y2,color='#8498a5',width=.7):
    d.add(Line(x1,y1,x2,y2,strokeColor=HexColor(color),strokeWidth=width))


def footer(d,p,note=''):
    text(d,38,18,f'{ROLES[p["role"]]}  ·  注册 n={len(p["seeds"])}  ·  自建本地场景假设，非官方分布',8,color='#617580')
    if note:text(d,d.width-24,18,note,8,'end',color='#617580')


def export(d,out,name):
    renderPDF.drawToFile(d,str(out/(name+'.pdf')))
    renderSVG.drawToFile(d,str(out/(name+'.svg')))
    try:
        import pypdfium2
        document=pypdfium2.PdfDocument(str(out/(name+'.pdf')))
        document[0].render(scale=1.6).to_pil().save(out/(name+'.png'));document.close()
    except ImportError: pass


def stacked(p,out):
    d=Drawing(650,400); left=70; bottom=72; width=535; height=255
    names=p['variants']; values=[p['summary'][v]['mean_total'] for v in names]
    step=1000 if max(values)>2500 else 500; top=math.ceil(max(values)*1.08/step)*step
    for y in range(0,int(top)+1,step):
        yy=bottom+height*y/top;line(d,left,yy,left+width,yy,'#e1e8ec',.5);text(d,left-10,yy-3,y,9,'end')
    text(d,left,345,'平均整场虚拟时间 / s',10)
    bar=min(90,width/len(names)*.58)
    for i,v in enumerate(names):
        x=left+width*(i+.5)/len(names); current=0
        for field,label,color in COMPONENTS:
            value=p['summary'][v][field];rect(d,x-bar/2,bottom+current/top*height,bar,value/top*height,color);current+=value
        text(d,x,bottom+current/top*height+9,f'{current:.1f}',10,'middle')
        text(d,x,bottom-22,p['labels'][v],10,'middle')
    for i,(_,label,color) in enumerate(COMPONENTS):
        x=75+i*108;rect(d,x,370,9,8,color);text(d,x+14,369,label,9)
    footer(d,p);export(d,out,'time_components')


def paired(p,out,comp):
    a,b=comp['baseline'],comp['candidate']; differences=comp['differences']; n=len(differences)
    d=Drawing(760,400); left=70; bottom=72; width=650; height=250
    maximum=max(abs(x) for x in differences) or 1.; step=10**math.floor(math.log10(maximum))/2
    if maximum/step>8:step*=2
    low=math.floor(min(0.,min(differences))*1.12/step)*step
    high=math.ceil(max(0.,max(differences))*1.12/step)*step
    if high==low: low,high=-step,step
    Y=lambda y:bottom+height*(y-low)/(high-low)
    for k in range(int(round(low/step)),int(round(high/step))+1):
        y=k*step;line(d,left,Y(y),left+width,Y(y),'#e1e8ec',.5);text(d,left-9,Y(y)-3,f'{y:g}',9,'end')
    line(d,left,Y(0),left+width,Y(0),'#566c77',1.)
    for i,(seed,value) in enumerate(zip(p['seeds'],differences)):
        x=left+width*(i+.5)/n;color='#cc7950' if value>0 else '#398697'
        line(d,x,Y(0),x,Y(value),color,1.1);d.add(Circle(x,Y(value),2.5,fillColor=HexColor(color),strokeColor=None))
        if not (p['data'][a][seed]['all_success'] and p['data'][b][seed]['all_success']):
            line(d,x-4,Y(value)-4,x+4,Y(value)+4,'#9f2442',1.4);line(d,x-4,Y(value)+4,x+4,Y(value)-4,'#9f2442',1.4)
    stride=max(1,math.ceil(n/10))
    for i in range(n):
        if i==0 or i==n-1 or (i+1)%stride==0:text(d,left+width*(i+.5)/n,bottom-18,i+1,9,'middle')
    faster=sum(v<-1e-6 for v in differences);slower=sum(v>1e-6 for v in differences);mean=statistics.mean(differences)
    text(d,left,353,f'{p["labels"].get(b,b)} 减 {p["labels"].get(a,a)}：整场总时间差 / s',11)
    text(d,left,374,f'更快 {faster} 场  ·  更慢 {slower} 场  ·  持平 {n-faster-slower} 场  ·  平均差 {mean:+.2f} s',10)
    text(d,left+width/2,38,'注册场景序号（与源数据中的种子逐行对应）',10,'middle')
    footer(d,p,'负值更快；退步与失败局均保留')
    export(d,out,f'paired_difference_{a}_{b}')


def metric_table(p,out):
    names=p['variants']; d=Drawing(825,118+35*len(names)); top=d.height-30
    widths=[115,80,120,120,120,120,105]; xs=[25]
    for w in widths:xs.append(xs[-1]+w)
    headers=['策略','完整清除','平均每源 / s','平均整场 / s','整场 P95 / s','最坏整场 / s','平均现实 / s']
    rect(d,25,top-25,sum(widths),30,'#e7eff2')
    for i,label in enumerate(headers):text(d,(xs[i]+xs[i+1])/2,top-14,label,9,'middle')
    for j,v in enumerate(names):
        y=top-55-j*35;s=p['summary'][v]
        values=[p['labels'][v],f'{s["complete"]}/{len(p["seeds"])}']+[f'{s[k]:.2f}' for k in ('mean_per_source','mean_total','p95','worst','mean_wall')]
        for i,value in enumerate(values):text(d,(xs[i]+xs[i+1])/2,y,value,10,'middle')
        line(d,25,y-11,xs[-1],y-11,'#dbe5e9',.5)
    footer(d,p);export(d,out,'metrics_table')


def save_data(p,out):
    columns=['variant','label','registered_n','complete','mean_per_source','mean_total','p95','worst','mean_wall']+[x[0] for x in COMPONENTS]
    with (out/'table_data.csv').open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.DictWriter(file,columns);writer.writeheader()
        for v in p['variants']:writer.writerow(dict(variant=v,label=p['labels'][v],registered_n=len(p['seeds']),**{k:p['summary'][v][k] for k in columns[3:]}))
    with (out/'paired_differences.csv').open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.writer(file);writer.writerow(['comparison','index','seed','baseline','candidate','baseline_total_s','candidate_total_s','difference_s','both_complete'])
        for c in p['comparisons']:
            a,b=c['baseline'],c['candidate']
            for i,(seed,difference) in enumerate(zip(p['seeds'],c['differences']),1):
                aa=p['data'][a][seed];bb=p['data'][b][seed]
                writer.writerow([a+'__'+b,i,seed,a,b,aa['total_time'],bb['total_time'],difference,aa['all_success'] and bb['all_success']])
    outputs=[x.name for x in sorted(out.iterdir()) if x.suffix in ('.pdf','.svg','.png','.csv')]
    manifest=dict(phase=p['registration']['phase'],registered_role=p['role'],registered_n=len(p['seeds']),
                  seeds=p['seeds'],variants=p['variants'],data_kind='local_scenario_assumptions_not_official_distribution',
                  source_sha256={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in p['files']},
                  generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  generated_utc=datetime.now(timezone.utc).isoformat(),outputs=outputs,
                  pair_count={c['baseline']+'__'+c['candidate']:c['pairs'] for c in p['comparisons']},
                  same_world_verification_reported={c['baseline']+'__'+c['candidate']:c['identical_worlds_verified'] for c in p['comparisons']},
                  all_registered_rows_retained=True,summary_recomputed_from_csv=True,p95_method='linear interpolation, index (n-1)*0.95')
    (out/'SOURCES.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    captions=['# 图表引用与口径', '', f'数据阶段：{ROLES[p["role"]]}，每策略注册 n={len(p["seeds"])}。',
              '本地分布为实验假设；本图不代表官方演练、正式成绩或官方场景分布。', '',
              '- `time_components.pdf/.svg`：完整场景的平均虚拟总时间，按移动、无线检测、切频、光学和成功清除分解；五项之和已与总时间核对。',
              '- `metrics_table.pdf/.svg`：每场平均每源时间再作算术平均；P95 对完整场景总时间计算，采用线性插值。现实耗时为策略计时，不是整批开发预算。',
              '- `paired_difference_*.pdf/.svg`：候选减基线的逐场总时间差；负值更快。场景序号对应注册种子顺序，退步局和失败局均保留；叉号表示至少一臂未完整清除。',
              '- `paired_differences.csv`、`table_data.csv`：全部图表的数值来源。',
              '- `SOURCES.json`：注册口径、输入 SHA256、生成器 SHA256、配对与相同世界核验数量。',
              '', 'PDF 为嵌入中文字体的矢量文件；SVG 保留文字，编辑时需安装 SimHei 字体。PNG 仅用于渲染检查。',
              '图中不放大标题；以上文字可用于论文图注。不能把不同注册种子集的两项均值称为配对结果。']
    (out/'CAPTIONS.md').write_text('\n'.join(captions)+'\n',encoding='utf-8')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase-dir',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--baseline');parser.add_argument('--candidate');parser.add_argument('--labels',type=Path)
    parser.add_argument('--font',type=Path,default=Path('C:/Windows/Fonts/simhei.ttf'))
    args=parser.parse_args()
    if bool(args.baseline)!=bool(args.candidate):parser.error('Set both --baseline and --candidate, or neither')
    if not args.font.is_file():parser.error('A Chinese TTF font is required; set --font')
    global FONT
    FONT='SimHei';pdfmetrics.registerFont(TTFont(FONT,str(args.font)))
    p=load_phase(args.phase_dir,args.baseline,args.candidate,read_json(args.labels) if args.labels else None)
    args.out.mkdir(parents=True,exist_ok=True)
    if any(args.out.iterdir()):parser.error('Output directory must be empty to prevent mixed-phase artifacts')
    stacked(p,args.out);metric_table(p,args.out)
    for comparison in p['comparisons']:paired(p,args.out,comparison)
    manifest=save_data(p,args.out)
    print(json.dumps(dict(output=str(args.out.resolve()),registered_role=p['role'],n=len(p['seeds']),
                         variants=p['variants'],pair_count=manifest['pair_count']),ensure_ascii=False))


if __name__=='__main__':main()
