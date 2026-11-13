# Phase 5 GPU memory: bounded completed-heap returns

Agent 1 branch: `codex/zelda-phase5-gpu`, from Phase 3
`17020e5403ceec9aeeff756c6e7047f9d2d2f945`. Target: M2 MacBook Air,
8 GB unified memory. Source-only experiment; no Mac or gameplay run performed.

## Current candidate after the P2 review

[Completed heap returns exceed the idle recycle budget](../reference/rendering.md#completed-heap-returns-exceed-the-idle-recycle-budget)
describes the underlying gap. Phase 3 admitted every completed heap and trimmed
only at submission start, at most 64 entries. The initial Phase 5 commit
`2e66e1b5fde8b15b184589394efde5e827e28bc6` instead rejected new returns at a full
256 MiB cache. Review identified repeated allocations when old cached sizes could
not serve a newly recurring size. That rejection-only policy is superseded.

The revised policy plans oldest-idle eviction under the recycle lock, then
admits the incoming completed heap within the existing 256 MiB capacity. No live
or in-flight texture enters this list; retirement fences and serial ownership
are unchanged. Evicted references transfer to a local list under the lock;
residency removal and final release happen after unlocking. Reuse and trim share
the same metadata removal helper, and trim's previously unlocked count precheck
is removed so concurrent return/reuse/trim do not race on that read.

Planning is bounded to 64 candidate scans/evictions. An oversized heap or a
return requiring more than 64 evictions is rejected without partially destroying
the cache. LRU means oldest idle return time, not texture access history. It is
not a compatibility-aware partition: old heaps of useful sizes can be evicted
as well as incompatible sizes. This removes the demonstrated size-change churn
case, but mixed workloads can still churn. Worst-case planning is O(64 times
idle entry count) under the recycle lock; Mac lock time remains unmeasured.
The shared C policy is in `nvn_heap_cache.h`, exercised directly by portable tests.

This bounds logical cached capacity, not physical footprint, driver retention,
pending evictions or live GPU memory. An evicted heap may remain alive in Metal
or in a diagnostic snapshot. The reported frame 7525 stall and SIGKILL cause
remain unconfirmed. Recycle-off behavior and the shader chain are unchanged.

The diagnostic now retains a local array snapshot under `g_res_mu`, unlocks,
then queries `allocatedSize`. The snapshot and weak-enumeration autoreleases
are released in a local pool before the helper returns. There is no persistent
snapshot cache. Snapshot construction still costs O(residency count) and O(count)
temporary references under the lock; driver queries no longer hold that mutex.
This is a sampled logical capacity, not an atomic simultaneous view of the
whole renderer or unique physical memory. Overlapping no-copy buffers may
count the same storage twice. New counters distinguish cumulative evictions
from rejections; existing counters cover upload staging, deferred backlog,
serial-held retirements, heap reuse and residency commit churn/time.

The native delayed-completion test now calls a process-only `_Exit(1)` helper
immediately after a bounded wait fails, skipping ARC cleanup and exit handlers.
It never proceeds to `mtl_drain` on timeout. The forced-timeout run leaves the
GPU gate unsignaled and waits 50 ms; a parent requires the expected failure
within 15 seconds. This does not change production shutdown or GPU recovery.

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

## Fresh validation after the P2 fixes

- Focused docs/chain/graphics-Makefile/shader-compatibility plus new portable
  policy/timeout and env-switch catalog suite: **47 passed**.
- Production C policy fixture: strict C11/GCC `-Wall -Wextra -Werror` passed;
  the same concurrent fixture passed ASan/UBSan and separately ThreadSanitizer,
  with no suppressions. Counts vary with scheduling; every run reports zero
  failed assertions. This validates metadata/locking, not ARC or Metal lifetimes.
- Portable deterministic size-change case: a full cache of size-4 heaps receives
  60 size-5 requests (size-6 replacement capacity): **one allocation, 59 reuses**.
  Tests also cover exact capacity, oversized returns, timestamp ties, oldest
  selection in unsorted storage, 64-eviction limits, rejection without mutation,
  and admission/reuse/trim with a deterministic first interleaving plus stress.
- Portable rejection-only negative control (initial Phase 5 admission behavior):
  the same fixture **fails as expected**, including its one-allocation assertion.
  This is distinct from an unrun native old-renderer negative control.
- Portable timeout child registers an intentionally non-returning cleanup handler:
  expected exit 1 occurs within the parent deadline, proving cleanup is skipped.
- CPU texture suite: **5,382/5,382 passed**.
- Changed Python Ruff and Pyright: **passed**, zero Pyright errors/warnings.
- Full graphics Python discovery: **480 run, nine errors, 179 skipped**. Every
  error is a missing-`xcrun` Metal compile test; all three new portable tests pass.
- Final full tools discovery: **1,399 run, 15 failure records, 37 errors,
  70 skips**. An earlier run exposed the missing forced-timeout catalog row;
  that new failure was fixed and is absent from the final rerun. Remaining
  records include missing macOS dylibs/tools, a bundled Mach-O executable,
  macOS/APFS/device fixtures and an inode-reuse assumption. Full discoveries
  are **not green**; failure records include subtests.
- Broader iOS fixtures: **52 run, 21 failure records, ten skipped**, including
  macOS/APFS packaging behavior. Host Python discovery: **two missing native
  `t_svc_memory` executable errors**. No native host pass claimed.
- Full Python lint ratchet remains red on unchanged `dmsh_entry.py`'s F401
  (`dmsh_fetch`) and three locally resolved baseline imports. The two new Python
  files pass direct Ruff/Pyright; no baseline growth or chain edit hides failures.
- Native recycle-budget/snapshot target attempted: **blocked before compilation**
  by missing `xcrun` generating built-in host Metal headers. C lint compilation
  database likewise blocked; clang-tidy unrun locally. This session exposes only
  a Linux executor, no Metal-capable Mac. Native old-code negative controls,
  forced-GPU-timeout execution and Foundation snapshot lifetime test remain unrun.
- Regression impact/five-game gameplay check retain the previously established
  macOS `libproc.dylib` import blocker; Phase 4 #8 is not integrated to mask it.

`t_res_snapshot` uses a fake allocation whose getter acquires the residency
mutex and drops its last external reference. It requires the snapshot to keep
it alive through the getter and release it before returning, then verifies an
empty subsequent snapshot. It does not need a Metal device but still requires
macOS/Foundation compilation. `t_rt_recycle_budget` now verifies actual Metal
size-change reuse and concurrent admission/reuse/trim, plus delayed GPU retirement
with valid readback and the forced-timeout child in direct/deferred encoding.

Portable commands (set `DM_GAME=0400486024DEC000` and `DM_ROOT` to new scratch):

```sh
python -m unittest dm/gfx/tests/test_heap_cache.py dm/tools/tests/test_docs.py dm/tools/tests/test_nsp_chain.py dm/tools/tests/test_gfx_tests_makefile.py dm/tools/tests/test_shader_compat.py dm/tools/tests/test_env_switches.py
make -C dm/gfx/tests GAME=0400486024DEC000 t_heap_cache
./dm/gfx/tests/t_heap_cache
cc -std=c11 -O1 -g -Wall -Wextra -Werror -pthread -fsanitize=address,undefined dm/gfx/tests/t_heap_cache.c -o <scratch>/heap-asan
cc -std=c11 -O1 -g -Wall -Wextra -Werror -pthread -fsanitize=thread dm/gfx/tests/t_heap_cache.c -o <scratch>/heap-tsan
```

## Mac validation before integration

Use an isolated source checkout and matching existing host/archive chain, without
rebuilding shaders or replacing the Phase 4 app. This branch keeps chain
`3ae08e02ec6a`; do not relabel an older archive to match it. Follow the
[Phase 3 isolation procedure](zelda-phase3-integration.md).

```sh
make -C dm/gfx/tests GAME=0400486024DEC000 check_t_rt_recycle_budget check_t_res_snapshot
make -C dm/gfx/tests GAME=0400486024DEC000 check_t_rt_recycle check_t_image_alias
make -C dm/gfx/tests GAME=0400486024DEC000 check_t_pool_retire check_t_upload_slots check_t_upload_budget
make -C dm/gfx/tests GAME=0400486024DEC000 run
```

Run native negative controls with only the rejection-only `rh_wait` from
`2e66e1b5` restored, and separately with the Phase 3 unbounded `rh_wait`; the
new reuse/capacity assertions must fail. Run native sanitizer/lint checks. Select Ocarina of
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
SIGKILL and confirmed OS memory kills separately. Measure snapshot construction/query
cost, recycle-lock planning time and churn after eviction/rejection; the memory bound alone is not
an acceptance test for frame pacing.

Publish only sanitized aggregate results and source revisions: no private paths,
machine identifiers, raw laptop logs, game assets or screenshots containing
private data. No M2 FPS, footprint, stall or reliability gain is measured here.
Draft review only; do not merge into main or combine Phase 4 candidates without
separate review and authorization.
