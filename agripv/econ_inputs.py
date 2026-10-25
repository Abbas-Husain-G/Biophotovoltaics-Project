"""M8 inputs - economic parameters for Phase 6. Every value is an explicit, sourced (or flagged) assumption.

Sources were checked on 2026-10-25. Money is in nominal Indian rupees (INR); 1 crore = 1e7, 1 lakh = 1e5.
Quality flags: A = official / regulatory value for the year of the study; B = peer-reviewed or official but
older or from another region; C = indicative only (mixed vintage or proxy), tested at +/- 50 % in sensitivity.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PVEcon:
    # Ground-mounted PV capital cost: CTUIL revised benchmark project cost "Rs 35 million per MW for solar
    # projects" (CTUIL advisory, reported 7 Sep 2026). Taken as INR per Wp DC (stated assumption).
    capex_inr_per_wp: float = 35.0
    # Agrivoltaic premium on capex. Elevated (3 m) structures C1, C2: "25-30 percent more to set up than
    # conventional ground-mounted solar" (MNRE Secretary S. K. Sarangi, reported 20 Oct 2026) -> midpoint 27.5 %.
    # C3 (interspace, standard 0.5 m height, wider rows): no elevated structure; 5 % for longer DC cabling,
    # fencing and per-MW civil work on a larger area (assumption, sensitivity 0-15 %).
    capex_premium: dict = field(default_factory=lambda: {"C1": 0.275, "C2": 0.275, "C3": 0.05, "REF": 0.0})
    # O&M: CERC order of 26 Dec 2025 (NTPC Green 40 MW, Ayodhya): Rs 3.63 lakh/MW/yr, escalation 5.25 %/yr.
    om_inr_per_kwp_yr: float = 363.0
    om_escalation: float = 0.0525
    # Discount rate: 9.05 % used by CERC in the same order (levelised tariff Rs 3.36/kWh).
    discount_rate: float = 0.0905
    life_years: int = 25
    # Module degradation: 0.5 %/yr (assumption; CERC regulations "do not provide norms for a module
    # degradation factor" - same order; 0.7 %/yr tested in sensitivity).
    degradation: float = 0.005
    # Sale tariff, INR/kWh, flat nominal for 25 years. Base 3.00: decentralised PM-KUSUM installations
    # "Rs 2.80 to Rs 3.00 per unit" (MNRE, Oct 2026); MSKVY 2.0 Maharashtra weighted average 2.825 (MERC order
    # 5 Aug 2026); Rajasthan KUSUM-C feeder tariffs 2.79-3.04. Scenario "AV tariff" 3.25: AgriPV "Rs 3.20 to
    # Rs 3.30 per unit" (MNRE, Oct 2026).
    tariff_inr_per_kwh: float = 3.00
    tariff_av_scenario: float = 3.25
    # Extra crop operating cost under elevated arrays (working around posts, smaller machinery): 10 %
    # (assumption, sensitivity 0-20 %). Not applied to C3 (crop strips are open).
    av_crop_cost_penalty: dict = field(default_factory=lambda: {"C1": 0.10, "C2": 0.10, "C3": 0.0})
    # Nominal growth of crop prices and costs: RBI CPI inflation target 4 % (assumption that crop net income
    # keeps pace with general inflation).
    crop_escalation: float = 0.04


# Crop economics per case, per hectare of open (unshaded) field, at state-average farm yields.
# yield_q_ha: quintals/ha (1 q = 100 kg); price: INR/q; cost_inr_ha: operating (paid-out + family labour) cost.
# net_override: when a source reports only the net return, it is used directly (yield/price/cost then None).
CROP_ECON = {
    "RJ-chickpea": dict(yield_q_ha=10.81, price=5875, cost_inr_ha=10.81 * 3699, grade="A",
        src="Yield: DPD Annual Report 2023-24 (Rajasthan normal 2018-19 to 2022-23, 22.51 lakh t / 20.82 lakh ha). "
            "Price: MSP 2026-27. Cost: CACP projected all-India A2+FL 2026-27, Rs 3,699/q (PIB, Oct 2025)."),
    "RJ-mungbean": dict(yield_q_ha=4.92, price=8780, cost_inr_ha=4.92 * 5438, grade="A",
        src="Yield: DPD Annual Report 2023-24 (Rajasthan normal, 12.04 lakh t / 24.48 lakh ha). Price: MSP 2026-27 "
            "Rs 8,780/q; cost of production Rs 5,438/q (PIB, May 2026)."),
    "MP-chickpea": dict(yield_q_ha=14.21, price=5875, cost_inr_ha=14.21 * 3699, grade="A",
        src="Yield: DPD Annual Report 2023-24 (MP normal, 31.93 lakh t / 22.47 lakh ha). Price/cost as RJ-chickpea."),
    "GJ-tomato": dict(yield_q_ha=291.2, price=1009, cost_inr_ha=130534, grade="C",
        src="Yield: ICAR-IASRI Agricultural Research Data Book Table 4.13 (Gujarat 2017-18, 29.12 t/ha). Price and "
            "cost A2: Sai et al. (2022) Biol. Forum 14(2):381-383 (Telangana, 2019-20) - proxy region and year."),
    "KA-tomato": dict(yield_q_ha=324.0, price=1009, cost_inr_ha=130534, grade="C",
        src="Yield: ICAR-IASRI Data Book Table 4.13 (Karnataka 2017-18, 32.40 t/ha). Price/cost as GJ-tomato."),
    "MP-wheat": dict(yield_q_ha=31.63, price=2585, cost_inr_ha=31.63 * 1239, grade="A",
        src="Yield: MoA&FW final estimates 2024-25 via UPAg (MP 24.51 Mt / 7.75 Mha). Price: MSP 2026-27. Cost: "
            "CACP projected A2+FL 2026-27, Rs 1,239/q (PIB, Oct 2025)."),
    "UP-wheat": dict(yield_q_ha=37.14, price=2585, cost_inr_ha=37.14 * 1239, grade="A",
        src="Yield: MoA&FW final estimates 2024-25 via UPAg (UP 35.65 Mt / 9.60 Mha). Price/cost as MP-wheat."),
    "UP-potato": dict(yield_q_ha=None, price=None, cost_inr_ha=None, net_override=45372, grade="B",
        src="Net return over cost C3: Yadav et al. (2024) J. Exp. Agric. Int. 46(5):825-831, Azamgarh UP "
            "(gross Rs 1,23,527/ha, cost C3 Rs 78,155/ha). State yield 27.5 t/ha 2023-24 (ASaG 2024-25 T2.49b) for reference."),
    "MH-onion": dict(yield_q_ha=250.0, price=1833, cost_inr_ha=159268, grade="C",
        src="Yield: NHRDF rabi onion Maharashtra 250 q/ha (in SFAC/Agriwatch 2012). Price: Patil et al. (2024) Mysore "
            "J. Agric. Sci. 58(3) Rs 1,833/q (Karnataka). Cost: DES cost of cultivation, Maharashtra onion 2022, "
            "operating cost Rs 1,59,268/ha (via CEIC). Mixed vintage."),
    "RJ-cumin": dict(yield_q_ha=None, price=None, cost_inr_ha=None, net_override=61606, grade="C",
        src="Net return, farmers' practice: Choudhary et al. (2016) Annals of Arid Zone 52(2), Pali RJ, FLDs "
            "2005-06 to 2009-10 (old; not inflated). State yield 552 kg/ha 2020-21 (DASD) for reference."),
}


def crop_net_open_field(case_id):
    """Annual net crop income, INR per hectare of unshaded field (year-1 value)."""
    c = CROP_ECON[case_id]
    if c.get("net_override") is not None:
        return float(c["net_override"])
    return c["yield_q_ha"] * c["price"] - c["cost_inr_ha"]


def crop_gross_and_cost(case_id):
    """(gross revenue, operating cost) per open-field ha. For net-only sources, gross/cost are unknown:
    the shaded yield then scales the whole net (cost assumed to scale with yield - stated limitation)."""
    c = CROP_ECON[case_id]
    if c.get("net_override") is not None:
        return None, None
    return c["yield_q_ha"] * c["price"], c["cost_inr_ha"]
