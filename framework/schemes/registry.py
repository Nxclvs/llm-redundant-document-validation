from __future__ import annotations

from typing import Any, Dict, Callable

from framework.scheme import FieldSpec

from framework.schemes import (
    urlaubsantrag,
    rechnung,
    reisekosten,
    bescheid,
    meldebescheinigung,
)


_SCHEMA_REGISTRY: Dict[str, Callable[[], Dict[str, FieldSpec]]] = {
    urlaubsantrag.DOC_TYPE: urlaubsantrag.get_schema,
    rechnung.DOC_TYPE: rechnung.get_schema,
    reisekosten.DOC_TYPE: reisekosten.get_schema,
    bescheid.DOC_TYPE: bescheid.get_schema,
    meldebescheinigung.DOC_TYPE: meldebescheinigung.get_schema,
}


def get_schema_for_type(doc_type: str) -> Dict[str, FieldSpec]:
    dt = (doc_type or "").strip().lower()
    if dt not in _SCHEMA_REGISTRY:
        raise ValueError(f"Unknown document type '{dt}'. Available: {sorted(_SCHEMA_REGISTRY.keys())}")
    return _SCHEMA_REGISTRY[dt]()


def get_schema_for_document(extracted_json: Dict[str, Any]) -> Dict[str, FieldSpec]:
    dt = (extracted_json.get("typ") or "").strip().lower()
    return get_schema_for_type(dt)


def get_schema_for_doc_type(doc_type: str) -> Dict[str, FieldSpec]:
    return get_schema_for_type(doc_type)
