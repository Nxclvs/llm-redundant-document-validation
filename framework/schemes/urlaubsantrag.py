from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from framework.scheme import FieldSpec


DOC_TYPE = "urlaubsantrag"
DATE_FORMATS = ["%d.%m.%Y", "%d.%m.%y"]


def get_schema() -> Dict[str, FieldSpec]:
    return {
        "typ": FieldSpec(True, str, DOC_TYPE, "Dokumenttyp"),
        "personalnummer": FieldSpec(True, str, "13278", "Personalnummer"),
        "name": FieldSpec(True, str, "Prof. Sandra Staude MBA.", "Name, Vorname"),
        "abteilung": FieldSpec(True, str, "Vertrieb", "Abteilung"),
        "art": FieldSpec(True, str, "Erholungsurlaub", "Urlaubsart"),
        "von": FieldSpec(True, str, "02.09.2026", "Urlaub von (Datum)"),
        "bis": FieldSpec(True, str, "06.09.2026", "Urlaub bis (Datum)"),
        "tage": FieldSpec(True, int, 4, "Anzahl Urlaubstage"),
        "datum": FieldSpec(False, str, "18.01.2026", "Datum der Antragstellung"),
        "unterschrift_arbeitnehmer": FieldSpec(False, str, "", "Unterschrift Arbeitnehmer (kann leer sein)"),
    }


def get_rules():
    return [
        _rule_required_nonempty_core,
        _rule_date_format,
        _rule_date_range,
        _rule_days_plausibility,
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
    for k in ["personalnummer", "name", "abteilung", "art", "von", "bis", "tage"]:
        if k not in data or data.get(k) in (None, "", [], {}):
            issues.append(_violation(k, "required", "error", f"Pflichtfeld '{k}' fehlt oder ist leer."))
    return issues


def _rule_date_format(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    for k in ["von", "bis", "datum"]:
        val = data.get(k)
        if val in (None, ""):
            continue
        if _parse_date(val) is None:
            issues.append(_violation(k, "date_format", "error", f"Datum '{val}' ist in keinem erwarteten Format."))
    return issues


def _rule_date_range(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    start = _parse_date(data.get("von"))
    end = _parse_date(data.get("bis"))
    if start and end and start > end:
        issues.append(_violation("von/bis", "date_range", "error", "Startdatum liegt nach Enddatum."))
    return issues


def _rule_days_plausibility(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    start = _parse_date(data.get("von"))
    end = _parse_date(data.get("bis"))
    days = data.get("tage")

    if start and end and isinstance(days, int):
        max_days = (end - start).days + 1
        if days <= 0:
            issues.append(_violation("tage", "days_nonpositive", "error", "Urlaubstage <= 0 ist unplausibel."))
        elif days > max_days:
            issues.append(_violation("tage", "days_inconsistent", "warning", f"Urlaubstage ({days}) > Zeitraum ({max_days})."))
    return issues
