from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any, Dict, Tuple


from framework.models.mistral_client import get_mistral_client
from framework.models.openai_client import get_openai_client


def _encode_image(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with path.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _extract_json_string(text: str) -> str:
    """
    Tries to extract a pure JSON object from a model response.
    Handles Markdown code fences and leading/trailing chatter.
    """
    cleaned = (text or "").strip()

    # Remove code fences
    if cleaned.startswith("```"):
        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json") :].strip()
        else:
            cleaned = cleaned[len("```") :].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    # Cut to JSON object boundaries
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]

    return cleaned


def _build_prompt(extracted_data: Dict[str, Any]) -> Tuple[str, str]:
    extracted_json_str = json.dumps(extracted_data, indent=2, ensure_ascii=False)

    system_prompt = (
        "Du bist ein Validierungsmodell für verwaltungsnahe Dokumente. "
        "Deine Aufgabe ist es, extrahierte Felder kritisch und unabhängig "
        "gegen das Originaldokument zu prüfen. "
        "Sei explizit in deinen Bewertungen und melde auch Unsicherheiten. "
        "Antworte ausschließlich mit JSON."
    )

    user_prompt = f"""
Lies zunächst selbstständig die relevanten Informationen aus dem angehängten Dokument aus.
Nutze dafür ausschließlich das Dokument, NICHT die JSON-Daten.

Vergleiche dann deine eigenen Beobachtungen mit den unten angegebenen JSON-Daten.
Deine Aufgabe ist nicht, dem JSON zuzustimmen, sondern Abweichungen, Fehler und Unsicherheiten zu identifizieren.

Gib das Ergebnis ausschließlich als gültiges JSON in folgendem Format zurück:

{{
  "status": "valid" | "invalid" | "uncertain",
  "issues": [
    {{
      "field": "<feldname>",
      "type": "<error_type (z.B. 'mismatch', 'missing', 'uncertain', 'info')>",
      "severity": "<'error' | 'warning' | 'info'>",
      "message": "<kurze Beschreibung der Abweichung, Unsicherheit oder Information>"
    }}
  ],
  "comments": "<kurze Gesamtbewertung der Extraktion>"
}}

Definitionen:
- 'error' für echte Fehler (falscher Wert, wichtiges Feld fehlt).
- 'warning' für Unsicherheiten (schwer lesbar, Kontext unklar).
- 'info' nur für Hinweise, bei denen alles korrekt ist, du aber etwas kommentieren möchtest
  (z.B. Feld ist leer und korrekt leer extrahiert).

Regeln:
- Wenn alle Werte korrekt erscheinen und es nur 'info'-Einträge gibt → status="valid".
- Wenn Unsicherheiten bestehen, aber keine klaren Fehler → status="uncertain".
- Wenn wesentliche Werte klar falsch oder widersprüchlich sind → status="invalid".
- Schreibe KEINEN zusätzlichen Text außerhalb des JSON und verwende KEINE Markdown-Codeblöcke (keine ```-Syntax).

Hier sind die vom Extraktionsmodell gelieferten JSON-Daten:
{extracted_json_str}
""".strip()

    return system_prompt, user_prompt


def semantic_validate(
    image_path: str,
    extracted_data: Dict[str, Any],
    provider: str = "mistral",
    model: str = "pixtral-large-latest",
    *,
    temperature: float = 0.0,
    max_tokens: int = 1200,
    retry_on_parse_error: int = 1,
) -> Dict[str, Any]:
    """
    Provider-agnostic semantic validation entry point.

    provider: "mistral" | "openai"
    model:    provider-specific model name
    """
    provider_norm = (provider or "").strip().lower()

    if provider_norm == "openai":
        return semantic_validate_openai(
            image_path=image_path,
            extracted_data=extracted_data,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider_norm == "mistral":
        return semantic_validate_mistral(
            image_path=image_path,
            extracted_data=extracted_data,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            retry_on_parse_error=retry_on_parse_error,
        )

    return {
        "status": "parse_error",
        "issues": [],
        "comments": f"Unknown provider '{provider}'.",
        "raw_response": "",
        "duration_seconds": 0.0,
        "model": model,
        "provider": provider_norm,
        "parsed": None,
    }


def semantic_validate_mistral(
    image_path: str,
    extracted_data: Dict[str, Any],
    model: str = "pixtral-large-latest",
    *,
    temperature: float = 0.0,
    max_tokens: int = 1200,
    retry_on_parse_error: int = 1,
) -> Dict[str, Any]:
    """
    Mistral/Pixtral-based semantic validation (vision).
    Includes optional retry if parsing fails.
    """

    client = get_mistral_client()
    encoded_image = _encode_image(image_path)
    system_prompt, user_prompt = _build_prompt(extracted_data)

    def _call_once() -> tuple[str, float]:
        start_time = time.time()
        
        print(f"   [Mistral] Validating {Path(image_path).name} with {model}...")

        response = client.chat.complete(
            model=model,
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
            temperature=temperature,
            max_tokens=max_tokens,
        )
        duration = time.time() - start_time
        raw = response.choices[0].message.content
        return raw, duration

    # Erster Versuch
    try:
        raw_content, duration = _call_once()
    except Exception as e:
        print(f"   [Mistral] Error during first validation call: {e}")
        raw_content = ""
        duration = 0.0

    def _parse(raw: str):
        json_str = _extract_json_string(raw)
        parsed = json.loads(json_str)
        status = parsed.get("status", "uncertain")
        issues = parsed.get("issues", []) or []
        comments = parsed.get("comments", "")
        return parsed, status, issues, comments

    try:
        if not raw_content:
            raise ValueError("No content received (Network/Timeout error)")
        parsed, status, issues, comments = _parse(raw_content)
    except Exception as e:
        # optional retry
        if retry_on_parse_error and retry_on_parse_error > 0:
            print(f"   [Mistral] Validation parsing failed ({e}). Retrying...")
            try:
                retry_raw, retry_dur = _call_once()
                duration += retry_dur
                raw_content = raw_content + "\n\n---RETRY---\n\n" + retry_raw
                parsed, status, issues, comments = _parse(retry_raw)
            except Exception as retry_e:
                print(f"   [Mistral] Retry also failed: {retry_e}")
                parsed = None
                status = "parse_error"
                issues = []
                comments = f"Validierungsmodell (Mistral) hat kein gültiges JSON zurückgegeben. Error: {retry_e}"
        else:
            parsed = None
            status = "parse_error"
            issues = []
            comments = f"Validierungsmodell (Mistral) hat kein gültiges JSON zurückgegeben. Error: {e}"

    return {
        "status": status,
        "issues": issues,
        "comments": comments,
        "raw_response": raw_content,
        "duration_seconds": round(duration, 3),
        "model": model,
        "provider": "mistral",
        "parsed": parsed,
    }


def semantic_validate_openai(
    image_path: str,
    extracted_data: Dict[str, Any],
    model: str = "gpt-4o",
    *,
    temperature: float = 0.0,
    max_tokens: int = 1200,
) -> Dict[str, Any]:
    """
    OpenAI vision-based semantic validation.

    Enforces response_format={"type":"json_object"} for robust parsing.
    """
    client = get_openai_client()
    encoded_image = _encode_image(image_path)
    system_prompt, user_prompt = _build_prompt(extracted_data)

    start_time = time.time()
    response = client.chat.completions.create(
        model=model,
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
        temperature=temperature,
        response_format={"type": "json_object"},
        max_tokens=max_tokens,
    )
    duration = time.time() - start_time

    raw_content = response.choices[0].message.content

    try:
        parsed = json.loads(raw_content)
        status = parsed.get("status", "uncertain")
        issues = parsed.get("issues", []) or []
        comments = parsed.get("comments", "")
    except Exception:
        parsed = None
        status = "parse_error"
        issues = []
        comments = "Validierungsmodell (OpenAI) hat kein gültiges JSON zurückgegeben."

    return {
        "status": status,
        "issues": issues,
        "comments": comments,
        "raw_response": raw_content,
        "duration_seconds": round(duration, 3),
        "model": model,
        "provider": "openai",
        "parsed": parsed,
    }