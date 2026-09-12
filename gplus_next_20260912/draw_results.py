"""Vector paired scientific charts using the already bundled ReportLab."""
import math
from pathlib import Path


def draw(pairs,root):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.colors import HexColor
    pdfmetrics.registerFont(TTFont('Chinese','C:/Windows/Fonts/simhei.ttf'))
    pdf=canvas.Canvas(str(root/'figures/Gplus_next_validation.pdf'),pagesize=(960,430))
    pdf.setTitle('冻结 G+ 与新候选的100场独立配对验证')
    low=20*math.floor(min(min(p['baseline'],p['candidate']) for p in pairs)/20)-20
    high=20*math.ceil(max(max(p['baseline'],p['candidate']) for p in pairs)/20)+20
    x0,y0,w,h=65,70,345,300
    def x(v):return x0+w*(v-low)/(high-low)
    def y(v):return y0+h*(v-low)/(high-low)
    for value in range(low,high+1,40):
        pdf.setStrokeColor(HexColor('#d8dee8'));pdf.line(x(value),y0,x(value),y0+h);pdf.line(x0,y(value),x0+w,y(value))
        pdf.setFillColor(HexColor('#475569'));pdf.setFont('Chinese',10)
        pdf.drawCentredString(x(value),y0-16,str(value));pdf.drawRightString(x0-8,y(value)-3,str(value))
    pdf.setStrokeColor(HexColor('#94a3b8'));pdf.setDash(3,3);pdf.line(x(low),y(low),x(high),y(high));pdf.setDash()
    for row in pairs:
        pdf.setFillColor(HexColor('#15806a' if row['saved']>=0 else '#cb6c26'))
        pdf.circle(x(row['baseline']),y(row['candidate']),2.4,stroke=0,fill=1)
    pdf.setFillColor(HexColor('#172b45'));pdf.setFont('Chinese',12)
    pdf.drawCentredString(x0+w/2,25,'冻结 G+ 平均时间（秒/源）')
    pdf.saveState();pdf.translate(18,y0+h/2);pdf.rotate(90);pdf.drawCentredString(0,0,'新候选平均时间（秒/源）');pdf.restoreState()
    x0,w=540,350
    ordered=sorted(p['saved'] for p in pairs)
    spread=max(ordered)-min(ordered)
    step=1 if spread<8 else 2 if spread<16 else 5 if spread<40 else 10
    bottom=step*math.floor(min(0,min(ordered))/step)-step
    top=step*math.ceil(max(0,max(ordered))/step)+step
    def yd(value):return y0+h*(value-bottom)/(top-bottom)
    for value in range(bottom,top+1,step):
        pdf.setStrokeColor(HexColor('#d8dee8'));pdf.setFillColor(HexColor('#475569'));pdf.setFont('Chinese',10)
        pdf.line(x0,yd(value),x0+w,yd(value));pdf.drawRightString(x0-8,yd(value)-3,str(value))
    pdf.setStrokeColor(HexColor('#475569'));pdf.line(x0,yd(0),x0+w,yd(0))
    for i,value in enumerate(ordered):
        pdf.setFillColor(HexColor('#15806a' if value>=0 else '#cb6c26'))
        pdf.rect(x0+i*w/len(ordered),yd(min(value,0)),w/len(ordered)-.5,abs(yd(value)-yd(0)),fill=1,stroke=0)
    pdf.setFillColor(HexColor('#172b45'));pdf.setFont('Chinese',12)
    pdf.drawCentredString(x0+w/2,25,'按节省时间排序的100个配对场景')
    pdf.saveState();pdf.translate(485,y0+h/2);pdf.rotate(90);pdf.drawCentredString(0,0,'冻结 G+ 减新候选（秒/源）');pdf.restoreState()
    pdf.setFont('Chinese',11);pdf.drawString(65,400,'每点对应同一场景；虚线为等时线')
    pdf.drawString(540,400,'绿色：新候选更快；橙色：新候选更慢')
    pdf.save()
