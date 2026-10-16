import os,sys,json,hashlib,subprocess,time,resource,shutil
from pathlib import Path
R=Path(os.environ.get('HSM_AUDIT_ROOT','/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab')); O=Path(os.environ.get('HSM_AUDIT_OUT','/private/tmp/hsm-hist-audit-20261015'))
sys.path.insert(0,str(R/'src')); os.chdir(R)
from hsm_lab.provenance.manifest import capture_environment
paths=subprocess.check_output(['git','ls-files','-z'],cwd=R).decode().split('\0'); paths=[p for p in paths if p and (R/p).is_file()]
hashes={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in paths}
info={'head':subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),'branch':subprocess.check_output(['git','branch','--show-current']).decode().strip(),'status_before':subprocess.check_output(['git','status','--porcelain']).decode(),'hashes':hashes,'environment':capture_environment()}
info['lock_git_blobs']={rev:subprocess.check_output(['git','rev-parse',rev+':uv.lock']).decode().strip() for rev in ['bc5f1f6','f1576e2','bda0d78','HEAD']}
p=Path('/Users/wahrfreiheit/Downloads/HSM_Historical_Institutional_Simulation_VNext_Codex_Review_Baseline_2026-10-15.md');info['input_copies']={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [p,R/p.name] if f.exists()}
(O/'baseline-before.json').write_text(json.dumps(info,indent=2))
commands=[('ruff',[str(R/'.venv/bin/ruff'),'check','--no-cache','src','tests']),('baseline',[str(R/'.venv/bin/hsm'),'baseline','verify','--json'])]
for i,sid in enumerate(['historical_f2_replay','historical_f2_trade_scenario']):
 for rep in [1,2]: commands.append((f'C{i}-r{rep}',[str(R/'.venv/bin/hsm'),'run','--scenario',sid,'--output-dir',str(O/f'C{i}-r{rep}'),'--json']))
commands.extend([('closure-f1',[str(R/'.venv/bin/hsm'),'calibration','audit-closure','--diagnostic-ticks','116','--output-dir',str(O/'closure-f1'),'--json']),('closure-f2',[str(R/'.venv/bin/hsm'),'calibration','audit-closure','--scenario','historical_f2_replay','--diagnostic-ticks','116','--output-dir',str(O/'closure-f2'),'--json'])])
records=[]
for name,cmd in commands:
 t=time.perf_counter()
 try:
  p=subprocess.run(cmd,cwd=R,capture_output=True,text=True,timeout=60,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
  (O/(name+'.log')).write_text(p.stdout+p.stderr);rec={'id':name,'argv':cmd,'exit':p.returncode,'wall_s':time.perf_counter()-t,'maxrss_children':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}
 except subprocess.TimeoutExpired as e:
  rec={'id':name,'argv':cmd,'exit':'TIMEOUT','wall_s':time.perf_counter()-t};(O/(name+'.log')).write_text(str(e))
 records.append(rec);(O/'commands.json').write_text(json.dumps(records,indent=2));print(json.dumps(rec),flush=True)
 if (O/name/'manifest.json').exists():
  m=json.loads((O/name/'manifest.json').read_text()); print(json.dumps({k:m.get(k) for k in ['status','deterministic_replay_digest','lock_hash','parameter_hash','git_commit','ticks_completed','input_artifact_hashes']}),flush=True)
