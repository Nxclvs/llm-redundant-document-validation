import json

from framework.extraction.extractor_gpt import GPTVisionExtractor
from framework.validation.rule_validation import validate_rules
from framework.validation.semantic_validation import semantic_validate
from framework.pipeline.aggregator import aggregate_validation, save_result_to_file
from framework.scheme import get_urlaubsantrag_schema
from framework.validation.scheme_validation import validate_scheme


if __name__ == "__main__":
    image_path = "tests/test_documents/Urlaubsantrag-Vorlage.png"  # Pfad anpassen

    # 1) Extraction
    extractor = GPTVisionExtractor(model="gpt-4o")
    extraction_result = extractor.extract_from_image(image_path)

    print("=== Extraktion ===")
    print("Modell:", extraction_result["model"])
    print("Dauer (s):", extraction_result["duration_seconds"])
    print("Daten:", extraction_result["data"])
    print()

    # 2) scheme validation
    specs = get_urlaubsantrag_schema()
    scheme_result = validate_scheme(
        data=extraction_result["data"],
        scheme_specs=specs,
        allow_extra_keys=True
    )

    # 2) rule based validation
    rule_result = validate_rules(extraction_result["data"])
    print("=== Regelbasierte Validierung ===")
    print(rule_result)
    print()

    # 3) semantic validation
    sem_result = semantic_validate(
        image_path=image_path,
        extracted_data=extraction_result["data"],
        model="pixtral-large-latest",
    )

    print("=== Semantische Validierung (Mistral/Pixtral) ===")
    print("Status:", sem_result["status"])
    print("Dauer (s):", sem_result["duration_seconds"])
    print("Issues:", sem_result["issues"])
    print("Comments:", sem_result["comments"])
    print()

    # 4) Aggregation
    pipeline_result = aggregate_validation(
        image_path=image_path,
        extraction_result=extraction_result,
        schema_result=scheme_result,
        rule_result=rule_result,
        semantic_result=sem_result,
        cross_model_result=None,
    )

    print("=== Aggregiertes Ergebnis ===")
    print("Finaler Status:", pipeline_result["final_status"])
    print("Summary:", pipeline_result["summary"])
    print()

    # 5) Speichern
    output_path = save_result_to_file(pipeline_result, output_dir="results")
    print(f"Ergebnis gespeichert unter: {output_path}")