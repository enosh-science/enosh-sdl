"""ENOSH-SDL v0.3 experiment suite (standard library only).

Runs:
  1. 60-seed robustness study, variants A-F (F = period-matched fixed batching)
  2. Energy-weight (lambda_E) sensitivity of semantic routing: energy vs quality proxy
  3. Fixed-batching period sweep against the phase scheduler (D)
  4. Coupling (k) sweep: phase-gate activity and D vs matched control F
  5. Safety/authorization probe set

Usage:  python -m enosh_sdl.experiments [--out results/v0_3] [--seeds 60] [--quick]
All energies are ASSUMED accounting joules; quality is a hand-set proxy.
"""
from __future__ import annotations
import argparse, csv, json, math, os, statistics as st
from .benchmark import benchmark
from .decision import decide
from .probes import evaluate
from .scheduler import phase_window_stats

# ---------- small stats helpers (no SciPy) ----------
def _t_pdf(x, df):
    return math.exp(math.lgamma((df+1)/2)-math.lgamma(df/2))/math.sqrt(df*math.pi)*(1+x*x/df)**(-(df+1)/2)

def t_cdf(x, df):
    if x==0:return .5
    n=400; a=0.; b=abs(x); h=(b-a)/n
    s=_t_pdf(a,df)+_t_pdf(b,df)+sum((4 if i%2 else 2)*_t_pdf(a+i*h,df) for i in range(1,n))
    area=s*h/3
    return .5+area if x>0 else .5-area

from functools import lru_cache
@lru_cache(maxsize=64)
def t_ppf(p, df):
    lo,hi=-50.,50.
    for _ in range(60):
        mid=(lo+hi)/2
        if t_cdf(mid,df)<p:lo=mid
        else:hi=mid
    return (lo+hi)/2

def _fmt_p(p):
    p=min(1.,max(0.,p))
    return '<0.0001' if p<1e-4 else round(p,4)

def paired(x:list[float], y:list[float])->dict:
    d=[a-b for a,b in zip(x,y)]; n=len(d); m=st.mean(d); sd=st.stdev(d) if n>1 else 0.
    out={'n':n,'mean_diff':round(m,4),'sd_diff':round(sd,4)}
    if sd>0:
        se=sd/math.sqrt(n); t=m/se; tc=t_ppf(.975,n-1)
        out.update({'t':round(t,3),'p_two_sided':_fmt_p(2*(1-t_cdf(abs(t),n-1))),
                    'ci95':[round(m-tc*se,4),round(m+tc*se,4)]})
    else:
        out.update({'t':None,'p_two_sided':1.0 if m==0 else 0.0,'ci95':[round(m,4),round(m,4)]})
    neg=sum(v< -1e-9 for v in d); pos=sum(v>1e-9 for v in d); k=min(neg,pos); nn=neg+pos
    sign_p=min(1.,2*sum(math.comb(nn,i) for i in range(k+1))/2**nn) if nn else 1.
    out.update({'n_first_lower':neg,'n_second_lower':pos,'ties':n-nn,'sign_test_p':_fmt_p(sign_p)})
    return out

def _write_csv(path, rows):
    if not rows:return
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

def _by(r):return {v['name'][0]:v for v in r['variants']}

# ---------- experiments ----------
def robustness(seeds, n=200, lam=0.18, k=8):
    rows=[]
    for s in seeds:
        v=_by(benchmark(n=n,seed=s,energy_weight=lam,k=k))
        row={'seed':s}
        for L in 'ABCDEF':
            row[f'{L}_energy']=v[L]['energy_j_assumed']
        for L in 'ABCDEF':
            row[f'{L}_quality']=v[L]['mean_quality_proxy']
        for L in 'ABCDEF':
            row[f'{L}_inference']=v[L]['inference_count']
        for L in 'DEF':
            row[f'{L}_wakeups']=v[L]['receiver_wakeups']
            row[f'{L}_wait_ms']=v[L]['mean_dispatch_wait_ms']
            row[f'{L}_p95_ms']=v[L]['p95_dispatch_wait_ms']
            row[f'{L}_max_ms']=v[L]['max_dispatch_wait_ms']
        row['C_rule']=v['C']['route_distribution'].get('rule',0)
        row['C_light']=v['C']['route_distribution'].get('light',0)
        row['C_deep']=v['C']['route_distribution'].get('deep',0)
        rows.append(row)
    col=lambda c:[r[c] for r in rows]
    summ={'variants':{L:{'energy_mean':round(st.mean(col(f'{L}_energy')),4),
                         'energy_sd':round(st.stdev(col(f'{L}_energy')),4),
                         'quality_mean':round(st.mean(col(f'{L}_quality')),4)} for L in 'ABCDEF'},
          'scheduling':{L:{'wakeups_mean':round(st.mean(col(f'{L}_wakeups')),3),
                           'wait_mean_ms':round(st.mean(col(f'{L}_wait_ms')),3),
                           'p95_mean_ms':round(st.mean(col(f'{L}_p95_ms')),3),
                           'max_mean_ms':round(st.mean(col(f'{L}_max_ms')),3)} for L in 'DEF'},
          'paired':{
             'D_vs_E_energy':paired(col('D_energy'),col('E_energy')),
             'D_vs_E_wakeups':paired(col('D_wakeups'),col('E_wakeups')),
             'D_vs_E_wait':paired(col('D_wait_ms'),col('E_wait_ms')),
             'D_vs_E_p95':paired(col('D_p95_ms'),col('E_p95_ms')),
             'D_vs_F_energy':paired(col('D_energy'),col('F_energy')),
             'D_vs_F_wakeups':paired(col('D_wakeups'),col('F_wakeups')),
             'D_vs_F_wait':paired(col('D_wait_ms'),col('F_wait_ms')),
             'D_vs_F_p95':paired(col('D_p95_ms'),col('F_p95_ms')),
             'C_vs_B_energy':paired(col('C_energy'),col('B_energy')),
             'C_vs_B_quality':paired(col('C_quality'),col('B_quality')),
             'C_vs_A_quality':paired(col('C_quality'),col('A_quality'))},
          'routes_C_mean':{r:round(st.mean(col(f'C_{r}')),3) for r in ('rule','light','deep')}}
    # energy-difference identity: D-E energy == 0.23 * (D-E wakeups)
    resid=max(abs((r['D_energy']-r['E_energy'])-0.23*(r['D_wakeups']-r['E_wakeups'])) for r in rows)
    summ['identity_max_residual_J']=round(resid,9)
    return rows,summ

def lambda_sweep(seeds, lams=(0,0.05,0.1,0.15,0.18,0.2,0.3,0.5,1.0,2.0), k=8):
    rows=[]
    for lam in lams:
        E=[];Q=[];R={'rule':0,'light':0,'deep':0}
        for s in seeds:
            c=_by(benchmark(seed=s,energy_weight=lam,k=k,include_matched=False))['C']
            E.append(c['energy_j_assumed']);Q.append(c['mean_quality_proxy'])
            for r in R:R[r]+=c['route_distribution'].get(r,0)
        tot=sum(R.values()) or 1
        rows.append({'lambda_E':lam,'C_energy_mean':round(st.mean(E),3),'C_quality_mean':round(st.mean(Q),4),
                     'share_rule':round(R['rule']/tot,4),'share_light':round(R['light']/tot,4),'share_deep':round(R['deep']/tot,4)})
    return rows

def period_sweep(seeds, periods=None, k=8):
    periods=periods or [round(0.30+0.01*i,2) for i in range(21)]
    rows=[]
    for p in periods:
        D=[];E=[];DW=[];EW=[];DP=[];EP=[];DK=[];EK=[]
        for s in seeds:
            v=_by(benchmark(seed=s,k=k,fixed_period=p,include_matched=False))
            D.append(v['D']['energy_j_assumed']);E.append(v['E']['energy_j_assumed'])
            DK.append(v['D']['receiver_wakeups']);EK.append(v['E']['receiver_wakeups'])
            DW.append(v['D']['mean_dispatch_wait_ms']);EW.append(v['E']['mean_dispatch_wait_ms'])
            DP.append(v['D']['p95_dispatch_wait_ms']);EP.append(v['E']['p95_dispatch_wait_ms'])
        pe=paired(D,E)
        rows.append({'fixed_period_s':p,'D_minus_E_energy_J':pe['mean_diff'],'ci_low':pe['ci95'][0],'ci_high':pe['ci95'][1],
                     'p':pe['p_two_sided'],'D_minus_E_wakeups':round(st.mean(DK)-st.mean(EK),3),
                     'D_minus_E_wait_ms':round(st.mean(DW)-st.mean(EW),3),'D_minus_E_p95_ms':round(st.mean(DP)-st.mean(EP),3)})
    return rows

def k_sweep(seeds, ks=(0,1,2,4,6,8,10,12,15)):
    rows=[]
    for k in ks:
        g=phase_window_stats(31,k=k)
        D=[];F=[];DW=[];FW=[];DK=[];FK=[];E=[]
        for s in seeds:
            r=benchmark(seed=s,k=k); v=_by(r)
            D.append(v['D']['energy_j_assumed']);F.append(v['F']['energy_j_assumed']);E.append(v['E']['energy_j_assumed'])
            DK.append(v['D']['receiver_wakeups']);FK.append(v['F']['receiver_wakeups'])
            DW.append(v['D']['mean_dispatch_wait_ms']);FW.append(v['F']['mean_dispatch_wait_ms'])
        pf=paired(D,F); pe=paired(D,E)
        rows.append({'k':k,'crossings':g['crossings'],'windows':g['windows'],'gate_rejection_fraction':g['rejection_fraction'],
                     'median_gap_s':g['median_gap_s'],'min_gap_s':g['min_gap_s'],'max_gap_s':g['max_gap_s'],
                     'matched_period_s':r['metadata']['matched_period_s'],
                     'D_minus_F_energy_J':pf['mean_diff'],'D_minus_F_p':pf['p_two_sided'],
                     'D_minus_E_energy_J':pe['mean_diff'],'D_minus_E_p':pe['p_two_sided'],
                     'D_minus_F_wakeups':round(st.mean(DK)-st.mean(FK),3),'D_minus_F_wait_ms':round(st.mean(DW)-st.mean(FW),3)})
    return rows

def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument('--out',default=os.path.join('results','v0_3'))
    ap.add_argument('--seeds',type=int,default=60); ap.add_argument('--quick',action='store_true')
    a=ap.parse_args(argv)
    os.makedirs(a.out,exist_ok=True)
    seeds=list(range(10 if a.quick else a.seeds))
    print(f'[1/5] robustness, {len(seeds)} seeds',flush=True)
    rows,summ=robustness(seeds); _write_csv(os.path.join(a.out,'robustness_60_seeds_v0_3.csv'),rows)
    ref=benchmark(seed=24)
    with open(os.path.join(a.out,'benchmark_seed24_v0_3.json'),'w',encoding='utf-8') as f:json.dump(ref,f,ensure_ascii=False,indent=2)
    print('[2/5] lambda_E sweep',flush=True); lam=lambda_sweep(seeds); _write_csv(os.path.join(a.out,'sweep_lambda.csv'),lam)
    print('[3/5] fixed-period sweep',flush=True); per=period_sweep(seeds); _write_csv(os.path.join(a.out,'sweep_fixed_period.csv'),per)
    print('[4/5] coupling k sweep',flush=True); ks=k_sweep(seeds); _write_csv(os.path.join(a.out,'sweep_k.csv'),ks)
    print('[5/5] safety probes',flush=True); pr=evaluate(decide)
    with open(os.path.join(a.out,'safety_probes_v0_3.json'),'w',encoding='utf-8') as f:json.dump(pr,f,ensure_ascii=False,indent=1)
    summary={'seeds':[seeds[0],seeds[-1]],'robustness':summ,'reference_seed24':ref['metadata'],
             'safety_probes':{'n':pr['n'],'correct':pr['correct'],'confusion':pr['confusion']}}
    with open(os.path.join(a.out,'summary_v0_3.json'),'w',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
    print(json.dumps(summ['paired']['D_vs_E_energy']),'\n',json.dumps(summ['paired']['D_vs_F_energy']),flush=True)
    print('done ->',a.out)

if __name__=='__main__':main()
