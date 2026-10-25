"""M2 ground irradiance and M3 PV energy.

Diffuse model: Hay-Davies. The circumsolar share A_i = DNI / DNI_extra of the diffuse irradiance is
treated as coming from the sun's direction (shaded like beam); the remainder is isotropic.
Hay, J.E. & Davies, J.A. (1980) Calculation of the solar radiation incident on an inclined surface.
Proc. First Canadian Solar Radiation Data Workshop, 59-72.

PV chain (all stated assumptions, editable in PVParams):
- angle of incidence modifier: ASHRAE, b0 = 0.05, applied to beam and circumsolar
- row-to-row shading: front-row shadow on the slant reduces beam + circumsolar linearly
  (no electrical mismatch penalty: optimistic for portrait modules; stated limitation)
- isotropic sky diffuse on the module: reduced by the front row (module_sky_view)
- ground-reflected: albedo * GHI * (1 - cos beta)/2 (the ground below the array is partly shaded:
  slight overestimate, small at these tilts)
- cell temperature: Faiman (u0 = 25 W/m2K, u1 = 6.84 W/m3sK)
- DC power: PVWatts form, gamma = -0.0035 /K; all other losses lumped at 14 % (as PVGIS default)
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd

from .solarpos import solar_position, extraterrestrial_dni
from .geometry import (Layout, sun_t, strip_centres, ground_shade, ground_sky_view,
                       module_beam_shaded_fraction, module_sky_view)


@dataclass(frozen=True)
class PVParams:
    module_wp: float = 550.0
    module_area_m2: float = 2.28 * 1.13
    gamma_per_k: float = -0.0035
    system_loss: float = 0.14
    iam_b0: float = 0.05
    albedo: float = 0.20
    faiman_u0: float = 25.0
    faiman_u1: float = 6.84

    @property
    def wp_per_m2_module(self):
        return self.module_wp / self.module_area_m2


def sun_and_components(weather: pd.DataFrame, lat, lon):
    """weather: index tz-aware UTC timestamps at the CENTRE of each hour; columns ghi, dni, dhi, temp_air, wind."""
    zen, elev, az = solar_position(weather.index, lat, lon)
    dni_extra = extraterrestrial_dni(weather.index)
    up = elev > 0
    dni = np.where(up, weather["dni"].to_numpy(), 0.0)
    dhi = weather["dhi"].to_numpy()
    ghi = weather["ghi"].to_numpy()
    ai = np.clip(np.where(up, dni / dni_extra, 0.0), 0, 1)
    return dict(zen=zen, elev=elev, az=az, up=up, dni=dni, dhi=dhi, ghi=ghi, ai=ai)


def ground_irradiance(lay: Layout, sc: dict, n_strips=40):
    """Hourly horizontal irradiance at ground strips under the array, W/m2. Shape (n_times, n_strips).
    beam + circumsolar follow the beam shadow; isotropic diffuse scaled by each strip's sky view factor.
    Reflections from panel backs and from the ground are ignored (small; stated)."""
    y = strip_centres(lay, n_strips)
    t = np.where(sc["up"], sun_t(np.where(sc["up"], sc["elev"], 45.0), sc["az"]), 0.0)
    lit = 1.0 - ground_shade(lay, y, t)
    cosz = np.where(sc["up"], np.cos(np.radians(sc["zen"])), 0.0)
    beam_h = sc["dni"] * cosz
    circ_h = sc["ai"] * sc["dhi"]
    iso_h = (1 - sc["ai"]) * sc["dhi"]
    svf = ground_sky_view(lay, y)
    g = (beam_h + circ_h)[:, None] * lit + iso_h[:, None] * svf[None, :]
    g[~sc["up"], :] = iso_h[~sc["up"], None] * svf[None, :]
    return y, g, svf


def open_field_irradiance(sc: dict):
    """Unshaded horizontal irradiance built from the SAME components as ground_irradiance
    (beam DNI cos z + diffuse DHI), so that an unobstructed strip has RSR = 0 exactly.
    Using the file's GHI instead would turn any GHI/DNI/DHI closure error into apparent shade."""
    cosz = np.where(sc["up"], np.cos(np.radians(sc["zen"])), 0.0)
    return sc["dni"] * cosz + sc["dhi"]


def poa_interior_row(lay: Layout, sc: dict, prm: PVParams, array_az=180.0, shading=True):
    """Plane-of-array irradiance (effective, after IAM) for an interior row, W/m2."""
    b = lay.beta
    zen, az = np.radians(sc["zen"]), np.radians(sc["az"])
    cos_aoi = np.cos(zen) * np.cos(b) + np.sin(zen) * np.sin(b) * np.cos(az - np.radians(array_az))
    front = (cos_aoi > 0) & sc["up"]
    cos_aoi_c = np.clip(cos_aoi, 1e-6, 1)
    iam = np.where(front, np.clip(1 - prm.iam_b0 * (1 / cos_aoi_c - 1), 0, 1), 0.0)
    shade = module_beam_shaded_fraction(lay, sc["elev"], sc["az"], array_az) if shading else 0.0
    beam = sc["dni"] * np.where(front, cos_aoi, 0.0)
    cosz = np.clip(np.cos(zen), 0.0871557, 1)               # Hay-Davies Rb, cos z floored at 85 deg
    circ = sc["ai"] * sc["dhi"] * np.where(front, cos_aoi / cosz, 0.0)
    svf_mod = module_sky_view(lay) if shading else (1 + np.cos(b)) / 2
    iso = (1 - sc["ai"]) * sc["dhi"] * svf_mod
    refl = prm.albedo * sc["ghi"] * (1 - np.cos(b)) / 2
    poa_eff = (beam + circ) * (1 - shade) * iam + iso + refl
    poa_raw = (beam + circ) * (1 - shade) + iso + refl
    return poa_eff, poa_raw


def pv_energy(lay: Layout, weather: pd.DataFrame, sc: dict, prm: PVParams, shading=True):
    """Hourly AC energy per kWp (kWh/kWp per hour step = kW/kWp)."""
    poa_eff, poa_raw = poa_interior_row(lay, sc, prm, shading=shading)
    tcell = weather["temp_air"].to_numpy() + poa_raw / (prm.faiman_u0 + prm.faiman_u1 * weather["wind"].to_numpy())
    p_dc = (poa_eff / 1000.0) * (1 + prm.gamma_per_k * (tcell - 25.0))
    p_ac = np.clip(p_dc, 0, None) * (1 - prm.system_loss)
    return p_ac  # kW per kWp, hourly -> summing gives kWh/kWp


def kwp_per_ha(lay: Layout, prm: PVParams):
    """Installed capacity per gross hectare for infinite rows (no roads/edges).
    Module area per unit ground area = slant / pitch (= GCR / cos beta)."""
    return (lay.slant_m / lay.pitch_m) * prm.wp_per_m2_module * 10000 / 1000.0
