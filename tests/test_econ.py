"""Checks of the Phase 6 cash-flow maths against closed forms. Run: python -I tests/test_econ.py"""
import sys, pathlib, dataclasses
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np
from agripv.econ_inputs import PVEcon
from agripv.econ import pv_project, crop_npv, annuity, breakeven_tariff, irr

ok = True
def check(name, value, limit):
    global ok
    good = abs(value) <= limit; ok &= good
    print(f"[{'PASS' if good else 'FAIL'}] {name}: {value:.3e} (limit {limit:g})")

p = dataclasses.replace(PVEcon(), degradation=0.0, om_escalation=0.0, crop_escalation=0.0)
r, n = p.discount_rate, p.life_years
A = (1 - (1 + r) ** -n) / r                                   # annuity factor
kwp, kwh = 700.0, 1650.0
res = pv_project(kwp, kwh, 0.0, p)
capex = kwp * p.capex_inr_per_wp * 1000
lcoe_cf = (capex + kwp * p.om_inr_per_kwp_yr * A) / (kwp * kwh * A)
check("E1 LCOE vs closed form (no degradation/escalation), rel. error", res["lcoe"] / lcoe_cf - 1, 1e-12)
npv_cf = -capex + (kwp * kwh * p.tariff_inr_per_kwh - kwp * p.om_inr_per_kwp_yr) * A
check("E2 NPV vs closed form, rel. error", res["npv"] / npv_cf - 1, 1e-12)
check("E3 NPV at tariff = LCOE is zero (rel. to capex)", pv_project(kwp, kwh, 0.0, p, tariff=res["lcoe"])["npv"] / capex, 1e-12)
check("E4 crop NPV vs annuity factor, rel. error", crop_npv(1e5, p) / (1e5 * A) - 1, 1e-12)
check("E5 annuity(NPV) of a level stream returns the stream, rel. error", annuity(1e5 * A, p) / 1e5 - 1, 1e-12)
q = PVEcon()
bt = breakeven_tariff(kwp, kwh, 0.275, q, target_npv=1.23e6, extra_npv=4.0e5)
check("E6 break-even tariff reproduces the target NPV (rel.)",
      (pv_project(kwp, kwh, 0.275, q, tariff=bt)["npv"] + 4.0e5) / 1.23e6 - 1, 1e-9)
cash = np.array([-100.0] + [12.0] * 25)
x = irr(cash)
check("E7 NPV at IRR is zero", float(np.sum(cash / (1 + x) ** np.arange(26))), 1e-8)
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
