from datetime import datetime
from typing import Any, Dict, List, Optional

from framework.scheme import get_urlaubsantrag_schema, required_fields_from_specs

DATE_FORMATS = ["%d.%m.%Y", "%d.%m.%y"]


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def validate_rules(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes rule based checks

    Output format:
    {
        "is_valid": bool,  # True, if no Error
        "violations": [
            {"field": str, "rule": str, "severity": "error|warning|info", "message": str}
        ]
    }
    """
    violations: List[Dict[str, str]] = []

    # 1) required fields
    specs = get_urlaubsantrag_schema()
    required_fields = required_fields_from_specs(specs)

    for field in required_fields:
        if field not in data or data.get(field) in ("", None):
            violations.append({
                "field": field,
                "rule": "required",
                "severity": "error",
                "message": f"Pflichtfeld '{field}' ist leer oder fehlt (Extraktion unvollständig)."
            })

    # 2) check date format
    for field in ["eintrittsdatum", "urlaub_von", "urlaub_bis"]:
        value = data.get(field)
        if value:
            parsed = _parse_date(value)
            if parsed is None:
                violations.append({
                    "field": field,
                    "rule": "date_format",
                    "severity": "error",
                    "message": f"Wert '{value}' im Feld '{field}' entspricht keinem erwarteten Datumsformat."
                })

    # 3) Urlaub_von <= Urlaub_bis 
    start = _parse_date(data.get("urlaub_von", ""))
    end = _parse_date(data.get("urlaub_bis", ""))
    if start and end and start > end:
        violations.append({
            "field": "urlaub_von/urlaub_bis",
            "rule": "date_range",
            "severity": "error",
            "message": "Das Startdatum des Urlaubs liegt nach dem Enddatum (inkonsistente Extraktion)."
        })

    # 4) day count plausibillity
    days = data.get("urlaubstage")
    if days is not None and isinstance(days, (int, float)) and start and end:
        diff = (end - start).days + 1  # inkl. beider Tage
        if days <= 0 or days > diff:
            violations.append({
                "field": "urlaubstage",
                "rule": "days_inconsistent",
                "severity": "warning",
                "message": f"Anzahl der Urlaubstage ({days}) ist nicht konsistent zum Zeitraum ({diff} mögliche Tage)."
            })

    # 5) specific things
    # Example: signature
    if "unterschrift_vorgesetzter" in data and not data.get("unterschrift_vorgesetzter"):
        violations.append({
            "field": "unterschrift_vorgesetzter",
            "rule": "approval_info",
            "severity": "info",
            "message": "Unterschrift des Vorgesetzten ist leer. Dies kann fachlich relevant sein, ist aber kein Extraktionsfehler."
        })

    has_error = any(v.get("severity") == "error" for v in violations)

    return {
        "is_valid": not has_error,
        "violations": violations,
    }
