import datetime, hashlib, json, pathlib, re, shutil, subprocess
R=pathlib.Path.cwd();D=R/'docs/upgrade_review';E=D/'evidence';O=R/'outputs/codex-audit-vnext-20261011'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
initial=json.loads((E/'initial-tracked-sha.json').read_text())
diffs=[f for f,h in initial.items() if not (R/f).is_file() or sha(R/f)!=h]
assert not diffs,diffs
summaries=[]
for p in sorted(O.rglob('manifest.json')):
 d=json.loads(p.read_text());summaries.append({'manifest':str(p.relative_to(R)),'sha256':sha(p),'run_id':d.get('run_id'),'scenario':d.get('scenario_id'),'digest':d.get('deterministic_replay_digest'),'seed':d.get('seed'),'parameter_hash':d.get('parameter_hash'),'end':d.get('end')})
outputs=[]
for p in sorted(O.rglob('*')):
 if p.is_file():outputs.append({'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)})
extra=[]
for p in R.glob('outputs/p06-clearance-digest-*'):
 if datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc)>=datetime.datetime(2026,10,10,17,20,tzinfo=datetime.timezone.utc):extra.append(str(p.relative_to(R)))
(E/'output-manifest.json').write_text(json.dumps({'new_root':str(O),'manifests':summaries,'files':outputs,'additional_clearance_dirs_created_in_audit_time_window':extra},indent=2))
for a,b in [('C0/summary.json','C0-summary.json'),('C1/summary.json','C1-summary.json'),('leak/leak_audit.json','leak-audit.json'),('reproduction/reproduction_table.json','reproduction-table.json')]:shutil.copy2(O/a,E/b)
for tag in ['closure','f2-h0-closure']:
 print(tag,[p.name for p in (O/tag).glob('*.json')])
 for p in (O/tag).glob('*.json'):
  if p.stat().st_size<200000:shutil.copy2(p,E/(tag+'-'+p.name))
shutil.copy2('/private/tmp/hsm-write-reports.py',E/'write-reports.py')
shutil.copy2(__file__,E/'finalize-audit.py')
shutil.copy2('/private/tmp/hsm-derived-metrics.py',E/'derived-metrics.py')
paths={}
for p in D.glob('0*.md'):
 paths[p.name]={'lines':len(p.read_text().splitlines()),'bytes':p.stat().st_size,'sha256':sha(p)}
badlinks=[]
for p in D.glob('0*.md'):
 for link in re.findall(r'\]\(([^\s)]+)\)',p.read_text()):
  if link.startswith(('https://','http://','#')):continue
  local=re.sub(r':\d+(?:–\d+)?$','',link)
  if not (p.parent/local).exists() and local!='evidence/audit-integrity.json':badlinks.append({'file':p.name,'link':link})
assert not badlinks,badlinks
checks={'verified_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'initial_code_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'branch':subprocess.check_output(['git','branch','--show-current'],text=True).strip(),'preexisting_tracked_files':len(initial),'preexisting_tracked_files_changed_by_audit':diffs,'report_files':paths,'broken_local_markdown_links':badlinks,'source_documents_unchanged':{'kickoff_sha256':sha(R/'CODEX_KICKOFF_PROMPT_HSM_VNEXT_2026-10-11.md'),'baseline_review_sha256':sha(R/'HSM_LAB_VNEXT_CODEX_AUDIT_BASELINE_2026-10-11.md')},'scope':{'kernel_modified':False,'baseline_modified':False,'formal_lock_modified':False,'omp_config_modified':False,'inference_run':False,'reserved_values_read':False,'omp_llm_dispatched':False,'push_run':False},'new_output_files':len(outputs),'new_output_bytes':sum(p['bytes'] for p in outputs)}
(E/'audit-integrity.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
manifest=[{'path':str(p.relative_to(D)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(D.rglob('*')) if p.is_file() and p.name!='SHA256_MANIFEST.json']
(D/'SHA256_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(checks,ensure_ascii=False,indent=2))
