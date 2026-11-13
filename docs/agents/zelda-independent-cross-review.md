# Independent integration review: Zelda on M2, 8 GB

## Continued review and publication, November 12, 2026

This section supersedes the earlier access, CI and publication status below.
The assigned compatibility work is on `codex/zelda-independent-cross-review`,
draft [PR #1](https://github.com/emersonortiz195/nxnative/pull/1). The source
remains chain `3ae08e02ec6a`; no runtime, profile, shader-chain or archive was
modified in this continuation. `DM_M2_NO_FULL_POOL` was not enabled.

### Completed fixture fix

The focused suite reproduced `FileExistsError` in the cache-padding test's
fake translator. It returned the same scratch directory for both batches.
Translation overlaps finishing even with `NJ=1`, and the real builder removes
each finished batch directory; the next fake translation's `mkdir` therefore
raced the preceding cleanup. The fixture now creates a distinct temporary
directory per batch, matching the real translator. Production translation,
dependency ordering, cache publication and cache restoration remain exercised.
No runtime optimization or shader rebuild is implied by this test correction.

### Fresh validation

Python commands use `/workspace/venv/bin/python`; game-specific commands set
`DM_GAME=0400486024DEC000`. Logs are local scratch under `work/`.

| Check | Result |
|---|---|
| Focused `unittest` files: shader_compat, shader_toolchain_cache, shader_lib, nsp_chain, docs, env_switches, pollwait_fixture | Before fix: 86 run, one cache-fixture error. After fix: **86 passed** |
| Shader gather_offsets, hmma, border, reflect, fetch, ampere_mem plus tbdr_budget, with `DM_ROOT` in workspace scratch | **147 run: 63 passed, 84 skipped**, no errors/failures |
| CPU textures: `make -C dm/gfx/tex/tests CLANG=cc t_tex`, then `t_tex` | **5,382/5,382 checks passed** |
| Published memory branch `df2c6e9f` guard C model, copied with its unchanged header into scratch; `cc -std=c11 -O2 -Wall -Wextra -Werror` | Compile and execution passed |
| Cache-padding test independently after the fix | One passed |
| Changed-file Ruff; `git diff --check` | Passed |
| Full tools discovery | 1,394 run; failed with 14 failure records, 37 errors, 70 skips |
| Full gfx Python discovery | 477 run; 14 errors, 179 skips |
| Full iOS Python discovery | 52 run; 21 failure records, 10 skips |
| Host Python discovery | Two errors: missing native `t_svc_memory` executable |
| Native host/gfx `make ... run` | Blocked by missing clang/Xcode/Metal; no native pass claimed |
| `scripts/regress.py check --games 0400486024DEC000` | Cannot import macOS `/usr/lib/libproc.dylib` on Linux |
| Python lint ratchet against origin/main | Failed: unchanged `dmsh_entry.py:7` unused `dmsh_fetch` import; three locally resolved imports remain in baseline |

The broad discovery commands were `python -m unittest discover -s` with
`dm/tools/tests`, `dm/gfx/tests`, `dm/ios/tests`, and `dm/host/tests` respectively.
They are **not passing suites**. Their failure records include subtests, so
subtracting records from discovered counts does not give reliable pass totals.
Observed blockers include missing macOS libraries, Xcode `xcrun`, native build
products, macOS-specific copy flags/APFS clone expectations, and strict GCC
warnings in unrelated test C snippets. The initial full gfx run also used a
default scratch directory under the read-only home; its five budget-test errors
were resolved by setting `DM_ROOT` under workspace scratch in the focused run.
The cache-fixture race above is fixed; broad discovery was recorded before it.
These failures must not be suppressed or described as successful Linux coverage.

### Observed GitHub CI

At `a70a4864a5bf41ebb74f561a101fa6f3be71640c`, the
[tests workflow](https://github.com/emersonortiz195/nxnative/actions/runs/43293263685)
completed successfully. All six jobs passed: host/CPU gfx, sanitizers, tool
tests, coverage, Mac/gfx/iOS source build checks, and unsigned synthetic iOS app.
This establishes CI coverage on that revision, not gameplay or this new commit.
The local fixture correction and report still need their own PR CI run.

[Python lint](https://github.com/emersonortiz195/nxnative/actions/runs/43293263535)
failed on the unchanged shader-chain import above. Removing it would change the
chain and invalidate existing libraries for a lint-only cleanup, so it remains
an explicit blocker for a separate chain-coordinated fix. No baseline was edited.
[C lint](https://github.com/emersonortiz195/nxnative/actions/runs/43293263741)
never reached compilation: checkout failed three times with `Could not resolve
host: github.com`. This is infrastructure failure, not a clang-tidy result.

### Published branch compatibility and coordination

Remote heads were fetched explicitly and inspected without editing other branches.

| Branch/head | Review and integration recommendation |
|---|---|
| `codex/zelda-compatibility-review` / `27fbc92f` | Ancestor already included in #1; do not apply again |
| `codex/zelda-ci-fixes` / `5a5b94d1` | Contains #1's `a70a4864` plus its own progress report; no additional code to integrate |
| `codex/zelda-phase2-integration` / `28debc68` | Exposed as draft [PR #2](https://github.com/emersonortiz195/nxnative/pull/2), with review comment; optional map/table checks extend the same preflight and tests. Integrate its incremental commit after #1, preserving #1's newer pollwait/catalog fixes. Local three-way merge-tree inspection showed no conflict markers; GitHub mergeability and CI must still be checked |
| `zelda-m2-memory-experiments` / `df2c6e9f` | Exposed as draft [PR #3](https://github.com/emersonortiz195/nxnative/pull/3), with review comment. Older renderer diff reverses main's `MLOG` host-stack logging protection. Preserve main's `dm_log`; extract diagnostics separately from unsafe mapping bypass after ARC/Metal validation |
| `zelda-m2-8gb-optimization` and backup / `02353ca3` | Same mapping experiment, inherited by #3; complete raw-address coverage unproven, blocked |

Opening #2/#3 made existing published proposals reviewable; it did not modify
their commits or imply author validation. No merge, rebase, force-push or rewrite
of another contributor's branch occurred. GitHub connector access worked even
though local `gh auth status` reported an invalid token.

Recommended order remains #1 compatibility/test work, then #2 optional read-only
map/table checks, then diagnostics-only work from #3 after Foundation/ARC O0/O2,
real Metal residency/add/remove/submission/retirement and scene-transition tests.
Full-pool bypass stays blocked. Diagnostics add overhead and do not reduce peak
memory by themselves. No separately published shader-stall or renderer throughput
optimization was found beyond these proposals.

### Benchmark and readiness limits

No M2, game files, installed archive or Metal GPU is available here. FPS,
frame-time p50/p95/p99, peak footprint, swap, shader stalls and thermal results
are **not measured**. The 720p/~30 FPS target is unverified. On the target M2,
first establish a correct matching-chain baseline, verify internal/presented
resolution, then compare each proposal separately with alternating runs and
sustained scene transitions. Keep the original archive untouched.

This branch is ready for independent code/integration review as a draft.
It is not merge-ready or evidence of reliable 720p/30 gameplay. Mac GPU tests,
real archive compatibility, required impacted-game regressions for any future
runtime change, M2 benchmarks and lint resolution remain outstanding.

Agent 4 review, November 12, 2026. Goal: correct Ocarina of Time gameplay at
approximately 1280x720 and 30 FPS on an Apple M2 MacBook Air with 8 GB unified
RAM. All checks below ran on Linux. No Metal, Xcode, Apple GPU, installed game,
real shader archive or gameplay was available for validation.

## Access and inspected revisions

The attached executor became usable after its earlier failure. These requested
commands succeeded in `/workspace/nxnative`:

```sh
pwd
git status
git fetch origin
```

The path was `/workspace/nxnative`, branch `work`, clean. The configured fetch
refspec covers main only, so review branches were fetched explicitly afterward:

```sh
git fetch origin \
  refs/heads/zelda-m2-memory-experiments:refs/remotes/origin/zelda-m2-memory-experiments \
  refs/heads/zelda-m2-8gb-optimization:refs/remotes/origin/zelda-m2-8gb-optimization \
  refs/heads/codex/zelda-compatibility-review:refs/remotes/origin/codex/zelda-compatibility-review
```

`git ls-remote --heads origin` listed five remote branches:

| Branch | Inspected HEAD | Contribution status |
|---|---|---|
| main | `084f5aa5c59bbfbebfcab7ad1b1a3b9bc196a582` | Baseline, chain `3ae08e02ec6a` |
| zelda-m2-memory-experiments | `df2c6e9f1f2aeb123f5c1c851050e6b3c9ca49a7` | Diagnostics and synthetic tests published; Mac execution unverified |
| zelda-m2-8gb-optimization | `02353ca3b826ce2be52627f3da370bbb96605ea7` | Experimental opt-in mapping bypass only; not a validated optimization |
| backup-zelda-before-ai-agents | `02353ca3b826ce2be52627f3da370bbb96605ea7` | Same commit as the preceding branch, not another contribution |
| codex/zelda-compatibility-review | `27fbc92fbe6e7211809bdf4cb2a2504663c103c1` | Agent 4 preflight, cache-safety patch and report published; tests rerun here |

The first two experiment branches' commits name `emersonortiz195` as author.
That does not identify which external agent produced them. Only the compatibility
branch is attributable to Agent 4 through this task's history. No separate
published Metal-performance or shader-optimization branch was discoverable.
Their work is **unavailable for review**, not presumed absent or complete.
Earlier local render/shader worktrees in this workspace are investigation
checkpoints, not evidence of another agent's delivered work.

Both experiment branches fork at `2d3fb83b`, before main's `3e940796` host-stack
logging fix and `084f5aa5` graphics-scale answer change. Replacing a whole host
from those older branches changes more than memory diagnostics relative to main.
Their base must be controlled in comparisons. No branches were merged here.

## Correctness, ownership and synchronization review

### Mapping bypass: reject for integration

Commit `02353ca3` changes `gmem_map` in `dm/gfx/nvn/nvn_mtl.m`.
The switch below exists only on that experimental branch, not in this review
branch's current code. It must remain unset/disabled; this is historical analysis,
not a configuration recipe.
`DM_M2_NO_FULL_POOL=1` suppresses full buffers for large guest pools, while the
generated table still describes only existing buffers/chunks in `g_pools`.
Raw shader addresses are data-dependent and need not lie in a chunk previously
created by a host buffer lookup. There is no replacement coverage proof or
fault-and-remap implementation. Raw reads can therefore resolve as unmapped,
and required writes can be lost. This is a confirmed missing-mapping path by
source inspection, not a reproduced M2 GPU failure.

This opt-in path is not ready for integration or correctness/performance claims.
Keep the variable unset or zero. Reducing accounted/wired bytes by removing
required mappings is not an acceptable optimization. A repair needs Agent 1/3
to establish all reachable shader addresses or implement a correct alternative
mapping scheme, with GPU read/write tests; portable threshold tests cannot prove
that property. No speculative runtime replacement was implemented in this review.

### Memory diagnostics: plausible ownership design, conditional Mac testing

Reviewed `6796288d` and `df2c6e9f` in full, including `res_commit`,
`mem_guard_init`, `nvn_mem_guard.h`, the C policy tests, Foundation harness,
Python negative controls and CI entries.

- Set mutation and weak committed snapshots use `g_res_mu`; cached totals use
  atomics for the timer. Threshold data is initialized before timer activation.
- Strong local snapshots with precise-lifetime annotations are intended to keep
  allocations alive until after unlock. Destruction can call `res_remove`;
  releasing the last reference under that mutex could deadlock. The local
  autorelease pool bounds guest-thread temporary ownership. Preserve both
  lifetime guarantees in any refactor.
- `df2c6e9f` separately declares both test snapshots `__weak`, correcting a
  masked negative control. The Foundation harness tests deallocation reentry
  and dirty-state preservation; it does not model actual MTLResidencySet or
  command-buffer ownership, timer delivery, shutdown or device allocation.
- Diagnostics do not enforce a budget, evict resources or prevent OOM. Removed
  but deallocated weak entries disappear; overlapping no-copy buffers can count
  the same physical pages more than once. Neither logical totals nor the
  memorystatus percentage establish exact free memory or process footprint.
- With diagnostics enabled, every `res_commit` request scans both sets even on
  clean calls, and `sysctlbyname` is performed under the residency mutex. This
  adds O(number of resident allocations) CPU work and lock hold time. The 100 ms
  timer adds more sysctl traffic. The existing commit-time counter starts after
  the first diagnostic scan, so it does not measure the full added cost.

No additional confirmed guard-specific concurrency defect was established by
this Linux review. That is not proof of safety. Mac O0/O2 lifetime negative
controls, actual Metal allocation/removal and concurrent scene-transition tests
remain mandatory. Diagnostic-only testing is reasonable once chain compatibility
is solved; leave the mapping bypass off and benchmark guard-off separately.

### Compatibility branch and reuse safety

`27fbc92f` changes no residency or submission code. Its source-header chain
remains `3ae08e02ec6a`; `04811a63` records `39eb2f781d07`. The user's existing
6.9 GB archive is not mounted here and was not inspected or changed.

The loader appends its compiled-in chain to DM_MSL_DIR and checks per-shader
reflection chain. Header-only changes, renamed images and JSON edits cannot
prove ABI compatibility. First test an actual host built from a matching source
revision against the preserved archive. A 720p window is not proof of 720p
internal rendering, and a black-screen FPS counter is always a failure.

The new preflight audits metadata and base-file presence, including folder-first
per-file overlays. It does not validate every side library, shader-map coverage,
entry point, binary target or reflection ABI. Its zero exit status must not be
described as successful gameplay validation. This limitation is documented and
the synthetic tests passed again.

The MSL cache's source/compiler/target/flags keys and prefill checks are preserved.
Failed/empty xcrun probes are now rejected rather than used as cache provenance;
successful identity bytes remain unchanged. Earlier archives lacking source or
compiler metadata cannot be assumed reusable. Prefill may compile samples and
keyed builds may rewrite an output image, so neither is an authorized read-only
inspection of the original archive. Only a separate output/cache root may be
used for a later approved compilation trial. No cache reuse percentage is known.

## Confirmed test portability issue and isolated correction

The first broader shader run exposed six `test_dmsh_fetch.py` methods that call
`xcrun` without an availability check. They produced ten error records because
some methods have platform/compile-unit subtests. This is an unsupported-tool
test invocation, not evidence that the shader rewrite is incorrect.

On `codex/zelda-independent-cross-review`, these six Metal compilation methods
now explicitly skip without xcrun, following neighboring shader tests. The
copied-body and compile-unit rewrite assertions were split into portable tests
and remain executed on Linux. All Metal assertions remain enabled when xcrun
is present; an installed but failing compiler is still an error. Nothing in
`dm/gfx/tools`, host code, profiles or the chain identifier changed in this
correction. No shader rebuild is required for it.

## Exact validation commands and results

Compatibility checkout: `/workspace/nxnative-cross-review`.

```sh
/workspace/venv/bin/python -W ignore::ResourceWarning -m unittest -v \
  dm/tools/tests/test_shader_compat.py \
  dm/tools/tests/test_shader_toolchain_cache.py \
  dm/tools/tests/test_shader_lib.py \
  dm/tools/tests/test_nsp_chain.py \
  dm/tools/tests/test_docs.py
```

**84 passed**, zero failures/errors/skips before the new report was added; rerun
after the documentation change before publication. Tests include the actual
portable C archive reader, truncated images and empty mappings. ResourceWarnings
from existing tests were filtered; no assertions or outcomes were suppressed.

```sh
DM_GAME=0400486024DEC000 /workspace/venv/bin/python \
  -W ignore::ResourceWarning -m unittest -v \
  dm/gfx/tests/test_dmsh_gather_offsets.py \
  dm/gfx/tests/test_dmsh_hmma.py \
  dm/gfx/tests/test_dmsh_border.py \
  dm/gfx/tests/test_dmsh_reflect.py \
  dm/gfx/tests/test_dmsh_fetch.py \
  dm/gfx/tests/test_dmsh_ampere_mem.py
```

Before the correction: **140 discovered, 10 error records, 78 skipped**, command
exit 1. All error records were `FileNotFoundError: 'xcrun'` in the six fetch
methods. This run is not reported as passing.

After correction: **142 discovered, 58 passed, 84 skipped**, zero failures/errors,
exit 0. Skips require Xcode/Metal, a configured native translator or a GPU test
executable. Portable passing tests check source rewrites/reflection, not real
compiled shader numerics or M2 register pressure. Added methods retain portable
copied-body and compile-unit assertions instead of skipping those checks.

Memory branch checkout: `/workspace/nxnative-render-review`, HEAD `df2c6e9f`:

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror dm/gfx/tests/t_mem_guard.c \
  -o /tmp/zelda-cross-memguard
/tmp/zelda-cross-memguard
/workspace/venv/bin/python -m unittest -v dm/gfx/tests/test_mem_guard_lifetime.py
/workspace/venv/bin/python -W ignore::ResourceWarning -m unittest -v \
  dm/tools/tests/test_docs.py
```

C compile and executable: **passed**, exit 0. Lifetime: **1 skipped**, explicitly
requires macOS Foundation/ARC. Documentation: **6 passed**. No Mac host build or
five-game regression was attempted on Linux. Original and reviewed worktrees
were kept clean except this review's isolated changes.

## Coordination, conflicts and readiness

Git reads and push access work. `gh pr list --repo emersonortiz195/nxnative
--state all --limit 50 --json number,title,headRefName,baseRefName,isDraft,url`
failed with `Post "https://api.github.com/graphql": Forbidden`. Public HTML
inspection found no matching PRs and no issue results. This is bounded discovery,
not proof no restricted or subsequently published artifacts exist. GitHub API
access is still needed to publish a draft PR or issue through gh; a pushed
engineering document is the coordination artifact for now.

No published Agent 2/3 proposal could be independently reviewed. Request their
exact commit, base revision, touched files, chain declaration and Mac evidence.
Do not silently label their work complete. Memory changes share `nvn_mtl.m` with
future renderer work and require joint fence/retirement review. Shader/cache
changes can overlap the compatibility branch's `dmsh_mtlcache.py` and cache tests.
The new fetch-test-only patch overlaps neither runtime memory nor renderer code.

Readiness decisions:

1. **Compatibility/preflight:** ready for controlled Mac tool and archive-load
   testing, not proof a new host can replace the installed one. Correctness and
   successful xcrun output still need actual Mac checks.
2. **Memory diagnostics alone:** conditional Mac testing only, separate from
   timing baselines; Foundation/ARC and Metal lifetimes unverified.
3. **Full-pool bypass:** not integration-ready; keep disabled until complete raw
   address coverage is demonstrated.
4. **Metal/shader optimizations from other tasks:** review pending publication.
5. **Combined candidate / merge:** not ready. No branches were merged and no
   installed app, game asset or shader archive was touched.

Expected effects are qualitative only: diagnostics add CPU work; unmapped pool
coverage can reduce accounting while breaking rendering; preflight catches a
class of deployment errors; compiler-provenance rejection avoids unsafe cache
acceptance. There is no measured RAM reduction or FPS improvement here.

The safe M2 sequence is matching-chain baseline first, host/unit tests and tiny
synthetic compiler/cache checks second, each host-only proposal separately third,
then approved shader variants in separate archives. Verify actual internal and
presented resolution, correct pictures/audio, frame p50/p95/p99 and late frames
against 33.3 ms, CPU submit/GPU waits, footprint, swap, thermal state and long-run
scene transitions. A minimum of three alternating baseline/candidate runs plus
sustained play is advisable. Follow the repository's impacted five-game checks
before a future runtime/chain integration. The existing
[compatibility procedure](zelda-compatibility-review.md) gives detailed steps.
