"""State-crop-season cases (plan section 3) and their crop-group mapping to Laub et al. (2022).

Growing months are PROVISIONAL (typical sowing-to-harvest windows); each must be checked against the
ICAR / State Agricultural University package of practices for the proxy district before reporting.
group = None means no Laub group fits: the case is reported from its field anchor(s) only.
"""
CASES = [
    # id, state, crop, season, months (growing period), Laub group, grade
    ("RJ-chickpea", "Rajasthan",      "Chickpea",  "rabi",   [11, 12, 1, 2],       "grain legumes",      "A"),
    ("RJ-mungbean", "Rajasthan",      "Mung bean", "kharif", [7, 8, 9],            "grain legumes",      "A*"),
    ("MP-chickpea", "Madhya Pradesh", "Chickpea",  "rabi",   [10, 11, 12, 1, 2],   "grain legumes",      "A (transferred)"),
    ("GJ-tomato",   "Gujarat",        "Tomato",    "rabi",   [11, 12, 1, 2, 3],    "fruity vegetables",  "A-"),
    ("KA-tomato",   "Karnataka",      "Tomato",    "rabi",   [11, 12, 1, 2, 3],    "fruity vegetables",  "B"),
    ("MP-wheat",    "Madhya Pradesh", "Wheat",     "rabi",   [11, 12, 1, 2, 3],    "C3 cereals",         "B"),
    ("UP-wheat",    "Uttar Pradesh",  "Wheat",     "rabi",   [11, 12, 1, 2, 3],    "C3 cereals",         "B"),
    ("UP-potato",   "Uttar Pradesh",  "Potato",    "rabi",   [10, 11, 12, 1, 2],   "tubers/root crops",  "B"),
    ("MH-onion",    "Maharashtra",    "Onion",     "rabi",   [12, 1, 2, 3, 4],     None,                 "B-"),
    ("RJ-cumin",    "Rajasthan",      "Cumin",     "rabi",   [11, 12, 1, 2],       None,                 "A (single trial)"),
]

# Published relative-yield predictions from Laub et al. (2022, Agron. Sustain. Dev. 42:51, doi:10.1007/s13593-022-00783-7)
# text, used as the Phase 4 gate. (group, RSR, relative yield) - the refit must reproduce these within a tolerance.
# All eleven values checked against the paper text on 2026-10-25.
LAUB_PUBLISHED = [
    ("berries", 0.20, 1.14), ("fruits", 0.20, 1.14), ("fruity vegetables", 0.20, 1.08),
    ("forages", 0.20, 1.03), ("berries", 0.40, 1.14), ("fruits", 0.40, 1.13),
    ("fruity vegetables", 0.40, 1.02), ("forages", 0.40, 0.93),
    ("leafy vegetables", 0.40, 0.86), ("maize", 0.40, 0.45), ("grain legumes", 0.40, 0.50),
]

# Field anchors (relative yield AV / control) with their source; used to CHECK the curves, never fitted.
# rsr_lo, rsr_hi: the shade level reported with the anchor (None = not reported). CAZRI values are spot PAR
# readings under the arrays, not season-integrated radiation, so they are an approximate RSR only.
# (crop, relative yield, rsr_lo, rsr_hi, note, source) - values checked against the sources on 2026-10-25
# (CAZRI: Poonia & Santra, AgriVoltaics Conf. Proc. 1, 2022).
ANCHORS = [
    ("Chickpea", 2490 / 2670, 0.47, 0.59, "CAZRI Jodhpur rabi 2021-22, irrigated; PAR -47 to -59 % (spot)", "doi:10.52825/agripv.v1i.601"),
    ("Cumin",    1000 / 1120, 0.42, 0.44, "CAZRI Jodhpur rabi 2021-22; PAR -42 to -44 % (spot)",           "doi:10.52825/agripv.v1i.601"),
    ("Mung bean", 1 - 0.046,  None, None, "CAZRI Jodhpur kharif 2021, rainfed; control yield and RSR not reliably reported", "doi:10.52825/agripv.v1i.601"),
    ("Wheat",    1 - 0.187,   0.30, 0.30, "Heggelbach 2017; PAR about -30 %",  "doi:10.3390/agronomy11040733"),
    ("Wheat",    1.027,       0.30, 0.30, "Heggelbach 2018; PAR about -30 %",  "doi:10.3390/agronomy11040733"),
    ("Potato",   1 - 0.182,   0.30, 0.30, "Heggelbach 2017; PAR about -30 %",  "doi:10.3390/agronomy11040733"),
    ("Potato",   1.11,        0.30, 0.30, "Heggelbach 2018; PAR about -30 %",  "doi:10.3390/agronomy11040733"),
    ("Onion",    66.4 / 82.4, None, None, "Korea 2018-19",                     "doi:10.3390/agriculture12050619"),
    ("Onion",    76.3 / 84.3, None, None, "Korea 2019-20",                     "doi:10.3390/agriculture12050619"),
]
