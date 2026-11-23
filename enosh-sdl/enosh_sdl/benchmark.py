"""Controlled synthetic policy and scheduling benchmark. No real robot outcomes.

v0.3: adds variant F (semantic routing + fixed batching whose period and offset are
matched to the phase-window grid), mean quality proxy per variant, p95/max wait,
and phase-gate statistics. Variants A-E reproduce v0.2 numbers exactly.
"""
from __future__ import annotations
import json, random, math
from .decision import decide, ENERGY_J
from .examples import EXAMPLES
from .scheduler import schedule, matched_grid, phase_window_stats

VARIANTS={
    'A_always_deep':('always_deep','direct'),
    'B_event_only':('event_only','direct'),
    'C_semantic':('sdl','direct'),
    'D_semantic_phase':('sdl','phase'),
    'E_semantic_fixed':('sdl','fixed'),
    'F_semantic_fixed_matched':('sdl','fixed_matched'),
}

_DECISIONS={}
def _decide_cached(i:int, policy:str, energy_weight:float)->dict:
    """Decisions depend only on (scenario, policy, lambda_E); memoised for sweeps."""
    key=(i,policy,float(energy_weight))
    if key not in _DECISIONS:
        _DECISIONS[key]=decide(EXAMPLES[i]['observation'],policy=policy,energy_weight=energy_weight)
    return _DECISIONS[key]

def benchmark(n:int=200, seed:int=24, energy_weight:float=0.18, k:float=8,
              fixed_period:float=0.4, include_matched:bool=True)->dict:
    if not 10<=n<=1000:raise ValueError('n must be between 10 and 1000')
    if not math.isfinite(energy_weight) or not 0<=energy_weight<=2:raise ValueError('energy_weight out of range')
    if not math.isfinite(k) or not 0<=k<=15:raise ValueError('k must be between 0 and 15')
    if not math.isfinite(fixed_period) or not 0.05<=fixed_period<=2:raise ValueError('fixed_period must be 0.05..2 s')
    rng=random.Random(seed)
    indices=[rng.randrange(len(EXAMPLES)) for _ in range(n)]
    times=sorted(rng.random()*30 for _ in range(n))
    m_period,m_offset=matched_grid(31,k=k)
    # Decisions do not depend on the scheduler: compute once per policy.
    cache={}
    out=[]
    for name,(policy,sched) in VARIANTS.items():
        if sched=='fixed_matched' and not include_matched:continue
        if policy not in cache:
            cache[policy]=[_decide_cached(i,policy,energy_weight) for i in indices]
        total_energy=0.; requests=[]; route_counts={}; risky_blocked=0; safety=0; real_tool_calls=0; q=[]
        for d,t in zip(cache[policy],times):
            route=d['route']; route_counts[route]=route_counts.get(route,0)+1
            total_energy+=d['expected_energy_j']
            risky_blocked+=int(d['requires_approval'])
            safety+=int(route=='safe_stop')
            if d.get('quality_proxy') is not None:q.append(d['quality_proxy'])
            if route in ('light','deep'):
                # Baseline charges per wakeup; batch scheduler charges per UNIQUE wakeup.
                total_energy-=ENERGY_J['wakeup']
                requests.append(t+d['expected_latency_ms']/1000.)
        if sched=='fixed_matched':
            stat=schedule(requests,'fixed',duration_s=31,k=k,fixed_period=m_period,fixed_offset=m_offset)
        else:
            stat=schedule(requests,sched,duration_s=31,k=k,fixed_period=fixed_period)
        total_energy+=ENERGY_J['wakeup']*stat['n_wakeups']
        out.append({'name':name,'energy_j_assumed':round(total_energy,3),
                    'inference_count':len(requests),'receiver_wakeups':stat['n_wakeups'],
                    'mean_dispatch_wait_ms':stat['mean_wait_ms'],
                    'p95_dispatch_wait_ms':stat['p95_wait_ms'],
                    'max_dispatch_wait_ms':stat['max_wait_ms'],
                    'mean_quality_proxy':round(sum(q)/len(q),4) if q else None,
                    'approval_blocks':risky_blocked,'safety_proposals':safety,
                    'route_distribution':route_counts,'real_tool_calls':real_tool_calls})
    return {'metadata':{'version':'0.3.0','n':n,'seed':seed,'energy_weight':energy_weight,
                'phase_coupling_k':k,'fixed_period_s':fixed_period,
                'matched_period_s':m_period,'matched_offset_s':round(m_offset,4),
                'phase_gate':phase_window_stats(31,k=k),
                'corpus':'20 hand-written input examples sampled with replacement',
                'energy_units':'assumed joules, not measured',
                'quality_units':'hand-specified proxy c*q_m(xi), not measured task success',
                'outcome_warning':'No models or actuators execute. No true task success/accuracy is measured.',
                'safety':'all policies use the same hard safety and approval guardrails'},
            'variants':out}

if __name__=='__main__':
    print(json.dumps(benchmark(),ensure_ascii=False,indent=2))
