from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from framework.schemes.registry import get_schema_for_type

DATE_FORMATS = ["%d.%m.%Y", "%d.%m.%y"]


def _parse_date(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def _is_empty(v: Any) -> bool:
    return v in (None, "", {}, [])


def _add(violations: List[Dict[str, str]], field: str, rule: str, severity: str, message: str):
    violations.append(
        {"field": field, "rule": rule, "severity": severity, "message": message}
    )


def _required_fields_from_schema(schema: Dict[str, Any]) -> List[str]:
    fields = schema.get("fields") or {}
    out = []
    for k, meta in fields.items():
        if isinstance(meta, dict) and meta.get("required") is True:
            out.append(k)
    return out


def _validate_required_fields(data: Dict[str, Any], schema: Dict[str, Any], violations: List[Dict[str, str]]):
    required = _required_fields_from_schema(schema)
    for field in required:
        if field not in data or _is_empty(data.get(field)):
            _add(
                violations,
                field=field,
                rule="required",
                severity="error",
                message=f"Pflichtfeld '{field}' ist leer oder fehlt (Extraktion unvollständig).",
            )


def _validate_date_fields(data: Dict[str, Any], schema: Dict[str, Any], violations: List[Dict[str, str]]):
    
    fields = schema.get("fields") or {}
    for key, meta in fields.items():
        if isinstance(meta, dict) and meta.get("type") == "date":
            v = data.get(key)
            if _is_empty(v):
                continue
            if _parse_date(v) is None:
                _add(
                    violations,
                    field=key,
                    rule="date_format",
                    severity="error",
                    message=f"Wert '{v}' im Feld '{key}' entspricht keinem erwarteten Datumsformat.",
                )


def _date_order(data: Dict[str, Any], start_key: str, end_key: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    start = _parse_date(data.get(start_key))
    end = _parse_date(data.get(end_key))
    return start, end


def _apply_schema_rules(data: Dict[str, Any], schema: Dict[str, Any], violations: List[Dict[str, str]]):
    """
    Liest die rules direkt aus dem Schema:
    [
      {"field": "...", "rule": "...", "severity": "...", "description": "..."}
    ]
    """
    rules = schema.get("rules") or []
    for r in rules:
        if not isinstance(r, dict):
            continue

        rule_name = (r.get("rule") or "").strip()
        field = (r.get("field") or "").strip() or "unknown"
        severity = (r.get("severity") or "warning").strip().lower()
        desc = (r.get("description") or "").strip()

        # 1) date_order
        if rule_name == "date_order":
            if "/" not in field:
                continue
            a, b = field.split("/", 1)
            a = a.strip()
            b = b.strip()

            start, end = _date_order(data, a, b)
            if start and end and start > end:
                _add(
                    violations,
                    field=f"{a}/{b}",
                    rule="date_order",
                    severity=severity,
                    message=desc or f"Datum '{a}' liegt nach '{b}' (inkonsistent).",
                )

        # 2) day_range
        elif rule_name == "day_range":
            # erwartet: tage + (von,bis)
            days = data.get("tage") if "tage" in data else data.get("urlaubstage")
            start, end = _date_order(data, "von", "bis")
            if isinstance(days, (int, float)) and start and end:
                diff = (end - start).days + 1
                if days <= 0 or days > diff:
                    _add(
                        violations,
                        field="tage",
                        rule="day_range",
                        severity=severity,
                        message=desc or f"Anzahl Tage ({days}) ist nicht konsistent zum Zeitraum ({diff} mögliche Tage).",
                    )

        # 3) items_present
        elif rule_name == "items_present":
            items = data.get("items")
            if not isinstance(items, list) or len(items) == 0:
                _add(
                    violations,
                    field="items",
                    rule="items_present",
                    severity=severity,
                    message=desc or "Rechnung enthält keine Positionen.",
                )

        # 4) vat_consistency
        elif rule_name == "vat_consistency":
            net = data.get("total_net")
            vat = data.get("total_vat")
            gross = data.get("total_gross")
            if isinstance(net, (int, float)) and isinstance(vat, (int, float)) and isinstance(gross, (int, float)):
                expected = float(net) + float(vat)
                if abs(float(gross) - expected) > 0.02:  # cent tolerance
                    _add(
                        violations,
                        field="total_gross",
                        rule="vat_consistency",
                        severity=severity,
                        message=desc or f"Brutto ({gross}) ist nicht Netto+MwSt ({expected:.2f}).",
                    )

        # 5) sum_check
        elif rule_name == "sum_check":
            kd = data.get("kosten_details")
            total = data.get("erstattungsbetrag")
            if isinstance(kd, dict) and isinstance(total, (int, float)):
                parts = [v for v in kd.values() if isinstance(v, (int, float))]
                if parts:
                    expected = float(sum(parts))
                    if abs(float(total) - expected) > 0.02:
                        _add(
                            violations,
                            field="erstattungsbetrag",
                            rule="sum_check",
                            severity=severity,
                            message=desc or f"Erstattungsbetrag ({total}) passt nicht zur Summe der Positionen ({expected:.2f}).",
                        )

        # 6) positive_value: z.B. Bescheid betrag > 0
        elif rule_name == "positive_value":
            # Default: field zeigt auf das Feld im Schema
            val = data.get(field)
            if isinstance(val, (int, float)) and float(val) <= 0:
                _add(
                    violations,
                    field=field,
                    rule="positive_value",
                    severity=severity,
                    message=desc or f"Wert im Feld '{field}' muss > 0 sein.",
                )

        # 7) past_date
        elif rule_name == "past_date":
            dt = _parse_date(data.get(field))
            if dt is None:
                continue
            if dt > datetime.now():
                _add(
                    violations,
                    field=field,
                    rule="past_date",
                    severity=severity,
                    message=desc or f"Datum im Feld '{field}' liegt in der Zukunft.",
                )

        else:
            continue


def validate_rules(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Routing-fähige Rule Validation:
    - erkennt doc_type über data["typ"]
    - lädt passendes schema über Registry
    - required/date checks generisch aus schema
    - wendet schema['rules'] an
    """
    violations: List[Dict[str, str]] = []

    doc_type = (data.get("typ") or "").strip().lower()
    if not doc_type:
        return {
            "is_valid": False,
            "violations": [
                {
                    "field": "typ",
                    "rule": "missing_doc_type",
                    "severity": "error",
                    "message": "Dokumenttyp 'typ' fehlt im extrahierten JSON. Routing nicht möglich.",
                }
            ],
        }

    try:
        schema = get_schema_for_type(doc_type)
    except Exception as e:
        return {
            "is_valid": False,
            "violations": [
                {
                    "field": "typ",
                    "rule": "unknown_doc_type",
                    "severity": "error",
                    "message": f"Unbekannter Dokumenttyp '{doc_type}': {e}",
                }
            ],
        }

    # 1) required fields 
    _validate_required_fields(data, schema, violations)

    # 2) date format checks 
    _validate_date_fields(data, schema, violations)

    # 3) scheme rules 
    _apply_schema_rules(data, schema, violations)

    has_error = any(v.get("severity") == "error" for v in violations)
    return {"is_valid": not has_error, "violations": violations}
