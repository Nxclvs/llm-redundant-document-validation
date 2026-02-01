# framework/validation/multi_stage_validation.py

from __future__ import annotations
from typing import Any, Dict, List, Callable


def _unique_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def merge_semantic_results(stage_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merges multiple semantic validation results into a single result.

    Adds:
      - duration_seconds_total
      - models_used
      - providers_used
      - stats: errors/warnings/infos derived from issue severities
    """
    statuses = [r.get("status", "uncertain") for r in stage_results]

    if any(s == "invalid" for s in statuses):
        status = "invalid"
    elif any(s in ("parse_error", "uncertain") for s in statuses):
        status = "uncertain"
    else:
        status = "valid"

    issues: List[Dict[str, Any]] = []
    comments = []

    duration_total = 0.0
    models_used: List[str] = []
    providers_used: List[str] = []

    for r in stage_results:
        issues.extend(r.get("issues", []) or [])

        c = r.get("comments")
        if c:
            comments.append(c)

        d = r.get("duration_seconds")
        if isinstance(d, (int, float)):
            duration_total += float(d)

        m = r.get("model")
        if m:
            models_used.append(str(m))

        p = r.get("provider")
        if p:
            providers_used.append(str(p))

    # severity stats
    errors = warnings = infos = 0
    for it in issues:
        sev = (it.get("severity") or "warning").lower()
        if sev == "error":
            errors += 1
        elif sev == "warning":
            warnings += 1
        else:
            infos += 1

    return {
        "status": status,
        "issues": issues,
        "comments": " | ".join(comments) if comments else "",
        "stages": stage_results,
        "duration_seconds_total": round(duration_total, 3),
        "models_used": _unique_preserve_order(models_used),
        "providers_used": _unique_preserve_order(providers_used),
        "stats": {"errors": errors, "warnings": warnings, "infos": infos},
    }


def multi_stage_semantic_validate(
    validators: List[Callable[..., Dict[str, Any]]],
    image_path: str,
    extracted_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    validators: list of callables(image_path=..., extracted_data=...) -> semantic_result
    """

    if not validators:
        return {
            "status": "skipped",
            "issues": [],
            "comments": "No semantic validators configured.",
            "stages": [],
            "duration_seconds_total": 0.0,
            "models_used": [],
            "providers_used": [],
            "stats": {"errors": 0, "warnings": 0, "infos": 0},
        }


    stage_results = []
    for v in validators:
        stage_results.append(v(image_path=image_path, extracted_data=extracted_data))

    return merge_semantic_results(stage_results)
 