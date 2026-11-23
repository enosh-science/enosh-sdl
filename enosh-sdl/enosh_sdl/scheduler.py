"""Compare phase-gated vs ordinary periodic message batching. Synthetic times.
Mansour 2026 eq (1),(2),(4) inspire a phase-gain prototype; this is NOT
neural validation, and dispatch-time decisions are an original engineering rule.

v0.3 additions
- phase_window_stats(): reports receiver-cycle crossings, accepted windows and
  gate rejections, so one can see whether the gain gate does any work.
- matched_grid(): period and offset of the phase windows, used to build a
  period-matched fixed-batching control (variant F).
- schedule(..., fixed_period, fixed_offset): the fixed grid can be shifted.
  Defaults reproduce v0.2 exactly (400 ms, offset 0).
"""
from __future__ import annotations
from bisect import bisect_left
from functools import lru_cache
from math import pi, sin, cos, exp, ceil
from statistics import median

def wrap(x):return (x+pi)%(2*pi)-pi

@lru_cache(maxsize=256)
def _phase_run(duration_s:float, dt:float, k:float, kappa:float, min_gain:float):
    n=int(duration_s/dt)+1
    th_s=[0.]*(n+1); th_r=[0.]*(n+1)
    th_r[0]=0.85
    ws=2*pi*2.45; wr=2*pi*2.51; tau=0.03
    lag=max(1,round(tau/dt))
    alpha_sr=-ws*tau; alpha_rs=-wr*tau
    windows=[]; crossings=0; gains=[]
    for i in range(1,n+1):
        j=max(0,i-1-lag)
        th_s[i]=th_s[i-1]+dt*(ws+k*sin(th_r[j]-th_s[i-1]-alpha_rs))
        th_r[i]=th_r[i-1]+dt*(wr+k*sin(th_s[j]-th_r[i-1]-alpha_sr))
        crossed=int(th_r[i]/(2*pi))>int(th_r[i-1]/(2*pi))
        if crossed:
            crossings+=1
            err=wrap(th_s[max(0,i-lag)]-th_r[i]-alpha_sr)
            g=exp(kappa*(cos(err)-1)); gains.append(g)
            if g>=min_gain:
                windows.append(round(i*dt,4))
    return tuple(windows), crossings, tuple(gains)

def phase_windows(duration_s:float=30, dt:float=0.008, k:float=8, kappa:float=3, min_gain:float=0.70)->list[float]:
    return list(_phase_run(float(duration_s),float(dt),float(k),float(kappa),float(min_gain))[0])

def phase_window_stats(duration_s:float=31, dt:float=0.008, k:float=8, kappa:float=3, min_gain:float=0.70)->dict:
    w,c,g=_phase_run(float(duration_s),float(dt),float(k),float(kappa),float(min_gain))
    gaps=[b-a for a,b in zip(w,w[1:])]
    return {'crossings':c,'windows':len(w),'rejected':c-len(w),
            'rejection_fraction':round((c-len(w))/c,4) if c else 0.,
            'median_gap_s':round(median(gaps),4) if gaps else None,
            'min_gap_s':round(min(gaps),4) if gaps else None,
            'max_gap_s':round(max(gaps),4) if gaps else None,
            'first_window_s':w[0] if w else None,
            'mean_gain':round(sum(g)/len(g),4) if g else None}

def matched_grid(duration_s:float=31, k:float=8)->tuple[float,float]:
    """(period, offset) of the phase-window grid; fallback to v0.2 fixed grid."""
    st=phase_window_stats(duration_s,k=k)
    if not st['median_gap_s'] or st['first_window_s'] is None:return 0.4,0.0
    period=st['median_gap_s']
    return period, st['first_window_s']%period

def schedule(ready_times:list[float], method:str, *, duration_s:float=30,
             fixed_period:float=0.4, fixed_offset:float=0.0, max_wait:float=0.55, k:float=8)->dict:
    """Preserves event order and a bounded wait; real emergency stops bypass this.
    p95 uses the lower nearest-rank index int(0.95*(n-1)) (unchanged from v0.2)."""
    if method not in ('direct','fixed','phase'):raise ValueError('Unknown scheduler')
    if not fixed_period>0:raise ValueError('fixed_period must be > 0')
    if not ready_times:return {'n_wakeups':0,'mean_wait_ms':0.,'p95_wait_ms':0.,'max_wait_ms':0.}
    windows=phase_windows(duration_s+1,k=k) if method=='phase' else []
    dispatch=[]
    for t in ready_times:
        if method=='direct': d=t
        elif method=='fixed':
            d=fixed_offset+ceil((t-fixed_offset-1e-10)/fixed_period)*fixed_period
        else:
            ix=bisect_left(windows,t-1e-10)
            d=windows[ix] if ix<len(windows) else t+max_wait
        # Absolute guard to avoid unbounded waiting when phase locking fails.
        d=min(d,t+max_wait)
        dispatch.append(round(max(t,d),5))
    wait=sorted([(d-t)*1000 for t,d in zip(ready_times,dispatch)])
    unique=len(set(dispatch))
    return {'n_wakeups':unique,'mean_wait_ms':round(sum(wait)/len(wait),2),
            'p95_wait_ms':round(wait[min(len(wait)-1,int(.95*(len(wait)-1)))],2),
            'max_wait_ms':round(max(wait),2)}
