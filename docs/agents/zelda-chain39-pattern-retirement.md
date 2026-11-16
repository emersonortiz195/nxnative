# Independent chain-39 fill-pattern retirement candidate

Branch `codex/zelda-chain39-pattern-retirement`, based on the reviewed lifetime
branch `26eed50b`. This is a pattern-only runtime candidate. It does not include
the separate upload-staging release change or any heap eviction change. No main
merge, shader rebuild, installed application change or archive/cache modification
has occurred. Linux tests do not establish native Metal or M2 gameplay correctness.

## Fix and lifetime reasoning

The old `mtl_sub_fill` pattern cache registered a new 64 KiB buffer every time
its 32-bit pattern changed, but replacing the static strong `pat` reference did
not remove the previous residency registration. PR #6's direct initialization
optimization alone did not repair that retention. The pinned PR #6 source
remains a passing missing-retirement negative control in the review suite.

The implementation now:

1. Allocates a new shared pattern buffer and verifies allocation succeeded.
2. Writes all pattern words in the new buffer and registers it.
3. Calls the existing `defer_obj_release(pat)` before assigning `pat = next`.
4. Updates the cached value only after replacement succeeds. Equal values reuse
   the existing buffer and produce no additional retirement entry.

Every caller found is a submission encoding path: OP_CLEAR_BUF replay or a
compute dispatch's generated first stores. Earlier copies can still read the
old immutable pattern in the same submission. The existing retirement helper
queues it at `g_fence + 1`, as other submission-owned replacement buffers do;
there is no immediate residency removal while those copies are in flight.
The cache's remaining current pattern is deliberately retained for reuse.

An allocation failure reaches the existing fatal-error mechanism before changing
the cache or retirement queue. No attempt is made to recover from host allocation
failure; the test's recoverable model only verifies ordering of side effects.
The replacement is initialized in shared storage, so no extra 64 KiB temporary
CPU allocation/copy is needed. This is source reasoning, not a measured memory
or frame-rate improvement.

The normal retirement system owns actual deferred removal: this patch introduces
no new mutex or callback. Deferred object lifetime, queue completion and residency
commits remain governed by the existing host. Physical driver memory may disappear
later than host tracking removal; no fixed footprint reduction is promised.

## Tests

`test_pattern_retirement.py` executes the actual production initialization and
`defer_obj_release` fence body after substituting only Metal allocation syntax
with a C model. It checks multiple values in one outstanding submission, unchanged
value reuse, immutable earlier contents, delayed completion, later-fence rollover,
and failure before retirement/cache mutation. A no-retirement mutation fails.
The known-failing control has core dumps disabled and does not sleep on the GPU.

The new current-source retirement gate passes. The historical pinned PR #6 gate
now explicitly asserts missing retirement as a passing negative control; it is not
relabeled as a fixed proposal. The upload-only branch retains its original expected
failure because it does not contain this pattern repair.

The native `t_copy_alias` extension records multiple nontrivial patterns, including
an equal repeated value and a partial final 64 KiB chunk, while GPU completion is
held behind a shared event. It checks old residency before the fence, valid
destination/tail bytes after completion, and removal of old tracked residency.
The native weak-table classifier selects deferred 64 KiB buffers and could also
include an unrelated deferred allocation of that size; the production model gives
the specific pattern negative control. The existing `check_t_copy_alias` runs
direct and deferred encoding. This native
extension was not compiled or executed on Linux.

Portable command:

```sh
python -W ignore::ResourceWarning -m unittest -v \
  dm/tools/tests/test_pattern_retirement.py \
  dm/tools/tests/test_chain39_subset.py \
  dm/tools/tests/test_chain39_lifetime_review.py \
  dm/tools/tests/test_zelda_capture_report.py \
  dm/tools/tests/test_metal_cache_concurrency.py \
  dm/tools/tests/test_shader_toolchain_cache.py \
  dm/tools/tests/test_nsp_chain.py dm/tools/tests/test_docs.py \
  dm/tools/tests/test_env_switches.py
```

Final result: **76 discovered, all 76 passed**;
no unexpected failures/errors/skips. Ruff and whitespace checks pass. The full
pinned Python 3.14 ratchet reports 336 baseline findings, zero new findings and
zero stale baseline entries. Computed chain `39eb2f781d07` and byte-for-byte
hashed-input comparisons against `04811a63` pass.

## Mac gates and integration dependencies

Run `make -C dm/gfx/tests GAME=0400486024DEC000 check_t_copy_alias` on an isolated
matching-chain checkout before considering combination with any other runtime
proposal. Both direct/deferred variants must finish with zero failures and no
command-buffer error. Add a native allocation-failure injector if the driver
path needs failure testing; the portable model does not exercise Apple allocation
failure or ARC code generation. Run native sanitizers and appropriate five-game
regressions (Ocarina of Time, Breath of the Wild, Tears of the Kingdom, Link's
Awakening and Mario Kart World by fill/copy/upload reach), using only owned,
already-compatible archives. Stop if any prerequisite would rebuild shaders.

Only after those gates should this pattern-only change be combined in a separate
reviewed candidate with upload or heap work. The overlap is `nvn_mtl.m`, existing
`t_copy_alias.m`, the source-review test and documentation; the upload growth
branch and heap owner categories are unchanged. The original
`39eb2f781d07` chain contract remains intact, but actual Mac host/archive loading
and controlled 20-minute M2 gameplay tests are still required. No Mac compatibility,
FPS gain, memory reduction or full integration readiness is claimed.
