from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class FieldSpec:
    """
    specification of a field in the extraction scheme
    - required: has to be extracted (even if empty), else error
    - dtype: expected python-type (also for rule checks)
    - example: example scheme
    - description: short description
    """
    required: bool
    dtype: type
    example: Any
    description: Optional[str] = None

def get_urlaubsantrag_schema() -> Dict[str, FieldSpec]:
    """
    central scheme for document type "Urlaubsantrag"
    keys = output keys for extraction
    """
    return {
        "name_vorname": FieldSpec(True, str, "Maier, Max", "Name, Vorname"),
        "eintrittsdatum": FieldSpec(False, str, "08.09.15", "Eintrittsdatum (wie im Dokument angegeben)"),
        "personal_nr": FieldSpec(False, str, "12345", "Personalnummer"),
        "urlaub_von": FieldSpec(True, str, "07.04.20", "Urlaub von (Datum)"),
        "urlaub_bis": FieldSpec(True, str, "11.04.20", "Urlaub bis (Datum)"),
        "urlaubstage": FieldSpec(False, int, 4, "Anzahl Urlaubstage"),
        "ort_datum": FieldSpec(False, str, "", "Ort/Datum (kann leer sein)"),
        "unterschrift_arbeitnehmer": FieldSpec(False, str, "", "Unterschrift Arbeitnehmer (kann leer sein)"),
        "unterschrift_vorgesetzter": FieldSpec(False, str, "", "Unterschrift Vorgesetzter (kann leer sein)"),
        "kontrollkaesten": FieldSpec(
            False,
            dict,
            {
                "resturlaub": False,
                "sonderurlaub": False,
                "sonstiges": False,
            },
            "Kontrollkästchen (true/false)"
        ),
    }

def scheme_example_from_specs(specs: Dict[str, FieldSpec]) -> Dict[str, Any]:
    """
    builds example json from field specs (for prompt/scheme orientation)
    """
    return {k: v.example for k, v in specs.items()}

def required_fields_from_specs(specs: Dict[str, FieldSpec]) -> list[str]:
    return[k for k, v in specs.items() if v.required]