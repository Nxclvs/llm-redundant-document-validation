from __future__ import annotations
from typing import Any, Dict, List, Tuple

from framework.scheme import FieldSpec

def _is_instance(value: Any, dtype: type) -> bool:
    """
    checks if value is of expected dtype
    "None" is always allowed
    """
    if value is None:
        return True
    return isinstance(value, dtype)


def validate_scheme(
    data: Dict[str, Any],
    scheme_specs: Dict[str, FieldSpec],
    *,
    allow_extra_keys: bool = True
) -> Dict[str, Any]:
    """
    checks if 'data' has the correct scheme
    - all scheme-keys present
    - required keys not empty
    - correct data types

    Output:
        {
        "is_valid": bool,  # True if no 'error'
        "violations": [
            {"field": str, "rule": str, "severity": "error|warning|info", "message": str}
        ]
        }
    """

    violations: List[Dict[str, str]] = []

    scheme_keys = set(scheme_specs.keys())
    data_keys = set(data.keys())

    # 1) missing keys
    missing_keys = sorted(list(scheme_keys - data_keys))

    for key in missing_keys:
        spec = scheme_specs[key]
        severity = "error" if spec.required else "warning"
        violations.append({
            "field": key,
            "rule": "missing_key",
            "severity": severity,
            "message": f"Feld '{key}' fehlt im extrahierten Ergebnis."
        })

    # 2) extra keys
    extra_keys = sorted(list(data_keys - scheme_keys))
    if extra_keys and not allow_extra_keys:
        for key in extra_keys:
            violations.append({
                "field": key,
                "rule": "unexpected_key",
                "severity": "warning",
                "message": f"Unerwarteter Schlüssel '{key}' im extrahierten Ergebnis."
            })

    # 3) required keys not empty
    for key, spec in scheme_specs.items():
        if key not in data:
            continue
        val = data.get(key)

        if spec.required:
            # handle empty strings as empty
            if val is None or val == "" or val == {} or val == []:
                violations.append({
                    "field": key,
                    "rule": "required_field_empty",
                    "severity": "error",
                    "message": f"Pflichtfeld '{key}' ist leer."
                })

    # 4) type checks
    for key, spec in scheme_specs.items():
        if key not in data:
            continue
        val = data.get(key)

        # allow None
        if val is None:
            continue

        # for required
        if not _is_instance(val, spec.dtype):
            violations.append({
                "field": key,
                "rule": "type_mismatch",
                "severity": "warning",
                "message": f"Feld '{key}' hat falschen Datentyp. Erwartet: {spec.dtype.__name__}, Gefunden: {type(val).__name__}."
            })

    has_error = any(v.get("severity") == "error" for v in violations)
    return {"is_valid": not has_error, "violations": violations}