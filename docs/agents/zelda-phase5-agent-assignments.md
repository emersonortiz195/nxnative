# Phase 5 agent assignments — start independently

**Safety:** source-code-only experiments. Do not build, upload, or distribute copyrighted game data. Do not touch existing installed app, saves, caches, or shader archive. Do not merge into main. Read [Phase 5 plan](zelda-phase5-community-stability.md) and [sanitized community report](../community/zelda-m2-stability-help.md) first.

## Agent 1 — GPU memory / resource lifetime
Start from `codex/zelda-phase3-integration` on a new branch `codex/zelda-phase5-gpu`. Review draft #5 and upstream/community changes: seedds/nxnative 707cac9 and 352e4a6, cheemu21/kid-with-sword-remake 5a6abb8, and upstream memory guide. Compare source carefully and identify code already present. Instrument current/live vs cumulative Metal allocations, deferred-release backlog, heap reuse, residency churn, and upload staging. Choose one minimal guarded memory fix, with retirement and delayed-GPU-completion tests. Avoid unsafe early releases. Open draft PR with exact provenance and regression evidence; don't claim actual M2 gains without a Mac test.

## Agent 2 — Metal stalls / synchronization
Start from `codex/zelda-phase3-integration` on `codex/zelda-phase5-metal`. Review #6, frame ~7525 submit+present 8.13s, whole 8.66s, GPU 1.24s. Investigate command-buffer waits, locks, residency commits, presentation, texture upload bursts, and autorelease pools. Add low-overhead timing counters with no sensitive path logging. Change only one justified bottleneck; preserve synchronization correctness. Tests and draft PR, no main merge.

## Agent 3 — shader memory footprint
Start from `codex/zelda-phase3-integration` on `codex/zelda-phase5-shader-memory`. Review #7 and cheemu21 shader-warmup zero-retention. Do not regenerate shader archive, alter chain/format, or optimize compile throughput unrelated to runtime stall. Measure/reason about warmup retained temporary memory and cache ownership; implement only a narrow validated fix if evidence supports one. Draft PR or evidence-only report.

## Agent 4 — QA / integration gates
Start from `codex/zelda-phase3-integration` on `codex/zelda-phase5-qa`. Review #8 and prepare read-only Mac capture script/guide: FPS p50/p95, longframes, submit+present time, GPU completion, live Metal allocation, process footprint/peak, swap, residency and staging churn, 20-minute repeatable scene transitions, crash/termination classification. Sanitize all reports (no user paths, machine IDs, game assets). Validate portable tests and CI; no Mac run claimed unless performed. Do not integrate other branches without separate review and user approval.

**Shared acceptance:** 8 GB M2 Air, stable ~30 FPS as goal, not promise; one experimental change per branch, no shader rebuild, no unverified broad community merges, document origin/license and regressions. Public help page has no private logs or copyrighted assets.
