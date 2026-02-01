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

def scheme_example_from_specs(specs: Dict[str, FieldSpec]) -> Dict[str, Any]:
    """
    builds example json from field specs (for prompt/scheme orientation)
    """
    return {k: v.example for k, v in specs.items()}

def required_fields_from_specs(specs: Dict[str, FieldSpec]) -> list[str]:
    return[k for k, v in specs.items() if v.required]