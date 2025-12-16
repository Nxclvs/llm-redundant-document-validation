from __future__ import annotations
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


def load_results(folder: Path) -> List[Dict[str, Any]]:
    results = []
    for p in folder.glob("*.json"):
        if p.name in ("metrics_summary.json",) or p.name.endswith("scheme.json"):
            continue
        if p.name == "index.jsonl":
            continue

        try:
            with p.open("r", encoding="utf-8") as f:
                results.append(json.load(f))
        except Exception:
            pass
    return results


def safe_get(d: Dict[str, Any], path: List[str], default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="results", help="Results folder")
    args = parser.parse_args()

    folder = Path(args.results) 
    if not folder.exists():
        print(f"Folder not found: {folder}")
        return
    
    res = load_results(folder)
    if not res:
        print(f"No result files")
        return
    
    status_counter = Counter()
    dur_a = []
    dur_b = []
    dur_sem = []
    cm_total = Counter()
    conflicts_by_field = defaultdict(Counter)
    conflicts_examples = defaultdict(list)

    for r in res:
        status_counter[r.get("final_status", "unknown")] += 1

        # durations
        da = safe_get(r, ["extraction", "extractor_a", "duration_seconds"])
        db = safe_get(r, ["extraction", "extractor_b", "duration_seconds"])
        ds = safe_get(r, ["semantic_validation", "duration_seconds"])

        if isinstance(da, (int, float)): dur_a.append(float(da))
        if isinstance(db, (int, float)): dur_b.append(float(db))
        if isinstance(ds, (int, float)): dur_sem.append(float(ds))

        # cross-model
        cm = r.get("cross_model_validation") or {}
        stats = cm.get("stats") or {}

        cm_total["errors"] += int(stats.get("errors", 0) or 0)
        cm_total["warnings"] += int(stats.get("warnings", 0) or 0)
        cm_total["infos"] += int(stats.get("infos", 0) or 0)

        for c in cm.get("conflicts", []) or []:
            field = c.get("field", "unknown")
            sev = c.get("severity", "warning")
            conflicts_by_field[field][sev] += 1
            if len(conflicts_examples[field]) < 3:     # only append if more than 3 times
                conflicts_examples[field].append(c.get("message", ""))

    def avg(xs):
        return round(sum(xs) / len(xs), 3) if xs else None
    
    metrics = {
        "num_documents": len(res),
        "final_status_distribution": dict(status_counter),
        "avg_duration_seconds": {
            "extractor_a": avg(dur_a),
            "extractor_b": avg(dur_b),
            "semantic_validation": avg(dur_sem),
        },
        "cross_model_totals": dict(cm_total),
        "top_conflict_fields": [
            {
                "field": f,
                "counts": dict(cnt),
                "examples": conflicts_examples[f],
            }
            for f, cnt in sorted(
                conflicts_by_field.items(),
                key=lambda kv: sum(kv[1].values()),
                reverse=True,
            )[:15]
        ],
    }

    out_json = folder / "metrics_summary.json"
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    out_csv = folder / "conflicts_by_field.csv"

    with out_csv.open("w", encoding="utf-8", newline='') as f:
        w = csv.writer(f)
        w.writerow(["field", "errors", "warnings", "infos"])
        for field, cnt in sorted(conflicts_by_field.items(), key=lambda kv: sum(kv[1].values()), reverse=True):
            w.writerow([field, cnt.get("error", 0), cnt.get("warning", 0), cnt.get("info", 0)])


    
    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_csv}")


if __name__ == "__main__":
    main()