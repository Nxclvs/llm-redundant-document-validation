from __future__ import annotations

from typing import Any, Dict, List, Tuple

from framework.scheme import FieldSpec


def _normalize_str(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip().lower()
    return v


def _both_empty(a: Any, b: Any) -> bool:
    empties = (None, "")
    return (a in empties) and (b in empties)


def _compare_values(path: str, a: Any, b: Any) -> Tuple[bool, str]:
    """
    Lightweight comparison with normalization.
    Returns (equal, message).
    """
    a_n = _normalize_str(a)
    b_n = _normalize_str(b)

    # identical after normalization
    if a_n == b_n:
        return True, "equal"

    # treat None/"" as equivalent empties
    if _both_empty(a_n, b_n):
        return True, "both empty"

    return False, f"mismatch at {path}: A={a_n!r} vs B={b_n!r}"


def validate_cross_model(
    json_a: Dict[str, Any],
    json_b: Dict[str, Any],
    scheme_specs: Dict[str, FieldSpec],
) -> Dict[str, Any]:
    """
    Compares two extraction JSONs field-by-field based on scheme.

    Output:
    {
        "is_consistent": bool,
        "conflicts": [
            {"field": "...", "severity": "warning|error|info", "type": "...", "message": "..."}
        ],
        "stats": {"errors": int, "warnings": int, "infos": int}
    }
    """

    conflicts: List[Dict[str, str]] = []

    def add_conflict(field: str, severity: str, ctype: str, msg: str):
        conflicts.append(
            {
                "field": field,
                "severity": severity,
                "type": ctype,
                "message": msg,
            }
        )

    for key, spec in scheme_specs.items():
        a_has = key in json_a
        b_has = key in json_b

        # key missing
        if not a_has or not b_has:
            if not a_has and not b_has:
                sev = "error" if spec.required else "warning"
                add_conflict(key, sev, "missing_key", "Key fehlt in beiden Extraktoren (A und B).")
                continue

            missing_side = "A" if not a_has else "B"
            sev = "error" if spec.required else "warning"
            add_conflict(key, sev, "missing_key", f"Key fehlt in Extraktor {missing_side}.")
            continue

        a_val = json_a.get(key)
        b_val = json_b.get(key)

        # nested object compare (dict)
        if isinstance(a_val, dict) and isinstance(b_val, dict):
            subkeys = set(a_val.keys()) | set(b_val.keys())
            for sk in sorted(subkeys):
                ap = a_val.get(sk)
                bp = b_val.get(sk)
                ok, msg = _compare_values(f"{key}.{sk}", ap, bp)
                if not ok:
                    sev = "error" if spec.required else "warning"
                    add_conflict(key, sev, "mismatch", msg)
            continue

        # if one is dict but other isn't -> mismatch
        if isinstance(a_val, dict) != isinstance(b_val, dict):
            sev = "error" if spec.required else "warning"
            add_conflict(key, sev, "type_mismatch", f"type mismatch: A={type(a_val).__name__} vs B={type(b_val).__name__}")
            continue

        # scalar compare (strings, ints, floats, bools, None)
        ok, msg = _compare_values(key, a_val, b_val)
        if not ok:
            sev = "error" if spec.required else "warning"
            add_conflict(key, sev, "mismatch", msg)

    errors = sum(1 for c in conflicts if c["severity"] == "error")
    warnings = sum(1 for c in conflicts if c["severity"] == "warning")
    infos = sum(1 for c in conflicts if c["severity"] == "info")

    is_consistent = (errors == 0 and warnings == 0)

    return {
        "is_consistent": is_consistent,
        "conflicts": conflicts,
        "stats": {"errors": errors, "warnings": warnings, "infos": infos},
    }
