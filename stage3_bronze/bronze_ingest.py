"""Stage 3 bronze ingest logic — plain Python, no PySpark here.

This module does the HTTP ingest (reusing Stage 1's Open-Meteo URL/field
constants) and builds plain Python row dicts for the bronze_api_response
table. It deliberately has no pyspark import so it can be imported and
unit-exercised outside Databricks too; the Databricks notebook
(bronze_ingest_notebook.py) is the only place that touches `spark`/Delta.

Table: env_events_v1.bronze_api_response
Columns: ingest_id, location_id, source, requested_at, payload (string
JSON), http_status, pull_date
"""

from __future__ import annotations

import json
from datetime import date as date_type
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

from src.openmeteo import (
    AIR_QUALITY_HOURLY_FIELDS,
    AIR_QUALITY_URL,
    DEFAULT_TIMEOUT_S,
    WEATHER_HOURLY_FIELDS,
    WEATHER_URL,
)

BRONZE_SCHEMA_NAME = "env_events_v1"
BRONZE_TABLE_NAME = "bronze_api_response"
FULL_TABLE_NAME = f"{BRONZE_SCHEMA_NAME}.{BRONZE_TABLE_NAME}"

SOURCE_WEATHER = "open_meteo_weather"
SOURCE_AIR_QUALITY = "open_meteo_aq"

# One schema only (no Unity Catalog multi-schema sprawl — PROJECT_PLAN.md
# spec corrections). Uses whatever catalog is the workspace default
# (typically hive_metastore on a non-UC-enabled workspace).
CREATE_SCHEMA_SQL = f"CREATE SCHEMA IF NOT EXISTS {BRONZE_SCHEMA_NAME}"

# Column types here must stay in sync with the pyspark StructType built in
# bronze_ingest_notebook.py (duplicated there so this module stays
# pyspark-free).
CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {FULL_TABLE_NAME} (
  ingest_id STRING,
  location_id STRING,
  source STRING,
  requested_at TIMESTAMP,
  payload STRING,
  http_status INT,
  pull_date DATE
) USING DELTA
"""

BRONZE_COLUMNS = [
    "ingest_id",
    "location_id",
    "source",
    "requested_at",
    "payload",
    "http_status",
    "pull_date",
]


def _http_get_raw(url: str, params: Dict[str, Any], timeout_s: int) -> Tuple[int, str]:
    """Plain Python HTTP GET -> (http_status, raw_response_text).

    Basic error handling only (per Stage 3 scope): network/timeout errors
    are caught and recorded as http_status=0 with a small JSON error
    payload, rather than raising and losing the whole ingest run. No
    retries.
    """
    try:
        response = requests.get(url, params=params, timeout=timeout_s)
        return response.status_code, response.text
    except requests.exceptions.RequestException as exc:
        return 0, json.dumps({"error": str(exc)})


def fetch_weather_raw(latitude: float, longitude: float, timezone: str, forecast_days: int = 2) -> Tuple[int, str]:
    """Same request Stage 1's fetch_weather() makes, but returns the raw
    (status_code, response_text) instead of parsed JSON, since bronze
    lands the raw payload string.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(WEATHER_HOURLY_FIELDS),
        "timezone": timezone,
        "forecast_days": forecast_days,
    }
    return _http_get_raw(WEATHER_URL, params, DEFAULT_TIMEOUT_S)


def fetch_air_quality_raw(latitude: float, longitude: float, timezone: str, forecast_days: int = 2) -> Tuple[int, str]:
    """Raw-response counterpart of Stage 1's fetch_air_quality()."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(AIR_QUALITY_HOURLY_FIELDS),
        "timezone": timezone,
        "forecast_days": forecast_days,
    }
    return _http_get_raw(AIR_QUALITY_URL, params, DEFAULT_TIMEOUT_S)


def build_bronze_rows(
    location,
    ingest_id: str,
    requested_at: datetime,
    forecast_days: int = 2,
    pull_date: Optional[date_type] = None,
) -> List[Dict[str, Any]]:
    """Fetch both Open-Meteo APIs for one location and return two bronze
    row dicts (one per source), ready to load into bronze_api_response.

    `location` is a src.config.Location (location_id, latitude, longitude,
    timezone). `pull_date` defaults to "today" in the location's timezone.
    """
    if pull_date is None:
        pull_date = datetime.now(ZoneInfo(location.timezone)).date()

    rows: List[Dict[str, Any]] = []
    for source, fetch_fn in (
        (SOURCE_WEATHER, fetch_weather_raw),
        (SOURCE_AIR_QUALITY, fetch_air_quality_raw),
    ):
        http_status, payload = fetch_fn(location.latitude, location.longitude, location.timezone, forecast_days)
        rows.append(
            {
                "ingest_id": ingest_id,
                "location_id": location.location_id,
                "source": source,
                "requested_at": requested_at,
                "payload": payload,
                "http_status": http_status,
                "pull_date": pull_date,
            }
        )
    return rows
