from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from framework.scheme import FieldSpec


DOC_TYPE = "rechnung"
DATE_FORMATS = ["%d.%m.%Y", "%d.%m.%y"]


def get_schema() -> Dict[str, FieldSpec]:
    return {
        "typ": FieldSpec(True, str, DOC_TYPE, "Dokumenttyp"),
        "sender": FieldSpec(True, str, "Jäkel Martin e.V.", "Absender/Firma"),
        "empfaenger": FieldSpec(True, str, "Iwona Martin", "Empfänger"),
        "rechnungsnummer": FieldSpec(True, str, "RE-2026-1520", "Rechnungsnummer"),
        "datum": FieldSpec(True, str, "09.01.2026", "Rechnungsdatum"),
        "items": FieldSpec(
            True,
            list,
            [
                {"description": "Incubate collaborative eyeballs", "quantity": 2, "unit_price": 40.61, "total": 81.22},
            ],
            "Positionen: Liste aus dicts(description, quantity, unit_price, total)",
        ),
        "total_net": FieldSpec(True, float, 929.74, "Nettosumme"),
        "total_vat": FieldSpec(True, float, 176.65, "MwSt"),
        "total_gross": FieldSpec(True, float, 1106.39, "Gesamtsumme (brutto)"),
    }


def get_rules():
    return [
        _rule_required_nonempty_core,
        _rule_date_format,
        _rule_items_structure,
        _rule_item_totals_consistency,
        _rule_invoice_totals_consistency,
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
    for k in ["sender", "empfaenger", "rechnungsnummer", "datum", "items", "total_net", "total_vat", "total_gross"]:
        if k not in data or data.get(k) in (None, "", [], {}):
            issues.append(_violation(k, "required", "error", f"Pflichtfeld '{k}' fehlt oder ist leer."))
    return issues


def _rule_date_format(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    val = data.get("datum")
    if val not in (None, "") and _parse_date(val) is None:
        issues.append(_violation("datum", "date_format", "error", f"Datum '{val}' ist in keinem erwarteten Format."))
    return issues


def _rule_items_structure(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    items = data.get("items")
    if items is None:
        return issues
    if not isinstance(items, list):
        return [_violation("items", "type", "error", "items ist kein Array/Liste.")]
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            issues.append(_violation(f"items[{i}]", "type", "error", "Position ist kein Objekt/dict."))
            continue
        for k in ["description", "quantity", "unit_price", "total"]:
            if k not in it:
                issues.append(_violation(f"items[{i}].{k}", "missing_key", "warning", "Key fehlt in Item."))
    return issues


def _rule_item_totals_consistency(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    items = data.get("items")
    if not isinstance(items, list):
        return issues

    for i, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        q = it.get("quantity")
        up = it.get("unit_price")
        t = it.get("total")
        if isinstance(q, (int, float)) and isinstance(up, (int, float)) and isinstance(t, (int, float)):
            calc = round(float(q) * float(up), 2)
            if abs(calc - float(t)) > 0.02:
                issues.append(_violation(
                    f"items[{i}].total",
                    "item_total_mismatch",
                    "warning",
                    f"Item total weicht ab: quantity*unit_price={calc} vs total={t}."
                ))
    return issues


def _rule_invoice_totals_consistency(data: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    net = data.get("total_net")
    vat = data.get("total_vat")
    gross = data.get("total_gross")

    if all(isinstance(x, (int, float)) for x in [net, vat, gross]):
        calc = round(float(net) + float(vat), 2)
        if abs(calc - float(gross)) > 0.02:
            issues.append(_violation(
                "total_gross",
                "totals_mismatch",
                "error",
                f"Brutto != Netto+MwSt: {calc} vs {gross}."
            ))
    return issues
