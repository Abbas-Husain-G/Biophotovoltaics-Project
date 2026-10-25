"""Phases 2-3 runner: ground light under each layout (M2) and PV energy per hectare (M3, M6).

Inputs : data/pvgis/tmy_<State>.json (PVGIS 5.3 TMY), data/pvgis/pvcalc_*_<State>.json
Outputs: outputs/phase2_*.csv, outputs/phase3_*.csv, outputs/phase23_log.txt
Run    : python -I run_phase23.py
"""
import json, pathlib, sys
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from agripv.config import SITES, build_layouts
from agripv.geometry import cropped_mask
from agripv.pv import PVParams, sun_and_components, ground_irradiance, pv_energy, kwp_per_ha
from agripv.solarpos import solar_position

DATA = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "pvgis"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
SEASONS = {"kharif (Jun-Oct)": [6, 7, 8, 9, 10], "rabi (Nov-Mar)": [11, 12, 1, 2, 3], "annual": list(range(1, 13))}
N_STRIPS = 40
log_lines = []
def log(*a):
    s = " ".join(str(x) for x in a); print(s); log_lines.append(s)


def load_tmy(state):
    js = json.loads((DATA / f"tmy_{state.replace(' ', '_')}.json").read_text())
    rows = js["outputs"]["tmy_hourly"]
    df = pd.DataFrame(rows)
    raw_t = pd.to_datetime(df["time(UTC)"], format="%Y%m%d:%H%M", utc=True)
    # re-stamp every month onto a nominal non-leap year, keeping month/day/hour/minute
    nominal = pd.to_datetime(dict(year=2025, month=raw_t.dt.month, day=raw_t.dt.day,
                                  hour=raw_t.dt.hour, minute=raw_t.dt.minute), utc=True)
    w = pd.DataFrame({"ghi": df["G(h)"].values, "dni": df["Gb(n)"].values, "dhi": df["Gd(h)"].values,
                      "temp_air": df["T2m"].values, "wind": df["WS10m"].values}, index=pd.DatetimeIndex(nominal))
    w = w[~((w.index.month == 2) & (w.index.day == 29))].sort_index()
    meta = js.get("inputs", {}).get("meteo_data", {})
    months = js.get("outputs", {}).get("months_selected", [])
    return w, meta, months


def choose_time_offset(w, lat, lon):
    """PVGIS hourly stamps: pick the offset (min) at which GHI = DNI cos z + DHI closes best (diagnostic)."""
    best = None
    for off in (0, 10, 30, -30):
        idx = w.index + pd.Timedelta(minutes=off)
        zen, el, _ = solar_position(idx, lat, lon)
        m = (el > 10) & (w["ghi"].to_numpy() > 50)
        resid = (w["dni"].to_numpy() * np.cos(np.radians(zen)) + w["dhi"].to_numpy() - w["ghi"].to_numpy())[m]
        score = np.sqrt(np.mean(resid ** 2))
        if best is None or score < best[1]:
            best = (off, score)
    return best


def optimal_tilt(w, lat, lon, prm):
    sc = sun_and_components(w, lat, lon)
    tilts = np.arange(0, 41, 1.0)
    e = [pv_energy(build_layouts(b)["REF"], w, sc, prm).sum() for b in tilts]
    return float(tilts[int(np.argmax(e))]), sc


def pvgis_value(state, tag):
    f = DATA / f"pvcalc_{tag}_{state.replace(' ', '_')}.json"
    if not f.exists():
        return None, None
    js = json.loads(f.read_text())
    ey = js["outputs"]["totals"]["fixed"]["E_y"]
    ang = js["inputs"]["mounting_system"]["fixed"]["slope"]["value"]
    return float(ey), float(ang)


def main():
    prm = PVParams()
    rsr_rows, strip_rows, energy_rows, check_rows = [], [], [], []
    for state, (district, lat, lon, _) in SITES.items():
        w, meta, months = load_tmy(state)
        off, rmse = choose_time_offset(w, lat, lon)
        w.index = w.index + pd.Timedelta(minutes=off)
        log(f"{state} ({district}): radiation db = {meta.get('radiation_db', '?')}, TMY months = "
            f"{[m.get('year') for m in months] if months else '?'}, time offset {off} min (closure RMSE {rmse:.1f} W/m2), "
            f"annual GHI {w['ghi'].sum() / 1000:.0f} kWh/m2, diffuse share {w['dhi'].sum() / w['ghi'].sum():.2f}")
        tilt, sc = optimal_tilt(w, lat, lon, prm)
        lays = build_layouts(tilt)
        e_ref = pv_energy(lays["REF"], w, sc, prm).sum()
        kwph_ref = kwp_per_ha(lays["REF"], prm)

        # PVGIS cross-check: our open-rack (unshaded) model vs PVcalc at the nearest fetched tilt
        tag = min((10, 15, 20, 25, 30), key=lambda a: abs(a - tilt))
        ours_open = pv_energy(build_layouts(float(tag))["REF"], w, sc, prm, shading=False).sum()
        ey, ang = pvgis_value(state, tag)
        ey_opt, ang_opt = pvgis_value(state, "opt")
        if ey:
            check_rows.append(dict(state=state, tilt_deg=tag, ours_kwh_per_kwp=round(ours_open, 1),
                                   pvgis_kwh_per_kwp=round(ey, 1), diff_pct=round(100 * (ours_open / ey - 1), 2),
                                   pvgis_optimal_tilt=ang_opt, our_optimal_tilt=tilt))

        for cname in ("C1", "C2", "C3", "REF"):
            lay = lays[cname]
            e = pv_energy(lay, w, sc, prm).sum()
            kwph = kwp_per_ha(lay, prm)
            energy_rows.append(dict(state=state, district=district, config=cname, tilt_deg=tilt, gcr=round(lay.gcr, 3),
                                    pitch_m=round(lay.pitch_m, 2), clearance_m=lay.clearance_m,
                                    kwp_per_ha=round(kwph, 1), kwh_per_kwp=round(e, 1),
                                    mwh_per_ha=round(e * kwph / 1000, 1),
                                    energy_ratio_vs_ref=round(e * kwph / (e_ref * kwph_ref), 3)))
            if cname == "REF":
                continue
            y, g, svf = ground_irradiance(lay, sc, N_STRIPS)
            crop = cropped_mask(lay, y)
            open_h = sc["ghi"]
            month = w.index.month
            for sname, ms in SEASONS.items():
                m = np.isin(month, ms)
                open_sum = open_h[m].sum()
                strip_sum = g[m].sum(axis=0)
                rsr_strip = 1 - strip_sum / open_sum
                rsr_rows.append(dict(state=state, config=cname, season=sname,
                                     rsr_field_mean=round(1 - strip_sum.mean() / open_sum, 4),
                                     rsr_cropped_mean=round(1 - strip_sum[crop].mean() / open_sum, 4),
                                     rsr_cropped_min=round(rsr_strip[crop].min(), 4),
                                     rsr_cropped_max=round(rsr_strip[crop].max(), 4),
                                     cropped_share_of_land=round(crop.mean(), 3)))
            for mo in range(1, 13):
                m = month == mo
                for yi, gi, ci in zip(y, g[m].sum(axis=0), crop):
                    strip_rows.append(dict(state=state, config=cname, month=mo, y_m=round(yi, 3), cropped=bool(ci),
                                           ground_kwh_m2=round(gi / 1000, 3), open_kwh_m2=round(open_h[m].sum() / 1000, 3)))

    pd.DataFrame(rsr_rows).to_csv(OUT / "phase2_rsr_seasonal.csv", index=False)
    pd.DataFrame(strip_rows).to_csv(OUT / "phase2_ground_strips_monthly.csv", index=False)
    pd.DataFrame(energy_rows).to_csv(OUT / "phase3_energy.csv", index=False)
    pd.DataFrame(check_rows).to_csv(OUT / "phase3_pvgis_check.csv", index=False)
    (OUT / "phase23_log.txt").write_text("\n".join(log_lines))
    log("written outputs")


if __name__ == "__main__":
    main()
