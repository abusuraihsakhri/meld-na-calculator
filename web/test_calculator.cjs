"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
const { calculate } = require("./calculator.js");

test("independent reference values for MELD 3.0 and legacy formulas", () => {
  const caseData = { bilirubin: 2.5, inr: 1.8, creatinine: 1.5,
    sodium: 135, albumin: 3.2, sex: "male", dialysis: false };
  assert.deepEqual(
    [calculate(caseData).meld_3, calculate(caseData).meld_na, calculate(caseData).meld],
    [22, 21, 20]
  );
  assert.equal(calculate({ ...caseData, sex: "female" }).meld_3, 23);
});

test("floor, upper bounds and female adjustment", () => {
  assert.equal(calculate({ bilirubin: .5, inr: .8, creatinine: .9,
    sodium: 140, albumin: 4, sex: "male" }).meld_3, 6);
  assert.equal(calculate({ bilirubin: 1, inr: 1, creatinine: 1,
    sodium: 137, albumin: 3.5, sex: "female" }).meld_3, 7);
});

test("dialysis uses 3 mg/dL for MELD 3.0 and 4 mg/dL for old scores", () => {
  const result = calculate({ bilirubin: 2.5, inr: 1.8, creatinine: .8,
    sodium: 135, albumin: 3.2, sex: "male", dialysis: true });
  assert.equal(result.applied.creatinine_meld3, 3);
  assert.equal(result.applied.creatinine_meld, 4);
});

test("rejects missing, negative, infinite and malformed values", () => {
  const valid = { bilirubin: 2.5, inr: 1.8, creatinine: 1.5,
    sodium: 135, albumin: 3.2, sex: "male" };
  for (const value of ["", -1, Infinity, NaN, "bad", 0]) {
    assert.throws(() => calculate({ ...valid, sodium: value }));
  }
  assert.throws(() => calculate({ ...valid, sex: "unknown" }));
});

test("sodium is still checked when legacy MELD has no sodium adjustment", () => {
  assert.throws(() => calculate({ bilirubin: 1, inr: 1, creatinine: 1,
    sodium: "", albumin: 3.5, sex: "male" }));
});
