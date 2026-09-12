# R2 B path-only partial optical: development smoke

Status: not promoted; zero actions selected and zero speed improvement.

Implementation: optional partial_optical, initially false. Candidates are current position and nine deterministic positions on the pre-existing first RF leg. A proposed clear includes movement, optical fee, success surcharge, miss continuation through the existing RF or complete four-point optical baseline, and the next-task outgoing leg. At most one trial per actual-positive-information version and four trials per channel. Failed accepted clear actions create a separate radius 20-1e-5 disk; the convex polygon, guaranteed clearance, and legal exit rules remain unchanged. Filtering affects finite ranking hypotheses only.

Validation: all 61 unit tests passed, including eight new partial optical/accounting/provenance/guard tests. Pre-registered development smoke seeds 1101 through 1110 ran both compact and partial configurations. Both variants completed 10/10, every journal was purely feedback-replayed, and every run passed the independent exit verifier. The actual action sequences are identical in all ten pairs, with zero partial actions. Both mean per-source times are 490.646859 s, mean total 6056.908472 s, P95 6791.515012 s. This negative result is preserved rather than claimed as an improvement.

Evidence: R2_B_smoke10/registration.json, runs.jsonl, paired_results.csv, summary.json, negative_result.json. Per-run requests, audit, independent exit and complete source snapshots remain under this worktree's runs directory. The first source snapshot exactly records the prototype executed; subsequent local-candidate experiments use new phase registration and are not part of this report.

No official simulator was used. The two paired configurations were generated only from legal history and fixed local scene feedback, with the same source world and spatial error field per seed. This is development evidence, not independent validation or an official score.
