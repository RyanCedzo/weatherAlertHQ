"""Load the single Stage 1 location from config/locations.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "locations.yaml"


@dataclass(frozen=True)
class Location:
    location_id: str
    name: str
    latitude: float
    longitude: float
    timezone: str
    active: bool = True


def load_location(
    config_path: Path = DEFAULT_CONFIG_PATH,
    location_id: Optional[str] = None,
) -> Location:
    """Load one location from the YAML config.

    If location_id is None, returns the first location marked active: true
    (or the first location in the file if none are marked active).
    """
    with open(config_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    locations = data.get("locations") or []
    if not locations:
        raise ValueError(f"No locations defined in {config_path}")

    if location_id is not None:
        for entry in locations:
            if entry.get("location_id") == location_id:
                return _to_location(entry)
        raise ValueError(f"location_id={location_id!r} not found in {config_path}")

    for entry in locations:
        if entry.get("active", True):
            return _to_location(entry)

    return _to_location(locations[0])


def _to_location(entry: dict) -> Location:
    return Location(
        location_id=entry["location_id"],
        name=entry.get("name", entry["location_id"]),
        latitude=float(entry["latitude"]),
        longitude=float(entry["longitude"]),
        timezone=entry["timezone"],
        active=bool(entry.get("active", True)),
    )
