import sys,json,pandas as pd,matplotlib,matplotlib.ticker; matplotlib.use('Agg'); import matplotlib.pyplot as plt
R=sys.argv[1]; O=R+'/figures/'
B1,O2,A3,G='#2a78d6','#eb6834','#1baf7a','#8a8985'; T2='#52514e'
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#9a9994',
 'axes.labelcolor':'#0b0b0b','xtick.color':T2,'ytick.color':T2,'axes.grid':True,'grid.color':'#e6e5e1','grid.linewidth':.6,'figure.dpi':300})
s=json.load(open(R+'/summary_v0_3.json'))['robustness']
lam=pd.read_csv(R+'/sweep_lambda.csv'); per=pd.read_csv(R+'/sweep_fixed_period.csv'); k=pd.read_csv(R+'/sweep_k.csv')
pr=json.load(open(R+'/safety_probes_v02_vs_v03.json'))
# Fig 4 energy vs quality
fig,ax=plt.subplots(figsize=(6.3,3.6))
ax.plot(lam.C_quality_mean,lam.C_energy_mean,'-',color=B1,lw=2,zorder=1)
for _,r in lam.drop_duplicates(['C_energy_mean']).iterrows():
    ax.plot(r.C_quality_mean,r.C_energy_mean,'o',ms=8,color=B1,mec='white',mew=2,zorder=3)
    if r.lambda_E==0: continue
    ax.annotate(f"C, λᴱ={r.lambda_E:g}",(r.C_quality_mean,r.C_energy_mean),xytext=(8,-4),textcoords='offset points',color=T2,fontsize=8.5)
v=s['variants']
for L,c in (('A',G),('B',G)):
    ax.plot(v[L]['quality_mean'],v[L]['energy_mean'],'s',ms=8,color=c,mec='white',mew=2,zorder=3)
    ax.annotate(L+(' (always deep)' if L=='A' else ' (event-only) = C at λᴱ≤0.10'),(v[L]['quality_mean'],v[L]['energy_mean']),xytext=(-8,6),textcoords='offset points',ha='right',color=T2,fontsize=8.5)
ax.set_xlabel('Mean quality proxy c·qₘ(ξ) (hand-specified, not measured)'); ax.set_ylabel('Assumed J per 200 events')
ax.set_xlim(.58,.9); ax.set_ylim(35,150); fig.tight_layout(); fig.savefig(O+'fig4_energy_quality_tradeoff.png'); plt.close()
# Fig 5 period sweep
fig,(a,b)=plt.subplots(1,2,figsize=(7.6,3.2))
a.fill_between(per.fixed_period_s*1000,per.ci_low,per.ci_high,color=B1,alpha=.18,lw=0)
a.plot(per.fixed_period_s*1000,per.D_minus_E_energy_J,color=B1,lw=2)
b.plot(per.fixed_period_s*1000,per.D_minus_E_p95_ms,color=O2,lw=2)
for ax,yl,t in ((a,'D − E energy (assumed J)','(a) Energy, mean ± 95% CI'),(b,'D − E p95 wait (ms)','(b) 95th-percentile wait')):
    ax.axhline(0,color=G,lw=1,ls='--'); ax.axvline(408,color=T2,lw=1,ls=':'); ax.axvline(400,color=T2,lw=1,ls='-',alpha=.5)
    ax.set_xlabel('Fixed-batching period of control E (ms)'); ax.set_ylabel(yl); ax.set_title(t,fontsize=10,color='#0b0b0b',loc='left')
a.annotate('400 ms\n(paper)',(400,-1.15),xytext=(-4,0),textcoords='offset points',ha='right',fontsize=8,color=T2)
a.annotate('408 ms =\nphase grid',(408,0.75),xytext=(4,0),textcoords='offset points',fontsize=8,color=T2)
fig.tight_layout(); fig.savefig(O+'fig5_fixed_period_sweep.png'); plt.close()
# Fig 6 k sweep
fig,(a,b)=plt.subplots(1,2,figsize=(7.6,3.0))
a.plot(k.k,k.gate_rejection_fraction*100,'-o',color=B1,lw=2,ms=6,mec='white',mew=1.5)
a.set_xlabel('Coupling k'); a.set_ylabel('Crossings rejected by gain gate (%)'); a.set_title('(a) Gate activity',fontsize=10,loc='left')
kk=k[k.k>0]
b.plot(kk.k,kk.D_minus_F_energy_J,'-o',color=A3,lw=2,ms=6,mec='white',mew=1.5,label='D − F (period-matched)')
b.plot(kk.k,kk.D_minus_E_energy_J,'-o',color=O2,lw=2,ms=6,mec='white',mew=1.5,label='D − E (400 ms)')
b.axhline(0,color=G,lw=1,ls='--'); b.legend(frameon=False,fontsize=8); b.set_xlabel('Coupling k (k = 0 omitted: D − F = +5.06 J)')
b.set_ylabel('Energy difference (assumed J)'); b.set_title('(b) Phase vs fixed controls',fontsize=10,loc='left')
fig.tight_layout(); fig.savefig(O+'fig6_coupling_sweep.png'); plt.close()
# Fig 7 probes
cats=[('review','Must review (n=18)'),('safe_stop','Must stop (n=6)'),('none','Must not trigger (n=8)')]
import numpy as np; x=np.arange(3); w=.36
fig,ax=plt.subplots(figsize=(6.3,3.0))
for i,(ver,c) in enumerate((('v0_2',G),('v0_3',B1))):
    vals=[pr[ver]['confusion'][e][e] for e,_ in cats]; tots=[sum(pr[ver]['confusion'][e].values()) for e,_ in cats]
    bars=ax.bar(x+(i-.5)*(w+.02),vals,w,color=c,label=ver.replace('_','.'))
    for xb,vv,tt in zip(x+(i-.5)*(w+.02),vals,tots): ax.text(xb,vv+.3,f'{vv}/{tt}',ha='center',fontsize=8.5,color=T2)
ax.set_xticks(x,[l for _,l in cats]); ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True)); ax.set_ylabel('Probes handled correctly'); ax.legend(frameon=False); ax.grid(axis='x',visible=False)
fig.tight_layout(); fig.savefig(O+'fig7_safety_probes.png'); plt.close()
print('ok')
