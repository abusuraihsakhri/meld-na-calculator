#!/usr/bin/env python3
"""
MELD-Na Calculator — Real clinical scoring implementations.

Implements:
  - MELD (original): Kamath et al. 2001
  - MELD-Na (2016):  UNOS revision incorporating serum sodium
  - MELD 3.0 (2023): Kim et al. — adds albumin and sex adjustment

All formulas use only Python stdlib (math).

DISCLAIMER: This is an educational/reference implementation.
It is NOT a substitute for clinical judgment. Always verify
scores against institutional protocols before clinical use.
"""

import math
from typing import Optional, Dict, Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BILI_MIN = 1.0
BILI_MAX = 99.0      # upper cap rarely hit; prevents math domain errors
INR_MIN = 1.0
INR_MAX = 99.0
CREAT_MIN = 1.0
CREAT_MAX = 4.0      # UNOS cap
NA_MIN = 125.0
NA_MAX = 137.0
MELD_MIN = 1
MELD_MAX = 40

# 3-month mortality lookup (approximate, from Kamath / Wiesner literature)
MORTALITY_TIERS = [
    (9,  0.019,  "≤9"),
    (19, 0.060,  "10–19"),
    (29, 0.196,  "20–29"),
    (39, 0.526,  "30–39"),
    (40, 0.713,  "≥40"),
]

# Allocation priority tiers (simplified UNOS-style)
ALLOCATION_TIERS = [
    (40, "Status 1A equivalent — highest urgency, acute liver failure / graft non-function"),
    (30, "Status 1B equivalent — very high priority, MELD ≥ 30"),
    (25, "High priority — MELD 25–29"),
    (15, "Moderate priority — MELD 15–24"),
    (1,  "Lower priority — MELD < 15 (exception points may apply)"),
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _validate_numeric(value: str, name: str) -> float:
    """Validate and convert a numeric input, rejecting NaN and Inf."""
    try:
        result = float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{name} must be a valid number, got {value!r}") from e
    if math.isnan(result) or math.isinf(result):
        raise ValueError(f"{name} must be finite, got {result}")
    return result


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp *value* to [lo, hi]."""
    return max(lo, min(value, hi))


# ---------------------------------------------------------------------------
# MELD (original)
# ---------------------------------------------------------------------------
def calculate_meld(
    bilirubin: float,
    inr: float,
    creatinine: float,
    dialysis: bool = False,
) -> int:
    """
    Calculate the original MELD score (Kamath et al. 2001).

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
    """
    # Validate and floor at 1.0 (log of values < 1 is negative; MELD uses 1.0 minimum)
    bili = _clamp(_validate_numeric(bilirubin, "bilirubin"), BILI_MIN, BILI_MAX)
    inr_val = _clamp(_validate_numeric(inr, "inr"), INR_MIN, INR_MAX)
    creat = _clamp(_validate_numeric(creatinine, "creatinine"), CREAT_MIN, CREAT_MAX)

    # Dialysis override: ≥ 2 sessions in past week → creatinine = 4.0
    if dialysis:
        creat = 4.0

    meld_raw = (
        3.78 * math.log(bili)
        + 11.2 * math.log(inr_val)
        + 9.57 * math.log(creat)
        + 6.43
    )

    return int(_clamp(round(meld_raw), MELD_MIN, MELD_MAX))


# ---------------------------------------------------------------------------
# MELD-Na (2016 UNOS revision)
# ---------------------------------------------------------------------------
def calculate_meld_na(
    bilirubin: float,
    inr: float,
    creatinine: float,
    sodium: float,
    dialysis: bool = False,
) -> int:
    """
    Calculate MELD-Na per the 2016 UNOS revision.

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
    """
    meld = calculate_meld(bilirubin, inr, creatinine, dialysis)

    # No sodium correction if MELD ≤ 11
    if meld <= 11:
        return meld

    na = _clamp(_validate_numeric(sodium, "sodium"), NA_MIN, NA_MAX)

    delta = 137.0 - na  # always ≥ 0 after clamping
    meld_na_raw = meld + 1.32 * delta - 0.033 * meld * delta

    return int(_clamp(round(meld_na_raw), MELD_MIN, MELD_MAX))


# ---------------------------------------------------------------------------
# MELD 3.0 (Kim et al. 2023)
# ---------------------------------------------------------------------------
def calculate_meld_3(
    bilirubin: float,
    inr: float,
    creatinine: float,
    sodium: float,
    albumin: float,
    female: bool = False,
    dialysis: bool = False,
) -> int:
    """
    Calculate MELD 3.0 (Kim et al., NEJM 2023).

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
    """
    bili = _clamp(_validate_numeric(bilirubin, "bilirubin"), BILI_MIN, BILI_MAX)
    inr_val = _clamp(_validate_numeric(inr, "inr"), INR_MIN, INR_MAX)
    creat = _clamp(_validate_numeric(creatinine, "creatinine"), CREAT_MIN, CREAT_MAX)
    na = _clamp(_validate_numeric(sodium, "sodium"), NA_MIN, NA_MAX)
    alb = max(0.1, _validate_numeric(albumin, "albumin"))  # prevent log(0); no clinical cap specified

    if dialysis:
        creat = 4.0

    sex_bonus = 1.334 if female else 0.0
    delta = 137.0 - na

    meld3_raw = (
        4.56 * math.log(bili)
        + 9.09 * math.log(inr_val)
        + 11.14 * math.log(creat)
        - 1.85 * math.log(alb)
        + 0.82 * delta
        - 0.24 * delta * math.log(creat)
        + sex_bonus
        + 6.0
    )

    return int(_clamp(round(meld3_raw), MELD_MIN, MELD_MAX))


# ---------------------------------------------------------------------------
# Clinical interpretation helpers
# ---------------------------------------------------------------------------
def estimate_3month_mortality(meld_score: int) -> float:
    """
    Return estimated 3-month mortality proportion for a given MELD score.

    Based on Kamath & Wiesner et al. data. Returns a float in [0, 1].
    """
    score = int(_clamp(_validate_numeric(meld_score, "meld_score"), MELD_MIN, MELD_MAX))
    for upper, rate, _label in MORTALITY_TIERS:
        if score <= upper:
            return rate
    return 0.713  # fallback for score == 40


def get_allocation_priority(meld_score: int) -> str:
    """Return a human-readable allocation priority tier description."""
    score = int(_clamp(_validate_numeric(meld_score, "meld_score"), MELD_MIN, MELD_MAX))
    for upper, description in ALLOCATION_TIERS:
        if score >= upper:
            return description
    return ALLOCATION_TIERS[-1][1]


def get_exception_points_info() -> str:
    """Return a summary of MELD exception point policies."""
    return (
        "MELD Exception Points:\n"
        "  - Hepatocellular carcinoma (HCC): MELD 28 at listing, +3 every 3 months\n"
        "  - Hepatopulmonary syndrome: MELD 22 at listing, reassessed every 3 months\n"
        "  - Portopulmonary hypertension: MELD 22 after documented treatment response\n"
        "  - Hilar cholangiocarcinoma: MELD 28 at listing (requires protocol enrollment)\n"
        "  - Cystic fibrosis: MELD 22 at listing, +3 every 3 months\n"
        "  - Familial amyloid polyneuropathy: MELD 22 at listing\n"
        "  - Primary hyperoxaluria: MELD 28 at listing (combined liver-kidney)\n"
        "  NOTE: Exception policies are set by regional review boards and may vary.\n"
        "  Always verify current UNOS policy for the most up-to-date criteria."
    )


# ---------------------------------------------------------------------------
# Full assessment (convenience wrapper)
# ---------------------------------------------------------------------------
def full_assessment(
    bilirubin: float,
    inr: float,
    creatinine: float,
    sodium: float,
    albumin: Optional[float] = None,
    female: bool = False,
    dialysis: bool = False,
) -> Dict[str, Any]:
    """
    Run all applicable MELD calculations and return a result dict.

    Returns
    -------
    dict with keys:
        meld           — original MELD score (int)
        meld_na        — MELD-Na 2016 score (int)
        meld_3         — MELD 3.0 score (int) or None if albumin not provided
        mortality_3mo  — estimated 3-month mortality (float)
        priority       — allocation priority tier (str)
        inputs         — dict of clamped/adjusted input values used
    """
    bilirubin = _validate_numeric(bilirubin, "bilirubin")
    inr = _validate_numeric(inr, "inr")
    creatinine = _validate_numeric(creatinine, "creatinine")
    sodium = _validate_numeric(sodium, "sodium")

    meld = calculate_meld(bilirubin, inr, creatinine, dialysis)
    meld_na = calculate_meld_na(bilirubin, inr, creatinine, sodium, dialysis)

    meld_3 = None
    if albumin is not None:
        meld_3 = calculate_meld_3(
            bilirubin, inr, creatinine, sodium, albumin, female, dialysis
        )

    # Use the best available score for mortality / priority
    best = meld_na if meld_na is not None else meld

    return {
        "meld": meld,
        "meld_na": meld_na,
        "meld_3": meld_3,
        "mortality_3mo": estimate_3month_mortality(best),
        "priority": get_allocation_priority(best),
        "inputs": {
            "bilirubin_mgdl": _clamp(float(bilirubin), BILI_MIN, BILI_MAX),
            "inr": _clamp(float(inr), INR_MIN, INR_MAX),
            "creatinine_mgdl": 4.0 if dialysis else _clamp(float(creatinine), CREAT_MIN, CREAT_MAX),
            "sodium_meql": _clamp(float(sodium), NA_MIN, NA_MAX),
            "albumin_gdl": albumin,
            "dialysis": dialysis,
            "female": female,
        },
    }
