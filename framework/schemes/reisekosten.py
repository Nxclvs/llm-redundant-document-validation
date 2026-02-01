from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from framework.scheme import FieldSpec


DOC_TYPE = "reisekosten"
DATE_FORMATS = ["%d.%m.%Y", "%d.%m.%y"]


def get_schema() -> Dict[str, FieldSpec]:
    return {
        "typ": FieldSpec(True, str, DOC_TYPE, "Dokumenttyp"),
        "mitarbeiter": FieldSpec(True, str, "Herr Hans Dieter Conradi", "Mitarbeiter"),
        "zielort": FieldSpec(True, str, "Mittweida", "Reiseziel"),
        "start": FieldSpec(True, str, "03.01.2026", "Startdatum"),
        "ende": FieldSpec(True, str, "05.01.2026", "Enddatum"),
        "kosten_details": FieldSpec(
            True,
            dict,
            {"transport": 96.60, "hotel": 258.07, "tagegeld": 84.00},
            "Kostenaufschlüsselung (transport/hotel/tagegeld)",
        ),
        "erstattungsbetrag": FieldSpec(True, float, 438.67, "Erstattungsbetrag (Summe)"),
    }


def get_rules():
    return [
        _rule_required_nonempty_core,
        _rule_date_format,
        _rule_date_range,
        _rule_costs_sum_matches_total,
    ]


def _parse_date(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            pass
    return None


def _violation(field: str, rule: str, severity: str, message: str) -> Dict[str, str]:
    return {"field": field, "rule": rule, "severity": severity, "message": message}


def _rule_required_nonempty_core(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    for k in ["mitarbeiter", "zielort", "start", "ende", "kosten_details", "erstattungsbetrag"]:
        if k not in data or data.get(k) in (None, "", [], {}):
            issues.append(_violation(k, "required", "error", f"Pflichtfeld '{k}' fehlt oder ist leer."))
    return issues


def _rule_date_format(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    for k in ["start", "ende"]:
        val = data.get(k)
        if val not in (None, "") and _parse_date(val) is None:
            issues.append(_violation(k, "date_format", "error", f"Datum '{val}' ist in keinem erwarteten Format."))
    return issues


def _rule_date_range(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    start = _parse_date(data.get("start"))
    end = _parse_date(data.get("ende"))
    if start and end and start > end:
        issues.append(_violation("start/ende", "date_range", "error", "Startdatum liegt nach Enddatum."))
    return issues


def _rule_costs_sum_matches_total(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    details = data.get("kosten_details")
    total = data.get("erstattungsbetrag")

    if not isinstance(details, dict) or not isinstance(total, (int, float)):
        return issues

    parts = []
    for k in ["transport", "hotel", "tagegeld"]:
        v = details.get(k)
        if isinstance(v, (int, float)):
            parts.append(float(v))

    if parts:
        calc = round(sum(parts), 2)
        if abs(calc - float(total)) > 0.05:
            issues.append(_violation(
                "erstattungsbetrag",
                "sum_mismatch",
                "warning",
                f"Summe der Kosten ({calc}) weicht vom Erstattungsbetrag ({total}) ab."
            ))
    return issues
