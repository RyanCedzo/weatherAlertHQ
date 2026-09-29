"""Sunset time + azimuth via a local solar-geometry library (astral).

Stage 1 explicitly avoids any third-party HTTP "sunrise/sunset API" — this
is pure local computation from lat/lon/date/timezone (D4 in PROJECT_PLAN.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, timezone as dt_timezone
from typing import Optional
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import azimuth, sun


@dataclass(frozen=True)
class SunsetInfo:
    local_date: date_type
    sunset_utc: datetime
    sunset_local: datetime
    azimuth_deg: float


def compute_sunset(
    latitude: float,
    longitude: float,
    timezone_name: str,
    for_date: Optional[date_type] = None,
) -> SunsetInfo:
    """Compute sunset time (UTC + local) and solar azimuth at sunset.

    for_date is interpreted as a local calendar date in timezone_name. If
    omitted, "today" in that timezone is used.
    """
    tz = ZoneInfo(timezone_name)
    if for_date is None:
        for_date = datetime.now(tz).date()

    observer = Observer(latitude=latitude, longitude=longitude)
    events_local = sun(observer, date=for_date, tzinfo=tz)
    sunset_local = events_local["sunset"]
    sunset_utc = sunset_local.astimezone(dt_timezone.utc)
    sunset_azimuth = azimuth(observer, sunset_local)

    return SunsetInfo(
        local_date=for_date,
        sunset_utc=sunset_utc,
        sunset_local=sunset_local,
        azimuth_deg=sunset_azimuth,
    )
