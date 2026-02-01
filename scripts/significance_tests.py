# scripts/significance_tests.py
from __future__ import annotations

import argparse
import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import numpy as np

# SciPy is required
from scipy import stats


# ---------------------------
# JSON / NumPy safety helpers
# ---------------------------

def py(x: Any) -> Any:
    """Convert numpy/scipy scalar types to native Python types (JSON-safe)."""
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, (np.ndarray,)):
        return [py(v) for v in x.tolist()]
    return x


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------
# Metrics extraction
# ---------------------------

def extract_metric_vectors(metrics_summary: Dict[str, Any]) -> Dict[str, Dict[str, List[float]]]:
    """
    Returns:
      {
        "accuracy": { "EXP_A": [...], "EXP_B": [...] },
        "audit_ready": { ... },
        "semantic_stability": { ... },
      }
    Expected per experiment:
      metrics_summary["experiments"][i]["documents"][] entries contain:
        - field_accuracy (float)
        - audit_ready (bool)
        - semantic_stability (float)
    """
    by_metric: Dict[str, Dict[str, List[float]]] = {
        "accuracy": {},
        "audit_ready": {},
        "semantic_stability": {},
    }

    for exp in metrics_summary.get("experiments", []):
        exp_name = exp.get("experiment") or exp.get("name") or "unknown_experiment"
        docs = exp.get("documents", []) or []

        acc = []
        audit = []
        stab = []

        for d in docs:
            # accuracy
            if "field_accuracy" in d and d["field_accuracy"] is not None:
                acc.append(float(d["field_accuracy"]))

            # audit readiness (bool -> 0/1)
            if "audit_ready" in d and d["audit_ready"] is not None:
                audit.append(float(1.0 if bool(d["audit_ready"]) else 0.0))

            # semantic stability
            if "semantic_stability" in d and d["semantic_stability"] is not None:
                stab.append(float(d["semantic_stability"]))

        by_metric["accuracy"][exp_name] = acc
        by_metric["audit_ready"][exp_name] = audit
        by_metric["semantic_stability"][exp_name] = stab

    return by_metric


# ---------------------------
# Stats utilities
# ---------------------------

def safe_shapiro(x: List[float]) -> Optional[float]:
    """
    Shapiro-Wilk test p-value for normality.
    Returns None if sample size unsuitable.
    """
    n = len(x)
    if n < 3:
        return None
    # Shapiro in SciPy is typically recommended up to 5000
    if n > 5000:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, p = stats.shapiro(x)
        return float(p)
    except Exception:
        return None


def cohens_d(x: List[float], y: List[float]) -> float:
    """Cohen's d with pooled std (classic)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    nx = x.size
    ny = y.size
    if nx < 2 or ny < 2:
        return 0.0
    vx = x.var(ddof=1)
    vy = y.var(ddof=1)
    pooled = ((nx - 1) * vx + (ny - 1) * vy) / (nx + ny - 2)
    if pooled <= 0:
        return 0.0
    return float((x.mean() - y.mean()) / math.sqrt(pooled))


def rank_biserial_from_u(u_stat: float, nx: int, ny: int) -> float:
    """
    Rank-biserial correlation r_rb derived from Mann-Whitney U.
    r_rb = 1 - (2U)/(nx*ny)   (depending on U definition; we map to [-1,1])
    Using scipy's U for x vs y (U counts wins of x over y).
    """
    if nx <= 0 or ny <= 0:
        return 0.0
    r = 1.0 - (2.0 * u_stat) / (nx * ny)
    # clamp
    return float(max(-1.0, min(1.0, r)))


def choose_test(x: List[float], y: List[float], alpha_normality: float = 0.05) -> Tuple[str, Dict[str, Any]]:
    """
    Decide between t-test and Mann-Whitney U test.
    We use normality checks as a heuristic.
    """
    info: Dict[str, Any] = {}

    nx, ny = len(x), len(y)
    info["n_x"] = nx
    info["n_y"] = ny

    pnx = safe_shapiro(x)
    pny = safe_shapiro(y)
    info["shapiro_p_x"] = pnx
    info["shapiro_p_y"] = pny

    normal_x = (pnx is not None and pnx >= alpha_normality)
    normal_y = (pny is not None and pny >= alpha_normality)

    info["normal_x"] = normal_x
    info["normal_y"] = normal_y

    # If too few points -> use non-parametric
    if nx < 3 or ny < 3:
        return "mannwhitney", info

    # If both look normal -> use Welch t-test (robust against unequal variances)
    if normal_x and normal_y:
        return "welch_t", info

    return "mannwhitney", info


def compare(x: List[float], y: List[float], alpha: float = 0.05) -> Dict[str, Any]:
    """
    Performs chosen test + effect sizes.
    Returns JSON-safe dict.
    """
    test_name, info = choose_test(x, y)
    nx, ny = len(x), len(y)

    out: Dict[str, Any] = {
        "test": test_name,
        "alpha": float(alpha),
        **info,
        "warnings": [],
    }

    # Capture warnings (e.g., catastrophic cancellation)
    with warnings.catch_warnings(record=True) as wlog:
        warnings.simplefilter("always")

        if test_name == "welch_t":
            # Welch's t-test
            stat, p = stats.ttest_ind(x, y, equal_var=False, nan_policy="omit")
            out["stat"] = float(stat)
            out["p"] = float(p)
            out["effect_cohens_d"] = float(cohens_d(x, y))
            out["effect_rank_biserial"] = 0.0  # not applicable
        else:
            # Mann-Whitney U (two-sided)
            # Use "auto" method if available
            try:
                res = stats.mannwhitneyu(x, y, alternative="two-sided", method="auto")
                u_stat, p = res.statistic, res.pvalue
            except TypeError:
                # older SciPy without method=
                u_stat, p = stats.mannwhitneyu(x, y, alternative="two-sided")

            out["stat"] = float(u_stat)
            out["p"] = float(p)
            out["effect_cohens_d"] = float(cohens_d(x, y))  # still a helpful standardized diff
            out["effect_rank_biserial"] = float(rank_biserial_from_u(float(u_stat), nx, ny))

    out["significant"] = bool(out["p"] < alpha)

    # store warnings text (if any)
    if wlog:
        out["warnings"] = [str(w.message) for w in wlog]

    # ensure JSON safety
    return {k: py(v) for k, v in out.items()}


# ---------------------------
# Multiple test correction
# ---------------------------

def holm_correction(pvals: List[float]) -> List[float]:
    """
    Holm-Bonferroni adjusted p-values.
    Returns adjusted p in original order.
    """
    m = len(pvals)
    if m == 0:
        return []

    indexed = sorted(enumerate(pvals), key=lambda t: t[1])
    adjusted = [0.0] * m

    # Holm step-down
    prev = 0.0
    for rank, (idx, p) in enumerate(indexed, start=1):
        adj = (m - rank + 1) * p
        adj = max(adj, prev)  # ensure monotonicity
        adj = min(adj, 1.0)
        adjusted[idx] = adj
        prev = adj

    return adjusted


# ---------------------------
# Pairwise runner
# ---------------------------

def pairwise_tests(
    metric_vectors: Dict[str, Dict[str, List[float]]],
    alpha: float,
) -> Dict[str, Any]:
    """
    Returns:
      {
        "accuracy": { "comparisons": [...], "correction": "holm", ... },
        ...
      }
    """
    results: Dict[str, Any] = {}

    for metric, exp_map in metric_vectors.items():
        exp_names = sorted(exp_map.keys())
        comparisons: List[Dict[str, Any]] = []

        raw_ps: List[float] = []

        # pairwise
        for i in range(len(exp_names)):
            for j in range(i + 1, len(exp_names)):
                a = exp_names[i]
                b = exp_names[j]
                x = exp_map[a]
                y = exp_map[b]

                if len(x) == 0 or len(y) == 0:
                    comp = {
                        "metric": metric,
                        "a": a,
                        "b": b,
                        "skipped": True,
                        "reason": "empty_vector",
                    }
                    comparisons.append(comp)
                    continue

                comp = {
                    "metric": metric,
                    "a": a,
                    "b": b,
                    "skipped": False,
                    "result": compare(x, y, alpha=alpha),
                    "means": {"a": float(np.mean(x)), "b": float(np.mean(y))},
                    "stds": {"a": float(np.std(x, ddof=1)) if len(x) > 1 else 0.0,
                             "b": float(np.std(y, ddof=1)) if len(y) > 1 else 0.0},
                }
                comparisons.append(comp)
                raw_ps.append(float(comp["result"]["p"]))

        # correction only for non-skipped comps
        p_adj = holm_correction(raw_ps)
        k = 0
        for comp in comparisons:
            if comp.get("skipped"):
                continue
            comp["result"]["p_holm"] = float(p_adj[k])
            comp["result"]["significant_holm"] = bool(p_adj[k] < alpha)
            k += 1

        results[metric] = {
            "metric": metric,
            "alpha": float(alpha),
            "correction": "holm",
            "experiments": exp_names,
            "comparisons": [{kk: py(vv) for kk, vv in c.items()} for c in comparisons],
        }

    return results


# ---------------------------
# Main entry point
# ---------------------------

def run():
    parser = argparse.ArgumentParser(description="Pairwise significance tests for experiment metrics.")
    parser.add_argument(
        "--metrics",
        default="results/metrics_summary.json",
        help="Path to metrics_summary.json (default: results/metrics_summary.json)",
    )
    parser.add_argument(
        "--out",
        default="results/significance_tests.json",
        help="Output JSON path (default: results/significance_tests.json)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance level (default: 0.05)",
    )
    args = parser.parse_args()

    metrics_path = Path(args.metrics)
    out_path = Path(args.out)

    if not metrics_path.exists():
        raise FileNotFoundError(f"Metrics file not found: {metrics_path}")

    metrics_summary = load_json(metrics_path)
    metric_vectors = extract_metric_vectors(metrics_summary)

    # Only keep metrics where we have at least 2 experiments with data
    metric_vectors = {
        m: emap
        for m, emap in metric_vectors.items()
        if sum(1 for _k, v in emap.items() if len(v) > 0) >= 2
    }

    results = {
        "source_metrics": str(metrics_path.resolve()),
        "generated_at": py(np.datetime64("now").astype(str)),
        "alpha": float(args.alpha),
        "metrics": pairwise_tests(metric_vectors, alpha=float(args.alpha)),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"✅ Wrote significance results: {out_path.resolve()}")


if __name__ == "__main__":
    run()
