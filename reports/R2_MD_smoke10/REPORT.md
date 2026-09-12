# MD: bounded local commitment after an actual M direction

MD tests one scheduling change on the unchanged S22 + M + L baseline. The hypothesis is that immediately completing one more local step after an informative M measurement can avoid a long global-route detour before returning to the same source.

The default-off option is `bounded_direction_commit`. The public `localize` method calls the unchanged local-step primitive once. Only an actual adaptive-single `direction` response that has not cleared the source can trigger one extra call to that primitive. The second call cannot call the wrapper recursively. A due eight-task search or a source already at the ten-round guard suppresses the extra call. The extra call increments the existing round count, first checks the guaranteed-clear region, and otherwise uses the existing candidate ranking and optical choices. New RF points within 0.05 m of a previous same-channel measurement are blocked before transmission.

“One extra local attempt” does not mean one guaranteed extra RF: the existing primitive can choose a single RF, a full two-endpoint pair, a certified compact optical cover, or the finite optical fallback if geometry requires it. Each block logs actual RF count, optical count, movement time, total virtual time, actual clearing outcome, and its return to global scheduling. These block totals are not causal overhead relative to the baseline; some of those actions would have occurred later anyway.

Single no-signal feedback cannot trigger this option and never supplies a paired-negative certificate. Negative-region updates, guaranteed clearing, source discovery, the actual-history exit certificate, protocol acceptance, request replay, source/engine isolation, and the skeleton are unchanged. No finite candidate model is promoted into hard geometric evidence. The distinct MC option for recovery after a no-signal response is not enabled or tested in this experiment.

The independent optical worker reviewed the wrapper and execution hooks and found no unbounded recursion, hard-region bypass, or exit bypass. Seven new targeted tests and all 154 repository tests passed. Targeted cases cover first/second no-signal, near clearing, repeated points, both guards, default off, and a second direction without a third call.

Experiment: fresh worker development seeds 1431--1440, pre-registered before the first run, two variants per seed. All cases use the same local source configurations and fixed spatial error field for both strategies. Replays receive only recorded feedback. The independent exit checker uses actual accepted histories. This is a ten-pair local smoke comparison, not a validation/holdout result or an official test. The prior engineering screen remains at least 1% average-per-source improvement with no more than 2% P95 total-time degradation, after requiring every registered case to finish correctly.

## Completed results and decision

All 20 registered runs completed correctly; all 20 feedback replays and all 20 independent exits passed. The evaluator confirmed identical worlds and fixed-error configuration in all ten pairs. No failed or incomplete cases were removed. Total experiment wall time, including serial runs, feedback replays and second exit checks, was 532.3523 s.

| Metric | S22 + ML | S22 + ML + MD |
|---|---:|---:|
| Mean complete time per source, s | 444.662009 | 447.209121 |
| Mean total time, s | 5792.770355 | 5828.492369 |
| P95 total time, s | 6118.070804 | 6199.099798 |
| Worst total time, s | 6219.548488 | 6319.186933 |
| Mean policy wall time, s | 12.974847 | 14.337521 |
| Mean movement time, s | 4242.670357 | 4290.592371 |
| Mean RF time, s | 1238.5 | 1230.0 |
| Mean switching time, s | 232.5 | 230.3 |
| Mean optical time, s | 52.5 | 51.0 |
| Mean successful clearing time, s | 26.6 | 26.6 |
| Mean no-signal count | 215.0 | 213.2 |
| Mean optical failure count | 4.2 | 3.7 |
| Mean fallback count | 0 | 0 |

MD worsened mean time per source by **0.57282%** and P95 total time by **1.32442%**. It was faster in one pair, slower in eight and identical in one. The paired bootstrap 95% interval for improvement was **[-1.21982%, +0.15418%]**. It fails the pre-existing improvement gate and is **not promoted**. The default option remains disabled; there was no follow-up parameter tuning or validation/holdout consumption.

The candidate executed 40 bounded commitment blocks and cleared the selected source within 21 of them. Those blocks contained 27 RF actions and 30 optical actions; all returned to global scheduling. No duplicate-point block or guard skip occurred in these ten scenarios; those branches are covered by the targeted tests. The block movement sum was 2685.1893 s and total action time 2952.1893 s across all ten runs. Again, these are actual within-block costs, not added costs relative to baseline.

The complete-task decomposition explains why this local change is rejected. RF, switching and optical time together fell by 12.2 s per scene, while movement rose by 47.9220 s, producing a net 35.7220 s increase. Search-role movement fell by 83.9708 s, but movement charged to adaptive-single probes rose by 145.5364 s and guaranteed clearing rose by 53.7852 s. Reductions in other local roles did not offset this. Immediate local completion alone therefore did not justify taking control away from the global route in this sample.

Code commit: `4728e7c` on base `7893c8a`. The exact configuration and all code hashes are in `registration.json`; each run retains a copied source snapshot and manifest. Run command: `python reports/run_direction_commit_smoke.py`. Post-run command: `python reports/summarize_direction_commit.py`. `paired_results.csv`, `comparison_s22ml_s22ml_md.json`, `commitment_diagnostics.json`, `summary.json` and the retained raw local run directories contain the individual cases and evidence. This result makes no claim about official performance or about the separate MC option.
