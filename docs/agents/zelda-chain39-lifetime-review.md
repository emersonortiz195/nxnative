# Chain-39 lifetime and dependency review

Branch `codex/zelda-chain39-lifetime-review` starts at
`ff236c5a17da216386cb453e8f49f789f49485de` on
`codex/zelda-chain39-reviewed`.
This review adds tests, targeted CI source fetches and this document only. No runtime proposal is integrated.
No main merge, shader rebuild, installed application change, or access to game
assets, saves, archives or caches occurred. Tests use repository source and
temporary synthetic C programs on Linux, not Metal or M2 gameplay.

## Baseline and QA handoff

Reviewed `ff236c5a` and [its handoff](zelda-chain39-reviewed-subset.md).
The three files selected from `109af09b` remain unchanged: capture reducer,
capture tests, and [original QA report](zelda-phase5-qa.md). The cache coalescing
selection from `34b3ac81` remains outside the chain hash. This review neither
expands those dependencies nor changes their behavior.

`test_chain39_subset.py` still verifies the computed default `39eb2f781d07`,
the matching header and every hashed input byte-for-byte against
`04811a634b7f9344e882129b0973dd493369dd62`. There is no evidence that a
`3ae08e02ec6a` executable can load the existing archive; preserve the actual
old-source baseline instead of relabeling the newer host. Source equality is
necessary compatibility evidence, not proof of actual Mac archive loading.

## Pinned independent runtime reviews

| Proposal | Exact inspected source | Source-level decision |
|---|---|---|
| PR #5 upload staging | `6cfb79edb0127027323df9ec7e53fd5e57e4d9c6` | Protocol matches chain-39; conditionally eligible for an isolated backport with native completion tests |
| PR #6 fill pattern | `3c2198152292f64cbedf06701c84b6381d4e8285` | Old-pattern retirement acceptance gate fails; do not treat CPU allocation removal as a lifetime repair |
| PR #9 heap policy | `863e2ab1d2915b5ba36a47ebe237403b2c41cc22` | Pure metadata policy passes exhaustive small-state checks; ownership paths differ from chain-39, so no wholesale backport approval |

These are fixed-revision conclusions. Review a new head separately; branch names
and a passing old test do not validate subsequent changes.

### PR #5: upload ownership and completion ordering

The new source tests compare the actual functions in the pinned proposal with
`04811a63`. After removing comments/whitespace, `up_begin` and `up_flush` are
identical. In `up_alloc`, the sole executable text change is
`defer_obj_release(*sb)` to `res_remove(*sb)`. This is concrete dependency
evidence rather than an assumption that both branches happen to have three slots.
The normalization is a source audit of these manually reviewed functions, not
a general C semantic-equivalence proof.

Reviewed chain-39 flow:

1. `up_begin` publishes pending work before waiting on the chosen slot's busy
   flag, then claims the slot and resets its allocator.
2. The upload feedback handler removes temporary staging residency, clears its
   staging/views arrays and commits that residency change before clearing the
   busy flag. The publication/wait ordering tests pin these relationships.
3. A retained primary block can grow only in the first-block branch, when there
   is no current batch block. Mid-batch switched blocks follow the existing keep
   list; this proposal does not free them immediately.
4. The allocator's sole call site is the GPU texture upload path. It writes
   staging with `g_up_ce`, records buffer-to-texture copies with `up_blit_add`,
   and returns the destination texture. Rendering uses that destination, not a
   public handle to primary staging. Retained staging is excluded from the
   temporary staging array released by the feedback handler.

Consequently PR #5's assumption appears consistent with the pinned old source.
An isolated chain-39 port can be prepared for native testing without a shader
ABI change, but that is not an endorsement to replace the installed host.
Actual Metal completion delivery, captured ARC references, same-queue ordering
and early error/recovery paths are not proven by source-string tests.
`res_remove` updates the pending residency set; physical allocation disappearance
can await a residency commit or driver cleanup. Do not promise an immediate or
fixed MiB saving from removing an entry from the host's tracking table.

Required Mac gate: port/run `t_upload_slots` with pending GPU work held behind
an event; reuse the slot, grow the primary block and verify the event completed,
the old primary is not put behind an unrelated rendering fence, and all copied
edge bytes remain valid. Exercise retained and non-reuse modes, oversized uploads,
burst splitting, lost-upload recovery and concurrent diagnostics. Check the
old host's test/build dependencies before taking the newer test file wholesale.

### PR #6: previous fill patterns remain a blocker

Both the old chain-39 implementation and PR #6 register each newly selected
pattern with residency. The static `pat` reference is overwritten when the
32-bit value changes, but the replacement branch has no deferred retirement of
the previous pattern. PR #6 avoids a temporary CPU copy; it does not close that
retention path. No measured leak rate or retained-MiB estimate is inferred.

The new retirement acceptance test is deliberately an **expected failure** on
the pinned PR #6 source. It must not be advertised as a passed/fixed lifetime
check. It checks the missing deferred retirement call, not actual ARC behavior.
Equal values should continue to reuse one pattern; changing values must keep
the previous pattern immutable and resident while any encoded copy can read it.

A later repair should allocate/initialize successfully before replacing the
current pattern, queue the old one behind its last possible submission use,
and use the existing retirement API rather than immediate `res_remove` while
commands are in flight. Required native cases: multiple values in one open
submission, GPU completion held behind an event, repeated equal values, partial
final chunks, allocation failure, and residency/weak-reference checks after
completion. This review does not add that runtime repair or bypass its gate.

### PR #9: metadata safety is not heap ownership safety

The new test compiles the exact pinned `nvn_heap_cache.h` and compares it with
an independent reference selector. For 0 through 6 entries it enumerates all
timestamp assignments from three values, all eviction limits, varying initial
headroom and every incoming size through capacity plus one. It checks oldest
selection with index tie-breaking, exact byte/count accounting, unique/disjoint
dropped and retained identities, and byte-for-byte rollback on rejection.
That test passes. It contains no driver resource or GPU work.

The ownership difference is explicit: chain-39 `NvImageHeap::dealloc` calls
`res_remove(heap)`; PR #9's newer source calls `rh_wait(heap)`. Chain-39 also
returns recycled target heaps through `NvRecycledHeap::dealloc`, whereas the
newer source shares a broader recycle path. A straight patch transplant can
change which resources remain resident, the callback timing and the cache's
population. Do not treat the helper test as proof those changes are safe.

Any old-source port must preserve the existing owner categories or separately
justify expanding them. Keep residency removal and final releases outside the
recycle mutex; review lock ordering with `g_res_mu` and deferred retirement.
Prove that every admitted heap has no live/in-flight texture, that trimming and
completion returns cannot duplicate identities, and that work-budget rejection
does not strand transferred ownership. Idle-cap metadata is not total footprint;
pending evicted allocations and live resources can exceed it. Native tests must
exercise delayed completion, timestamp ties, mixed heap sizes, concurrent
returns/takes/trims, diagnostics reentry and GPU timeout cleanup.

## Exact portable checks

Fetch the reviewed branches before these tests in a shallow checkout; they read
fixed Git source objects, not files from an installed game. Missing objects are
explicit skips with a fetch message. A skipped review is not validation.

```sh
python -m unittest -v dm/tools/tests/test_chain39_lifetime_review.py
```

Initial result: **5 discovered, 4 passed, 1 expected failure**, no unexpected
failures/errors/skips. The expected failure is the unresolved PR #6 retirement
gate. The PR #9 test compiles a synthetic executable using the actual header;
the source comparison tests inspect actual Git objects. No native Metal code
is compiled by this suite.

```sh
python -W ignore::ResourceWarning -m unittest -v \
  dm/tools/tests/test_chain39_subset.py \
  dm/tools/tests/test_chain39_lifetime_review.py \
  dm/tools/tests/test_zelda_capture_report.py \
  dm/tools/tests/test_metal_cache_concurrency.py \
  dm/tools/tests/test_shader_toolchain_cache.py \
  dm/tools/tests/test_nsp_chain.py dm/tools/tests/test_docs.py \
  dm/tools/tests/test_env_switches.py
```

Under the pinned Python 3.14 environment this discovers **74 tests: 73 passed,
one expected failure**, with no unexpected failures/errors/skips. Do not interpret
the known expected failure as a clean retirement acceptance gate. Changed-file
Ruff and `git diff --check` pass. Full Python ratchet uses
`python dm/tools/lint_python.py --against 04811a63`; matching tool/runtime versions
matter, as the previous handoff documents. It passes: 336 baseline findings,
zero new findings and zero stale resolved entries. No baseline growth or lint suppression.

The coverage and tool-test jobs now explicitly fetch only the four pinned review
commits at depth 1 before testing. This supplies source objects in shallow CI
checkouts without switching the checked-out tree, changing the archive or taking
runtime dependencies from those objects. Native steps, timeouts and action pins
remain unchanged. This is CI preparation, not evidence of remote workflow success.
A regression check ties both workflow fetch lists to the pinned review sources
so a changed source pin cannot silently leave the CI preparation stale.
The exact targeted fetch command also succeeded in an independent temporary bare
repository. It did not alter the shared checkout's shallow/history metadata.
The final new Python test file passes standalone Pyright as well as Ruff.

## Candidate readiness

The QA/cache baseline remains a useful verified source-chain starting point.
A **limited upload-only runtime backport** is now justified for preparation and
controlled native testing based on the source dependency review, not for release
or a claim of safety under the driver. A combined chain-39 runtime candidate is
not yet reviewed: fill-pattern retirement remains unresolved and heap ownership
needs an old-source-specific port. Do not silently include allocator/visibility
or shader changes from newer-chain branches while solving these three proposals.

The dedicated integration agent should select exact commits, build only an
isolated matching-chain host after inspecting prerequisites, verify actual archive
loading and correct visuals/audio, and run native gates before a repeated
20-minute M2 test. Preserve the installed app and archives. No FPS improvement,
memory reduction or Mac correctness is established here.
