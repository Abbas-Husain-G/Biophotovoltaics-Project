"""M1 - Solar position.

PSA algorithm: Blanco-Muriel, M., Alarcon-Padilla, D.C., Lopez-Moratalla, T., Lara-Coira, M. (2001).
Computing the solar vector. Solar Energy 70(5), 431-441. Stated accuracy about 0.01 deg (1999-2015);
used here outside that window, where accuracy degrades slowly (checked against NOAA, see tests).

Conventions used everywhere in this package
- elevation alpha: degrees above horizon (geometric, no refraction)
- azimuth: degrees clockwise from NORTH (south = 180)
"""
import numpy as np
import pandas as pd

EARTH_MEAN_RADIUS_KM = 6371.01
AU_KM = 149597890.0


def solar_position(times_utc: pd.DatetimeIndex, lat_deg: float, lon_deg: float):
    """Return (zenith_deg, elevation_deg, azimuth_deg_from_north) as numpy arrays."""
    t = times_utc.tz_convert("UTC")
    n = t.to_julian_date().to_numpy() - 2451545.0
    hours = t.hour.to_numpy() + t.minute.to_numpy() / 60 + t.second.to_numpy() / 3600

    omega = 2.1429 - 0.0010394594 * n
    mean_lon = 4.8950630 + 0.017202791698 * n
    mean_anom = 6.2400600 + 0.0172019699 * n
    ecl_lon = (mean_lon + 0.03341607 * np.sin(mean_anom) + 0.00034894 * np.sin(2 * mean_anom)
               - 0.0001134 - 0.0000203 * np.sin(omega))
    obliq = 0.4090928 - 6.2140e-9 * n + 0.0000396 * np.cos(omega)

    ra = np.arctan2(np.cos(obliq) * np.sin(ecl_lon), np.cos(ecl_lon)) % (2 * np.pi)
    dec = np.arcsin(np.sin(obliq) * np.sin(ecl_lon))

    gmst = 6.6974243242 + 0.0657098283 * n + hours
    lmst = np.radians(gmst * 15 + lon_deg)
    hour_angle = lmst - ra
    lat = np.radians(lat_deg)

    zen = np.arccos(np.clip(np.cos(lat) * np.cos(hour_angle) * np.cos(dec)
                            + np.sin(dec) * np.sin(lat), -1, 1))
    az_south = np.arctan2(-np.sin(hour_angle),
                          np.tan(dec) * np.cos(lat) - np.sin(lat) * np.cos(hour_angle))
    az = np.degrees(az_south % (2 * np.pi))  # PSA gives azimuth from north, clockwise
    zen = zen + EARTH_MEAN_RADIUS_KM / AU_KM * np.sin(zen)  # parallax
    zen_deg = np.degrees(zen)
    return zen_deg, 90.0 - zen_deg, az


def extraterrestrial_dni(times: pd.DatetimeIndex) -> np.ndarray:
    """Spencer-type eccentricity correction, W/m2 (solar constant 1367)."""
    doy = times.dayofyear.to_numpy()
    return 1367.0 * (1 + 0.033 * np.cos(2 * np.pi * doy / 365.0))
