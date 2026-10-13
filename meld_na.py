#!/usr/bin/env python3
"""Reference MELD, MELD-Na (2016), and adult MELD 3.0 calculations.

The legacy models are provided for comparison. Since July 2023, adult U.S.
liver allocation has used MELD 3.0 rather than the older MELD-Na formula.
Scores are not clinical decisions or official OPTN allocation assignments.

References:
  Kim WR et al. MELD 3.0. Gastroenterology. 2021;161:1887-1895.e4.
  https://www.hrsa.gov/optn/data-calculators/allocation-calculators/meld-calculator
"""
import math
from typing import Any, Dict, Optional

BILI_MIN = 1.0
BILI_MAX = math.inf
INR_MIN = 1.0
INR_MAX = math.inf
CREAT_MIN = 1.0
CREAT_MAX = 4.0                 # historical MELD / MELD-Na
CREAT_3_MAX = 3.0               # adult MELD 3.0
NA_MIN = 125.0
NA_MAX = 137.0
ALBUMIN_MIN = 1.5
ALBUMIN_MAX = 3.5
MELD_MIN = 6
MELD_MAX = 40

# Historical original-MELD strata, not calibrated MELD-Na/MELD 3.0 estimates.
MORTALITY_TIERS = (
    (9, 0.019, "6–9"),
    (19, 0.060, "10–19"),
    (29, 0.196, "20–29"),
    (39, 0.526, "30–39"),
    (40, 0.713, "40"),
)


def _validate_numeric(value: float, name: str) -> float:
    """Reject non-finite and non-positive laboratory values."""
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a positive, finite number") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be a positive, finite number")
    return result


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def _score(raw: float) -> int:
    """Clinical whole-number rounding (0.5 rounds upward), bounded 6–40."""
    return int(_clamp(math.floor(raw + 0.5), MELD_MIN, MELD_MAX))


def calculate_meld(
    bilirubin: float, inr: float, creatinine: float, dialysis: bool = False
) -> int:
    """Historical original MELD (not the current U.S. allocation formula)."""
    bili = _clamp(_validate_numeric(bilirubin, "bilirubin"), BILI_MIN, BILI_MAX)
    coag = _clamp(_validate_numeric(inr, "inr"), INR_MIN, INR_MAX)
    creat = _clamp(_validate_numeric(creatinine, "creatinine"), CREAT_MIN, CREAT_MAX)
    if dialysis:
        creat = CREAT_MAX
    return _score(
        3.78 * math.log(bili) + 11.2 * math.log(coag)
        + 9.57 * math.log(creat) + 6.43
    )


def calculate_meld_na(
    bilirubin: float, inr: float, creatinine: float,
    sodium: float, dialysis: bool = False
) -> int:
    """Historical 2016 MELD-Na, sodium correction only when MELD > 11."""
    na = _clamp(_validate_numeric(sodium, "sodium"), NA_MIN, NA_MAX)
    meld = calculate_meld(bilirubin, inr, creatinine, dialysis)
    if meld <= 11:
        return meld
    delta = 137.0 - na
    return _score(meld + 1.32 * delta - 0.033 * meld * delta)


def calculate_meld_3(
    bilirubin: float, inr: float, creatinine: float, sodium: float,
    albumin: float, female: bool = False, dialysis: bool = False
) -> int:
    """Adult MELD 3.0 (2023 OPTN implementation; laboratory component only).

    Dialysis means >=2 sessions or >=24 hours of CVVHD in the preceding week.
    Adult use only; candidates aged 12–17 use an age-specific modification.
    """
    bili = _clamp(_validate_numeric(bilirubin, "bilirubin"), BILI_MIN, BILI_MAX)
    coag = _clamp(_validate_numeric(inr, "inr"), INR_MIN, INR_MAX)
    creat = _clamp(_validate_numeric(creatinine, "creatinine"), CREAT_MIN, CREAT_3_MAX)
    na = _clamp(_validate_numeric(sodium, "sodium"), NA_MIN, NA_MAX)
    alb = _clamp(_validate_numeric(albumin, "albumin"), ALBUMIN_MIN, ALBUMIN_MAX)
    if dialysis:
        creat = CREAT_3_MAX
    sodium_gap = 137.0 - na
    albumin_gap = 3.5 - alb
    result = (
        (1.33 if female else 0.0)
        + 4.56 * math.log(bili)
        + 0.82 * sodium_gap
        - 0.24 * sodium_gap * math.log(bili)
        + 9.09 * math.log(coag)
        + 11.14 * math.log(creat)
        + 1.85 * albumin_gap
        - 1.83 * albumin_gap * math.log(creat)
        + 6.0
    )
    return _score(result)


def estimate_3month_mortality(meld_score: int) -> float:
    """Historical 90-day mortality from original MELD score strata only.

    Not validated for MELD-Na, MELD 3.0, or an individual patient.
    """
    score = _score(_validate_numeric(meld_score, "meld_score"))
    for upper, rate, _label in MORTALITY_TIERS:
        if score <= upper:
            return rate
    raise AssertionError("Unreachable MELD score")


def get_allocation_priority(meld_score: int) -> str:
    """Descriptive score band, NOT an allocation status or priority assignment."""
    score = _score(_validate_numeric(meld_score, "meld_score"))
    if score >= 30:
        return "Very high MELD score (30–40); allocation status is determined separately"
    if score >= 25:
        return "High MELD score (25–29); allocation status is determined separately"
    if score >= 15:
        return "Moderate MELD score (15–24); allocation status is determined separately"
    return "Lower MELD score (6–14); allocation status is determined separately"


def get_exception_points_info() -> str:
    """Avoid displaying obsolete or speculative HCC/exception point thresholds."""
    return (
        "MELD exception requests are governed by current OPTN policy, including "
        "diagnosis-specific criteria and review procedures. This tool cannot "
        "determine exception eligibility or award points. HCC and other indications "
        "must be checked against the current policy and the transplant program. "
        "Official information: "
        "https://www.hrsa.gov/optn/data-calculators/allocation-calculators/meld-calculator"
    )


def full_assessment(
    bilirubin: float, inr: float, creatinine: float, sodium: float,
    albumin: Optional[float] = None, female: bool = False,
    dialysis: bool = False
) -> Dict[str, Any]:
    """Return three historical/current scores with transparently capped inputs."""
    bili = _validate_numeric(bilirubin, "bilirubin")
    coag = _validate_numeric(inr, "inr")
    creat = _validate_numeric(creatinine, "creatinine")
    na = _validate_numeric(sodium, "sodium")
    alb = None if albumin is None else _validate_numeric(albumin, "albumin")
    meld = calculate_meld(bili, coag, creat, dialysis)
    meld_na = calculate_meld_na(bili, coag, creat, na, dialysis)
    meld3 = (
        calculate_meld_3(bili, coag, creat, na, alb, female, dialysis)
        if alb is not None else None
    )
    return {
        "meld": meld,
        "meld_na": meld_na,
        "meld_3": meld3,
        "mortality_3mo": estimate_3month_mortality(meld),
        "mortality_note": "Historical original-MELD strata; not a patient-specific risk or MELD 3.0 estimate.",
        "priority": get_allocation_priority(meld3 if meld3 is not None else meld_na),
        "priority_note": "A descriptive score band only; not an OPTN allocation assignment.",
        "inputs": {
            "bilirubin_mgdl": _clamp(bili, BILI_MIN, BILI_MAX),
            "inr": _clamp(coag, INR_MIN, INR_MAX),
            "creatinine_mgdl": CREAT_MAX if dialysis else _clamp(creat, CREAT_MIN, CREAT_MAX),
            "creatinine_mgdl_meld3": CREAT_3_MAX if dialysis else _clamp(creat, CREAT_MIN, CREAT_3_MAX),
            "sodium_meql": _clamp(na, NA_MIN, NA_MAX),
            "albumin_gdl": None if alb is None else _clamp(alb, ALBUMIN_MIN, ALBUMIN_MAX),
            "dialysis": bool(dialysis),
            "female": bool(female),
        },
    }
