"""Apply the predeclared adoption decision to local UI and documentation."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'local_simulator';DEST=ROOT/'reports'/'optimization'


def main():
    summary=json.loads((DEST/'F_SUMMARY.json').read_text());default=summary['recommended_default']
    path=ROOT/'web'/'index.html';html=path.read_text(encoding='utf-8')
    old='<option value="E" selected>E · 安全测站与补测重规划（推荐）</option>'
    new=('<option value="E">E · 安全测站与补测重规划</option><option value="F" selected>F · 计费搜索替代与顺路清除（推荐）</option>' if default=='F'
         else old+'<option value="F">F · 结构改进候选</option>')
    if '<option value="F"' not in html:
        assert old in html;html=html.replace(old,new,1)
    if "id='perSource'" not in html:
        marker="for(let ch=1;ch<=20;ch++)"
        inject="const metricNote=document.createElement('div');metricNote.id='perSource';metricNote.className='hint';metricNote.textContent='每源均值：结束后显示';$('total').parentElement.appendChild(metricNote);\n"
        assert marker in html;html=html.replace(marker,inject+marker,1)
        marker="$ ('cleared')".replace(' ','')+'.textContent=s.count;'
        assert marker in html
        html=html.replace(marker,"$('perSource').textContent=s.ended&&s.count?'平均定位清除：'+fmt(totalTime()/s.count)+' 秒/源':'每源均值：结束后显示';"+marker,1)
        html=html.replace('ctx.beginPath();r.polygon.forEach','for(const piece of (r.pieces||[r.polygon])){ctx.beginPath();piece.forEach',1)
        html=html.replace("ctx.lineWidth=1;ctx.stroke();marker(r.center","ctx.lineWidth=1;ctx.stroke();}marker(r.center",1)
    path.write_text(html,encoding='utf-8')
    server=ROOT/'code'/'server.py';text=server.read_text(encoding='utf-8')
    text=text.replace('("A", "B", "C", "D", "E")','("A", "B", "C", "D", "E", "F")')
    server.write_text(text,encoding='utf-8')
    runner=ROOT/'code'/'runner.py';text=runner.read_text(encoding='utf-8')
    if default=='F':
        text=text.replace('def run_case(seed=1, strategy="E"','def run_case(seed=1, strategy="F"',1)
        text=text.replace('choices=["A", "B", "C", "D", "E", "F"], default="E"','choices=["A", "B", "C", "D", "E", "F"], default="F"',1)
    runner.write_text(text,encoding='utf-8')
    readme=ROOT/'README.md';text=readme.read_text(encoding='utf-8')
    note=f'''## 2026-09-12：结构改进与指标更正

当前推荐 **{default}**。本轮 {summary['additional_local_runs']} 次本地运行，100 个新场景的配对验证：
E 整局 {summary['mean_E_total_s']:.2f} 秒、{summary['mean_E_s_per_source']:.2f} 秒/源；
F 整局 {summary['mean_F_total_s']:.2f} 秒、{summary['mean_F_s_per_source']:.2f} 秒/源。
平均整局改善 {summary['improvement_percent']:.2f}%，35 项规则和几何检查通过。
详细结果以 `reports/optimization/F_RESULTS.md` 为准；冻结参数在 `code/f_policy_presets.py`，
代码在 `code/structural.py` 与 `code/structural_geometry.py`。命令行 `--strategy F` 可运行候选；E 保留不变。

题面指标为逐场 `总时间/清除数`。原 E 的上一批 100 场实际为 **229.62 秒/源**，
已经处于 200–300 秒/源范围。此前“整局 200–300 秒不可达”的下界论证不能用于否定这个题面指标。
界面结束后同时显示整局时间和秒/源。`F_replay.html` 可直接打开，不需要 Python。

下方 E 说明和历史结果保留供追溯，默认策略与当前结论以本节和 F_RESULTS.md 为准。

'''
    if '## 2026-09-12：结构改进与指标更正' not in text:
        text=text.replace('## 打开可视化界面',note+'## 打开可视化界面',1)
    readme.write_text(text,encoding='utf-8')
    print('Recommended default:',default)


if __name__=='__main__':main()
