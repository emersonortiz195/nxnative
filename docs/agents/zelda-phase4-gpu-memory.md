# Phase 4 GPU memory: completed upload-slot growth

Target: Apple M2 MacBook Air, 8 GB unified memory, approximately 720p at 30 FPS.
Branch `codex/zelda-phase4-gpu-memory` starts at main `084f5aa5` and does not
modify the Phase 3 integration branch or another agent's work.

## Isolated candidate and ownership argument

The [reference finding](../reference/rendering.md#completed-upload-staging-waits-for-an-unrelated-render-fence)
is the canonical description. The only runtime change is the primary retained
upload-slot growth path in `up_alloc`: the old upload-only buffer is removed
from residency and its slot reference released before its replacement is made,
after `up_begin` waited for that slot's completion flag. The completion handler
clears the flag after the GPU upload finishes. Main rendering samples the
destination textures, never this private deswizzle staging buffer.

Previously `defer_obj_release` tied the old block to the next rendering fence,
although the known last use was already complete. This is avoidable overlap,
not evidence that live render targets can be reclaimed or that guest buffers
can be omitted. The main renderer logging, graphics tier and dirty-page fixes
are preserved. Shader tools/header/ABI and profiles' inputs are unchanged;
no shader recompilation is required. `DM_M2_NO_FULL_POOL` is absent/disabled.

The source change has not been compiled or run on macOS in this environment.
Its safety argument is bounded to the slot whose completion was waited for;
do not generalize immediate removal to overflow/parameter/main render buffers.
Independent review must confirm no new user of primary upload staging bypasses
this ownership contract. Metal allocator retention can delay actual destruction
even after the host reference is dropped, so logical residency changes do not
establish a particular footprint reduction.

## Tests and falsifiable Mac gate

`t_upload_slots` is extended at its delayed first-slot reuse, where the retained
primary grows from 4 to 32 MiB before the render submission is committed.
A weak reference observes the old allocation without extending its lifetime.
If it remains alive it must no longer be in `g_res_objects`, and it must not
appear in the render-deferred queue. The old implementation fails these new
assertions by construction; **that negative-control execution is still required
on a Mac**, not claimed as run here. Existing GPU edge readbacks, same-batch
non-overlap, delayed gate, overflow/oversized staging and retained-budget checks
remain, including reuse-off execution.

On a supported Mac with Xcode 27.2, in this isolated checkout:

```sh
make -C dm/gfx/tests GAME=0400486024DEC000 check_t_upload_slots
DM_NVN_ENC_THREAD=1 make -C dm/gfx/tests GAME=0400486024DEC000 check_t_upload_slots
make -C dm/gfx/tests GAME=0400486024DEC000 check_t_upload_budget
make -C dm/gfx/tests GAME=0400486024DEC000 run
```

The check target enables Metal validation and repeats with reuse disabled.
Run the new test against main's `up_alloc` as a negative control, changing only
that growth line in a disposable checkout. Never alter the installed app or
preserved shader archives. Use the Phase 3 guide's isolated same-chain host
build and identical-save route comparison. Log peak process footprint, allocated
Metal bytes, residency counts, frame p50/p95/p99, pipeline waits, resolution,
swap and thermal state through loading and sustained scene transitions.
No expected FPS gain is asserted. There are no hardware measurements here.

Linux results (Python `/workspace/venv/bin/python`):

- `python -m unittest dm/tools/tests/test_docs.py dm/tools/tests/test_nsp_chain.py dm/tools/tests/test_gfx_tests_makefile.py`: **28 passed**, after the reference entry, generated symptom index and this guide were added.
- `DM_GAME=0400486024DEC000 DM_ROOT=<workspace scratch> python -W ignore::ResourceWarning -m unittest discover -s dm/gfx/tests`: **475 run, 19 error records, 173 skipped**. All 19 records are missing `xcrun` from unguarded Metal compilation methods (including ten subtest error records in six fetch methods on main). The first discovery without DM_ROOT also had five read-only-home scratch errors; the explicit workspace root removes those five errors. This is not a passing shader suite.
- `make -C dm/gfx/tex/tests CLANG=cc t_tex`, then its executable: **5,382/5,382 checks passed**.
- `make -C dm/gfx/tests GAME=0400486024DEC000 check_t_upload_slots`: blocked by missing `xcrun`/Xcode before the native test compiles. No Metal test pass is claimed.
- `python3 dm/tools/lint_c.py compdb`: blocked generating host Metal headers without `xcrun`; clang-tidy was not run.
- `python3 scripts/regress.py impact origin/main..HEAD`: blocked importing macOS `libproc.dylib` even before inspecting a diff. The same import blocks the gameplay harness on Linux.
- `git diff --check`: passed. Shader chain remains `3ae08e02ec6a`.

Native
Objective-C/Metal compilation and the five-game host regression gate are blocked
without macOS/Xcode/game assets. Select Ocarina, Tears of the Kingdom, Link's
Awakening (movie reuploads), Octopath Traveler II and Mario Kart World to cover
NVN uploads, streaming, sparse assets and slot growth when those owned game
builds are available. Do not rebuild any shader library solely for this change.

Ready only for independent source review and Mac unit testing after publication.
Not merge-ready until the Metal tests, negative control, compatible host loading
and controlled gameplay gates pass. Nothing in this branch proves reliable
720p/30 or eliminates allocation failures on an 8 GB machine.
