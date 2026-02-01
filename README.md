
# LLM Redundant Document Validation Framework
### Governance and Auditability in AI-Supported Administrative Processes

This repository contains the prototype framework and experimental setup for the Master's thesis on **"Governance and Revisionssicherheit in KI-gestützten Verwaltungsprozessen"**. 

The framework implements an architecture that combines probabilistic extraction models (LLMs like GPT-4o) with deterministic rule sets and redundant semantic validators (e.g., Pixtral/Mistral). The primary goal is not merely to maximize extraction accuracy, but to ensure **Audit Readiness** and prevent *Silent Failures* in sensitive administrative workflows.

---

## 🔬 Research Motivation

LLM-based document extraction is increasingly applied in administrative and audit-relevant contexts. However, many existing approaches rely on single-pass extraction without systematic validation, which limits transparency and trustworthiness.

**Core Research Question:**
> *How can extracted information be validated in a transparent, robust, and audit-compliant way?*

To answer this, the framework combines:
- **Schema-driven extraction** using Large Language Models (LLMs).
- **Deterministic validation layers** (Hard Gates: schema compliance & rules).
- **Semantic validation** using independent Vision-Language-Models (Soft Gates).
- **Aggregation logic** for explainable final decisions (`valid` vs. `review_needed`).

The framework explicitly focuses on validating the **quality of extraction**, not the business correctness of the underlying document.

---

## 🏛 Architecture & Concepts

### The Pipeline

1. **Extraction (GPT-4o)**
   Generates structured JSON from document images based on a strict schema definition.

2. **Validation Layers**
   * **Schema Validation:** Checks for required keys, missing fields, and data types.
   * **Rule Validation:** Deterministic checks (e.g., regex patterns, logical consistency).
   * **Semantic Validation:** An independent model (Pixtral-Large) verifies the extracted JSON against the original image to detect hallucinations.

3. **Aggregation**
   Combines all signals into a final status and generates an audit-proof JSON report.

### Key Concept: Extraction vs. Business Validation

* **Extraction Validation (In Scope):** Did the model correctly extract what is visible?
* **Business Validation (Out of Scope):** Is the request legally valid? (e.g., missing signature). These are logged as `info` but do not invalidate the extraction quality.

---

## 📂 Project Structure

The project structure strictly separates core logic (`src`), data (`data`), and execution scripts (`scripts`).

```text
.
├── tests/                   
│   └── datasets/            # test data
├── results/ 
│              
├── framework/                # Framework source code
│   ├── extraction/           # Extractor stage
│   ├── metrics/              # Predefined Metrics
│   ├── models/               # LLM Models
│   ├── pipeline/
│   ├── schemes/              # Defined shemes
    └── validation/   
├── scripts/                # Executable scripts
│   ├── generate_test_data.py    # Synthetic corpus generation
│   └── batch_run.py             # Execution of validation pipelines
│               
├── config                  # Experiment configuration
├── requirements.txt        # Python dependencies
└── README.md               # Documentation
```

---

## 🛠 Installation & Setup

**Prerequisites:** Python 3.9+

Clone the repository:
```bash
git clone https://github.com/Nxclvs/llm-redundant-document-validation.git
cd llm-redundant-document-validation
```

Install dependencies:
```bash
pip install -r requirements.txt
```

**Configuration:**
The project uses a local configuration file for API keys.
Create a file named `localconfig.py` in the root directory:
Example `localconfig.py`:

```python
config = {
    "gpt": "YOUR_OPENAI_API_KEY",
    "mistral": "YOUR_MISTRAL_API_KEY",
}
```

---

# ▶️ Usage

## 1. Generate Synthetic Data
Generates test documents (invoices, applications, notifications) to populate `tests/datasets/`.

```bash
python generate_data.py --input <DATASET NAME> --num-per-type <NUM PER TYPE> --seed <SEED>
```

## 2. Run Experiment Batch
The main execution is handled via `batch_run.py`. You must specify the input dataset folder (located inside `tests/datasets/`) and the experiment ID (defined in `config/experiments.json`).

**Syntax:**
```bash
python batch_run.py --input <DATASET_FOLDER> --experiment <EXPERIMENT_ID>
```

### Example: Run Baseline (E1V0)
Executes the pipeline with extraction and deterministic rules only (Hard Gate).

```bash
python batch_run.py --input generated_de_v1 --experiment E1V0_gpt_only_no_validation
```

### Example: Run Mixed Validation (E1V2b)
Executes the full pipeline including heterogeneous semantic validation (GPT-4o + Pixtral).

```bash
python batch_run.py --input generated_de_v1 --experiment E1V2b_mixed_gpt_pixtral
```

**Results** are saved to `results/<EXPERIMENT_ID/` as structured JSON files.

---

## 🔬 Evaluation & Metrics

The framework evaluates performance based on Governance Capabilities:

| Metric                     | Description                                                                 |
|----------------------------|-----------------------------------------------------------------------------|
| Field Accuracy             | Exact match of extracted fields against Ground Truth.                       |
| Audit Readiness Rate (ARR) | Percentage of documents processed without human intervention (`valid`).     |
| Semantic Stability         | Measure of agreement between multiple validation instances (Inter-Annotator Agreement). |

### Experiment Configurations

| ID    | Name         | Description                                                                 |
|-------|--------------|-----------------------------------------------------------------------------|
| E1V0  | Baseline     | Extraction + Hard Gate (Rules) only.                                        |
| E1V1  | Semantic     | E1V0 + Single Semantic Validator (Pixtral).                                  |
| E1V2a | Twostage     | Homogeneous Redundancy (Model checks itself/clone).                         |
| E1V2b | Mixed        | Heterogeneous Redundancy (GPT-4o checks Pixtral).                           |

---

## 🛡 License & Scientific Context

This project is part of an academic Bachelor's thesis.
Code and data are available under the **MIT License** unless otherwise noted.

**Anti-Sycophancy Design:**
To mitigate model bias, the semantic validation stage receives the original document and the extracted JSON but is explicitly instructed to verify independently rather than confirm prior outputs.

**Out of Scope:**
The framework does not make legal decisions or replace human case workers. It acts as a technical pre-filter to sort documents into automated or manual processing queues.
