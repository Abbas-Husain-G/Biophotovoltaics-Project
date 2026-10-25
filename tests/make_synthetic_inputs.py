"""SYNTHETIC inputs for an end-to-end PLUMBING test of the pipeline. NOT real data - never report these numbers.

Writes PVGIS-format TMY / PVcalc JSON for the six sites and a Zenodo-format workbook + column map, so that
run_phase23 -> run_phase45 -> run_phase6 can be exercised before the real downloads are available.
The TMY deliberately includes 29 February (a leap-year February) to exercise the leap-day handling.
Usage: python -I tests/make_synthetic_inputs.py <data_dir>
"""
import json, pathlib, sys
import numpy as np
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agripv.config import SITES
from agripv.solarpos import solar_position, extraterrestrial_dni

out = pathlib.Path(sys.argv[1]); (out / "pvgis").mkdir(parents=True, exist_ok=True); (out / "zenodo").mkdir(exist_ok=True)
rng = np.random.default_rng(1)
years = [2016, 2009, 2012, 2018, 2011, 2007, 2015, 2019, 2010, 2014, 2017, 2013]   # Feb from 2016 -> has 29 Feb

for state, (_, lat, lon, _) in SITES.items():
    rows = []
    for m, yr in enumerate(years, start=1):
        t = pd.date_range(f"{yr}-{m:02d}-01", periods=pd.Period(f"{yr}-{m:02d}").days_in_month * 24, freq="h", tz="UTC")
        zen, el, _ = solar_position(t, lat, lon)
        cz = np.clip(np.cos(np.radians(zen)), 0, None)
        clear = 1098 * cz * np.exp(-0.057 / np.maximum(cz, 0.05))                 # Haurwitz clear-sky GHI
        kc = np.clip(rng.normal(0.75 if m not in (7, 8) else 0.45, 0.2, len(t)), 0.1, 1.0)
        ghi = np.where(el > 0, clear * kc, 0.0)
        kt = np.where(el > 0, ghi / np.maximum(extraterrestrial_dni(t) * cz, 1), 0)
        fd = np.where(kt <= 0.22, 1 - 0.09 * kt, np.where(kt <= 0.8,
             0.9511 - 0.1604 * kt + 4.388 * kt**2 - 16.638 * kt**3 + 12.336 * kt**4, 0.165))   # Erbs
        dhi = ghi * fd
        dni = np.where(cz > 0.05, (ghi - dhi) / np.maximum(cz, 0.05), 0.0)
        for i, ts in enumerate(t):
            rows.append({"time(UTC)": ts.strftime("%Y%m%d:%H%M"), "T2m": 25 + 8 * np.sin(2 * np.pi * (ts.hour - 9) / 24),
                         "G(h)": float(ghi[i]), "Gb(n)": float(dni[i]), "Gd(h)": float(dhi[i]), "WS10m": 2.5})
    js = {"inputs": {"meteo_data": {"radiation_db": "SYNTHETIC"}},
          "outputs": {"months_selected": [{"month": m, "year": y} for m, y in enumerate(years, 1)], "tmy_hourly": rows}}
    name = state.replace(" ", "_")
    (out / "pvgis" / f"tmy_{name}.json").write_text(json.dumps(js))
    for a in (10, 15, 20, 25, 30, "opt"):
        ang = 22 if a == "opt" else a
        pj = {"inputs": {"mounting_system": {"fixed": {"slope": {"value": ang}}}},
              "outputs": {"totals": {"fixed": {"E_y": 1600.0}}}}
        (out / "pvgis" / f"pvcalc_{a}_{name}.json").write_text(json.dumps(pj))

# Zenodo-format workbook: groups with Laub-like curves, random location slopes
truth = {"grain legumes": (-0.30, -1.0), "fruity vegetables": (0.35, -0.85), "C3 cereals": (-0.15, -0.9),
         "tubers/root crops": (-0.2, -0.8), "berries": (0.70, -1.10), "fruits": (0.70, -1.1),
         "forages": (0.15, -0.55), "leafy vegetables": (-0.2, -0.45), "maize": (-0.5, -1.9)}
recs = []
for loc in range(40):
    u = rng.multivariate_normal([0, 0], [[0.02, -0.005], [-0.005, 0.02]])
    for g, (a, b) in truth.items():
        if rng.random() < 0.5:
            recs.append(dict(Location=f"L{loc}", CropType=g, RSR_pct=0.0, RelYield_pct=100.0))
            for r in rng.uniform(0.05, 0.7, 3):
                y = (a + u[0]) * r + (b + u[1]) * r**2 + rng.normal(0, 0.03)
                recs.append(dict(Location=f"L{loc}", CropType=g, RSR_pct=100 * r, RelYield_pct=100 * 10**y))
pd.DataFrame(recs).to_excel(out / "zenodo" / "SYNTHETIC.xlsx", sheet_name="data", index=False)
(out / "zenodo_columns.json").write_text(json.dumps({
    "file": "SYNTHETIC.xlsx", "sheet": "data", "rsr": "RSR_pct", "rsr_units": "percent", "yield": "RelYield_pct",
    "yield_units": "percent", "group": "CropType", "location": "Location", "group_names": {g: g for g in truth}}, indent=1))
print("synthetic inputs written to", out)
