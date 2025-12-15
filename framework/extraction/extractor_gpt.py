import base64
import json
import time
import os
from pathlib import Path
from typing import Any, Dict

from framework.models.openai_client import get_openai_client
from framework.scheme import get_urlaubsantrag_schema, scheme_example_from_specs


class GPTVisionExtractor:
    """
    Capable of:
    - Loading an image document
    - Calling gpt-4o (vision)
    - Strucuturized extraction of information in JSON
    """

    def __init__(self, model: str = "gpt-4o"):
        self.client = get_openai_client()
        self.model = model

    @staticmethod
    def _encode_image(image_path: str) -> str:
        """
        Reads an image file and returns it base64 encoded
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        with path.open("rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
        
    @staticmethod
    def _get_scheme_description() -> str:
        specs = get_urlaubsantrag_schema()
        scheme_example = scheme_example_from_specs(specs)
        return json.dumps(scheme_example, indent=2, ensure_ascii=False)

    
    def extract_from_image(self, image_path:str) -> Dict[str, Any]:
        """
        Executes the extraction:
        - Loading Image
        - Call gpt-4o
        - Parse JSON
        - Append Metadata


        Output:
        {
            "data": <extracted_json_dict>,
            "raw_response": "<raw-string from gpt>",
            "duration_seconds": <float>,
            "model": "<model name>"
        }
        """

        encoded_image = self._encode_image(image_path)

        scheme_description = self._get_scheme_description()

        system_prompt = (
            "Du extrahierst strukturierte Informationen aus Formularen.\n"
            "Gib die Ausgabe ausschließlich als gültiges JSON zurück.\n"
            "Verwende nur Kleinbuchstaben und Unterstriche für Keys, keine Umlaute.\n"
            "Halte dich strikt an die Keys des Schemas und gib alle Keys immer aus, auch wenn sie leer sind.\n"
            "Fülle Felder mit leeren Strings, false oder null, wenn etwas nicht vorhanden oder nicht lesbar ist.\n"
            "Lasse keine relevanten Felder weg."
        )


        user_text = (
            "Lies die Informationen aus dem folgenden Dokument aus und gib sie "
            "im beschriebenen JSON-Format zurück.\n\n"
            "Beispielschema (nur zur Orientierung, Werte an das Dokument anpassen):\n"
            f"{scheme_description}"
        )

        start_time = time.time()
        
        # api call

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role":"system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
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
        )
        duration = time.time() - start_time

        raw_content = response.choices[0].message.content

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError:
            # Fallback
            data = {}

        return {
            "data": data,
            "raw_response": raw_content,
            "duration_seconds": round(duration, 3),
            "model": self.model
        }