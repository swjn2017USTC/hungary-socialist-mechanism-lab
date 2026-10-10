"""Recalculate diagnostic ratios using fresh local C0/leak output only."""
import json
from pathlib import Path
import polars as pl
from hsm_lab.calibration.reproduction_table import annual_household_consumption_index
R=Path.cwd();O=R/'outputs/codex-audit-vnext-20261011';E=R/'docs/upgrade_review/evidence'
d=json.loads((E/'derived-metrics.json').read_text())
c=pl.read_parquet(O/'leak/commodity_circuit.parquet')
s=pl.read_parquet(O/'leak/service_expiry.parquet')
b=pl.read_parquet(O/'leak/bank_circuit.parquet')
m=pl.read_parquet(O/'leak/money_stock.parquet')
gates=json.loads((O/'leak/leak_audit.json').read_text())['gate_metrics']
d.pop('service_funding',None)
d['service_realization_over_funded']={}
for g in ['g03_electricity_heat','g15_market_services','g16_housing_public_services']:
 v=c.filter(pl.col('commodity_id')==g)
 d['service_realization_over_funded'][g]=float(v['household_realized'].sum()/v['household_funded'].sum())
 v=s.filter((pl.col('commodity_id')==g)&(pl.col('tick')>=106)&(pl.col('tick')<=115))
 d['expiry_tail_ratio'][g]=float(v['expired'].sum()/v['production'].sum())
d['physical_block_share_allocated']=gates['physical_blocked_total']/gates['allocated_total']
d['physical_block_share_alternative_delivered_plus_blocked']=gates['physical_blocked_total']/(gates['delivered_total']+gates['physical_blocked_total'])
d['min_bank_reserves']=float(b['bank_reserves_close'].min())
for k in d['money']:d['money'][k]=float(m[k].sum())
d['consumption_index_1978']={t:annual_household_consumption_index(pl.read_parquet(O/t/'national_accounts.parquet'))[1978] for t in ['C0','C1']}
d['definitions'].pop('service_funding',None)
d['definitions']['service_realization_over_funded']='sum commodity_circuit.household_realized / sum commodity_circuit.household_funded by commodity over ticks 0..115; ratio of totals. NOT funded/desired or nominal household income.'
(E/'derived-metrics.json').write_text(json.dumps(d,indent=2))
print(json.dumps(d,indent=2))
