# Phase 4 shader cache coordination

Agent 3, November 12, 2026. Target: Apple M2 MacBook Air, 8 GB unified memory,
approximately 720p/30 FPS. Branch `codex/zelda-phase4-shader` is based on Phase 3
`17020e5403ceec9aeeff756c6e7047f9d2d2f945` (draft PR #4), not on the memory
experiment. This proposal changes build-time cache coordination only.

## Change and evidence

The [reference entry](../reference/shaders.md#concurrent-cache-misses-compile-the-same-metal-source-repeatedly)
holds the cause and fix. Parallel shader workers could all observe an absent
MSL-keyed Metal library and then compile that identical source independently.
The existing cache already promises byte-identical output for a given source,
compiler, target and flags. Per-entry coordination now rechecks the store after
waiting for that same entry's producer, so successful publication makes the
waiters ordinary cache hits. Hot-cache hits retain their original fast path.

Coordination applies to workers sharing **one Cache instance**. It does not
deduplicate separate instances, separate processes, prefill validation samples
or runtime Metal pipeline compilation. The entry registry retains no completed
keys: the last producer/waiter removes its lock. No Store/global lock is held
while compiling. Different source/target keys remain parallel. Failure releases
the entry; the original compiler exception reaches its caller, while a waiting
caller can compile normally. If a full/nonpersistent cache cannot publish,
waiters must compile rather than assume publication succeeded; identical
requests are then serialized, potentially increasing build time.

The existing `compile_split` contract (one source always splits the same way)
is preserved. This patch neither changes that API's format nor permits arbitrary
mixing of whole-library and differently split uses of the same source. Cache
paths, FORMAT, source hashing, compiler/SDK identities and compile flags remain
unchanged. Shader-chain files and header remain unchanged, computing
`3ae08e02ec6a`. Existing verified archives require no rebuild for this change.
No app, real archive, game data or profile inputs were modified or deleted.
`DM_M2_NO_FULL_POOL` remains absent/disabled, as on Phase 3.

## Tests

All commands ran in the isolated worktree using `/workspace/venv/bin/python`.
Scratch is under `work/`; no real shader compilation or game build ran.

```sh
python -W ignore::ResourceWarning -m unittest \
  dm/tools/tests/test_metal_cache_concurrency.py \
  dm/tools/tests/test_shader_toolchain_cache.py \
  dm/tools/tests/test_shader_cache.py dm/tools/tests/test_shader_pch.py \
  dm/tools/tests/test_nsp_chain.py dm/tools/tests/test_shader_compat.py \
  dm/tools/tests/test_shader_lib.py dm/tools/tests/test_docs.py
```

**132 discovered: 124 passed, 8 skipped**, no errors/failures before adding this
report; documentation checks are rerun after its addition. The eight skips need
Xcode/Metal. The injected full-disk `[RED]` in archive tests is expected.
Changed-file Ruff and `git diff --check` pass.

Full tool discovery was attempted with `DM_GAME=0400486024DEC000` and `DM_ROOT`
under scratch: **1,406 discovered, 15 failure records, 37 errors, 70 skipped**.
It is not a passing suite. Failures match the Phase 3 categories (macOS
libraries/tools and copy/device assumptions, GCC warnings in an unrelated
synthetic reader, and an inode-reuse test assumption). Seven new tests add to
Phase 3's 1,399 discovered count. Full shader translation/gameplay and native
Metal/host suites are not available on this Linux executor. The Python lint
ratchet still reports the inherited unchanged `dmsh_entry.py` unused import
and three locally resolved imports remaining in the baseline; this patch adds
no Ruff/Pyright finding. No baseline or chain-hashed tool was edited to hide it.

Seven new concurrency tests cover ordinary/split misses, independent-source
and independent-target parallelism, compiler failure and waiter recovery,
nonpersistent-cache output, split failure/cleanup, and empty registry afterward.
They use a barrier on the first store lookup, forcing all eight requests to
observe a miss before a producer can finish; no scheduler sleeps are used.
Running the first two tests against Phase 3's original cache produces exactly
eight synthetic compiler calls for each API and fails their one-compile
assertions. The fixed cache produces exactly one compile and seven cache hits,
with all ordinary output bytes and all three split pieces preserved.

Those compiler invocation counts are a measured **synthetic** result. No actual
M2 compilation time, compiler peak memory, cache reuse percentage, runtime shader
stall, gameplay FPS or process footprint has been measured. Reduced build CPU
and peak memory from avoiding duplicate compilers are hypotheses, not numbers.

## Mac validation without a full shader rebuild

Follow [Phase 3's setup and preservation gates](zelda-phase3-integration.md).
With its arm64 Python and selected Xcode 27.2, run the test command above. The
PCH tests then exercise the actual Metal compiler on tiny synthetic sources,
including source-name independence; the cache concurrency tests still use
synthetic compiler bytes to force concurrency deterministically. Confirm
`python3 dm/gfx/tools/dmsh_chain.py` remains `3ae08e02ec6a`. Do not run a full
game build or import/prefill the user's preserved archive just to validate this
coordination change; prefill can compile samples and write cache records.

Before integration, owners with disposable cache/build outputs may compare a
small, fixed set of already-owned shader sources under baseline/candidate at
the same worker count, cold temporary cache and identical toolchain. Compare
every metallib byte, actual compiler invocation counts, elapsed/CPU time and
peak compiler-process memory, then repeat warm-cache hits. Never clear the
system shader cache or delete an existing game build to make a cold test.
Report no gain where sources do not duplicate or cache persistence fails.

The impacted five-game candidates are Ocarina of Time and Pokopia (large Ampere
NVN sets), Breath of the Wild and Tears of the Kingdom (shared pixel-source
workloads), and Super Mario Bros. Wonder (a smaller Maxwell NVN regression).
Their IDs are `0400486024DEC000`, `0400A3A01EE4C000`, `01007EF00011E000`,
`0100F2C0115B6000`, `010015100B514000`. None has game files/builds mounted here.
`regress.py impact` cannot run in this branch on Linux because it imports
`/usr/lib/libproc.dylib`; parent Agent 4 is addressing that separate QA issue.
No five-game regression or gameplay pass is claimed.

## Integration status

Ready for independent review and isolated tiny Mac tests as a draft, not a merge
approval. Integrate after PR #4; the only executable production diff is
`dm/gfx/tools/dmsh_mtlcache.py`, outside the shader chain. No renderer/host code
changed. Additive documentation links in the common game note/symptom index may
need combining with other Phase 4 reports; retain each separate finding.
Remaining gates are actual Mac tool tests, controlled small-source byte/memory
comparisons, relevant game-owner regression evidence and CI review. No lengthy
shader rebuild is initiated or required by this proposal.
