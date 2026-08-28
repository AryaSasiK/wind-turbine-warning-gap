import os
import pandas as pd, numpy as np

a = pd.read_parquet(os.path.join(os.environ.get("WTWG_DERIVED", "wind-turbine-warning-gap-data/derived"), "attribution.parquet"))
t2 = a[a.T2_wide_grid].copy()
t2['cluster'] = t2.farm + '_' + t2.turbine_id.astype(str)
print('T2 events:', len(t2), 'clusters:', t2.cluster.nunique())

rng = np.random.default_rng(20260828)
B = 10_000

for rule, col in [('same', 'same_warn_72h'), ('any', 'any_warn_72h')]:
    w = t2[t2[col]].duration_h.values
    u = t2[~t2[col]].duration_h.values
    obs = np.median(u) - np.median(w)
    print(f'{rule}: med warned {np.median(w):.3f} h, unwarned {np.median(u):.3f} h, diff {obs:.3f}')
    clusters = t2.cluster.unique()
    groups = {c: g for c, g in t2.groupby('cluster')}
    diffs = np.empty(B); bad = 0
    for b in range(B):
        pick = rng.choice(clusters, size=len(clusters), replace=True)
        parts = []
        for c in pick:
            g = groups[c]
            idx = rng.integers(0, len(g), len(g))
            parts.append(g.iloc[idx])
        s = pd.concat(parts)
        wv = s[s[col]].duration_h.values
        uv = s[~s[col]].duration_h.values
        if len(wv) == 0 or len(uv) == 0:
            bad += 1; diffs[b] = np.nan; continue
        diffs[b] = np.median(uv) - np.median(wv)
    d = diffs[~np.isnan(diffs)]
    lo, hi = np.percentile(d, [2.5, 97.5])
    p_le0 = (d <= 0).mean()
    print(f'  bootstrap 95% CI on median diff: [{lo:.3f}, {hi:.3f}] h; frac<=0: {p_le0:.4f}; degenerate reps: {bad}')
