# ENOSH-SDL v0.3: interface and research specification

## State transitions

1. Ingest normalized observation: `{domain, text, audio:{transcript,confidence}, vision:[labels], sensors:{...}, context:{...}}`.
2. Derive a **low-fidelity heuristic** intent and confidence. Optionally invoke local Ollama to supply a semantic hint (no actions permitted).
3. Apply non-optimizable constraints: hazard → `safe_stop_proposed`; irreversible/external-send → `review`.
4. Apply contextual policy: respect speaker turn and requested preconditions; ask for clarification when uncertainty is high.
5. For eligible intents, select `rule`, `light`, or `deep` by a hand-specified utility score.
6. Return a **plan only** (no tool execution); include rationale, confidence, assumed energy, latency, scores.
7. Benchmark optional phase-vs-fixed sending scheduler, preserving safety bypass and max wait.

## Prototype decision objective

For model selection `m` among {rule, light, deep}, the illustrative uncalibrated score is:

`U(m|o) = 3·p_proxy(success|intent,confidence,m) - 0.005·latency_ms(m) - λE·energy_j(m)`

`argmax_m U(m|o)` is used only after hard constraints and contextual decision rules.

The utility is NOT based on measured or validated probability predictions. The λ weights are not optimized with real workloads. Future work: fit performance estimates to held-out task data, calibrate model uncertainty and risk, and account for energy at the device level.

## Phase gate

The phase delay and receiver-gain proxy follow the structure of Mansour (2026), Eq. (1),(2),(4):

`delta_ij = wrap(theta_j(t-tau) - theta_i(t) - alpha_ij)`

`g(delta) = exp(kappa*(cos(delta)-1))`

An *additional engineering design assumption* says that sending can be batched at a receiver-cycle crossing when gain exceeds the threshold; max wait is 550 ms. The comparison control dispatches every 400 ms. Neither model implies neural consciousness or improved semantic inference. Safety is never batched.

## Ports and interfaces

- Runs on 127.0.0.1:8765 by default, JSON over HTTP.
- `/api/decide` supports `backend=heuristic` and `backend=ollama` plus `model=<installed model tag>`.
- The optional Ollama adapter talks ONLY to 127.0.0.1:11434; it does not authorize tool calls.
- No MCP server, A2A implementation, cloud integration, microphone capture, image encoder, or actuators are included in v0.3. They are integration targets, not shipped features.

## Research concerns

- Phase-gated scheduling is **not** the same as information-theoretic integration.
- Energy is from accounting assumptions, not battery measurements.
- The corpus is 20 hand-written examples with repeated samples; apparent gains are not robust external measurements.
- Textual matching and optional generative classification are not validated comprehension.
- No safety-critical use; emergency behavior here is an advisory object, not an interlock.
