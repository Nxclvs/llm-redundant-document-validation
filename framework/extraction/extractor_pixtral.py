import base64
import json
import time
from pathlib import Path
from typing import Any, Dict

from framework.models.mistral_client import get_mistral_client
from framework.scheme import get_urlaubsantrag_schema, scheme_example_from_specs

class PixtralVisionExtractor:
    """
    Pixtral/Mistral based vision extractor
    """

    def __init__(self, model: str = "pixtral-large-latest"):
        self.model = model

    @staticmethod
    def _encode_image(image_path: str) -> str:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        with path.open("rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
        
    @staticmethod
    def _scheme_json_str() -> str:
        specs = get_urlaubsantrag_schema()
        example = scheme_example_from_specs(specs)
        return json.dumps(example, indent=2, ensure_ascii=False)
    
    def extract_from_image(self, image_path: str) -> Dict[str, Any]:
        client = get_mistral_client()
        encoded_image = self._encode_image(image_path)

        system_prompt = (
            "Du extrahierst strukturierte Informationen aus Formularen.\n"
            "Gib die Ausgabe ausschließlich als gültiges JSON zurück.\n"
            "Halte dich strikt an die Keys des Schemas und gib alle Keys immer aus, auch wenn sie leer sind.\n"
            "Wenn etwas nicht vorhanden oder nicht lesbar ist: nutze leere Strings, false oder null.\n"
            "Verwende nur Kleinbuchstaben und Unterstriche für Keys, keine Umlaute.\n"
            "Kein zusätzlicher Text, keine Markdown-Codeblöcke."
        )

        user_prompt = f"""
            Extrahiere die Felder aus dem Dokument gemäß diesem JSON-Schema (Beispielstruktur):
            {self._scheme_json_str()}

            Regeln:
            - Gib ausschließlich JSON aus (kein Markdown, keine Erklärtexte).
            - Nutze exakt diese Keys (inkl. verschachteltes kontrollkaesten-Objekt).
            """
        
        start = time.time()
        resp = client.chat.complete(
            model = self.model,
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}}
                    ],
                },
            ],
            temperature=0.0
        )
        duration = time.time() - start

        raw_content = resp.choices[0].message.content

        # JSON parsing

        def _extract_json_string(text: str) -> str:
            cleaned = text.strip()
            if cleaned.startswith("```"):
                if cleaned.startswith("```json"):
                    cleaned = cleaned[len("```json"):].strip()
                else:
                    cleaned = cleaned[len("```"):].strip()
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()

            s = cleaned.find("{")
            e = cleaned.rfind("}")
            if s != -1 and e != -1 and e > s:
                cleaned = cleaned[s : e + 1]
            return cleaned

        parsed = None
        try: 
            parsed = json.loads(_extract_json_string(raw_content))
            data = parsed
        except json.JSONDecodeError:
            data = {}

        return {
            "data": data,
            "raw_response": raw_content,
            "duration_seconds": round(duration, 3),
            "model": self.model,
            "parsed": parsed
        }