from __future__ import annotations

from typing import Any, Dict, Callable, List

from framework.schemes import (
    urlaubsantrag,
    rechnung,
    reisekosten,
    bescheid,
    meldebescheinigung,
)


_RULE_REGISTRY: Dict[str, Callable[[], List[Callable]]] = {
    urlaubsantrag.DOC_TYPE: urlaubsantrag.get_rules,
    rechnung.DOC_TYPE: rechnung.get_rules,
    reisekosten.DOC_TYPE: reisekosten.get_rules,
    bescheid.DOC_TYPE: bescheid.get_rules,
    meldebescheinigung.DOC_TYPE: meldebescheinigung.get_rules,
}


def get_rules_for_type(doc_type: str):
    dt = (doc_type or "").strip().lower()
    fn = _RULE_REGISTRY.get(dt)
    return fn() if fn else []


def get_rules_for_document(extracted_json: Dict[str, Any]):
    dt = (extracted_json.get("typ") or "").strip().lower()
    return get_rules_for_type(dt)

def validate_rules_for_doc_type(doc_type: str, data: Dict[str, Any], specs=None):
    rules = get_rules_for_type(doc_type)

    violations = []
    for rule in rules:
        res = rule(data, specs)
        if res:
            violations.extend(res)

    has_error = any(v.get("severity") == "error" for v in violations)

    return {
        "is_valid": not has_error,
        "violations": violations,
    }
