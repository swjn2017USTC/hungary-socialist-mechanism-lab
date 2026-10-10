"""Isolated synthetic numerical audit, no historical observations."""
import json
import platform
import resource
import sys
import time
from importlib.metadata import version

import linopy
import numpy as np
import pandas as pd
import pymrio
from scipy.optimize import linprog

start = time.perf_counter()
cases = []
for tag, edge_cap, cash in [("open", 10.0, 20.0), ("cut_edge", 0.0, 20.0), ("zero_cash", 10.0, 0.0)]:
    model = linopy.Model()
    # Two regions, two commodities, two quarters. A owns commodity 0,
    # B owns commodity 1; both ship 3 per commodity/quarter to the other.
    flow = model.add_variables(lower=0, coords=[pd.Index([0, 1], name="commodity"), pd.Index([0, 1], name="quarter")], name="shipment")
    model.add_constraints(flow == 3, name="destination_demand")
    model.add_constraints(flow.sum("commodity") <= edge_cap, name="edge_capacity")
    model.add_constraints(flow.sum("commodity") <= cash, name="prepayment_budget")
    model.add_objective(flow.sum())
    t = time.perf_counter()
    status, termination = model.solve(solver_name="highs", log_to_console=False)
    solve_s = time.perf_counter() - t
    scipy = linprog(np.ones(4), A_eq=np.eye(4), b_eq=np.full(4, 3.0), A_ub=[[1, 0, 1, 0], [0, 1, 0, 1]], b_ub=[min(edge_cap, cash)] * 2, bounds=(0, None), method="highs")
    feasible = termination == "optimal"
    assert feasible == scipy.success
    item = {"case": tag, "status": status, "termination": termination, "scipy_status": int(scipy.status), "solve_seconds": solve_s}
    if feasible:
        x = flow.solution.values
        assert np.max(np.abs(x - 3)) < 1e-9
        assert abs(model.objective.value - scipy.fun) < 1e-9
        item.update(objective=float(model.objective.value), max_balance_residual=float(np.max(np.abs(x - 3))), dual=model.dual.to_array().values.tolist())
    cases.append(item)

# Synthetic two-sector IO: independently calculate Leontief identity.
idx = pd.MultiIndex.from_product([["HU"], ["I", "II"]], names=["region", "sector"])
yidx = pd.MultiIndex.from_product([["HU"], ["households"]], names=["region", "category"])
A = np.array([[0.2, 0.1], [0.05, 0.25]])
y = np.array([10.0, 20.0])
x = np.linalg.solve(np.eye(2) - A, y)
Z = A * x[None, :]
t = time.perf_counter()
io = pymrio.IOSystem(Z=pd.DataFrame(Z, index=idx, columns=idx), Y=pd.DataFrame(y[:, None], index=idx, columns=yidx)).calc_all()
assert np.allclose(io.A.values, A)
assert np.allclose(io.L.values @ y, x)
assert np.max(np.abs(io.x.values.ravel() - x)) < 1e-9
report = {"python": sys.version, "platform": platform.platform(), "versions": {k: version(k) for k in ["linopy", "highspy", "pymrio", "numpy", "scipy", "pandas", "polars"]}, "lp_cases": cases, "io": {"output": x.tolist(), "max_balance_residual": float(np.max(np.abs(x - A @ x - y))), "calc_seconds": time.perf_counter() - t}, "total_seconds": time.perf_counter() - start, "max_rss_bytes_macos": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
print("AUDIT_JSON=" + json.dumps(report))
