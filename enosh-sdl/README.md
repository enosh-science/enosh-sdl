# ENOSH-SDL — Supervisory Decision Layer (v0.3)

A transparent supervisory decision layer for cost-aware model routing in multimodal AI agents, with a controlled ablation of phase-gated scheduling.

This repository contains the source code, benchmark scenarios, authorization/hazard probes, per-seed results, sweep tables and figure script for the manuscript:

> *ENOSH-SDL: A Transparent Supervisory Decision Layer for Cost-Aware Model Routing in Multimodal AI Agents, with a Controlled Ablation of Phase-Gated Scheduling* (manuscript under review).

> **Important.** All energies are **assumed accounting joules (J\*)** produced by a fixed cost table — not power measurements. "Quality" is the hand-specified proxy c·qₘ(ξ), not measured task success. ENOSH-SDL is a **dry-run** policy engine: it returns recommendations only and never executes tool calls or actuation. Its safety gates are illustrative and are **not** a safety certification.

---

## What it does

ENOSH-SDL takes an already-extracted multimodal observation (text, ASR transcript, vision labels, sensor fields) and:

1. derives an intent estimate and a confidence proxy (token-level cue matching with an explicit Arabic affix list);
2. applies **hard constraints before any optimization** — hazard → `safe_stop_proposed`; deletion, payment, outbound send/publish → `human review`; low confidence → clarification;
3. for eligible requests, selects an inference route (`rule`, `light`, `deep`) by an explicit cost–latency utility, Eq. (1) of the paper;
4. optionally schedules dispatch through a phase-inspired receiver scheduler (delay-coupled oscillators with a bounded receptive gain).

It does **not** decode raw audio or images, run a trained multimodal model, call external tools, or control motors.

## Requirements

- Python **3.10 or newer**
- **No third-party dependencies** for the engine, tests and experiments (standard library only)
- Optional, only to redraw figures: `pandas`, `matplotlib` (see `requirements-figures.txt`)

## Quick start

```bash
git clone https://github.com/<your-username>/enosh-sdl.git
cd enosh-sdl

# 1. Run the test suite (36 tests)
python -m unittest discover -s tests

# 2. Regenerate every number reported in the paper (~2 s)
python -m enosh_sdl.experiments --out results/v0_3

# 3. Optional: start the local dashboard and JSON API
python -m enosh_sdl.server --port 8765
# then open http://127.0.0.1:8765/
```

On Windows you can double-click `Run_Tests.cmd`, `Run_Experiments.cmd` or `Start_ENOSH_SDL.cmd`.

### Redrawing the figures

```bash
pip install -r requirements-figures.txt
python results/v0_3/figures/make_figures.py results/v0_3
```

## Reproducibility

`python -m enosh_sdl.experiments` writes, into `results/v0_3/`:

| File | Content |
|---|---|
| `robustness_60_seeds_v0_3.csv` | Per-seed energy, quality proxy, inference count, wake-ups, mean/p95/max wait and route counts for variants A–F (seeds 0–59) |
| `summary_v0_3.json` | Means, SDs and all paired tests (mean difference, 95% CI, paired *t*, sign test) |
| `benchmark_seed24_v0_3.json` | Reference run (seed 24) with phase-gate statistics |
| `sweep_lambda.csv` | Energy-weight (λᴱ) sensitivity of utility routing |
| `sweep_fixed_period.csv` | Fixed-batching period sweep (300–500 ms) against the phase scheduler |
| `sweep_k.csv` | Coupling sweep: gate activity, D − E and D − F |
| `safety_probes_v0_3.json`, `safety_probes_v02_vs_v03.json` | Probe-level authorization/hazard results |

The run is deterministic: regenerating the results reproduces the committed files byte for byte. The Holm adjustment reported in Table 4 of the paper is applied to the six unadjusted paired-*t* *p*-values in `summary_v0_3.json`.

## Experimental variants

| Variant | Inference policy | Dispatch policy |
|---|---|---|
| A | Always deep for eligible requests | Direct |
| B | Event-only threshold: deep if ξ > 0.52, else light | Direct |
| C | Utility routing, Eq. (1) | Direct |
| D | As C | Phase-gated windows |
| E | As C | Fixed batching, 400 ms grid |
| F | As C | Fixed batching, period and offset matched to D's window grid (408 ms, 384 ms offset at k = 8) |

Workload: 200 events per run drawn with replacement from 20 hand-written Arabic/English scenarios; seeds 0–59; λᴱ = 0.18; k = 8 unless stated.

## Key results (60 paired seeds)

| Variant | Mean J\* | SD J\* | Mean quality proxy | Wake-ups | Mean wait (ms) | p95 wait (ms) |
|---|---|---|---|---|---|---|
| A | 135.960 | 10.963 | 0.865 | = inference | 0 | 0 |
| B | 81.718 | 8.047 | 0.773 | = inference | 0 | 0 |
| C | 55.251 | 5.140 | 0.684 | = inference | 0 | 0 |
| D | 49.402 | 4.688 | 0.684 | 45.50 | 206.02 | 381.54 |
| E | 49.509 | 4.658 | 0.684 | 45.97 | 199.72 | 374.44 |
| F | 49.405 | 4.674 | 0.684 | 45.52 | 203.28 | 379.50 |

- **Routing:** utility routing (C) saves 26.47 J\* versus event-only routing (B) but gives up 0.089 in the quality proxy (−11.5%); the saving is a step function of λᴱ and vanishes for λᴱ ≤ 0.10.
- **Phase-gated dispatch — negative result:** at k = 8 the gate accepts every receiver-cycle crossing, so the scheduler behaves as a 408 ms periodic batcher. Against the period-matched control F the energy difference is −0.004 J\* (95% CI −0.061 to +0.054). Where the gate is active (k = 0), phase scheduling is markedly worse (+5.06 J\*).
- **Authorization/hazard probes:** correct gating rose from 16/32 (v0.2) to 29/32 (v0.3). The three misses are paraphrases with no cue word. Probes and rules share an author, so these scores are optimistic.

See `RESULTS_v0_3.md` for the full analysis.

## Repository structure

```
enosh_sdl/          Engine: fusion (cues, confidence), decision (constraints, utility),
                    scheduler (phase gate, fixed batching), benchmark, experiments,
                    probes, local HTTP server, optional Ollama adapter
tests/              Unit tests (36)
examples/           Sample observations (JSON)
results/            Reference outputs; results/v0_3 holds all paper results and the figure script
paper_figures/      Figures 1–7 as they appear in the manuscript (300 dpi PNG)
index.html          Browser dashboard (served on localhost)
ARCHITECTURE_EN.md  Interface and research specification
RESULTS_v0_3.md     Full v0.3 results
README_AR.md        Arabic user guide
CHANGELOG.md        Version history
```

Figure numbering: `results/v0_3/figures/fig4…fig7` correspond to manuscript Figures 6, 4, 5 and 7 respectively.

## API (local only)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Server status and version |
| `/api/examples` | GET | The 20 benchmark scenarios |
| `/api/decide` | POST | Route and proposed action for one observation |
| `/api/batch` | POST | Batch of up to 100 observations |
| `/api/benchmark` | POST | Compare policies and schedulers |

The server binds to `127.0.0.1`. The optional Ollama adapter talks only to a locally installed model at `127.0.0.1:11434`; its output is treated as an untrusted hint and cannot override the hazard or authorization constraints. No model was invoked in any experiment reported in the paper.

## Limitations

- Energy, latency and quality coefficients are set by hand; nothing is trained or calibrated on real task outcomes.
- The 20 scenarios and 32 probes were written by the author; results describe behaviour under an assumed workload, not generalization.
- Proposing a stop is not stopping a robot. Emergency stopping on physical hardware must rely on a separate certified interlock.

## Citation

If you use this software, please cite it using the metadata in `CITATION.cff` (GitHub shows a "Cite this repository" button). After the archival DOI is minted on Zenodo, cite that DOI.

## License

Released under the MIT License — see `LICENSE`.
