"""One registered complete-scene factorial screen; no source mutation during execution."""
from experiment import run_phase

if __name__=='__main__':
    run_phase('R2_LM_dev30',{
        'compact':'D_compact_optical.json',
        'stable':'R2_L_stable_quadrature.json',
        'single':'R2_M_adaptive_single.json',
        'single_stable':'R2_ML_single_stable.json',
    },list(range(500001,500031)),role='development',replay=True)
