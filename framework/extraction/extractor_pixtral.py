# framework/extraction/extractor_pixtral.py

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import asdict
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Dict, Optional

from framework.models.mistral_client import get_mistral_client
from framework.scheme import FieldSpec


# Helpers
def _encode_image(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    with path.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _extract_json_string(text: str) -> str:
    """
    Extracts first JSON object from model output.
    Removes code fences and leading/trailing chatter.
    """
    cleaned = (text or "").strip()

    
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned).strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    
    s = cleaned.find("{")
    e = cleaned.rfind("}")
    if s != -1 and e != -1 and e > s:
        cleaned = cleaned[s : e + 1]

    return cleaned


def _camel_to_snake(s: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s


def _normalize_key(k: str) -> str:
    k = (k or "").strip()
    k = _camel_to_snake(k)
    k = k.lower()
    k = k.replace("-", "_").replace(" ", "_")
    k = re.sub(r"__+", "_", k)
    k = k.strip("_")
    return k


def _coerce_number(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return None
    # strip currency and normalize decimal comma
    s = s.replace("€", "").replace("eur", "").replace("euro", "")
    s = s.replace(".", "").replace(",", ".") if re.search(r"\d+,\d+", s) else s
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        return float(s)
    except Exception:
        return None



class PixtralVisionExtractor:
    """
    Pixtral/Mistral vision extractor.

    Key idea:
    - let model extract freely
    - then *force* output into schema via alias-mapping + normalization
    """

    def __init__(self, model: str = "pixtral-large-latest"):
        self.client = get_mistral_client()
        self.model = model


    # Alias maps (doc-type specific)
    def _alias_map_for_doc_type(self, doc_type: str) -> Dict[str, list[str]]:
        """
        Maps schema_key -> possible model keys (normalized).
        Keep this small + high-signal.
        """
        dt = (doc_type or "").strip().lower()

        if dt == "rechnung":
            return {
                "typ": ["typ", "document_type", "doctype"],
                "sender": ["sender", "absender", "vendor", "issuer", "aussteller", "company", "firma"],
                "empfaenger": ["empfaenger", "empfänger", "recipient", "customer", "kunde", "client"],
                "rechnungsnummer": ["rechnungsnummer", "invoice_number", "invoice_no", "invoiceid", "rechnung_nr", "rechnungnummer"],
                "datum": ["datum", "date", "invoice_date", "rechnungsdatum", "belegdatum"],
                "items": ["items", "positionen", "positions", "line_items", "lines"],
                "total_net": ["total_net", "netto", "subtotal", "sum_net", "net_amount", "total_ex_vat"],
                "total_vat": ["total_vat", "mwst", "vat", "tax", "tax_amount"],
                "total_gross": ["total_gross", "gesamt", "total", "gross", "grand_total", "total_inc_vat"],
            }

        if dt == "urlaubsantrag":
            return {
                "typ": ["typ", "document_type", "doctype"],
                "personalnummer": ["personalnummer", "personal_nr", "employee_id", "personnel_number"],
                "name": ["name", "employee", "mitarbeiter", "mitarbeiter_name", "full_name"],
                "abteilung": ["abteilung", "department"],
                "art": ["art", "urlaubsart", "leave_type", "vacation_type"],
                "von": ["von", "urlaub_von", "start", "start_date", "from"],
                "bis": ["bis", "urlaub_bis", "ende", "end_date", "to"],
                "tage": ["tage", "urlaubstage", "days", "day_count"],
                "datum": ["datum", "date", "antragsdatum"],
                "unterschrift_arbeitnehmer": ["unterschrift_arbeitnehmer", "signature_employee", "sign_employee"],
            }

        if dt == "reisekosten":
            return {
                "typ": ["typ", "document_type", "doctype"],
                "mitarbeiter": ["mitarbeiter", "name", "employee", "traveler"],
                "zielort": ["zielort", "destination", "city", "reiseort"],
                "start": ["start", "von", "start_date", "reise_von"],
                "ende": ["ende", "bis", "end_date", "reise_bis"],
                "kosten_details": ["kosten_details", "kosten", "details", "breakdown"],
                "erstattungsbetrag": ["erstattungsbetrag", "total", "summe", "reimbursement", "total_amount"],
            }

        if dt == "bescheid":
            return {
                "typ": ["typ", "document_type", "doctype"],
                "behoerde": ["behoerde", "behörde", "authority", "issuer", "aussteller"],
                "aktenzeichen": ["aktenzeichen", "reference", "reference_number", "ref", "az"],
                "betrag": ["betrag", "amount", "summe", "fee", "total"],
                "grund": ["grund", "betreff", "reason", "anlass", "beschreibung"],
                "datum": ["datum", "date"],
                "zahlungsfrist": ["zahlungsfrist", "frist", "faelligkeit", "due_date", "pay_until"],
                "adressat": ["adressat", "empfaenger", "recipient", "bürger", "person"],
            }

        if dt == "meldebescheinigung":
            return {
                "typ": ["typ", "document_type", "doctype"],
                "behoerde": ["behoerde", "behörde", "authority", "issuer"],
                "name": ["name", "bürger", "person", "full_name"],
                "geburtsdatum": ["geburtsdatum", "birth_date", "date_of_birth", "dob"],
                "anschrift": ["anschrift", "adresse", "address", "wohnort"],
                "datum": ["datum", "date", "ausstellungsdatum"],
                "aktenzeichen": ["aktenzeichen", "reference", "reference_number", "az"],
            }

        return {}


    # Scheme forcing

    def _force_schema_shape(self, raw: Dict[str, Any], schema: Dict[str, FieldSpec], doc_type: str) -> Dict[str, Any]:
        """
        Returns dict with exactly schema keys.
        Tries: direct match -> alias match -> fuzzy match (last resort).
        """
        schema_keys = list(schema.keys())
        alias_map = self._alias_map_for_doc_type(doc_type)

        # normalize 
        raw_norm: Dict[str, Any] = {}
        for k, v in (raw or {}).items():
            raw_norm[_normalize_key(k)] = v

        out: Dict[str, Any] = {k: None for k in schema_keys}

      
        for sk in schema_keys:
            sk_norm = _normalize_key(sk)
            # direct
            if sk_norm in raw_norm:
                out[sk] = raw_norm[sk_norm]
                continue

            # alias list 
            aliases = alias_map.get(sk, [])
            found = False
            for a in aliases:
                a_norm = _normalize_key(a)
                if a_norm in raw_norm:
                    out[sk] = raw_norm[a_norm]
                    found = True
                    break
            if found:
                continue

            candidates = get_close_matches(sk_norm, list(raw_norm.keys()), n=1, cutoff=0.92)
            if candidates:
                out[sk] = raw_norm[candidates[0]]

        if "typ" in out and (out.get("typ") is None or str(out.get("typ")).strip() == ""):
            out["typ"] = doc_type

        
        for k, spec in schema.items():
            if out.get(k) is None:
                continue
            expected = spec.dtype

            
            if expected is float:
                out[k] = _coerce_number(out[k])

            
            if expected is int:
                n = _coerce_number(out[k])
                out[k] = int(n) if n is not None else None

        return out

    def _build_prompt(self, schema: Dict[str, FieldSpec], doc_type: str) -> tuple[str, str]:
        """
        Prompt: keep it simple + force exact JSON shape.
        Avoid markdown fences in the instruction (Pixtral tends to answer with them).
        """
        keys = list(schema.keys())

        
        template = {}
        for k, spec in schema.items():
            
            template[k] = None

        schema_hints = []
        for k, spec in schema.items():
            t = getattr(spec, "dtype", None)
            tname = getattr(t, "__name__", str(t))
            desc = getattr(spec, "description", "") or ""
            schema_hints.append(f"- {k} ({tname}): {desc}".strip())

        system_prompt = (
            "You are a strict information extraction system.\n"
            "Return ONLY valid JSON.\n"
            "Do NOT use markdown fences.\n"
            "Use EXACTLY the provided keys and no others.\n"
            "If a value is missing or unreadable, use null.\n"
        )

        user_prompt = (
            f"Document type: {doc_type}\n\n"
            "Extract the data from the image and fill this JSON object.\n"
            "IMPORTANT: Output must be a JSON object with exactly these keys.\n\n"
            "Field hints:\n"
            + "\n".join(schema_hints)
            + "\n\n"
            "JSON to fill:\n"
            + json.dumps(template, ensure_ascii=False, indent=2)
        )

        return system_prompt, user_prompt


 

    def extract_from_image(self, image_path: str, schema: Dict[str, FieldSpec], doc_type: str) -> Dict[str, Any]:
        encoded_image = _encode_image(image_path)
        system_prompt, user_prompt = self._build_prompt(schema, doc_type)

        start_time = time.time()
        raw_content = ""

        try:
            try:
                response = self.client.chat.complete(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}},
                            ],
                        },
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
            except TypeError:
                response = self.client.chat.complete(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}},
                            ],
                        },
                    ],
                    temperature=0.0,
                )

            raw_content = response.choices[0].message.content
            duration = time.time() - start_time


            json_str = _extract_json_string(raw_content)
            parsed = json.loads(json_str) if json_str else {}

            # force scheme
            final_data = self._force_schema_shape(parsed if isinstance(parsed, dict) else {}, schema, doc_type)

            return {
                "data": final_data,
                "raw_response": raw_content,
                "duration_seconds": round(duration, 3),
                "model": self.model,
                "doc_type": doc_type,
                "parsed": parsed,
            }

        except Exception as e:
            duration = time.time() - start_time
            return {
                "data": {k: None for k in schema.keys()} if schema else {},
                "raw_response": f"EXCEPTION: {e}\nRAW: {raw_content}",
                "duration_seconds": round(duration, 3),
                "model": self.model,
                "doc_type": doc_type,
                "parsed": None,
            }
