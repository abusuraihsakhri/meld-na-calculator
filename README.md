# MELD 3.0 / MELD-Na Calculator

A compact, locally running calculator for **adult MELD 3.0**, with **historical MELD-Na (2016)** and **original MELD** scores for comparison. Provides a standalone browser interface, Python calculation functions, a CLI with CSV batch processing, and an optional FastAPI service.

**Clinical scope:** Educational and methodological reference only. This is not the official OPTN allocation calculator and does not assign transplant priority, Status 1A/1B, or exception points. MELD 3.0 was introduced for U.S. adult allocation in July 2023. The adolescent (12–17 years) formula differs; PELD applies to younger children.

## Browser calculator

Open [web/index.html](web/index.html) in a modern browser, or serve the `web/` directory:

```bash
python -m http.server 8001 --directory web
# Then visit http://localhost:8001/
```

Enter bilirubin (mg/dL), INR, creatinine (mg/dL), sodium (mEq/L), albumin (g/dL), sex used for the adult formula, and whether the dialysis criterion is met. Calculate to view all three scores and the laboratory caps applied. A CSV export of the scores and laboratory inputs is available. **Everything in this browser UI is calculated locally**: there are no third-party scripts, uploads, analytics, browser storage, or external API calls. External reference pages are visited only if you choose to open a link.

A [GitHub Pages publishing workflow](.github/workflows/pages.yml) is included. The public URL should be used only after the deployment is enabled and verified.

## Clinical equations

**Adult MELD 3.0** (Kim et al., *Gastroenterology*, 2021):

```text
1.33 × female + 4.56 × ln(bilirubin)
+ 0.82 × (137 − sodium)
− 0.24 × (137 − sodium) × ln(bilirubin)
+ 9.09 × ln(INR) + 11.14 × ln(creatinine)
+ 1.85 × (3.5 − albumin)
− 1.83 × (3.5 − albumin) × ln(creatinine) + 6
```

Values below 1 are floored to 1 for bilirubin, INR, and creatinine. Sodium is bounded to 125–137 mEq/L, albumin to 1.5–3.5 g/dL, and creatinine to 3.0 mg/dL for MELD 3.0. Qualifying dialysis sets creatinine to 3.0 mg/dL for MELD 3.0 (but 4.0 for the legacy models). Qualifying dialysis is at least two sessions or 24 hours of CVVHD in the prior week. Each score is rounded to a whole number and bounded to 6–40. Nonpositive, nonfinite, and missing required laboratory values are rejected.

**Historical MELD-Na (2016):** MELD + 1.32 × (137 − sodium) − 0.033 × MELD × (137 − sodium), with the sodium adjustment applied only if original MELD exceeds 11. These historical scores are displayed as comparators and must not be substituted for current OPTN allocation calculations.

The optional historical 90-day mortality strata in the Python CLI are associated with **original MELD**. They must not be interpreted as individual predictions or as validated MELD 3.0 mortality estimates.

## Python CLI and API

Requires Python 3.10 or later. Install the project:

```bash
python -m pip install -e .
python cli.py calculate --bilirubin 2.5 --inr 1.8 --creatinine 1.5 --sodium 135 --albumin 3.2
python cli.py calculate --bilirubin 2.5 --inr 1.8 --creatinine 1.5 --sodium 135 --albumin 3.2 --female --json
python cli.py batch --input sample.csv --output output.csv
```

Batch CSV requires `bilirubin`, `inr`, `creatinine`, and `sodium` (documented aliases are accepted), with optional `albumin`, `sex`, and `dialysis`; `sex` (or a consistent `female` flag) is required when albumin is provided to calculate MELD 3.0. Rows with missing/invalid inputs are marked `ERROR`, not silently imputed. Exported spreadsheet-formula-like text cells are escaped.

To run the optional web service, including the same browser calculator:

```bash
python cli.py serve --host 127.0.0.1 --port 8000
# Browser: http://127.0.0.1:8000/
# Interactive HTTP docs: http://127.0.0.1:8000/docs
```

`POST /api/calculate` accepts a JSON body such as:

```json
{"bilirubin":2.5,"inr":1.8,"creatinine":1.5,"sodium":135,"albumin":3.2,"female":false,"dialysis":false}
```

The optional `/api/audit`, `/api/chat`, and `/api/audit/logs` endpoints are legacy demonstration features, **not clinical scoring or validated safety systems**. The chat endpoint is a deterministic placeholder, not live model inference; the audit log is in-memory and its HMAC chain is checked using the process key.

For Docker Compose, generate a unique `AUDIT_SECRET_KEY` and set it via the shell environment or an untracked `.env` based on `.env.example` before starting `docker compose up --build`. Never reuse the sample placeholder or commit the generated secret.

## Tests

```bash
python -m pip install -e ".[test]"
python -m pytest -q
python test_meld_na.py
node --check web/calculator.js
node --test web/test_calculator.cjs
```

GitHub Actions runs the Python suite on Python 3.10–3.12 and the browser math tests on Node 22.

## Privacy and limitations

The static browser application has no server interaction and does not retain laboratory inputs. The optional Python server and CLI may process locally supplied data and should be deployed only within an appropriately secured environment; their limited regex identifier checks do **not** establish HIPAA compliance or complete PHI de-identification. Avoid sharing patient-identifiable CSVs.

Scores are not exception-point eligibility determinations, allocation decisions, or standalone clinical guidance. Confirm transplantation decisions and any policy-dependent score with your transplant service and the official calculator.

## References

- [HRSA / OPTN MELD calculator](https://www.hrsa.gov/optn/data-calculators/allocation-calculators/meld-calculator)
- Kim WR et al. *MELD 3.0: The Model for End-Stage Liver Disease Updated for the Modern Era.* Gastroenterology. 2021;161:1887–1895.e4.
- [Adult and adolescent MELD equation comparison](https://pmc.ncbi.nlm.nih.gov/articles/PMC10363200/)

## License

MIT — see [LICENSE](LICENSE).
