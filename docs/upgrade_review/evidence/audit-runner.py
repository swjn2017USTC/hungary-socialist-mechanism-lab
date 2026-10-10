import json,subprocess,time,datetime,sys,platform,os
from pathlib import Path
ROOT=Path('/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab')
E=ROOT/'docs/upgrade_review/evidence'
E.mkdir(parents=True,exist_ok=True)
OUT=ROOT/'outputs/codex-audit-vnext-20261011'
assert not OUT.exists(), f'fresh outputs required: {OUT}'
commands=[('ruff',['uv','run','--locked','ruff','check','src','tests']),('pytest',['uv','run','--locked','python','-m','pytest','-q','-p','no:cacheprovider']),('baseline',['uv','run','--locked','hsm','baseline','verify','--json'])]
for tag,scenario in [('C0','historical_f2_replay'),('C1','historical_f2_trade_scenario')]:
 commands += [(tag,['uv','run','--locked','hsm','run','--scenario',scenario,'--until','1985Q4','--output-dir',str(OUT/tag),'--json']),(tag+'-summary',['uv','run','--locked','hsm','summary','--run-dir',str(OUT/tag),'--json'])]
records=[]
for name,args in commands:
 start=time.perf_counter()
 with (E/(name+'.log')).open('w') as f:
  r=subprocess.run(['/usr/bin/time','-l',*args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 rec={'id':name,'argv':args,'exit_code':r.returncode,'wall_seconds':round(time.perf_counter()-start,3),'log':str(E/(name+'.log')),'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 records.append(rec)
 (E/'commands.json').write_text(json.dumps(records,indent=2))
 print(json.dumps(rec),flush=True)
 print((E/(name+'.log')).read_text()[-2500:],flush=True)
