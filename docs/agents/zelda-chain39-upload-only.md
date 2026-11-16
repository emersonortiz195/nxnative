# Upload-only chain-39 candidate

Branch `codex/zelda-chain39-upload-only`, based on
`26eed50b` / `codex/zelda-chain39-lifetime-review`, which in turn builds on the
reviewed `ff236c5a` subset and exact source `04811a63`. This is the upload-only
backport of PR #5 (`6cfb79edb0127027323df9ec7e53fd5e57e4d9c6`). Pattern retirement
and heap eviction are intentionally separate proposals and are not combined here.

## Runtime change and preserved ownership

The only executable host change is in the first primary staging allocation of
`up_alloc`: when a retained slot buffer is too small, use `res_remove(*sb)`
instead of deferring retirement until a rendering fence, then clear the slot's
strong reference before allocating its replacement. No upload allocator, queue,
slot count, offset/alignment, overflow ownership or submission behavior changes.

The prior [lifetime review](zelda-chain39-lifetime-review.md) established that
chain-39 and PR #5's `up_begin`/`up_flush` have identical executable text. Tests
now also compare this branch's actual begin/flush/allocator functions with the
pinned reviewed proposal, after stripping comments and whitespace. This is a
source audit, not a formal C equivalence or native lifetime proof.

Required assumptions retained by the implementation:

- `up_begin` publishes pending work and waits for the selected slot's earlier
  upload before resetting/reclaiming it.
- Upload completion clears temporary staging/views and commits residency changes
  before the slot busy flag is cleared.
- Primary growth occurs only with `g_up_block == nil` at the beginning of that
  batch. Old buffers used by copies already recorded mid-batch still go through
  their original keep/retirement paths.
- Another slot's in-flight primary remains resident and untouched. Rendering
  reads the uploaded texture, not this private primary staging allocation.

`res_remove` changes pending residency and host references; actual physical
reclamation may await a residency commit and driver ownership release. No fixed
peak-MiB reduction, improved allocation success or FPS improvement is promised.
Allocation failure still uses the existing fatal guard.

## Automated coverage

Four new portable tests execute the actual production first-block branch after
substituting only Objective-C allocation/property syntax and synthetic resource
operations. They check:

1. Growth removal happens before replacement allocation; unchanged-size reuse,
   mid-batch exclusion, oversized primary exclusion, other-slot ownership and
   reuse-off demand behavior remain correct.
2. Restoring the old deferred-release statement fails the model's release-order
   checks. This is a negative control, not a passing substitute implementation.
3. Failed replacement allocation takes the existing explicit fatal path.
4. Current production upload protocol matches the pinned reviewed PR #5 source.

The model tracks host logical ownership, not ARC or driver completion. Initial
harness compilation exposed missing Objective-C `nil` substitution and GCC's
warning about global references to automatic fixture objects; the test fixture
was corrected with a NULL definition and static fixture lifetime, without
weakening compiler warnings or changing production behavior. The four tests
then pass with GCC, O2, Wall/Wextra/Werror.

`t_upload_slots.m` is ported byte-for-byte from PR #5. Relative to chain-39 this
adds only its 15-line weak-reference/residency/deferred-queue checks. Existing
event-delayed uploads, multiple in-flight batches, edge-byte readback, oversized
and burst cases, retained budget and reuse-off behavior remain intact. The
native test was not compiled or executed on Linux.

Full portable command (pinned Python 3.14 environment):

```sh
python -W ignore::ResourceWarning -m unittest -v \
  dm/tools/tests/test_chain39_upload_only.py \
  dm/tools/tests/test_chain39_subset.py \
  dm/tools/tests/test_chain39_lifetime_review.py \
  dm/tools/tests/test_zelda_capture_report.py \
  dm/tools/tests/test_metal_cache_concurrency.py \
  dm/tools/tests/test_shader_toolchain_cache.py \
  dm/tools/tests/test_nsp_chain.py dm/tools/tests/test_docs.py \
  dm/tools/tests/test_env_switches.py
```

The inherited expected failure is the historical pinned PR #6 pattern-retirement
gate. It is not a failure of this upload change and must not be represented as
resolved by it. Result: **78 discovered, 77 passed, one expected failure**, no
unexpected failures/errors/skips. Full pinned Python 3.14 lint ratchet passes:
336 baseline findings, zero new findings and zero stale resolved entries.
Changed-file Ruff and whitespace checks pass. No native Mac pass is inferred.

## Compatibility and conflicts

The computed shader chain remains `39eb2f781d07`. The inherited gate compares
every hashed source input against `04811a63`; none changed. The only runtime
file edited is `dm/gfx/nvn/nvn_mtl.m`, and only the reviewed growth branch changes.
No shader tools, ABI, profile, archive, asset, save, cache or installed app changed.
No shader compilation or merge into main occurred.

This branch shares the runtime file with the separately delegated pattern fix,
but its hunks concern `up_alloc`, not `mtl_sub_fill`. Keep their tests/commits
independent. PR #9 has not been adapted: old-source image-family ownership and
completion/lock-order gates must be established before any heap port is selected.
Do not transplant whole newer-chain branches to resolve a textual conflict.

## Mac acceptance before installation or combination

1. Build/test only in an isolated source/app output using an already-matching
   archive. Inspect Makefile prerequisites; stop if a shader rebuild would occur.
   Do not replace the installed host or change the user's archive.
2. Run `make -C dm/gfx/tests GAME=0400486024DEC000 check_t_upload_slots` with
   Metal validation, in the test's reuse-on and reuse-off modes. Verify delayed
   completion prevents reuse before the event opens and edge bytes remain valid.
3. Confirm old grown-out primaries are absent from active host residency and
   the rendering-fence deferred queue only after their upload has completed.
   Distinguish actual deallocation from removal from the tracking set.
4. Run upload budget, copy alias, lost upload/error recovery and relevant
   concurrent diagnostics tests on the old source. Bound the test process when
   investigating GPU hangs; do not replace a failed lifetime assertion with a
   longer timeout. Review native sanitizer/lint results.
5. Run the repository's impacted five-game regression only with owned matching
   existing archives, without preparation/rebuild. Then perform controlled,
   repeated 20-minute M2 8 GB scene-transition runs of this change alone against
   the unchanged chain-39 control, measuring correct visuals/audio, resolution,
   frame tails, CPU/GPU waits, footprint/pressure/swap and thermal state.

Readiness: source-reviewed, upload-only candidate for controlled native validation.
It is not yet Metal-validated or approved for the installed game, and not a
combined runtime candidate. Pattern and heap changes retain their separate gates.
