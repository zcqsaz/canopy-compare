# Canopy Compare

Review historical canopy changes from a computer. The viewer uses a historical forecast to flag candidate image dates. It puts two existing, time-stamped photographs side by side, reveals the independently recorded colour index on request, and exports a reviewer's visual interpretation with both original archive links. Open **`index.html`** in a current browser. The two archive windows, images, model results and observations work offline. Opening an original image on the PhenoCam website needs internet access.

## Try two real cases

1. Start at the 8 May 2025 issue, greenness, through 15 May. Open **Compare images** for **STEI** (Steigerwaldt-Chequamegon, Wisconsin). Compare the canopy on 6 and 15 May. Choose what you see. Then enable **Reveal later observations**. The green index reached 0.44603 against a recent baseline of 0.35067. The model identified the direction and underestimated the size of the increase.
2. Choose 9 October 2025, redness, through 16 October. **TREE** (Treehaven, Wisconsin) ranked first. The model expected a drop from 0.50248 to 0.41969. The observed value was 0.51467. Use the original photographs to interpret the disagreement.
3. **Export review log** downloads a CSV with the ranking, dates, thresholds, forecast and observed values, visual marks and links to both original photographs. Marks are keyed by historical issue, site, comparison date and index. They persist on the current device when browser storage is available. If storage is disabled, the viewer keeps marks in the current session and the CSV preserves them.

![Actual offline comparison of the same Wisconsin canopy on 6 and 15 May 2025](evidence/spring-pair.png)

In the comparison dialog, turn on **Show measured canopy region** to see which vegetation contributed to PhenoCam’s colour measurement. The gold outline and dimmed background use the archive’s dated sampling mask. Each verified frame links to its original TIFF. The switch preserves the blind visual review and leaves later observations hidden until requested. [Measured region in the spring pair](evidence/measured-region.png)

For the STEI spring flag, the remote entrant was asked to look at the outlined canopy in the two photographs before comparing the recorded values. The entrant reported viewing both images and chose to keep the greening flag. The independently recorded daily green index rose from 0.35728 on 6 May to 0.44603 on 15 May. [Entrant’s reply, source images and subsequent numerical check](evidence/entrant-review.md)

The archive supplied 208 photos at 14 sites. For 197 photos, exactly one dated mask reproduced all three published midday channel means to within one count on the 0–255 scale. Sixteen of those photos had two eligible masks before the RGB check. One other photo had a different midday filename and ten exceeded the colour tolerance. The viewer keeps the original photos available for all 11. On the 197 accepted frames, the median maximum channel difference from the published RGB was 0.0042 with the mask and 32.95 across the whole image. These measurements check whether the overlay matches the archive’s sampling area.

[Autumn forecast compared with observations](evidence/autumn-miss.png) · [Exported review log preview](evidence/review-log.png)

## How an archive date gets flagged

For a historical issue, the model estimated a mean and error scale for each site, index and target day. It combined seasonal history, matching trajectories in earlier years and a fitted gradient-boosted correction. The baseline is the median of available observations in the four days ending on that site's last reported day before the historical issue, allowing the model's two-day latency. The interface requires a baseline within seven days and two verified, locally archived image files.

For each eligible pair the viewer calculates `|forecast mean − baseline| − 0.84162 × forecast standard deviation`. Under the fitted normal-error assumption with a fixed observed baseline, this is a one-sided 80% lower bound for the magnitude of change in the selected direction. The viewer selects the best available date per site and flags candidates crossing the selected threshold. It never reads the observed *value* or visual mark to score a pair. Archival availability limits the candidates. The central 80% band in the chart describes the index forecast separately. Correlation across dates and selecting the largest score affect interpretation of the flag.

## What held up in later years

The predictive model trained on target dates before 2023 and calibrated errors on 2023. The later evaluation uses 14 sites selected for current reporting status. The published target file contains provisional historical observations and can change retrospectively. This replay models a two-day observation lag. Historical releases were not separately retrieved to recover every provisional value as originally posted.

| Forecast year | Scored site/day/index values¹ | Model CRPS | Last observed colour CRPS | Seasonal CRPS |
|---|---:|---:|---:|---:|
| 2024 | 20,834 | 0.00778 | 0.01133 | 0.00960 |
| 2025 | 20,054 | 0.00741 | 0.01035 | 0.00947 |
| 2026 | 18,044 | 0.00741 | 0.01066 | 0.00950 |

¹Only issue and target dates falling in the same listed year. Lower continuous ranked probability score (CRPS) is better. Across all 60,014 archived verified values, including forecasts spanning a year boundary, nominal central 80% intervals covered 82.88% of green and 86.45% of red observations.

The *decision* evaluation asks a different question. For each of 74 biweekly issues from January 2024 to October 2026, select three site/date pairs for remote archive review within seven days. A hit is an observed absolute index shift of at least 0.010 from the decision-time baseline. The comparison restricts all methods to the same sites with seven verifying days, two usable pre-issue windows and at least six available sites. The recent-trend policy ranks by the absolute change between two pre-issue four-day windows seven days apart and uses the archived index on day seven. Each column contains 222 site/date selections. Unobserved targets could change these estimates.

| Review policy | Green hits | Mean absolute green shift | Red hits | Mean absolute red shift |
|---|---:|---:|---:|---:|
| Planner chooses day | 37.39% | 0.01235 | 56.76% | 0.02472 |
| Predicted change without uncertainty discount | 35.14% | 0.01208 | 61.71% | 0.02556 |
| Planner ranks sites on day seven | 39.64% | 0.01292 | 54.95% | 0.02553 |
| Recent trend, day seven | 32.88% | 0.01081 | 59.91% | 0.02348 |

Discounting uncertainty improved green hit rate by 2.25 percentage points relative to using the predicted change alone. It reduced red hit rate by 4.95 points. In the October Treehaven replay the red forecast even misses the direction. Lighting, snow, shadows, camera angle and region selection can change image-derived indices. A reviewer compares the archived images before marking a change. The index alone does not identify the cause.

## Reproduce

The viewer reads `data/bundle.js` locally and makes no automatic network calls. The optional CPU rebuild uses Python 3.12 and the packages in `requirements.txt`.

```text
python -m pip install -r requirements.txt
python model/forecast.py --issue 2026-11-26
python prepare.py
```

The frozen input gzip and its SHA-256 are bundled in `model/`. `prepare.py` reconstructs browser data and the decision evaluation using the bundled CSV metadata and images. Add `--images` to fill missing archival frames from PhenoCam. Image origin URLs and checksums are recorded in `data/images.json`. Published and preserved observations are credited in [DATA.md](DATA.md).

To reproduce the measured-region overlays, run `python prepare_regions.py --cache ../roi-cache`. It downloads original archive JPEGs, mask registries, daily summaries and the dated mask TIFFs. It checks the original photo hash and compares masked mean RGB against the publisher’s midday measurement. The bundled overlays work offline. [Frame-by-frame evidence](data/regions.js) · [Validation summary](evidence/region_verification.json)

Optional UI regression checks use Playwright 1.64.1 for Python and its headless Chromium shell. Install with `python -m pip install playwright==1.64.1` and `python -m playwright install chromium --only-shell`. Then `python evidence/check_ui.py` reproduces the checks in [evidence/ui_checks.json](evidence/ui_checks.json). They verify ordinary spring and autumn cases, persistent visual marks, repeated exports, all available image pairs in one week, no matching site, an unsupported date, blocked storage, outcome isolation and mobile overflow. Raw per-site decisions and aggregate outputs are in `evidence/`. The optional demonstration recording source is in `evidence/demo/`. It uses the same offline app, Windows Speech, a headless renderer and FFmpeg.

## Contributions and development disclosure

The pre-existing EFI/NEON forecast pipeline supplied the historical model predictions and held-out forecast tests. During the event the entrant specified that their work had to be entirely remote. That requirement led to restricting the workflow to completed archive dates, linking actual before/after photographs, adding a persistent visual interpretation and including both sources in the exported log. Codex implemented the application, model-to-archive selection, interface, tests, media preparation and documentation in response. The entrant reviewed one STEI photo pair and retained its greening flag. The demonstration’s interface actions and the regression tests use scripted visual marks.

The runtime model uses a fitted gradient-boosted predictor. Ranking and archive review run locally without a generative model or external AI service. NEON, the PhenoCam Network and EFI supplied the external imagery, site information and observations. All performance values are local retrospective evaluations.
