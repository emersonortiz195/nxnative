# Zelda on M2 Air (8 GB): community stability investigation

We are testing GPU-memory and Metal-rendering optimizations in a public fork of [nxnative](https://github.com/seedds/nxnative). This page contains **code references and sanitized performance observations only**. No game files, game images, shaders extracted from the game, saves, personal paths, or private system logs are included.

## Hardware and reproducible symptom

- Apple Silicon M2 MacBook Air, 8 GB unified memory.
- A native test build of a Zelda remake approached 29–30 FPS in a scene, but later developed multi-second frame stalls and terminated.
- Sampled log observations: frame ~7525 took ~8.66 s, including ~8.13 s submit/present; an earlier overlay showed GPU allocations near ~5.1 GB. These counters are not proof of a memory leak or OS out-of-memory termination.
- The launcher reported signal 9 (SIGKILL). The source of that signal is **not confirmed**.
- No new shader pipelines were being compiled during the worst observed frame stalls, so the immediate focus is GPU allocation/retirement, residency, texture uploads, and Metal synchronization.

## What we would appreciate help with

1. Can anyone identify whether the apparent Metal allocation and residency growth is expected, cumulative accounting, or a genuine retention/retirement bug?
2. What tools/counters reliably distinguish submit/present waiting on GPU completion from CPU lock contention or OS memory pressure on an 8 GB Apple Silicon Mac?
3. Which current upstream/community fixes for texture recycling, alias ownership, upload staging budgets, and delayed resource retirement are safe to adapt?
4. Are there known pitfalls in pooling shared Metal resources or changing command-buffer residency sets that could cause rendering corruption?

## Public source and plans

- [Our nxnative fork](https://github.com/emersonortiz195/nxnative)
- [Phase 5 community-informed stability plan](https://github.com/emersonortiz195/nxnative/blob/codex/zelda-phase5-community-stability/docs/agents/zelda-phase5-community-stability.md)
- [Phase 4 GPU memory proposal](https://github.com/emersonortiz195/nxnative/pull/5)
- [Phase 4 Metal proposal](https://github.com/emersonortiz195/nxnative/pull/6)
- [Phase 4 shader proposal](https://github.com/emersonortiz195/nxnative/pull/7)
- [Phase 4 QA proposal](https://github.com/emersonortiz195/nxnative/pull/8)

Our next step is **small, separately tested source-code changes** based on current upstream/community work. The Phase 4 proposals are not being presented as validated Mac stability fixes.

We welcome code review, suggestions, and pointers to existing upstream commits. Please keep discussion focused on code and performance; **do not request, share, or link to copyrighted game dumps or proprietary game assets**.
