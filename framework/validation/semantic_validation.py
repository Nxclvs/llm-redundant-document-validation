import base64
import time
import json
from pathlib import Path
from typing import Any, Dict
from framework.models.mistral_client import get_mistral_client

def _encode_image(image_path: str) -> str:
    """
    Reads an image file and return it base64 encoded
    """

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    with path.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
    


def semantic_validate(
    image_path: str,
    extracted_data: Dict[str, Any],
    model: str = "pixtral-large-latest",
) -> Dict[str, Any]:
    """
    Calling validation LLM
    - View access to original Document
    - gets the JSON from the extraction
    - First comes self extracting the relevant information from the document
      and afterwards comparing with the JSON (Anti-Sycophancy)
    - Output comes in structured JSON
    
    Output format example:

        {
        "status": "valid" | "invalid" | "uncertain" | "parse_error",
        "issues": [
            {"field": "urlaubstage", "type": "mismatch", "message": "..."}
        ],
        "comments": "Kurze Zusammenfassung...",
        "raw_response": "<Originaltext der Modellantwort>",
        "duration_seconds": 1.234,
        "model": "pixtral-large-latest"
    }
    """
    client = get_mistral_client()
    encoded_image = _encode_image(image_path)

    #Format extracted JSON for LLM-Prompt
    extracted_json_str = json.dumps(extracted_data, indent=2, ensure_ascii=False)
    
    system_prompt = (
        "Du bist ein Validierungsmodell für verwaltungsnahe Dokumente. "
        "Deine Aufgabe ist es, extrahierte Felder kritisch und unabhängig "
        "gegen das Originaldokument zu prüfen. "
        "Sei explizit in deinen Bewertungen und melde auch Unsicherheiten."
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
            "type": "<error_type (z.B. 'mismatch', 'missing', 'uncertain')>",
            "severity": "<'error' | 'warning' | 'info'>",
            "message": "<kurze Beschreibung der Abweichung, Unsicherheit oder Information>"
            }}
        ],
        "comments": "<kurze Gesamtbewertung der Extraktion>"
        }}

        Wenn ein Element nicht eindeutig im Dokument erkennbar ist, formuliere es als „nicht sichtbar / nicht eindeutig erkennbar“ und verwende severity: warning nur dann, wenn dieses Feld für die Validität relevant ist.

        Definitionen:
        - Verwende 'error' für echte Fehler (z. B. falscher Wert, wichtiges Feld fehlt).
        - Verwende 'warning' für Unsicherheiten (schwer lesbar, Kontext unklar).
        - Verwende 'info' für Hinweise, bei denen alles korrekt ist, du aber etwas kommentieren möchtest
        (z. B. ein Feld ist im Dokument leer und wurde korrekt als leer extrahiert).

        Regeln:
        - Wenn alle Werte korrekt erscheinen und es nur 'info'-Einträge gibt → "status": "valid".
        - Wenn Unsicherheiten bestehen, aber keine klaren Fehler → "status": "uncertain".
        - Wenn wesentliche Werte klar falsch oder widersprüchlich sind → "status": "invalid".
        - Nimm ein Feld nur dann in 'issues' auf, wenn es für die Validität relevant ist.
        - Schreibe KEINEN zusätzlichen Text außerhalb des JSON und verwende KEINE Markdown-Codeblöcke (keine ```-Syntax).

        Hier sind die vom Extraktionsmodell gelieferten JSON-Daten:
        {extracted_json_str}
    """


    # TODO Implementieren - inkl. Anti-Sycophancy-Prompt
    start_time = time.time()
    response = client.chat.complete(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{encoded_image}"
                        }, 
                    },
                ],
            },
        ],
        temperature=0.0
    )
    duration = time.time() - start_time

    def _extract_json_string(text: str) -> str:
        """
        Versucht, aus einer Modellantwort eine reine JSON-Struktur herauszuschneiden.
        Handhabt u.a. Markdown-Codeblöcke (```json ... ```).
        """
        cleaned = text.strip()

        # Fall 1: Antwort in ```json ... ``` oder ``` ... ```
        if cleaned.startswith("```"):
            # Entferne führende ```json oder ``` 
            if cleaned.startswith("```json"):
                cleaned = cleaned[len("```json"):].strip()
            else:
                cleaned = cleaned[len("```"):].strip()
            # Entferne abschließende ```
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()

        # Fall 2: Sicherheitshalber nur den Bereich zwischen erstem '{' und letztem '}' nehmen
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]

        return cleaned


    raw_content = response.choices[0].message.content

    try:
        json_str = _extract_json_string(raw_content)
        parsed = json.loads(json_str)
        status = parsed.get("status", "uncertain")
        issues = parsed.get("issues", [])
        comments = parsed.get("comments", "")
    except json.JSONDecodeError:
        parsed = None
        status = "parse_error"
        issues = []
        comments = "Validierungsmodell hat kein gültiges JSON zurückgegeben."

    return {
        "status": status,
        "issues": issues,
        "comments": comments,
        "raw_response": raw_content,
        "duration_seconds": round(duration, 3),
        "model": model,
        "parsed": parsed
    }