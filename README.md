# LLM Redundant Document Validation

Framework for redundancy-based validation of LLM-driven document extraction in audit-compliant administrative workflows.

---

## Overview

This repository contains a prototype framework for **schema-driven extraction** and **multi-stage, redundancy-based validation** of information from administrative documents (e.g., forms used in administrative processes).

The framework addresses a central challenge of LLM-based document processing:

**How can extracted information be validated in a transparent, robust, and audit-compliant way?**

To answer this, the framework combines:

- schema-driven extraction using Large Language Models (LLMs),
- deterministic validation layers (schema compliance and rule-based checks),
- semantic validation using an independent LLM,
- aggregation logic for explainable final decisions,
- and a structured JSON output suitable for audit and evaluation.

The framework explicitly focuses on validating the **quality of extraction**, not the business correctness of the underlying document.

---

## Key Concepts

### Extraction validation vs. business validation

The framework strictly distinguishes between two validation perspectives:

- **Extraction validation (in scope):**  
  *Did the model correctly extract what is visible in the document?*

- **Business validation (out of scope):**  
  *Is the document/request complete, correct, or legally valid according to administrative rules?*

Business-related issues (e.g., missing signatures) are documented as **informational findings**, but do not automatically invalidate extraction quality.

---

## Architecture

### High-level pipeline

1. **Extraction**
   - LLM Extractor A (currently GPT-based)
   - Output: structured JSON according to a predefined schema

2. **Validation Layer**
   - **Schema validation**
     - required keys present
     - missing or unexpected fields
     - basic type consistency
   - **Rule validation**
     - deterministic plausibility checks (e.g., date ranges)
     - extraction-oriented rules only
   - **Semantic validation**
     - independent LLM verifies extracted JSON against the original document
     - anti-sycophancy prompt design to reduce model bias

3. **Aggregation**
   - combines all validation signals
   - determines final status:
     - `valid`
     - `review_needed`
     - `invalid`
   - produces an audit-friendly result JSON

---

## Project Structure

```text
framework/
  extraction/
    extractor_gpt.py
  models/
    openai_client.py
    mistral_client.py
  validation/
    schema_validation.py
    rule_validation.py
    semantic_validation.py
  pipeline/
    aggregator.py

tests/
  test_documents/
    (example images)

results/
  (generated output files)

main.py


# Setup

## Requirements

- Python 3.10 or newer recommended
- OpenAI Python SDK
- Mistral AI Python SDK

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

API keys must be stored locally and must not be committed to the repository.

Expected directory structure:

```
config/
  localconfig.py   # ignored by git
```

Example `localconfig.py`:

```python
config = {
    "gpt": "YOUR_OPENAI_API_KEY",
    "mistral": "YOUR_MISTRAL_API_KEY",
}
```

## Usage

Run the pipeline on a single document:

```bash
python main.py
```

The pipeline performs the following steps:

1. Extracts structured data from the document using an LLM.
2. Validates schema compliance of the extracted JSON.
3. Applies deterministic rule-based consistency checks.
4. Performs semantic validation using an independent LLM.
5. Aggregates all validation signals.
6. Stores a structured JSON result in the `results/` directory.

## Output Format

Each pipeline run produces a structured JSON file containing:

- document metadata
- extraction output and duration
- schema validation results
- rule validation results
- semantic validation results and duration
- aggregated final status and summary

**Example (shortened):**

```json
{
  "final_status": "valid",
  "summary": "Dokument: ... | Schema-Validation: ... | Rule-Validation: ... | Semantische Validation: ...",
  "extraction": {...},
  "schema_validation": {...},
  "rule_validation": {...},
  "semantic_validation": {...}
}
```

The output is designed to be audit-friendly and suitable for further evaluation.

---

# Scientific Notes

## Research Motivation

LLM-based document extraction is increasingly applied in administrative and audit-relevant contexts.
However, many existing approaches rely on single-pass extraction without systematic validation, which limits transparency and trustworthiness.

Typical shortcomings include:

- lack of redundancy,
- absence of explicit validation layers,
- insufficient explainability in audit scenarios.

## Research Objective

The objective of this work is the design and evaluation of a redundancy-based validation framework for LLM-driven document extraction that:

- improves robustness through multiple validation stages,
- separates extraction validation from business validation,
- supports auditability and explainability,
- enables systematic analysis of redundancy effects.

## Methodological Scope

The framework investigates:

- schema-driven extraction consistency,
- deterministic rule-based validation,
- semantic validation using independent LLMs,
- aggregation of heterogeneous validation signals,
- (planned) cross-model redundancy between multiple extractors.

It explicitly does not aim to replace domain-specific business logic or administrative decision-making.

## Anti-Sycophancy Design

To mitigate model bias (sycophancy), the semantic validation stage:

- receives both the original document and the extracted JSON,
- performs an independent verification step,
- is instructed to extract and compare rather than confirm prior outputs.

This design reduces the risk of uncritical agreement with earlier model outputs.

## Evaluation Perspective

The framework enables systematic evaluation of redundancy-based validation strategies along several dimensions:

- **Extraction correctness:** Agreement between extracted JSON and document content.
- **Redundancy effects:** Agreement or disagreement between multiple extractors or validators.
- **Validation signal quality:** Number and severity of errors, warnings, and informational findings.
- **Robustness:** Stability of results across different documents and model configurations.
- **Runtime overhead:** Latency introduced by additional validation stages.

The evaluation focuses on extraction trustworthiness rather than business correctness.

## Validation Checklist

For each processed document, the following validation steps are executed:

| Step                     | Content                                                                 |
|--------------------------|-------------------------------------------------------------------------|
| Schema compliance check  | All expected keys present, required fields not empty, basic type consistency |
| Rule-based validation    | Deterministic plausibility checks, extraction-oriented rules only       |
| Semantic validation      | Independent LLM verification against the original document, anti-sycophancy prompt design applied, findings classified by severity (error, warning, info) |
| Aggregation              | Combination of all validation signals, final status: valid, review_needed, or invalid |

## Out of Scope

The framework explicitly does not cover:

- business or legal correctness of documents,
- approval or rejection of administrative requests,
- domain-specific decision logic,
- replacement of human decision-makers.

Such aspects may be logged as informational findings but are not used to invalidate extraction quality.

---

# Status and Roadmap

## Implemented

- Schema-driven LLM extraction
- Central schema definition
- Schema compliance validation
- Rule-based extraction validation
- Semantic validation with independent LLM
- Aggregated decision logic
- Structured JSON result output

## Planned

- Cross-model redundancy (Extractor B + JSON comparison)
- Batch evaluation over multiple documents
- Extended evaluation metrics
- Additional administrative document templates
