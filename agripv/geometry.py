"""M2 - Geometry of infinite east-west rows of south-facing fixed-tilt modules (2-D, N-S cross-section).

Coordinates: y points NORTH along the ground, z points UP. Row k occupies the segment
    (k*p, h0)  ->  (k*p + L*cos(beta), h0 + L*sin(beta))
i.e. lower edge to the south, upper edge to the north. Infinite rows => results are
periodic in y with period p, and edge effects of a finite field are ignored (stated limitation).

Sun direction in the cross-section is described by t = s_y / s_z, the northward horizontal
displacement per unit height of a ray travelling TOWARD the sun (negative when the sun is
south of the zenith plane). A point at height z casts its shadow at y - z * t ... written below
as shadow_y = y_point - z_point * t.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Layout:
    name: str
    tilt_deg: float          # beta
    slant_m: float           # L, module dimension along the slope
    pitch_m: float           # p, row-to-row horizontal distance (centre-to-centre)
    clearance_m: float       # h0, height of the lower edge
    crop_margin_m: float = 0.0     # strip kept uncropped on each side of the footprint (interspace designs)
    crop_under_panels: bool = True  # False for interspace designs (no crop below the footprint)

    @property
    def beta(self):
        return np.radians(self.tilt_deg)

    @property
    def footprint_m(self):
        return self.slant_m * np.cos(self.beta)

    @property
    def gcr(self):
        return self.footprint_m / self.pitch_m

    @property
    def top_height_m(self):
        return self.clearance_m + self.slant_m * np.sin(self.beta)

    @staticmethod
    def from_gcr(name, tilt_deg, slant_m, gcr, clearance_m, **kw):
        pitch = slant_m * np.cos(np.radians(tilt_deg)) / gcr
        return Layout(name, tilt_deg, slant_m, pitch, clearance_m, **kw)


def sun_t(elev_deg, az_deg):
    """t = s_y/s_z for a sun at (elevation, azimuth-from-north). Only meaningful for elev > 0."""
    el = np.radians(elev_deg)
    az = np.radians(az_deg)
    return np.cos(el) * np.cos(az) / np.sin(el)


def strip_centres(lay: Layout, n_strips: int):
    return (np.arange(n_strips) + 0.5) / n_strips * lay.pitch_m


def cropped_mask(lay: Layout, y):
    """Boolean mask of ground positions that are cropped (footprint lies on [0, footprint))."""
    if lay.crop_under_panels:
        return np.ones_like(y, dtype=bool)
    lo = lay.footprint_m + lay.crop_margin_m          # north of footprint + margin
    hi = lay.pitch_m - lay.crop_margin_m              # south margin before the next footprint
    return (y >= lo) & (y < hi)


def ground_shade(lay: Layout, y, t):
    """Beam-shadow indicator on the ground.

    y: (n_strips,) ground positions in [0, p);  t: (n_times,) sun parameter.
    Returns (n_times, n_strips) array of 0/1 (1 = in shadow). Exact for infinite periodic rows.
    The shadow of row 0 on the ground spans [a, b]; row k adds k*p.
    """
    L, b0, h0, p = lay.slant_m, lay.beta, lay.clearance_m, lay.pitch_m
    t = np.asarray(t, float)[:, None]
    a = 0.0 - h0 * t
    b = L * np.cos(b0) - (h0 + L * np.sin(b0)) * t
    lo = np.minimum(a, b)
    width = np.abs(b - a)
    rel = np.mod(y[None, :] - lo, p)
    return np.where(width >= p, 1.0, (rel < width).astype(float))


def ground_shade_raycast(lay: Layout, y, t, k_range=200):
    """Brute-force check of ground_shade: test every row k for intersection (for validation only)."""
    L, b0, h0, p = lay.slant_m, lay.beta, lay.clearance_m, lay.pitch_m
    t = np.asarray(t, float)
    out = np.zeros((t.size, y.size))
    denom = L * np.cos(b0) - t * L * np.sin(b0)
    for k in range(-k_range, k_range + 1):
        with np.errstate(divide="ignore", invalid="ignore"):
            s = (y[None, :] + t[:, None] * h0 - k * p) / denom[:, None]
        out = np.maximum(out, ((s >= 0) & (s <= 1)).astype(float))
    return out


def ground_sky_view(lay: Layout, y, n_ang=20001):
    """Isotropic sky view factor of horizontal ground points (2-D), by angular sampling.

    Direction phi from zenith (positive = north). Horizontal-surface weight cos(phi)/2.
    A direction is blocked if the ray hits any row: same interval test as ground_shade with t = tan(phi).
    """
    phi = np.linspace(-np.pi / 2 + 1e-6, np.pi / 2 - 1e-6, n_ang)
    blocked = ground_shade(lay, y, np.tan(phi))            # (n_ang, n_strips)
    w = np.cos(phi)[:, None] / 2.0
    return 1.0 - np.trapezoid(blocked * w, phi, axis=0)


def ground_sky_view_crossed_strings(lay: Layout, y, k_range=400):
    """Independent analytic check (Hottel crossed-strings form in 2-D):
    F_sky = 1 - 1/2 * sum over the UNION of blocked angular intervals of (sin phi_b - sin phi_a)."""
    L, b0, h0, p = lay.slant_m, lay.beta, lay.clearance_m, lay.pitch_m
    res = []
    for yy in np.atleast_1d(y):
        iv = []
        for k in range(-k_range, k_range + 1):
            y1, z1 = k * p - yy, h0
            y2, z2 = k * p + L * np.cos(b0) - yy, h0 + L * np.sin(b0)
            f1, f2 = np.arctan2(y1, z1), np.arctan2(y2, z2)
            iv.append((min(f1, f2), max(f1, f2)))
        iv.sort()
        merged = [list(iv[0])]
        for a, b in iv[1:]:
            if a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        blocked = sum(0.5 * (np.sin(b) - np.sin(a)) for a, b in merged)
        res.append(1.0 - blocked)
    return np.array(res)


def module_beam_shaded_fraction(lay: Layout, elev_deg, az_deg, array_az_deg=180.0):
    """Fraction of the module slant shaded by the row in front (sun in front of the module plane).

    Derived in the notes: shaded length from the lower edge = L - p*sin(ap)/sin(ap+beta),
    ap = profile (projected) solar elevation in the N-S plane.
    """
    el = np.radians(elev_deg)
    rel = np.radians(az_deg - array_az_deg)
    with np.errstate(divide="ignore", invalid="ignore"):
        ap = np.arctan2(np.tan(el), np.cos(rel))          # profile elevation, in (0, pi) when el>0
    b0 = lay.beta
    with np.errstate(divide="ignore", invalid="ignore"):
        f = 1 - (lay.pitch_m / lay.slant_m) * np.sin(ap) / np.sin(ap + b0)
    f = np.clip(np.nan_to_num(f, nan=1.0), 0.0, 1.0)
    return np.where(el > 0, f, 0.0)


def module_beam_shaded_fraction_raycast(lay: Layout, elev_deg, az_deg, n=2000):
    """Brute-force check: points along the back module, ray toward the sun, does it hit the front row?"""
    s = (np.arange(n) + 0.5) / n * lay.slant_m
    b0, p, L = lay.beta, lay.pitch_m, lay.slant_m
    t = sun_t(np.asarray(elev_deg, float), np.asarray(az_deg, float))
    py, pz = s * np.cos(b0), s * np.sin(b0)               # back row k=0, lower edge at origin
    # front row k=-1: (-p, 0) -> (-p + L cos b, L sin b) (heights relative to h0)
    out = []
    for tt in np.atleast_1d(t):
        # ray: (py + u*tt, pz + u), u>0 ; intersect with front segment param v in [0,1]
        # py + u*tt = -p + v L cos b ; pz + u = v L sin b
        denom = L * np.cos(b0) - tt * L * np.sin(b0)
        v = (py - pz * tt + p) / denom
        u = v * L * np.sin(b0) - pz
        out.append(np.mean((v >= 0) & (v <= 1) & (u > 0)))
    return np.array(out)


def module_sky_view(lay: Layout, n=400):
    """Isotropic sky view factor of the FRONT surface of an interior-row module, averaged over the slant.
    Unobstructed value is (1+cos beta)/2. The row in front blocks directions below its top edge."""
    s = (np.arange(n) + 0.5) / n * lay.slant_m
    b0, p, L = lay.beta, lay.pitch_m, lay.slant_m
    dy = (-p + L * np.cos(b0)) - s * np.cos(b0)
    dz = L * np.sin(b0) - s * np.sin(b0)
    phi_f = np.arctan2(dy, dz)            # direction to front-row top edge, from zenith (negative = south)
    f = 0.5 * (1 - np.sin(phi_f + b0))
    return float(np.mean(f))
