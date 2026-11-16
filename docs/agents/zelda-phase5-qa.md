# Phase 5 Agent 4: isolated QA and integration gates

Branch `codex/zelda-phase5-qa`, based on Phase 3 `17020e54`. No runtime
proposal has been integrated. All local verification is Linux-only; no Metal,
Mac or gameplay result is claimed. This report supersedes the earlier blocked
environment status: shell commands and Git fetch now work.

## First implementation

`scripts/zelda_capture_report.py` reads an existing host frame TSV and emits
whitelisted numeric JSON aggregates. It never starts a game, samples another
process, compiles shaders, or writes its input. Unknown log lines and columns
are not reproduced. Error text does not include the input path or raw data.

It reports nearest-rank p50/p95/p99/max and sample counts for frame, presented,
GPU, submit, sync and work time; over-budget frames use 1000/30 ms by default.
Dropped presentation (-1) is counted separately; missing GPU samples remain
unknown rather than zero. Delayed GPU rows are joined by frame ID. Conflicting
timestamps and nonmonotonic/reset captures are rejected. Sparse frame IDs suppress
the observed frame-rate estimate rather than treating sparse telemetry as FPS.
The 1200-second flag checks timestamp span only, not uninterrupted healthy play.

Read-only invocation (the input remains local):

```sh
python3 scripts/zelda_capture_report.py <private-capture.tsv> > <sanitized-summary.json>
```

Review the aggregate JSON before sharing. Do not publish the original TSV, host
logs, screenshots, paths, device identifiers, saves, assets or crash reports.
Timing output cannot establish correct rendering: a black screen's frame counter
is not evidence of gameplay. Footprint, swap, residency, staging churn, thermals,
audio, visuals, termination cause and internal resolution are explicitly listed
as unmeasured, not guessed from timings.

## Independent PR #9 review

Observed [PR #9](https://github.com/emersonortiz195/nxnative/pull/9): draft,
head `863e2ab1d2915b5ba36a47ebe237403b2c41cc22` on
`codex/zelda-phase5-gpu`, base `17020e54`. Reviewed its runtime diff, pure heap
policy, tests and review follow-up. This is an idle placement-heap cap/eviction
and diagnostic snapshot proposal, not the retired-texture or upload changes
requested for the next agents.

- Cache admission plans at most 64 evictions before mutating entries. Failed
  planning leaves the cache untouched and returns no dropped ownership.
- Oldest entries use timestamp/index ordering; descending index removal keeps
  swap-removal from accidentally selecting an unplanned entry.
- `rh_wait` and `rh_trim` remove residency and release evicted objects after
  unlocking the recycle mutex. Do not move driver removals into that mutex.
- The weak residency table is snapshotted under its lock, then allocatedSize is
  queried outside it. Retained snapshots bound ownership to the diagnostic call.
  The new Foundation reentry test still needs Mac execution.
- The unlocked `g_rh_n` shortcut in trim was removed. Tests cover rejection
  transactionality, exact work limits, timestamp ties, reuse and concurrent
  metadata operations. This does not prove that real textures return only after
  GPU completion or that driver callbacks obey the assumed lifetime boundary.
- Planning cost is O(64 times idle-entry-count) in the worst allowed case;
  callback latency, transient dropped-but-still-resident heaps and allocation
  churn need measurement. The 256 MiB cap is idle cache accounting, not a bound
  on total live Metal allocations or process footprint.

No new confirmed defect was found in this pure metadata policy. This is limited
source review plus portable tests, not approval of native ownership or lock-order
safety. Native delayed-completion, ARC reentry, forced-timeout and five-game
regressions remain gates. Public CI inspection and GitHub API access can be
incomplete; `gh pr list` still returns proxy 403. Do not infer green CI from
local passing tests.

The public [PR #9 checks page](https://github.com/emersonortiz195/nxnative/pull/9/checks)
reports host tests, sanitizers, coverage, tool tests, build check and synthetic
unsigned iOS jobs succeeded; Python and C lint jobs failed. These are observed
remote statuses, not tests executed on this Linux host. Both lint failures remain
integration blockers pending exact log review; this report does not invent their
causes from earlier runs.

Published Phase 5 source discovery found the community/assignments branch and
PR #9's GPU branch. Separate Phase 5 submission-safety and upload/alias proposals
were not identifiable yet. Review their exact heads when published, including
the named upstream commit provenance. Do not assume adaptations already exist
or cherry-pick unreviewed upstream code. Expected overlaps are `nvn_mtl.m`,
submission retirement, upload slots and texture ownership; this QA patch touches
none of them and is not a combined candidate.

## Shader-chain blocker

Phase 3 and both observed Phase 5 branches declare `3ae08e02ec6a`, while the user
requires preserving the installed `39eb2f781d07` archive. No chain file is changed
by this QA patch, and neither archive is rebuilt, relabeled or replaced. The
existing mismatch must be resolved by a reviewed host-source compatibility plan
before calling any of these branches suitable for the installed archive.
Do not combine proposals into an integration candidate merely because their
portable tests pass. A compatible isolated host and preserved matching archive
must exist first; no original application is modified.

## Validation

On this QA branch:

```sh
python -m unittest -v dm/tools/tests/test_zelda_capture_report.py
python -W ignore::ResourceWarning -m unittest -v \
  dm/tools/tests/test_zelda_capture_report.py dm/tools/tests/test_shader_compat.py \
  dm/tools/tests/test_nsp_chain.py dm/tools/tests/test_docs.py
```

Four new regression methods pass, covering delayed rows, percentiles, drop
counts, sparse/single-frame duration handling, nonfinite values, resets/conflicts,
CLI sanitization and input preservation. The combined suite has **42 passed**,
no failures/errors/skips, and is rerun after documentation edits. Changed-file
Ruff and whitespace checks must pass before push.

In a separate detached checkout of PR #9 head, without combining its sources:

```sh
python -W ignore::ResourceWarning -m unittest -v \
  dm/gfx/tests/test_heap_cache.py dm/tools/tests/test_docs.py \
  dm/tools/tests/test_nsp_chain.py dm/tools/tests/test_gfx_tests_makefile.py \
  dm/tools/tests/test_shader_compat.py dm/tools/tests/test_env_switches.py
```

**47 passed, no failures/errors/skips.** This includes a GCC pthread metadata
stress test, rejection-only negative control, and process-timeout cleanup test.
An initial invocation accidentally ran in the original main checkout and failed
on missing heap tests and its stale switch catalog; it is not a PR #9 result.
It was corrected to the exact detached review checkout and rerun successfully.
No native Mac tests ran; absence of skips in this selected portable suite does
not imply Metal coverage. Existing ResourceWarnings were filtered.

## Controlled 20-minute Mac protocol (not run)

1. Resolve host/archive chain compatibility and review Agents 1-3 exact source
   heads before preparing a separately named integration branch. Keep all risky
   game-specific options off unless that individual experiment is approved.
2. Run native ownership, residency reentry, submission-ring wraparound,
   visibility-buffer retirement, archive serialization, upload-alias and GPU
   timeout regression tests appropriate to the published changes. Include slow
   completion and concurrent submission/diagnostic cases. No shader rebuild.
3. Use an isolated candidate app/host, copied test save state and the same route
   on the real 8 GB M2 Air. Do not replace the installed app. Verify actual
   internal/presented resolution and correct visuals/audio before timing.
4. Collect frame TSV locally with the host's supported telemetry. Use at least
   20 minutes with fixed scene transitions, camera movement, menus and focus
   changes. Record baseline and one changed candidate alternately, repeated at
   least three times, with identical warm-up and thermal conditions.
5. Keep separate local samples for process current/peak footprint, OS memory
   pressure/swap, current live/logical Metal allocations, idle capacity, deferred
   retirement backlog, upload staging and residency commit time. Do not add
   logical overlapping buffers to process footprint, equate cumulative allocation
   counters with live bytes, or treat archive disk size as resident memory.
6. Reduce TSV offline with this tool. Correlate long frames and submit/present
   stalls with GPU completion and local memory samples; submit time alone is
   not GPU completion time. Missing telemetry stays unknown. Report thermal
   throttling and input/visual problems alongside p50/p95/p99 and budget misses.
7. Classify clean exits, application crashes, command-buffer errors, watchdog
   termination and SIGKILL separately. A SIGKILL alone does not prove OS OOM;
   inspect local OS evidence without publishing private logs. Stop on black
   screens, missing shaders, faults, corruption or uncontrolled memory growth.

Current readiness: QA tooling is available for read-only capture reduction;
runtime integration and M2 acceptance are blocked on chain compatibility,
unpublished source changes and actual native testing. No FPS, memory or stability
gain has been measured.

## November 16 follow-up for the dedicated integration agent

Integration is now owned by a separate task. This branch continues QA only and
does not move or combine any runtime branch. Its original dependency remains
Phase 3 `17020e54`; the capture-tool commit is `8906e6d8`. The follow-up touches
only `scripts/zelda_capture_report.py`, `dm/tools/tests/test_zelda_capture_report.py`
and this report. No overlap with `nvn_mtl.m`, allocator rings, upload slots,
texture aliases, shader rewrites or chain files is introduced.

Two own-code defects were fixed:

- Argument parsing previously echoed rejected command-line values before the
  sanitized runtime exception handler ran. A private path supplied as an extra
  argument or malformed budget could therefore appear in stderr. A fixed-name
  parser now emits generic argument errors without raw argv; normal `--help`
  still works. Regression cases cover unknown flags, malformed budget, missing
  capture and extra positional arguments.
- Two finite timestamps separated by a subnormal interval could produce an
  infinite observed rate. JSON serialization then failed outside the sanitized
  error handler and printed a traceback. The reducer now rejects a nonfinite
  computed rate before serialization. Both function-level and CLI checks verify
  a generic exit-2 failure with no raw path or traceback.

These are telemetry correctness/privacy fixes, with no runtime performance
effect or new shader-chain dependency. The four earlier test methods plus two
new ones pass (**6 total**). The combined command above now passes **44 tests**,
with no errors/failures/skips. Changed-file Ruff and whitespace checks pass.
Earlier PR #9 test/CI observations above are point-in-time evidence, not freshly
rerun native results. The published branches were fetched for discovery; the
dedicated integrator must review any new heads before selecting patches.

### Upstream evidence corrections

Reviewed the retrieved public issue bodies and discussion text, without copying
private attachments or raw logs into this repository:

- [Issue #2319](https://github.com/seedds/nxnative/issues/2319) is currently about
  file-backed guest memory plus LRU eviction on an 8 GB M2 Air, for Fire Emblem
  Fortune's Weave on another shader chain. It reports freezes/resets despite
  lower footprint and hypothesizes page-in/locking interactions. The hypothesis
  is not a verified root cause. This is not the border-register-pressure issue
  named in the assignment; do not attribute a border shader fix to it.
- [Issue #2321](https://github.com/seedds/nxnative/issues/2321) concerns intermittent
  Breath of the Wild GPU hangs and access revocation on an M4, on another source
  revision/chain. A prior longer run succeeded, so a short successful run is weak
  evidence against intermittent resource/synchronization problems. It is not
  direct evidence of an 8 GB M2 Ocarina defect or a validated remedy.
- [Discussion #1789](https://github.com/seedds/nxnative/discussions/1789) describes
  Ocarina's NDSR output cost remaining at its output resolution while internal
  resolution changes, and reports matrix/gather work requiring shader rebuilds.
  Some measurements are from M4/iPad hardware, not this target. It also records
  experiments with reduced threadgroup memory and pass/queue changes that did
  not help, and known GPU hangs/area-transition problems. These findings support
  measuring stage costs and output resolution, not assuming all 720p modes or
  newer-chip wins transfer to the M2. Do not rebuild or relabel the user's archive
  to import those results under the current constraints.

Handoff recommendation: take the QA fixes independently of runtime proposals;
preserve unknown telemetry fields as unknown; verify native queue retirement and
file-backed page-in behavior separately from accounting improvements. A lower
memory number alone must not pass stability review. The `39eb2f781d07` versus
`3ae08e02ec6a` compatibility blocker remains unresolved by these QA-only changes.
