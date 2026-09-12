# S22 scan-before-commit scheduling candidate

Status: passed the first ten-scene development screen, not yet independently validated or promoted. The new option scan_before_commit defaults to false. All experiments here use the self-built local simulator.

## Why this change

The existing S22 controller routes remaining search stations and known-source proxies together. A source that still spans hundreds of metres is represented by its minimum-enclosing-circle center, although later source-specific RF movement may go elsewhere. Committing to that proxy before a nearby mandatory search stop can therefore be premature.

A legal-feedback reconstruction of all 100 S22 validation journals exactly reproduced all 3800 original route decisions. Only two decisions were forced by the eight-source-task search guard, and the mean maximum source-task streak was 3.84. Tuning that guard has little opportunity. By contrast, 760 of 1809 source tasks retained radius above 100 m. There were 793 cases where the next planned search station had a positive existing shared-measurement score for the first source; 411 exceeded the complete proxy-route movement increase plus a conservative 6 s diagnostic reserve. These are heuristic opportunities, not realized savings. The old validation journals are now diagnostic/development material for this candidate; new validation must use new scenes.

The separately supplied worst S22 validation regression, 510078, has 16 actual clears, zero tail after the last clear and no forced-search event. Its seven analogous information opportunities fit the same mechanism. The rule and parameters were not tuned to that individual case.

## Enabled decision rule

After the original open-route solver returns its order, retain that order unless its first task is an uncertain source. Consider only the first existing search station later in that same route. Predict the current known sources' shared-measurement priorities at that station using the unchanged feedback-only information model. The original first source must be in the existing top-three shared-measurement budget and must not have been measured there already.

Move that search task to the front only when its target-source information score exceeds the movement-time increase of the entire reordered open proxy route. The information score already includes the 5 s RF and 1 s switch and includes no-signal outcomes; these are not charged a second time. Guaranteed-clear sources are not delayed. The station set, route solver, source locator, optical policy, existing scan procedure and all exit proofs stay the same. Newly discovered sources may change actual shared-measurement priorities; the controller uses those real responses and replans normally.

This changes one global scheduling factor. It creates no measurement, negative station or empty-channel certificate in advance. Every promoted task removes one actually visited station from the finite existing plan; after the finite search list is exhausted the ordinary known-source locator and finite optical fallback still apply. F, L, partial-optical and extra optical-chain options are disabled in both arms.

## Paired local results

Seeds 1411–1420 were registered before execution. Both arms used identical sources, emission directions, radii and fixed spatial error fields. All 20 scenes completed; all 20 response-only replays, independent exits and registered source-hash checks passed. The 106-test regression suite passed before the batch.

| Metric | S22 | Scan before commit |
|---|---:|---:|
| Full success | 10/10 | 10/10 |
| Mean per-source time, s | 436.967679 | 428.676441 |
| Mean total, s | 5720.567148 | 5604.751731 |
| P95 total, s | 6310.101795 | 6250.253489 |
| Worst total, s | 6519.818886 | 6394.482903 |
| Mean real policy runtime, s | 4.150528 | 4.206139 |
| Mean movement, s | 4244.367151 | 4160.051733 |
| Mean RF, s | 1179.0 | 1148.0 |
| Mean switching, s | 219.0 | 215.8 |
| Mean optical, s | 51.0 | 53.7 |
| Mean clear success, s | 27.2 | 27.2 |
| Mean no-signal count | 199.8 | 198.2 |
| Mean optical failures | 3.4 | 4.3 |
| Mean fallback count | 0 | 0 |

The average per-source reduction is **1.897449%**; paired bootstrap improvement interval **[0.151235%, 3.768993%]**. P95 decreases **0.948452%**. Seven scenes improve and three regress. The batch with replay takes 160.42 real seconds. These ten new scenes support a larger screen and independent validation, not immediate default replacement.

There were 36 scan-order changes across ten scenes. The intended known source was actually measured on all 36: 33 direction responses and three no-signal responses. Mean radius changed from 652.37 m before that scan to 85.03 m after it. This confirms receipt of useful feedback in this sample; radius reduction is not the optimization metric. Source-specific paired RF actions fell from 14.2 to 6.5 per scene, while shared RF rose from 15.2 to 18.1. Added search travel was offset by reduced committed source travel; total movement fell 84.32 s and total RF fell 31 s per scene.

The three regressions, 1416 (+46.07 s), 1419 (+25.72 s), and 1420 (+216.91 s), are retained in every aggregate. No unsuccessful forecast was discarded or converted into a signal guarantee. There is no guarantee of improvement on every scene, and interaction with M/L must be tested rather than added arithmetically.

## Reproduction and merge notes

Use `python -m unittest discover -s tests -q`, then `python code/r2_b_smoke.py --phase NEW_PHASE --start 1411 --count 10 --variants '{"S22":"R2_S_outer13.json","scan_commit":"R2_scan_commit.json"}'`. Reusing these seeds is further development, not independent validation. The phase comparison is `python code/compare_phase.py NEW_PHASE S22 scan_commit`.

Implementation is the new scan_commit_scheduler.py plus a small hook immediately after route ordering in Q4Controller.run. The callback must use the same model flags as share_at_actual_station when merged into a parent with extra joint-weight/error flags. This branch retains its existing hypotheses/exclusions/stable interfaces. No root-parent file was changed.

Evidence is in R2_SCAN_COMMIT10; the legal-history diagnosis summary/script is in R2_SCHEDULE_DIAGNOSTIC and code/scheduling_diagnose.py. Raw local journals, source snapshots, evaluations and replay audits remain in this worktree's runs directory. Frozen S22, D_COMPACT, H0 and Q3 G are unchanged.
