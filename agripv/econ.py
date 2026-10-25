"""M8 - Discounted cash-flow economics per gross hectare (Phase 6).

Conventions
- Year 0: capital expenditure. Years 1..N: revenue and O&M at year end. Nominal INR, nominal discount rate.
- PV revenue = energy x flat nominal tariff; energy degrades geometrically: E_t = E_1 (1 - d)^(t-1).
- O&M escalates: OM_t = OM_1 (1 + e)^(t-1). Crop net income escalates at g: C_t = C_1 (1 + g)^(t-1).
- No taxes, depreciation, subsidies, financing structure or land purchase/lease (stated limitations): this is a
  project-level comparison of land-use options on the same hectare, not an investor model.
LCOE = (CAPEX + PV of O&M) / PV of energy (same discount rate) - the standard discounted levelised cost.
"""
import numpy as np
from scipy.optimize import brentq


def _disc(r, n):
    t = np.arange(1, n + 1)
    return t, (1 + r) ** -t


def pv_project(kwp, kwh_per_kwp_y1, premium, p, tariff=None, r=None):
    """Per-hectare PV economics. kwp: installed kWp per gross ha; kwh_per_kwp_y1: AC yield in year 1."""
    tariff = p.tariff_inr_per_kwh if tariff is None else tariff
    r = p.discount_rate if r is None else r
    t, df = _disc(r, p.life_years)
    capex = kwp * p.capex_inr_per_wp * 1000.0 * (1 + premium)
    energy = kwp * kwh_per_kwp_y1 * (1 - p.degradation) ** (t - 1)            # kWh/yr
    om = kwp * p.om_inr_per_kwp_yr * (1 + p.om_escalation) ** (t - 1)
    cash = energy * tariff - om
    npv = -capex + float(np.sum(cash * df))
    pv_energy = float(np.sum(energy * df))
    lcoe = (capex + float(np.sum(om * df))) / pv_energy if pv_energy > 0 else np.nan
    return dict(capex=capex, energy_y1=float(energy[0]), npv=npv, lcoe=lcoe, pv_energy=pv_energy,
                irr=irr(np.concatenate([[-capex], cash])), payback=payback(capex, cash))


def crop_npv(net_y1, p, r=None):
    r = p.discount_rate if r is None else r
    t, df = _disc(r, p.life_years)
    return float(np.sum(net_y1 * (1 + p.crop_escalation) ** (t - 1) * df))


def annuity(npv, p, r=None):
    """Equivalent constant annual amount over the project life (capital recovery factor)."""
    r = p.discount_rate if r is None else r
    n = p.life_years
    return npv * r / (1 - (1 + r) ** -n)


def irr(cash):
    f = lambda x: np.sum(cash / (1 + x) ** np.arange(len(cash)))
    try:
        return brentq(f, -0.9, 1.0)
    except ValueError:
        return np.nan


def payback(capex, cash):
    """Simple (undiscounted) payback in years, linear within the crossing year."""
    cum = -capex + np.cumsum(cash)
    k = np.argmax(cum >= 0) if (cum >= 0).any() else None
    if k is None:
        return np.nan
    prev = -capex if k == 0 else cum[k - 1]
    return k + (-prev) / cash[k]


def av_crop_net(case_econ, yield_rel, crop_share, penalty):
    """Year-1 crop net income per gross ha under the array.
    case_econ: (gross, cost, net_open). If gross/cost are known, revenue scales with relative yield and the
    operating cost with the cropped share (plus the AV penalty). For net-only sources, the whole net scales."""
    gross, cost, net_open = case_econ
    if gross is None:
        return crop_share * yield_rel * net_open
    return crop_share * (yield_rel * gross - cost * (1 + penalty))


def breakeven_tariff(kwp, kwh, premium, p, target_npv, extra_npv=0.0):
    """Tariff at which PV NPV + extra_npv equals target_npv (NPV is linear in tariff)."""
    a = pv_project(kwp, kwh, premium, p, tariff=0.0)["npv"]
    b = pv_project(kwp, kwh, premium, p, tariff=1.0)["npv"] - a
    return (target_npv - extra_npv - a) / b
