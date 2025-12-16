from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import List

from framework.extraction.extractor_gpt import GPTVisionExtractor
from framework.extraction.extractor_pixtral import PixtralVisionExtractor

from framework.scheme import get_urlaubsantrag_schema
from framework.validation.scheme_validation import validate_scheme
from framework.validation.rule_validation import validate_rules
from framework.validation.semantic_validation import semantic_validate
from framework.validation.cross_model_validation import validate_cross_model
from framework.validation.multi_stage_validation import multi_stage_semantic_validate

from framework.pipeline.aggregator import aggregate_validation, save_result_to_file


SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def iter_images(folder: Path) -> List[Path]:
    paths = []
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXT:
            paths.append(p)
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input folder with images")
    parser.add_argument("--output", default="results", help="Output results folder")
    parser.add_argument("--gpt-model", default="gpt-4o", help="OpenAI Model for extraction")
    parser.add_argument("--pixtral-model", default="pixtral-large-latest", help="Pixtral Model for extraction and semantic validation")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    index_path = output_dir / "index.jsonl"

    specs = get_urlaubsantrag_schema()

    extractor_a = GPTVisionExtractor(model=args.gpt_model)
    extractor_b = PixtralVisionExtractor(model=args.pixtral_model)

    images = iter_images(input_dir)
    
    if not images:
        print(f"No images found in {input_dir}.")
        return
    
    print(f"Gefundene Dokumente: {len(images)}")
    print(f"Schreibe Ergebnisse nach: {output_dir}")
    print(f"Index-Datei: {index_path}")

    # appending mode (multiple document processing)

    with index_path.open("a", encoding="utf-8") as idx:
        for i, img_path in enumerate(images, start=1):
            print(f"\n[{i}/{len(images)}] {img_path}")

            extraction_a = extractor_a.extract_from_image(str(img_path))
            json_a = extraction_a.get("data", {}) or {}

            extraction_b = extractor_b.extract_from_image(str(img_path))
            json_b = extraction_b.get("data", {}) or {}

            scheme_result = validate_scheme(json_a, specs, allow_extra_keys=True)
            rule_result = validate_rules(json_a)

            def sem_stage_1(image_path: str, extracted_data: dict):
                return semantic_validate(image_path=image_path, extracted_data=extracted_data, model=args.pixtral_model)

            def sem_stage_2(image_path: str, extracted_data: dict):
                return semantic_validate(image_path=image_path, extracted_data=extracted_data, model=args.pixtral_model)

            sem_result = multi_stage_semantic_validate(
                validators=[sem_stage_1, sem_stage_2],
                image_path=str(img_path),
                extracted_data=json_a,
            )


            cross_result = validate_cross_model(json_a, json_b, specs)


            pipeline_result = aggregate_validation(
                image_path=str(img_path),
                extraction_result={
                    "extractor_a": extraction_a,
                    "extractor_b": extraction_b,
                    "data": json_a,
                },
                schema_result=scheme_result,
                rule_result=rule_result,
                semantic_result=sem_result,
                cross_model_result=cross_result,
            )

            out_file = save_result_to_file(pipeline_result, output_dir=str(output_dir))

            idx_entry = {
                "document": pipeline_result.get("document", {}),
                "created_at": pipeline_result.get("created_at"),
                "final_status": pipeline_result.get("final_status"),
                "result_file": str(out_file),
                "summary": pipeline_result.get("summary"),
            }
            idx.write(json.dumps(idx_entry, ensure_ascii=False) + "\n")

    print("\nBatch abgeschlossen.")

if __name__ == "__main__":
    main()