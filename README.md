# MELD-Na Calculator

A Python implementation of the **MELD**, **MELD-Na**, and **MELD 3.0** liver transplant scoring systems.

## What This Is

This calculator implements three published clinical scoring formulas used in liver transplant organ allocation:

| Score | Reference | Year |
|-------|-----------|------|
| **MELD** (original) | Kamath et al. | 2001 |
| **MELD-Na** (UNOS revision) | UNOS policy update | 2016 |
| **MELD 3.0** | Kim et al. (NEJM) | 2023 |

It also provides:
- 3-month mortality risk estimation (based on Kamath/Wiesner data)
- Organ allocation priority tier classification
- MELD exception point policy summary

## What This Is NOT

**This is NOT a medical device.** It is an educational and reference implementation of published formulas. It has not been validated for clinical use, has no regulatory clearance, and must not be used to make treatment or allocation decisions. Always verify scores against your institutional protocols and UNOS policy.

## Requirements

Python 3.8+ (stdlib only — no third-party dependencies).

## Quick Start

### Single Patient

```bash
python cli.py calculate --bilirubin 2.5 --inr 1.8 --creatinine 1.5 --sodium 135
```

Output:
```
============================================================
  MELD-Na Calculator Results
============================================================
  MELD (original) :  21
  MELD-Na (2016)  :  20
  MELD 3.0 (2023) :  N/A (requires --albumin)
  3-month mortality:  19.6%
  Priority tier   :  High priority — MELD 25–29
------------------------------------------------------------
  Inputs (after clamping/adjustment):
    bilirubin_mgdl      : 2.5
    inr                 : 1.8
    creatinine_mgdl     : 1.5
    sodium_meql         : 135.0
    albumin_gdl         : None
    dialysis            : False
    female              : False
============================================================
```

### With Albumin (MELD 3.0)

```bash
python cli.py calculate --bilirubin 2.5 --inr 1.8 --creatinine 1.5 \
    --sodium 135 --albumin 3.2 --female
```

### Dialysis Patient

```bash
python cli.py calculate --bilirubin 4.0 --inr 2.5 --creatinine 1.0 \
    --sodium 130 --dialysis
```

### JSON Output

```bash
python cli.py calculate --bilirubin 2.5 --inr 1.8 --creatinine 1.5 --sodium 135 --json
```

### Batch Processing

Create a CSV with columns: `bilirubin`, `inr`, `creatinine`, `sodium`, and optionally `albumin`, `sex`, `dialysis`.

```bash
python cli.py batch --input patients.csv --output scored.csv
```

### Exception Points

```bash
python cli.py exceptions
```

## Formulas

### MELD (original)

```
MELD = 3.78 × ln(bilirubin) + 11.2 × ln(INR) + 9.57 × ln(creatinine) + 6.43
```

- Values < 1.0 are set to 1.0
- Creatinine capped at 4.0 (set to 4.0 if on dialysis)
- Score range: 1–40

### MELD-Na (2016)

```
MELD-Na = MELD + 1.32 × (137 − Na) − 0.033 × MELD × (137 − Na)
```

- Sodium clamped to 125–137 mEq/L
- Na correction applied only when MELD > 11
- Score range: 1–40

### MELD 3.0 (2023)

```
MELD 3.0 = 4.56 × ln(bili) + 9.09 × ln(INR) + 11.14 × ln(creat)
           − 1.85 × ln(albumin) + 0.82 × (137 − Na)
           − 0.24 × (137 − Na) × ln(creat)
           + sex_bonus + 6
```

- `sex_bonus` = 1.334 if female, 0 if male
- Same capping rules as MELD/MELD-Na
- Requires albumin input

## Python API

```python
from meld_na import full_assessment, calculate_meld_na

# Full assessment
result = full_assessment(
    bilirubin=2.5, inr=1.8, creatinine=1.5, sodium=135,
    albumin=3.2, female=False, dialysis=False,
)
print(result["meld"])       # 21
print(result["meld_na"])    # 20
print(result["meld_3"])     # 22
print(result["mortality_3mo"])  # 0.196

# Individual score
score = calculate_meld_na(bilirubin=2.5, inr=1.8, creatinine=1.5, sodium=135)
```

## Running Tests

```bash
python -m pytest test_meld_na.py -v
```

Or without pytest:

```bash
python test_meld_na.py
```

## Project Structure

```
meld_na.py          — Core scoring formulas (the actual calculator)
cli.py              — Command-line interface
test_meld_na.py     — Test suite
sample.csv          — Example batch input
README.md           — This file
```

## License

MIT License. See [LICENSE](LICENSE).
