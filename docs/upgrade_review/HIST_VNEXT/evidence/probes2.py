import sys,json,os,subprocess,hashlib,tomllib,importlib.metadata,time
from pathlib import Path
import numpy as np,polars as pl
from scipy.optimize import linprog
R=Path(os.environ.get('HSM_AUDIT_ROOT','/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab'));O=Path(os.environ.get('HSM_AUDIT_OUT','/private/tmp/hsm-hist-audit-20261015'));sys.path[:0]=[str(R),str(R/'src')];os.chdir(R)
from tests.test_material import _transport_fixture,_transport_hub_edge,_food_chain_fixture
from tests.test_material_finance import _credit_grant_fixture,_case8_parameters
from hsm_lab.engine.state import capture_material_stocks
from hsm_lab.engine.material import tick_material
from hsm_lab.evidence.loader import load_all_evidence_records
from hsm_lab.calibration.axis_sweep import _gate_metrics
from hsm_lab.calibration.reproduction_table import annual_household_consumption_index
D={};D['transport']={}
for name,opening_services in [('no_freight',0.0),('freight',1.0)]:
 f=_transport_fixture(transport_opening=opening_services);edge=_transport_hub_edge(f);opening=capture_material_stocks(f.state);cash=float(f.state.organization_cash[2]);flow=f.tick(1)[0];gate=f.check(opening,flow)
 upper=linprog([-1],bounds=[(0,10)],method='highs');bounded=linprog([-1],A_ub=[[0.1]],b_ub=[opening_services],bounds=[(0,10)],method='highs')
 D['transport'][name]={'relaxed_lp_delivery':float(upper.x[0]),'freight_lp_delivery':float(bounded.x[0]),'allocated':float(flow.edge_allocated[edge]),'actual_delivery':float(flow.edge_delivered[edge]),'freight_fee':float(flow.edge_service_fee[edge]),'buyer_cash_delta':float(f.state.organization_cash[2])-cash,'seller_receipts':float(flow.organization_sales_receipts[1]),'carrier_receipts':float(flow.organization_sales_receipts[4]),'max_material_residual':gate.max_material_abs_residual,'max_finance_residual':gate.max_finance_abs_residual}
f=_credit_grant_fixture();opening=capture_material_stocks(f.state);flow=tick_material(f.state,f.forcing(1),_case8_parameters(f),f.network);gate=__import__('hsm_lab.engine.accounting',fromlist=['check_material_invariants']).check_material_invariants(opening,f.state,flow,_case8_parameters(f),f.network)
D['credit_without_material']={'credit_drawn':float(flow.organization_credit_drawn[1]),'wages_paid':float(flow.organization_wage_paid[1]),'production':float(np.sum(flow.production)) if hasattr(flow,'production') else float(np.sum(flow.activity_realized)),'max_material_residual':gate.max_material_abs_residual,'max_finance_residual':gate.max_finance_abs_residual}
f=_food_chain_fixture();D['food_pipeline']=[];forcing=f.forcing(3)
for tick in range(3):
 opening=capture_material_stocks(f.state);flow=tick_material(f.state,forcing,f.parameters,f.network);gate=f.check(opening,flow);f.state.completed_ticks+=1;D['food_pipeline'].append({'tick':tick,'ready_food_produced':float(flow.activity_realized[0]),'household_food':float(flow.household_realized[0,f.g('food')]),'max_material_residual':gate.max_material_abs_residual,'max_finance_residual':gate.max_finance_abs_residual})
try:D['load_all_evidence_records']={'result':'loaded','count':len(load_all_evidence_records(R))}
except Exception as e:D['load_all_evidence_records']={'result':'rejected','type':type(e).__name__,'error':str(e)}
for tag in ['C0-r1','C0-r2','C1-r1','C1-r2']:
 m=json.loads((O/tag/'manifest.json').read_text());s=json.loads((O/tag/'summary.json').read_text());g=_gate_metrics(O/tag);na=pl.read_parquet(O/tag/'national_accounts.parquet');D.setdefault('runs',{})[tag]={'manifest':{k:m[k] for k in ['completed_ticks','deterministic_replay_digest','lock_hash','parameter_hash','dependency_versions','python','output_hashes']},'invariants':s.get('invariants'),'gates':g,'consumption_index_1978':annual_household_consumption_index(na)[1978]}
lock=tomllib.loads((R/'uv.lock').read_text());mismatch=[];installed=[]
for p in lock['package']:
 try:v=importlib.metadata.version(p['name']);installed.append(p['name']);
 except importlib.metadata.PackageNotFoundError:continue
 if v!=p['version']:mismatch.append({'name':p['name'],'installed':v,'locked':p['version']})
D['installed_lock_mismatches']=mismatch;D['installed_locked_count']=len(installed)
# Track exactly which ignored audit manifests contain the alleged digest prefix.
D['beb_prefix_manifest_hits']=[]
for p in (R/'outputs').rglob('manifest.json'):
 try:
  m=json.loads(p.read_text());dg=m.get('deterministic_replay_digest','')
  if dg.startswith('beb74c54'):D['beb_prefix_manifest_hits'].append({'path':str(p.relative_to(R)),'digest':dg,'scenario_hash':m.get('scenario_hash'),'lock_hash':m.get('lock_hash'),'parameter_hash':m.get('parameter_hash')})
 except (OSError,ValueError):pass
(O/'probes2.json').write_text(json.dumps(D,indent=2,default=str))
print(json.dumps({k:v for k,v in D.items() if k not in ['runs','load_all_evidence_records']},indent=2));print('manifest loader:',D['load_all_evidence_records']['result']);print('C0 gates',json.dumps(D['runs']['C0-r1']['gates']))
