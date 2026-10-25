"""Report figures from the pipeline outputs. Usage: python -I make_figures.py [outputs_dir] [figures_dir]"""
import pathlib, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from agripv.config import build_layouts, SITES
from agripv.cases import ANCHORS, LAUB_PUBLISHED, CASES

OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "outputs"
FIG = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# Validated categorical palette (light), fixed order; series follow the entity, never rank
S = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
COL = {"C1": S[0], "C2": S[1], "C3": S[2], "REF": S[3], "PV-only (REF)": S[3], "Agri-only": S[4]}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "legend.frameon": False, "figure.dpi": 200, "savefig.bbox": "tight"})
STATE_ORDER = list(SITES)
ABBR = {"Rajasthan": "RJ", "Gujarat": "GJ", "Maharashtra": "MH", "Madhya Pradesh": "MP", "Karnataka": "KA", "Uttar Pradesh": "UP"}


def save(fig, name):
    fig.savefig(FIG / name); plt.close(fig); print("figure", name)


def fig_layouts():
    tilt = pd.read_csv(OUT / "phase3_energy.csv").tilt_deg.median()
    lays = build_layouts(float(tilt))
    fig, axs = plt.subplots(4, 1, figsize=(7.2, 5.6), sharex=True)
    for ax, c in zip(axs, ("C1", "C2", "C3", "REF")):
        L = lays[c]
        for k in range(-1, 4):
            y0 = k * L.pitch_m
            ax.plot([y0, y0 + L.footprint_m], [L.clearance_m, L.top_height_m], color=COL[c], lw=3, solid_capstyle="round")
            ax.plot([y0 + 0.3, y0 + 0.3], [0, L.clearance_m + 0.15], color=INK2, lw=0.8)
            ax.plot([y0 + L.footprint_m - 0.3] * 2, [0, L.top_height_m - 0.1], color=INK2, lw=0.8)
            if not L.crop_under_panels:
                ax.axvspan(y0 + L.footprint_m + L.crop_margin_m, y0 + L.pitch_m - L.crop_margin_m, ymax=0.08,
                           color="#1baf7a", alpha=0.25, lw=0)
        ax.axhline(0, color=INK, lw=0.8); ax.set_ylim(-0.2, 5); ax.set_xlim(-2, 30); ax.grid(False)
        ax.set_yticks([0, 2.5, 5]); ax.set_ylabel("m")
        ax.text(29.8, 4.3, f"{c}: GCR {L.gcr:.2f}, pitch {L.pitch_m:.1f} m, clearance {L.clearance_m} m",
                ha="right", va="top", color=INK, fontsize=8)
    axs[-1].set_xlabel("north-south distance (m); south to the left; tilt %.0f deg" % tilt)
    axs[2].text(29.8, 3.3, "green band on the ground = cropped strip (C3)", ha="right", fontsize=7, color=INK2)
    save(fig, "fig1_layouts.png")


def fig_ground_profile(state="Rajasthan"):
    st = pd.read_csv(OUT / "phase2_ground_strips_monthly.csv")
    st = st[(st.state == state) & st.month.isin([11, 12, 1, 2, 3])]
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    for c in ("C1", "C2", "C3"):
        s = st[st.config == c].groupby("y_m").agg(g=("ground_kwh_m2", "sum"), o=("open_kwh_m2", "sum"), cr=("cropped", "first"))
        rel = s.g / s.o
        ax.plot(s.index, rel, color=COL[c], lw=2, label=c)
        if (~s.cr).any():
            ax.plot(s.index[~s.cr], rel[~s.cr], color="white", lw=0.8, ls=(0, (2, 2)))
    ax.set_ylim(0, 1.05); ax.set_xlabel("position within one row pitch, from the lower (south) edge of a row (m)")
    ax.set_ylabel("ground irradiation / open field")
    ax.set_title(f"Rabi-season (Nov-Mar) light at the ground, {state}", loc="left", fontsize=10, color=INK)
    ax.legend(ncol=3, loc="lower right")
    save(fig, "fig2_ground_profile.png")


def grouped_bars(ax, df, value, cats, groups, err=None):
    n = len(groups); w = 0.8 / n
    x = np.arange(len(cats))
    for i, g in enumerate(groups):
        v = [df[(df.cat == c) & (df.grp == g)][value].mean() for c in cats]
        ax.bar(x + (i - (n - 1) / 2) * w, v, w * 0.92, color=COL[g], label=g, zorder=2)
    ax.set_xticks(x); ax.set_xticklabels(cats)


def fig_rsr():
    r = pd.read_csv(OUT / "phase2_rsr_seasonal.csv")
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True)
    for ax, season in zip(axs, ("rabi (Nov-Mar)", "kharif (Jun-Oct)")):
        d = r[r.season == season].assign(cat=lambda x: x.state.map(ABBR), grp=lambda x: x.config)
        grouped_bars(ax, d, "rsr_cropped_mean", [ABBR[s] for s in STATE_ORDER], ["C1", "C2", "C3"])
        ax.set_title(season, loc="left", fontsize=10, color=INK)
    axs[0].set_ylabel("RSR on cropped land (season mean)"); axs[1].legend(ncol=3, loc="upper right")
    save(fig, "fig3_rsr.png")


def fig_energy():
    e = pd.read_csv(OUT / "phase3_energy.csv").assign(cat=lambda x: x.state.map(ABBR), grp=lambda x: x.config)
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    grouped_bars(ax, e, "mwh_per_ha", [ABBR[s] for s in STATE_ORDER], ["C1", "C2", "C3", "REF"])
    ax.set_ylabel("AC energy, year 1 (MWh per gross ha)"); ax.legend(ncol=4, loc="upper left", bbox_to_anchor=(0, 1.15))
    save(fig, "fig4_energy.png")


def fig_curves():
    cv = pd.read_csv(OUT / "phase4_curves.csv"); dd = pd.read_csv(OUT / "phase4_dataset_used.csv")
    groups = [g for g in ("grain legumes", "fruity vegetables", "C3 cereals", "tubers/root crops") if g in set(cv.group)]
    crop_group = {c[2]: c[5] for c in CASES if c[5]}
    fig, axs = plt.subplots(1, len(groups), figsize=(7.2, 2.7), sharey=True)
    axs = np.atleast_1d(axs)
    for ax, g in zip(axs, groups):
        c = cv[cv.group == g]
        ax.fill_between(c.rsr, c.pi_low, c.pi_high, color=S[0], alpha=0.12, lw=0, label="95 % prediction")
        ax.fill_between(c.rsr, c.ci_low, c.ci_high, color=S[0], alpha=0.28, lw=0, label="95 % confidence")
        ax.plot(c.rsr, c.mu, color=S[0], lw=2, label="fitted mean")
        x = dd[dd.group == g]
        ax.scatter(x.rsr, x.y_pct / 100, s=10, color=INK2, alpha=0.5, lw=0, label="meta-analysis data")
        for gg, r_, v in LAUB_PUBLISHED:
            if gg == g:
                ax.scatter([r_], [v], marker="D", s=22, color=S[1], zorder=4, label="Laub et al. published")
        for crop, ry, lo, hi, *_ in ANCHORS:
            if crop_group.get(crop) == g and lo is not None:
                ax.errorbar([(lo + hi) / 2], [ry], xerr=[[(hi - lo) / 2]], fmt="s", ms=4, color=S[2], zorder=5,
                            label="field anchor")
        ax.set_title(g, fontsize=9, loc="left", color=INK); ax.set_xlim(0, 0.8); ax.set_ylim(0, 1.6)
        ax.set_xlabel("RSR")
    axs[0].set_ylabel("relative yield")
    h, l = axs[0].get_legend_handles_labels(); seen = {}
    for a in axs:
        for hh, ll in zip(*a.get_legend_handles_labels()):
            seen.setdefault(ll, hh)
    fig.legend(seen.values(), seen.keys(), ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.12), fontsize=7.5)
    save(fig, "fig5_crop_curves.png")


def fig_ler():
    t = pd.read_csv(OUT / "phase4_case_yields.csv")
    t["mid"] = np.where(t.basis == "group curve", t.ler, (t.ler_low + t.ler_high) / 2)
    cases = list(dict.fromkeys(t.case))
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    for i, c in enumerate(("C1", "C2", "C3")):
        d = t[t.config == c].set_index("case").reindex(cases)
        y = np.arange(len(cases)) + (i - 1) * 0.25
        ax.errorbar(d["mid"], y, xerr=[d["mid"] - d.ler_low, d.ler_high - d["mid"]], fmt="o", ms=4.5, color=COL[c],
                    elinewidth=1.2, capsize=0, label=c)
        anc = (d.basis != "group curve").to_numpy()
        ax.scatter(d["mid"][anc], y[anc], s=28, facecolor="white", edgecolor=COL[c], zorder=4, lw=1.2)
    ax.axvline(1, color=INK, lw=0.8); ax.text(1.005, len(cases) - 0.4, "LER = 1", fontsize=7, color=INK2)
    ax.set_yticks(range(len(cases))); ax.set_yticklabels(cases); ax.invert_yaxis()
    ax.set_xlabel("land equivalent ratio (95 % band); open markers = field-anchor range only")
    ax.legend(ncol=3, loc="lower right")
    save(fig, "fig6_ler.png")


def fig_npv():
    e = pd.read_csv(OUT / "phase6_economics.csv")
    cases = list(dict.fromkeys(e.case)); systems = ["Agri-only", "PV-only (REF)", "C1", "C2", "C3"]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    h = 0.8 / len(systems)
    for i, s in enumerate(systems):
        d = e[e.system == s].set_index("case").reindex(cases)
        ax.barh(np.arange(len(cases)) + (i - 2) * h, d.total_npv / 1e5, h * 0.9, color=COL[s], label=s, zorder=2)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_yticks(range(len(cases))); ax.set_yticklabels(cases); ax.invert_yaxis()
    ax.set_xlabel("net present value over 25 years (INR lakh per gross hectare)")
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.08), fontsize=7.5)
    save(fig, "fig7_npv.png")


def fig_tornado(case=None, cfg="C2"):
    s = pd.read_csv(OUT / "phase6_sensitivity.csv")
    case = case or s.case.iloc[0]
    d = s[(s.case == case) & (s.config == cfg)].copy()
    d["span"] = (d.high_vs_ref - d.low_vs_ref).abs(); d = d.sort_values("span")
    base = d.base_vs_ref.iloc[0] / 1e5
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    for i, r in enumerate(d.itertuples()):
        lo, hi = r.low_vs_ref / 1e5, r.high_vs_ref / 1e5
        ax.barh(i, lo - base, left=base, color=S[0], height=0.6, zorder=2)
        ax.barh(i, hi - base, left=base, color=S[1], height=0.6, zorder=2)
    ax.axvline(base, color=INK, lw=0.8)
    ax.set_yticks(range(len(d))); ax.set_yticklabels(d.parameter, fontsize=7.5)
    ax.set_xlabel(f"NPV({cfg}) - NPV(PV-only), INR lakh/ha  [{case}]")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=S[0], label="first value of each pair"), Patch(color=S[1], label="second value")],
              loc="lower right", fontsize=7.5)
    save(fig, f"fig8_tornado_{case}_{cfg}.png")


if __name__ == "__main__":
    fig_layouts(); fig_ground_profile(); fig_rsr(); fig_energy(); fig_curves(); fig_ler(); fig_npv()
    fig_tornado("MP-wheat", "C2"); fig_tornado("MP-wheat", "C3")
