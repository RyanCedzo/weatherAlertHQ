# weatherAlertHQ

Initial testing/work with weather-related data. See `PROJECT_PLAN.md` for the
full roadmap; this repo currently implements **Stage 1 — Local data
prototype** and **Stage 2 — Local heuristic** only (no Databricks/Spark/
Delta/UI/ML yet).

## Stage 1 — what's here

A tiny local Python project that, for one configured location:

1. Fetches Open-Meteo **weather** hourly forecast (cloud cover total/low/mid/high,
   humidity, visibility, precipitation, weather code).
2. Fetches Open-Meteo **air quality** hourly forecast (aerosol optical depth, PM2.5).
3. Computes sunset time + azimuth locally with the `astral` library (no
   external solar HTTP API).
4. Joins weather + AQ on timestamp, filters to the sunset window
   `[sunset-2h, sunset+1h]`, and prints the window rows plus simple
   aggregates (means/sum).
5. Optionally saves the raw JSON responses to `fixtures/` so the join/window
   logic can be re-run offline.

```
config/locations.yaml   # one location (lat/lon/timezone) — confirm before running
requirements.txt
docs/heuristic_v1.md    # formula write-up for the Stage 2 scorer
src/
  config.py              # load the location from YAML
  openmeteo.py            # HTTP GET calls to Open-Meteo weather + air-quality
  solar.py                # sunset time/azimuth via astral (local computation)
  features.py             # join hourly rows, sunset-window filter, aggregates
  fixtures.py             # save/load raw JSON fixtures for offline reruns
  scoring/
    heuristic_v1.py        # Stage 2: transparent 0-100 score + drivers
  main.py                 # CLI entry point wiring the above together
fixtures/                 # generated JSON fixtures (git-ignored)
```

## Setup

```bash
pip install -r requirements.txt
```

Before running, open `config/locations.yaml` and confirm/replace the
`latitude`, `longitude`, and `timezone` values with your actual location —
they are placeholder/example values and must be correct for the sunset
calculation and API results to mean anything.

## Run

```bash
python -m src.main                  # live fetch, print sunset window + aggregates + score card
python -m src.main --save-fixtures  # also save weather.json / air_quality.json
python -m src.main --offline        # reuse previously saved fixtures, no network
python -m src.main --location-id home --forecast-days 2
```

Every run ends with a `heuristic_v1` score card: sunset time, a 0-100 score,
a grade (`poor`/`fair`/`good`/`excellent`), and 3-6 driver strings citing the
actual feature values behind the subscores. See `docs/heuristic_v1.md` for
the formula (weights/bands live in `src/scoring/heuristic_v1.py`).

## Stage 1 acceptance notes

Fields confirmed present in a live pull for the configured location
(Erie, PA — 2026-09-27):

- Weather hourly: `cloud_cover`, `cloud_cover_low`, `cloud_cover_mid`,
  `cloud_cover_high`, `relative_humidity_2m`, `visibility`, `precipitation`,
  `weather_code`
- Air quality hourly: `aerosol_optical_depth`, `pm2_5`

Sunset for that date/location computed locally (via `astral`) as
`2026-09-27T19:08:58-04:00`, azimuth `~268°` — plausible for the location and
time of year. The sunset window `[sunset-2h, sunset+1h]` returned 3 hourly
rows, within the expected ~3-4 hour range.

Explicitly **not** built in Stage 1: scoring/heuristic, Databricks, Spark,
Delta, job scheduler, UI, multi-location loops, retry frameworks. See
`PROJECT_PLAN.md` Stage 1 for the full scope lock.

## Stage 2 acceptance notes

`heuristic_v1` is a pure function (`src/scoring/heuristic_v1.py`): the same
feature dict always yields the same score, drivers cite the real feature
values, and bumping a weight moves the score in the expected direction
(verified manually — e.g. raising the `horizon_access` weight while that
subscore is bad pulls the total score down, as expected). Explicitly not
built in Stage 2: ML/MLflow, Databricks/Spark/Delta, score persistence,
notifications, multi-location, UI. See `PROJECT_PLAN.md` Stage 2 for the
full scope lock.
