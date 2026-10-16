import os,sys,json
from pathlib import Path
import numpy as np
R=Path(os.environ.get('HSM_AUDIT_ROOT','/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab'));O=Path(os.environ.get('HSM_AUDIT_OUT','/private/tmp/hsm-hist-audit-20261015'));sys.path[:0]=[str(R),str(R/'src')]
from tests.test_material import _services_fixture,_org_activity
from hsm_lab.engine.material import tick_material
from hsm_lab.engine.policy import TickControls
from hsm_lab.engine.state import capture_material_stocks
from hsm_lab.engine.accounting import check_material_invariants
rows={};base=_services_fixture();baseflow=base.tick(1)[0];schedule=baseflow.activity_target.copy()
# TECHNICAL upper-bound schedule: use baseline target declarations, never fitted historic outcomes.
# Change only declared service target, keep physical capacity 5 and all other initial state fixed.
for name,autonomy,target in [('legacy_target',0.0,5.0),('proposed_target',0.0,3.0),('nonbinding_local',1.0,3.0)]:
 f=_services_fixture();a=_org_activity(f,4);proposal=schedule.copy();proposal[a]=target
 ctrl=TickControls(material_parameters=f.parameters,household_parameters=f.household_parameters,household_catalog=f.network.household_catalog,autonomy=autonomy,central_target=proposal)
 opening=capture_material_stocks(f.state);flow=tick_material(f.state,f.forcing(1),f.parameters,f.network,controls=ctrl);g=check_material_invariants(opening,f.state,flow,f.parameters,f.network,controls=ctrl)
 assert g.max_material_tolerance_ratio<=1 and g.max_finance_tolerance_ratio<=1
 rows[name]={'autonomy':autonomy,'proposed_service_target':target,'effective_target':float(flow.activity_target[a]),'unchanged_service_capacity':float(f.state.organization_capacity[4]),'produced':float(flow.activity_realized[a]),'delivered':float(np.sum(flow.edge_delivered)),'used_service':float(np.sum(flow.edge_service_used)),'expired':float(flow.expired_services),'max_material_residual':g.max_material_abs_residual,'max_finance_residual':g.max_finance_abs_residual}
(O/'proposal-probe.json').write_text(json.dumps({'grade':'VERIFIED_BY_RUN; technical synthetic controller probe only','scope':'existing TickControls target bridge; not a new ObservedState authority implementation','arms':rows},indent=2));print(json.dumps(rows,indent=2))
