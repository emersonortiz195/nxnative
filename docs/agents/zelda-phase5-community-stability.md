# Phase 5 — community-informed GPU stability (M2 Air, 8 GB)

Status: investigation plan only. No runtime fix merged or validated.

## Baseline evidence (Nov 13, 2026)
- Phase 4 reportedly approached 30 FPS before a severe stall and SIGKILL; OS kill cause remains unconfirmed.
- Game log: frame 7525 whole frame 8659.5 ms, submit+present 8128.4 ms, GPU 1240 ms; no new shaders or pipelines in that frame.
- GPU allocation reported about 5.1 GB near end; do not equate this counter with physical footprint or proof of OOM.
- macOS log searches returned unrelated jetsam/Quick Look messages, not a confirmed Zelda memory kill.

## Community code to evaluate (verify already present before porting)
1. https://github.com/cheemu21/kid-with-sword-remake/releases — V18 Potato mode: GPU memory guard, 64 MB texture recycle bin, unused shared-texture sweep, shader warmup with no retained allocations, file-backed large pools, lazy render targets. Do not assume its 4400 MB trigger is appropriate for an 8 GB Mac.
2. https://github.com/seedds/nxnative/commit/707cac9 — recycled Metal heaps for dynamic-resolution render targets.
3. https://github.com/seedds/nxnative/commit/352e4a6 — indexed storage-takeover lookup instead of scanning entire alias table.
4. https://github.com/seedds/nxnative/blob/main/docs/reference/memory.md — bounded upload staging, readback autorelease pools and completion lifetimes.
5. https://github.com/seedds/nxnative/issues/2423 — buffer texture residency churn; cross-check related #1061 and exact code path.
6. https://github.com/cheemu21/kid-with-sword-remake/commit/5a6abb8eea2a3fc9d86aae67e4777dbac899c0b2 — pool_skip_retired and raw global memory pool table improvements.

## Parallel work, separate branches
- **GPU memory:** trace Metal allocation ownership, retired resources, staging blocks, alias storage, lazy render targets. Select one small guarded fix with deterministic retirement tests.
- **Metal renderer:** instrument submission vs GPU completion and residency-set commits; investigate long present stalls without disabling fences or hazard tracking.
- **Shader:** preserve existing archive and chain. Inspect only shader warmup's transient footprint, not compile speed.
- **QA:** establish repeatable Kokiri scene/transition route; sample FPS, frame p95, GPU time, physical footprint and peak, swap, live Metal allocations, upload bursts, residency churn, thermal state and process termination. Validate 20-minute M2 sessions and rendering correctness.

## Integration gates
- Review existing draft PRs #5 (GPU), #6 (Metal), #7 (shader), #8 (QA) first; avoid duplicating and mixing unvalidated fixes.
- Preserve Phase 4 app, saves, game assets, shader archives and backup branches.
- No shader rebuild, automatic merge, or replacement of working app until Mac validation.
- Attribute borrowed contributions and comply with upstream licenses.
- Compare each candidate against the same baseline, one change at a time. Document exact source commit and test results.
