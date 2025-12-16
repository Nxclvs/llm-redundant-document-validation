from __future__ import annotations
from typing import Any, Dict, List, Optional

def merge_semantic_results(stage_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merges multiple semantic validation results into a single result.
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

    for r  in stage_results:
        issues.extend(r.get("issues", []) or [])
        c = r.get("comments")
        if c:
            comments.append(c)

    return {
        "status": status,
        "issues": issues,
        "comments": " | ".join(comments) if comments else "",
        "stages": stage_results,
    }


def multi_stage_semantic_validate(
        validators: List,
        image_path: str,
        extracted_data: Dict[str, Any],
) -> Dict[str, Any]:
    
    stage_results = []
    for v in validators:
        stage_results.append(v(image_path=image_path, extracted_data=extracted_data))

    merged = merge_semantic_results(stage_results)
    return merged