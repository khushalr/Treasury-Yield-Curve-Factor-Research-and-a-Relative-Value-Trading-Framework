"""Descriptive rolling factor stability; no prediction or trading claims."""
import numpy as np
import pandas as pd
from .pca_model import fit_rolling_pca


def loading_similarity(previous, current):
    """Sign-invariant PC alignment and worst principal-angle cosine.

    Subspace comparison remains meaningful when nearby eigenvalues swap PCs.
    """
    a, b = np.asarray(previous, dtype=float), np.asarray(current, dtype=float)
    if a.shape != b.shape or a.ndim != 2 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Finite, equal loading shapes required")
    if not np.allclose(a.T @ a, np.eye(a.shape[1]), atol=1e-6) or not np.allclose(b.T @ b, np.eye(b.shape[1]), atol=1e-6):
        raise ValueError("Orthonormal PCA columns required")
    cosines = np.clip(np.abs(np.sum(a*b, axis=0)), 0, 1)
    subspace = np.linalg.svd(a.T @ b, compute_uv=False)
    return cosines, float(np.clip(subspace.min(), 0, 1))


def stability_panel(changes, windows=(63, 126, 252)):
    if not changes.index.is_unique or not changes.index.is_monotonic_increasing:
        raise ValueError("Unique ordered observations required")
    if not np.isfinite(changes.to_numpy()).all():
        raise ValueError("Finite changes required")
    rows = []
    for window in windows:
        result = fit_rolling_pca(changes, window)
        previous = None
        for date, frame in result.loadings.items():
            current = frame.to_numpy()
            if previous is not None:
                cosine, subspace = loading_similarity(previous, current)
                rows.append({"date": date, "window": window,
                             "era": f"{date.year//10*10}s",
                             "pc1_cosine": cosine[0], "pc2_cosine": cosine[1],
                             "pc3_cosine": cosine[2], "subspace_min_cosine": subspace,
                             "pc1_variance": result.explained_variance.loc[date, "PC1"]})
            previous = current
    return pd.DataFrame(rows)
