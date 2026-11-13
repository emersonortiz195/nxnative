# Phase 4 integration and QA: Zelda on an 8 GB M2

November 12, 2026. This is the Agent 4 branch,
`codex/zelda-phase4-qa`, based on Phase 3 draft PR #4 at
`17020e5403ceec9aeeff756c6e7047f9d2d2f945`. The target remains correct Zelda
gameplay near 720p and 30 FPS, without allocation failures. The inherited title
is Ocarina of Time `0400486024DEC000`, v131072. No M2 measurements are available.

## QA change and PR #4 review

PR #4 integrated compatibility/preflight PR #1 before PR #2 and preserved main's
renderer, graphics answers and chain. Its renderer has no full-pool bypass.
PR #3's unvalidated runtime diagnostics remain excluded. Phase 4 source changes
are separate draft proposals, not evidence of safe combined gameplay.

This QA branch fixes the eager loading of macOS `libproc.dylib` in
`scripts/regress.py`. Linux can now import the report readers and run read-only
`impact`, without any game files or compilation. The library loads only when
actual Mac footprint sampling starts. Non-Mac live sampling raises an explicit
error, not a false zero/missing-memory success. Sampling errors from
`proc_pid_rusage` keep the previous unknown result. Tests cover deferred loading,
unsupported platforms, one-time Mac loading/current-and-peak field extraction,
library failure and failed sampling. Existing regression/host fixtures pass.

The impact map now classifies `shader_compat.py` as standalone read-only
inspection: it changes no game build or runtime and is not an unmapped renderer
change. See the [root cause](../reference/packing.md#read-only-regression-impact-fails-before-reading-revisions-on-linux).
No shader-chain tool, compiler cache format, archive, game profile or renderer
is changed by the QA branch. Chain remains `3ae08e02ec6a`.

## CI and automated checks

PR #4's observed checks on its exact head:

| Workflow | Observed result |
|---|---|
| [tests 43346361086](https://github.com/emersonortiz195/nxnative/actions/runs/43346361086) | Queued at inspection; no pass or failure claimed |
| [C lint 43346361062](https://github.com/emersonortiz195/nxnative/actions/runs/43346361062) | Queued at inspection; clang-tidy has not been established |
| [Python lint 43346361075](https://github.com/emersonortiz195/nxnative/actions/runs/43346361075) | Failed: 324 findings, 323 baseline, one new-to-baseline F401 |

The F401 is the unchanged `dmsh_fetch` import at `dmsh_entry.py:7`, verified in
the job log. It predates these branches but is absent from the baseline.
Removing it or adding `noqa` edits a chain-hashed source and invalidates the
chain, even if generated MSL stays the same. Growing the lint baseline is
forbidden by the repository ratchet. This branch neither hides it with a broad
lint exception nor changes the chain for a lint-only cleanup. Resolve it in a
separate coordinated chain change, or retain it as a merge blocker while
testing these experiments. Local Python 3.12 also resolves three `backports`
imports that remain in the pinned baseline; CI Python 3.14 did not report that
baseline drift. Do not shrink the baseline using a different environment just
to make one machine green.

Fresh Linux QA checks (Python `/workspace/venv/bin/python`,
`DM_GAME=0400486024DEC000`, `DM_ROOT` in workspace scratch):

| Check | Result |
|---|---|
| Existing regression/host-MSL fixtures before new checks | 69 passed after deferred loading |
| Same suites with four sampler checks | 73 passed |
| Regression, host-MSL, usage, shader preflight, lint-ratchet and docs suites | 110 passed |
| Full tools discovery | 1,463 run; 15 failure records, 35 errors, 70 skips |
| Full gfx Python discovery | 477 run; nine missing-`xcrun` errors, 179 skips |
| Full iOS Python discovery | 52 run; 21 failure records, ten skips |
| CPU texture test with GCC | 5,382/5,382 checks passed |
| CPU textures with GCC ASan/UBSan, no suppressions | 5,382/5,382 checks passed |
| Changed-file Ruff | Passed |
| Full Python lint ratchet against main | Failed on the F401 and three locally resolved baseline imports above |
| Host Python/native host/native Metal targets | Missing native binaries or clang/Xcode/Metal; no native pass |

The full suites are **not green**. Failure records include subtests. Missing
macOS `libSystem`, `xcrun`, `lipo`, `xattr`, APFS copy/device-transfer behavior,
GCC warnings in a synthetic reader and an inode-reuse test assumption remain.
The QA fix exposes 64 more tools tests than the Phase 3 discovery while removing
the eager-import errors; this is more executed test coverage, not improved FPS.
No tests were disabled, lint baselines enlarged, games run or shaders rebuilt.

Commands for the focused checks:

```sh
DM_GAME=0400486024DEC000 python3 -W ignore::ResourceWarning -m unittest \
  dm/tools/tests/test_regress.py dm/tools/tests/test_host_msl.py \
  dm/tools/tests/test_usage.py dm/tools/tests/test_shader_compat.py \
  dm/tools/tests/test_lint_python.py dm/tools/tests/test_docs.py
python3 scripts/regress.py impact origin/main..HEAD --out work/phase4/impact
```

Full discoveries use `python3 -W ignore::ResourceWarning -m unittest discover
-s <directory>` for `dm/tools/tests`, `dm/gfx/tests`, `dm/ios/tests` and
`dm/host/tests`. ResourceWarnings are filtered, not assertion failures.

## Mac preparation without rebuilding game shaders

Use arm64 macOS 26.6+, Xcode 27.2 and the repository's Python prerequisites.
Keep the existing application, game files and archives untouched. These steps
only build new hosts in source worktrees and write new trial outputs on an
external drive. They do **not** invoke `build_ipa_from_nsp.py`, `dmsh_build.py`,
cache prefill or any archive repack. Do not run a full shader rebuild to make a
failed compatibility check disappear.

1. Record the original host/archive's actual chain and verified profile/map.
   A folder name alone is not provenance. The historically recorded old archive
   `39eb2f781d07` does not match this source's `3ae08e02ec6a`. If no verified
   matching archive exists, stop before a new-host launch; preserving the old
   pair takes priority over preparing an experimental run. Never relabel JSON.
2. Fetch branches into source worktrees on an external drive. Test one proposal
   at a time against its exact base. Do not overwrite an installed executable.
3. Set these paths to the verified, existing inputs; `TRIAL` must be new:

```sh
export DEVELOPER_DIR=/Applications/Xcode_27.2.app/Contents/Developer
export G=0400486024DEC000
export DRIVE=/Volumes/ZeldaWork
export TRIAL="$DRIVE/phase4/run-01"
export READONLY_BUILD="$DRIVE/Ocarina/${G}_build"
export SHMAP="$DRIVE/Ocarina/verified-profiles/$G/shader_map.tsv"
export MSL="$DRIVE/Ocarina/verified-msl"
export SAVE_SEED="$DRIVE/Ocarina/reference-save"
test ! -e "$TRIAL" || { echo 'Choose a new TRIAL directory'; exit 1; }
mkdir -p "$TRIAL/hosts" "$TRIAL/runtime"
unset DM_M2_NO_FULL_POOL DM_NVN_MEMORY_GUARD
xcodebuild -version
xcrun -sdk macosx metal --version
uname -m
python3 dm/tools/shader_compat.py "$MSL/b-3ae08e02ec6a" \
  --host-header dm/gfx/nvn/dmsh_chain.h --game "$G" \
  --shader-map "$SHMAP" --tables-dir "$(dirname "$SHMAP")" \
  > "$TRIAL/preflight.json"
```

Preflight success does not prove Metal loadability, side libraries, numerical
correctness or gameplay. A missing/mismatched chain/map is a blocker. `MSL` is
the parent library root used by the host; the preflight takes its chain-specific
child (image overlays are supported). The verified map/table paths must match
the libraries and game build, not merely the repository title ID.

Build each chosen source checkout's host into that checkout, then copy only the
new host to trial storage; this may compile small built-in host shaders, not the
game's shader archive:

```sh
export CONTROL_SRC="$DRIVE/phase4/src-control"
export CANDIDATE_SRC="$DRIVE/phase4/src-candidate"
DM_GAMES_DIR="$(dirname "$(dirname "$SHMAP")")" DM_GAMES_FIRST=1 \
  make -C "$CONTROL_SRC/dm/host" GAME="$G" -j2 dmhost
cp "$CONTROL_SRC/dm/host/dmhost" "$TRIAL/hosts/control"
DM_GAMES_DIR="$(dirname "$(dirname "$SHMAP")")" DM_GAMES_FIRST=1 \
  make -C "$CANDIDATE_SRC/dm/host" GAME="$G" -j2 dmhost
cp "$CANDIDATE_SRC/dm/host/dmhost" "$TRIAL/hosts/candidate"
```

`DM_GAMES_DIR` must contain a directory named `$G` with the verified profile;
adjust its path accordingly. Both sources must declare the actual matching
chain. Record `git rev-parse HEAD` and `git diff --check` in each checkout.
Use immutable profile copies if generating headers would otherwise target
user-owned data; make's generated outputs belong in the new source trees.

## Measurements and acceptance gates

First run the candidate's relevant Mac unit tests, then the host suite and
sanitizers. Check the exit status of each command before continuing:

```sh
make -C "$CANDIDATE_SRC/dm/host/tests" GAME="$G" -j2 run
make -C "$CANDIDATE_SRC/dm/host/tests" GAME="$G" -j2 asan tsan-threads
make -C "$CANDIDATE_SRC/dm/gfx/tests" GAME="$G" -j2 run
```

Run real `t_copy_alias` for fill-buffer GPU content/order and `t_upload_slots`
for delayed upload slot reuse/growth before those proposals enter any combined
candidate. Repeat with Metal validation enabled per the repository's graphics
guide. For upload release, the old-production negative control must fail the
new residency/deferred-retention assertions while GPU output remains correct;
repeat direct and deferred encode modes as documented by its owner. Linux's
arithmetic/source models are insufficient to waive these gates.

For manual launch, use the existing build's printed command as a template,
replacing only the executable with the new trial host. Redirect every writable
path (`DM_ROOT`, `DM_SAVE`, `DM_TEMP`, `DM_CTL`, logs, capture and
`DM_PSO_ARCHIVE`) into `TRIAL`; copy the reference save there first. Point
`DM_MSL_DIR`, `DM_NVN_SHMAP`, `DM_ROMFS`, fonts and patched modules at verified
read-only inputs. Use `DM_FPS_TARGET=30 DM_WINDOW=1 DM_AUDIO=1`; leave mapping
bypasses off. Confirm correct pictures, audio and real-time game speed before
timing. A black-screen FPS counter is a failure.

The profile has **no verified fixed RENDER_SCALE stub**. Do not advertise
`DM_RENDER_SCALE` or `bench.py --scale` as a working 720p control here. A
1280x720-point window on Retina also proves neither output pixels nor internal
scene size. In a separate run, capture a scene pass dump and screenshot; record
the main scene attachments/viewport and final output dimensions. Report the
actual dimensions/range. If the scene exceeds roughly 1280x720, fixed-720p
acceptance remains blocked even if 30 FPS holds. Dynamic-resolution trials
must be labeled adaptive and record their range; keep upstream graphics-tier
fixes rather than restoring an older answer to force a smaller picture.

Once unit/compatibility/manual gates pass, run identical saves/routes with
three alternating control/candidate runs. This command writes fresh saves,
temps, logs and pipeline archives under trial storage, with explicit input
library/map paths:

```sh
python3 scripts/bench.py "$READONLY_BUILD" --route kokiri-deck --fps 30 --runs 3 \
  --save "$SAVE_SEED" --out "$TRIAL/bench" \
  --variant "control:host=$TRIAL/hosts/control,msl=$MSL,shmap=$SHMAP,pso=$TRIAL/pso/control" \
  --variant "candidate:host=$TRIAL/hosts/candidate,msl=$MSL,shmap=$SHMAP,pso=$TRIAL/pso/candidate" \
  --env "DM_ROOT=$TRIAL/runtime" --env DM_AUDIO=1 --env DM_OPMODE=0 \
  --env DM_DYNAMIC_RESOLUTION=0 --env DM_PRESENT_UPSCALE=off \
  --lock "$DRIVE/phase4/measure.lock"
```

Verify the route loads the Kokiri deck save before trusting its timing window.
Use a path without commas for the variant syntax. Preserve first-start/cold
pipeline logs, then compare consistently warmed runs. Do not evict the user's
existing caches or describe warm reuse as a cold-start gain.

For each run collect:

| Area | Evidence |
|---|---|
| FPS/pacing | `results.md`, `results.json`, frame TSV p50/p95/p99/max, dropped frames; count >33.33 ms separately from bench's built-in >50 ms count at 30 FPS |
| GPU and stalls | host library/pipeline wait and long-frame logs; GPU span, not the sum of overlapping command-buffer times; separate profiled/capture runs from timing baselines |
| Memory | existing periodic host memory lines; repeated `footprint -p PID` and `vmmap -summary PID` through loads/transitions; `sysctl vm.swapusage` and Activity Monitor memory pressure before/during/after |
| Resolution | scene/output dimensions with exact capture frame; dynamic range if adaptive |
| Thermal stability | at least 20 minutes of transitions/menu/focus loss and return; record power mode, power source, ambient conditions and OS thermal observations; do not infer temperature from FPS alone |
| Correctness/reliability | screenshots, audio/speed, Metal command-buffer errors, crashes/hangs, allocation failures, save integrity |

Stop on any allocation failure, GPU error, corrupt picture, hang or uncontrolled
memory growth; retain the failed run's logs. Do not hide the failure with a
mapping bypass, residency clamp or suppressed errors. A final footprint sample
is not peak footprint. Logical Metal allocation totals can overlap physical
pages; report both rather than claiming either equals exact free RAM.

Record `pmset -g therm` before, during and after the sustained run, retaining an
unsupported/no-recorded-warning result as such. It is not a temperature sensor.
Use the OS thermal state or a documented hardware sampler for thermal claims;
do not invent a temperature from these logs. Profilers, repeated footprint
queries and captures can perturb timing, so collect detailed diagnostic runs
separately from the consistently instrumented control/candidate comparison.

Shader work is validated first with isolated synthetic compiler fixtures. A
small disposable Mac compile can then confirm byte-identical library/cache
provenance behavior; a full game rebuild is neither required nor authorized by
this phase. Count compiler invocations and duplicate misses independently of
runtime pipeline stalls. Existing archives remain read-only.

## Integration readiness

Published proposals reviewed in this phase:

| Assignment | Branch / reviewed commit | Review and remaining gate |
|---|---|---|
| GPU memory, [#5](https://github.com/emersonortiz195/nxnative/pull/5) | `codex/zelda-phase4-gpu-memory` / `6cfb79edb0127027323df9ec7e53fd5e57e4d9c6` | Source path waits upload completion before removing old primary-slot residency; within-batch/overflow lifetime rules remain. Delayed-slot GPU test and negative control still need Mac execution. Requested release is not proof of immediate physical deallocation |
| Metal rendering, [#6](https://github.com/emersonortiz195/nxnative/pull/6) | `codex/zelda-phase4-metal` / `3c2198152292f64cbedf06701c84b6381d4e8285` | New shared fill buffer is initialized directly before encoding, preserves old-source immutability and repeated values, checks nil. Portable negative control proves elimination of an explicit 64 KiB temporary/copy; real Metal content/residency still pending |
| Shader cache, [#7](https://github.com/emersonortiz195/nxnative/pull/7) | `codex/zelda-phase4-shader` / `34b3ac8138dacf7a70566b55cc96c29fa31910e8` | Per-Cache-instance active digest gates coalesce identical misses; lock registry drains on success/failure, no global/Store lock held during compilation. Synthetic eight-worker requests drop from eight compiler callbacks to one, not measured compiler time or runtime shader stalls. Separate processes/instances are not coalesced |

The memory and fill edits touch different functions of the renderer. Shader
cache changes are outside the chain hash and preserve FORMAT/compiler/source
keys and compiled bytes. All three preserve main's Metal logging and graphics
fixes. Their game-note/reference/symptom additions can conflict textually;
preserve every finding and regenerate the symptom index when rehearsing a
combined source tree. The shader branch is stacked on #4, while #5/#6 are based
on main; their older inherited Python-test failures are not introduced changes.

Recommended review/testing order: #4 compatibility baseline, this QA fix, then
#7 in isolated tiny compiler/cache tests and #6 in actual Metal copy tests;
test #5 separately last because it changes residency retirement. Combine only
after those independent gates. A local compatibility rehearsal is not a new
release candidate and never substitutes for the Mac gates.

### Local-only compatibility rehearsal

A detached scratch worktree combined QA commit `12ed2f14` with the exact #7,
#6 and #5 commits above, in that order. Its final local commit was
`4af6808a7b85f4186310874696e6ff1c21d7279c`. It was **not published** as a runtime
candidate or merged into any source branch. Two textual conflicts were confined
to additions under Ocarina's "Found on this game"; all three findings were
retained. Renderer hunks merged without conflict. The regenerated symptom index
was already consistent, and whitespace checks passed.

**191 combined portable checks passed**, no errors/failures/skips, using:

```sh
DM_GAME=0400486024DEC000 python3 -W ignore::ResourceWarning -m unittest \
  dm/tools/tests/test_regress.py dm/tools/tests/test_host_msl.py \
  dm/tools/tests/test_usage.py dm/tools/tests/test_shader_compat.py \
  dm/tools/tests/test_lint_python.py dm/tools/tests/test_docs.py \
  dm/tools/tests/test_metal_cache_concurrency.py \
  dm/tools/tests/test_shader_toolchain_cache.py dm/tools/tests/test_shader_lib.py \
  dm/tools/tests/test_nsp_chain.py dm/tools/tests/test_gfx_tests_makefile.py \
  dm/gfx/tests/test_fill_pattern.py
```

This validates synthetic ownership/initialization/compiler coordination and
metadata/test compatibility only. It does not execute GPU command buffers or
the delayed-upload-slot test. The combined tree still computes chain
`3ae08e02ec6a`, preserves `hle_oe.c` and the upstream logging definition, and
contains no `DM_M2_NO_FULL_POOL` reader.

Read-only impact now runs on Linux for all proposals. At the reviewed revisions,
#5 and #6 each reach 26 NVN/HLE entry points; three committed usage manifests
match (Breath of the Wild, Tears of the Kingdom, Pokémon Scarlet), one is not
affected and 154 profiles are unknown. #7 reaches those same three only through
the broad shader-stage rule, with 154 unknown. "Unknown" must not be reported
as unaffected. QA-only changes map to no game-runtime paths.

Recommended five-game Mac coverage before runtime integration: Ocarina
`0400486024DEC000` (target workload), Breath of the Wild `01007EF00011E000`,
Tears of the Kingdom `0100F2C0115B6000`, Pokémon Scarlet `0100A3D008C5C000`
(the three manifest matches), and Link's Awakening `01006BB00C6F0000` (repeated
movie/texture uploads). All five remain unrun here: no game assets, Mac or GPU
is available. Owners should use their existing matching-chain libraries and
routes. Do not start `regress.py check`/`chain` if it would initiate a lengthy
translation/rebuild; establish reusable harness inputs with the owners first.
Static impact is not a substitute for these gameplay checks.

Ready for independent review and Mac test preparation as a draft, not merging.
No measured M2 FPS, peak-footprint, shader-stall or thermal improvement is
claimed. Source proposals remain separate until their own Mac correctness
gates pass. Full-pool bypass and PR #3 diagnostics remain excluded.
