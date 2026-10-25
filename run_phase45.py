"""Phases 4-5 runner: crop response (M4) and technical comparison (M7).

Inputs
  data/zenodo/<workbook>.xlsx       Laub & Pataczek dataset (Zenodo 5716091), CC BY 4.0
  data/zenodo_columns.json          EXPLICIT column mapping, written after inspecting the workbook
                                    (no automatic column guessing):
      {"file": "Data_Meta_Analysis_updated.xlsx", "sheet": "...", "rsr": "...", "rsr_units": "percent|fraction",
       "yield": "...", "yield_units": "percent|ratio", "group": "...", "location": "...",
       "group_names": {"<label in workbook>": "<Laub group name used in cases.py>", ...}}
  outputs/phase2_ground_strips_monthly.csv, outputs/phase3_energy.csv  (from run_phase23.py)
Outputs
  outputs/phase4_fit.csv, phase4_gate.csv, phase4_case_yields.csv, phase5_technical.csv, phase45_log.txt
Usage: python -I run_phase45.py [data_dir] [outputs_dir]
"""
import json, pathlib, sys
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from agripv.cropfit import fit_lmm, strip_yield
from agripv.cases import CASES, LAUB_PUBLISHED, ANCHORS
from agripv.config import gross_factor

DATA = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "outputs"
GATE_TOL = 0.05            # absolute tolerance on relative yield for reproducing published values
UNCULTIVABLE = {"C1": 0.0, "C2": 0.0}   # posts/access under elevated layouts: base 0 %, scenario 5 % (M6)
log_lines = []
def log(*a):
    s = " ".join(str(x) for x in a); print(s); log_lines.append(s)


def load_dataset():
    cfg = json.loads((DATA / "zenodo_columns.json").read_text())
    df = pd.read_excel(DATA / "zenodo" / cfg["file"], sheet_name=cfg["sheet"])
    rsr = pd.to_numeric(df[cfg["rsr"]], errors="coerce")
    rsr = rsr / 100 if cfg["rsr_units"] == "percent" else rsr
    yld = pd.to_numeric(df[cfg["yield"]], errors="coerce")
    y_pct = yld if cfg["yield_units"] == "percent" else yld * 100
    grp = df[cfg["group"]].astype(str).map(cfg["group_names"])
    d = pd.DataFrame({"rsr": rsr, "y_pct": y_pct, "group": grp, "location": df[cfg["location"]].astype(str)})
    n0 = len(d)
    d = d.dropna()
    d = d[(d.rsr > 0) & (d.rsr <= 1) & (d.y_pct > 0)]
    log(f"dataset: {n0} rows read, {len(d)} usable shaded observations (controls and incomplete rows dropped)")
    d["log_ratio"] = np.log10(d.y_pct) - 2
    return d


def main():
    d = load_dataset()
    res = fit_lmm(d.rsr, d.log_ratio, d.group, d.location)
    log(f"REML converged: {res.converged}; sigma = {np.sqrt(res.sigma2):.4f}; G = {np.round(res.G, 4).tolist()}")
    fit_rows = []
    for g in res.groups:
        a, b = res.coef(g)
        fit_rows.append(dict(group=g, a=a, b=b, n_obs=res.n_obs[g], n_locations=res.n_loc[g],
                             rsr_min=res.rsr_range[g][0], rsr_max=res.rsr_range[g][1]))
    pd.DataFrame(fit_rows).to_csv(OUT / "phase4_fit.csv", index=False)
    # curves for the figures (fitted mean, 95 % confidence and prediction bands) and the data actually used
    rr = np.linspace(0, 0.8, 81); crow = []
    for g in res.groups:
        mu, clo, chi = res.predict(g, rr, "confidence"); _, plo, phi = res.predict(g, rr, "prediction")
        crow += [dict(group=g, rsr=r_, mu=m_, ci_low=a_, ci_high=b_, pi_low=c_, pi_high=d_)
                 for r_, m_, a_, b_, c_, d_ in zip(rr, mu, clo, chi, plo, phi)]
    pd.DataFrame(crow).to_csv(OUT / "phase4_curves.csv", index=False)
    d.to_csv(OUT / "phase4_dataset_used.csv", index=False)

    gate_rows = []
    for g, r, pub in LAUB_PUBLISHED:
        if g not in res.groups:
            gate_rows.append(dict(group=g, rsr=r, published=pub, refit=np.nan, abs_diff=np.nan, pass_=False)); continue
        mu, lo, hi = res.predict(g, r)
        gate_rows.append(dict(group=g, rsr=r, published=pub, refit=round(float(mu[0]), 3),
                              ci_low=round(float(lo[0]), 3), ci_high=round(float(hi[0]), 3),
                              abs_diff=round(abs(float(mu[0]) - pub), 3), pass_=abs(float(mu[0]) - pub) <= GATE_TOL))
    gate = pd.DataFrame(gate_rows); gate.to_csv(OUT / "phase4_gate.csv", index=False)
    gate_ok = bool(gate.pass_.all())
    log(f"Phase 4 gate (reproduce published values within {GATE_TOL}): {'PASS' if gate_ok else 'FAIL'} "
        f"({int(gate.pass_.sum())}/{len(gate)})")

    # Field-anchor check (never fitted): does the group curve's 95 % prediction band, evaluated over the
    # anchor's reported shade range, contain the observed relative yield?
    crop_group = {c[2]: c[5] for c in CASES if c[5]}
    anc_rows = []
    for crop, ry, rlo, rhi, note, src in ANCHORS:
        g = crop_group.get(crop)
        row = dict(crop=crop, observed_rel_yield=round(ry, 3), rsr_lo=rlo, rsr_hi=rhi, group=g or "none", note=note, source=src)
        if g and g in res.groups and rlo is not None:
            rr = np.linspace(rlo, rhi, 5) if rhi > rlo else np.array([rlo])
            mu, lo, hi = res.predict(g, rr, "prediction")
            row.update(curve_mid=round(float(mu.mean()), 3), band_low=round(float(lo.min()), 3),
                       band_high=round(float(hi.max()), 3),
                       within_band=bool(lo.min() <= ry <= hi.max()))
        anc_rows.append(row)
    anc = pd.DataFrame(anc_rows); anc.to_csv(OUT / "phase4_anchor_check.csv", index=False)
    chk = anc.dropna(subset=["curve_mid"]) if "curve_mid" in anc else anc.iloc[0:0]
    log(f"Field-anchor check: {int(chk.within_band.sum()) if len(chk) else 0}/{len(chk)} anchors inside the 95 % prediction band")

    strips = pd.read_csv(OUT / "phase2_ground_strips_monthly.csv")
    energy = pd.read_csv(OUT / "phase3_energy.csv")
    gf = gross_factor()
    rows = []
    for cid, state, crop, season, months, group, grade in CASES:
        for cfg in ("C1", "C2", "C3"):
            s = strips[(strips.state == state) & (strips.config == cfg) & strips.month.isin(months) & strips.cropped]
            agg = s.groupby("y_m").agg(g=("ground_kwh_m2", "sum"), o=("open_kwh_m2", "sum"))
            strip_rsr = (1 - agg.g / agg.o).to_numpy()
            crop_share_strip = strips[(strips.state == state) & (strips.config == cfg) & (strips.month == 1)].cropped.mean()
            # cropped share of the GROSS hectare: row-field cropped share x (1 - aux land) x (1 - uncultivable)
            crop_share = crop_share_strip * gf * (1 - UNCULTIVABLE.get(cfg, 0.0))
            e = energy[(energy.state == state) & (energy.config == cfg)].iloc[0]
            row = dict(case=cid, state=state, crop=crop, season=season, config=cfg, grade=grade, group=group or "none",
                       rsr_cropped_mean=round(float(strip_rsr.mean()), 3), cropped_share=round(crop_share, 3),
                       energy_ratio=e.energy_ratio_vs_ref, mwh_per_ha=e.mwh_per_ha)
            if group and group in res.groups:
                mu, lo, hi, ex = strip_yield(res, group, strip_rsr, "prediction")
                # growing-window sensitivity (months are provisional): season extended by one month at the end
                ext = months + [months[-1] % 12 + 1]
                s2 = strips[(strips.state == state) & (strips.config == cfg) & strips.month.isin(ext) & strips.cropped]
                a2 = s2.groupby("y_m").agg(g=("ground_kwh_m2", "sum"), o=("open_kwh_m2", "sum"))
                mu_ext = strip_yield(res, group, (1 - a2.g / a2.o).to_numpy(), "prediction")[0]
                row.update(yield_rel_window_plus1=round(mu_ext, 3))
                row.update(yield_rel=round(mu, 3), yield_low=round(lo, 3), yield_high=round(hi, 3),
                           extrapolated_share=round(ex, 2), basis="group curve",
                           ler=round(mu * crop_share + e.energy_ratio_vs_ref, 3),
                           ler_low=round(lo * crop_share + e.energy_ratio_vs_ref, 3),
                           ler_high=round(hi * crop_share + e.energy_ratio_vs_ref, 3))
            else:
                anc_v = [a[1] for a in ANCHORS if a[0] == crop]
                if anc_v:
                    # NOT layout-responsive: the same field range is used for C1, C2 and C3
                    row.update(yield_low=round(min(anc_v), 3), yield_high=round(max(anc_v), 3),
                               basis="field anchors only (not layout-responsive)",
                               ler_low=round(min(anc_v) * crop_share + e.energy_ratio_vs_ref, 3),
                               ler_high=round(max(anc_v) * crop_share + e.energy_ratio_vs_ref, 3))
                else:
                    row.update(basis="no curve and no anchor: not assessed")
            rows.append(row)
    tech = pd.DataFrame(rows)
    tech.to_csv(OUT / "phase4_case_yields.csv", index=False)

    # Technical ranking, curve-based rows only (anchor-only rows do not respond to the layout, so ranking them
    # alongside curve rows would not be like-for-like; they are reported separately). Rows whose 95 % band
    # overlaps the tier leader's band share its tier.
    tech["ler_mid"] = tech[["ler_low", "ler_high"]].mean(axis=1)
    ranked = tech[tech.basis == "group curve"].sort_values("ler_mid", ascending=False).reset_index(drop=True)
    tier, tiers, top_low = 1, [], None
    for _, r in ranked.iterrows():
        if top_low is None:
            top_low = r.ler_low
        elif r.ler_high < top_low:
            tier += 1; top_low = r.ler_low
        tiers.append(tier)
    ranked["tier"] = tiers
    other = tech[tech.basis != "group curve"].assign(tier=np.nan)
    pd.concat([ranked, other], ignore_index=True).to_csv(OUT / "phase5_technical.csv", index=False)
    (OUT / "phase45_log.txt").write_text("\n".join(log_lines))
    log("written outputs")


if __name__ == "__main__":
    main()
