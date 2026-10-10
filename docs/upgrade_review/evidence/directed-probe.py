"""Read-only observer and LP recheck against unmodified HSM functions."""
import inspect
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import polars as pl

from hsm_lab.calibration.alignment import build_alignment_problem, execution_target_compatibility, solve_alignment
from hsm_lab.calibration.mechanism_cards import load_mechanism_cards
from hsm_lab.calibration.time_expanded import build_regional_problem, solve_regional_feasibility
from hsm_lab.contract.guards import load_research_contract, load_scenario
from hsm_lab.data.registry import DataRegistry
from hsm_lab.engine import material
from hsm_lab.engine.initial import build_material_initial_conditions
from hsm_lab.engine.network import build_material_network
from hsm_lab.engine.rng import RngRegistry
from hsm_lab.engine.state import initialize_material

R = Path.cwd()
O = R / 'outputs/codex-audit-vnext-20261011'
spec = load_scenario(R, 'historical_f2_replay')
contract = load_research_contract(R)
initial = build_material_initial_conditions(spec, RngRegistry(spec.seed))
network = build_material_network(spec, contract, initial)
state = initialize_material(spec, initial, network)
cg = np.asarray(network.cell_commodity)
cr = np.asarray(network.cell_region)
G, K = len(network.commodity_ids), len(network.region_ids)
opening = np.bincount(cg, weights=state.stock_value, minlength=G)
problem = build_alignment_problem(network, parameters=spec.material_parameters, equivalent_persons=float(initial.equivalent_persons), opening_stock=opening)
aligned = solve_alignment(problem, objective='min_output')
compat = execution_target_compatibility(problem, aligned)
regional_opening = np.zeros((K, G))
np.add.at(regional_opening, (cr, cg), state.stock_value)
persons = np.bincount(state.household_region, weights=state.household_weight * state.household_size, minlength=K)
rp = build_regional_problem(network, parameters=spec.material_parameters, equivalent_persons_by_region=persons, opening_stock_by_region=regional_opening)
reg = {}
for mode in ['none', 'free']:
    v = solve_regional_feasibility(rp, transfers=mode, objective='min_output')
    reg[mode] = {k: x for k, x in v.items() if k != 'activity'}

records = {}
orig = material._group_factor
def observer(need, capacity):
    out = orig(need, capacity)
    f = inspect.currentframe().f_back
    key = f'{Path(f.f_code.co_filename).name}:{f.f_lineno}:{f.f_code.co_name}'
    active = np.asarray(need) > 0
    d = records.setdefault(key, {'calls': 0, 'active_groups': 0, 'zero_capacity_groups': 0, 'factor_sum': 0.0, 'need_sum': 0.0, 'allowed_need_sum': 0.0})
    d['calls'] += 1
    d['active_groups'] += int(active.sum())
    d['zero_capacity_groups'] += int(np.count_nonzero(active & (np.asarray(capacity) <= 0)))
    d['factor_sum'] += float(np.asarray(out)[active].sum())
    d['need_sum'] += float(np.asarray(need)[active].sum())
    d['allowed_need_sum'] += float((np.asarray(need)[active] * np.asarray(out)[active]).sum())
    return out
with patch.object(material, '_group_factor', observer):
    manifest = material.run_material(spec, O / 'factor-observer', contract, DataRegistry.load(R), until='1985Q4')
assert manifest.deterministic_replay_digest == '92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d'
for d in records.values():
    d['mean_factor_active_groups'] = d['factor_sum'] / max(d['active_groups'], 1)
    d['need_weighted_factor'] = d['allowed_need_sum'] / max(d['need_sum'], 1e-12)
cards = load_mechanism_cards(R)
schemas = {}
for t in ['C0', 'C1']:
    s = json.loads((O / t / 'summary.json').read_text())
    schemas[t] = {'invariants': s['invariants'], 'mechanism_diagnostics': s['mechanism_diagnostics'], 'tables': {p.stem: list(pl.read_parquet_schema(p)) for p in (O/t).glob('*.parquet')}}
result = {'alignment_status': aligned['status'], 'compatibility': compat, 'regional': reg, 'factor_observer_digest': manifest.deterministic_replay_digest, 'group_factors': records, 'cards_validated': len(cards), 'f2_second_input_commodities': list(network.second_input_commodities), 'f2_second_output_commodities': list(network.second_output_commodities), 'schemas_and_invariants': schemas}
(R / 'docs/upgrade_review/evidence/directed-probe.json').write_text(json.dumps(result, indent=2))
print(json.dumps({k:v for k,v in result.items() if k != 'schemas_and_invariants'}, indent=2))
