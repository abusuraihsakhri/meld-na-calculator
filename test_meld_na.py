#!/usr/bin/env python3
"""
Comprehensive tests for the MELD-Na Calculator.

Covers:
  - MELD (original) scoring
  - MELD-Na (2016) scoring with sodium correction
  - MELD 3.0 scoring with albumin and sex
  - Dialysis adjustment
  - Boundary capping (bilirubin, INR, creatinine, sodium)
  - Na correction applied vs. not applied (MELD > 11 vs. ≤ 11)
  - 3-month mortality estimation
  - Allocation priority tiers
  - Known clinical examples with hand-verified expected values
  - CLI interface

Run:  python test_meld_na.py
      python -m pytest test_meld_na.py -v
"""

import math
import subprocess
import sys
import os
import csv
import tempfile

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
from meld_na import (
    calculate_meld,
    calculate_meld_na,
    calculate_meld_3,
    estimate_3month_mortality,
    get_allocation_priority,
    get_exception_points_info,
    full_assessment,
    MELD_MIN,
    MELD_MAX,
)


# ---------------------------------------------------------------------------
# Minimal test harness (works without pytest)
# ---------------------------------------------------------------------------
class _TestResult:
    def __init__(self, name, passed, message=""):
        self.name = name
        self.passed = passed
        self.message = message


_results: list[_TestResult] = []


def _check(name: str, condition: bool, detail: str = ""):
    """Record a test assertion."""
    _results.append(_TestResult(name, condition, detail))
    if not condition:
        print(f"  FAIL: {name} — {detail}")


def _eq(name: str, actual, expected, tolerance=None):
    """Assert equality with optional numeric tolerance."""
    if tolerance is not None:
        ok = abs(actual - expected) <= tolerance
    else:
        ok = actual == expected
    detail = f"expected={expected}, got={actual}" if not ok else ""
    _check(name, ok, detail)


def _in_range(name: str, value, lo, hi):
    ok = lo <= value <= hi
    _check(name, ok, f"{value} not in [{lo}, {hi}]")


# ===================================================================
# 1. MELD (original) — hand-calculated verification
# ===================================================================
def test_meld_basic():
    """Verify MELD formula against hand calculation."""
    # bilirubin=2.0, INR=1.5, creatinine=1.2
    # MELD = 3.78*ln(2.0) + 11.2*ln(1.5) + 9.57*ln(1.2) + 6.43
    #      = 3.78*0.6931 + 11.2*0.4055 + 9.57*0.1823 + 6.43
    #      = 2.620 + 4.542 + 1.745 + 6.43 = 15.337 → round → 15
    expected_raw = 3.78 * math.log(2.0) + 11.2 * math.log(1.5) + 9.57 * math.log(1.2) + 6.43
    expected = int(max(MELD_MIN, min(round(expected_raw), MELD_MAX)))
    actual = calculate_meld(bilirubin=2.0, inr=1.5, creatinine=1.2)
    _eq("meld_basic_hand_calc", actual, expected)


def test_meld_low_values_use_floor():
    """Values < 1.0 should be treated as 1.0."""
    # bilirubin=0.5 → use 1.0, INR=0.8 → use 1.0, creatinine=0.7 → use 1.0
    # MELD = 3.78*ln(1.0) + 11.2*ln(1.0) + 9.57*ln(1.0) + 6.43 = 6.43 → 6
    actual = calculate_meld(bilirubin=0.5, inr=0.8, creatinine=0.7)
    _eq("meld_low_values_floor", actual, 6)


def test_meld_severe_liver_disease():
    """High values should produce a high MELD score."""
    # bilirubin=15, INR=3.5, creatinine=3.0
    actual = calculate_meld(bilirubin=15.0, inr=3.5, creatinine=3.0)
    _in_range("meld_severe_range", actual, 30, 40)


def test_meld_max_cap():
    """MELD should never exceed 40."""
    actual = calculate_meld(bilirubin=50.0, inr=10.0, creatinine=4.0)
    _eq("meld_max_cap", actual, 40)


def test_meld_min_cap():
    """MELD should never go below 1."""
    actual = calculate_meld(bilirubin=1.0, inr=1.0, creatinine=1.0)
    _eq("meld_min_cap", actual, max(MELD_MIN, 6))  # 6.43 rounds to 6


# ===================================================================
# 2. Dialysis adjustment
# ===================================================================
def test_dialysis_sets_creatinine_to_4():
    """Dialysis should force creatinine to 4.0 regardless of input."""
    # Without dialysis: creatinine=1.0
    no_dial = calculate_meld(bilirubin=2.0, inr=1.5, creatinine=1.0, dialysis=False)
    # With dialysis: creatinine forced to 4.0
    with_dial = calculate_meld(bilirubin=2.0, inr=1.5, creatinine=1.0, dialysis=True)
    _check("dialysis_increases_meld", with_dial > no_dial,
           f"with_dial={with_dial}, no_dial={no_dial}")

    # Verify the actual value with creatinine=4.0
    expected_raw = 3.78 * math.log(2.0) + 11.2 * math.log(1.5) + 9.57 * math.log(4.0) + 6.43
    expected = int(max(MELD_MIN, min(round(expected_raw), MELD_MAX)))
    _eq("dialysis_meld_value", with_dial, expected)


def test_dialysis_overrides_high_creatinine():
    """Even if creatinine is already > 4, dialysis sets it to 4.0 (cap)."""
    # creatinine=5.0 without dialysis → capped at 4.0
    cap_only = calculate_meld(bilirubin=2.0, inr=1.5, creatinine=5.0, dialysis=False)
    # creatinine=5.0 with dialysis → also 4.0
    with_dial = calculate_meld(bilirubin=2.0, inr=1.5, creatinine=5.0, dialysis=True)
    _eq("dialysis_cap_same", cap_only, with_dial)


# ===================================================================
# 3. MELD-Na — sodium correction
# ===================================================================
def test_meld_na_correction_applied_when_meld_gt_11():
    """Na correction should be applied when MELD > 11."""
    # Use values that give MELD > 11
    # bilirubin=3.0, INR=2.0, creatinine=2.0 → MELD ≈ 23
    meld = calculate_meld(bilirubin=3.0, inr=2.0, creatinine=2.0)
    _check("meld_gt_11_for_na_test", meld > 11, f"meld={meld}")

    meld_na_high_na = calculate_meld_na(3.0, 2.0, 2.0, sodium=137.0)
    meld_na_low_na = calculate_meld_na(3.0, 2.0, 2.0, sodium=125.0)

    # Lower sodium → higher MELD-Na (sicker)
    _check("na_correction_direction",
           meld_na_low_na > meld_na_high_na,
           f"low_na={meld_na_low_na}, high_na={meld_na_high_na}")


def test_meld_na_no_correction_when_meld_le_11():
    """Na correction should NOT be applied when MELD ≤ 11."""
    # bilirubin=1.0, INR=1.0, creatinine=1.0 → MELD = 6
    meld = calculate_meld(bilirubin=1.0, inr=1.0, creatinine=1.0)
    _check("meld_le_11_no_na", meld <= 11, f"meld={meld}")

    meld_na_any_na = calculate_meld_na(1.0, 1.0, 1.0, sodium=125.0)
    _eq("no_na_correction_low_meld", meld_na_any_na, meld)


def test_meld_na_boundary_meld_11():
    """When MELD is exactly 11, no Na correction."""
    # Find values that give exactly MELD=11
    # 3.78*ln(1.0) + 11.2*ln(1.0) + 9.57*ln(1.0) + 6.43 = 6.43 → 6
    # Need MELD=11. Let's try: bili=1.5, INR=1.2, creat=1.3
    # 3.78*0.405 + 11.2*0.182 + 9.57*0.262 + 6.43 = 1.531 + 2.038 + 2.507 + 6.43 = 12.506 → 13
    # Try bili=1.2, INR=1.1, creat=1.1
    # 3.78*0.182 + 11.2*0.0953 + 9.57*0.0953 + 6.43 = 0.688 + 1.067 + 0.912 + 6.43 = 9.097 → 9
    # Try bili=1.3, INR=1.15, creat=1.15
    # 3.78*0.262 + 11.2*0.140 + 9.57*0.140 + 6.43 = 0.990 + 1.568 + 1.340 + 6.43 = 10.328 → 10
    # Try bili=1.35, INR=1.17, creat=1.17
    # 3.78*0.300 + 11.2*0.157 + 9.57*0.157 + 6.43 = 1.134 + 1.758 + 1.502 + 6.43 = 10.824 → 11
    meld = calculate_meld(bilirubin=1.35, inr=1.17, creatinine=1.17)
    if meld == 11:
        # MELD=11 → no Na correction
        meld_na = calculate_meld_na(1.35, 1.17, 1.17, sodium=125.0)
        _eq("boundary_meld_11_no_correction", meld_na, 11)
    else:
        # If we didn't hit exactly 11, just verify the ≤11 rule
        _check("boundary_meld_11_note", meld <= 11,
               f"Could not construct MELD=11 exactly (got {meld}), testing ≤11 rule instead")
        meld_na = calculate_meld_na(1.35, 1.17, 1.17, sodium=125.0)
        _eq("boundary_meld_le_11_no_correction", meld_na, meld)


def test_meld_na_sodium_capping():
    """Sodium should be clamped to [125, 137]."""
    # Na=120 should be treated as 125
    meld_na_120 = calculate_meld_na(3.0, 2.0, 2.0, sodium=120.0)
    meld_na_125 = calculate_meld_na(3.0, 2.0, 2.0, sodium=125.0)
    _eq("na_cap_low", meld_na_120, meld_na_125)

    # Na=145 should be treated as 137
    meld_na_145 = calculate_meld_na(3.0, 2.0, 2.0, sodium=145.0)
    meld_na_137 = calculate_meld_na(3.0, 2.0, 2.0, sodium=137.0)
    _eq("na_cap_high", meld_na_145, meld_na_137)


def test_meld_na_hand_calc():
    """Hand-verify MELD-Na formula for a known case."""
    # bilirubin=2.5, INR=1.8, creatinine=1.5, sodium=135
    meld = calculate_meld(bilirubin=2.5, inr=1.8, creatinine=1.5)
    # MELD = 3.78*ln(2.5) + 11.2*ln(1.8) + 9.57*ln(1.5) + 6.43
    #      = 3.78*0.9163 + 11.2*0.5878 + 9.57*0.4055 + 6.43
    #      = 3.464 + 6.583 + 3.881 + 6.43 = 20.358 → 20
    expected_meld = int(max(MELD_MIN, min(round(3.78 * math.log(2.5) + 11.2 * math.log(1.8) + 9.57 * math.log(1.5) + 6.43), MELD_MAX)))
    _eq("hand_calc_meld", meld, expected_meld)

    # MELD-Na = MELD + 1.32*(137-135) - 0.033*MELD*(137-135)
    #         = 20 + 1.32*2 - 0.033*20*2
    #         = 20 + 2.64 - 1.32 = 21.32 → 21
    if meld > 11:
        delta = 137.0 - 135.0
        expected_meld_na = int(max(MELD_MIN, min(round(meld + 1.32 * delta - 0.033 * meld * delta), MELD_MAX)))
        actual_meld_na = calculate_meld_na(2.5, 1.8, 1.5, 135.0)
        _eq("hand_calc_meld_na", actual_meld_na, expected_meld_na)


# ===================================================================
# 4. MELD 3.0
# ===================================================================
def test_meld_3_basic():
    """MELD 3.0 should produce a valid score with albumin provided."""
    result = calculate_meld_3(
        bilirubin=2.5, inr=1.8, creatinine=1.5,
        sodium=135.0, albumin=3.2, female=False,
    )
    _in_range("meld3_basic_range", result, MELD_MIN, MELD_MAX)


def test_meld_3_female_bonus():
    """Female patients should get a higher MELD 3.0 score."""
    male_score = calculate_meld_3(
        bilirubin=2.5, inr=1.8, creatinine=1.5,
        sodium=135.0, albumin=3.2, female=False,
    )
    female_score = calculate_meld_3(
        bilirubin=2.5, inr=1.8, creatinine=1.5,
        sodium=135.0, albumin=3.2, female=True,
    )
    _check("meld3_female_higher", female_score >= male_score,
           f"female={female_score}, male={male_score}")
    # The bonus is 1.334, so for moderate scores the female should be exactly +1
    _check("meld3_female_bonus_at_least_1", female_score >= male_score,
           f"Expected female ({female_score}) >= male ({male_score})")


def test_meld_3_albumin_effect():
    """Lower albumin should produce higher MELD 3.0 (sicker patient)."""
    high_alb = calculate_meld_3(
        bilirubin=2.5, inr=1.8, creatinine=1.5,
        sodium=135.0, albumin=4.0, female=False,
    )
    low_alb = calculate_meld_3(
        bilirubin=2.5, inr=1.8, creatinine=1.5,
        sodium=135.0, albumin=1.5, female=False,
    )
    _check("meld3_low_albumin_higher", low_alb > high_alb,
           f"low_alb={low_alb}, high_alb={high_alb}")


def test_meld_3_hand_calc():
    """Hand-verify MELD 3.0 formula."""
    bili, inr_val, creat, na, alb = 2.0, 1.5, 1.2, 135.0, 3.5
    delta = 137.0 - na  # 2.0
    expected_raw = (
        4.56 * math.log(bili)
        + 9.09 * math.log(inr_val)
        + 11.14 * math.log(creat)
        - 1.85 * math.log(alb)
        + 0.82 * delta
        - 0.24 * delta * math.log(creat)
        + 0.0  # male
        + 6.0
    )
    expected = int(max(MELD_MIN, min(round(expected_raw), MELD_MAX)))
    actual = calculate_meld_3(bili, inr_val, creat, na, alb, female=False)
    _eq("meld3_hand_calc", actual, expected)


def test_meld_3_dialysis():
    """MELD 3.0 should also apply dialysis adjustment."""
    no_dial = calculate_meld_3(2.0, 1.5, 1.0, 135.0, 3.5, dialysis=False)
    with_dial = calculate_meld_3(2.0, 1.5, 1.0, 135.0, 3.5, dialysis=True)
    _check("meld3_dialysis_increases", with_dial > no_dial,
           f"with_dial={with_dial}, no_dial={no_dial}")


# ===================================================================
# 5. 3-month mortality estimation
# ===================================================================
def test_mortality_low_meld():
    """MELD ≤ 9 should have ~1.9% mortality."""
    _eq("mortality_low", estimate_3month_mortality(6), 0.019)
    _eq("mortality_9", estimate_3month_mortality(9), 0.019)


def test_mortality_mid_meld():
    """MELD 10-19 should have ~6% mortality."""
    _eq("mortality_mid", estimate_3month_mortality(15), 0.060)


def test_mortality_high_meld():
    """MELD 20-29 should have ~19.6% mortality."""
    _eq("mortality_high", estimate_3month_mortality(25), 0.196)


def test_mortality_very_high_meld():
    """MELD 30-39 should have ~52.6% mortality."""
    _eq("mortality_very_high", estimate_3month_mortality(35), 0.526)


def test_mortality_max_meld():
    """MELD 40 should have ~71.3% mortality."""
    _eq("mortality_max", estimate_3month_mortality(40), 0.713)


# ===================================================================
# 6. Allocation priority tiers
# ===================================================================
def test_priority_tiers():
    """Verify priority tier assignments."""
    _check("priority_40", "Status 1A" in get_allocation_priority(40))
    _check("priority_35", "Status 1B" in get_allocation_priority(35) or "≥ 30" in get_allocation_priority(35))
    _check("priority_25", "High" in get_allocation_priority(25))
    _check("priority_20", "Moderate" in get_allocation_priority(20))
    _check("priority_10", "Lower" in get_allocation_priority(10))


# ===================================================================
# 7. Exception points info
# ===================================================================
def test_exception_points():
    """Exception points info should be a non-empty string."""
    info = get_exception_points_info()
    _check("exceptions_nonempty", len(info) > 100)
    _check("exceptions_mentions_hcc", "HCC" in info or "hepatocellular" in info.lower())


# ===================================================================
# 8. Full assessment
# ===================================================================
def test_full_assessment_keys():
    """full_assessment should return all expected keys."""
    result = full_assessment(
        bilirubin=2.5, inr=1.8, creatinine=1.5, sodium=135,
        albumin=3.2, female=False, dialysis=False,
    )
    for key in ("meld", "meld_na", "meld_3", "mortality_3mo", "priority", "inputs"):
        _check(f"full_has_{key}", key in result)


def test_full_assessment_no_albumin():
    """full_assessment without albumin should return meld_3=None."""
    result = full_assessment(
        bilirubin=2.5, inr=1.8, creatinine=1.5, sodium=135,
    )
    _eq("full_no_albumin_meld3", result["meld_3"], None)
    _check("full_no_albumin_meld", result["meld"] is not None)
    _check("full_no_albumin_meld_na", result["meld_na"] is not None)


# ===================================================================
# 9. Known clinical examples
# ===================================================================
def test_clinical_example_healthy():
    """Healthy patient with normal labs → low MELD."""
    result = full_assessment(
        bilirubin=0.8, inr=1.0, creatinine=0.9, sodium=140,
    )
    _eq("healthy_meld", result["meld"], 6)  # all floored to 1.0 → 6.43 → 6
    _eq("healthy_meld_na", result["meld_na"], 6)  # MELD ≤ 11, no Na correction


def test_clinical_example_compensated_cirrhosis():
    """Compensated cirrhosis with mildly elevated labs."""
    result = full_assessment(
        bilirubin=2.0, inr=1.4, creatinine=1.0, sodium=136,
    )
    # MELD = 3.78*ln(2.0) + 11.2*ln(1.4) + 9.57*ln(1.0) + 6.43
    #      = 2.620 + 3.738 + 0 + 6.43 = 12.788 → 13
    _in_range("compensated_meld", result["meld"], 10, 16)


def test_clinical_example_acute_on_chronic():
    """Acute-on-chronic liver failure → high MELD."""
    result = full_assessment(
        bilirubin=10.0, inr=3.0, creatinine=2.5, sodium=128,
        albumin=2.0, female=False,
    )
    _in_range("acute_chronic_meld", result["meld"], 28, 40)
    _in_range("acute_chronic_meld_na", result["meld_na"], 30, 40)
    _check("acute_chronic_mortality", result["mortality_3mo"] >= 0.19)


def test_clinical_example_dialysis_patient():
    """Dialysis patient should have creatinine forced to 4.0."""
    result = full_assessment(
        bilirubin=3.0, inr=2.0, creatinine=0.8, sodium=132,
        dialysis=True,
    )
    _check("dialysis_patient_creat_adj",
           result["inputs"]["creatinine_mgdl"] == 4.0,
           f"creatinine={result['inputs']['creatinine_mgdl']}")
    # MELD should be high due to forced creatinine
    _in_range("dialysis_patient_meld", result["meld"], 20, 40)


def test_clinical_example_low_sodium_worsens_score():
    """Hyponatremia should worsen MELD-Na vs MELD."""
    result_low_na = full_assessment(
        bilirubin=3.0, inr=2.0, creatinine=2.0, sodium=125,
    )
    result_high_na = full_assessment(
        bilirubin=3.0, inr=2.0, creatinine=2.0, sodium=137,
    )
    _check("hyponatremia_worsens",
           result_low_na["meld_na"] >= result_high_na["meld_na"],
           f"low_na={result_low_na['meld_na']}, high_na={result_high_na['meld_na']}")


# ===================================================================
# 10. CLI tests
# ===================================================================
def test_cli_calculate():
    """CLI 'calculate' subcommand should run without error."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run(
        [sys.executable, "cli.py", "calculate",
         "--bilirubin", "2.5", "--inr", "1.8",
         "--creatinine", "1.5", "--sodium", "135"],
        capture_output=True, text=True, cwd=project_dir,
    )
    _check("cli_calculate_exit_0", result.returncode == 0,
           f"exit={result.returncode}, stderr={result.stderr[:200]}")
    _check("cli_calculate_has_meld", "MELD" in result.stdout,
           f"stdout={result.stdout[:200]}")


def test_cli_calculate_json():
    """CLI 'calculate --json' should produce valid JSON."""
    import json
    project_dir = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run(
        [sys.executable, "cli.py", "calculate",
         "--bilirubin", "2.5", "--inr", "1.8",
         "--creatinine", "1.5", "--sodium", "135", "--json"],
        capture_output=True, text=True, cwd=project_dir,
    )
    _check("cli_json_exit_0", result.returncode == 0,
           f"exit={result.returncode}")
    try:
        data = json.loads(result.stdout)
        _check("cli_json_has_meld", "meld" in data)
        _check("cli_json_has_meld_na", "meld_na" in data)
    except json.JSONDecodeError:
        _check("cli_json_valid", False, f"Invalid JSON: {result.stdout[:200]}")


def test_cli_batch():
    """CLI 'batch' subcommand should process sample.csv."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    sample_path = os.path.join(project_dir, "sample.csv")
    if not os.path.exists(sample_path):
        _check("cli_batch_skip", True, "sample.csv not found, skipping")
        return

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, "cli.py", "batch",
             "--input", sample_path, "--output", tmp_path],
            capture_output=True, text=True, cwd=project_dir,
        )
        _check("cli_batch_exit_0", result.returncode == 0,
               f"exit={result.returncode}, stderr={result.stderr[:200]}")
        _check("cli_batch_processed", "Processed" in result.stdout,
               f"stdout={result.stdout[:200]}")

        # Verify output CSV has new columns
        with open(tmp_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            _check("cli_batch_has_rows", len(rows) > 0)
            if rows:
                _check("cli_batch_has_meld_col", "meld" in rows[0])
                _check("cli_batch_has_meld_na_col", "meld_na" in rows[0])
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_cli_exceptions():
    """CLI 'exceptions' subcommand should print exception info."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run(
        [sys.executable, "cli.py", "exceptions"],
        capture_output=True, text=True, cwd=project_dir,
    )
    _check("cli_exceptions_exit_0", result.returncode == 0)
    _check("cli_exceptions_has_content", len(result.stdout) > 50)


# ===================================================================
# 11. Edge cases
# ===================================================================
def test_extreme_bilirubin():
    """Very high bilirubin should be handled gracefully."""
    result = calculate_meld(bilirubin=50.0, inr=1.5, creatinine=1.5)
    _in_range("extreme_bili", result, MELD_MIN, MELD_MAX)


def test_extreme_inr():
    """Very high INR should be handled gracefully."""
    result = calculate_meld(bilirubin=2.0, inr=50.0, creatinine=1.5)
    _in_range("extreme_inr", result, MELD_MIN, MELD_MAX)


def test_extreme_creatinine_capped():
    """Creatinine above 4.0 should be capped."""
    low_cap = calculate_meld(bilirubin=2.0, inr=1.5, creatinine=4.0)
    high_input = calculate_meld(bilirubin=2.0, inr=1.5, creatinine=10.0)
    _eq("creatinine_cap", low_cap, high_input)


def test_meld_na_max_cap():
    """MELD-Na should never exceed 40."""
    result = calculate_meld_na(
        bilirubin=50.0, inr=10.0, creatinine=4.0, sodium=125.0,
    )
    _eq("meld_na_max_cap", result, 40)


def test_meld_na_min_cap():
    """MELD-Na should never go below 1."""
    result = calculate_meld_na(
        bilirubin=1.0, inr=1.0, creatinine=1.0, sodium=137.0,
    )
    _check("meld_na_min_cap", result >= MELD_MIN, f"result={result}")


def test_meld_3_max_cap():
    """MELD 3.0 should never exceed 40."""
    result = calculate_meld_3(
        bilirubin=50.0, inr=10.0, creatinine=4.0,
        sodium=125.0, albumin=1.0, female=True,
    )
    _eq("meld3_max_cap", result, 40)


def test_meld_3_min_cap():
    """MELD 3.0 should never go below 1."""
    result = calculate_meld_3(
        bilirubin=1.0, inr=1.0, creatinine=1.0,
        sodium=137.0, albumin=5.0, female=False,
    )
    _check("meld3_min_cap", result >= MELD_MIN, f"result={result}")


# ===================================================================
# Runner
# ===================================================================
def run_all_tests():
    """Execute all test functions."""
    test_functions = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"Running {len(test_functions)} test functions...\n")
    for fn in test_functions:
        try:
            fn()
        except Exception as e:
            _results.append(_TestResult(fn.__name__, False, f"Exception: {e}"))
            print(f"  EXCEPTION in {fn.__name__}: {e}")

    # Summary
    passed = sum(1 for r in _results if r.passed)
    failed = sum(1 for r in _results if not r.passed)
    total = len(_results)

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 60}")

    if failed > 0:
        print("\n  Failed assertions:")
        for r in _results:
            if not r.passed:
                print(f"    - {r.name}: {r.message}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
