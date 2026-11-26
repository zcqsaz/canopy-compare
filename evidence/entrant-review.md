# Human Visual Check at STEI (May 2025)

Before revealing the held-out numerical observations for the **8 May 2025** spring greenness flag at **Steigerwaldt-Chequamegon (`STEI`)**, Wisconsin, I inspected the two archived PhenoCam frames side by side with the verified deciduous broadleaf canopy ROI overlay enabled.

- **Recorded decision:** “看过两张照片，保留提示” (*"I looked at both photos. Keep the flag."*)
- **Scope:** Applies to the spring greening flag for the `6 May` → `15 May 2025` STEI pair. (Note: clicks and selection marks in the automated UI test suite and recorded walkthrough video are scripted for reproducibility.)

[6 May 2025 original photograph](https://phenocam.nau.edu/data/archive/NEON.D05.STEI.DP1.00033/2025/05/NEON.D05.STEI.DP1.00033_2025_05_06_120005.jpg) · [15 May 2025 original photograph](https://phenocam.nau.edu/data/archive/NEON.D05.STEI.DP1.00033/2025/05/NEON.D05.STEI.DP1.00033_2025_05_15_120005.jpg) · [Side-by-side ROI view](measured-region.png)

## Observations revealed after the visual check

Once the flag was kept, I revealed the held-out ground-truth series:

- Between the two photo dates, the daily green chromatic coordinate (`gcc_90`) climbed from **0.35728** (6 May) to **0.44603** (15 May), a jump of **+0.08875**.
- Against the four-day pre-issue baseline of **0.35067** (3–6 May median), the model had forecast **0.39732** (`+0.04665`) for 15 May, while the actual observed increase from baseline was **+0.09536**. The retained flag matched the direction of real canopy leaf-out, though the model underestimated its magnitude.

[Frozen daily observations](../model/phenology-targets.csv.gz) · [UI verification output](ui_checks.json) · [Frame-by-frame mask verification](../data/regions.js)
