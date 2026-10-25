# Agrivoltaics in India: state-wise technical and economic assessment

Agriculture-only vs PV-only vs three agrivoltaic layouts (C1, C2 elevated; C3 interspace) for ten crop-season cases
in Rajasthan, Gujarat, Maharashtra, Madhya Pradesh, Karnataka and Uttar Pradesh.

## Contents of the submission
| Folder | What it holds |
|---|---|
| `Agrivoltaics_India_Report.pdf / .docx` | The report |
| `Defence_Brief.pdf / .docx` | Likely questions and answers for the viva |
| `outputs/` | Every result table (CSV) and run log; all numbers in the report come from these |
| `figures/` | Report figures (PNG) |
| `data/` | The exact inputs used: PVGIS 5.3 TMY + PVcalc (6 sites), Zenodo 5716091 workbook, column map |
| `code/` | The model package and runners (see below) |

## Model chain
| Module | File | What it does |
|---|---|---|
| M1 | `agripv/solarpos.py` | Solar position (PSA algorithm) |
| M2 | `agripv/geometry.py`, `agripv/pv.py` | Row geometry, ground shadows, sky view factors, ground irradiance |
| M3 | `agripv/pv.py` | Plane-of-array irradiance, row shading, temperature, AC energy |
| M4 | `agripv/cropfit.py` | REML mixed-model refit of Laub et al. (2022); strip-wise yields |
| M6-M7 | `config.py`, `run_phase45.py` | Gross-hectare land accounting, LER, technical ranking |
| M8 | `agripv/econ_inputs.py`, `agripv/econ.py`, `run_phase6.py` | NPV, LCOE, IRR, break-even tariff, sensitivity |

## Reproduce
```
pip install -r requirements.txt
python scripts/fetch_all_data.py            # or use the data/ folder supplied
python -I tests/test_validation.py          # 10 physics checks
python -I tests/test_cropfit.py             # REML parameter recovery
python -I tests/test_econ.py                # cash-flow closed forms
python -I run_phase23.py data/pvgis outputs
python -I run_phase45.py data outputs
python -I run_phase6.py outputs
python -I make_figures.py outputs figures
```
`make_submission.py` runs all of the above and also builds the report (needs Node.js with `docx`, and LibreOffice).

Changes made to the original code are listed in `CHANGELOG.md`.

## Data licences
PVGIS data (c) European Union, JRC. Crop dataset: Pataczek & Laub (2021), Zenodo doi:10.5281/zenodo.5716091, CC BY 4.0.
