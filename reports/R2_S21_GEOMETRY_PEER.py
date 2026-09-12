"""Continuous proof of a proposed search skeleton, NOT an exit certificate."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code'),str(ROOT/'reports')]
from directional_geometry import skeleton,DirectionalCoverage
from independent_exit import cell_certificate
from R2_S22_CERTIFICATE_PEER import decimal_certificate


def main():
    started=time.perf_counter()
    parameters=dict(inner_count=8,outer_count=12,inner_radius=999.,outer_radius=1869.,
                    inner_phase=0.,outer_phase=0.)
    stations=skeleton(**parameters)
    ordinary=DirectionalCoverage(max_depth=13,max_cells=250000,time_budget=float('inf')).prove(stations)
    independent=cell_certificate(stations,max_depth=13,max_cells=250000,budget_s=30.)
    precise=decimal_certificate(stations)
    assert ordinary['complete'] and independent['complete'] and precise['complete']
    result=dict(parameters=parameters,stations=stations,planning_geometry_only=True,
        actual_feedback_obtained=False,may_use_as_exit_certificate=False,
        ordinary=ordinary,independent=independent,decimal=precise,
        actual_scene_runs=0,wall_time_s=time.perf_counter()-started,
        source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
            ('code/directional_geometry.py','code/independent_exit.py','reports/R2_S22_CERTIFICATE_PEER.py')})
    (ROOT/'reports/R2_S21_GEOMETRY_PEER.json').write_bytes(json.dumps(result,indent=2).encode())
    print(json.dumps({k:v for k,v in result.items() if k!='stations'},indent=2))


if __name__=='__main__':main()
