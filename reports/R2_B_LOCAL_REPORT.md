# R2 B local partial optical candidate

Status: experimental, not promoted. The combined candidate improved average per-source time only 0.286573% in ten repeated development scenarios, below the 1% engineering gate.

Features: the original path-only prototype is preserved in commit c6eb9f205e2be2c0a0b8562d6f19aa5fd67583b1 and configuration R2_B_partial_path.json. The local candidate adds the convex region minimum-circle center and three long-axis positions with at most 120 m modeled detour. This is a finite legal-history geometry-derived candidate set, not hidden source access. It pays actual movement, optical 3 s, successful 2 s, miss continuation and outgoing task leg in ranking.

Independent timing switches:
- partial_optical: master switch, absent/false preserves baseline actions.
- partial_before_pair: compare before the original RF pair; defaults true only when master is enabled.
- partial_after_first: compare one possible optical action against the remaining single RF; defaults false. No complete optical-cover upgrade after the first RF is silently enabled.

Configurations: R2_B_partial_before.json = local before-pair only; R2_B_partial_after.json = after-first only; R2_B_partial.json = both. R2_B_ablation10 pre-registers compact/before/after on the same ten development seeds 1101–1110; results are pending at this commit and must not be represented as completed.

Actual accepted optical failures persist as request-bound exclusion disks of radius 20-1e-5. They filter later ranking hypotheses and prevent retries at identical failed points. The conservative convex polygon is retained without taking a convex hull of a punched region. At most one trial per actual positive-measurement version and four per channel. All failures continue the original reliable pair/complete-cover baseline; no source count, exit proof, or guaranteed clear rule is relaxed. If all finite samples lie in the trial disk but the polygon is not wholly covered, ranking reserves at least 5% miss mass and a nonzero conservative continuation cost. This reserve is an engineering ranking safeguard, not a probability or a hard geometry claim.

Scoring limitation: this is the existing two-RF/single-RF finite estimate plus its terminal approximation and next-task outgoing distance. It includes miss costs but is not a full-world rollout or a proven exact remaining value function.

Completed checks: 64 unit tests passed, including 11 optical state/provenance/boundary/finite-guard/continuation tests. R2_B_local10: both variants 10/10 complete, all 20 pure-feedback replays and independent exit audits valid. Combined: mean per-source 489.240796 s versus 490.646859 s compact; mean total 6037.548530 versus 6056.908472 s; P95 6784.676344 versus 6791.515012 s; worst 7069.199220 versus 7063.087191 s; policy wall means 6.976052 versus 5.744341 s. Six paired scenes improved, three worsened, one tied. There were 13 partial actions, seven successes and six failures, with no fallbacks. Partial moves consumed average 71.679516 s per scene while paired RF movement decreased 79.717056 s; net whole-scene benefit is modest, not equal to gross saved RF travel.

Evidence: R2_B_local10/{registration.json,summary.json,paired_results.csv,checks_and_trial_diagnostics.json}; original per-run logs/source snapshots remain under this worktree runs directory. No official simulator was used; seeds 1101–1110 were explicitly reused development scenes, not validation or holdout.

Merge points: q4controller imports/state, clear failure recorder, filtered choose_pair/hypotheses/shared_information_value calls, before-pair trial with re-ranking on actual miss, and optional first-endpoint trial. lookahead adds optional exclusions as the final argument of hypotheses, choose_pair, shared_information_value. audit adds actual accepted failure request binding and finite-guard checks. Keep any separate negative_cells hooks in parent code; these optical exclusions do not replace them.
