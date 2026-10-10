import json,subprocess,time,datetime
from pathlib import Path
R=Path('/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab'); E=R/'docs/upgrade_review/evidence'; O=R/'outputs/codex-audit-vnext-20261011'
cmd=[]
for t in ['C0','C1']:
 cmd += [(t+'-bundle',['uv','run','--locked','hsm','calibration','bundle','--run-dir',str(O/t),'--bundle-dir',str(O/('bundle-'+t)),'--json']),(t+'-bundle-verify',['uv','run','--locked','hsm','calibration','bundle-verify','--bundle-dir',str(O/('bundle-'+t)),'--replay-dir',str(O/('rebuilt-'+t)),'--json'])]
cmd += [('reproduction',['uv','run','--locked','hsm','calibration','reproduction-table','--output-dir',str(O/'reproduction'),'--json']),('closure',['uv','run','--locked','hsm','calibration','audit-closure','--output-dir',str(O/'closure'),'--json']),('leak',['uv','run','--locked','hsm','calibration','audit-leak','--output-dir',str(O/'leak'),'--json'])]
rec=[]
for name,args in cmd:
 start=time.perf_counter()
 with (E/(name+'.log')).open('w') as f: r=subprocess.run(['/usr/bin/time','-l',*args],cwd=R,stdout=f,stderr=subprocess.STDOUT)
 item={'id':name,'argv':args,'exit_code':r.returncode,'wall_seconds':round(time.perf_counter()-start,3),'log':str(E/(name+'.log'))}
 rec.append(item); (E/'post-commands.json').write_text(json.dumps(rec,indent=2)); print(json.dumps(item),flush=True); print((E/(name+'.log')).read_text()[:1800],flush=True)
