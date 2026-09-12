"""Post-run route gallery from accepted feedback only; no scene truth is loaded."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / 'reports/R2_SCAN_COMMIT10'
OUT = ROOT / 'examples/R2_O'


def replay(metrics, destination):
    records = [json.loads(s) for s in Path(metrics['raw_log_path']).read_text(encoding='utf-8').splitlines()]
    frames = []; seen = set(); role = ''; regions = {}; last = (0., 0.)
    distance = 0.; rf = optical = switch = success = 0; channel = 1
    for row in records:
        if row.get('reason') == 'q4_action_role': role = row['role']
        if row.get('reason') in ('q4_positive_region', 'q4_paired_negative_clip'):
            ch = row.get('channel', row.get('witness', {}).get('channel'))
            regions[ch] = row['polygon']
            if frames: frames[-1]['regions'] = dict(regions)
        if row.get('event') != 'response' or row['http_status'] != 200: continue
        response = json.loads(row['response_body']); payload = row['payload']; rid = payload['request_id']
        if not response.get('accepted') or rid in seen: continue
        seen.add(rid); path = row['path']; ch = payload.get('channel')
        point = payload.get('position', dict(x=last[0], y=last[1])); point = point['x'], point['y']
        distance += sum((point[i] - last[i]) ** 2 for i in (0, 1)) ** .5
        if path == '/measure': rf += 1; switch += int(ch != channel); channel = ch
        if path == '/clear':
            optical += 1
            if response['clear_result'] == 'success': success += 1; regions.pop(ch, None)
        frames.append(dict(path=path, point=point, ch=ch,
                           result=response.get('measure_result', response.get('clear_result', response.get('exit_reason', 'entered'))),
                           bearing=response.get('svd_deg'), time=response['virtual_time_s'],
                           role=role if path in ('/measure', '/clear') else '', regions=dict(regions),
                           distance=distance, rf=rf, switch=switch, optical=optical, success=success))
        last = point
    data = dict(frames=frames, sources=[], summary={k: metrics[k] for k in
                ['version', 'all_success', 'total_time', 'mean_time_per_source', 'policy_wall_time_s', 'fallback_count']})
    template = (ROOT / 'code/replay_template.html').read_text(encoding='utf-8')
    template = template.replace('type="checkbox"> 显示事后真值（仅用于回放）', 'type="checkbox" disabled> 此回放不包含真值')
    template = template.replace('真值只在策略结束后交给评估器。勾选真值不会改变动作序列；该图不代表决策器能看到真实位置或发射朝向。', '此页面只包含实际历史动作、反馈与保守位置区域，没有真实源坐标或发射朝向。')
    destination.write_text(template.replace('__Q4_DATA__', json.dumps(data, ensure_ascii=False).replace('</', '<\\/')), encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(x) for x in (PHASE / 'runs.jsonl').read_text(encoding='utf-8').splitlines()]
    selected = {(r['task']['seed'], r['task']['variant']): r['metrics'] for r in rows if r['task']['seed'] in (1415, 1420)}
    sections = []
    for seed, title, explanation in [
        (1415, '最大收益', '两次提前扫描均收到真实示向度。第二次把源位置区域半径从 750.59 m 缩到 14.30 m，直接获得保证清除位置。全局移动减少 431.84 秒；无线检测反而多 6 次，光学失败多 5 次。'),
        (1420, '最大退步', '前两次提前扫描都收到示向度并达到 20 m 保证定位范围。第三次预测净收益只有 2.77 秒，计划路线增量为 95.14 秒，实际收到无信号，位置区域保持原样。全局移动增加 198.91 秒、无线检测多 4 次。')]:
        base = selected[seed, 'S22']; cand = selected[seed, 'scan_commit']
        for variant, m in [('S22', base), ('O', cand)]: replay(m, OUT / f'{seed}_{variant}.html')
        table = ''.join(f'<tr><td>{label}</td><td>{base[key]:.2f}</td><td>{cand[key]:.2f}</td><td>{cand[key]-base[key]:+.2f}</td></tr>'
                        for key, label in [('move_time','移动'), ('RF_detection_time','射频检测'), ('channel_switch_time','切频'), ('optical_time','光学'), ('clear_time','成功清除')])
        sections.append(f'<section><h2>{title} · 开发场景 {seed}</h2><a href="{seed}_S22.html">S22：{base["total_time"]:.2f} 秒</a><a href="{seed}_O.html">O：{cand["total_time"]:.2f} 秒</a><table><tr><th>分项 / 秒</th><th>S22</th><th>O</th><th>O−S22</th></tr>{table}</table><p>{explanation}</p></section>')
    html = '''<!doctype html><html lang="zh"><meta charset="utf-8"><title>Q4 O：搜索与清除调度</title><style>body{font-family:Microsoft YaHei,Arial,sans-serif;max-width:1040px;margin:36px auto;padding:0 20px;background:#eff4f6;color:#173e48}p{line-height:1.8}section{background:white;border-radius:16px;padding:20px;margin:20px 0}a{display:inline-block;background:#e5f2f3;padding:14px;border-radius:8px;color:#145a69;margin:6px}td,th{padding:7px 14px;text-align:right}td:first-child,th:first-child{text-align:left}table{border-collapse:collapse}tr{border-bottom:1px solid #d5e2e6}</style><h1>Q4：先取得沿途信息，再承诺清除路线</h1><p>已结束的自建本地模拟，页面仅包含实际反馈，没有真值数据。选择首批十场中最大收益和最大退步两对；全部十场都计入均值和尾部指标。O 首批平均每源改善 1.897%，尚需更大规模验证，不能据此称为最终最佳方案。</p>'''
    (OUT / 'index.html').write_text(html + ''.join(sections) + '<p>局部定位信息变好不保证完整任务更快。模型预测只排序动作，不更新位置区域或退出证书；所有动作依据实际反馈重新规划。此结果属于开发实验，不是官方演练或正式成绩。</p></html>', encoding='utf-8')
    print(OUT / 'index.html')


if __name__ == '__main__': main()
