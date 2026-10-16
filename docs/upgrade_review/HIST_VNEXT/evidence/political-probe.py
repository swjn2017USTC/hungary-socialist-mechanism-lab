import os
import json
from pathlib import Path
import polars as pl
from hsm_lab.contract.guards import load_research_contract,load_scenario
from hsm_lab.contract.politics import PoliticalMode,InterventionSpec
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine.political_run import run_political
from hsm_lab.storage.fork import load_counterfactual_origin
R=Path(os.environ.get('HSM_AUDIT_ROOT',str(Path.cwd())));O=Path(os.environ.get('HSM_AUDIT_OUT','/private/tmp/hsm-hist-audit-20261015'))/'political-micro';con=load_research_contract(R);reg=DataRegistry.load(R);rows=[]
for sid in ['p04_replay','p04_endogenous']:
 spec=load_scenario(R,sid);d=O/sid
 run_political(spec,d/'parent',con,reg,until='1957Q4',checkpoint_every=4)
 checkpoint=d/'parent/checkpoints/tick-0004';child=spec.model_copy(update={'politics':spec.politics.model_copy(update={'mode':PoliticalMode.COUNTERFACTUAL})})
 specs=[('control',[]),('soviet',[InterventionSpec.model_validate({'intervention_id':'audit-soviet','effective_quarter':'1958Q1','target':'soviet_constraint_multiplier','value':2.0,'provenance':'Codex synthetic first-stage audit; no historical evidence'})])]
 frames={};dig={}
 for tag,ints in specs:
  origin=load_counterfactual_origin(checkpoint,child,con,interventions=ints);m=run_political(child,d/tag,con,reg,until='1958Q2',fork_from=origin);frames[tag]=pl.read_parquet(d/tag/'political_quarters.parquet').filter(pl.col('tick')>=4);dig[tag]=m.deterministic_replay_digest
 cols=[x for x in frames['control'].columns if x.startswith('policy_') and frames['control'][x].dtype.is_numeric()];delta={c:float((frames['control'][c]-frames['soviet'][c]).abs().max()) for c in cols}
 rows.append({'scenario':sid,'quarters':'1958Q1-1958Q2','digests':dig,'policy_max_abs_delta':delta,'nonzero_policy_coordinates':[c for c,v in delta.items() if v>1e-12]})
(O.parent/'political-probe.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
