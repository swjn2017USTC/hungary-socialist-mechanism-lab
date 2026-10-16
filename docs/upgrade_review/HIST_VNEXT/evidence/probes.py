import json,sys,re,hashlib,os,time
from pathlib import Path
import numpy as np, polars as pl
R=Path(os.environ.get('HSM_AUDIT_ROOT','/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab'));O=Path(os.environ.get('HSM_AUDIT_OUT','/private/tmp/hsm-hist-audit-20261015'));sys.path[:0]=[str(R),str(R/'src')];os.chdir(R)
from hsm_lab.evidence.schemas import TimeWindow,MetricSpec,ObservedState,InterventionBinding,EvidenceRecord
from hsm_lab.evidence.metric_enricher import enrich_metric_spec,enrich_card_metrics
from hsm_lab.evidence.table_registry import F2_TABLE_COLUMNS,F2_TABLES
from hsm_lab.evidence.run_adapter import verify_digest_unchanged,build_stub_evidence_record
from hsm_lab.evidence.adapter import load_v2_card_registry
from hsm_lab.evidence.intervention_validator import validate_intervention_binding
out={}; supers=json.loads((R/'config/mechanisms/v2/supersedes.json').read_text());cards=[]
for i in range(1,12):
 p=R/f'config/p06/cards/M{i}.json'; c=json.loads(p.read_text());sha=hashlib.sha256(p.read_bytes()).hexdigest();decl=json.loads((R/f'studies/M{i:02}/study_decl.json').read_text()); specs=enrich_card_metrics(f'M{i}',c['metrics']);cards.append({'id':f'M{i}','sha256':sha,'supersedes_match':supers[f'M{i}']==sha,'decl_sha_match':decl['v1_card_sha256']==sha,'legacy':c,'study':decl,'enriched':[s.model_dump(mode='json') for s in specs],'unmapped':[m for m in c['metrics'] if enrich_metric_spec(f'M{i}',m) is None]})
out['cards']=cards
actual={p.stem:pl.read_parquet(p) for p in (O/'C0-r1').glob('*.parquet')};out['actual_tables']={n:{'rows':df.height,'columns':df.columns} for n,df in actual.items()}
out['registry_diff']={n:{'not_actual':sorted(set(cols)-set(actual[n].columns if n in actual else [])),'omitted_actual':sorted(set(actual[n].columns if n in actual else [])-set(cols)),'actual_rows':actual[n].height if n in actual else None} for n,cols in F2_TABLE_COLUMNS.items()}
text=(R/'docs/upgrade_review/evidence/P08_DIAGNOSTIC_ONTOLOGY.md').read_text();mid=None;nodes=[]
for no,line in enumerate(text.splitlines(),1):
 if m:=re.match(r'### (M\d+) ',line):mid=m[1]
 for table,col in re.findall(r'(?:MetricNode: |Composite: |\+ )([a-z_]+)\.([a-z_]+)',line):
  nodes.append({'mechanism':mid,'line':no,'table':table,'column':col,'actual_column':table in actual and col in actual[table].columns,'rows':actual[table].height if table in actual else None})
out['ontology_metric_nodes']=nodes
base=enrich_metric_spec('M1','household_consumption').model_dump(mode='json');cases={
 'TimeWindow_end_1988':lambda:TimeWindow(start_quarter='1985Q4',end_quarter='1988Q4',missing_policy='abort'),
 'TimeWindow_before_start':lambda:TimeWindow(start_quarter='1900Q1',end_quarter='1957Q1',missing_policy='abort'),
 'TimeWindow_zero':lambda:TimeWindow(start_quarter='1957Q1',end_quarter='1958Q1',missing_policy='0'),
 'Metric_zero_fill':lambda:MetricSpec.model_validate({**base,'missing_policy':'zero_fill'}),
 'Metric_unknown_column':lambda:MetricSpec.model_validate({**base,'column':'invented_column'}),
 'Observed_future_snapshot':lambda:ObservedState(observed_state_id='x',source_run_id='x',source_scenario='x',source_checkpoint_quarter='1988Q4',source_digest='0'*64,captured_at='2026-10-15T00:00:00Z'),
 'M01_stub_id':lambda:build_stub_evidence_record(scenario_id='historical_f2_replay',mechanism_ids=['M01'],phase='audit',registry=load_v2_card_registry(R,'audit')),
 'Unsupported_status_without_run':lambda:EvidenceRecord(record_id='false-support',mechanism_id='M1',v1_card_sha256='0'*64,hypothesis='synthetic',status='supported',metric_specs=[MetricSpec.model_validate(base)],declared_reason='test only',created_by_phase='audit'),
}
out['adversarial_schemas']={}
for name,fn in cases.items():
 try:r=fn();out['adversarial_schemas'][name]={'accepted':True,'value':r.model_dump(mode='json')}
 except Exception as e:out['adversarial_schemas'][name]={'accepted':False,'error':str(e)}
out['wrong_identity_digest_accepted']=verify_digest_unchanged('wrong_scenario',999999,json.loads((O/'C0-r1/manifest.json').read_text())['deterministic_replay_digest'],O/'C0-r1',Path('/does/not/exist'))
# Never open a historical target: only existing model outputs and declared controls.
from hsm_lab.contract.guards import load_research_contract,load_scenario
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.rng import RngRegistry
spec=load_scenario(R,'historical_f2_replay');network=build_material_network(spec,load_research_contract(R),build_material_initial_conditions(spec,RngRegistry(spec.seed)))
out['f2_second_economy_axes']={'input':list(network.second_input_commodities),'output':list(network.second_output_commodities)}
# Tiny real-kernel service target contrast; no mock of execution.
from tests.test_material import _services_fixture,_org_activity,_energy_lag_fixture
from hsm_lab.engine.state import capture_material_stocks
for arm,cap in [('legacy',5.0),('exact_use',3.0),('zero_capacity',0.0)]:
 f=_services_fixture();a=_org_activity(f,4); orgidx=int(f.network.activity_org_index[a]);f.state.organization_capacity[orgidx]=cap;opening=capture_material_stocks(f.state);flow=f.tick(1)[0];gate=f.check(opening,flow)
 out.setdefault('service_tiny',{})[arm]={'capacity':cap,'produced':float(flow.activity_realized[a]),'service_used':float(np.sum(flow.edge_service_used)),'expired':float(flow.expired_services),'delivered':float(np.sum(flow.edge_delivered)),'max_material_residual':gate.max_material_abs_residual,'max_finance_residual':gate.max_finance_abs_residual}
for buffer in [0.0,2.0]:
 f=_energy_lag_fixture(capital_buffer=buffer);rows=[];forcing=f.forcing(2)
 for j in range(2):
  opening=capture_material_stocks(f.state);flow=__import__('hsm_lab.engine.material',fromlist=['tick_material']).tick_material(f.state,forcing,f.parameters,f.network);gate=f.check(opening,flow);f.state.completed_ticks+=1;rows.append({'tick':j,'activity_realized':flow.activity_realized.tolist(),'delivered':float(np.sum(flow.delivered)),'max_material_residual':gate.max_material_abs_residual,'max_finance_residual':gate.max_finance_abs_residual})
 out.setdefault('opening_inventory_tiny',{})[str(buffer)]=rows
(O/'probes.json').write_text(json.dumps(out,indent=2,default=str));print(json.dumps({'cards':len(cards),'all_hashes_match':all(c['supersedes_match'] and c['decl_sha_match'] for c in cards),'ontology_nodes':len(nodes),'missing_ontology_nodes':sum(not x['actual_column'] for x in nodes),'registry_fake_columns':sum(len(x['not_actual']) for x in out['registry_diff'].values()),'schema_accepted':{k:v['accepted'] for k,v in out['adversarial_schemas'].items()},'wrong_identity_digest_accepted':out['wrong_identity_digest_accepted'],'service_tiny':out.get('service_tiny'),'inventory':out.get('opening_inventory_tiny')},indent=2))
