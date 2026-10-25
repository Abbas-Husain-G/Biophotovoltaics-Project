"""Study configuration: proxy points and layouts. Every value here is an explicit, editable assumption.

Proxy points: district headquarters, coordinates rounded to 0.01 deg (approximate, to be checked
against Survey of India / Census coordinates before final reporting). They are representative
locations, not descriptions of the whole state.
"""
from .geometry import Layout

SITES = {
    # state: (proxy district, lat, lon, elevation_m approx)
    "Rajasthan":      ("Jodhpur",  26.26, 73.02, 230),
    "Gujarat":        ("Junagadh", 21.52, 70.46, 105),
    "Maharashtra":    ("Nashik",   19.99, 73.79, 580),
    "Madhya Pradesh": ("Vidisha",  23.52, 77.81, 420),
    "Karnataka":      ("Kolar",    13.14, 78.13, 840),
    "Uttar Pradesh":  ("Agra",     27.18, 78.01, 170),
}

MODULE_SLANT_M = 2.28        # 550 Wp module, 2.28 m x 1.13 m, portrait (one module along the slope)

# Configurations (Section 5.3 of the plan). Tilt is filled per site with the PV-only energy optimum.
# GCR here is the ROW-LEVEL ground coverage ratio (footprint / pitch). REF is not set by a GCR: its
# row spacing is solved from the CTUIL land norm in build_layouts.
GCR = {"C1": 0.20, "C2": 0.30, "C3": 0.30}
CLEARANCE_M = {"C1": 3.0, "C2": 3.0, "C3": 0.5, "REF": 0.5}
# C3 interspace: no crop under the footprint; 0.5 m working margin each side (assumption).
C3_MARGIN_M = 0.5
# REF: stand-alone PV at the CTUIL benchmark land use of 3 acres/MW (CTUIL advisory, Sept 2026: "unchanged
#      at 3 acres per MW for solar") -> 823.7 kWp per GROSS hectare (whole plant: rows + roads, inverter pads,
#      boundary setbacks).
CTUIL_ACRES_PER_MW = 3.0
# Share of gross land NOT occupied by the row field (roads, inverter/transformer pads, setbacks, drainage).
# Applied identically to every system, so that all land-based comparisons are on the same gross-hectare
# basis. Assumption (no Indian norm found); sensitivity 0-0.25 in the economics. 0 reproduces the original
# treatment, in which the CTUIL gross norm was used as if it were a row-level density.
AUX_LAND_SHARE = 0.15


def gross_factor(aux_share=AUX_LAND_SHARE):
    """Multiply any row-level per-hectare quantity (kWp/ha, MWh/ha, cropped share) by this."""
    return 1.0 - aux_share


def ref_row_kwp_per_ha(aux_share=AUX_LAND_SHARE):
    """Row-level capacity density of the reference plant such that its GROSS density equals the CTUIL norm."""
    return 1000.0 / (CTUIL_ACRES_PER_MW * 0.404686) / gross_factor(aux_share)   # 1 acre = 0.404686 ha


def build_layouts(tilt_deg, wp_per_m2=550.0 / (2.28 * 1.13), aux_share=AUX_LAND_SHARE):
    L = MODULE_SLANT_M
    lay = {}
    for c in ("C1", "C2"):
        lay[c] = Layout.from_gcr(c, tilt_deg, L, GCR[c], CLEARANCE_M[c])
    lay["C3"] = Layout.from_gcr("C3", tilt_deg, L, GCR["C3"], CLEARANCE_M["C3"],
                                crop_margin_m=C3_MARGIN_M, crop_under_panels=False)
    # Reference plant: gross capacity density fixed by the CTUIL land norm, independent of tilt.
    pitch = L * wp_per_m2 * 10.0 / ref_row_kwp_per_ha(aux_share)   # slant/pitch * Wp/m2 * 10 = kWp/ha (row level)
    lay["REF"] = Layout("REF", tilt_deg, L, pitch, CLEARANCE_M["REF"])
    return lay
