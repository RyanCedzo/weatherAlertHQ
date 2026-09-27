"""Join weather + air-quality hourly arrays on timestamp and build the
sunset-window feature view.

Deliberately plain Python (dict/list) — no pandas/Spark. Stage 1 only needs
to prove the data and window logic, not build a dataframe framework.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

# Sunset window: [sunset - 2h, sunset + 1h]
WINDOW_BEFORE = timedelta(hours=2)
WINDOW_AFTER = timedelta(hours=1)


def _hourly_to_rows(hourly: Dict[str, List[Any]]) -> Dict[str, Dict[str, Any]]:
    """Convert an Open-Meteo `hourly` block (parallel arrays keyed by field
    name, aligned to hourly["time"]) into {timestamp_str: {field: value}}.
    """
    times = hourly.get("time", [])
    fields = [key for key in hourly.keys() if key != "time"]

    rows: Dict[str, Dict[str, Any]] = {}
    for idx, ts in enumerate(times):
        row = {field: hourly[field][idx] for field in fields}
        rows[ts] = row
    return rows


def join_weather_and_air_quality(
    weather_json: Dict[str, Any],
    air_quality_json: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Join hourly weather + AQ rows on the local timestamp string.

    Open-Meteo returns naive local timestamps (e.g. "2026-09-27T18:00") when
    a `timezone` param is supplied, so a plain string join is sufficient
    here as long as both calls used the same location timezone.
    """
    weather_rows = _hourly_to_rows(weather_json.get("hourly", {}))
    aq_rows = _hourly_to_rows(air_quality_json.get("hourly", {}))

    joined: List[Dict[str, Any]] = []
    for ts in sorted(set(weather_rows) & set(aq_rows)):
        row = {"time": ts}
        row.update(weather_rows[ts])
        row.update(aq_rows[ts])
        joined.append(row)
    return joined


def filter_sunset_window(
    rows: List[Dict[str, Any]],
    sunset_local: datetime,
) -> List[Dict[str, Any]]:
    """Select rows with naive local timestamp in [sunset-2h, sunset+1h]."""
    window_start = sunset_local.replace(tzinfo=None) - WINDOW_BEFORE
    window_end = sunset_local.replace(tzinfo=None) + WINDOW_AFTER

    windowed = []
    for row in rows:
        row_time = datetime.fromisoformat(row["time"])
        if window_start <= row_time <= window_end:
            windowed.append(row)
    return windowed


def aggregate_window(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Simple aggregates over the sunset window: means for cloud/humidity/
    visibility/AOD, sum for precipitation, plus the raw weather-code list.
    """
    if not rows:
        return {"hour_count": 0}

    def mean(field: str) -> float:
        values = [row[field] for row in rows if row.get(field) is not None]
        return sum(values) / len(values) if values else float("nan")

    def total(field: str) -> float:
        values = [row[field] for row in rows if row.get(field) is not None]
        return sum(values)

    return {
        "hour_count": len(rows),
        "cloud_cover_mean": mean("cloud_cover"),
        "cloud_cover_low_mean": mean("cloud_cover_low"),
        "cloud_cover_mid_mean": mean("cloud_cover_mid"),
        "cloud_cover_high_mean": mean("cloud_cover_high"),
        "relative_humidity_2m_mean": mean("relative_humidity_2m"),
        "visibility_mean": mean("visibility"),
        "aerosol_optical_depth_mean": mean("aerosol_optical_depth"),
        "pm2_5_mean": mean("pm2_5"),
        "precipitation_sum": total("precipitation"),
        "weather_codes": [row.get("weather_code") for row in rows],
    }
