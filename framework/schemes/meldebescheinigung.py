from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from framework.scheme import FieldSpec


DOC_TYPE = "meldebescheinigung"
DATE_FORMATS = ["%d.%m.%Y", "%d.%m.%y"]


def get_schema() -> Dict[str, FieldSpec]:
    return {
        "typ": FieldSpec(True, str, DOC_TYPE, "Dokumenttyp"),
        "behoerde": FieldSpec(True, str, "Stadt Hoyerswerda", "Ausstellende Behörde"),
        "name": FieldSpec(True, str, "Hedda Stadelmann", "Name (Familienname, Vorname)"),
        "geburtsdatum": FieldSpec(True, str, "18.05.1945", "Geburtsdatum"),
        "anschrift_aktuell": FieldSpec(True, str, "Geißlerallee 32/14, 08607 Hoyerswerda", "Aktuelle Anschrift"),
        "einzugsdatum": FieldSpec(True, str, "13.10.2022", "Einzugsdatum"),
        "anschrift_vorher": FieldSpec(False, str, "Hermannallee 77/60, 03397 Iserlohn", "Vorherige Anschrift"),
        "datum": FieldSpec(True, str, "26.01.2026", "Ausstellungsdatum"),
        "siegel": FieldSpec(False, bool, True, "Siegel vorhanden (true/false)"),
    }


def get_rules():
    return [
        _rule_required_nonempty_core,
        _rule_date_format,
        _rule_move_in_before_issue_date,
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
    for k in ["behoerde", "name", "geburtsdatum", "anschrift_aktuell", "einzugsdatum", "datum"]:
        if k not in data or data.get(k) in (None, "", [], {}):
            issues.append(_violation(k, "required", "error", f"Pflichtfeld '{k}' fehlt oder ist leer."))
    return issues


def _rule_date_format(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    for k in ["geburtsdatum", "einzugsdatum", "datum"]:
        val = data.get(k)
        if val not in (None, "") and _parse_date(val) is None:
            issues.append(_violation(k, "date_format", "warning", f"Datum '{val}' konnte nicht sicher geparst werden."))
    return issues


def _rule_move_in_before_issue_date(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    move_in = _parse_date(data.get("einzugsdatum"))
    issued = _parse_date(data.get("datum"))
    if move_in and issued and move_in > issued:
        issues.append(_violation(
            "einzugsdatum",
            "temporal_conflict",
            "error",
            "Einzugsdatum liegt nach Ausstellungsdatum (unplausibel)."
        ))
    return issues
