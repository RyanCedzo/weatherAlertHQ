# `heuristic_v1` sunset score

Pure function: `src/scoring/heuristic_v1.heuristic_v1(features) -> {score, score_version, grade, drivers, subscores}`.

Input `features` is the dict from `src.features.aggregate_window()` (Stage 1),
optionally passed `sunset_local` so it also includes
`cloud_cover_low_presunset_mean` (the horizon-access proxy).

All numbers below live as constants at the top of `src/scoring/heuristic_v1.py`
— that file is the source of truth; this doc just explains them.

## Subscores and weights

Each subscore is computed independently on a 0-100 scale, then combined as
a weighted sum (weights sum to 1.0):

| Subscore | Weight | Inputs | Idea |
|---|---|---|---|
| `cloud_canvas` | 0.40 | `cloud_cover_mid_mean`, `cloud_cover_high_mean`, `cloud_cover_low_mean` | Reward mid/high cloud in a partial-cover band; penalize empty sky, total overcast, and heavy low cloud blocking the canvas. |
| `horizon_access` | 0.20 | `cloud_cover_low_presunset_mean` | Crude proxy (PROJECT_PLAN.md D9): higher low cloud in the hour(s) right before sunset -> worse. Not real horizon geometry — the API has no directional cloud data. |
| `aerosol_clarity` | 0.25 | `aerosol_optical_depth_mean`, `relative_humidity_2m_mean` | AOD is non-monotonic: a modest band is neutral/good, very high AOD is a penalty. High humidity amplifies the penalty once AOD is already past the good band. |
| `hygiene` | 0.15 | `visibility_mean`, `precipitation_sum`, `pm2_5_mean` | Visibility bonus; precipitation-in-window penalty; extreme PM2.5 penalty. |

Final score = `round(sum(weight * subscore))`, clamped to `[0, 100]`.

## `cloud_canvas`

- `combined_mid_high = (cloud_cover_mid_mean + cloud_cover_high_mean) / 2`
- Base score: 100 when `combined_mid_high` is in `[30, 70]`; falls off
  linearly to 0 at `0` (empty sky) or `100` (total overcast).
- Penalty: if `cloud_cover_low_mean > 50`, subtract up to 30 points
  (linear, maxing out at `cloud_cover_low_mean = 100`).

## `horizon_access`

- `score = 100 * (1 - cloud_cover_low_presunset_mean / 100)`, i.e. a direct
  inverse of pre-sunset low cloud percentage.
- If the pre-sunset window happened to contain no rows, falls back to the
  whole-window `cloud_cover_low_mean` rather than assuming perfect access.

## `aerosol_clarity`

- Base score: 100 when `aerosol_optical_depth_mean` is in `[0.05, 0.20]`;
  falls off linearly to 0 at `0.0` or at the ceiling `0.60`. AOD below the
  band is treated as neutral (not specifically rewarded) — "more aerosols"
  is never treated as better.
- Extra haze penalty (up to 20 points), only applied when
  `aod_mean > 0.20` **and** `relative_humidity_2m_mean > 70`:
  `penalty = 20 * humidity_fraction * aod_fraction`, where each fraction is
  how far past its threshold the value is, normalized over a 30-point
  humidity span and a 0.40 AOD span (each clamped to `[0, 1]`).

## `hygiene`

- Visibility bonus: 0 at/below 5,000 m, 100 at/above 20,000 m, linear
  between.
- Precipitation penalty: `15 * precipitation_sum_mm`, capped at 60 points.
- PM2.5 penalty: 0 at/below 12 µg/m³, ramping linearly to 40 points at
  55 µg/m³ and beyond.
- `hygiene = clamp(visibility_bonus - precip_penalty - pm25_penalty)`

## Grade bands

| Score | Grade |
|---|---|
| 76-100 | excellent |
| 56-75 | good |
| 31-55 | fair |
| 0-30 | poor |

## Drivers

Four strings, one per subscore, each citing the real feature values that
fed that subscore plus the subscore's own 0-100 value — not a debug dump,
but numbers a person can sanity-check against the printed window rows.
