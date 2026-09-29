"""Stage 1 + Stage 2 entry point.

Load one location -> fetch Open-Meteo weather + air quality -> compute
sunset time/azimuth -> join on timestamp -> print sunset-window rows and
aggregates -> score the window with heuristic_v1 and print a score card.

Usage:
    python -m src.main
    python -m src.main --location-id home
    python -m src.main --save-fixtures
    python -m src.main --offline           # reuse previously saved fixtures
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_location  # noqa: E402
from src.features import (  # noqa: E402
    aggregate_window,
    filter_sunset_window,
    join_weather_and_air_quality,
)
from src.fixtures import load_fixture, save_fixture  # noqa: E402
from src.openmeteo import (  # noqa: E402
    AIR_QUALITY_HOURLY_FIELDS,
    WEATHER_HOURLY_FIELDS,
    fetch_air_quality,
    fetch_weather,
)
from src.scoring.heuristic_v1 import heuristic_v1  # noqa: E402
from src.solar import compute_sunset  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Stage 1 local sunset-window prototype")
    parser.add_argument("--location-id", default=None, help="location_id from config/locations.yaml")
    parser.add_argument("--forecast-days", type=int, default=2, help="Open-Meteo forecast_days (default 2)")
    parser.add_argument("--save-fixtures", action="store_true", help="Save raw weather+AQ JSON to fixtures/")
    parser.add_argument("--offline", action="store_true", help="Load weather+AQ JSON from fixtures/ instead of HTTP")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    location = load_location(location_id=args.location_id)

    print(f"Location: {location.name} ({location.location_id})")
    print(f"  lat/lon: {location.latitude}, {location.longitude}")
    print(f"  timezone: {location.timezone}")
    print()

    if args.offline:
        print("Loading weather + air quality from saved fixtures (--offline)...")
        weather_json = load_fixture("weather")
        air_quality_json = load_fixture("air_quality")
    else:
        print("Fetching Open-Meteo weather...")
        weather_json = fetch_weather(
            location.latitude, location.longitude, location.timezone, args.forecast_days
        )
        print("Fetching Open-Meteo air quality...")
        air_quality_json = fetch_air_quality(
            location.latitude, location.longitude, location.timezone, args.forecast_days
        )

    if args.save_fixtures:
        weather_path = save_fixture(weather_json, "weather")
        aq_path = save_fixture(air_quality_json, "air_quality")
        print(f"Saved fixtures: {weather_path}, {aq_path}")

    weather_hourly_keys = set(weather_json.get("hourly", {}).keys())
    aq_hourly_keys = set(air_quality_json.get("hourly", {}).keys())
    print()
    print("Fields confirmed present:")
    print(f"  weather hourly: {sorted(k for k in WEATHER_HOURLY_FIELDS if k in weather_hourly_keys)}")
    print(f"  air quality hourly: {sorted(k for k in AIR_QUALITY_HOURLY_FIELDS if k in aq_hourly_keys)}")

    sunset = compute_sunset(location.latitude, location.longitude, location.timezone)
    print()
    print(f"Sunset ({sunset.local_date}):")
    print(f"  local:   {sunset.sunset_local.isoformat()}")
    print(f"  UTC:     {sunset.sunset_utc.isoformat()}")
    print(f"  azimuth: {sunset.azimuth_deg:.1f} deg")

    joined_rows = join_weather_and_air_quality(weather_json, air_quality_json)
    window_rows = filter_sunset_window(joined_rows, sunset.sunset_local)

    print()
    print(f"Sunset window rows [sunset-2h, sunset+1h] -> {len(window_rows)} hour(s):")
    for row in window_rows:
        print(f"  {json.dumps(row, default=str)}")

    aggregates = aggregate_window(window_rows, sunset_local=sunset.sunset_local)
    print()
    print("Window aggregates:")
    print(json.dumps(aggregates, indent=2, default=str))

    card = heuristic_v1(aggregates)
    print()
    print("=== Today's sunset score card ===")
    print(f"  Location: {location.name}")
    print(f"  Sunset (local): {sunset.sunset_local.isoformat()}")
    print(f"  Score: {card['score']}/100 ({card['grade']}) [{card['score_version']}]")
    print("  Drivers:")
    for driver in card["drivers"]:
        print(f"    - {driver}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
