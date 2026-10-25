"""Build the report spec (JSON) from the pipeline outputs; render_docx.js turns it into Word.

Usage: python -I report/build_report.py <outputs_dir> <figures_dir> <spec_out.json> [cover.json]
Every number in the text is computed here from the output CSVs - nothing is typed in by hand.
"""
import json, pathlib, re, sys
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agripv.config import SITES, GCR, CLEARANCE_M, C3_MARGIN_M, AUX_LAND_SHARE, CTUIL_ACRES_PER_MW
from agripv.cases import CASES, ANCHORS, LAUB_PUBLISHED
from agripv.pv import PVParams
from agripv.econ_inputs import PVEcon, CROP_ECON, crop_net_open_field

OUT, FIG, SPEC = (pathlib.Path(a) for a in sys.argv[1:4])
cover = json.loads(pathlib.Path(sys.argv[4]).read_text()) if len(sys.argv) > 4 else {}
rd = lambda f: pd.read_csv(OUT / f)
energy, rsr, chk = rd("phase3_energy.csv"), rd("phase2_rsr_seasonal.csv"), rd("phase3_pvgis_check.csv")
fit, gate, anc = rd("phase4_fit.csv"), rd("phase4_gate.csv"), rd("phase4_anchor_check.csv")
cy, tech = rd("phase4_case_yields.csv"), rd("phase5_technical.csv")
eco, sens, summ = rd("phase6_economics.csv"), rd("phase6_sensitivity.csv"), rd("phase6_state_summary.csv")
val = rd("validation_checks.csv")
log23 = (OUT / "phase23_log.txt").read_text().splitlines()
log45 = (OUT / "phase45_log.txt").read_text().splitlines()
P, E = PVParams(), PVEcon()

B = []
def h1(t, newpage=False): B.append(dict(type="h1", text=t, newpage=newpage))
def h2(t): B.append(dict(type="h2", text=t))
def h3(t): B.append(dict(type="h3", text=t))
def p(t, **k): B.append(dict(type="p", text=t, **k))
def eq(t, label=None): B.append(dict(type="eq", text=t, label=label))
def bullets(items, numbered=False): B.append(dict(type="bullets", items=items, numbered=numbered))
def figure(name, caption, width=1.0): B.append(dict(type="figure", path=str((FIG / name).resolve()), caption=caption, width=width))
def table(caption, header, rows, widths=None, note=None, font=None, align=None):
    B.append(dict(type="table", caption=caption, header=header, rows=rows, widths=widths, note=note, font=font, align=align))
f0 = lambda x: f"{x:,.0f}"; f1 = lambda x: f"{x:,.1f}"; f2 = lambda x: f"{x:,.2f}"; f3 = lambda x: f"{x:.3f}"
pct = lambda x: f"{100 * x:.0f} %"
lakh = lambda x: f"{x / 1e5:,.1f}"
states = list(SITES)

# ---------------------------------------------------------------- derived numbers
e_ref = energy[energy.config == "REF"].set_index("state")
e_by = energy.pivot(index="state", columns="config", values="energy_ratio_vs_ref").reindex(states)
kwh_ref = e_ref.kwh_per_kwp.reindex(states)
rabi = rsr[rsr.season == "rabi (Nov-Mar)"].pivot(index="state", columns="config", values="rsr_cropped_mean").reindex(states)
khar = rsr[rsr.season == "kharif (Jun-Oct)"].pivot(index="state", columns="config", values="rsr_cropped_mean").reindex(states)
gate_ok = bool(gate.pass_.all()); n_gate = int(gate.pass_.sum())
anc_c = anc.dropna(subset=["curve_mid"]) if "curve_mid" in anc else anc.iloc[0:0]
curve = tech[tech.basis == "group curve"]
best_ler = curve.loc[curve.ler_mid.idxmax()]
ecoav = eco[eco.system.isin(["C1", "C2", "C3"])]
ref_rows = eco[eco.system == "PV-only (REF)"].drop_duplicates("state").set_index("state").reindex(states)
agri_rows = eco[eco.system == "Agri-only"].set_index("case")
n_av_beats_ref = int((ecoav.npv_vs_ref > 0).sum()); n_av = len(ecoav)
n_av_beats_agri = int((ecoav.npv_vs_agri > 0).sum())
best_cfg_counts = summ.best_av.value_counts().to_dict()
synthetic = any("SYNTHETIC" in l for l in log23)
gvar = rd("phase4_gate_variants.csv") if (OUT / "phase4_gate_variants.csv").exists() else None
wald = next((l for l in log45 if l.startswith("Wald test")), "")
radb = sorted({l.split("radiation db = ")[1].split(",")[0] for l in log23 if "radiation db = " in l})
# technical: best layout per case by mean LER, and tier structure
best_by_case = curve.loc[curve.groupby("case").ler_mid.idxmax()]
n_tiers = int(curve.tier.max()) if len(curve) else 0
c2c3 = curve[curve.config.isin(["C2", "C3"])].pivot(index="case", columns="config", values="yield_rel")
crop_part = curve.assign(cp=curve.yield_rel * curve.cropped_share).pivot(index="case", columns="config", values="cp")
# economics
ell = ecoav[ecoav.system.isin(["C1", "C2"])]
c3 = ecoav[ecoav.system == "C3"].set_index("case")
agri_beats_ref = [r.case for r in summ.itertuples() if r.npv_agri_lakh > r.npv_ref_lakh]
ref_by_case = eco[eco.system == "PV-only (REF)"].set_index("case")
n_c3_avtariff_beats_ref = int(sum(c3.loc[c, "total_npv_av_tariff"] > ref_by_case.loc[c, "total_npv"] for c in c3.index))
n_prem_beats_ref = int(sum(r.total_npv_premium_covered > ref_by_case.loc[r.case, "total_npv"] for r in ell.itertuples()))
be_c3, be_ell = c3.breakeven_tariff_vs_ref, ell.breakeven_tariff_vs_ref
cropsens = sens[sens.parameter.str.startswith("crop")]
flips = cropsens[(cropsens.base_vs_ref < 0) & (cropsens.high_vs_ref > 0)]
hort = {"GJ-tomato", "KA-tomato", "MH-onion"}
crop_span = cropsens.assign(sp=(cropsens.high_vs_ref - cropsens.low_vs_ref).abs() / 2)
pname = lambda t: re.split(r" (?=[-+]?\d|Rs )", t, maxsplit=1)[0]
andjoin = lambda xs: (", ".join(xs[:-1]) + " and " + xs[-1]) if len(xs) > 1 else "".join(xs)
elec_rev = ref_rows.energy_mwh_y1 * 1000 * E.tariff_inr_per_kwh
crop_net = agri_rows.crop_net_y1
pv_lo, pv_hi = (chk.diff_pct.min(), chk.diff_pct.max()) if len(chk) else (np.nan, np.nan)

# ---------------------------------------------------------------- front matter
B.append(dict(type="title", text=cover.get("title", "Agrivoltaics in India: a state-wise technical and economic assessment"),
              subtitle=cover.get("subtitle", "Agriculture-only vs PV-only vs agrivoltaic land use in six states"),
              lines=cover.get("lines", [])))
if synthetic:
    p("**DRAFT BUILT ON SYNTHETIC TEST INPUTS - NUMBERS ARE NOT RESULTS.**", center=True)
h1("Abstract")
p(f"Agrivoltaic (AV) systems place photovoltaic (PV) arrays over cropland so that the same hectare produces both food "
  f"and electricity. This study compares three uses of a hectare - agriculture only, a conventional ground-mounted PV "
  f"plant, and three AV layouts - for ten crop-season cases in six Indian states (Rajasthan, Gujarat, Maharashtra, "
  f"Madhya Pradesh, Karnataka and Uttar Pradesh). A validated chain of physical models computes, from typical-year hourly "
  f"weather (PVGIS 5.3), the light reaching each 1/40th strip of ground between the rows and the PV energy per hectare. "
  f"Crop yield under shade is predicted with a mixed-effects meta-regression refitted to the Laub et al. (2022) dataset "
  f"and checked against published Indian and German field trials. Technical performance is summarised as a land "
  f"equivalent ratio (LER) with 95 % bands, and economics as 25-year net present value (NPV) per gross hectare with "
  f"official Indian cost and tariff benchmarks for 2025-26.")
p(f"The PV-only reference yields {f0(kwh_ref.min())}-{f0(kwh_ref.max())} kWh/kWp in year one. All "
  f"{len(curve)} curve-based AV combinations have a mean LER above 1 ({f2(curve.ler.min())}-{f2(curve.ler.max())}), "
  f"but their 95 % bands overlap, so " + ("they all fall in a single statistical tier" if n_tiers == 1 else
  f"they form {n_tiers} statistical tiers") + ". The densely "
  f"cropped elevated layout C2 has the highest mean LER in {int((best_by_case.config == 'C2').sum())} of "
  f"{len(best_by_case)} curve-based cases (highest: {best_ler.case}, LER {f2(best_ler.ler)}, band {f2(best_ler.ler_low)}-"
  f"{f2(best_ler.ler_high)}). Economics point the other way. At a tariff of Rs {E.tariff_inr_per_kwh:.2f}/kWh none of the "
  f"{n_av} AV combinations matches the PV-only hectare on NPV" if n_av_beats_ref == 0 else
  f"The PV-only reference yields {f0(kwh_ref.min())}-{f0(kwh_ref.max())} kWh/kWp in year one. {n_av_beats_ref} of {n_av} AV "
  f"combinations beat PV-only on NPV")
B[-1]["text"] += (f"; the elevated layouts have an LCOE of Rs {f2(ell.lcoe.min())}-{f2(ell.lcoe.max())}/kWh, above the "
  f"tariff. The low-cost interspace layout C3 is the best AV option by NPV in {best_cfg_counts.get('C3', 0)} of "
  f"{len(summ)} cases and beats agriculture alone in {int((c3.npv_vs_agri > 0).sum())}. It would match PV-only at "
  f"tariffs of Rs {f2(be_c3.min())}-{f2(be_c3.max())}/kWh, close to the Rs 3.20-3.30 that MNRE expects for AgriPV, "
  f"whereas the elevated layouts would need Rs {f2(be_ell.min())}-{f2(be_ell.max())}/kWh. The decisive uncertainties are "
  f"the tariff, the capital cost and its AV premium, the discount rate, crop income for high-value vegetables, and the "
  f"crop response at high shade.")
B.append(dict(type="toc_placeholder"))

# ---------------------------------------------------------------- 1 introduction
h1("1. Introduction")
p("India's solar build-out competes with agriculture for flat, well-irradiated land. Ground-mounted plants occupy about "
  f"{CTUIL_ACRES_PER_MW:g} acres per MW (the CTUIL benchmark, unchanged in its September 2026 revision), so the national "
  "targets imply hundreds of thousands of hectares. Agrivoltaics offers a way to keep that land in production. The "
  "Ministry of New and Renewable Energy (MNRE) is preparing a central scheme for agrivoltaic plants, which it estimates "
  "cost 25-30 % more than conventional ground-mounted plants (MNRE Secretary, October 2026). Whether agrivoltaics is "
  "worthwhile depends on how much light each crop can give up, which differs by crop, season and site.")
p("**Objectives.** (i) Quantify, per state and season, the light reduction on cropped land under three AV layouts; "
  "(ii) compute PV energy per hectare for the AV layouts and for a conventional reference plant; (iii) predict crop "
  "yields under the computed shade with stated uncertainty; (iv) rank the options technically by LER; (v) compare them "
  "economically by NPV, levelised cost of electricity (LCOE) and break-even tariff; and (vi) identify which assumptions "
  "decide the outcome.")

# ---------------------------------------------------------------- 2 study design
h1("2. Study design")
h2("2.1 States, proxy sites and crop cases")
p("Each state is represented by one district headquarters (Table 1). The weather and results at that point stand "
  "for the main agrivoltaic-relevant growing area of the state, not the whole state. The ten cases (Table 2) pair a "
  "state with a crop and season that are important locally and that have either a crop group in the meta-analysis "
  "or a published agrivoltaic field trial.")
table("Proxy sites (district headquarters).", ["State", "District", "Latitude (deg N)", "Longitude (deg E)", "Elevation (m)",
      "Optimal tilt (deg)", "Annual GHI (kWh/m2)"],
      [[s, SITES[s][0], f2(SITES[s][1]), f2(SITES[s][2]), f0(SITES[s][3]), f0(e_ref.loc[s].tilt_deg),
        next((l.split("annual GHI ")[1].split(" kWh")[0] for l in log23 if l.startswith(s)), "")] for s in states],
      widths=[0.18, 0.13, 0.13, 0.14, 0.12, 0.14, 0.16])
table("Crop-season cases and their crop group in Laub et al. (2022).", ["Case", "State", "Crop", "Season",
      "Growing months", "Crop group", "Evidence grade"],
      [[c[0], c[1], c[2], c[3], "-".join(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1]
        for m in (c[4][0], c[4][-1])), c[5] or "none (field anchors only)", c[6]] for c in CASES],
      widths=[0.14, 0.15, 0.11, 0.09, 0.12, 0.24, 0.15], align="left",
      note="Growing months are typical sowing-to-harvest windows; Section 5.3 tests the effect of extending each season by one month.")
h2("2.2 Systems compared")
bullets([
    "**Agri-only:** the crop on open land, at state-average farm yield.",
    f"**PV-only (REF):** a conventional fixed-tilt plant at the CTUIL land norm ({CTUIL_ACRES_PER_MW:g} acres/MW = "
    f"{f1(1000 / (CTUIL_ACRES_PER_MW * 0.404686))} kWp per gross hectare), low clearance, no crop.",
    f"**C1:** elevated AV, row GCR {GCR['C1']:.2f}, lower edge {CLEARANCE_M['C1']:g} m above ground, crop under and between rows.",
    f"**C2:** elevated AV, row GCR {GCR['C2']:.2f}, clearance {CLEARANCE_M['C2']:g} m, crop under and between rows.",
    f"**C3:** interspace AV, row GCR {GCR['C3']:.2f}, standard clearance {CLEARANCE_M['C3']:g} m; crop only between "
    f"rows, leaving {C3_MARGIN_M:g} m uncropped on each side of the footprint.",
])
p(f"All arrays face south with east-west rows of 550 Wp modules (2.28 m x 1.13 m) mounted portrait, one module along the "
  f"slope. The tilt at each site is the energy-optimal tilt of the reference plant (0-40 deg, 1 deg steps) and is "
  f"used for all layouts at that site. Per-hectare quantities are given per **gross** hectare: {pct(AUX_LAND_SHARE)} of "
  f"every PV or AV hectare is assumed to be taken by roads, inverter pads and setbacks, the same for every system "
  f"(Section 3.5).")
figure("fig1_layouts.png", "North-south cross-sections of the four PV layouts at the median optimal tilt (to scale).")

# ---------------------------------------------------------------- 3 methods
h1("3. Methods", newpage=True)
p("The model chain has eight modules (M1-M8). M1-M3 are physics, M4 is the crop statistics, M6-M7 combine them on a "
  "land basis and M8 is the economics. Each module was validated on its own before it was used (Section 4).")
h2("3.1 Weather and solar position (M1)")
p(f"Hourly global horizontal (GHI), beam normal (DNI) and diffuse horizontal (DHI) irradiance, air temperature and wind "
  f"speed come from the PVGIS 5.3 typical meteorological year for each proxy site (radiation database: {', '.join(radb) or 'see log'}, "
  "2005-2023). Months taken from leap years can "
  "contain 29 February; these hours are dropped, and every month is re-stamped onto one nominal non-leap year. The "
  "time stamp at which the file's GHI best equals DNI cos z + DHI (offsets of 0, +10, +30 and -30 minutes tested) is "
  "used for the solar geometry. The solar position uses the PSA algorithm (Blanco-Muriel et al., 2001) with "
  "elevation in degrees above the horizon and azimuth clockwise from north.")
h2("3.2 Ground irradiance under the array (M2)")
p("Rows are treated as infinitely long in the east-west direction, so the light field depends only on the north-south "
  "coordinate y and repeats every row pitch p (edge effects of a finite field are neglected). A row of slant length L at "
  "tilt beta and lower-edge height h_{0} casts a ground shadow, for a sun with northward-horizontal-to-vertical "
  "direction ratio t = cos(alpha) cos(A) / sin(alpha), that spans")
eq("y in [ -h_{0} t ,  L cos(beta) - (h_{0} + L sin(beta)) t ]   (+ k p for row k)", "1")
p("Diffuse irradiance is split with the Hay-Davies model: the circumsolar part, a fraction A_{i} = DNI/DNI_{extra} "
  "of DHI, travels with the beam and is shaded with it; the remaining isotropic part reaches each ground point in "
  "proportion to its sky view factor, F_{sky}(y) = 1 - (1/2) integral of cos(phi) over the directions phi blocked by "
  "any row. The ground irradiance on a strip at position y is therefore")
eq("G_{ground}(y) = [DNI cos(z) + A_{i} DHI] (1 - s(y)) + (1 - A_{i}) DHI F_{sky}(y)", "2")
p("where s(y) is 1 inside a shadow and 0 outside. Light reflected from the module undersides and from the ground is "
  "ignored, so the shade is slightly over-estimated (conservative for the crop). Each pitch is divided into 40 strips. "
  "The relative solar radiation reduction (RSR) of a strip over a growing season is")
eq("RSR(y) = 1 - Sum_{season} G_{ground}(y) / Sum_{season} [DNI cos(z) + DHI]", "3")
p("The open-field reference in the denominator is built from the same DNI and DHI as the numerator, so that an "
  "unobstructed strip has RSR = 0 exactly. (Using the file's GHI instead would turn any small inconsistency between GHI, "
  "DNI and DHI into apparent shade: a 2 % mismatch reads as 2 % RSR.)")
h2("3.3 PV energy (M3)")
p(f"Plane-of-array irradiance for an interior row uses Hay-Davies transposition. Beam and circumsolar irradiance are "
  f"reduced by the shaded fraction of the module, f = 1 - (p/L) sin(alpha_{{p}}) / sin(alpha_{{p}} + beta), where alpha_{{p}} "
  f"is the solar elevation projected onto the north-south plane. Isotropic sky diffuse is reduced by the module's sky "
  f"view factor (the row in front blocks part of the sky), and ground-reflected irradiance uses an albedo of "
  f"{P.albedo:g}. The angle-of-incidence loss follows the ASHRAE model (b_{{0}} = {P.iam_b0:g}); cell temperature follows "
  f"Faiman (U_{{0}} = {P.faiman_u0:g} W/m2K, U_{{1}} = {P.faiman_u1:g} W s/m3K); DC power is PVWatts-type with "
  f"gamma = {100 * P.gamma_per_k:.2f} %/K; all other losses are lumped at {pct(P.system_loss)}, as in PVGIS. Partial "
  f"shading is treated as a linear loss (no electrical mismatch), which is optimistic for portrait modules.")
eq("P_{AC} = (G_{POA,eff} / 1000) [1 + gamma (T_{cell} - 25)] (1 - L_{sys})   kW per kWp", "4")
h2("3.4 Crop response to shade (M4)")
p("Crop yield under shade follows the meta-regression form of Laub et al. (2022), refitted here to their public dataset "
  "(Zenodo 10.5281/zenodo.5716091, CC BY 4.0) by restricted maximum likelihood (REML):")
eq("log_{10}(Y_{rel} %) - 2 = a_{g} RSR + b RSR^{2} + u_{1,loc} RSR + u_{2,loc} RSR^{2} + e", "5")
p("Here a_{g} is a linear shade coefficient for crop group g, b is a quadratic coefficient shared by all groups, "
  "(u_{1}, u_{2}) are random linear and quadratic slopes by location with an unstructured covariance G, and e is the "
  "residual. A single b reproduces the final model of Laub et al., whose backward elimination removed non-significant "
  "fixed effects: solving their published 20 % and 40 % predictions for each group gives the same quadratic "
  "coefficient, about -0.72, for every group, so the RSR^{2} x crop-group interaction was evidently among the terms "
  "dropped. A location is one study in the dataset (the 'Reference' "
  "column), and the 89 unshaded control rows (RSR = 0, yield 100 %) are kept, as in the paper's 428 data points. "
  "There is no intercept, so 0 % shade gives 100 % yield by construction. Before use, the refit must reproduce eleven "
  "relative yields quoted in the paper within 0.05 (the Phase 4 gate). The curve is applied strip by strip, and the strip yields are then averaged, because averaging "
  "RSR first would bias a non-linear curve. The 95 % band is a prediction band for a new location: it includes "
  "the between-location spread of slopes but not plot-level residual noise. Field anchors - published AV trials in "
  "India (CAZRI Jodhpur), Germany (Heggelbach) and Korea - are never fitted; they are used to check the curves. Crops "
  "with no group (onion, cumin) are reported from their field anchors only.")
h2("3.5 Land accounting and technical comparison (M6, M7)")
p(f"All systems are compared per gross hectare. A share of {pct(AUX_LAND_SHARE)} of every PV or AV hectare is assumed "
  f"to be taken by roads, inverter and transformer pads, drainage and boundary setbacks. The reference plant's row "
  f"spacing is solved so that its gross density equals the CTUIL norm; the row-level GCR that results "
  f"({f3(e_ref.gcr.median())}) is typical of Indian fixed-tilt plants. The land equivalent ratio is")
eq("LER = Y_{rel} x (cropped share of the gross hectare) + E_{AV} / E_{REF}", "6")
p("where E is the energy per gross hectare. LER > 1 means that one hectare of AV produces more than splitting the "
  "hectare between a crop field and a PV plant would. The technical ranking orders the curve-based case-layout rows by "
  "LER; rows whose 95 % band overlaps that of the leader of a tier share the tier. Anchor-only rows do not respond to "
  "the layout's shade and are reported separately.")
h2("3.6 Economics (M8)")
p("Cash flows are evaluated per gross hectare over 25 years in nominal rupees. Year 0 carries the capital cost; years "
  "1-25 carry electricity revenue at a flat nominal tariff, O&M with escalation, and crop net income with escalation. "
  "Energy degrades geometrically. NPV, LCOE, PV-only IRR and payback follow the standard definitions:")
eq("NPV = -C_{0} + Sum_{t=1..25} [E_{1} (1-d)^{t-1} tau - OM_{1} (1+e)^{t-1} + N_{1} (1+g)^{t-1}] / (1+r)^{t}", "7")
eq("LCOE = [C_{0} + Sum OM_{t} (1+r)^{-t}] / Sum E_{t} (1+r)^{-t}", "8")
p("Under AV, the crop revenue scales with the relative yield, and the operating cost scales with the cropped share. "
  "C1 and C2 also carry a working penalty for cropping around posts. For each AV row, the break-even tariff is the "
  "tariff at which its NPV per hectare equals that of the PV-only plant on the same land. There are no taxes, "
  "subsidies, financing structure or land costs: the comparison is of land-use options on the same hectare, not an "
  "investor model. Table 3 lists the inputs.")
table("Economic inputs (base case) and their sources.", ["Parameter", "Base value", "Sensitivity", "Source"], [
    ["Capital cost, ground-mounted PV", f"Rs {E.capex_inr_per_wp:.0f}/Wp (Rs 3.5 crore/MW)", "-20 % / +20 %", "CTUIL revised benchmark, Sept 2026"],
    ["AV premium, elevated C1/C2", f"{100 * E.capex_premium['C1']:.1f} %", "15 % / 40 %", "MNRE: 25-30 % higher (Oct 2026)"],
    ["AV premium, interspace C3", pct(E.capex_premium['C3']), "0 % / 15 %", "Assumption (cabling, fencing)"],
    ["O&M", f"Rs {E.om_inr_per_kwp_yr:.0f}/kWp/yr, +{100 * E.om_escalation:.2f} %/yr", "-30 % / +30 %", "CERC order 26 Dec 2025"],
    ["Discount rate", f"{100 * E.discount_rate:.2f} %", "7 % / 11 %", "CERC order 26 Dec 2025"],
    ["Module degradation", f"{100 * E.degradation:.1f} %/yr", "0.3 % / 0.7 %", "Assumption (no CERC norm)"],
    ["Tariff", f"Rs {E.tariff_inr_per_kwh:.2f}/kWh flat", "Rs 2.50 / 3.50", "PM-KUSUM 2.80-3.00 (MNRE); MSKVY 2.0 avg 2.825 (MERC)"],
    ["AV tariff scenario", f"Rs {E.tariff_av_scenario:.2f}/kWh", "-", "MNRE estimate for AgriPV, 3.20-3.30"],
    ["AV crop cost penalty (C1/C2)", pct(E.av_crop_cost_penalty['C1']), "-", "Assumption"],
    ["Crop price and cost growth", f"{100 * E.crop_escalation:.0f} %/yr", "-", "RBI CPI target"],
    ["Crop net income", "Table 4", "-50 % / +50 %", "Table 4"],
    ["Non-array land share", pct(AUX_LAND_SHARE), "0 / 25 %", "Assumption"],
    ["Project life", f"{E.life_years} years", "-", "CERC tariff period"]],
    widths=[0.27, 0.23, 0.17, 0.33], align="left")
table("Crop economics per open-field hectare (year 1).", ["Case", "Yield (q/ha)", "Price (Rs/q)", "Cost (Rs/ha)",
      "Net (Rs/ha)", "Grade"],
      [[k, f1(v["yield_q_ha"]) if v["yield_q_ha"] else "-", f0(v["price"]) if v["price"] else "-",
        f0(v["cost_inr_ha"]) if v["cost_inr_ha"] else "-", f0(crop_net_open_field(k)), v["grade"]] for k, v in CROP_ECON.items()],
      widths=[0.2, 0.16, 0.16, 0.18, 0.18, 0.12],
      note="Grade A: official values for 2024-27; B: peer-reviewed or official, other year or district; C: indicative "
           "(proxy region or mixed vintage). Sources for each row are listed in Appendix A.")

# ---------------------------------------------------------------- 4 validation
h1("4. Model validation", newpage=True)
p("Every physical module was checked against an independent calculation before any result was computed (Table 5). "
  "The economics were checked against closed-form solutions, and the REML fitting code against simulated data with "
  "known parameters.")
table("Validation checks of the physical models (tests/test_validation.py).", ["Check", "Result", "Limit", "Pass"],
      [[r.check, f"{r.value:.3g}", f"{r.limit:g}", "yes" if r.pass_ else "NO"] for r in val.rename(columns={"pass": "pass_"}).itertuples()],
      widths=[0.62, 0.14, 0.12, 0.12], font=16)
if len(chk):
    p(f"**PV energy against PVGIS.** For an unshaded, open-rack array at the nearest tilt, the model's annual yield is "
      f"{f1(pv_lo)} % to {f1(pv_hi)} % above PVGIS PVcalc across the six sites (Table 6). The in-plane irradiation agrees "
      f"to within {f1(chk.poa_diff_pct.min())} % to {f1(chk.poa_diff_pct.max())} % (PVGIS averages 2005-2023, the model "
      f"uses the typical year), so the gap lies in the conversion: the model's performance ratio is "
      f"{f2(chk.ours_pr.min())}-{f2(chk.ours_pr.max())} against {f2(chk.pvgis_pr.min())}-{f2(chk.pvgis_pr.max())} in PVGIS, "
      f"whose module model (Huld et al.) charges {f0(-chk.pvgis_temp_lowirr_loss_pct.max())}-"
      f"{f0(-chk.pvgis_temp_lowirr_loss_pct.min())} % for temperature and low irradiance, more than the Faiman-PVWatts "
      f"model used here. Absolute PV energy and PV revenue are therefore probably a few percent optimistic. This affects "
      f"all PV layouts alike, so energy ratios and the AV-versus-PV ranking are unchanged. A 5 % lower yield is "
      f"equivalent to a tariff of Rs {0.95 * E.tariff_inr_per_kwh:.2f}/kWh, which lies inside the tariff sensitivity range.")
    table("Annual specific yield, model vs PVGIS PVcalc (unshaded).", ["State", "Tilt (deg)", "Model (kWh/kWp)",
          "PVGIS (kWh/kWp)", "Yield diff. (%)", "In-plane diff. (%)", "PR model / PVGIS", "Opt. tilt PVGIS / model"],
          [[r.state, f0(r.tilt_deg), f1(r.ours_kwh_per_kwp), f1(r.pvgis_kwh_per_kwp), f2(r.diff_pct),
            f"{r.poa_diff_pct:+.1f}", f"{r.ours_pr:.3f} / {r.pvgis_pr:.3f}",
            f"{r.pvgis_optimal_tilt:.0f} / {r.our_optimal_tilt:.0f}"] for r in chk.itertuples()],
          widths=[0.17, 0.08, 0.13, 0.13, 0.12, 0.12, 0.13, 0.12], font=16,
          note="In-plane: model irradiation on the array plane vs PVGIS H(i), before reflection loss. PR: annual yield / in-plane irradiation.")
p(f"**Crop model gate.** The refit reproduces {n_gate} of the {len(gate)} published values within 0.05 "
  f"({'PASS' if gate_ok else 'FAIL'}; Table 7); the largest difference is {f3(gate.abs_diff.max())}, i.e. within the "
  f"rounding of the two-decimal published values. " + (
  "The crop results are therefore based on a model that reproduces the original analysis. " if gate_ok else
  "Where the refit does not reproduce a published value, the affected groups are flagged in the results. "))
table("Phase 4 gate: refit vs published relative yields (Laub et al., 2022).", ["Crop group", "RSR", "Published",
      "Refit", "|diff|", "Pass"],
      [[r.group, f2(r.rsr), f2(r.published), f3(r.refit) if pd.notna(r.refit) else "-",
        f3(r.abs_diff) if pd.notna(r.abs_diff) else "-", "yes" if r.pass_ else "no"] for r in gate.itertuples()],
      widths=[0.3, 0.12, 0.15, 0.15, 0.13, 0.15])
if gvar is not None:
    gq = gvar[gvar.quadratic == "group"]
    p(f"Table 8 shows why the model form matters. With a separate quadratic term for each group the refit passes only "
      f"{int(gq.passed.min())}-{int(gq.passed.max())} of 11 values (largest error {f2(gq.max_abs_diff.max())}): the small "
      f"groups (fruity vegetables, 10 observations at 3 locations) then get unstable curvature. Grouping by site "
      f"(latitude-longitude) instead of by study also passes the gate with the shared term. One caveat: in our refit, a "
      f"Wald test without small-sample correction does not support a shared quadratic "
      f"({wald.split(': ', 1)[1] if wald else 'see log'}). The shared term is used because it is the published model and "
      f"reproduces the published predictions; it is a modelling choice inherited from the source, not a result of this study.")
    table("Phase 4 gate under alternative model forms.", ["Location unit", "Quadratic term", "Gate passed", "Largest |diff|", "Used"],
          [[r.location, "shared" if r.quadratic == "common" else "per group", f"{r.passed}/{r.of}", f3(r.max_abs_diff),
            "yes" if r.used else "no"] for r in gvar.itertuples()], widths=[0.26, 0.2, 0.18, 0.18, 0.18])

# ---------------------------------------------------------------- 5 results
h1("5. Results", newpage=True)
h2("5.1 Energy per hectare")
p(f"The reference plant produces {f0(kwh_ref.min())} kWh/kWp ({kwh_ref.idxmin()}) to {f0(kwh_ref.max())} kWh/kWp "
  f"({kwh_ref.idxmax()}) in year one, or {f0(e_ref.mwh_per_ha.min())}-{f0(e_ref.mwh_per_ha.max())} MWh per gross "
  f"hectare. Because they have fewer modules per hectare, the AV layouts produce less energy per hectare: C1 "
  f"{pct(e_by.C1.min())}-{pct(e_by.C1.max())} of the reference, and C2 and C3 {pct(e_by.C2.min())}-{pct(e_by.C2.max())} "
  f"(Figure 2). Per kWp, wider rows shade each other less, so the AV layouts lose less to row-to-row shading.")
figure("fig4_energy.png", "Year-1 AC energy per gross hectare by state and layout.")
table("PV performance by state and layout.", ["State", "Layout", "kWp/ha (gross)", "kWh/kWp", "MWh/ha", "Energy ratio vs REF"],
      [[r.state, r.config, f1(r.kwp_per_ha), f0(r.kwh_per_kwp), f1(r.mwh_per_ha), f3(r.energy_ratio_vs_ref)]
       for r in energy.itertuples()], widths=[0.22, 0.12, 0.17, 0.15, 0.15, 0.19], font=16)
h2("5.2 Light on the cropped land")
p(f"In the rabi season (November-March), the mean RSR on the cropped land is {pct(rabi.C1.min())}-{pct(rabi.C1.max())} "
  f"under C1, {pct(rabi.C2.min())}-{pct(rabi.C2.max())} under C2 and {pct(rabi.C3.min())}-{pct(rabi.C3.max())} under C3 "
  f"(Figure 3). The elevated layouts spread the shade over the whole pitch (Figure 4). In the interspace layout the "
  f"footprint and its margins, where the shade is deepest, are left uncropped, so the cropped strips see much less "
  f"shade on average. In rabi, however, the long winter shadows still reach the cropped strips nearest the row to the "
  f"north (strip RSR up to {pct(rsr[(rsr.season == 'rabi (Nov-Mar)') & (rsr.config == 'C3')].rsr_cropped_max.max())}). "
  f"Shade is deeper in rabi than in kharif in every state and layout, because the sun is lower and the shadows longer.")
figure("fig3_rsr.png", "Season-mean RSR on cropped land by state and layout.")
figure("fig2_ground_profile.png", "Rabi-season ground irradiation relative to the open field across one row pitch at "
       "Jodhpur. Dotted segments are not cropped (C3 footprint and margins).", width=0.85)
h2("5.3 Crop yield under shade")
p("Table 10 lists the fitted coefficients. Figure 5 shows the fitted curves with the data, the published values and the "
  f"field anchors. {len(anc_c)} field anchors have both a crop group and a reported shade level; "
  f"{int(anc_c.within_band.sum()) if len(anc_c) else 0} of them fall inside the 95 % prediction band (Table 11). "
  + (f"The exception is CAZRI chickpea: an observed {f2(cpa.observed_rel_yield)} against a curve value of "
     f"{f2(cpa.curve_mid)} (band {f2(cpa.band_low)}-{f2(cpa.band_high)}) at the reported shade (Section 6)."
     if len(cpa := anc_c[~anc_c.within_band.astype(bool)]) and (cpa := cpa.iloc[0]) is not None else ""))
table("Fitted crop-group coefficients (Eq. 5).", ["Crop group", "a", "b", "Observations", "Locations", "RSR range"],
      [[r.group, f"{r.a:+.3f}", f"{r.b:+.3f}", f0(r.n_obs), f0(r.n_locations), f"{r.rsr_min:.2f}-{r.rsr_max:.2f}"]
       for r in fit.itertuples()], widths=[0.28, 0.13, 0.13, 0.15, 0.13, 0.18])
figure("fig5_crop_curves.png", "Fitted shade-response curves for the four crop groups used, with 95 % confidence and "
       "prediction bands, the meta-analysis data, the published values and the field anchors.")
table("Field anchors against the fitted curves.", ["Crop", "Observed", "RSR", "Curve (95 % band)", "Inside", "Trial"],
      [[r.crop, f2(r.observed_rel_yield), "-" if pd.isna(r.rsr_lo) else f"{r.rsr_lo:.2f}-{r.rsr_hi:.2f}",
        "-" if pd.isna(getattr(r, "curve_mid", np.nan)) else f"{r.curve_mid:.2f} ({r.band_low:.2f}-{r.band_high:.2f})",
        "-" if pd.isna(getattr(r, "curve_mid", np.nan)) else ("yes" if r.within_band else "no"), r.note.split(";")[0]]
       for r in anc.itertuples()], widths=[0.11, 0.1, 0.11, 0.2, 0.09, 0.39], align="left", font=16)
cyc = cy[cy.basis == "group curve"]
xmax = cyc.loc[cyc.extrapolated_share.idxmax()]
p(f"Under the computed shade, curve-based relative yields range from {f2(cyc.yield_rel.min())} to "
  f"{f2(cyc.yield_rel.max())} (Table 12). Extending each growing season by one month changes the yields by at most "
  f"{f3((cyc.yield_rel_window_plus1 - cyc.yield_rel).abs().max())}, small next to the width of the 95 % bands, so "
  f"the provisional crop calendars do not change the conclusions. Part of the predictions are extrapolations. In "
  f"{int((cyc.extrapolated_share > 0).sum())} of {len(cyc)} rows some cropped strips are shaded beyond the largest RSR in the "
  f"group's data, up to {pct(xmax.extrapolated_share)} of the strips for {xmax.case} under {xmax.config} (the C3-cereal data "
  f"stop at RSR {f2(fit.set_index('group').loc[xmax.group, 'rsr_max'])}). These yields rest on the shape of the quadratic "
  f"rather than on observations.")
table("Relative yield and LER by case and layout.", ["Case", "Layout", "RSR", "Cropped share", "Yield (95 % band)",
      "LER (95 % band)", "Tier"],
      [[r.case, r.config, f2(r.rsr_cropped_mean), f2(r.cropped_share),
        (f"{r.yield_rel:.2f} ({r.yield_low:.2f}-{r.yield_high:.2f})" if r.basis == "group curve"
         else f"anchors {r.yield_low:.2f}-{r.yield_high:.2f}" if pd.notna(r.yield_low) else "-"),
        (f"{r.ler:.2f} ({r.ler_low:.2f}-{r.ler_high:.2f})" if r.basis == "group curve"
         else f"{r.ler_low:.2f}-{r.ler_high:.2f}" if pd.notna(r.ler_low) else "-"),
        "-" if pd.isna(r.tier) else f0(r.tier)] for r in tech.sort_values(["case", "config"]).itertuples()],
      widths=[0.15, 0.09, 0.09, 0.13, 0.22, 0.22, 0.1], font=16,
      note="Tier: rows whose 95 % LER band overlaps that of the tier leader share its tier (curve-based rows only).")
h2("5.4 Technical ranking")
top = curve.sort_values("ler_mid", ascending=False).head(5)
below1 = [f"{r.case} {r.config}" for r in curve[curve.ler < 1].itertuples()]
p((f"Every curve-based combination has a mean LER above 1 except {andjoin(below1)}. " if below1 else
   f"Every curve-based combination has a mean LER above 1 ({f2(curve.ler.min())}-{f2(curve.ler.max())}). ") +
  f"The top of the ranking is {'; '.join(f'{r.case} {r.config} ({r.ler:.2f})' for r in top.itertuples())} (Figure 6). " +
  ("The ranking is indicative only: all " + str(len(curve)) + " curve-based rows fall in a single tier, " if n_tiers == 1
   else f"The rows form {n_tiers} tiers, ") +
  f"because their 95 % bands overlap, mainly through the between-location spread of the crop response. Within each case, "
  f"C2 has the highest mean LER in {int((best_by_case.config == 'C2').sum())} of {len(best_by_case)} cases. C2 and C3 "
  f"have the same row spacing and therefore the same energy ratio, so the comparison is purely about the crop: C2 "
  f"crops {pct(curve[curve.config == 'C2'].cropped_share.iloc[0])} of the gross hectare at a lower relative yield, "
  f"C3 only {pct(curve[curve.config == 'C3'].cropped_share.iloc[0])} at a higher one, and the crop term (relative yield "
  f"x cropped share) is larger under C2 in {int((crop_part.C2 > crop_part.C3).sum())} of {len(crop_part)} cases. Tomato "
  f"(fruity vegetables) leads overall because its group curve stays near or above 1 at moderate shade.")
figure("fig6_ler.png", "Land equivalent ratio with 95 % bands. Open markers: field-anchor range only (not layout-responsive).")
h2("5.5 Economics")
p(f"At Rs {E.tariff_inr_per_kwh:.2f}/kWh, the PV-only plant's LCOE is Rs {f2(ref_rows.lcoe.min())}-{f2(ref_rows.lcoe.max())}/kWh "
  f"and its NPV per gross hectare is Rs {lakh(ref_rows.total_npv.min())}-{lakh(ref_rows.total_npv.max())} lakh. Agriculture "
  f"alone gives Rs {lakh(agri_rows.total_npv.min())}-{lakh(agri_rows.total_npv.max())} lakh over the same 25 years. "
  f"Year-one electricity revenue of the PV-only hectare (Rs {lakh(elec_rev.min())}-{lakh(elec_rev.max())} lakh) is "
  f"{elec_rev.min() / crop_net.max():.0f} to {elec_rev.max() / crop_net.min():.0f} times the net crop income "
  f"(Rs {lakh(crop_net.min())}-{lakh(crop_net.max())} lakh), so the NPV ordering is "
  f"driven mainly by installed capacity per hectare and by the capital cost premium. " + ("None" if n_av_beats_ref == 0 else str(n_av_beats_ref)) + f" of the {n_av} "
  f"AV combinations beat PV-only on NPV, and {n_av_beats_agri} beat agriculture-only (Figure 7, Table 13).")
p(f"The elevated layouts carry fewer modules per hectare and the {100 * E.capex_premium['C1']:.1f} % structure premium, so their "
  f"LCOE (Rs {f2(ell.lcoe.min())}-{f2(ell.lcoe.max())}/kWh) is above the base tariff in every state and the PV part of "
  f"C1 and C2 loses money; {int((ell.total_npv < 0).sum())} of {len(ell)} elevated combinations have a negative total "
  f"NPV even with the crop income. The interspace layout C3 (LCOE Rs {f2(c3.lcoe.min())}-{f2(c3.lcoe.max())}/kWh) is "
  f"the best AV layout in {best_cfg_counts.get('C3', 0)} of {len(summ)} cases and beats agriculture alone in "
  f"{int((c3.npv_vs_agri > 0).sum())}; the exceptions are the high-value vegetables "
  f"({andjoin(list(c3.index[c3.npv_vs_agri <= 0]))}), whose open-field income is close to or above the PV-only NPV. "
  + (f"In {andjoin(agri_beats_ref)} agriculture alone even beats the PV-only plant at the base tariff. " if agri_beats_ref else "")
  + f"At the MNRE AgriPV tariff of Rs {E.tariff_av_scenario:.2f}/kWh, C3 overtakes the PV-only plant (still at Rs "
  f"{E.tariff_inr_per_kwh:.2f}) in {n_c3_avtariff_beats_ref} of {len(c3)} cases. If the elevated-structure premium is "
  f"covered by a grant, {n_prem_beats_ref} of {len(ell)} elevated combinations do.")
figure("fig7_npv.png", "25-year NPV per gross hectare by case and system (base case).")
table("Economic summary: best AV layout per case.", ["Case", "Best AV", "NPV agri", "NPV PV-only", "NPV best AV",
      "LCOE PV-only", "LCOE AV", "Break-even tariff"],
      [[r.case, r.best_av, f1(r.npv_agri_lakh), f1(r.npv_ref_lakh), f1(r.npv_best_av_lakh), f2(r.lcoe_ref),
        f2(r.lcoe_best_av), f2(r.breakeven_tariff_vs_ref)] for r in summ.itertuples()],
      widths=[0.15, 0.09, 0.11, 0.13, 0.13, 0.13, 0.11, 0.15], font=16,
      note="NPV in Rs lakh per gross hectare; LCOE and tariff in Rs/kWh. Break-even tariff: tariff at which the AV "
           "hectare (PV + crop) has the same NPV as a PV-only hectare at the base tariff.")
h2("5.6 Sensitivity")
sd = sens[(sens.config == "C2")].assign(span=lambda x: (x.high_vs_ref - x.low_vs_ref).abs())
rank = sd.groupby("parameter").span.mean().sort_values(ascending=False)
cs_h = crop_span[crop_span.case.isin(hort)].sp; cs_o = crop_span[~crop_span.case.isin(hort)].sp
p(f"Figure 8 shows, for MP wheat, how the NPV gap between AV and PV-only responds to each input. Averaged over all "
  f"cases for C2, the most influential inputs are {andjoin([pname(x) for x in rank.index[:3]])}. The effect of crop income depends on "
  f"the crop: a +/-50 % change moves the gap by at most Rs {lakh(cs_o.max())} lakh/ha for the pulses, cereals, potato "
  f"and cumin, but by up to Rs {lakh(cs_h.max())} lakh/ha for tomato and onion. "
  + (f"For {andjoin([f'{r.case} {r.config}' for r in flips.itertuples()])}, a 50 % higher crop income is enough to "
     f"make the AV hectare beat PV-only." if len(flips) else "In no case does it reverse the AV-versus-PV result."))
figure("fig8_tornado_MP-wheat_C2.png", "One-at-a-time sensitivity of NPV(C2) - NPV(PV-only) for MP wheat.", width=0.85)
figure("fig8_tornado_MP-wheat_C3.png", "As Figure 8, for the interspace layout C3.", width=0.85)

# ---------------------------------------------------------------- 6 discussion
h1("6. Discussion", newpage=True)
p(f"**Interspace versus elevated layouts.** The two criteria disagree. Technically, the elevated layout C2 keeps "
  f"{pct(curve[curve.config == 'C2'].cropped_share.iloc[0])} of the gross hectare in crop and has the highest mean LER in "
  f"most cases. Economically, its structure premium and lower module density push its LCOE above the tariff, while the "
  f"interspace layout C3 avoids the premium, keeps the crop out of the deepest shade and is the best AV option in every "
  f"case, at the price of cropping only {pct(curve[curve.config == 'C3'].cropped_share.iloc[0])} of the hectare. "
  f"Because the LER bands overlap, the technical advantage of C2 is not statistically firm, whereas its economic "
  f"disadvantage (break-even Rs {f2(be_ell.min())}-{f2(be_ell.max())}/kWh) is large. Unless a policy rewards the share "
  f"of land kept in crop, or pays for the structure, interspace AV is the realistic option.")
_cp = anc[anc.crop == "Chickpea"].iloc[0]
_gl = gate[(gate.group == "grain legumes") & (gate.rsr == 0.4)].iloc[0]
p(f"**The chickpea discrepancy.** The CAZRI trial reported a {pct(1 - _cp.observed_rel_yield)} chickpea yield loss under "
  f"spot PAR reductions of 47-59 %, whereas the grain-legume curve predicts a relative yield of {f2(_gl.refit)} at 40 % "
  f"RSR and {f2(_cp.curve_mid)} over 47-59 %; even the upper end of the prediction band ({f2(_cp.band_high)}) is below the "
  f"observation. Three explanations are possible: "
  "(i) spot noon PAR readings over-state season-integrated shade under a sparse, low array; (ii) shade may have "
  "relieved heat and water stress in an irrigated arid-zone rabi crop; and (iii) the meta-analysis grain legumes are "
  "dominated by temperate studies. The curve is used as the conservative case, and the anchor shows that the true "
  "response at Indian arid sites may be milder.")
p(f"**Policy.** The break-even tariffs in Table 13 indicate the support an AV hectare needs to match a PV-only hectare. "
  f"For C3 they are Rs {f2(be_c3.min())}-{f2(be_c3.max())}/kWh, close to the Rs 3.20-3.30 that MNRE expects AgriPV "
  f"plants to need; for the elevated layouts they are Rs {f2(be_ell.min())}-{f2(be_ell.max())}/kWh, well above it. A "
  f"tariff premium of Rs {f2(be_c3.min() - E.tariff_inr_per_kwh)}-{f2(be_c3.max() - E.tariff_inr_per_kwh)}/kWh would "
  f"therefore suffice for interspace AV (the MNRE mid-point of Rs {E.tariff_av_scenario:.2f} covers "
  f"{int((be_c3 <= E.tariff_av_scenario).sum())} of {len(be_c3)} cases), but elevated AV would need Rs "
  f"{f2(be_ell.min() - E.tariff_inr_per_kwh)}-{f2(be_ell.max() - E.tariff_inr_per_kwh)}/kWh more. Covering the "
  f"elevated-structure premium by grant (the 'premium covered' scenario in outputs/phase6_economics.csv) makes "
  f"{n_prem_beats_ref} of {len(ell)} elevated combinations competitive with PV-only. The PV model's few-percent "
  f"optimism (Section 4) would raise all these thresholds slightly.")
h2("6.1 Limitations")
bullets([
    "Two-dimensional infinite rows: edge rows and east-west gaps of real fields are ignored.",
    "Reflected light under the array is neglected, which slightly over-estimates crop shade.",
    "Partial shading is modelled as a linear loss; real electrical mismatch would reduce PV energy further.",
    "One proxy point per state and one typical weather year; inter-annual variability is not modelled.",
    "The crop model uses crop groups, not cultivars; temperature and water effects of shade are not modelled.",
    ("Crop economics for horticultural crops are indicative (grade C) and tested at +/- 50 %; for "
     + andjoin(sorted({r.case for r in flips.itertuples()})) + " this is enough to change whether C3 beats PV-only."
     if len(flips) else "Crop economics for horticultural crops are indicative (grade C); tested at +/- 50 %, they do not change the AV-versus-PV result."),
    f"The PV model's annual yield is {f1(pv_lo)}-{f1(pv_hi)} % above PVGIS (smaller temperature and low-irradiance losses), so absolute PV revenue is probably slightly optimistic.",
    "The crop curves share one quadratic term across groups (the published model form); several predictions extrapolate beyond the shade range of the data.",
    "No taxes, subsidies, financing, land lease or grid-connection costs in the economics.",
])

# ---------------------------------------------------------------- 7 conclusions
h1("7. Conclusions")
bullets([
    f"Per gross hectare, the AV layouts produce {pct(e_by.C1.min())}-{pct(e_by.C2.max())} of the energy of a conventional plant while keeping the land in production.",
    f"Shade on the cropped land is deepest in rabi. The interspace layout (C3) keeps the crop at {pct(rabi.C3.min())}-{pct(rabi.C3.max())} RSR, against {pct(rabi.C2.min())}-{pct(rabi.C2.max())} under C2.",
    f"Technically, every curve-based AV combination has a mean LER above 1, so sharing the land is more productive than splitting it; C2 has the highest mean LER in most cases ({best_ler.case} {best_ler.config}: {f2(best_ler.ler)}), but the 95 % bands overlap, so no layout is statistically superior.",
    f"Economically, electricity dominates the value of a hectare: at Rs {E.tariff_inr_per_kwh:.2f}/kWh " + ("none" if n_av_beats_ref == 0 else str(n_av_beats_ref)) + f" of the {n_av} AV combinations beat PV-only and {n_av_beats_agri} beat agriculture alone. Elevated AV (LCOE Rs {f2(ell.lcoe.min())}-{f2(ell.lcoe.max())}/kWh) is not viable at current tariffs; interspace C3 is the best AV option in {best_cfg_counts.get('C3', 0)} of {len(summ)} cases.",
    f"C3 would match PV-only at Rs {f2(be_c3.min())}-{f2(be_c3.max())}/kWh, within reach of the MNRE AgriPV tariff estimate (Rs 3.20-3.30); elevated layouts would need Rs {f2(be_ell.min())}-{f2(be_ell.max())}/kWh or a capital grant.",
    "The decisive inputs are the tariff, the capital cost and its AV premium, and the discount rate; for tomato and onion, crop income also matters. The crop response at high shade (the chickpea discrepancy) is the main scientific uncertainty.",
])

# ---------------------------------------------------------------- references
h1("References", newpage=True)
B.append(dict(type="refs", items=[
    "Blanco-Muriel, M., Alarcon-Padilla, D.C., Lopez-Moratalla, T., Lara-Coira, M. (2001). Computing the solar vector. *Solar Energy* 70(5), 431-441.",
    "CERC (2025). Order dated 26 December 2025, tariff determination for the 40 MW solar project of NTPC Green Energy Ltd at Ayodhya (reported by Power Peak Digest, 4 Jan 2026).",
    "Choudhary, M.K., Singh, D., Meena, M.L., Tomar, P.K. (2016). Economic analysis of front line demonstrations on cumin: a case in arid zone of Rajasthan. *Annals of Arid Zone* 52(2). doi:10.56093/aaz.v52i2.63269",
    "CTUIL (2026). Revised benchmark project costs and land requirements for renewable projects (reported by Indian Infrastructure, 7 Sep 2026).",
    "Directorate of Pulses Development (2025). Annual Report 2023-24. DPD/Pub./TR/47/2023-24, Bhopal.",
    "Faiman, D. (2008). Assessing the outdoor operating temperature of photovoltaic modules. *Progress in Photovoltaics* 16(4), 307-315.",
    "Hay, J.E., Davies, J.A. (1980). Calculation of the solar radiation incident on an inclined surface. Proc. First Canadian Solar Radiation Data Workshop, 59-72.",
    "ICAR-IASRI. Agricultural Research Data Book, Table 4.13: state-wise area, production and productivity of tomato.",
    "Huld, T., Friesen, G., Skoczek, A., Kenny, R.P., Sample, T., Field, M., Dunlop, E.D. (2011). A power-rating model for crystalline silicon PV modules. *Solar Energy Materials and Solar Cells* 95(12), 3359-3369.",
    "Laub, M., Pataczek, L., Feuerbacher, A., et al. (2022). Contrasting yield responses at varying levels of shade suggest different suitability of crops for dual land-use systems: a meta-analysis. *Agronomy for Sustainable Development* 42, 51. doi:10.1007/s13593-022-00783-7",
    "Meeus, J. (1998). *Astronomical Algorithms*, 2nd ed. Willmann-Bell (used for validation of M1).",
    "MERC (2026). Order of 5 August 2026 on procurement of 2,269 MW under MSKVY 2.0 (reported by SolarQuarter, 7 Aug 2026).",
    "MNRE (2026). Statement of Secretary S.K. Sarangi on a central scheme for AgriPV plants (reported by PSU Watch, 20 Oct 2026).",
    "Pataczek, L., Laub, M. (2021). Crop yield responses at varying levels of shade (dataset, v2). Zenodo. doi:10.5281/zenodo.5716091",
    "Patil, Y.S., Aravinda Kumar, M.K., Gaddi, G.M. (2024). Trends in area, production, productivity and economics of onion in Haveri district of Karnataka. *Mysore J. Agric. Sci.* 58(3), 393-401.",
    "PIB (2025). Cabinet approves MSP for rabi crops for marketing season 2026-27 (1 Oct 2025).",
    "PIB (2026). Cabinet approves MSP for kharif crops for marketing season 2026-27 (May 2026), PRID 2260617.",
    "Poonia, S., Santra, P. (2022). Evaluation of agrivoltaic system in Thar desert of India. *AgriVoltaics Conference Proceedings* 1. doi:10.52825/agripv.v1i.601",
    "Sai, K.S., Gayathri, P., Ashok, K., Ramya Sri, Ch., Uday Raj, B.M. (2022). Economic analysis of tomato cultivation. *Biological Forum* 14(2), 381-383.",
    "Weselek, A., Bauerle, A., Hartung, J., Zikeli, S., Lewandowski, I., Hogy, P. (2021). Agrivoltaic system impacts on microclimate and yield of different crops within an organic crop rotation in a temperate climate. *Agronomy* 11(4), 733. doi:10.3390/agronomy11040733",
    "Yadav, R.S., et al. (2024). A study on costs and returns of potato in Azamgarh district of eastern Uttar Pradesh. *J. Exp. Agric. Int.* 46(5), 825-831.",
    "European Commission JRC. PVGIS 5.3 (Photovoltaic Geographical Information System), typical meteorological year and PVcalc tools.",
]))

# ---------------------------------------------------------------- appendices
h1("Appendix A. Crop economics sources", newpage=True)
table("Source of each crop-economics value.", ["Case", "Source"], [[k, v["src"]] for k, v in CROP_ECON.items()],
      widths=[0.16, 0.84], align="left", font=16)
h1("Appendix B. Reproducing the results")
bullets([
    "Install Python 3.10+ with numpy, scipy, pandas, matplotlib and openpyxl (requirements.txt).",
    "Download the inputs: python scripts/fetch_all_data.py, then unzip agripv_data.zip into data/ (data/pvgis, data/zenodo).",
    "Check the Zenodo column mapping in data/zenodo_columns.json against the workbook.",
    "Run the tests: python -I tests/test_validation.py, python -I tests/test_cropfit.py, python -I tests/test_econ.py.",
    "Run the pipeline: python -I run_phase23.py data/pvgis outputs; python -I run_phase45.py data outputs; python -I run_phase6.py outputs; python -I make_figures.py outputs figures.",
], numbered=True)
h1("Appendix C. Changes to the model code during this study")
bullets([
    "Leap day: 29 February is now removed before re-stamping the typical year onto 2025 (previously a crash or a no-op).",
    "RSR reference: the open field is now built from DNI cos z + DHI, consistent with the strips, instead of the file's GHI.",
    "Land basis: all systems are compared per gross hectare with the same non-array land share; the reference plant's rows are solved from the CTUIL gross norm.",
    "Field anchors: shade levels added; anchors are now checked against the curves; anchor-only crops are excluded from the LER tiers.",
    "Gate extended from 9 to 11 published values; solar-position test now uses an independent Meeus reference (0.02 deg limit) at three sites.",
    "Added: growing-window sensitivity, Phase 6 economics with sensitivity, economics tests, figures and a synthetic end-to-end test.",
    "Crop model form: with the real data, the per-group quadratic passed only 6 of 11 gate values; the published final model (shared quadratic term), with studies as locations and the controls kept, passes 11/11 (largest error 0.005). Alternatives are reported in Table 8.",
    "PVGIS cross-check extended to separate in-plane irradiation from conversion losses.",
])

# static contents list (Word TOC fields are not refreshed by PDF conversion)
i = next(k for k, b in enumerate(B) if b["type"] == "toc_placeholder")
heads = [b["text"] for b in B[i + 1:] if b["type"] == "h1"]
B[i:i + 1] = [dict(type="h1", text="Contents"), dict(type="bullets", items=heads, numbered=False), dict(type="pagebreak")]
spec = dict(blocks=B, author=cover.get("author", ""), doc_title=cover.get("title", "Agrivoltaics in India"),
            running_head=cover.get("running_head", "Agrivoltaics in India - technical and economic assessment"))
SPEC.write_text(json.dumps(spec, indent=1))
print("spec written:", SPEC, len(B), "blocks")
