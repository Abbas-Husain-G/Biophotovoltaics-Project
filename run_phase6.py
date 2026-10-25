"""Phase 6 runner: economic comparison per gross hectare (M8) - agriculture-only vs PV-only vs agrivoltaics.

Inputs : outputs/phase3_energy.csv (run_phase23.py), outputs/phase4_case_yields.csv (run_phase45.py)
Outputs: outputs/phase6_economics.csv, phase6_sensitivity.csv, phase6_state_summary.csv, phase6_log.txt
Usage  : python -I run_phase6.py [outputs_dir]
"""
import dataclasses, pathlib, sys
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from agripv.econ_inputs import PVEcon, CROP_ECON, crop_net_open_field, crop_gross_and_cost
from agripv.econ import pv_project, crop_npv, annuity, av_crop_net, breakeven_tariff
from agripv.config import gross_factor, AUX_LAND_SHARE

OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "outputs"
log_lines = []
def log(*a):
    s = " ".join(str(x) for x in a); print(s); log_lines.append(s)


def av_yield(row, which="mid"):
    if row.basis == "group curve":
        return {"mid": row.yield_rel, "low": row.yield_low, "high": row.yield_high}[which]
    if str(row.basis).startswith("field anchors"):
        return {"mid": 0.5 * (row.yield_low + row.yield_high), "low": row.yield_low, "high": row.yield_high}[which]
    return np.nan


def evaluate(p, energy, yields, case_id, cfg, aux=None, crop_scale=1.0, yield_which="mid", tariff=None):
    """Total NPV/ha of one system for one case. aux: override auxiliary land share (rescales gross densities)."""
    st = yields[yields.case == case_id].iloc[0].state
    e = energy[(energy.state == st) & (energy.config == cfg)].iloc[0]
    gf_base, gf = gross_factor(), (gross_factor(aux) if aux is not None else gross_factor())
    kwp = e.kwp_per_ha * gf / gf_base if cfg != "REF" else e.kwp_per_ha        # REF gross fixed by CTUIL norm
    pv = pv_project(kwp, e.kwh_per_kwp, p.capex_premium[cfg], p, tariff=tariff)
    if cfg == "REF":
        return pv, 0.0, kwp
    r = yields[(yields.case == case_id) & (yields.config == cfg)].iloc[0]
    share = r.cropped_share * gf / gf_base
    g, c = crop_gross_and_cost(case_id)
    net_open = crop_net_open_field(case_id)
    econ = ((None if g is None else g * crop_scale), c, net_open * crop_scale)
    yr = av_yield(r, yield_which)
    cnet = av_crop_net(econ, yr, share, p.av_crop_cost_penalty[cfg]) if np.isfinite(yr) else np.nan
    return pv, cnet, kwp


def main():
    p = PVEcon()
    energy = pd.read_csv(OUT / "phase3_energy.csv")
    yields = pd.read_csv(OUT / "phase4_case_yields.csv")
    rows = []
    for cid in yields.case.unique():
        y0 = yields[yields.case == cid].iloc[0]
        net_open = crop_net_open_field(cid)
        agri_npv = crop_npv(net_open, p)
        rows.append(dict(case=cid, state=y0.state, crop=y0.crop, system="Agri-only", kwp_per_ha=0.0, crop_share=1.0,
                         yield_rel=1.0, crop_net_y1=round(net_open), crop_npv=round(agri_npv), pv_npv=0, capex=0,
                         energy_mwh_y1=0.0, lcoe=np.nan, pv_irr=np.nan, total_npv=round(agri_npv),
                         annuity=round(annuity(agri_npv, p)), crop_grade=CROP_ECON[cid]["grade"]))
        pv_ref, _, kwp_ref = evaluate(p, energy, yields, cid, "REF")
        ref_npv = pv_ref["npv"]
        rows.append(dict(case=cid, state=y0.state, crop=y0.crop, system="PV-only (REF)", kwp_per_ha=round(kwp_ref, 1),
                         crop_share=0.0, yield_rel=0.0, crop_net_y1=0, crop_npv=0, pv_npv=round(ref_npv),
                         capex=round(pv_ref["capex"]), energy_mwh_y1=round(pv_ref["energy_y1"] / 1000, 1),
                         lcoe=round(pv_ref["lcoe"], 3), pv_irr=round(pv_ref["irr"], 4),
                         pv_payback_yr=round(pv_ref["payback"], 1), total_npv=round(ref_npv),
                         annuity=round(annuity(ref_npv, p)), crop_grade=CROP_ECON[cid]["grade"]))
        for cfg in ("C1", "C2", "C3"):
            pv, cnet, kwp = evaluate(p, energy, yields, cid, cfg)
            cn = crop_npv(cnet, p) if np.isfinite(cnet) else np.nan
            tot = pv["npv"] + (cn if np.isfinite(cn) else 0.0)
            lo = [evaluate(p, energy, yields, cid, cfg, yield_which=w)[1] for w in ("low", "high")]
            r = yields[(yields.case == cid) & (yields.config == cfg)].iloc[0]
            pv_av_tariff = pv_project(kwp, energy[(energy.state == y0.state) & (energy.config == cfg)].iloc[0].kwh_per_kwp,
                                      p.capex_premium[cfg], p, tariff=p.tariff_av_scenario)
            pv_nopremium = pv_project(kwp, energy[(energy.state == y0.state) & (energy.config == cfg)].iloc[0].kwh_per_kwp,
                                      0.0, p)
            kwh = energy[(energy.state == y0.state) & (energy.config == cfg)].iloc[0].kwh_per_kwp
            rows.append(dict(case=cid, state=y0.state, crop=y0.crop, system=cfg, kwp_per_ha=round(kwp, 1),
                             crop_share=r.cropped_share, yield_rel=round(av_yield(r), 3),
                             yield_basis=r.basis, crop_net_y1=round(cnet) if np.isfinite(cnet) else np.nan,
                             crop_net_y1_low=round(min(lo)) if np.all(np.isfinite(lo)) else np.nan,
                             crop_net_y1_high=round(max(lo)) if np.all(np.isfinite(lo)) else np.nan,
                             crop_npv=round(cn) if np.isfinite(cn) else np.nan, pv_npv=round(pv["npv"]),
                             capex=round(pv["capex"]), energy_mwh_y1=round(pv["energy_y1"] / 1000, 1),
                             lcoe=round(pv["lcoe"], 3), pv_irr=round(pv["irr"], 4), pv_payback_yr=round(pv["payback"], 1),
                             total_npv=round(tot), annuity=round(annuity(tot, p)),
                             npv_vs_ref=round(tot - ref_npv), npv_vs_agri=round(tot - agri_npv),
                             total_npv_av_tariff=round(pv_av_tariff["npv"] + (cn if np.isfinite(cn) else 0)),
                             total_npv_premium_covered=round(pv_nopremium["npv"] + (cn if np.isfinite(cn) else 0)),
                             breakeven_tariff_vs_ref=round(breakeven_tariff(kwp, kwh, p.capex_premium[cfg], p, ref_npv,
                                                                            cn if np.isfinite(cn) else 0.0), 3),
                             crop_grade=CROP_ECON[cid]["grade"]))
    eco = pd.DataFrame(rows)
    eco.to_csv(OUT / "phase6_economics.csv", index=False)

    # One-at-a-time sensitivity of NPV(AV) - NPV(PV-only) and NPV(AV) - NPV(agri) for every case x AV config
    def delta(pp, cid, cfg, **kw):
        pv, cnet, _ = evaluate(pp, energy, yields, cid, cfg, aux=kw.get("aux"), crop_scale=kw.get("crop_scale", 1.0),
                               tariff=kw.get("tariff"))
        pref, _, _ = evaluate(pp, energy, yields, cid, "REF", tariff=kw.get("tariff"))
        cn = crop_npv(cnet, pp) if np.isfinite(cnet) else 0.0
        agri = crop_npv(crop_net_open_field(cid) * kw.get("crop_scale", 1.0), pp)
        return pv["npv"] + cn - pref["npv"], pv["npv"] + cn - agri

    swings = [
        ("capex -20 % / +20 %", lambda q, s: dataclasses.replace(q, capex_inr_per_wp=q.capex_inr_per_wp * (0.8 if s < 0 else 1.2)), {}),
        ("AV premium 15 % / 40 % (C3: 0 / 15 %)", lambda q, s: dataclasses.replace(q, capex_premium={
            "C1": 0.15 if s < 0 else 0.40, "C2": 0.15 if s < 0 else 0.40, "C3": 0.0 if s < 0 else 0.15, "REF": 0.0}), {}),
        ("tariff Rs 2.50 / 3.50", lambda q, s: q, {"tariff": None}),
        ("discount rate 7 % / 11 %", lambda q, s: dataclasses.replace(q, discount_rate=0.07 if s < 0 else 0.11), {}),
        ("O&M -30 % / +30 %", lambda q, s: dataclasses.replace(q, om_inr_per_kwp_yr=q.om_inr_per_kwp_yr * (0.7 if s < 0 else 1.3)), {}),
        ("degradation 0.3 % / 0.7 %", lambda q, s: dataclasses.replace(q, degradation=0.003 if s < 0 else 0.007), {}),
        ("crop net income -50 % / +50 %", lambda q, s: q, {"crop_scale": None}),
        ("aux land share 0 / 0.25", lambda q, s: q, {"aux": None}),
    ]
    srows = []
    for cid in yields.case.unique():
        for cfg in ("C1", "C2", "C3"):
            b_ref, b_agri = delta(p, cid, cfg)
            for name, mod, kw in swings:
                out = []
                for s in (-1, 1):
                    k = {}
                    if "tariff" in kw: k["tariff"] = 2.5 if s < 0 else 3.5
                    if "crop_scale" in kw: k["crop_scale"] = 0.5 if s < 0 else 1.5
                    if "aux" in kw: k["aux"] = 0.0 if s < 0 else 0.25
                    out.append(delta(mod(p, s), cid, cfg, **k))
                srows.append(dict(case=cid, config=cfg, parameter=name, base_vs_ref=round(b_ref), base_vs_agri=round(b_agri),
                                  low_vs_ref=round(out[0][0]), high_vs_ref=round(out[1][0]),
                                  low_vs_agri=round(out[0][1]), high_vs_agri=round(out[1][1])))
    pd.DataFrame(srows).to_csv(OUT / "phase6_sensitivity.csv", index=False)

    # State summary: best AV configuration per case by total NPV, plus the comparison systems
    summ = []
    for cid, g in eco.groupby("case", sort=False):
        av = g[g.system.isin(["C1", "C2", "C3"])].dropna(subset=["total_npv"])
        best = av.loc[av.total_npv.idxmax()]
        agri = g[g.system == "Agri-only"].iloc[0]; ref = g[g.system == "PV-only (REF)"].iloc[0]
        summ.append(dict(case=cid, state=best.state, crop=best.crop, best_av=best.system,
                         npv_agri_lakh=round(agri.total_npv / 1e5, 1), npv_ref_lakh=round(ref.total_npv / 1e5, 1),
                         npv_best_av_lakh=round(best.total_npv / 1e5, 1), best_av_yield_rel=best.yield_rel,
                         best_av_crop_share=best.crop_share, lcoe_ref=ref.lcoe, lcoe_best_av=best.lcoe,
                         breakeven_tariff_vs_ref=best.breakeven_tariff_vs_ref))
    summ = pd.DataFrame(summ); summ.to_csv(OUT / "phase6_state_summary.csv", index=False)
    log(f"Phase 6 economics: {len(eco)} rows; base tariff Rs {p.tariff_inr_per_kwh}/kWh, discount {p.discount_rate:.2%}, "
        f"aux land share {AUX_LAND_SHARE}")
    log(summ.to_string(index=False))
    (OUT / "phase6_log.txt").write_text("\n".join(log_lines))


if __name__ == "__main__":
    main()
