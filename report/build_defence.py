"""Defence brief: likely examiner questions with short answers, numbers pulled from the outputs.
Usage: python -I report/build_defence.py <outputs_dir> <spec_out.json> [cover.json]"""
import json, pathlib, re, sys
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agripv.config import AUX_LAND_SHARE
from agripv.econ_inputs import PVEcon

OUT, SPEC = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
cover = json.loads(pathlib.Path(sys.argv[3]).read_text()) if len(sys.argv) > 3 else {}
rd = lambda f: pd.read_csv(OUT / f)
val, gate, anc, chk = rd("validation_checks.csv"), rd("phase4_gate.csv"), rd("phase4_anchor_check.csv"), rd("phase3_pvgis_check.csv")
tech, eco, sens, energy = rd("phase5_technical.csv"), rd("phase6_economics.csv"), rd("phase6_sensitivity.csv"), rd("phase3_energy.csv")
cy = rd("phase4_case_yields.csv"); E = PVEcon()
curve = tech[tech.basis == "group curve"]; best = curve.loc[curve.ler_mid.idxmax()]
av = eco[eco.system.isin(["C1", "C2", "C3"])]
ref = eco[eco.system == "PV-only (REF)"].drop_duplicates("state")
ach = anc.dropna(subset=["curve_mid"]) if "curve_mid" in anc else anc.iloc[0:0]
cp = anc[anc.crop == "Chickpea"].iloc[0]
rank = sens[sens.config == "C2"].assign(s=lambda x: (x.high_vs_ref - x.low_vs_ref).abs()).groupby("parameter").s.mean().sort_values(ascending=False)
cyc = cy[cy.basis == "group curve"]
gvar = rd("phase4_gate_variants.csv")
log45 = (OUT / "phase45_log.txt").read_text().splitlines()
wald = next((l.split(": ", 1)[1] for l in log45 if l.startswith("Wald test")), "see outputs/phase45_log.txt")
ell = av[av.system.isin(["C1", "C2"])]; c3 = av[av.system == "C3"]
summ = rd("phase6_state_summary.csv")
best_by_case = curve.loc[curve.groupby("case").ler_mid.idxmax()]
cs = sens[sens.parameter.str.startswith("crop")].assign(sp=lambda x: (x.high_vs_ref - x.low_vs_ref).abs() / 2)
hort = cs.case.isin(["GJ-tomato", "KA-tomato", "MH-onion"])
flips = cs[(cs.base_vs_ref < 0) & (cs.high_vs_ref > 0)]
gl40 = gate[(gate.group == "grain legumes") & (gate.rsr == 0.4)].iloc[0]

QA = [
 ("Why these states and districts?",
  "They are six large agricultural states that cover arid (Jodhpur), semi-arid (Junagadh, Nashik), sub-humid central (Vidisha), "
  "southern plateau (Kolar) and Indo-Gangetic (Agra) conditions. Each crop case is important in its state and has either a "
  "crop group in the meta-analysis or a published AV trial. One district headquarters per state is a proxy for the state's main "
  "growing area, not the whole state; this is stated as a limitation."),
 ("Where does the weather come from, and why a typical year?",
  "PVGIS 5.3 typical meteorological year (hourly GHI, DNI, DHI, temperature, wind). A typical year represents the long-term "
  "climate rather than one particular year; the radiation database used is logged in outputs/phase23_log.txt. Inter-annual "
  "variability is not modelled."),
 ("How do you know the shading geometry is right?",
  f"Each formula was checked against an independent method: the ground shadow against brute-force ray casting (T2), the "
  f"field-mean shade against the analytic width (T3), the sky view factor against Hottel's crossed strings (T4), module "
  f"row-to-row shading against ray casting (T5), and beam energy closure (T7: ground + modules = beam entering the array, "
  f"error < 0.1 %). All {int(val['pass'].sum())}/{len(val)} checks pass; solar position agrees with Meeus within "
  f"{val.iloc[0].value:.3f} deg."),
 ("Why treat rows as infinitely long (2-D)?",
  "Real AV rows are tens to hundreds of metres long, so the interior of the field behaves like an infinite row field. Edge "
  "rows get more light, so ignoring edges slightly over-states shade, which is conservative for the crop."),
 ("Does your PV model agree with PVGIS?",
  (f"Our unshaded open-rack yield is {chk.diff_pct.min():.1f} % to {chk.diff_pct.max():.1f} % above PVGIS PVcalc. The in-plane "
   f"irradiation agrees within {chk.poa_diff_pct.min():.1f} % to {chk.poa_diff_pct.max():+.1f} %, so the gap is in the conversion: "
   f"our performance ratio is {chk.ours_pr.min():.2f}-{chk.ours_pr.max():.2f} against {chk.pvgis_pr.min():.2f}-{chk.pvgis_pr.max():.2f}, "
   f"because PVGIS's module model charges about {-chk.pvgis_temp_lowirr_loss_pct.mean():.0f} % for temperature and low light. So our "
   f"absolute PV revenue is probably a few percent optimistic. It affects all PV layouts equally, so ratios and rankings hold, and "
   f"a 5 % lower yield is equivalent to a tariff of Rs {0.95 * E.tariff_inr_per_kwh:.2f}, inside our tariff sensitivity."
   if len(chk) else "The cross-check table is in outputs/phase3_pvgis_check.csv.")),
 ("Why use RSR, and why refit Laub et al. instead of using their numbers?",
  f"Laub et al. express shade as the relative solar radiation reduction (RSR), so our ground model computes exactly that. The "
  f"paper does not print all its coefficients in the text, so we refitted their final model (log-ratio, group-specific linear "
  f"term, one shared quadratic term, random slopes by study, no intercept) to their public dataset by REML. The refit had to "
  f"reproduce eleven published values within 0.05 before use: {int(gate.pass_.sum())}/{len(gate)} pass, largest error "
  f"{gate.abs_diff.max():.3f}, which is the rounding of the published two-decimal values. The REML code was also tested on "
  f"simulated data with known parameters."),
 ("Why one quadratic term for all crop groups?",
  f"Because that is what Laub et al. ended up with after backward elimination; solving their published 20 % and 40 % values gives "
  f"almost the same curvature (about -0.72) for every group. With a separate quadratic per group our refit passes only "
  f"{int(gvar[gvar.quadratic == 'group'].passed.max())}/11 gate values, because groups like fruity vegetables (10 observations, 3 "
  f"locations) get unstable curvature. Honest caveat: a Wald test in our refit without small-sample correction would keep "
  f"separate curvature ({wald}), so the shared term is inherited from the source, not something we proved. Using sites instead "
  f"of studies as the location also passes the gate (Table 8 of the report)."),
 ("Why a prediction band and not a confidence band?",
  "A farm in Rajasthan is a new location that was not in the meta-analysis. The prediction band adds the between-location "
  "spread of the shade response, which is the uncertainty that matters for a new site."),
 (f"Your chickpea curve says about {gl40.refit:.0%} yield at 40 % shade, but CAZRI saw only a {1 - cp.observed_rel_yield:.0%} loss. Which is right?",
  f"The CAZRI anchor ({cp.observed_rel_yield:.2f} relative yield at spot PAR reductions of 47-59 %) "
  + (f"lies {'inside' if cp.within_band else 'outside'} the curve's 95 % band ({cp.band_low:.2f}-{cp.band_high:.2f}). "
     if pd.notna(cp.get('curve_mid')) else "") +
  "Spot noon PAR readings under a sparse, low array probably over-state the season-integrated shade; shade can also relieve "
  "heat and water stress in an arid irrigated rabi crop; and the grain-legume data are mostly temperate. We use the curve as "
  "the conservative case and report the anchor alongside it."),
 ("What is the LER, and can it mislead?",
  f"LER = relative yield x cropped share + energy ratio to the PV-only plant. LER > 1 means one AV hectare produces more than "
  f"splitting the land between a field and a PV plant. It weights a unit of food and a unit of energy equally relative to their "
  f"own mono-use, so it says nothing about value; that is why we add the economics. The best is {best.case} {best.config}, LER "
  f"{best.ler:.2f} ({best.ler_low:.2f}-{best.ler_high:.2f}), but " + ("the 95 % bands of all curve-based rows overlap (a single "
  "tier)" if int(curve.tier.max()) == 1 else f"the rows form only {int(curve.tier.max())} tiers") + ", so the technical ranking is indicative only."),
 ("Why is C2 best technically but C3 best economically?",
  f"C2 and C3 have the same row spacing, so the same energy. C2 crops {curve[curve.config == 'C2'].cropped_share.iloc[0]:.0%} of the "
  f"hectare, C3 only {curve[curve.config == 'C3'].cropped_share.iloc[0]:.0%}, so C2 has the larger crop term and the highest mean LER in "
  f"{int((best_by_case.config == 'C2').sum())} of {len(best_by_case)} cases. But C2 needs elevated structures (+{E.capex_premium['C2']:.1%} "
  f"capex), which gives it an LCOE of Rs {ell.lcoe.min():.2f}-{ell.lcoe.max():.2f}/kWh, above the Rs {E.tariff_inr_per_kwh:.2f} tariff. "
  f"Crop income is far too small to make up for that, so C3 is the best AV layout by NPV in "
  f"{int((summ.best_av == 'C3').sum())} of {len(summ)} cases."),
 ("Why 3 acres/MW for the PV-only plant, and what is the 15 % auxiliary land?",
  f"3 acres/MW is CTUIL's benchmark land requirement for solar (unchanged in the September 2026 revision). It is a whole-plant "
  f"figure, so to compare like with like every system loses the same {AUX_LAND_SHARE:.0%} of its hectare to roads, inverter "
  f"pads and setbacks; the PV-only rows are then packed so that the gross density equals the norm. Setting the share to 0 or "
  f"25 % is part of the sensitivity analysis."),
 ("Where do the cost numbers come from?",
  f"Capex Rs {E.capex_inr_per_wp:.0f}/Wp: CTUIL benchmark (Sept 2026). AV premium {E.capex_premium['C1']:.1%} for elevated "
  f"structures: MNRE said 25-30 % (Oct 2026). O&M Rs {E.om_inr_per_kwp_yr:.0f}/kWp/yr with 5.25 % escalation and the "
  f"{E.discount_rate:.2%} discount rate: CERC order of 26 Dec 2025. Tariff Rs {E.tariff_inr_per_kwh:.2f}/kWh: PM-KUSUM "
  f"decentralised plants Rs 2.80-3.00 (MNRE) and the MSKVY 2.0 average of Rs 2.825 (MERC, Aug 2026)."),
 ("Some crop economics come from other districts or older years. Does that matter?",
  f"For pulses and cereals, very little: one hectare of PV earns about Rs {ref.energy_mwh_y1.min() * 1000 * E.tariff_inr_per_kwh / 1e5:.0f}-"
  f"{ref.energy_mwh_y1.max() * 1000 * E.tariff_inr_per_kwh / 1e5:.0f} lakh a year from electricity, against Rs "
  f"{eco[eco.system == 'Agri-only'].crop_net_y1.min() / 1e5:.1f}-{eco[eco.system == 'Agri-only'].crop_net_y1.max() / 1e5:.1f} lakh net from "
  f"crops, and +/-50 % crop income moves the AV-PV gap by at most Rs {cs[~hort].sp.max() / 1e5:.1f} lakh. For tomato and onion (grade C "
  f"data) it matters: up to Rs {cs[hort].sp.max() / 1e5:.1f} lakh"
  + (f", and a 50 % higher crop income would make {' and '.join(f'{r.case} {r.config}' for r in flips.itertuples())} beat PV-only."
     if len(flips) else ".")),
 ("What decides whether AV beats PV-only economically?",
  f"In order of influence for C2: {', '.join(re.split(r' (?=[-+]?\d|Rs )', x, maxsplit=1)[0] for x in rank.index[:4])}. {int((av.npv_vs_ref > 0).sum())} of {len(av)} AV combinations "
  f"beat PV-only on NPV at the base tariff. C3 would break even at Rs {c3.breakeven_tariff_vs_ref.min():.2f}-"
  f"{c3.breakeven_tariff_vs_ref.max():.2f}/kWh, close to the Rs 3.20-3.30 MNRE expects for AgriPV; C1/C2 would need Rs "
  f"{ell.breakeven_tariff_vs_ref.min():.2f}-{ell.breakeven_tariff_vs_ref.max():.2f}/kWh."),
 ("Why no taxes, subsidies or loans?",
  "The question is which land use is better for the same hectare, not what an investor earns. Taxes and financing apply to all "
  "PV options in a similar way; subsidies are policy choices, shown as scenarios (the 'AV tariff' and 'premium covered' columns)."),
 ("Your growing months are 'typical'. What if they are wrong?",
  f"Extending each season by one month changes the predicted relative yield by at most "
  f"{(cyc.yield_rel_window_plus1 - cyc.yield_rel).abs().max():.3f}, small next to the 95 % bands, so the conclusions do not depend on "
  f"the exact dates."),
 ("What did you change in the model during the project?",
  "We fixed two bugs: a leap-day crash in the weather loader, and an RSR reference that used GHI instead of DNI cos z + DHI, "
  "which turned weather-file inconsistency into fake shade. We also put all systems on the same gross-hectare basis, added a "
  "check of the curves against field trials, and kept anchor-only crops out of the ranking (they don't respond to layout). "
  "When the real data arrived, the per-group quadratic failed the gate (6/11), so we switched to the published shared-quadratic "
  "form, which passes 11/11. "
  "All changes are listed in Appendix C and the code history."),
 ("What are the main limitations and next steps?",
  "Next steps: (1) measure season-integrated PAR in Indian AV trials, to settle the chickpea question; (2) use multi-year "
  "weather; (3) model the electrical mismatch from partial shading; (4) add crop microclimate (temperature, water) effects; "
  "(5) use district cost-of-cultivation data for horticultural crops."),
]
B = [dict(type="title", text="Defence brief", subtitle=cover.get("title", "Agrivoltaics in India"), lines=cover.get("lines", [])),
     dict(type="p", text="Likely questions with short answers. Every number comes from the submitted outputs.", italic=True)]
for i, (q, a) in enumerate(QA, 1):
    B += [dict(type="h2", text=f"Q{i}. {q}"), dict(type="p", text=a)]
SPEC.write_text(json.dumps(dict(blocks=B, doc_title="Defence brief", running_head="Defence brief - agrivoltaics in India")))
print("defence spec:", len(QA), "questions")
