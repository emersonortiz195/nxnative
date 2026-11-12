# M2 memory diagnostics experiment

Enable on macOS with `DM_NVN_MEMORY_GUARD=1`. The default is off; iOS is
unchanged. This is diagnostic only: estimated thresholds never abort, evict,
skip commits or persistently retain resources. It is not a demonstrated fix for a
driver failure.

Before a residency commit, sum each live allocation identity once across the
committed snapshot and pending set. Repeated adds and remove/re-add before commit
do not count twice. Pending removals remain counted while alive until commit;
after commit the cached total reflects the pending set alone. Persistent weak snapshots do
not retain resources. During a commit, precise-lifetime strong arrays pin both
scanned sets until after the residency mutex is unlocked; a pool around the
whole call then drains weak-table temporaries, including snapshot maintenance.
This bounds temporary ownership even on guest threads and lets final-release
heap-owner callbacks safely re-enter residency removal. Placement textures are represented by their owning heaps.
Distinct overlapping no-copy buffers still count separately: these logical
allocation totals are not unique physical memory or process footprint.

Warn once when logical bytes reach 95% of Metal's recommended working set, or
when approximate system headroom falls below 1024 MiB. A 100 ms timer reads the
cached total without renderer locks. `kern.memorystatus_level` is an integer
percentage estimate, not exact available bytes; multiplying it by `hw.memsize`
only gives a coarse estimate. Invalid readings disable that check and warn once.
Initialization failures warn and leave any available commit checks active.

Open limitations: allocations precede checks; other residency sets and classic
Metal work are outside the total; freed objects disappear from weak snapshots;
timer delivery may be delayed. These diagnostics cannot guarantee avoidance of
OOM, driver hangs or kernel panics.

CPU tests: `make -C dm/gfx/tests GAME=01007EF00011E000 check_t_mem_guard`.
They cover accounting transitions, threshold boundaries, invalid readings and
saturating addition, and are included in CI's CPU test list. Mac Objective-C
compilation, synthetic Metal allocation checks, timer checks and gameplay
regressions remain unvalidated. No game builds or gameplay validation were
performed here.

Lifetime regression: `python3 -m unittest dm/gfx/tests/test_mem_guard_lifetime.py`
requires macOS Foundation (no Metal device or game). It compiles the actual
`res_commit()` body with synthetic allocations at `-O0` and `-O2`, checks
destructor lock re-entry and dirty-state preservation for both scans, and checks
that snapshot insertion leaves no ownership in an outer guest-thread pool. It
also checks the disabled path. This test is skipped on Linux; its macOS run is
still required, along with the Metal and gameplay checks above.
