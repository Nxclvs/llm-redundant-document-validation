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
