# Zelda M2 compatibility and integration review (Agent 4)

Target: Ocarina of Time, `0400486024DEC000`, Apple M2 MacBook Air,
8 GB unified RAM, correct 1280x720 gameplay at approximately 30 FPS
(33.3 ms per frame). This review was performed on Linux. No Metal build,
gameplay, GPU timing, compiler spill measurement or M2 memory measurement was
performed. A black screen with audio or an FPS counter is a failed result.

## Findings and implemented changes

The user's existing 6.9 GB archive and black-screen symptoms were reported to
this task; the archive and installed application are not present here. Repository
evidence independently confirms these source-header identifiers:

| Source | DMSH_CHAIN | Existing archive usability |
|---|---|---|
| `04811a63` | `39eb2f781d07` | Candidate baseline; metadata and Mac loading still need verification |
| `084f5aa5` (review base) | `3ae08e02ec6a` | Rejects shaders whose reflection records the older chain |
| `6796288d`, `df2c6e9f` | `3ae08e02ec6a` | Memory diagnostics do not solve this mismatch |

`shmap_read` in `dm/gfx/nvn/nvn_mtl.m` appends `/b-DMSH_CHAIN` to
`DM_MSL_DIR`. Set that variable to the **parent** of `b-<chain>` or its `.img`,
not to the archive itself. `shader_load` also checks each reflection's chain.
Renaming an image, symlinking an old image under a new chain, editing JSON, or
changing only the header is not a supported compatibility fix. The chain covers
shader source transformations, ABI and toolchain conventions, not just a path.

The intervening work includes fixed-offset uniform reads bounded by host-side
padding (`e45694b7`), border function-constant specialization (`511a0a2c`),
blend-zero conventions (`0662f9d8`), NativeAOT tool changes and decoder repairs.
Host and shader ABI changes therefore need review together; equal MSL for one
sample is not proof that an entire old archive is interchangeable.

Implemented patches on `codex/zelda-compatibility-review`:

1. `dm/tools/shader_compat.py`: read-only metadata preflight for a folder, image,
   or folder-first partial overlay. It checks library name, game and inputs
   stamps, every base reflection's chain, missing/empty base libraries, and
   explicitly requested shader keys. It models the host's per-file fallback to
   the image even when the folder contains a stamp; this differs from simply
   calling `shader_lib.view`. Folded `gs_slice` geometry needs no base metallib.
   The tool reads the index and metadata and stats library sizes; it never reads
   all library payloads into RAM, compiles, packs, renames or writes the archive.
2. `dm/gfx/tools/dmsh_mtlcache.py`: compiler identity queries now require
   successful, nonempty `xcrun` output for metal, metallib, SDK version and SDK
   build. Previously a failed query's stdout was accepted, allowing an incomplete
   identity to participate in cache reuse. Successful probes produce exactly the
   old identity; install paths remain excluded. Invalid Xcode configuration now
   stops setup of this cache rather than risking reuse. This is a correctness
   safeguard, with no claimed FPS benefit.
3. `test_shader_lib.py`: the production C image-reader harness accepts `CC`,
   otherwise prefers Clang and falls back to `cc`. It uses the original warning
   checks, reader code and assertions. This enables real host-format lookup and
   mapping tests on Linux without pretending to compile Metal.

None of these files changes the computed chain identifier: it remains
`3ae08e02ec6a` on this branch. No header, shader archives, profiles or game assets
were changed. No shader compilation, cache prefill or host build was run.
The preflight is usable from this worktree to inspect an older installation;
it does not make the host built from this worktree compatible with it.

## Portable validation

From the review checkout with the prepared Python environment:

```sh
/workspace/venv/bin/python -W ignore::ResourceWarning -m unittest \
  dm/tools/tests/test_shader_compat.py \
  dm/tools/tests/test_shader_toolchain_cache.py \
  dm/tools/tests/test_shader_lib.py \
  dm/tools/tests/test_nsp_chain.py \
  dm/tools/tests/test_docs.py
```

Result: **84 tests passed**. Thirteen new test methods cover preflight and
compiler-probe failures (including subcases for all four probes). Existing tests
exercise cache invalidation, selected-target compilation, partial image updates,
cut archive rejection, zero-length mappings and the production C reader. The
`No space left on device` line in this suite is an intentional injected-failure
case, not a failure on this machine. Existing ResourceWarnings were filtered in
this combined run; no warnings were repaired by disabling assertions.

Changed-file Ruff and `git diff --check` are required before publishing. The
memory branch's `t_mem_guard.c` also compiled with GCC at O2 with strict warnings
and passed. Its Foundation/ARC lifetime suite executed with **one skipped test**
on Linux; that skip is not a pass. Neither these tests nor metadata preflight validates
Metal entry points, target compatibility, reflection ABI conversion, all side
libraries, pipeline archives or shader-map coverage. Supplying `--key` only
checks the keys explicitly requested; it does not infer game coverage.

Example for the existing archive, run without modifying the installation:

```sh
python3 dm/tools/shader_compat.py /path/to/cache/b-39eb2f781d07.img \
  --chain 39eb2f781d07 --game 0400486024DEC000
```

Add `--inputs <known-profile-inputs-digest>` if available, and repeated
`--key <16-hex-key>` for shaders named in a failing log. Alternatively use
`--host-header /path/to/matching-checkout/dm/gfx/nvn/dmsh_chain.h`.
A header describes a source tree, not the provenance of an arbitrary executable.
Record the actual binary's build revision and expected chain separately.
Exit 0 means metadata checks passed; exit 1 means incompatibility/incompleteness;
exit 2 means the tool could not inspect its inputs. A missing stamp is reported
conservatively: the host may load shaders but rejects derived uniform tables.

## Reuse and safe incremental compilation

Prioritize a host built from a matching `04811a63` checkout and the unmodified
old archive for baseline tests. Backport host-only optimization patches to an
isolated baseline branch only after reviewing their ABI assumptions. Do not
replace the installed executable. A backport is new work, not implemented here.

The current `dmsh_mtlcache.Cache` already keys compiled libraries by exact MSL
bytes, target, compiler identity and compile convention. `fill` accepts earlier
folders/images only with matching per-shader `chain_metal` and `chain_compiler`,
then freshly compiles samples (up to two per stage) and compares library bytes.
Legacy metadata without compiler identity is rejected. Side and tile-readable
libraries are deliberately excluded from ordinary prefill because their source
compile unit differs. These exclusions must remain. Cache reuse does not mean
the old JSON/reflection is loadable by a new host.

`DMSH_PREFILL` and implicit sibling discovery can perform these sample compiles.
Do not invoke prefill as a supposedly read-only diagnostic. Reuse cannot be
quantified until the old archive is inspected for `.metal` source and compiler
metadata, and the Mac compiler is tested. An app-only archive may contain neither
source nor usable provenance. No percentage or time saving is established here.

An explicitly keyed `dmsh_build.py` run is incremental, but it can publish a
replacement image and compile dependency shaders; it is not an in-place-safe
inspection command. If a later approved trial needs compilation:

1. Use a new output/cache root and a preserved copy or APFS clone of any input;
   keep the original archive and app immutable. Confirm disk headroom for copies,
   CAS staging and an image written alongside its predecessor.
2. Select a small key set supplied by Agent 3, with its dependency closure and
   expected outputs. Use `DMSH_TARGETS=mac`, `J=1`, a separate `DMSH_CAS`, and
   omit `IOSOUT`. Confirm the CLI and profile at that exact revision first.
3. Do not graft old-chain untouched shaders into a new-chain image. A partial
   new-chain build has only its generated keys and is not game-complete. The
   builder's same-chain partial-image preservation is separately tested.
4. Audit output chain, stamp, reflection and side-entry requirements, then test
   synthetic dispatches and a Mac route. Do not treat partial stamps or freshly
   edited JSON as evidence of full compatibility.

No full or incremental shader build is authorized by this procedure alone; this
task performed neither. Agent 3 must state whether a patch changes DMSH_CHAIN,
which libraries must be regenerated, and whether the old host can still be used.

## Coordination and review gates

GitHub inspection found only these relevant remote branches at review time:
`zelda-m2-memory-experiments`, `zelda-m2-8gb-optimization`, and
`backup-zelda-before-ai-agents`, plus `main`. The public pull-request page showed
no matching open PRs and the issues page showed no results. Authenticated
GraphQL and REST requests were blocked with HTTP 403 at the CONNECT proxy.
That limits discovery; it does not prove no private or newly published work
exists. Do not assume another task has read this document until its review is
visible on GitHub. Agents 2 and 3 have no identifiable published proposal to
review yet; review them later rather than inventing conclusions.

| Owner / proposal | Review result and dependency | Conflict / next evidence |
|---|---|---|
| Agent 1, `6796288d` | Opt-in logical allocation diagnostics, not memory reduction; weak snapshots and precise-lifetime arrays preserve resources across unlock | `nvn_mtl.m`; Mac compile, Foundation negative controls, real Metal allocation and timer tests required |
| Agent 1, `df2c6e9f` | Corrects the test's second weak declarator; prevents a strong test reference from hiding lifetime failure | Test-only; run both O0/O2 variants on Mac, do not infer Linux ARC validation |
| Existing `02353ca3` | `DM_M2_NO_FULL_POOL` skips full raw-global-pool mapping; shader accesses outside existing chunks can be unmapped | Keep disabled for correctness baseline; potential GPU faults/black screens are not performance wins |
| Agent 2 rendering changes | Pending publication; request exact base, host ABI assumptions and M2 traces | Shares `nvn_mtl.m` with Agent 1; review submission fences, resource retirement and barrier ordering together |
| Agent 3 shader changes | Pending publication; require chain/rebuild declaration and synthetic numerical checks | Owns chain tools/header; MSL/register changes require Mac compile and M2 measurement |
| Agent 4 patches here | Preflight, fail-closed cache provenance and portable reader tests | Agent 3 may edit `dmsh_mtlcache.py`/cache tests; preserve successful identity bytes and coordinate before rebasing |

The full-pool bypass discussed above is implemented only on the experimental
branch, not this checkout. Keep it disabled; do not add it to the active switch
catalog or reintroduce its reader to silence documentation validation.

This patch does not touch residency, command submission, shader rewrites or the
chain header. Its cache change stops a misconfigured compiler sooner; callers
must surface that exception and the Mac must validate genuine tool output.
Treat the unused local memory/render/shader review branches created earlier in
this session as investigation checkpoints only, not other agents' deliverables.

## Safe M2 validation and integration sequence

1. Record macOS/Xcode/Metal versions, host binary revision/chain, game version,
   profile stamp and archive location/size. Keep original assets, archive and app
   untouched. Store the candidate app/host and logs separately. Run metadata
   preflight against the **actual expected chain**, then confirm the host log
   selects that exact archive. A mismatched chain is a stop condition.
2. From a matching source checkout, build only the host using the supported
   host Makefile. First inspect `make -n -C dm/host GAME=0400486024DEC000` and the
   exact revision's instructions for incidental generated host-MSL prerequisites;
   do not run the all-in-one pack/build script or any game shader build. This
   Linux task cannot verify Xcode SDK headers, linking or API availability.
3. Run host/gfx unit tests, reflection and shader-library loading checks on Mac.
   Test the memory branch's Foundation lifetime harness at O0/O2 independently.
   On a separate candidate test failed Xcode probes and a successful tiny synthetic
   MSL cache compile/reuse; verify the recorded compiler identity remains stable.
4. First run the unchanged matching baseline on the actual 8 GB M2. Request
   `DM_FPS_TARGET=30`. Verify internal resolution and presented resolution in logs
   or a capture; a 720p window alone does not force the game's internal targets or
   NDSR output to 720p. Agent 2 must provide a verified Ocarina-specific resolution
   setting. Do not substitute Breath of the Wild's scale recipe.
5. Use the same save, camera and input route (the profile has a `kokiri-deck`
   benchmark route), then test loading, menus, movement/camera, new areas and
   focus loss/return. Validate real pictures, audio and controls. Include warm
   and cold starts, and asynchronous captures: synchronous waits can hide races.
6. Apply one compatible host-only proposal at a time. Compare at least three
   baseline/candidate runs in alternating order, warm-up excluded, then sustain
   gameplay long enough to expose Air thermal throttling and memory growth.
   Record frame p50/p95/p99, late frames relative to 33.3 ms, GPU and CPU submit
   time, waits, peak footprint, swap, memory pressure and thermal state.
   Metal logical allocated bytes, footprint, traffic per frame and archive size
   are distinct metrics; do not add or equate them.
7. Keep memory diagnostics off for performance baselines and enable separately
   for investigation: scanning sets and a 100 ms timer can perturb timings.
   Validate pool lifetimes under area transitions and backgrounding. Stop on
   missing shaders, GPU faults, new red lines, visual errors or unbounded growth.
8. Only after independent Mac validation combine Agent 1/2 patches in a new
   candidate branch with manual review of overlapping `nvn_mtl.m` hunks. Defer
   Agent 3's new-chain changes until a separate compatible shader set and archive
   plan are approved. Follow the repository's five-game regression requirement
   for host/chain changes (choose games by impact); none ran on Linux here.

No hardware result establishes that 720p/30 is achievable on this 8 GB machine.
The profile's virtual reserve and 6.2 GB heap request are not measured resident
RAM, but underline the need to measure combined guest, driver, GPU and OS demand.
No memory or FPS improvement is claimed by this compatibility patch.
