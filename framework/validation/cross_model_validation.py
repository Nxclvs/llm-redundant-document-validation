from __future__ import annotations
from typing import Any, Dict, List, Tuple

from framework.scheme import FieldSpec

def _normalize_str(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip().lower()
    return v


def _compare_values(path: str, a: Any, b: Any) -> Tuple[bool, str]:
    """
    lightweight comparison
    Returns (equal, message)
    """

    a_n = _normalize_str(a)
    b_n = _normalize_str(b)

    if a_n == b_n:
        return True, "equal"
    
    # handle None
    if(a_n in (None, "") and b_n in (None, "")):
        return True, "both empty"

    return False, f"mismatch: A={a_n!r} vs B={b_n!r}"

def validate_cross_model(
    json_a: Dict[str, Any],
    json_b: Dict[str, Any],
    scheme_specs: Dict[str, FieldSpec],
) -> Dict[str, Any]:
    """
    Compares two extraction JSONs field-by-field based on scheme

    Output:
    {
        "is_consistent": bool, 
        "conflicts": [
            {"field": "...", "severity": "warning|error", "type": "mismatch|missing", "message": "..."}
        ],
        "stats": {"errors"; int, "warnings": int, "infos": int}
    }
    """

    conflicts: List[Dict[str, str]] = []

    def add_conflicts(field: str, severity: str, ctype: str, msg: str):
        conflicts.append({
            "field": field,
            "severity": severity,
            "type": ctype,
            "message": msg,
        })
    
    # source of truth (keys from scheme camparison)
    for key, spec in scheme_specs.items():
        a_has = key in json_a
        b_has = key in json_b

        if not a_has and not b_has:
            sev = "error" if spec.required else "warning"
            missing_side = "A" if not a_has else "B"
            add_conflicts(key, sev, "missing_key", f"Key fehlt in Extraktor {missing_side}")

        a_val = json_a.get(key)
        b_val = json_b.get(key)

        # nested objects
        if isinstance(a_val, dict) and isinstance(b_val, dict):

            subkeys = set(a_val.keys()) | set(b_val.keys())
            for sk in sorted(subkeys):
                ap = a_val.get(sk)
                bp = b_val.get(sk)
                ok, msg = _compare_values(f"{key}.{sk}", ap, bp)
                if not ok:
                    sev = "error" if spec.required else "warning"
                    add_conflicts(key, sev, "mismatch", msg)

    # stats
    errors = sum(1 for c in conflicts if c["severity"] == "error")
    warnings = sum(1 for c in conflicts if c["severity"] == "warning")
    infos = sum(1 for c in conflicts if c["severity"] == "info")

    is_consistent = (errors == 0 and warnings == 0)

    return {
        "is_consistent": is_consistent,
        "conflicts": conflicts,
        "stats": {"errors": errors, "warnings": warnings, "infos": infos},
    }