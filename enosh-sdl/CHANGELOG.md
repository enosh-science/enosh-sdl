# Changelog

## 0.3.0 — 2026-11-22
- fusion: token-level cue matching with explicit Arabic affix list; extended delete/send/money cues; `outbound_request` flag.
- decision: outbound/publish wording triggers human review; `quality_proxy` reported for every inference route.
- scheduler: `phase_window_stats()`, `matched_grid()`, `fixed_offset`; defaults reproduce v0.2.
- benchmark: variant F (period-matched fixed batching), quality, p95/max wait, phase-gate metadata, decision memoisation.
- experiments: 60-seed A–F study, λᴱ / fixed-period / k sweeps, safety-probe set (`probes.py`).
- tests: 36 (11 new). A–E outputs identical to v0.2.
