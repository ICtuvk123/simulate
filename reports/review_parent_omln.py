"""Read-only integration audit against parent modules; writes only own report."""
import ast
import copy
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parents[1] / 'jammer_search_q4_r2'
sys.path.insert(0, str(PARENT / 'code'))
from q4controller import Q4Controller
from q4engine import Session, Source
from q3client import Client, canonical
from candidate_geometry import canonical_candidate_polygon
from adaptive_single import candidate_points


class Journal:
    def __init__(self): self.rows = []
    def append(self, row): self.rows.append(row)


def audit():
    files = ['q4controller.py', 'lookahead.py', 'adaptive_single.py', 'candidate_geometry.py',
             'region_quadrature.py', 'scan_commit_scheduler.py', 'q3client.py']
    trees = {name: ast.parse((PARENT / 'code' / name).read_text(encoding='utf-8')) for name in files}
    calls = [n for n in ast.walk(trees['q4controller.py']) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == 'shared_information_value']
    assert len(calls) >= 2
    kwargs = [{k.arg: ast.dump(k.value) for k in call.keywords} for call in calls]
    assert all(item == kwargs[0] for item in kwargs)
    assert set(kwargs[0]) == {'exclusions', 'joint', 'spatial_errors', 'balanced_errors', 'stable'}
    model_calls = []
    for file in ('q4controller.py', 'lookahead.py', 'adaptive_single.py'):
        for node in ast.walk(trees[file]):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'hypotheses':
                flags = {k.arg for k in node.keywords}
                assert {'joint', 'spatial_errors', 'balanced_errors', 'stable'} <= flags
                model_calls.append({'file':file, 'line':node.lineno, 'flags':sorted(flags)})
    results = []
    for heading, point, expected in [(None, (500.,0.), 'near'), (180., (800.,0.), 'no_signal')]:
        session = Session(sources=[Source(1, 500., 0., 1500., direction_deg=heading)])
        session._error = lambda ch,p: 0.
        def transport(path, body, timeout):
            status, response = session.handle(path, body)
            return status, canonical(response)
        journal = Journal(); client = Client('local-robot', journal, transport=transport)
        options = json.loads((PARENT/'configs/R2_S_outer13.json').read_text())
        options.update(scan_before_commit=True, stable_quadrature=True, adaptive_single=True,
                       canonical_single_candidates=True)
        c = Q4Controller(client, options); client.action('/enter'); c.measure((0.,0.), 1, 'unit')
        before = copy.deepcopy(c.polygons[1]); before_events = len(client.ledger.events)
        c.unknown = lambda: [20]
        c.refresh = lambda: None
        score = dict(estimated_gain_s=100., model_count=1, branches={expected:1.})
        with patch('q4controller.shared_information_value', return_value=score): c.scan(point)
        events = client.ledger.events[before_events:]
        assert c.since_search == 0 and (20,point) in c.measured and (1,point) in c.measured
        if expected == 'near':
            assert 1 in c.cleared and client.ledger.channel == 1 and client.ledger.position == point
            assert len(events) == 3 and client.ledger.optical_count == 1
            count = len(client.ledger.events)
            with patch('q4controller.shared_information_value', side_effect=AssertionError('cleared ranked again')):
                c.share_at_actual_station(point)
            assert len(client.ledger.events) == count
        else:
            assert 1 not in c.cleared and c.polygons[1] == before and c.negatives[1] == [point]
            assert len(events) == 2 and client.ledger.optical_count == 0
        results.append(dict(actual_shared_result=expected, new_accepted_actions=len(events),
                            cleared=sorted(c.cleared), same_channel_after_clear=True))
    poly = [(0.,-10.), (1000.,-10.), (1000.,10.), (0.,10.)]
    variant = [tuple((1-t)*a[k]+t*b[k] for k in (0,1))
               for a,b in zip(poly,poly[1:]+poly[:1]) for t in (0.,.2,.5,.8)]
    before = copy.deepcopy(variant)
    assert canonical_candidate_polygon(variant) == poly
    expected_points = candidate_points(canonical_candidate_polygon(poly), (-100.,100.), [], [])
    for p in (variant[::-1], poly[1:]+poly[:1]):
        assert candidate_points(canonical_candidate_polygon(p), (-100.,100.), [], []) == expected_points
    assert variant == before
    # Ensure N's simplified copy reaches candidate construction only: all
    # likelihood/branch/reception/guarantee calls keep the original poly.
    fn = next(n for n in trees['adaptive_single.py'].body if isinstance(n, ast.FunctionDef) and n.name=='choose_adaptive_single')
    for call in ast.walk(fn):
        if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id in ('hypotheses','pair_cost','one_action_cost'):
            assert isinstance(call.args[0],ast.Name) and call.args[0].id=='poly'
    output = dict(parent=str(PARENT), review_kind='read_only_interfaces_and_unit_fixtures_no_new_scenario_seeds',
                  module_sha256={n:hashlib.sha256((PARENT/'code'/n).read_bytes()).hexdigest() for n in files},
                  O_and_real_shared_model_kwargs_identical=True, model_calls=model_calls,
                  actual_feedback_integration=results, N_keeps_hard_polygon=True,
                  N_representation_invariant_candidate_count=len(expected_points), findings=[])
    destination = ROOT/'reports/R2_PARENT_OMLN_REVIEW.json'
    destination.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False))


if __name__ == '__main__': audit()
