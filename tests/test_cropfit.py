"""Parameter-recovery test for the REML mixed model (simulated data, known truth). Not a crop result."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np
from agripv.cropfit import fit_lmm, strip_yield

rng = np.random.default_rng(7)
truth = {"A": (-0.10, -0.40), "B": (0.15, -0.60), "C": (-0.60, -0.20)}
G_true = np.array([[0.04, -0.01], [-0.01, 0.03]]); s_true = 0.03
rows = []
for loc in range(60):
    u = rng.multivariate_normal([0, 0], G_true)
    for g, (a, b) in truth.items():
        if rng.random() < 0.6:
            for r in rng.uniform(0.05, 0.75, rng.integers(2, 5)):
                y = (a + u[0]) * r + (b + u[1]) * r ** 2 + rng.normal(0, s_true)
                rows.append((r, y, g, f"L{loc}"))
r, y, g, l = map(np.array, zip(*rows))
res = fit_lmm(r, y, g, l)
ok = res.converged
print(f"n = {len(r)}, converged = {res.converged}, sigma = {np.sqrt(res.sigma2):.4f} (true {s_true})")
for grp, (a, b) in truth.items():
    ah, bh = res.coef(grp)
    i = res.groups.index(grp)
    se = np.sqrt(np.diag(res.cov_beta))[2 * i:2 * i + 2]
    inside = abs(ah - a) < 3 * se[0] and abs(bh - b) < 3 * se[1]
    ok &= inside
    print(f"group {grp}: a {ah:+.3f} (true {a:+.3f}, se {se[0]:.3f})  b {bh:+.3f} (true {b:+.3f}, se {se[1]:.3f})  within 3 se: {inside}")
print("G estimate:\n", np.round(res.G, 4), "\nG true:\n", G_true)
ok &= np.allclose(res.G, G_true, atol=0.02)
m, lo, hi, ex = strip_yield(res, "A", np.array([0.1, 0.3, 0.5]))
print(f"strip_yield demo (group A): mean {m:.3f}, band {lo:.3f}-{hi:.3f}, extrapolated share {ex:.2f}")
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
