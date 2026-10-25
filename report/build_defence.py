"""Defence brief: likely examiner questions with short answers, numbers pulled from the outputs.
Usage: python -I report/build_defence.py <outputs_dir> <spec_out.json> [cover.json]"""
import json, pathlib, sys
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
  (f"For an unshaded open-rack array, the annual yield differs from PVGIS PVcalc by {chk.diff_pct.min():.1f} % to "
   f"{chk.diff_pct.max():.1f} %. PVGIS uses its own spectral and low-light module model, so a few percent difference is expected."
   if len(chk) else "The cross-check table is in outputs/phase3_pvgis_check.csv.")),
 ("Why use RSR, and why refit Laub et al. instead of using their numbers?",
  f"Laub et al. express shade as the relative solar radiation reduction (RSR), so our ground model computes exactly that. The "
  f"paper does not print all its coefficients in the text, so we refitted the same model form (log-ratio, quadratic in RSR, "
  f"random slopes by location, no intercept) to their public dataset by REML. The refit had to reproduce eleven published "
  f"values within 0.05 before use: {int(gate.pass_.sum())}/{len(gate)} pass. The REML code was also tested on simulated data "
  f"with known parameters."),
 ("Why a prediction band and not a confidence band?",
  "A farm in Rajasthan is a new location that was not in the meta-analysis. The prediction band adds the between-location "
  "spread of the shade response, which is the uncertainty that matters for a new site."),
 ("Your chickpea curve says about 50 % yield at 40 % shade, but CAZRI saw only a 7 % loss. Which is right?",
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
  f"{best.ler:.2f} ({best.ler_low:.2f}-{best.ler_high:.2f})."),
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
  f"Very little. One hectare of PV earns about Rs {ref.iloc[0].energy_mwh_y1 * 1000 * E.tariff_inr_per_kwh / 1e5:.0f} lakh "
  f"a year from electricity, against Rs 0.2-3 lakh net from crops. Varying crop income by +/-50 % moves the AV-PV gap far less "
  f"than the capex premium or the tariff does (sensitivity table). The weaker crop rows are labelled grade C."),
 ("What decides whether AV beats PV-only economically?",
  f"In order of influence for C2: {', '.join(rank.index[:4])}. {int((av.npv_vs_ref > 0).sum())} of {len(av)} AV combinations "
  f"beat PV-only on NPV at the base tariff; the break-even tariffs in the report show the premium an AV hectare would need."),
 ("Why no taxes, subsidies or loans?",
  "The question is which land use is better for the same hectare, not what an investor earns. Taxes and financing apply to all "
  "PV options in a similar way; subsidies are policy choices, shown as scenarios (the 'AV tariff' and 'premium covered' columns)."),
 ("Your growing months are 'typical'. What if they are wrong?",
  f"Extending each season by one month changes the predicted relative yield by at most "
  f"{(cyc.yield_rel_window_plus1 - cyc.yield_rel).abs().max():.3f}, so the conclusions do not depend on the exact dates."),
 ("What did you change in the model during the project?",
  "We fixed two bugs: a leap-day crash in the weather loader, and an RSR reference that used GHI instead of DNI cos z + DHI, "
  "which turned weather-file inconsistency into fake shade. We also put all systems on the same gross-hectare basis, added a "
  "check of the curves against field trials, and kept anchor-only crops out of the ranking (they don't respond to layout). "
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
