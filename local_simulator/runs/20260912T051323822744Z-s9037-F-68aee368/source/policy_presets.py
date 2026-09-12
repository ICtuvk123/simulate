"""Policy frozen after round6 training, before fresh validation or official use."""
FROZEN_D_OPTIONS = {
    'mode': 'joint', 'ring_radius': 1130.0, 'scan_gain': 0.18,
    'known_scan': True, 'max_region': 1000.0, 'opportunistic_clear': True,
    'optical_trial': 40.0, 'ring_rotation': 0.0, 'prune_stations': False,
    'adaptive_plan': False, 'future_stops': True, 'exact_neighborhood': True,
    'local_rollout': True, 'bearing_factor': 0.25, 'near_prediction': 14.0,
}
FROZEN_D_VERSION = 'joint-time-D-round6-refine-bearing'
