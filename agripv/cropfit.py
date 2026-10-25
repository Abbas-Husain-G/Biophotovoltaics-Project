"""M4 - Crop response to shade, following the model form of Laub et al. (2022, Agron. Sustain. Dev. 42:51):

    log10(relative yield %) - 2 = a_g * RSR + b_g * RSR^2 + (u1_loc * RSR + u2_loc * RSR^2) + e

  quad="common" (Laub et al.'s final model after backward elimination of the non-significant
  RSR^2 x crop-type interaction): b_g = b for every group. quad="group": one b_g per group.

- RSR: relative solar radiation reduction vs. the unshaded control (fraction 0..1)
- a_g, b_g: fixed effects per crop group (no intercept: 0 % shade = 100 % yield by construction)
- (u1, u2) ~ N(0, G): random linear and quadratic slopes by location (G: 2x2, unstructured)
- e ~ N(0, sigma^2)

Fitted by REML, implemented here with numpy/scipy because statsmodels is unavailable in this
workspace. Validated by parameter recovery on simulated data (tests/test_cropfit.py) and, once the
Zenodo data are available, by reproducing Laub et al.'s published predictions (Phase 4 gate).
"""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import minimize


@dataclass
class LMMResult:
    groups: list
    beta: np.ndarray          # (2*n_groups,) [a_g1, b_g1, a_g2, b_g2, ...]
    cov_beta: np.ndarray
    G: np.ndarray             # random-slope covariance (2x2)
    sigma2: float
    n_obs: dict
    n_loc: dict
    rsr_range: dict
    converged: bool
    quad: str = "group"

    def _cols(self, group):
        i = self.groups.index(group)
        return [i, len(self.groups)] if self.quad == "common" else [2 * i, 2 * i + 1]

    def coef(self, group):
        ia, ib = self._cols(group)
        return self.beta[ia], self.beta[ib]

    def predict(self, group, rsr, interval="confidence", z=1.96):
        """Relative yield (fraction of control) with a 95 % band.
        confidence: uncertainty of the mean curve; prediction: adds between-location slope variance."""
        c = self._cols(group)
        r = np.atleast_1d(np.asarray(rsr, float))
        X = np.column_stack([r, r ** 2])
        b = self.beta[c]
        C = self.cov_beta[np.ix_(c, c)]
        mu = X @ b
        var = np.einsum("ij,jk,ik->i", X, C, X)
        if interval == "prediction":
            var = var + np.einsum("ij,jk,ik->i", X, self.G, X)
        sd = np.sqrt(np.maximum(var, 0))
        f = lambda v: 10 ** v
        return f(mu), f(mu - z * sd), f(mu + z * sd)


def _design(rsr, group, groups, quad="group"):
    n, k = len(rsr), len(groups)
    gi = np.array([groups.index(g) for g in group])
    if quad == "common":
        X = np.zeros((n, k + 1))
        X[np.arange(n), gi] = rsr
        X[:, k] = rsr ** 2
    else:
        X = np.zeros((n, 2 * k))
        X[np.arange(n), 2 * gi] = rsr
        X[np.arange(n), 2 * gi + 1] = rsr ** 2
    Z = np.column_stack([rsr, rsr ** 2])
    return X, Z


def fit_lmm(rsr, log_ratio, group, location, groups=None, quad="group"):
    """rsr: fraction 0..1; log_ratio: log10(relative yield %) - 2; group, location: labels."""
    rsr = np.asarray(rsr, float); y = np.asarray(log_ratio, float)
    group = np.asarray(group); location = np.asarray(location)
    groups = list(groups) if groups is not None else sorted(set(group))
    keep = np.isin(group, groups) & np.isfinite(rsr) & np.isfinite(y)
    rsr, y, group, location = rsr[keep], y[keep], group[keep], location[keep]
    X, Z = _design(rsr, group, groups, quad)
    locs = sorted(set(location))
    idx = [np.where(location == l)[0] for l in locs]
    p = X.shape[1]

    def unpack(th):
        L = np.array([[np.exp(th[0]), 0.0], [th[1], np.exp(th[2])]])
        return L @ L.T, np.exp(2 * th[3])

    def reml(th):
        G, s2 = unpack(th)
        XtVX = np.zeros((p, p)); XtVy = np.zeros(p); logdet = 0.0; parts = []
        for ix in idx:
            Zi, Xi, yi = Z[ix], X[ix], y[ix]
            V = Zi @ G @ Zi.T + s2 * np.eye(len(ix))
            c = np.linalg.cholesky(V)
            logdet += 2 * np.log(np.diag(c)).sum()
            Vi_X = np.linalg.solve(V, Xi); Vi_y = np.linalg.solve(V, yi)
            XtVX += Xi.T @ Vi_X; XtVy += Xi.T @ Vi_y
            parts.append((Xi, yi, Vi_X, Vi_y))
        XtVX_r = XtVX + 1e-12 * np.eye(p)
        beta = np.linalg.solve(XtVX_r, XtVy)
        quad = sum(yi @ Vi_y - 2 * beta @ (Xi.T @ Vi_y) + beta @ (Xi.T @ Vi_X) @ beta
                   for Xi, yi, Vi_X, Vi_y in parts)
        sign, ld_x = np.linalg.slogdet(XtVX_r)
        return 0.5 * (logdet + ld_x + quad), beta, XtVX_r

    # start: OLS residual variance
    b0 = np.linalg.lstsq(X, y, rcond=None)[0]
    s0 = np.var(y - X @ b0) + 1e-6
    th0 = np.array([np.log(0.1), 0.0, np.log(0.1), 0.5 * np.log(s0)])
    opt = minimize(lambda th: reml(th)[0], th0, method="Nelder-Mead",
                   options=dict(maxiter=20000, xatol=1e-7, fatol=1e-9))
    _, beta, XtVX = reml(opt.x)
    G, s2 = unpack(opt.x)
    cov = np.linalg.inv(XtVX)
    n_obs = {g: int((group == g).sum()) for g in groups}
    n_loc = {g: len(set(location[group == g])) for g in groups}
    rng_ = {g: (float(rsr[group == g].min()), float(rsr[group == g].max())) for g in groups if (group == g).any()}
    return LMMResult(groups, beta, cov, G, float(s2), n_obs, n_loc, rng_, bool(opt.success), quad)


def strip_yield(result, group, strip_rsr, interval="prediction"):
    """Apply the curve strip by strip (avoids averaging RSR before a non-linear curve).
    Returns mean relative yield and band over the cropped strips, plus the extrapolated share."""
    mu, lo, hi = result.predict(group, strip_rsr, interval)
    rmin, rmax = result.rsr_range[group]
    extrap = np.mean((np.asarray(strip_rsr) > rmax) | (np.asarray(strip_rsr) < 0))
    return float(mu.mean()), float(lo.mean()), float(hi.mean()), float(extrap)
