import base64
import json
import time
from pathlib import Path
from typing import Any, Dict

from framework.models.openai_client import get_openai_client
from framework.scheme import FieldSpec


def _encode_image(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    with path.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def schema_to_example(schema: Dict[str, FieldSpec]) -> str:
    """
    Converts FieldSpec schema into a JSON example structure for prompting.
    """
    example = {}
    for name, spec in schema.items():
        dt = spec.dtype
        if dt == "bool":
            example[name] = False
        elif dt == "int":
            example[name] = 0
        elif dt == "float":
            example[name] = 0.0
        elif dt == "object":
            example[name] = {}
        else:
            example[name] = ""
    return json.dumps(example, indent=2, ensure_ascii=False)


class GPTVisionExtractor:
    """
    Schema-aware vision extractor using OpenAI GPT models.

    Extracts structured JSON based on a dynamically supplied schema and document type.
    """

    def __init__(self, model: str = "gpt-4o"):
        self.client = get_openai_client()
        self.model = model

    def extract_from_image(
        self,
        image_path: str,
        schema: Dict[str, FieldSpec],
        doc_type: str,
    ) -> Dict[str, Any]:
        encoded_image = _encode_image(image_path)
        schema_example = schema_to_example(schema)

        system_prompt = (
            "Du bist ein KI-Extraktionssystem für Verwaltungsdokumente.\n"
            "Deine Aufgabe ist es, strukturierte Felder aus dem Dokument zu extrahieren.\n\n"
            "Regeln:\n"
            "- Antworte ausschließlich mit gültigem JSON\n"
            "- Verwende nur die Felder aus dem Schema\n"
            "- Verwende Kleinbuchstaben und Unterstriche für Keys\n"
            "- Gib alle Felder aus, auch wenn sie leer sind\n"
            "- Wenn ein Wert fehlt oder nicht lesbar ist, verwende leere Strings, false oder null\n"
            "- Erfinde keine Werte\n"
        )

        user_prompt = (
            f"Dokumenttyp: {doc_type}\n\n"
            "Das Dokument folgt diesem Schema:\n\n"
            f"{schema_example}\n\n"
            "Extrahiere die Werte aus dem Bild und fülle das Schema entsprechend aus."
        )

        start_time = time.time()

        response = self.client.chat.completions.create(
            model=self.model,
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
            temperature=0.0,
            response_format={"type": "json_object"},
            max_tokens=1500,
        )

        duration = time.time() - start_time
        raw_content = response.choices[0].message.content

        try:
            data = json.loads(raw_content)
        except Exception:
            data = {}

        return {
            "data": data,
            "raw_response": raw_content,
            "duration_seconds": round(duration, 3),
            "model": self.model,
            "doc_type": doc_type,
        }
