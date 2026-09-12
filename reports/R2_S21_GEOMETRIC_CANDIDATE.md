# S21: geometric candidate, no complete-task score yet

The candidate is the origin, eight inner-ring stations at radius 999 m, and twelve outer-ring stations at radius 1869 m. Both rings use zero phase. It has 21 stations. Its runnable configuration inherits D compact optical and changes only the complete search skeleton.

The maximum requested search budget was five real minutes. The registered small regular-ring search checked 505 unique configurations in 19.1764 seconds. Eighteen passed the continuous proof, including two controls; exactly one passing candidate had 21 stations. Other failed candidates are not claimed mathematically impossible: a sampled point can reject one, and a bounded continuous proof can remain unproved. No source truth, scenario, simulator seed, or official endpoint was accessed.

The outer regular polygon has inradius 1805.3153693343 m, giving 5.3153693343 m slack beyond the target circle. More importantly, two separately implemented full quadtrees both certified the local 1000 m convex-hull condition: 5733 visited cells, 2980 certified leaves, zero unresolved leaves. The target-square cells outside the circle are excluded by a conservative distance check. Every retained leaf is wholly contained in the hull of stations whose distances to all its corners are at most 999.99999 m; convexity therefore establishes the continuous condition at every point in the cell. No grid-based acceptance or small-hole omission is used.

A third audit used 60-digit Decimal arithmetic on the exact binary floating coordinates for all accepted leaves. Minimum actual distance slack below 1000 m was **0.0286959302218 m**. Minimum signed distance from a leaf corner to a local hull edge was **0.0294145687668 m**. These are leaf-level strict margins, not simply the inner ring's nominal 1 m slack. Independent leaf digest: `e9269986860770e299d3a71cea5eb498d636336f8371abec4540bce094044fb1`. Decimal leaf digest: `2ea88fc0bb34a7be3e3f2a17e3ba3cfad50e75d0c45d595b2bb1baaa0b229e87`.

This establishes future geometric coverage feasibility only. An actual empty-channel exit still requires accepted no-signal feedback at the applicable sites for that specific channel and the independent actual-history exit check. Planned sites cannot be inserted as actual feedback.

No full-task run was performed for this candidate in this worker. Fewer sites does not imply a faster complete task; source detection order, localization detours, RF and switch counts remain to be measured in parent-controlled paired development scenarios. No average time or claimed speed improvement is attached to this geometric result.

Evidence: `R2_SMALL_SKELETON_SCREEN.py/.json`, `R2_S21_GEOMETRY_PEER.py/.json`. Reproduce with the configured Python runtime and those scripts. The second script calls the independent continuous implementation and the pre-existing high-precision audit routine; combined additional audit runtime was 3.1494 seconds. No validation or holdout seeds were consumed.
