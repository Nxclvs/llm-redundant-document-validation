# scripts/metrics.py

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# We use your registry to know expected schema fields.
from framework.schemes.registry import get_schema_for_type



def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def flatten_dict(d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten_dict(v, key))
        else:
            out[key] = v
    return out



# Normalization

_NUM_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)")


def _norm_str(x: Any) -> str:
    if x is None:
        return ""
    s = str(x)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = "\n".join(line.strip() for line in s.split("\n"))
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def _try_parse_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    s = _norm_str(x)
    if not s:
        return None
    m = _NUM_RE.search(s.replace(".", "").replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except Exception:
        return None


def values_equal(gt_val: Any, ext_val: Any) -> bool:
    """
    Robust comparison:
    - float: compare numerically 
    - dict: flatten compare 
    - list: compare length + per-element dict-like compare best-effort
    - else: compare normalized strings
    """
    if isinstance(gt_val, (int, float)) and not isinstance(gt_val, bool):
        gt_f = float(gt_val)
        ext_f = _try_parse_float(ext_val)
        if ext_f is None:
            return False
        return abs(gt_f - ext_f) <= 1e-2

    if isinstance(gt_val, dict):
        if not isinstance(ext_val, dict):
            return False
        gt_flat = flatten_dict(gt_val)
        ext_flat = flatten_dict(ext_val)
        for k, g in gt_flat.items():
            if k not in ext_flat:
                return False
            if not values_equal(g, ext_flat.get(k)):
                return False
        return True

    if isinstance(gt_val, list):
        if not isinstance(ext_val, list):
            return False
        if len(gt_val) != len(ext_val):
            return False
        for g_item, e_item in zip(gt_val, ext_val):
            if isinstance(g_item, dict) and isinstance(e_item, dict):
                if not values_equal(g_item, e_item):
                    return False
            else:
                if _norm_str(g_item) != _norm_str(e_item):
                    return False
        return True

    return _norm_str(gt_val) == _norm_str(ext_val)



# Ground Truth Loader

def load_ground_truth(gt_root: Path) -> Dict[str, Dict[str, Any]]:
    """
    Loads GT from:
      ground_truth/<doc_type>/<filename>.json

    Returns map:
      { "INV_001": {...}, "REQ_002": {...}, ... }
    """
    gt_map: Dict[str, Dict[str, Any]] = {}
    for doc_type_dir in gt_root.iterdir():
        if not doc_type_dir.is_dir():
            continue
        for p in doc_type_dir.glob("*.json"):
            gt_map[p.stem] = load_json(p)
    return gt_map



# Metrics

def compute_field_accuracy(extracted: Dict[str, Any], ground_truth: Dict[str, Any]) -> Tuple[float, int, int]:
    """
    Accuracy over GT fields (the truth).
    Returns: (accuracy, correct_fields, total_fields)
    """
    correct = 0
    total = 0

    for field, gt_val in ground_truth.items():
        total += 1
        ext_val = extracted.get(field, None)
        if values_equal(gt_val, ext_val):
            correct += 1

    acc = correct / total if total else 1.0
    return acc, correct, total


def compute_schema_coverages(doc_type: str, extracted: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, float]:
    """
    Measures:
    - GT coverage relative to schema keys
    - Extraction coverage relative to schema keys
    (Top-level keys only; your schema is top-level FieldSpec dict.)
    """
    try:
        schema = get_schema_for_type(doc_type)
        schema_keys = set(schema.keys())
    except Exception:
        schema_keys = set()

    if not schema_keys:
        return {
            "gt_schema_coverage": 0.0,
            "extraction_schema_coverage": 0.0,
            "schema_num_keys": 0,
        }

    gt_keys = set(ground_truth.keys())
    ext_keys = set(extracted.keys())

    gt_cov = len(gt_keys & schema_keys) / len(schema_keys)
    ext_cov = len(ext_keys & schema_keys) / len(schema_keys)

    return {
        "gt_schema_coverage": round(gt_cov, 4),
        "extraction_schema_coverage": round(ext_cov, 4),
        "schema_num_keys": len(schema_keys),
    }


def compute_semantic_stability(semantic_result: Dict[str, Any]) -> float:
    stages = semantic_result.get("stages", [])
    if len(stages) < 2:
        return 1.0
    statuses = [s.get("status") for s in stages]
    same = sum(1 for s in statuses if s == statuses[0])
    return same / len(statuses)


def compute_audit_readiness(result: Dict[str, Any]) -> bool:
    schema_ok = result.get("schema_validation", {}).get("is_valid", True)

    rules = result.get("rule_validation", {})
    rule_errors = any((v.get("severity") or "").lower() == "error" for v in rules.get("violations", []))

    semantic = result.get("semantic_validation", {})
    semantic_ok = semantic.get("status") != "invalid"

    cross = result.get("cross_model_validation")
    cross_ok = True
    if cross:
        cross_ok = cross.get("is_consistent", True)

    return schema_ok and not rule_errors and semantic_ok and cross_ok


def evaluate_experiment(experiment_dir: Path, ground_truth: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    index_path = experiment_dir / "index.jsonl"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing index.jsonl in {experiment_dir}")

    docs: List[Dict[str, Any]] = []
    with index_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            docs.append(json.loads(line))

    metrics: Dict[str, Any] = {
        "experiment": experiment_dir.name,
        "num_documents": len(docs),
        "documents": [],
        "summary": {},
    }

    acc_sum = 0.0
    audit_ready_count = 0
    semantic_stability_sum = 0.0
    gt_cov_sum = 0.0
    ext_cov_sum = 0.0
    cov_count = 0

    for entry in docs:
        result_path = Path(entry["result_file"])
        result = load_json(result_path)

        doc_name = Path(entry["document"]["name"]).stem
        doc_type = (entry.get("doc_type") or "").strip().lower() or "unknown"

        gt = ground_truth.get(doc_name, {})
        extracted = result.get("extraction", {}).get("data", {}) or {}

        if gt:
            acc, correct, total = compute_field_accuracy(extracted, gt)
        else:
            acc, correct, total = 0.0, 0, 0

        semantic = result.get("semantic_validation", {}) or {}
        stability = compute_semantic_stability(semantic)

        audit_ok = compute_audit_readiness(result)

        cover = compute_schema_coverages(doc_type, extracted, gt)
        if cover.get("schema_num_keys", 0) > 0:
            gt_cov_sum += cover["gt_schema_coverage"]
            ext_cov_sum += cover["extraction_schema_coverage"]
            cov_count += 1

        acc_sum += acc
        semantic_stability_sum += stability
        if audit_ok:
            audit_ready_count += 1

        metrics["documents"].append({
            "document": doc_name,
            "doc_type": doc_type,
            "field_accuracy": round(acc, 4),
            "correct_fields": correct,
            "total_fields": total,
            "semantic_status": semantic.get("status"),
            "semantic_stability": round(stability, 4),
            "audit_ready": audit_ok,
            "final_status": result.get("final_status"),
            **cover,
        })

    n = len(docs) or 1
    cov_n = cov_count or 1

    metrics["summary"] = {
        "mean_field_accuracy": round(acc_sum / n, 4),
        "audit_readiness_rate": round(audit_ready_count / n, 4),
        "mean_semantic_stability": round(semantic_stability_sum / n, 4),
        "mean_gt_schema_coverage": round(gt_cov_sum / cov_n, 4),
        "mean_extraction_schema_coverage": round(ext_cov_sum / cov_n, 4),
    }

    return metrics


def evaluate_all(results_root: Path, ground_truth_root: Path, output_path: Path) -> Dict[str, Any]:
    gt = load_ground_truth(ground_truth_root)

    all_metrics: Dict[str, Any] = {
        "dataset": str(ground_truth_root),
        "experiments": [],
        "comparison": {},
    }

    for exp_dir in results_root.iterdir():
        if not exp_dir.is_dir():
            continue
        try:
            m = evaluate_experiment(exp_dir, gt)
            all_metrics["experiments"].append(m)
        except Exception as e:
            print(f"Skipping {exp_dir.name}: {e}")

    ranked = sorted(
        all_metrics["experiments"],
        key=lambda x: x["summary"]["mean_field_accuracy"],
        reverse=True,
    )

    all_metrics["comparison"]["ranking_by_accuracy"] = [
        {
            "experiment": e["experiment"],
            "mean_field_accuracy": e["summary"]["mean_field_accuracy"],
            "audit_readiness_rate": e["summary"]["audit_readiness_rate"],
            "mean_semantic_stability": e["summary"]["mean_semantic_stability"],
            "mean_gt_schema_coverage": e["summary"]["mean_gt_schema_coverage"],
            "mean_extraction_schema_coverage": e["summary"]["mean_extraction_schema_coverage"],
        }
        for e in ranked
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2, ensure_ascii=False)

    return all_metrics
