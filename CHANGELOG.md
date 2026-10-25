# Changes to the model code

## Fixes
- **Leap day** (`run_phase23.load_tmy`): 29 February is removed *before* the typical year is re-stamped onto 2025. Previously a Feb-29 row crashed the re-stamp (`ValueError`), and the later filter could never act.
- **RSR open-field reference** (`run_phase23`, `pv.open_field_irradiance`): the unshaded reference is now DNI cos z + DHI, built from the same components as the ground strips. Previously the file's GHI was used, so any GHI/DNI/DHI closure error showed up as apparent shade (2 % mismatch = 2 % RSR).

## Method changes
- **Gross-hectare basis** (`config.AUX_LAND_SHARE`, `gross_factor`, `ref_row_kwp_per_ha`): the CTUIL 3 acres/MW norm is a whole-plant figure. Every system now loses the same 15 % of its hectare to roads, pads and setbacks, and the reference plant's rows are solved so its *gross* density equals the norm. Previously the AV layouts had no overhead while the reference did, which inflated the AV energy ratio and LER.
- **Field anchors** (`cases.ANCHORS`, `run_phase45`): shade levels added; every anchor with a crop group and a shade level is now checked against the curve's 95 % prediction band (`phase4_anchor_check.csv`).
- **Ranking**: anchor-only crops (onion, cumin) do not respond to the layout, so they are excluded from the LER tiers and reported separately. Rows with no estimate no longer silently join the last tier.
- **Gate** extended from 9 to 11 published values (berries and fruits at 40 % RSR added); all checked against the paper text.
- **Growing-window sensitivity**: yields are recomputed with each season extended by one month.

## Additions
- Phase 6 economics (`econ_inputs.py`, `econ.py`, `run_phase6.py`) with sourced inputs, NPV/LCOE/IRR/payback, break-even tariff, scenarios and one-at-a-time sensitivity; closed-form tests (`tests/test_econ.py`).
- Figures (`make_figures.py`), report and defence-brief builders (`report/`), one-command build (`make_submission.py`).
- Synthetic end-to-end plumbing test (`tests/make_synthetic_inputs.py`) and one-click data download (`scripts/fetch_all_data.py`).

## Tests
- Solar position now validated against an independent Meeus reference at three sites (limit 0.02 deg; was a 0.6 deg comparison against the NOAA approximation).
- `np.trapezoid` falls back to `np.trapz` on numpy < 2.

## Real-data run (25 Oct 2026)
- **Data**: PVGIS 5.3 TMY + PVcalc (42 files, PVGIS-ERA5) and Zenodo 5716091 workbooks fetched via browser (same URLs as `scripts/fetch_all_data.py`); see `data/MANIFEST.json`.
- **Column map** (`data/zenodo_columns.json`): `Crop_type` labels map 1:1 to the nine Laub groups; location = `Reference` (study); the 89 RSR = 0 control rows are kept (`include_controls`). `run_phase45.load_dataset` accepts a list of location columns.
- **Crop model form** (`cropfit.fit_lmm(quad=...)`, `run_phase45.QUAD`): with the real data the per-group quadratic passed only 6/11 gate values (fruity vegetables off by 0.37). Laub et al.'s published 20 %/40 % pairs imply one shared quadratic (about -0.72) for every group, i.e. the RSR^2 x group interaction was dropped by their backward elimination. The shared-quadratic model passes 11/11 (max |diff| 0.005 = rounding). Gate under all variants: `phase4_gate_variants.csv`; Wald test of equal quadratics logged in `phase45_log.txt` (it rejects equality without small-sample correction - reported as a caveat).
- **PVGIS check** (`run_phase23`): adds in-plane irradiation and performance-ratio columns. Model is 1-6 % above PVcalc; irradiation agrees (-3.8..+0.2 %), the gap is PVGIS's larger temperature/low-light loss.
- **Build** (`make_submission.py`): the LibreOffice helper path is found at run time instead of a hard-coded session path.
- **Report/defence wording** rewritten for the real results (single LER tier, C2 best technically, C3 best economically, no AV beats PV-only at Rs 3.00, break-even tariffs, crop-income flips for tomato/onion, PVGIS optimism).
