# Phase 5 GPU memory: bounded completed-heap returns

Agent 1 branch: `codex/zelda-phase5-gpu`, from Phase 3
`17020e5403ceec9aeeff756c6e7047f9d2d2f945`. Target: M2 MacBook Air,
8 GB unified memory. Source-only experiment; no Mac or gameplay run performed.

## Finding and candidate

[Completed heap returns exceed the idle recycle budget](../reference/rendering.md#completed-heap-returns-exceed-the-idle-recycle-budget)
describes the mechanism and fix. Previously `rh_wait` retained every completed
heap until a submission's `rh_trim` removed idle/excess entries, at most 64 per
call. There was no bound between submissions. The existing 256 MiB budget now
also gates admission, under the same lock that protects reuse/removal. A return
that cannot fit leaves residency outside the lock without entering the list.
There is no eviction of live textures or earlier resource retirement.

This bounds logical idle heap capacity, not total GPU memory, physical footprint,
pending deferred objects or driver retention. It does not diagnose the reported
frame 7525 stall (about 8.13 s submit/present, 1.24 s GPU) or prove why SIGKILL
occurred. At saturation rejecting the newest heap preserves the current cache,
rather than trim's oldest-first preference. A newly useful size may therefore
need allocating again; allocation, residency-commit time and frame tails must be
compared on Mac before integration. `DM_NVN_RT_RECYCLE=0` retains its old behavior.

The low-frequency, capped memory readout adds current logical residency capacity
and exact idle-heap bytes/limit, plus cumulative rejection counts/capacity. Weak
residency enumeration has its own autorelease pool so diagnostics do not pin
objects on guest threads. Heap-backed textures count their heap once through the
existing residency set. Overlapping no-copy buffers can count the same memory
more than once; this is not unique live physical allocation. Enumeration cost
under the residency mutex is unmeasured and must be checked on Mac.

Existing counters still cover deferred-release backlog, retired-but-serial-held
objects, heaps made/reused/trimmed, upload blocks created/swapped and swapped-out
blocks still alive/resident. Residency churn/timing by allocation site remains
in `mtl_res_stats`; those counts reset each reporting interval. Do not read
cumulative allocations, requested capacity or `currentAllocatedSize` as proof
of a leak or OS OOM. Correlate with physical footprint, swap and GPU completion.

## Community and Phase 4 review

| Source inspected | Present / decision |
|---|---|
| [Phase 4 GPU #5](https://github.com/emersonortiz195/nxnative/pull/5), `6cfb79edb0127027323df9ec7e53fd5e57e4d9c6` | Releases completed primary upload-slot staging before allocating its replacement. Not imported: a separate unvalidated candidate. The Phase 3 baseline still defers that growth release. Its delayed-slot/old-code negative control remains a Mac gate. |
| [seedds 707cac957fa8ed7d3d505ed253a55026da210a17](https://github.com/seedds/nxnative/commit/707cac957fa8ed7d3d505ed253a55026da210a17) | Already present: one recycled placement-heap list for GPU-only targets, resolution families and feedback snapshots; eighth-size headroom and best-fit up to 1.5 times requested capacity. Do not port again. Admission hardening is new local work. |
| [seedds 352e4a6e917e34bff4bd682901dfde6e38b0459e](https://github.com/seedds/nxnative/commit/352e4a6e917e34bff4bd682901dfde6e38b0459e) | Cell-indexed alias takeover is absent (`g_alias_cells`/`ALIAS_CELL`). Baseline still scans sharing-table capacity. Plausible CPU stall investigation, but no target trace establishes it as this stall's cause. Not mixed with this memory experiment; port needs all alias writers/index-removal tests and independent review. |
| [Upstream memory guide](https://github.com/seedds/nxnative/blob/main/docs/reference/memory.md), inspected blob `7e432a012fae47a2422e9c7b2aed283d50b81457` | Bounded staging, completion-owned temporary staging, autorelease-pool lifetime cautions and addressed-pool raw tables match relevant baseline mechanisms. Three retained upload slots keep at most 192 MiB; temporary batches have a 128 MiB budget with an oversized-single-upload exception. No early release of in-flight staging proposed. |
| [cheemu21 5a6abb8eea2a3fc9d86aae67e4777dbac899c0b2](https://github.com/cheemu21/kid-with-sword-remake/commit/5a6abb8eea2a3fc9d86aae67e4777dbac899c0b2) | This commit itself changes credits, not runtime code. Its tree credits David Lepe for `pool_skip_retired` and addressed raw-pool tables. Reviewed that tree's `nvn_mtl.m` and build history instead of treating the credit commit as an implementation patch. |

The community tree's `pool_skip_retired` intentionally substitutes a dummy for
a finalized texture ID without a view, guarded by a profile/env setting; its own
comment notes that console handles can still read finalized storage. Our baseline
has ghost/serial retention for finalized descriptors and addressed raw-pool
tracking already. Do not replace that lifetime contract with dummy substitution
without correctness evidence. The community's 64 MiB texture bin, orphan sweep,
lazy targets and 4,400 MB Potato trigger are separate gated policies, not a
validated 8 GB Mac budget. File-backed guest pools have disk/VM tradeoffs and
shader warmup belongs to another assignment. None was enabled or copied here.

Both inspected repositories carry the MIT license, copyright 2026 seedds;
the existing license is preserved. Community references informed the comparison;
no community runtime patch is transplanted. Other Phase 4 drafts (#6 Metal fill
initialization, #7 compiler-cache coalescing, #8 QA sampler portability) remain
separate; no source branch, app or combined runtime build is modified.

## Validation

Available Linux checks:

- Documentation, chain, graphics Makefile and shader compatibility:
  `python -m unittest dm/tools/tests/test_docs.py dm/tools/tests/test_nsp_chain.py
  dm/tools/tests/test_gfx_tests_makefile.py dm/tools/tests/test_shader_compat.py`:
  **43 passed**, including a final rerun after this report and symptom generation.
- `make -C dm/gfx/tex/tests CLANG=cc t_tex` and `dm/gfx/tex/tests/t_tex`:
  **5,382/5,382 checks passed**. GCC reports the existing missing-field-initializer
  warning in the texture fixture. These CPU tests do not exercise Metal admission.
- `make -C dm/gfx/tests GAME=0400486024DEC000 check_t_rt_recycle_budget`:
  **blocked before native compilation**, missing `xcrun` while generating host
  built-in Metal headers. No Objective-C/Metal compile or execution pass claimed.
- `python dm/tools/lint_c.py compdb`: blocked at the same missing `xcrun`
  prerequisite; clang-tidy not run.
- `python scripts/regress.py impact origin/main..HEAD --out <scratch>/impact`:
  blocked on import of macOS `libproc.dylib`. Phase 4 #8 addresses this separately;
  it is not included in this branch. The five-game gameplay `check` was also
  attempted and failed at the same import before any game or archive work.
- Whitespace/chain checks pass. No shader-chain tools, shader inputs, archive
  formats, game binaries/assets, saves or installed builds are changed.

New native `t_rt_recycle_budget` includes the actual renderer implementation:
exact budget, one-return overflow, reuse/return accounting, oversized heap,
concurrent returns, and retirement behind an unsignaled GPU event. It verifies
residency before completion and rejection after completion, plus zero-content
GPU readback. It retains test heap references deliberately to check logical
residency rather than assume immediate physical destruction. Its native target
runs with direct/deferred encoding and Metal validation. Existing recycle-off,
family-heap, upload and pool-retirement tests remain required. With only the old
`rh_wait` restored in a disposable checkout, the new capacity/rejection assertions
must fail; that negative control has **not** run here.

## Mac validation before integration

Use an isolated source checkout and matching existing host/archive chain, without
rebuilding shaders or replacing the Phase 4 app. This branch keeps chain
`3ae08e02ec6a`; do not relabel an older archive to match it. Follow the
[Phase 3 isolation procedure](zelda-phase3-integration.md).

```sh
make -C dm/gfx/tests GAME=0400486024DEC000 check_t_rt_recycle_budget
make -C dm/gfx/tests GAME=0400486024DEC000 check_t_rt_recycle check_t_image_alias
make -C dm/gfx/tests GAME=0400486024DEC000 check_t_pool_retire check_t_upload_slots check_t_upload_budget
make -C dm/gfx/tests GAME=0400486024DEC000 run
```

Run the negative control and native sanitizer/lint checks. Select Ocarina of
Time, Tears of the Kingdom, Link's Awakening (repeated movie uploads), Octopath
Traveler II and Mario Kart World (resolution churn) for `regress.py check --games`
when owned local builds and matching existing archives are available. This is
the five-game selection by resource reach, not a gameplay pass. Do not use the
regression harness to trigger archive preparation/rebuilds against user constraints;
stop if its prerequisites would require that and report the blocked gate.

On the 8 GB M2, compare the exact Phase 3 control with this candidate alone using
identical copied save state, verified actual resolution, 30 FPS cap and scene
route. Alternate at least three runs per revision, each with 20 minutes of
Kokiri/scene transitions and focus changes. Record frame p50/p95/p99 and longframes,
submit/present versus GPU completion, process footprint/peak, swap deltas, current
logical residency/idle capacity, heap rejection/reuse, upload bursts and residency
commit time. Compare render output and classify command-buffer errors, crashes,
SIGKILL and confirmed OS memory kills separately. Measure diagnostic enumeration
cost and watch for increased churn after rejection; the memory bound alone is not
an acceptance test for frame pacing.

Publish only sanitized aggregate results and source revisions: no private paths,
machine identifiers, raw laptop logs, game assets or screenshots containing
private data. No M2 FPS, footprint, stall or reliability gain is measured here.
Draft review only; do not merge into main or combine Phase 4 candidates without
separate review and authorization.
