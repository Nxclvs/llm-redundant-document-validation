# scripts/batch_run.py

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from framework.experiment_config import get_experiment, list_experiment_names
from framework.extraction.extractor_gpt import GPTVisionExtractor
from framework.extraction.extractor_pixtral import PixtralVisionExtractor

from framework.validation.scheme_validation import validate_scheme
from framework.validation.semantic_validation import semantic_validate
from framework.validation.cross_model_validation import validate_cross_model
from framework.validation.multi_stage_validation import multi_stage_semantic_validate
from framework.pipeline.aggregator import aggregate_validation, save_result_to_file

from framework.schemes.registry import get_schema_for_type
from framework.validation.rule_registry import get_rules_for_type


SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".webp"}

PREFIX_TO_TYPE = {
    "REQ": "urlaubsantrag",
    "INV": "rechnung",
    "EXP": "reisekosten",
    "NOT": "bescheid",
    "MEL": "meldebescheinigung",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def iter_images(folder: Path) -> List[Path]:
    return sorted(
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXT
    )


def safe_exp_folder(name: str) -> str:
    s = "".join(c for c in (name or "") if c.isalnum() or c in ("-", "_", "."))
    return s or "experiment"


def detect_doc_type_from_filename(img_path: Path) -> Optional[str]:
    stem = img_path.stem
    prefix = stem.split("_", 1)[0].strip().upper()
    return PREFIX_TO_TYPE.get(prefix)


def detect_doc_type(primary_json: Dict[str, Any], img_path: Path) -> str:
    # 1) filename prefix
    dt = detect_doc_type_from_filename(img_path)
    if dt:
        return dt

    # 2) extracted JSON field 
    t = (primary_json.get("typ") or "").strip().lower()
    if t:
        
        if "bescheid" in t:
            return "bescheid"
        return t

    
    parent = img_path.parent.name.strip().lower()
    if parent:
        return parent

    return "unknown"


def build_extractor(cfg: Dict[str, Any]):
    provider = (cfg.get("provider") or cfg.get("type") or "").strip().lower()
    model = cfg.get("model")

    if not provider:
        raise ValueError(f"Extractor config missing provider/type: {cfg}")
    if not model:
        raise ValueError(f"Extractor config missing model: {cfg}")

    if provider == "openai":
        return GPTVisionExtractor(model=model)
    if provider == "mistral":
        return PixtralVisionExtractor(model=model)

    raise ValueError(f"Unknown extractor provider/type: {provider} (cfg={cfg})")


def build_validator_callable(cfg: Dict[str, Any], defaults: Dict[str, Any] | None = None):
    defaults = defaults or {}
    provider = (cfg.get("provider") or cfg.get("type") or "").strip().lower()
    model = cfg.get("model")

    if not provider:
        raise ValueError(f"Validator config missing provider/type: {cfg}")
    if not model:
        raise ValueError(f"Validator config missing model: {cfg}")

    temperature = float(cfg.get("temperature", defaults.get("temperature", 0.0)))
    max_tokens = int(cfg.get("max_tokens", defaults.get("max_tokens", 1200)))
    retry_on_parse_error = int(cfg.get("retry_on_parse_error", defaults.get("retry_on_parse_error", 0)))

    def _call(image_path: str, extracted_data: dict):
        return semantic_validate(
            image_path=image_path,
            extracted_data=extracted_data,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            retry_on_parse_error=retry_on_parse_error,
        )

    return _call


def skipped_result(kind: str, reason: str) -> Dict[str, Any]:
    return {
        "is_valid": True,
        "violations": [],
        "skipped": True,
        "kind": kind,
        "reason": reason,
    }


def main():
    parser = argparse.ArgumentParser(description="Batch runner for redundancy-based document validation")
    parser.add_argument("--input", required=False, help="Input folder with images")
    parser.add_argument("--output", default="results", help="Base output folder")
    parser.add_argument("--config", default="config/experiments.json", help="Path to experiments config JSON")
    parser.add_argument("--experiment", required=False, help="Experiment name from config")
    parser.add_argument("--list-experiments", action="store_true", help="List experiment names and exit")

    args = parser.parse_args()

    if args.list_experiments:
        names = list_experiment_names(args.config)
        print("Available experiments:")
        for n in names:
            print(f" - {n}")
        return

    if not args.input:
        raise ValueError("Please provide --input (folder with images).")
    if not args.experiment:
        raise ValueError("Please provide --experiment (or use --list-experiments).")

    config_path = Path(args.config)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    input_dir = Path(args.input)
    if not input_dir.exists():
        raise FileNotFoundError(f"Input folder not found: {input_dir}")

    exp = get_experiment(str(config_path), args.experiment)

    base_output_dir = Path(args.output)
    exp_name = exp.get("name", "experiment")
    output_dir = base_output_dir / safe_exp_folder(exp_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    #index.jsonl for metrics
    index_path = output_dir / "index.jsonl"
    index_path.touch(exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    started_at = now_iso()
    config_hash = sha256_file(config_path)

    extractor_cfgs = exp.get("extractors", [])
    primary_id = exp.get("primary_extractor")

    extractors: Dict[str, Any] = {}
    for ecfg in extractor_cfgs:
        eid = ecfg.get("id")
        if not eid:
            raise ValueError(f"Extractor config missing 'id': {ecfg}")
        extractors[eid] = build_extractor(ecfg)

    if primary_id not in extractors:
        raise ValueError(f"primary_extractor '{primary_id}' not in extractors: {list(extractors.keys())}")

    validator_cfgs = exp.get("validators", [])
    validator_defaults = exp.get("validator_defaults", {}) or {}
    validators = [build_validator_callable(vcfg, validator_defaults) for vcfg in validator_cfgs]

    images = iter_images(input_dir)
    if not images:
        print(f"No images found in {input_dir}.")
        return

    manifest_path = output_dir / "run_manifest.json"
    manifest = {
        "run_id": run_id,
        "experiment": exp_name,
        "started_at": started_at,
        "finished_at": None,
        "config_path": str(config_path),
        "config_hash": config_hash,
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "num_documents": len(images),
        "primary_extractor": primary_id,
        "extractors": extractor_cfgs,
        "validators": validator_cfgs,
    }
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Run ID: {run_id}")
    print(f"Experiment: {exp_name}")
    print(f"Primary extractor: {primary_id}")
    print(f"Extractors: {list(extractors.keys())}")
    print(f"Validator stages: {len(validators)}")
    print(f"Documents: {len(images)}")
    print(f"Output: {output_dir}")
    print(f"Index: {index_path}")
    print(f"Manifest: {manifest_path}")

    for i, img_path in enumerate(images, start=1):
        print(f"\n[{i}/{len(images)}] {img_path}")

        
        doc_type = detect_doc_type(primary_json={}, img_path=img_path)

        # Route schema + rules
        try:
            schema = get_schema_for_type(doc_type)
        except Exception:
            schema = None

        if schema is None:
            schema_result = skipped_result("schema_validation", f"No schema registered for doc_type='{doc_type}'")
            rule_result = skipped_result("rule_validation", f"No rule set registered for doc_type='{doc_type}'")
        else:
            rules = get_rules_for_type(doc_type)

        # 1) Run extractors 
        extraction_results: Dict[str, Dict[str, Any]] = {}
        json_by_extractor: Dict[str, Dict[str, Any]] = {}

        for eid, ex in extractors.items():
            r = ex.extract_from_image(
                image_path=str(img_path),
                schema=(schema or {}),
                doc_type=doc_type,
            )
            extraction_results[eid] = r
            json_by_extractor[eid] = r.get("data", {}) or {}

        primary_json = json_by_extractor.get(primary_id, {}) or {}

        
        if schema is not None:
            schema_result = validate_scheme(primary_json, schema, allow_extra_keys=True)

            violations: List[Dict[str, Any]] = []
            for rule_fn in rules:
                violations.extend(rule_fn(primary_json) or [])

            rule_result = {
                "is_valid": not any((v.get("severity") or "").lower() == "error" for v in violations),
                "violations": violations,
            }

        
        if validators:
            sem_result = multi_stage_semantic_validate(
                validators=validators,
                image_path=str(img_path),
                extracted_data=primary_json,
            )
        else:
            sem_result = {
                "status": "skipped",
                "issues": [],
                "comments": "Semantic validation disabled for this experiment.",
                "stages": [],
                "duration_seconds_total": 0.0,
                "models_used": [],
                "providers_used": [],
                "stats": {"errors": 0, "warnings": 0, "infos": 0},
            }

        # 3) Cross-model redundancy 
        cross_result = None
        if schema is not None and len(json_by_extractor) >= 2:
            merged = {
                "is_consistent": True,
                "conflicts": [],
                "stats": {"errors": 0, "warnings": 0, "infos": 0},
            }

            for eid, js in json_by_extractor.items():
                if eid == primary_id:
                    continue
                cm = validate_cross_model(primary_json, js, schema)
                merged["conflicts"].extend(cm.get("conflicts", []))
                for k in ("errors", "warnings", "infos"):
                    merged["stats"][k] += int((cm.get("stats", {}) or {}).get(k, 0) or 0)

            merged["is_consistent"] = (merged["stats"]["errors"] == 0 and merged["stats"]["warnings"] == 0)
            cross_result = merged

        # 4) Aggregation
        pipeline_result = aggregate_validation(
            image_path=str(img_path),
            extraction_result={
                "run_id": run_id,
                "doc_type": doc_type,
                "experiment": {
                    "name": exp_name,
                    "primary_extractor": primary_id,
                    "extractors": extractor_cfgs,
                    "validators": validator_cfgs,
                },
                "extractors": extraction_results,
                "data": primary_json,
            },
            schema_result=schema_result,
            rule_result=rule_result,
            semantic_result=sem_result,
            cross_model_result=cross_result,
        )

        # 5) Save result file
        out_file = save_result_to_file(pipeline_result, output_dir=str(output_dir))

        # 6) Append to index.jsonl
        idx_entry = {
            "run_id": run_id,
            "experiment": exp_name,
            "doc_type": doc_type,
            "document": {"name": img_path.name, "path": str(img_path)},
            "created_at": pipeline_result.get("created_at", now_iso()),
            "final_status": pipeline_result.get("final_status"),
            "result_file": str(Path(out_file).resolve()),
            "summary": pipeline_result.get("summary"),
        }
        with index_path.open("a", encoding="utf-8") as idx:
            idx.write(json.dumps(idx_entry, ensure_ascii=False) + "\n")

    manifest["finished_at"] = now_iso()
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("\nBatch abgeschlossen.")


if __name__ == "__main__":
    main()
