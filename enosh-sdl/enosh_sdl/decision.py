"""ENOSH-SDL v0.3: policy engine, dry-run only; costs are hypothetical."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
from typing import Any
from .fusion import fuse

# Not power measurements; synthetic joules per stage for controlled comparisons.
ENERGY_J={'sense':0.016,'safety':0.006,'semantic':0.035,'rule':0.015,
          'light':0.12,'deep':1.45,'clarify':0.04,'human_review':0.06,
          'safe_stop':0.045,'send':0.035,'wakeup':0.23}
LATENCY_MS={'ignore':3,'rule':12,'light':40,'deep':190,'clarify':30,
            'review':20,'safe_stop':8,'wait':5}

COMPLEXITY={'greeting':0.12,'switch_light':0.14,'request_quote':0.40,
            'request_booking':0.48,'fetch_cup':0.72,'new_fact':0.67,
            'question':0.82,'conversation':0.70,'other':0.90}

def route_quality(route:str, complexity:float)->float:
    """Hand-specified, uncalibrated quality proxy q_m(xi). Not measured task success."""
    return {'rule':0.75-0.46*complexity,'light':0.93-0.53*complexity,
            'deep':0.985-0.12*complexity}[route]

@dataclass
class Decision:
    domain: str
    intent: str
    route: str
    proposed_action: str
    execution_status: str
    requires_approval: bool
    confidence: float
    expected_energy_j: float
    expected_latency_ms: float
    utility: float | None
    rationale: list[str]
    evidence: dict[str,Any]
    candidate_scores: dict[str,float]
    quality_proxy: float | None = None
    note: str = 'SIMULATION / DRY RUN — no tools or actuators executed.'

    def to_dict(self) -> dict[str, Any]:return asdict(self)


def decide(obs: dict[str, Any], *, energy_weight: float=0.18, policy: str='sdl') -> dict[str,Any]:
    if not isinstance(obs,dict):raise ValueError('Observation must be a JSON object.')
    if not math.isfinite(energy_weight) or not 0<=energy_weight<=2: raise ValueError('energy_weight must be finite in [0,2]')
    if policy not in ('sdl','always_deep','event_only'):raise ValueError('Unknown policy')
    f=fuse(obs)
    domain,intent,conf=f['domain'],f['intent'],f['confidence']
    ctx=f['context']; cues=f['cues']
    rationale=[]; scores={}; approval=False
    route='ignore';action='none'
    # Hard constraints: apply to EVERY policy, including the always-deep baseline.
    if f['hazard']:
        route,action='safe_stop','propose_emergency_stop'
        rationale=['Safety circuit has precedence over model routing and temporal gating.']
    elif intent=='high_impact' or bool(ctx.get('high_impact',False)):
        route,action,approval='review','draft_for_human_approval',True
        rationale=['Potentially irreversible/high-impact instruction; no autonomous execution.']
    elif bool(ctx.get('external_send',False)) or bool(ctx.get('publish',False)) or f.get('outbound_request',False):
        # v0.3: the gate also fires on outbound/publish wording, not only on a context flag.
        route,action,approval='review','draft_for_human_approval',True
        rationale=['External send/publish actions require explicit approval in this prototype.']
    elif intent=='noise' or (not f['evidence']['text'] and not f['evidence']['audio_transcript'] and not f['vision_tags'] and not f['evidence']['sensor_keys']):
        route,action='ignore','none'
        rationale=['No actionable information detected.']
    elif domain=='presenter' and bool(ctx.get('guest_speaking',False)) and not bool(ctx.get('turn_available',False)):
        route,action='wait','wait_for_speaking_turn'
        rationale=['Guest is speaking; suppress interruption unless an independent safety event occurs.']
    elif domain=='robot' and intent=='fetch_cup' and (cues['water'] or bool(ctx.get('liquid_present',False))):
        route,action='clarify','request_confirmation_of_liquid_state'
        rationale=['Conditional instruction depends on liquid detection; vision tags alone cannot establish it safely.']
    elif intent=='fetch_cup' and not f['vision_tags']:
        route,action='clarify','request_visual_confirmation'
        rationale=['Requested object cannot be located from the supplied observations.']
    elif conf<0.50:
        route,action='clarify','ask_for_clarification'
        rationale=['Low confidence; do not route a guess to an action tool.']
    elif domain=='presenter' and intent in ('conversation','greeting'):
        route,action='wait','listen_and_log'
        rationale=['No sufficiently relevant gap or novel fact warrants an interruption.']
    elif domain=='presenter' and intent=='new_fact' and not bool(ctx.get('turn_available',False)):
        route,action='wait','wait_for_speaking_turn'
        rationale=['Relevant content exists, but speaker turn is unavailable.']
    else:
        # Sample operations-research objective: task value × proxy success − energy/time penalties.
        # This is hand-specified and uncalibrated, not learned semantic inference.
        complexity=COMPLEXITY.get(intent,0.6)
        if policy=='always_deep': route='deep'
        elif policy=='event_only':route='deep' if complexity>0.52 else 'light'
        else:
            candidates=['rule','light','deep']
            for candidate in candidates:
                if candidate=='rule' and intent not in ('greeting','switch_light'):continue
                p=max(0.,min(1.,conf*route_quality(candidate,complexity)))
                cost=ENERGY_J[candidate]
                delay=LATENCY_MS[candidate]
                scores[candidate]=round(3*p-0.005*delay-energy_weight*cost,4)
            route=max(scores,key=scores.get)
        # Low battery and ambiguous semantics: never force a speculative low-cost action.
        if ctx.get('battery_pct') is not None and float(ctx['battery_pct'])<5 and route=='deep':
            route,action='clarify','defer_or_request_assistance'
            rationale=['Battery below 5%; defer nonemergency deep inference.']
        else:
            actions={'greeting':'draft_greeting','switch_light':'propose_light_toggle',
                     'request_quote':'draft_quote_questions','request_booking':'draft_booking_questions',
                     'fetch_cup':'propose_fetch_plan','new_fact':'propose_factual_interjection',
                     'question':'draft_answer','conversation':'draft_relevant_reply',
                     'other':'draft_clarifying_response'}
            action=actions.get(intent,'draft_response')
            rationale=['Optimize model route using synthetic quality, latency, and energy estimates.']
    # Model/tool call is NOT executed; this is an advisory plan only.
    inference_energy=ENERGY_J.get(route,0.)
    expected=ENERGY_J['sense']+ENERGY_J['safety']+ENERGY_J['semantic']+inference_energy
    if route in ('light','deep'):
        expected+=ENERGY_J['send']+ENERGY_J['wakeup']
    status='blocked_pending_approval' if approval else ('safe_stop_proposed' if route=='safe_stop' else 'dry_run_only')
    qp=None
    if route in ('rule','light','deep'):
        # Reported for EVERY policy so energy savings can be read against the quality proxy given up.
        qp=round(max(0.,min(1.,conf*route_quality(route,COMPLEXITY.get(intent,0.6)))),4)
    out=Decision(domain,intent,route,action,status,approval,conf,round(expected,4),
                 LATENCY_MS.get(route,0),scores.get(route),rationale,f['evidence'],scores,qp)
    data=out.to_dict()
    data['policy']=policy
    data['energy_weight']=energy_weight
    return data
