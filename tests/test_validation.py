"""Weather-independent validation of M1-M3 (Phase 2/3 gates). Run: python -I tests/test_validation.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from agripv.solarpos import solar_position
from agripv.geometry import (Layout, sun_t, strip_centres, ground_shade, ground_shade_raycast,
                             ground_sky_view, ground_sky_view_crossed_strings,
                             module_beam_shaded_fraction, module_beam_shaded_fraction_raycast,
                             module_sky_view)
from agripv.pv import PVParams, poa_interior_row, kwp_per_ha
from agripv.config import build_layouts

results = []
def check(name, value, limit, unit=""):
    ok = value <= limit
    results.append((name, value, limit, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {value:.6g} (limit {limit:g}{unit})")

rng = np.random.default_rng(42)
LAYS = [Layout.from_gcr("g20", 22, 2.28, 0.20, 3.0), Layout.from_gcr("g30", 22, 2.28, 0.30, 3.0),
        Layout.from_gcr("g30low", 25, 2.28, 0.30, 0.5), Layout.from_gcr("g45", 30, 2.0, 0.45, 1.0)]

# T1 solar position ----------------------------------------------------------
def noaa(times, lat, lon):
    tu = times.tz_convert("UTC"); day = tu.dayofyear.to_numpy(); hr = tu.hour.to_numpy() + tu.minute.to_numpy() / 60
    g = 2 * np.pi / 365 * (day - 1 + (hr - 12) / 24)
    eq = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    d = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g) + 0.000907 * np.sin(2 * g)
         - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    ha = np.radians((hr * 60 + eq + 4 * lon) / 4 - 180); la = np.radians(lat)
    return np.degrees(np.arcsin(np.clip(np.sin(la) * np.sin(d) + np.cos(la) * np.cos(d) * np.cos(ha), -1, 1)))

t = pd.date_range("2025-01-01", "2026-01-01", freq="20min", inclusive="left", tz="UTC")
_, el, az = solar_position(t, 26.26, 73.02)
up = el > 5
check("T1a PSA vs NOAA elevation, Jodhpur 2025, max |diff|", np.abs(el - noaa(t, 26.26, 73.02))[up].max(), 0.6, " deg")
t_noon = pd.date_range("2025-12-21 06:00", "2025-12-21 08:00", freq="1min", tz="UTC")
_, el_n, _ = solar_position(t_noon, 26.26, 73.02)
check("T1b winter-solstice max elevation vs 90-lat-23.44, |diff|", abs(el_n.max() - (90 - 26.26 - 23.44)), 0.05, " deg")

# T2 ground shading closed form vs brute-force ray cast ------------------------
tt = np.concatenate([rng.uniform(-3, 3, 400), np.tan(np.radians(rng.uniform(-80, 80, 200)))])
worst = 0
for lay in LAYS:
    y = strip_centres(lay, 97)
    worst = max(worst, np.abs(ground_shade(lay, y, tt) - ground_shade_raycast(lay, y, tt)).mean())
check("T2 ground beam shadow: closed form vs ray cast, mean |diff| (boundary strips only)", worst, 0.005)

# T3 field-mean shaded fraction vs analytic min(w/p, 1) -----------------------
worst = 0
for lay in LAYS:
    y = strip_centres(lay, 4000)
    w = np.abs(lay.footprint_m - lay.slant_m * np.sin(lay.beta) * tt)
    worst = max(worst, np.abs(ground_shade(lay, y, tt).mean(axis=1) - np.minimum(w / lay.pitch_m, 1)).max())
check("T3 field-mean shaded fraction vs analytic min(w/p,1), max |diff|", worst, 0.001)

# T4 sky view factor: angular sampling vs crossed-strings analytic -----------
worst = 0
for lay in LAYS:
    y = strip_centres(lay, 12)
    worst = max(worst, np.abs(ground_sky_view(lay, y) - ground_sky_view_crossed_strings(lay, y)).max())
check("T4 ground sky view factor: sampling vs crossed strings, max |diff|", worst, 0.002)

# T5 module front-row shading: analytic formula vs ray cast ------------------
els, azs = rng.uniform(3, 89, 300), rng.uniform(95, 265, 300)
worst = 0
for lay in LAYS:
    worst = max(worst, np.abs(module_beam_shaded_fraction(lay, els, azs) - module_beam_shaded_fraction_raycast(lay, els, azs)).max())
check("T5 module shaded fraction: formula vs ray cast, max |diff|", worst, 0.002)

# T6 module sky view tends to (1+cos b)/2 for an isolated row -----------------
iso = Layout("iso", 25, 2.28, 1e6, 1.0)
check("T6 module sky view, isolated row vs (1+cos b)/2, |diff|", abs(module_sky_view(iso) - (1 + np.cos(iso.beta)) / 2), 1e-4)

# T7 beam energy closure: ground + modules = beam crossing the array top ----------
worst = 0
for lay in LAYS:
    y = strip_centres(lay, 4000)
    zen = 90 - els; tsun = sun_t(els, azs)
    lit = 1 - ground_shade(lay, y, tsun).mean(axis=1)
    b = lay.beta; z, a = np.radians(zen), np.radians(azs)
    cos_aoi = np.cos(z) * np.cos(b) + np.sin(z) * np.sin(b) * np.cos(a - np.pi)
    front = cos_aoi > 0
    f = module_beam_shaded_fraction(lay, els, azs)
    panel = lay.slant_m * cos_aoi * (1 - f)
    total = lay.pitch_m * np.cos(z)
    err = np.abs(lit * lay.pitch_m * np.cos(z) + panel - total)[front] / total[front]
    worst = max(worst, err.max())
check("T7 beam energy closure (sun in front of modules), max relative error", worst, 0.002)

# T8 transposition limit: horizontal, unshaded, no IAM -> POA = GHI -------------
prm = PVParams(iam_b0=0.0, albedo=0.2)
flat = Layout("flat", 0.0, 2.28, 1e6, 1.0)
zen = rng.uniform(0, 85, 200); dni = rng.uniform(0, 900, 200); dhi = rng.uniform(20, 300, 200)
ghi = dni * np.cos(np.radians(zen)) + dhi
sc = dict(zen=zen, elev=90 - zen, az=rng.uniform(0, 360, 200), up=np.ones(200, bool), dni=dni, dhi=dhi, ghi=ghi,
          ai=np.clip(dni / 1367, 0, 1))
poa, _ = poa_interior_row(flat, sc, prm, shading=False)
check("T8 horizontal POA equals GHI, max |diff|", np.abs(poa - ghi).max(), 1e-6, " W/m2")

# T9 reference plant density matches CTUIL 3 acres/MW ---------------------------
lay = build_layouts(25)["REF"]
check("T9 reference plant kWp/ha vs 823.7 (CTUIL), |diff|", abs(kwp_per_ha(lay, PVParams()) - 823.7), 0.5, " kWp/ha")

n_fail = sum(not r[3] for r in results)
print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
pd.DataFrame(results, columns=["check", "value", "limit", "pass"]).to_csv(
    pathlib.Path(__file__).resolve().parents[1] / "outputs" / "validation_checks.csv", index=False)
sys.exit(1 if n_fail else 0)
