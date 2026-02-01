from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from framework.scheme import FieldSpec


DOC_TYPE = "bescheid"
DATE_FORMATS = ["%d.%m.%Y", "%d.%m.%y"]


def get_schema() -> Dict[str, FieldSpec]:
    return {
        "typ": FieldSpec(True, str, DOC_TYPE, "Dokumenttyp"),
        "behoerde": FieldSpec(True, str, "Stadtverwaltung Aurich", "Behörde / Aussteller"),
        "adressat": FieldSpec(False, str, "Dipl.-Ing. Nikolai Bien", "Adressat (Name)"),
        "aktenzeichen": FieldSpec(True, str, "AZ-325772", "Aktenzeichen"),
        "datum": FieldSpec(True, str, "11.01.2026", "Datum des Bescheids"),
        "grund": FieldSpec(True, str, "Meldebescheinigung", "Gebührenanlass / Grund"),
        "betrag": FieldSpec(True, float, 77.22, "Festgesetzter Betrag"),
        "zahlungsfrist": FieldSpec(True, str, "06.02.2026", "Zahlungsfrist (Datum)"),
    }


def get_rules():
    return [
        _rule_required_nonempty_core,
        _rule_date_format,
        _rule_deadline_after_date,
        _rule_amount_positive,
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
    for k in ["behoerde", "aktenzeichen", "datum", "grund", "betrag", "zahlungsfrist"]:
        if k not in data or data.get(k) in (None, "", [], {}):
            issues.append(_violation(k, "required", "error", f"Pflichtfeld '{k}' fehlt oder ist leer."))
    return issues


def _rule_date_format(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    for k in ["datum", "zahlungsfrist"]:
        val = data.get(k)
        if val not in (None, "") and _parse_date(val) is None:
            issues.append(_violation(k, "date_format", "error", f"Datum '{val}' ist in keinem erwarteten Format."))
    return issues


def _rule_deadline_after_date(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    d = _parse_date(data.get("datum"))
    fr = _parse_date(data.get("zahlungsfrist"))
    if d and fr and fr < d:
        issues.append(_violation("zahlungsfrist", "deadline_before_date", "error", "Zahlungsfrist liegt vor dem Bescheiddatum."))
    return issues


def _rule_amount_positive(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    amount = data.get("betrag")
    if isinstance(amount, (int, float)) and float(amount) <= 0:
        issues.append(_violation("betrag", "amount_nonpositive", "error", "Betrag <= 0 ist unplausibel."))
    return issues
