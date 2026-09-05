# MELD Na Calculator

> **Domain:** Gastroenterology, Hepatology & Clinical Nutrition  
> **Reference Guidelines & Standards:** `AASLD & ACG Clinical Practice Guidelines`

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg?logo=fastapi&logoColor=white)
![Audit Trail](https://img.shields.io/badge/Audit-HMAC--SHA256_Tamper--Evident-brightgreen.svg)
![Zero-PHI Guard](https://img.shields.io/badge/Guard-Zero--PHI_Outbound-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)

</div>

---

## 📖 What It Does

MELD-Na Calculator — Real clinical scoring implementations.

Implements:
  - MELD (original): Kamath et al. 2001
  - MELD-Na (2016):  UNOS revision incorporating serum sodium
  - MELD 3.0 (2023): Kim et al. — adds albumin and sex adjustment

All formulas use only Python stdlib (math).

DISCLAIMER: This is an educational/reference implementation.
It is NOT a substitute for clinical judgment. Always verify
scores against institutional protocols before clinical use.

---

## ⚙️ Key Capabilities & Algorithmic Modules

### 🔬 Analytical Functions

- **`calculate_meld()`**: Calculate the original MELD score (Kamath et al. 2001).

Parameters
----------
bilirubin : float   — serum bilirubin in mg/dL
inr       : float   — international normalized ratio
creatinine: float   — serum creatinine in mg/dL
dialysis  : bool    — True if patient received ≥ 2 dialysis sessions
                      in the past week

Returns
-------
int — MELD score, clamped to [1, 40]
- **`calculate_meld_na()`**: Calculate MELD-Na per the 2016 UNOS revision.

MELD-Na = MELD + 1.32 × (137 − Na) − 0.033 × MELD × (137 − Na)

The sodium correction is applied only when MELD > 11.
Sodium is clamped to [125, 137] mEq/L before use.

Parameters
----------
bilirubin  : float — serum bilirubin in mg/dL
inr        : float — international normalized ratio
creatinine : float — serum creatinine in mg/dL
sodium     : float — serum sodium in mEq/L
dialysis   : bool  — True if ≥ 2 dialysis sessions in past week

Returns
-------
int — MELD-Na score, clamped to [1, 40]
- **`calculate_meld_3()`**: Calculate MELD 3.0 (Kim et al., NEJM 2023).

MELD 3.0 = 4.56 × ln(bili) + 9.09 × ln(INR) + 11.14 × ln(creat)
           − 1.85 × ln(albumin) + 0.82 × (137 − Na)
           − 0.24 × (137 − Na) × ln(creat)
           + sex_bonus + 6

sex_bonus = 1.334 if female, 0 if male.

Parameters
----------
bilirubin  : float — serum bilirubin in mg/dL
inr        : float — international normalized ratio
creatinine : float — serum creatinine in mg/dL
sodium     : float — serum sodium in mEq/L
albumin    : float — serum albumin in g/dL
female     : bool  — True for female sex
dialysis   : bool  — True if ≥ 2 dialysis sessions in past week

Returns
-------
int — MELD 3.0 score, clamped to [1, 40]
- **`estimate_3month_mortality()`**: Return estimated 3-month mortality proportion for a given MELD score.

Based on Kamath & Wiesner et al. data. Returns a float in [0, 1].
- **`get_allocation_priority()`**: Return a human-readable allocation priority tier description.

---

## 📐 Mathematical Formulation & Logic

```text
  All formulas use only Python stdlib (math).
  Calculate the original MELD score (Kamath et al. 2001).
  Calculate MELD-Na per the 2016 UNOS revision.
  meld = calculate_meld(bilirubin, inr, creatinine, dialysis)
  Calculate MELD 3.0 (Kim et al., NEJM 2023).
```

---

## 💻 CLI Quickstart & Usage

### 1. Calculate MELD Scores
```bash
python cli.py calculate --bilirubin 2.5 --inr 1.8 --creatinine 1.5 --sodium 135
```

### 2. With MELD 3.0 (albumin + sex)
```bash
python cli.py calculate --bilirubin 2.5 --inr 1.8 --creatinine 1.5 \
    --sodium 135 --albumin 3.2 --female
```

### 3. JSON Output
```bash
python cli.py calculate --bilirubin 2.5 --inr 1.8 --creatinine 1.5 --sodium 135 --json
```

### 4. Batch Processing
```bash
python cli.py batch --input patients.csv --output scored.csv
```

### 5. Show Exception Points Info
```bash
python cli.py exceptions
```

### 6. Audit Task Evaluation
```bash
python cli.py audit --task-id TASK-001
```

### 7. Verify Audit Trail Integrity
```bash
python cli.py verify-audit
```

### 8. Start REST API Server
```bash
python cli.py serve --host 0.0.0.0 --port 8000
```

### Parameter Reference
| Parameter | Description | Required |
|:----------|:------------|:---------|
| `--bilirubin` | Serum bilirubin (mg/dL) | Yes |
| `--inr` | International normalized ratio | Yes |
| `--creatinine` | Serum creatinine (mg/dL) | Yes |
| `--sodium` | Serum sodium (mEq/L) | Yes |
| `--albumin` | Serum albumin (g/dL) — enables MELD 3.0 | No |
| `--female` | Patient is female (for MELD 3.0) | No |
| `--dialysis` | Patient had ≥2 dialysis sessions/week | No |
| `--json` | Output as JSON | No |

### Input Data Schema (for batch CSV)

| Field | Description | Requirement |
|:------|:------------|:------------|
| `patient_id` | Unique patient identifier | Required |
| `bilirubin` | Serum bilirubin (mg/dL) | Required |
| `creatinine` | Serum creatinine (mg/dL) | Required |
| `inr` | International normalized ratio | Required |
| `sodium` | Serum sodium (mEq/L) | Required |
| `albumin` | Serum albumin (g/dL) | Optional |
| `dialysis` | Dialysis flag (0/1/true/false) | Optional |
| `sex` | Sex (M/F) | Optional |

---

## 🛡️ Security & Enterprise Architecture

* **Zero-PHI Outbound Interceptor:** Active regex inspection blocking SSNs, MRNs, phone numbers, emails, and patient identifiers.
* **Tamper-Evident HMAC-SHA256 Audit Trail:** Chained, cryptographically signed logs for every evaluation. Set `AUDIT_SECRET_KEY` environment variable for production use.
* **Input Validation:** All numeric inputs are validated to reject NaN and Infinity values.
* **FastAPI & Prometheus Telemetry:** Exposes REST endpoints (`/health`, `/metrics`, `/api/audit`, `/api/chat`, `/api/audit/logs`).

---

## 🧪 Testing & Verification

Run the automated test suite:

```bash
pytest -v
```

Run specific test files:

```bash
pytest test_meld_na.py -v          # Core MELD calculation tests
pytest tests/test_enrichment.py -v # Enrichment module tests
pytest tests/test_meld_na_calculator.py -v  # Enterprise agent tests
```

Execute the simulation:

```bash
python simulator.py 100
```

---

## 🐳 Container Deployment

```bash
docker build -t meld-na-calculator .
docker run -p 8000:8000 meld-na-calculator
```
