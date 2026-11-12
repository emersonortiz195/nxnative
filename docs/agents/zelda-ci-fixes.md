# PR #1 CI fixes: switch catalog and pollwait fixture

Review of [run 43258379972](https://github.com/emersonortiz195/nxnative/actions/runs/43258379972),
on PR #1 head `9fe4ab09`. Linux-only diagnosis and portable validation.
The reported native failure is `t_pollwait` terminated by `Alarm clock: 14`.
GitHub API log/retry requests return proxy HTTP 403; the public job page is
readable but its raw log endpoint returned 404. The native failure text is the
user-supplied report, not a locally reproduced Mac execution.

## Switch catalog

Running `python dm/tools/env_switches.py --check` reproduced the missing catalog
row and meaning for the implemented `DM_NVN_VCONV_KEEP` reader in `vk_min`.
Regenerating the catalog added exactly one row. Its documented values now match
the code: unset/1 selects a 4096-vertex minimum, 0/negative disables, and larger
positive values select the minimum. The cache has a 256 MiB bound and 600 idle
submission retirement policy. The rendering reference records the same values.

Unread-switch diagnostics are advisory, not the exit-1 cause in this checker.
Historical/fork references remain evidence, not active settings: copy absorption
was removed, the larger view cache belongs to a fork, the reclaim experiment is
not implemented here, and the early-cut experiment was removed. Notes now make
the reclaim/early-cut status explicit. The Zelda reports clarify that the unsafe
full-pool bypass exists only on its experimental branch. It remains disabled;
no reader or catalog row was added to activate it.

## Pollwait watchdog diagnosis and correction

`t_pollwait` explicitly freezes `now_ns()` and advances it only for scenario
steps, keeping the poll-run/gap policy independent of CI descheduling. However,
the included production `sleep_precise` also sees that frozen clock, while the
fixture formerly called real `nanosleep`. Every guest sleep above its 20 us
margin consequently executes all 16 bounded attempts: no clock progress is
visible inside the helper. For a requested 300 us, it asks for 225 us 16 times,
3.6 ms in total before OS scheduling/slack, rather than observing elapsed time.
Hundreds of these sequences can consume the 20-second watchdog under CI load.
This is a confirmed fixture timing defect, not evidence of a production lost
wakeup. Whether it fully explains this particular Mac failure requires rerunning
the native job; another synchronization problem cannot be excluded from Linux.

The fixture now records guest nanosleep requests without executing wall-clock
sleeps. That matches the test's explicit policy clock; production host code is
unchanged. Added assertions ensure sleep scenarios still request sleeps, so the
test cannot pass simply by dropping the sleep path. Real condition-variable
timeouts, the signal-wait handoff, `SignalProcessWideKey`, mutex ownership and
backoff boundary assertions remain in place. `alarm(20)` is unchanged. Unbuffered
stdout preserves the last completed scenario if the watchdog fires again.

The new portable `test_pollwait_fixture.py` compiles the actual production
`sleep_precise` body with the fixture's adapter. A forbidden-wall-sleep sentinel
fails if that adapter calls the OS. Assertions demonstrate all 16 attempts,
their requested nanoseconds, the unchanged policy clock and the no-sleep
20 us boundary. This is not a substitute for the full Mach-dependent test.

## Validation and remaining gates

From the isolated fix checkout:

```sh
/workspace/venv/bin/python -W ignore::ResourceWarning -m unittest -v \
  dm/tools/tests/test_env_switches.py \
  dm/tools/tests/test_pollwait_fixture.py \
  dm/tools/tests/test_docs.py \
  dm/tools/tests/test_shader_compat.py \
  dm/tools/tests/test_shader_toolchain_cache.py \
  dm/tools/tests/test_shader_lib.py \
  dm/tools/tests/test_nsp_chain.py
```

The combined run passed **86 tests**, with no failures/errors/skips, including a
rerun after documentation edits. The archive suite's
full-disk case is deliberately injected. Existing ResourceWarnings were filtered.
Changed-file Ruff and whitespace checks pass. The full local Python lint ratchet
(`PATH=/workspace/venv/bin:$PATH python dm/tools/lint_python.py --against origin/main`)
still exits 1: `dmsh_entry.py:7` has an unused `dmsh_fetch` import (also present on
main), and three baseline entries for missing backports imports are now resolved
in this Python 3.12 environment but still listed. These are not findings in the
new test. No shader tool or baseline was edited to hide them: `dmsh_entry.py`
participates in the chain hash and cannot be changed under this task's explicit
chain-preservation constraint. This local ratchet failure does not establish the
result of the fresh Python 3.14 CI lint job.

No native `t_pollwait`, Metal or
gameplay pass is claimed on Linux.

Native follow-up, on the CI Mac using the workflow's Xcode and profile:

```sh
make -C dm/host/tests GAME=010015100B514000 build/t_pollwait
dm/host/tests/build/t_pollwait
make -C dm/host/tests GAME=010015100B514000 -j3 run
```

Confirm the exact output path in that revision's Makefile (B defaults to build).
Repeat the native test under normal and concurrent CI load; the real signal
case must still reacquire its mutex, and all PASS scenarios must finish before
the unchanged alarm. Review the new workflow run before declaring the original
timeout resolved. If it persists, unbuffered progress localizes the stalled case
and a Mac thread backtrace is the next diagnostic, not a larger timeout.

No shader-chain file or tool was changed. This branch still computes
`3ae08e02ec6a`, as PR #1 already did; the user's existing `39eb2f781d07` archive
and its compatible host were not altered. Neither identifier was rewritten and
no shaders were compiled or rebuilt. These CI fixes make no M2 memory/FPS claim.

Coordination: remote heads were checked before editing; no newly published agent
changes overlapped these files. The fix branch derives from PR #1's head. Only
ordinary fast-forward pushes may update its existing source branch; a changed
remote head must be reviewed before retrying, never overwritten or force-pushed.

The fixes were published as `a70a4864` on `codex/zelda-ci-fixes` and fast-forwarded
onto `codex/zelda-independent-cross-review`, updating PR #1 without a merge or
force-push. The PR checks page confirmed that head and fresh workflow runs. Host,
tool and build jobs were queued/in progress at inspection, not validated passes.
New run links: [tests](https://github.com/emersonortiz195/nxnative/actions/runs/43293263685),
[Python lint](https://github.com/emersonortiz195/nxnative/actions/runs/43293263535),
[C lint](https://github.com/emersonortiz195/nxnative/actions/runs/43293263741).
The explicit `gh run rerun 43258379972 --failed` request was blocked by the API
proxy; the PR synchronization event independently started the new workflows.
Review those results before calling the reported Mac timeout fixed.
