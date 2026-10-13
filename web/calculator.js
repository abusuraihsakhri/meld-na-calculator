/* Pure client-side MELD calculation; no uploads, storage or network requests. */
(function (root) {
  "use strict";
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const score = raw => clamp(Math.floor(raw + 0.5), 6, 40);

  function positiveFinite(value, name) {
    if (value === "" || value === null || value === undefined) {
      throw new Error(name + " is required.");
    }
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) {
      throw new Error(name + " must be a positive, finite number.");
    }
    return n;
  }

  function calculate(data) {
    const bilirubin = positiveFinite(data.bilirubin, "Bilirubin");
    const inr = positiveFinite(data.inr, "INR");
    const creatinine = positiveFinite(data.creatinine, "Creatinine");
    const sodium = positiveFinite(data.sodium, "Sodium");
    const albumin = positiveFinite(data.albumin, "Albumin");
    if (data.sex !== "male" && data.sex !== "female") {
      throw new Error("Select sex for adult MELD 3.0.");
    }
    const dialysis = data.dialysis === true;
    const bili = clamp(bilirubin, 1, Infinity);
    const coag = clamp(inr, 1, Infinity);
    const creatLegacy = dialysis ? 4 : clamp(creatinine, 1, 4);
    const creat3 = dialysis ? 3 : clamp(creatinine, 1, 3);
    const na = clamp(sodium, 125, 137);
    const alb = clamp(albumin, 1.5, 3.5);
    const gapNa = 137 - na;
    const gapAlb = 3.5 - alb;
    const meld = score(
      3.78 * Math.log(bili) + 11.2 * Math.log(coag) +
      9.57 * Math.log(creatLegacy) + 6.43
    );
    const meldNa = meld <= 11 ? meld : score(
      meld + 1.32 * gapNa - 0.033 * meld * gapNa
    );
    const meld3 = score(
      (data.sex === "female" ? 1.33 : 0) +
      4.56 * Math.log(bili) + 0.82 * gapNa -
      0.24 * gapNa * Math.log(bili) +
      9.09 * Math.log(coag) + 11.14 * Math.log(creat3) +
      1.85 * gapAlb - 1.83 * gapAlb * Math.log(creat3) + 6
    );
    return {
      meld: meld,
      meld_na: meldNa,
      meld_3: meld3,
      applied: { bilirubin: bili, inr: coag, creatinine_meld: creatLegacy,
        creatinine_meld3: creat3, sodium: na, albumin: alb, dialysis: dialysis,
        sex: data.sex }
    };
  }

  function setup() {
    const form = document.getElementById("meld-form");
    if (!form) return;
    const error = document.getElementById("error");
    const results = document.getElementById("results");
    const exportButton = document.getElementById("export");
    let latest = null;

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      error.textContent = "";
      try {
        const fields = new FormData(form);
        latest = calculate({
          bilirubin: fields.get("bilirubin"),
          inr: fields.get("inr"),
          creatinine: fields.get("creatinine"),
          sodium: fields.get("sodium"),
          albumin: fields.get("albumin"),
          sex: fields.get("sex"),
          dialysis: fields.has("dialysis")
        });
        document.getElementById("meld3-value").textContent = latest.meld_3;
        document.getElementById("meldna-value").textContent = latest.meld_na;
        document.getElementById("meld-value").textContent = latest.meld;
        const a = latest.applied;
        document.getElementById("adjustments").textContent =
          "Formula inputs after caps: bilirubin " + a.bilirubin +
          " mg/dL; INR " + a.inr + "; creatinine " + a.creatinine_meld3 +
          " mg/dL for MELD 3.0 (" + a.creatinine_meld +
          " mg/dL for legacy MELD); sodium " + a.sodium +
          " mEq/L; albumin " + a.albumin + " g/dL.";
        results.hidden = false;
        document.getElementById("empty").hidden = true;
        exportButton.disabled = false;
        results.focus();
      } catch (exc) {
        latest = null;
        results.hidden = true;
        document.getElementById("empty").hidden = false;
        exportButton.disabled = true;
        error.textContent = exc.message || "Could not calculate scores.";
      }
    });

    form.addEventListener("reset", function () {
      latest = null;
      results.hidden = true;
      document.getElementById("empty").hidden = false;
      exportButton.disabled = true;
      error.textContent = "";
    });
    exportButton.addEventListener("click", function () {
      if (!latest) return;
      const a = latest.applied;
      const headers = ["meld_3","meld_na_2016","meld_original","bilirubin_mgdl",
        "inr","creatinine_mgdl_meld3","creatinine_mgdl_legacy","sodium_meql",
        "albumin_gdl","sex","dialysis"];
      const values = [latest.meld_3, latest.meld_na, latest.meld, a.bilirubin,
        a.inr, a.creatinine_meld3, a.creatinine_meld, a.sodium, a.albumin,
        a.sex, a.dialysis];
      const csv = headers.join(",") + "\r\n" + values.join(",") + "\r\n";
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "meld-scores.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    });
  }
  root.MeldCalculator = { calculate: calculate };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { calculate: calculate };
  }
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", setup);
    } else {
      setup();
    }
  }
})(typeof window !== "undefined" ? window : globalThis);
