"""E candidate frozen before the 6001-6100 independent validation cases."""

FROZEN_E_VERSION = 'feedback-E-round10-shared1200'
FROZEN_E_OPTIONS = {
  "mode": "joint",
  "ring_radius": 1130,
  "scan_gain": 0.18,
  "known_scan": True,
  "max_region": 1000,
  "opportunistic_clear": True,
  "optical_trial": 40,
  "ring_rotation": 0,
  "prune_stations": False,
  "adaptive_plan": False,
  "future_stops": True,
  "exact_neighborhood": True,
  "local_rollout": True,
  "bearing_factor": 0.25,
  "near_prediction": 14,
  "adaptive_reception": True,
  "replan_measurements": True,
  "commit_radius": 120,
  "adaptive_rotation": False,
  "route_centroid": False,
  "area_rollout": False,
  "lateral": 1,
  "replacement_scan": False,
  "shared_limit": 1200,
  "route_hysteresis": 0,
  "eager_count_stop": True
}
