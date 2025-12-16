# main.py

from framework.extraction.extractor_gpt import GPTVisionExtractor
from framework.extraction.extractor_pixtral import PixtralVisionExtractor

from framework.scheme import get_urlaubsantrag_schema
from framework.validation.scheme_validation import validate_scheme
from framework.validation.rule_validation import validate_rules
from framework.validation.semantic_validation import semantic_validate
from framework.validation.cross_model_validation import validate_cross_model

from framework.pipeline.aggregator import aggregate_validation, save_result_to_file


if __name__ == "__main__":
    image_path = "tests/test_documents/Urlaubsantrag-Vorlage.png"

    specs = get_urlaubsantrag_schema()

    # A) Extraktion A (GPT)
    extractor_a = GPTVisionExtractor(model="gpt-4o")
    extraction_a = extractor_a.extract_from_image(image_path)
    json_a = extraction_a["data"]

    # B) Extraktion B (Pixtral)
    extractor_b = PixtralVisionExtractor(model="pixtral-large-latest")
    extraction_b = extractor_b.extract_from_image(image_path)
    json_b = extraction_b["data"]

    # 1) Schema-Validation (primär auf A, optional zusätzlich auf B)
    schema_result = validate_scheme(json_a, specs, allow_extra_keys=True)

    # 2) Regelvalidierung (auf A)
    rule_result = validate_rules(json_a)

    # 3) Semantische Validierung (validiert A gegen Dokument)
    sem_result = semantic_validate(
        image_path=image_path,
        extracted_data=json_a,
        model="pixtral-large-latest",
    )

    # 4) Cross-Model (A ↔ B)
    cross_result = validate_cross_model(json_a, json_b, specs)

    # 5) Aggregation
    pipeline_result = aggregate_validation(
        image_path=image_path,
        extraction_result={
            "extractor_a": extraction_a,
            "extractor_b": extraction_b,
            "data": json_a,  # primärer Output bleibt A
        },
        schema_result=schema_result,
        rule_result=rule_result,
        semantic_result=sem_result,
        cross_model_result=cross_result,
    )

    output_path = save_result_to_file(pipeline_result, output_dir="results")
    print(f"Ergebnis gespeichert unter: {output_path}")
