# Phase 3: experimental Zelda integration and M2 test procedure

November 12, 2026. Target: Apple M2 MacBook Air, 8 GB unified memory,
approximately 1280x720 internal rendering and 30 FPS. The inherited assignment
uses Ocarina of Time, profile `0400486024DEC000`, update `v131072`.
These instructions do not establish that this target is achievable.

## Integrated revisions and preserved fixes

Branch: `codex/zelda-phase3-integration`, created from freshly fetched main
`084f5aa5c59bbfbebfcab7ad1b1a3b9bc196a582`.

1. Integrated [PR #1](https://github.com/emersonortiz195/nxnative/pull/1)
   at `c9b7d237716d5df5721bb36bd2a1a20f36e455bc` with merge commit
   `708fbd17`. This includes read-only archive preflight, rejection of failed or
   empty compiler identities, portable shader assertions, and the pollwait,
   catalog and cache-fixture fixes.
2. Applied only PR #2's incremental `28debc680c3245841e1e297672a60fa20d5887c3`
   after #1, as `7058d80d`. Optional shader-map coverage and uniform-table
   diagnostics therefore retain #1's later fixes. Shared ancestors were not
   applied twice. Both operations completed without textual conflicts.
3. Reviewed [PR #3](https://github.com/emersonortiz195/nxnative/pull/3)
   at `df2c6e9f1f2aeb123f5c1c851050e6b3c9ca49a7` separately. It is closed,
   unmerged. **No runtime code from #3 is included.** Its portable arithmetic
   model does not prove ARC snapshot, destructor reentry, timer shutdown or
   in-flight Metal allocation safety. Diagnostics under the residency mutex
   also add unmeasured scan/sysctl overhead. These gates remain open.

The renderer `dm/gfx/nvn/nvn_mtl.m`, operation-mode/graphics answers
`dm/host/hle_oe.c`, chain header and game profile are byte-identical to main.
This preserves main's host-stack `MLOG` protection, shared-page dirty tracking
and tier-0 graphics fix. #3's older whole-file renderer diff must not replace
them. Shader chain remains `3ae08e02ec6a`. No runtime code reads
`DM_M2_NO_FULL_POOL` on this branch; the bypass implementation was never imported.
Keep the variable unset. Source PR branches and main were not modified.

Preflight success means metadata/base-file presence, plus requested map coverage.
It does not validate side libraries, binary entry points, Metal ABI, numerical
shader results or gameplay. Uniform-table warnings indicate conservative host
fallbacks. No archive was relabeled, rebuilt or modified in this Linux session.

## Linux validation

Commands run from the repository root with Python from `/workspace/venv` and
`DM_GAME=0400486024DEC000`; `DM_ROOT` points into workspace scratch. Full results
are recorded below after completion. Failures/skips are not counted as passes.

```sh
export DM_GAME=0400486024DEC000
export DM_ROOT="$PWD/work/phase3/runtime"
mkdir -p "$DM_ROOT"
python -W ignore::ResourceWarning -m unittest \
  dm/tools/tests/test_shader_compat.py \
  dm/tools/tests/test_shader_toolchain_cache.py \
  dm/tools/tests/test_shader_lib.py dm/tools/tests/test_nsp_chain.py \
  dm/tools/tests/test_docs.py dm/tools/tests/test_env_switches.py \
  dm/tools/tests/test_pollwait_fixture.py
python -W ignore::ResourceWarning -m unittest \
  dm/gfx/tests/test_dmsh_gather_offsets.py dm/gfx/tests/test_dmsh_hmma.py \
  dm/gfx/tests/test_dmsh_border.py dm/gfx/tests/test_dmsh_reflect.py \
  dm/gfx/tests/test_dmsh_fetch.py dm/gfx/tests/test_dmsh_ampere_mem.py \
  dm/gfx/tests/test_tbdr_budget.py
make -C dm/gfx/tex/tests CLANG=cc t_tex
dm/gfx/tex/tests/t_tex
```

Full discovery was also attempted separately for `dm/tools/tests`,
`dm/gfx/tests`, `dm/ios/tests` and `dm/host/tests` with
`python -W ignore::ResourceWarning -m unittest discover -s <directory>`.
Native host/gfx `make ... run`, the Python lint ratchet and regression harness
were attempted too. Mac-only tests remain enabled on their supported platform.

| Check | Fresh integration result |
|---|---|
| Focused compatibility/archive/cache/catalog/pollwait/docs | **91 passed** |
| Focused shader/budget tests | **147 run: 63 passed, 84 skipped** |
| Portable CPU texture executable, built with GCC (`CLANG=cc`) | **5,382/5,382 checks passed** |
| Full tools discovery | 1,399 run; **15 failure records, 37 errors, 70 skipped** |
| Full gfx Python discovery | 477 run; **9 errors, 179 skipped**; all nine errors require missing `xcrun` |
| Full iOS Python discovery | 52 run; **21 failure records, 10 skipped** |
| Host Python discovery | Two errors: native `t_svc_memory` missing |
| Changed integration Python files, Ruff | Passed |
| Documentation links/anchors | Six passed after adding this guide |
| Native host/gfx targets | Blocked by missing clang, Xcode and Metal |
| Regression `impact` and `check` | Blocked importing macOS `libproc.dylib` |
| Full Python lint ratchet | Failed: unchanged chain-tool unused import plus three resolved imports still in baseline |

The full discoveries are **not green**. Failure records include subtests, so
they must not be subtracted to invent pass totals. Examples include macOS
`libSystem.B.dylib`, `lipo`, `xattr`, `xcrun`, APFS/macOS copy/device-transfer
assumptions, and GCC's misleading-indentation error in a synthetic C reader.
One portable packaging test also assumes an unlinked/recreated image gets a
different inode; the filesystem reused its inode in this run. This is recorded
as an unresolved test assumption, not proven product corruption or a pass.
No tests were disabled to make these discoveries green. The nine shader tests
perform source assertions followed by Metal compilation; their compile steps
still need the Mac. Focused portable rewrites remain covered above.

The unchanged unused `dmsh_fetch` import is in `dmsh_entry.py`, a chain-hashed
file; a lint-only removal would change the chain and require coordinated library
rebuilds. The lint baseline and chain were not edited to conceal the failure.
The prior successful PR #1 CI at `a70a4864` is historical evidence only; this
integration's new CI must be reviewed independently.

## Exact Mac setup and isolated build

Use arm64 Python 3.12 or later, macOS 26.6 or later and Xcode 27.2 with its Metal
toolchain, per [requirements](../../README.md#requirements). Put game files,
keys, builds, saves and logs on a drive with enough space, outside this checkout
and the home folder. Do not reuse an original archive as an output directory.
The build command below can perform a full shader compilation into a **new**
build directory; do not run it against the user's preserved installed build.

From a checkout of this branch, in a shell whose Python environment already has
the repository's [build prerequisites](../../README.md#build-from-the-command-line):

```sh
export DEVELOPER_DIR=/Applications/Xcode_27.2.app/Contents/Developer
xcodebuild -version
xcrun -sdk macosx metal --version
uname -m
python3 --version
export G=0400486024DEC000
export DRIVE=/Volumes/ZeldaWork
export SOURCE="$DRIVE/Ocarina/game.nup"
export BUILD="$DRIVE/phase3/${G}_build"
export RESULTS="$DRIVE/phase3/results"
export REPO="$PWD"
mkdir -p "$RESULTS"
unset DM_M2_NO_FULL_POOL DM_NVN_MEMORY_GUARD
test ! -e "$BUILD" || { echo 'Choose a new BUILD directory'; exit 1; }
python3 scripts/build_ipa_from_nsp.py "$SOURCE" --platform mac \
  --work-dir "$BUILD" --keep-extracted
```

Replace the drive and source paths with the actual mounted drive and owned NUP
or dump folder. NUP/dump input needs no `prod.keys`; an NSP input for a different
title uses `-k /path/to/prod.keys`. Keep this game's ID and source together.
Do not pass `--allow-other-metal` or `--allow-shader-regressions` to bypass a
failed prerequisite. On 8 GB, close other workloads and monitor memory pressure
during compilation; no safe compiler concurrency override is established here.
If the toolchain reports a missing prerequisite, resolve that exact requirement
using the linked build guide before retrying.

Audit the newly produced library and generated profile before launching:

```sh
export CHAIN=$(awk '/^#define DMSH_CHAIN / {gsub(/"/, "", $3); print $3}' \
  dm/gfx/nvn/dmsh_chain.h)
export PROFILE="$BUILD/profile/$G"
if test ! -f "$PROFILE/game.tsv"; then
  export PROFILE="$REPO/dm/games/$G"
fi
python3 dm/tools/shader_compat.py "$BUILD/shader/cache/b-$CHAIN" \
  --host-header dm/gfx/nvn/dmsh_chain.h --game "$G" \
  --shader-map "$PROFILE/shader_map.tsv" \
  --tables-dir "$PROFILE" > "$RESULTS/preflight.json"
```

The folder/image overlay is handled by the tool; pass the chain-specific path,
not its parent. Verify these paths against the build's final printed launch
command. A pre-existing archive recorded as `39eb2f781d07` cannot be presumed
compatible with this host's `3ae08e02ec6a`; stop and retain its original host and
archive as a pair. Never rename images or edit reflection to force acceptance.

Run native checks before gameplay, keeping output on the external drive:

```sh
make -C dm/host/tests GAME="$G" -j2 run > "$RESULTS/host-tests.log" 2>&1
make -C dm/host/tests GAME="$G" -j2 asan tsan-threads > "$RESULTS/host-sanitizers.log" 2>&1
make -C dm/gfx/tests GAME="$G" -j2 run > "$RESULTS/metal-tests.log" 2>&1
```

Check each exit status before running the next command. `t_pollwait`, native
memory tests, Foundation/ARC, real Metal GPU tests and gameplay cannot be
validated by the Linux results. #3's ARC negative controls must be tested in
its own isolated checkout if that proposal is revived; they are not in this
integration branch. Do not enable the mapping bypass during those tests.

## 720p/30 procedure and resolution gate

Use the build's printed launch command for an initial manual run, prefixed by
`DM_WINDOW=1 DM_AUDIO=1 DM_FPS_TARGET=30 DM_OPMODE=0 DM_PRESENT_UPSCALE=off`.
Check correct scene rendering, movement speed, menus and audio before timing.
The window defaults to 1280x720 **points**, which is not proof of 720p pixels on
a Retina screen, and does not set the game's internal resolution.

This Ocarina profile declares frame-step and dynamic-resolution stubs but no
fixed `RENDER_SCALE` stub. Thus `--scale` / `DM_RENDER_SCALE` cannot be offered
as a verified 720p setting. Main's documented docked tier-0 sizes are output
2560x1440 and top internal 1920x1080. Handheld sizes must be measured. Keep
main's graphics-scale answer intact; do not silently restore tier 1.

In a separate diagnostic run add `DM_NVN_GPUPROF=60`, or drive `DM_CTL` with
`passdump 1` and `shot /absolute/path/frame.png` while standing in the scene.
Follow [GPU measurement](05-debugging.md#gpu-time-on-the-device): identify the
main scene attachments/viewports and final presentation dimensions, and inspect
the screenshot. Record both internal and output resolution. Profiling/capture
frames must not be used as unperturbed timing samples.

For the first controlled trial keep `DM_DYNAMIC_RESOLUTION=0`. If its observed
resolution exceeds 1280x720, the fixed-720p target is **blocked**, even if FPS
looks good. A separate `DM_DYNAMIC_RESOLUTION=1` trial can measure the existing
adaptive controller, but does not guarantee 720p and must report its observed
resolution range. A verified fixed-resolution patch would be separate future
work requiring game-code evidence; no such patch is included here.

## Controlled baseline/candidate benchmark

Use the same rewritten modules, save, shaders, PSO archive and environment for
both hosts. Their runtime renderer and shader chain are identical in this phase;
no frame-rate or memory gain is expected from a read-only preflight/test change.
Create a detached baseline checkout without switching the integration checkout:

```sh
export BASE="$DRIVE/phase3/nxnative-main"
git worktree add --detach "$BASE" 084f5aa5c59bbfbebfcab7ad1b1a3b9bc196a582
DM_GAMES_DIR="$(dirname "$PROFILE")" DM_GAMES_FIRST=1 \
  make -C "$BASE/dm/host" GAME="$G" -j2 dmhost
python3 scripts/bench.py "$BUILD" --route kokiri-deck --fps 30 --runs 3 \
  --save "$DRIVE/Ocarina/reference-save" \
  --variant "main:host=$BASE/dm/host/dmhost" \
  --variant "phase3:host=$BUILD/tools/dmhost" \
  --env DM_OPMODE=0 --env DM_DYNAMIC_RESOLUTION=0 \
  --env DM_PRESENT_UPSCALE=off --env DM_AUDIO=1 \
  --lock "$DRIVE/phase3/measure.lock" --out "$RESULTS/bench-fixed"
```

The `kokiri-deck` route requires the documented Kokiri Forest deck save; verify
the menu presses load it before trusting timing windows. Otherwise choose a
matching route in [bench.tsv](../../dm/games/0400486024DEC000/bench.tsv) and record
its save/setup. Variant paths must exist. With spaces/commas in a path, use a
simple external-drive path compatible with the benchmark variant syntax.
Warm each host's same-chain pipeline path once; retain first-launch logs as
cold-start evidence. Do not call a hot-cache run a cold-start improvement.

Report `results.md`/`results.json`, frame p50/p95/p99/max and late frames relative
to 33.33 ms, observed resolution, GPU span, shader/pipeline waits and `[RED]`
lines. `bench.py`'s built-in late-frame count uses 1.5 frame times: at 30 FPS
that is 50 ms, so also count >33.33 ms directly from its per-frame TSV. Record
macOS/Xcode versions, M2 GPU configuration, power state, ambient conditions and
background load. Repeat at least 20 minutes of transitions, menus and focus
loss/return to check sustained thermals and reliability.

For memory, use main's existing memory log and Activity Monitor; in a separate
diagnostic run capture `footprint -p PID`, `vmmap -summary PID`,
`sysctl vm.swapusage` and `memory_pressure`. Sample footprint repeatedly through
loading and transitions; a final sample is not peak memory. Optional upstream
`DM_NVN_ALLOCPROF=1` adds allocation logging and must be measured separately from
the timing baseline. Logical Metal allocation totals can overlap and are not
unique physical footprint. Do not equate a 9 GB guest virtual pool with 9 GB of
immediately resident memory, or infer 8 GB safety from it.

On Mac, also run the regression harness with its actual external paths:

```sh
python3 scripts/regress.py --root "$DRIVE/phase3/harness" \
  --games-dir "$DRIVE/games" check --games "$G" \
  --baseline 084f5aa5c59bbfbebfcab7ad1b1a3b9bc196a582 --candidate worktree
```

This phase's reach is narrow (read-only deployment checks/cache provenance and
test fixtures), so Ocarina is the selected initial game. Before broader cache
integration, add local titles with different shader stages/APIs and report their
routes and results; none are validated here. `regress.py impact` and `check`
currently fail at macOS `libproc.dylib` import on Linux, before inspecting games.

## Release gate

Draft review only. Main and the source PRs remain unmerged. Hardware performance,
peak memory, shader stalls and 720p/30 reliability are unmeasured. Required gates
are actual archive loading, clean Mac tests/CI, lint resolution, resolution
verification and sustained M2 gameplay. #3 runtime diagnostics and the full-pool
bypass remain excluded pending independent safety evidence.
