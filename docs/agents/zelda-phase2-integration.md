# Phase 2 integration: PR #1 and archive preflight

Agent 4, November 12, 2026. Linux-only review; no Apple hardware, Metal
compilation, installed game or original shader archive was available here.
Target remains correctly rendered Ocarina of Time at approximately 720p/30 FPS
on an M2 MacBook Air with 8 GB unified memory. No FPS or RAM improvement is
claimed.

## PR #1: draft state, not a demonstrated merge conflict

Reviewed [PR #1](https://github.com/emersonortiz195/nxnative/pull/1),
"Draft: independent Zelda cross-review and portable shader test fixes".
The public page's embedded pull-request metadata records:

| Field | Observed value |
|---|---|
| State | `DRAFT` |
| Base | `main`, `084f5aa5c59bbfbebfcab7ad1b1a3b9bc196a582` |
| Head | `codex/zelda-independent-cross-review`, `9fe4ab09fa501030926371478b88274413fd432e` |
| GitHub test-merge ref | `bab11800bda49078e900e6086ee2da3335d1fec5` |

The fetched `refs/pull/1/merge` has exactly those base/head parents. Both its tree
and the PR head's tree are `f6a15fe145f711569419758db461a0cd53c5420f`.
`git merge-base --is-ancestor origin/main origin/pr-1-head` exits 0. Therefore
there is no content conflict at these exact revisions. No local merge was run.
The `refs/pull/1/merge` object was created by GitHub; fetching it does not merge
the PR or modify main.

A draft PR cannot be merged until marked ready for review. This is the confirmed
state blocker, not evidence that files need conflict resolution. Do not rebase,
force-push, delete branches or change the PR's draft state to "repair" a conflict
that is not present. Marking ready later would not satisfy all testing or branch
protection requirements by itself.

The public [checks page](https://github.com/emersonortiz195/nxnative/pull/1/checks)
was also inspected. At observation time:

- Python lint ratchet: queued.
- Host tests, sanitizers, coverage, tool tests and Mac/iOS build check: in progress.
- Synthetic unsigned iOS app and area-label job: succeeded according to the page.

These are remote status observations, not Mac tests executed or independently
validated here. No complete CI pass is established. Hidden branch-protection or
approval requirements remain unknown. GraphQL requests through `gh pr view`
still fail with `Post "https://api.github.com/graphql": Forbidden`; API-only
merge-state details could not be retrieved. Old reports saying no PR was visible
describe their earlier observations and are superseded by this PR #1 review.

## Published contributions and dependencies

Fetched main and re-enumerated remote branches twice during this review. Existing
memory experiments remain at `df2c6e9f`; the large-pool experiment and its backup
remain at `02353ca3`; compatibility remains at `27fbc92f`; independent cross-review
remains at `9fe4ab09`; main remains at `084f5aa5`. No separately identifiable new
Agent 1/2/3 phase-2 branch was visible at these observations. This is not a claim
that their tasks are idle or that uncommitted work does not exist.

PR #1 includes two commits, `27fbc92f` and `9fe4ab09`: compatibility preflight,
fail-closed compiler probes, portable reader/test corrections and reports. It
does not contain a new GPU memory or rendering optimization. Attribution to
Agent 4 is supported by this task's history; author/branch names alone do not
identify owners of the memory experiments.

Prior independent source review remains applicable at the unchanged heads:

- `6796288d` adds opt-in memory diagnostics and lifetime/policy tests, not OOM
  prevention or memory reclamation. Snapshot scanning under `g_res_mu`, a sysctl
  inside that critical section and a 100 ms timer can perturb performance.
- `df2c6e9f` fixes weak ownership in the test harness; Mac O0/O2 negative controls
  and actual Metal lifetimes remain unverified here.
- `02353ca3` can suppress required raw-address mappings when
  `DM_M2_NO_FULL_POOL` is enabled. Keep it disabled. No coverage-preserving
  replacement has been published for this integration review yet.
- The memory branch predates main's host-stack logging and graphics-scale
  changes. Comparing whole executables from these branches without controlling
  the base revision confounds both correctness and performance.

Agent 3's new shader work is pending publication/review. Request its exact head,
base revision, chain/rebuild declaration, compiler identity and tests when
available. No shader-code conclusions are attributed to unpublished work.
Potential overlap: Agent 3 may change `dmsh_mtlcache.py` and cache tests from
PR #1. This phase-2 patch touches only `dm/tools/shader_compat.py`, its tests and
this document, avoiding shader translation, cache implementation, residency and
rendering files. Agent 3 should preserve the compiler failure checks and successful
identity stability if it later edits that cache.

## Implemented improvement: opt-in map and uniform-table checks

The existing metadata-only preflight deliberately did not prove map completeness.
A directory containing one valid base shader could pass even if most shaders
needed by a given map were missing. A partial build must not be mistaken for a
game-complete shader set merely because all present files have the right chain.

Added `--shader-map <TSV>`:

- Reads the control-section key in column 4, as the host does; ignores the map's
  header/comments, deduplicates keys and checks presence of every required base
  reflection. Existing audit logic checks that present reflections have a matching
  chain and a nonempty base metallib, except folded geometry stubs.
- Rejects malformed/empty maps rather than silently checking zero keys.
- Reports `required_keys`, combines map keys with repeated `--key`, and exits 1
  for missing required base reflections. Invalid map syntax exits 2.
- Coverage is relative to the supplied map. Known partial maps or intentionally
  unbuilt/unused shaders can fail this strict opt-in check; that is useful evidence
  of incompleteness, not necessarily proof that a specific route cannot run.

Added `--tables-dir <directory>`:

- Reads only the first lines of `c1_full.tsv` and `cb_extent.tsv` beside the
  runtime map and compares the exact `shmap_read` prefix, including the trailing
  space after the inputs stamp. A prefix collision such as `stamp2` does not
  count as `stamp`.
- Reports `accepted`, `stale` or `missing`, plus warnings when the host would use
  conservative uniform-block fallbacks. These fallbacks are valid host behavior,
  so warnings alone do not cause a shader-compatibility failure.
- Diagnoses an existing performance-relevant condition; it does not regenerate
  tables or claim a measured cost reduction.

Example read-only inspection, using the actual old chain and its matching map:

```sh
python3 dm/tools/shader_compat.py /path/to/cache/b-39eb2f781d07.img \
  --chain 39eb2f781d07 --game 0400486024DEC000 \
  --shader-map /path/to/matching-profile/shader_map.tsv \
  --tables-dir /path/to/matching-profile
```

Use the profile/map actually delivered with that archive, not an unrelated newer
checkout's map. Even a clean report does not test side-entry libraries, Metal
loadability, full reflection ABI semantics, numerical correctness or gameplay.
It cannot determine a binary's provenance from an arbitrary source header.

No shader-chain identifier or rebuild is required: only an agent-facing read-only
tool changed. Computed chain remains `3ae08e02ec6a` in this checkout. Do not
replace the installed host: the original `39eb2f781d07` archive still requires a
verified compatible host. No assets, archive bytes, source shaders or runtime
allocation policy were modified.

## Tests run in this phase

Worktree `/workspace/nxnative-phase2-integration`, branch
`codex/zelda-phase2-integration`, based on PR #1 head. Five new regression methods
cover map column selection/deduplication/missing keys, empty/malformed maps,
literal uniform-header matches and mismatches, fallback warnings, and CLI exits.

```sh
/workspace/venv/bin/python -m unittest -v dm/tools/tests/test_shader_compat.py
```

**15 passed**, no failures/errors/skips.

```sh
/workspace/venv/bin/python -W ignore::ResourceWarning -m unittest -v \
  dm/tools/tests/test_shader_compat.py \
  dm/tools/tests/test_shader_toolchain_cache.py \
  dm/tools/tests/test_shader_lib.py \
  dm/tools/tests/test_nsp_chain.py \
  dm/tools/tests/test_docs.py
```

**89 passed**, no failures/errors/skips. Existing injected full-disk failure
tests still pass; ResourceWarnings from existing tests were filtered, not test
failures. The separate 15-test command is included in these 89, not additive.

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

**142 discovered: 58 passed, 84 skipped**, no errors/failures. Skips require
Xcode/Metal, native GPU test tools or a configured translator. These tests
validate portable rewrite/reflection behavior, not compiled GPU correctness.

Changed-file Ruff, `git diff --check`, and `dmsh_chain.py` are run before
publication. No macOS, Metal, Xcode or gameplay pass is claimed. The memory
experiment's ARC/Metal gates are not replaced by these portable checks.

## Integration readiness and M2 gates

PR #1 has no content conflict at the recorded head/base, but remains a draft
with incomplete observed CI. It is not a validated game executable replacement.
This extension is ready for controlled read-only Mac archive inspection, not
evidence that 720p/30 is achievable on 8 GB.

Remaining gates:

1. Finish/review PR #1 CI; distinguish actual failures from queued/running jobs
   and branch-protection requirements. Do not merge or mark ready automatically.
2. Have Agent 3 review the preflight map/chain assumptions and publish any cache
   or shader changes with explicit ABI/rebuild requirements. Reuse requires exact
   source, flags, compiler and target provenance, not relabeled old JSON.
3. Run read-only preflight against the real original archive and delivered map;
   preserve both. Resolve missing shader evidence before performance testing.
4. On the M2, validate actual matching-chain host/library loading and correct
   pictures/audio. Compile only isolated synthetic tests or host prerequisites
   when authorized; no full shader rebuild is implied by this report.
5. Run ARC lifetime O0/O2 negative controls and Metal allocation/submission tests
   before approving Agent 1's changes. Keep the unsafe full-pool bypass off.
6. Verify internal and presented resolution; compare controlled baseline/candidate
   runs at 30 FPS with frame p50/p95/p99, late frames relative to 33.3 ms, GPU/CPU
   waits, footprint, swap, memory pressure and sustained thermal behavior. Repeat
   scene transitions, menus and focus loss/return; test asynchronous captures.

Expected benefit here is earlier, more specific deployment diagnosis. No runtime
FPS or memory savings are estimated. Combined runtime optimization readiness
remains blocked by unpublished proposals, actual archive inspection, Mac/Metal
validation and real M2 measurements.
