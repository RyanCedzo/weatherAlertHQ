"""Thin HTTP clients for the Open-Meteo Weather and Air Quality APIs.

Stage 1 scope only: two plain HTTP GET calls per run, basic error handling
via requests' raise_for_status(). No retries, no caching layer, no SDK.
"""

from __future__ import annotations

from typing import Any, Dict

import requests

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

WEATHER_HOURLY_FIELDS = [
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "relative_humidity_2m",
    "visibility",
    "precipitation",
    "weather_code",
]

AIR_QUALITY_HOURLY_FIELDS = [
    "aerosol_optical_depth",
    "pm2_5",
]

DEFAULT_TIMEOUT_S = 15


def fetch_weather(
    latitude: float,
    longitude: float,
    timezone: str,
    forecast_days: int = 2,
) -> Dict[str, Any]:
    """Fetch hourly weather forecast fields for one location."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(WEATHER_HOURLY_FIELDS),
        "timezone": timezone,
        "forecast_days": forecast_days,
    }
    response = requests.get(WEATHER_URL, params=params, timeout=DEFAULT_TIMEOUT_S)
    response.raise_for_status()
    return response.json()


def fetch_air_quality(
    latitude: float,
    longitude: float,
    timezone: str,
    forecast_days: int = 2,
) -> Dict[str, Any]:
    """Fetch hourly air-quality forecast fields for one location."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(AIR_QUALITY_HOURLY_FIELDS),
        "timezone": timezone,
        "forecast_days": forecast_days,
    }
    response = requests.get(AIR_QUALITY_URL, params=params, timeout=DEFAULT_TIMEOUT_S)
    response.raise_for_status()
    return response.json()
