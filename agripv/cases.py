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

# Published relative-yield predictions from Laub et al. (2022) text, used as the Phase 4 gate.
# (group, RSR, relative yield) - the refit must reproduce these within a tolerance.
LAUB_PUBLISHED = [
    ("berries", 0.20, 1.14), ("fruits", 0.20, 1.14), ("fruity vegetables", 0.20, 1.08),
    ("forages", 0.20, 1.03), ("fruity vegetables", 0.40, 1.02), ("forages", 0.40, 0.93),
    ("leafy vegetables", 0.40, 0.86), ("maize", 0.40, 0.45), ("grain legumes", 0.40, 0.50),
]

# Field anchors (relative yield AV / control) with their source; used to check the bands, never fitted.
ANCHORS = [
    ("Chickpea", 2490 / 2670, "CAZRI rabi 2021-22; PAR -47 to -59 % (spot readings)", "doi:10.52825/agripv.v1i.601"),
    ("Cumin",    1000 / 1120, "CAZRI rabi 2021-22; PAR -42 to -44 % (spot readings)", "doi:10.52825/agripv.v1i.601"),
    ("Mung bean", 1 - 0.046,  "CAZRI kharif 2021; control yield not reported",       "doi:10.52825/agripv.v1i.601"),
    ("Wheat",    1 - 0.187,   "Heggelbach 2017; PAR about -30 %",                    "doi:10.3390/agronomy11040733"),
    ("Wheat",    1.027,       "Heggelbach 2018; PAR about -30 %",                    "doi:10.3390/agronomy11040733"),
    ("Potato",   1 - 0.182,   "Heggelbach 2017",                                     "doi:10.3390/agronomy11040733"),
    ("Potato",   1.11,        "Heggelbach 2018",                                     "doi:10.3390/agronomy11040733"),
    ("Onion",    66.4 / 82.4, "Korea 2018-19",                                       "doi:10.3390/agriculture12050619"),
    ("Onion",    76.3 / 84.3, "Korea 2019-20",                                       "doi:10.3390/agriculture12050619"),
]
