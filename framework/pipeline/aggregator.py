import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def aggregate_validation(
    image_path: str,
    extraction_result: Dict[str, Any],
    schema_result: Dict[str, Any],
    rule_result: Dict[str, Any],
    semantic_result: Dict[str, Any],
    cross_model_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    """
    Aggregates all validating result into a final result

    Expects: 
        - extraction_result: output from extractor
        - rule_result: output of validate_rules(...)
        - semantic_result: output of semantic_validate(...)
        - cross_model_result: optional result of a cross-model-check

    Returns:
        {
            "document: {
                "path: str,
                "name: str
            },
            final_status: "valid" | "review_needed" | "invalid",
            "summary" : str,
            "extraction": {...},
            "rule_validation": {...},
            "semantic_validation": {...},
            "cross_model_validation": {...} | None,
            "created_at": iso_timestamp
        }
    """
    # Base information
    path_obj = Path(image_path)
    doc_name = path_obj.name

    # Signals
    rules_valid = rule_result.get("is_valid", False)
    rule_violations = rule_result.get("violations", [])

    # Scheme
    schema_violations = schema_result.get("violations", [])
    schema_errors = 0
    schema_warnings = 0
    schema_infos = 0

    for v in schema_violations:
        sev = v.get("severity", "error")
        if sev == "error":
            schema_errors += 1
        elif sev == "warning":
            schema_warnings += 1
        else:
            schema_infos += 1


    # Violation count with severity
    rule_errors = 0
    rule_warnings = 0
    rule_infos = 0

    for v in rule_violations:
        sev = v.get("severity", "error")
        if sev == "error":
            rule_errors += 1
        elif sev == "warning":
            rule_warnings += 1
        else:
            rule_infos += 1


    sem_status = semantic_result.get("status", "uncertain")
    sem_issues = semantic_result.get("issues", [])

    # Issues count with severity
    num_errors = 0
    num_warnings = 0
    num_infos = 0

    for issue in sem_issues:
        sev = issue.get("severity", "warning")
        if sev == "error":
            num_errors += 1
        elif sev == "warning":
            num_warnings += 1
        else:
            num_infos += 1

    # cross-model-redundancy
    cm_errors = cm_warnings = cm_infos = 0
    cm_conflicts = []

    if cross_model_result is not None:
        cm_conflicts = cross_model_result.get("conflicts", [])
        stats = cross_model_result.get("stats", {})
        cm_errors = stats.get("errors", 0)
        cm_warnings = stats.get("warnings", 0)
        cm_infos = stats.get("infos", 0)

    # final status
    if sem_status == "invalid" or num_errors > 0 or rule_errors > 0 or schema_errors > 0 or cm_errors > 0:
        final_status = "invalid"
    elif sem_status in ("parse_error", "uncertain") or num_warnings > 0 or rule_warnings > 0 or schema_warnings > 0 or cm_warnings > 0:
        final_status = "review_needed"
    else:
        final_status = "valid"



    # build up summary
    num_rule_violations = rule_errors + rule_warnings
    num_sem_issues = num_errors + num_warnings  


    summary_parts = []

    # 1) document
    summary_parts.append(f"Dokument: {doc_name}")

    # 2) scheme validation
    summary_parts.append(
        f"Schema-Validation: Errors={schema_errors}, Warnings={schema_warnings}, Infos={schema_infos}"
    )

    # 3) rule based validation
    summary_parts.append(
        f"Rule-Validation (Extraktion): "
        f"Errors={rule_errors}, Warnings={rule_warnings}, Infos={rule_infos}"
    )

    # 4) semantic validation
    summary_parts.append(
        f"Semantische Validation: "
        f"Status={sem_status}, "
        f"Errors={num_errors}, Warnings={num_warnings}, Infos={num_infos}"
    )
    
    # 5) cross-model validation
    if cross_model_result is not None:
        summary_parts.append(
            f"Cross-Model-Validation: Errors={cm_errors}, Warnings={cm_warnings}, Infos={cm_infos}"
        )


    # 6) final result
    summary_parts.append(f"Finaler Status: {final_status}")

    summary = " | ".join(summary_parts)


    aggregated = {
        "document": {
            "path": str(path_obj),
            "name": doc_name,
        },
        "final_status": final_status,
        "summary": summary,
        "extraction": extraction_result,
        "schema_validation": schema_result,
        "rule_validation": rule_result,
        "semantic_validation": semantic_result,
        "cross_model_validation": cross_model_result,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    return aggregated

def save_result_to_file(
    result: Dict[str, Any],
    output_dir: str = "results",
    filename: Optional[str] = None, 
) -> str:
    """
    saves the aggregation output as JSON file
    - output_dir gets created when needed
    - filename can be given otherwise it will be the document name + timestamp

    Output:
        - Path to stored file
    """

    os.makedirs(output_dir, exist_ok=True)

    if filename is None:
        doc_name = result.get("document", {}).get("name", "document")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        safe_doc_name = "".join(c for c in doc_name if c.isalnum() or c in ("-", "_", "."))
        filename = f"{safe_doc_name}_{timestamp}.json"

        output_path = Path(output_dir) / filename

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return str(output_path)