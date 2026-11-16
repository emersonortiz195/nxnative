# Archive-preserving reviewed subset for the dedicated integrator

Branch: `codex/zelda-chain39-reviewed`, based directly on
`04811a634b7f9344e882129b0973dd493369dd62`. This is a compatibility-scoped subset,
not a combined runtime optimization candidate. The dedicated integration task
still owns GPU/Metal runtime assembly. Nothing is merged into main or another
agent's branch; no installed game, asset, save, archive or cache is modified.

## Source compatibility evidence

The unchanged baseline computes `39eb2f781d07` using `dmsh_chain.version()`, and
its header declares that same value. The new `test_chain39_subset.py` compares
every listed chain-input file byte-for-byte with `04811a63`, tests the computed
default chain, and verifies the compiler-cache helper is outside that hash.
This is stronger than renaming a library or editing a header. No chain input,
ABI definition, translator, compiler lock or game profile was changed.

This does not prove that an arbitrary executable or the user's archive actually
matches the source: the original archive is not present here. Actual Mac host
build/loading, reflection checks and correct gameplay remain mandatory. The
`3ae08e02ec6a` Phase 3/4/5 sources are not declared compatible with the old
archive. They must not be substituted wholesale into this branch.

## Exact selected sources and conflicts

| Component | Source | Resolution |
|---|---|---|
| Historical matching source | `04811a63` | Genuine base, not a header-only downgrade |
| Hardened capture report and six tests | `109af09b` following `8906e6d8` | Script, test and original QA handoff copied without modification |
| Compile-miss coalescing and concurrency tests, PR #7 | `34b3ac8138dacf7a70566b55cc96c29fa31910e8` | Cache helper/test copied without changing output keys or format |
| Compiler-probe rejection inherited by that helper | Original Agent 4 compatibility work `27fbc92f` | Failed/empty probes rejected; successful identity unchanged |
| Source-integrity gate and this handoff | New subset implementation | Protects exact old chain sources; no runtime effect |

Only individual reviewed files were taken. Whole-branch cherry-picks would drag
newer ABI/tools and incompatible histories into the candidate. There was no
textual conflict requiring a guessed resolution. The original
[QA handoff](zelda-phase5-qa.md) describes its Phase 3 branch context; its references
to inherited `3ae08e02ec6a` are historical and do not describe this subset's base.

PR #7 review: a per-key process-local lock coalesces identical compile misses;
waiters recheck publication, unrelated keys/targets stay parallel, and the entry
is released on failure. No global cache/store lock is held while the compiler
runs. The concurrency tests use a synthetic compiler, deterministic initial
miss barriers, failure recovery and unwritable-cache controls. No real shaders
are compiled by those tests. Cache format, MSL bytes, target/flags identity and
compiler identity determine reuse exactly as before. This reduces redundant
build work when compilation is separately authorized; it is not a runtime FPS
or RAM optimization. This task did not execute compilation or prefill.

## Runtime changes withheld for review/native evidence

- PR #5 (`6cfb79ed`, completed upload staging release): requires proving slot
  completion and exclusive staging ownership against the older host's upload
  queues/allocator protocol. Source similarity is insufficient for early release.
- PR #6 (`3c219815`, direct fill-pattern initialization): removes temporary CPU
  storage, but its patch still overwrites the pattern after registering the old
  one without retiring that old pattern from residency. Retention already exists
  in the baseline; this optimization alone is not a repair. A follow-up must
  defer retirement behind the last GPU use and test changing values while an
  earlier copy is in flight. Do not remove residency immediately.
- PR #9 (`863e2ab1`, idle heap cap/eviction): previously reviewed pure metadata
  tests pass, but delayed completion, native callbacks, lock ordering and
  ownership must be validated in the actual old-source backport. It is not
  included in this subset merely because it bounds idle accounting.
- Phase 4 QA PR #8's lazy Mac sampler is useful but not a prerequisite for the
  standalone capture reducer. Avoid importing its full newer regression harness
  until its dependencies are reviewed against this source baseline.
- The unsafe full-pool bypass is not introduced or enabled. No shader rewrite,
  new-chain specialization, allocator-ring or visibility-ring adaptation is
  silently included. A separate runtime integration review is still required.

These are dependency gates, not claims that every withheld proposal is wrong.
The exposed pattern-retention path is a source observation; no leak amount or
M2 improvement is measured here.

## Portable validation

From this subset checkout, using the prepared Python environment:

```sh
python -W ignore::ResourceWarning -m unittest -v \
  dm/tools/tests/test_chain39_subset.py \
  dm/tools/tests/test_zelda_capture_report.py \
  dm/tools/tests/test_metal_cache_concurrency.py \
  dm/tools/tests/test_shader_toolchain_cache.py \
  dm/tools/tests/test_nsp_chain.py \
  dm/tools/tests/test_docs.py \
  dm/tools/tests/test_env_switches.py
```

The complete suite passes **68 tests**, with no failures/errors/skips, on both
Python 3.12.14 and Python 3.14.9. The latter uses an isolated environment with the
repository's pinned lint/dependency requirements. Existing ResourceWarnings are
filtered, not test failures. Changed-file Ruff and whitespace checks pass.
No Apple APIs, Xcode build or game was run. Test failures and exact final counts
are reported in the publication message; this source-only gate is not archive
or gameplay validation.

The older baseline also avoids the newer `dmsh_entry.py` F401 location because
that split module is not in this revision. This is not a lint suppression or
reason to downgrade unrelated work. Full lint results can still depend on the
pinned Python/tool versions; do not grow the baseline to hide findings.
The local Python 3.12 full ratchet reports zero new findings but exits 1 because
three previously missing backports imports are now resolved and remain in its
baseline. The baseline was not edited. With Python 3.14 and pinned tools, the
full ratchet **passes**: 336 baseline findings, zero new findings and zero stale
resolved entries. Command: `python dm/tools/lint_python.py --against 04811a63`
with the isolated Python 3.14 environment first on PATH. This is local Linux
evidence, not a claim that a remote CI workflow or Mac build has completed.

## Handoff and safe Mac gates

The dedicated integrator can use this separately published branch as a verified
source-chain starting point or take its individual QA/cache files. Overlap is
limited to `dmsh_mtlcache.py`, cache concurrency tests, capture script/tests and
handoff documents. Coordinate any Agent 3 cache edits before combining them.
Do not merge this old-base branch into main: doing so would reverse unrelated
newer changes. Its draft PR should target a published `04811a63` baseline ref,
not imply that a whole-tree downgrade of main is approved.

1. Inspect the actual archive and delivered profile/map read-only. Verify game,
   chain, library provenance and required shader coverage before launch.
2. Build only an isolated host from the reviewed old source; inspect Makefile
   prerequisites first. Do not invoke an all-in-one build or shader rebuild.
3. Confirm native archive loading and correct rendering/audio on the M2, not
   just an FPS counter. Verify actual internal and presented resolution.
4. Backport each runtime fix independently with slow-GPU completion, slot reuse,
   lifetime and lock-order tests. Repeat appropriate five-game regressions only
   with owned, already-compatible archives; stop if rebuilding would be required.
5. Only then prepare the dedicated combined candidate for controlled repeated
   20-minute scene-transition runs, recording frame tails, GPU/CPU stalls,
   footprint, pressure/swap and thermal behavior. The sanitized capture reducer
   leaves those missing measurements explicitly unknown.

No Mac compatibility, GPU correctness, FPS gain, memory reduction or complete
Phase 5 integration is asserted by publishing this subset.
