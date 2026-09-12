"""Structural F candidate. Frozen version is assigned before fresh validation."""
from e_policy_presets import FROZEN_E_OPTIONS

FROZEN_F_VERSION='structural-F-experimental'
FROZEN_F_OPTIONS={**FROZEN_E_OPTIONS,'negative_halfplanes':True,'joint_history':True,
    'task_search':True,'tail_cost':False,'optical_exclusions':False,'safe_shared':False,
    'strip_fallback':True}
