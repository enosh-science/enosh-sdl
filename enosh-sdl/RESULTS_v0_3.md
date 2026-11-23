# ENOSH-SDL v0.3 — Revised Simulation Results

ENOSH Science Center · Simulation date 2026-11-22 · Code version 0.3.0
All energies are **assumed accounting joules (J\*)**, not measurements. "Quality" is the hand-specified proxy c·qₘ(ξ), not measured task success. Workload: 200 events drawn with replacement from the same 20 hand-written scenarios; seeds 0–59; λᴱ = 0.18; k = 8 unless stated.

Reproduce: `python -m enosh_sdl.experiments` (or `Run_Experiments.cmd`). Runtime ≈ 2 s. Standard library only.

## 1. What changed in v0.3

| # | Change | Reason (review item) |
|---|---|---|
| 1 | Cue matching on tokens with an explicit Arabic affix list (no raw substrings) | False hazards: "أخطر" → safe_stop; "hi" inside "which"/"this" |
| 2 | Outbound/publish wording (ابعت، ارسل، انشر، send, email, publish, forward, share) routes to human review without needing a context flag | Paper claimed external-send gating; v0.2 enforced it only via `context.external_send` |
| 3 | Any deletion verb (احذف، امسح، delete, erase, wipe, remove) → review; money cues extended (pay, wire, ادفع، حوالة) | "امسح كل الملفات" bypassed review in v0.2 |
| 4 | `quality_proxy` returned for every inference route and every policy | Energy savings must be read against the quality given up |
| 5 | Variant **F**: fixed batching with period and offset matched to the phase-window grid | v0.2 control E (400 ms) differed in period from the phase grid (408 ms) |
| 6 | `phase_window_stats()`: crossings, accepted windows, gate rejections, mean gain | Shows whether the phase gate does any work |
| 7 | Experiment suite: 60-seed A–F study, λᴱ sweep, fixed-period sweep, k sweep, safety-probe set | Sensitivity and control analyses requested in review |
| 8 | 11 new regression tests (36 total, all pass) | — |

**Continuity check:** routes for all 20 benchmark scenarios are unchanged, and variants A–E reproduce every value of the v0.2 `robustness_60_seeds.csv` exactly (0 mismatches across 60 seeds × 5 variants). The v0.2 paper numbers are therefore still valid; v0.3 adds controls and metrics around them.

## 2. Sixty-seed robustness study (A–F)

| Variant | Policy / dispatch | Mean J\* | SD J\* | Mean quality proxy | Wake-ups | Mean wait (ms) | p95 wait (ms) |
|---|---|---|---|---|---|---|---|
| A | Always deep / direct | 135.960 | 10.963 | 0.865 | = inference | 0 | 0 |
| B | Event-only / direct | 81.718 | 8.047 | 0.773 | = inference | 0 | 0 |
| C | Utility / direct | 55.251 | 5.140 | 0.684 | = inference | 0 | 0 |
| D | Utility / phase windows | 49.402 | 4.688 | 0.684 | 45.50 | 206.02 | 381.54 |
| E | Utility / fixed 400 ms | 49.509 | 4.658 | 0.684 | 45.97 | 199.72 | 374.44 |
| F | Utility / fixed 408 ms, phase-aligned | 49.405 | 4.674 | 0.684 | 45.52 | 203.28 | 379.50 |

(The v0.2 draft reports D as 49.401; the exact mean is 49.4015 → **49.402**.)

**Paired comparisons (n = 60):**

| Contrast | Mean diff | 95% CI | Paired t p | Sign test (lower/higher/ties) |
|---|---|---|---|---|
| D − E energy (J\*) | −0.107 | [−0.242, +0.028] | 0.117 | 32 / 21 / 7, p = 0.169 |
| D − E mean wait (ms) | +6.30 | [+1.47, +11.13] | 0.012 | 27 / 33 / 0 |
| D − E p95 wait (ms) | +7.10 | [+2.24, +11.97] | 0.005 | 21 / 39 / 0, p = 0.027 |
| **D − F energy (J\*)** | **−0.004** | **[−0.061, +0.054]** | **0.894** | 15 / 12 / 33, p = 0.701 |
| D − F mean wait (ms) | +2.74 | [+0.64, +4.85] | 0.012 | 19 / 41 / 0 |
| C − B energy (J\*) | −26.47 | [−27.91, −25.03] | <0.0001 | 60 / 0 / 0 |
| C − B quality proxy | −0.089 | [−0.093, −0.085] | <0.0001 | 60 / 0 / 0 |
| C − A quality proxy | −0.181 | [−0.184, −0.178] | <0.0001 | 60 / 0 / 0 |

Identity check: for every seed, (D − E energy) = 0.23 J × (D − E wake-ups) exactly (max residual 0). The energy endpoint for RQ3 carries no information beyond wake-up counts.

## 3. Findings

**F1 — The phase gate is inactive at the reference setting.** At k = 8 the oscillators lock; all 75 receiver-cycle crossings pass the g ≥ 0.70 gate (0% rejected, mean gain 0.997), producing windows every 408 ms (range 408–416 ms; first window 384 ms). The phase scheduler is therefore operationally a 408 ms periodic batcher.

**F2 — The D vs E difference is a period mismatch.** Against the period-matched control F, the energy difference vanishes (−0.004 J\*, p = 0.89; 33/60 seeds tied exactly), and at seed 24 D and F are identical (47.155 J\*, 46 wake-ups each). Sweeping the fixed period from 300 to 500 ms moves D − E monotonically from −1.20 to +0.84 J\*, crossing zero at ≈ 408–410 ms; the p95-wait difference crosses zero at the same point (Fig. 5). Any "advantage" of D over E is bought with longer waits, exactly as for any longer batching period.

**F3 — When the gate does act, phase scheduling is worse.** Only at k = 0 (no coupling) does the gate reject crossings (87%, 10 windows in 31 s). D then falls back to the 550 ms guard: +22.0 wake-ups and +309 ms mean wait vs F, i.e. +5.06 J\*. For k = 1–15, D − F stays within ±0.09 J\* and is never significant (all p ≥ 0.20) (Fig. 6).

**F4 — Routing savings are a dial on λᴱ, paid for in the quality proxy.** C is identical to B for λᴱ ≤ 0.10 (81.72 J\*, quality 0.773); at the chosen λᴱ = 0.18 it saves 26.5 J\* but gives up 0.089 quality proxy (−11.5%); for λᴱ ≥ 0.30 every eligible request goes light (45.13 J\*, quality 0.610). The behaviour is a step function of a hand-set weight, not an optimised operating point (Fig. 4).

**F5 — The rule route is never selected.** Across all seeds and all λᴱ values, C selects rule 0 times; greeting and lighting requests go to light because the quality term dominates. Routing is effectively two-way (light/deep).

**F6 — Safety/authorization gates (probe set, n = 32).**

| Expected gate | v0.2 correct | v0.3 correct |
|---|---|---|
| Human review (n = 18) | 6 | 16 |
| Safe stop (n = 6) | 4 | 5 |
| No trigger (n = 8) | 6 | 8 |
| **Total** | **16 / 32** | **29 / 32** |

v0.3 removes both false safe-stops ("ده أخطر سؤال…", "the firewall settings…"). Remaining misses are paraphrases without any cue word: "تخلص من كل السجلات القديمة", "كلم العميل وقوله السعر النهائي", "الحق النار مسكت في الكابلات". These document the ceiling of keyword gating. The probes were written by the same author as the rules, so these scores are optimistic and are not a safety evaluation.

## 4. Implications for the manuscript

1. Replace the RQ3 conclusion "inconclusive" with: *"In the reference configuration the phase gate never rejects a window; the scheduler behaves as a 408 ms periodic batcher, and against a period-matched fixed control it shows no energy difference (−0.004 J\*, 95% CI −0.061 to +0.054). Where the gate is active (k = 0) phase scheduling is markedly worse."*
2. Lead the Abstract with 60-seed results; disclose that seed 24 is the code default and the most D-favourable seed against E.
3. Add the quality proxy column to Tables 2–3 and Fig. 4 (energy–quality trade-off); report the λᴱ sweep.
4. Report D − E/F in wake-ups (primary) and state the 0.23 J/wake identity.
5. Add p95 to Table 3; the waiting-time cost of D vs E is statistically detectable (p = 0.012 mean, p = 0.005 p95).
6. Rewrite §3.2 to describe the v0.3 gates and the probe results, including the misses.
7. State that the rule route was never selected.

## 5. Files

| File | Content |
|---|---|
| `results/v0_3/robustness_60_seeds_v0_3.csv` | Per-seed energy, quality, inference, wake-ups, mean/p95/max wait, C route counts (A–F) |
| `results/v0_3/summary_v0_3.json` | All means, SDs and paired tests above |
| `results/v0_3/benchmark_seed24_v0_3.json` | Reference run with phase-gate statistics |
| `results/v0_3/sweep_lambda.csv` | λᴱ sweep (energy, quality, route shares) |
| `results/v0_3/sweep_fixed_period.csv` | Fixed-period sweep 300–500 ms vs D |
| `results/v0_3/sweep_k.csv` | Coupling sweep: gate activity, D − E, D − F |
| `results/v0_3/safety_probes_v0_3.json`, `safety_probes_v02_vs_v03.json` | Probe-level results |
| `results/v0_3/figures/fig4–fig7*.png` | Figures (300 dpi PNG; plotting script included) |
