"""heuristic_v1: a transparent, non-ML sunset-condition score.

Pure function: Stage 1 sunset-window feature dict -> {score, score_version,
grade, drivers}. Same inputs always produce the same outputs (no live API
calls, no randomness). See docs/heuristic_v1.md for the human-readable
write-up of this formula; this module is the single source of truth for
the actual numbers.

Formula shape
-------------
Four subscores, each computed independently on a 0-100 scale, then combined
with WEIGHTS (summing to 1.0) into the final 0-100 integer score:

    cloud_canvas    (WEIGHTS["cloud_canvas"])    — mid/high cloud in a
        partial-cover "sweet band"; empty sky and total overcast both score
        low; extra penalty when low cloud is heavy (blocks the canvas).
    horizon_access  (WEIGHTS["horizon_access"])  — crude proxy only: mean
        low cloud in the hour(s) right before sunset (D9 in PROJECT_PLAN.md
        — the API has no directional horizon data, so this is not real
        horizon geometry).
    aerosol_clarity (WEIGHTS["aerosol_clarity"]) — AOD is non-monotonic: a
        modest band is treated as neutral/good, very high AOD is a
        penalty. High humidity amplifies the penalty once AOD is already
        past the "good" band (humid haze reads worse than dry haze).
    hygiene         (WEIGHTS["hygiene"])         — visibility bonus, window
        precipitation penalty, extreme PM2.5 penalty.

All weights/thresholds live in the *_PARAMS dicts and WEIGHTS below — change
a number here, rerun, and the score/drivers should move in the direction you
expect. Nothing else in this module encodes "magic" numbers.
"""

from __future__ import annotations

from typing import Any, Dict, List

SCORE_VERSION = "heuristic_v1"

# Final score = sum(WEIGHTS[name] * subscore[name]); must sum to 1.0.
WEIGHTS: Dict[str, float] = {
    "cloud_canvas": 0.40,
    "horizon_access": 0.20,
    "aerosol_clarity": 0.25,
    "hygiene": 0.15,
}

# Cloud canvas: reward mid/high cloud in a partial-cover band, penalize
# heavy low cloud stepping on the canvas.
CLOUD_CANVAS_PARAMS: Dict[str, float] = {
    "band_low": 30.0,  # % mid/high cloud where "canvas" starts being useful
    "band_high": 70.0,  # % mid/high cloud above which sky is too socked-in
    "low_cloud_penalty_threshold": 50.0,  # low-cloud % above which canvas gets blocked
    "low_cloud_penalty_max": 30.0,  # max points subtracted at 100% low cloud
}

# Horizon access: crude proxy from pre-sunset low cloud only (D9, locked).
HORIZON_ACCESS_PARAMS: Dict[str, float] = {
    "low_cloud_full_penalty": 100.0,  # low-cloud % at which access hits 0
}

# Aerosol / clarity: AOD sweet band is neutral-to-good; above it is haze.
AEROSOL_PARAMS: Dict[str, float] = {
    "band_low": 0.05,  # AOD below this: clean but not specifically rewarded
    "band_high": 0.20,  # AOD above this: haze starts penalizing clarity
    "ceiling": 0.60,  # AOD at/above this: clarity floors to 0
    "haze_humidity_threshold": 70.0,  # RH% above which haze reads worse
    "haze_humidity_span": 30.0,  # RH% span used to normalize the amplifier
    "haze_aod_span": 0.40,  # AOD span (above band_high) used to normalize
    "haze_penalty_max": 20.0,  # max extra points subtracted for humid haze
}

# Hygiene: visibility bonus, precipitation penalty, extreme PM2.5 penalty.
HYGIENE_PARAMS: Dict[str, float] = {
    "visibility_poor_m": 5_000.0,  # visibility at/below this: 0 bonus
    "visibility_good_m": 20_000.0,  # visibility at/above this: full bonus
    "precip_penalty_per_mm": 15.0,  # points subtracted per mm of window precip
    "precip_penalty_max": 60.0,
    "pm25_clean_ugm3": 12.0,  # PM2.5 at/below this: no penalty
    "pm25_hazardous_ugm3": 55.0,  # PM2.5 at/above this: penalty maxes out
    "pm25_penalty_max": 40.0,
}

# grade bands, inclusive of their lower bound
GRADE_BANDS = [
    (76, 100, "excellent"),
    (56, 75, "good"),
    (31, 55, "fair"),
    (0, 30, "poor"),
]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _band_score(value: float, low: float, high: float, min_val: float, max_val: float) -> float:
    """Piecewise-linear "sweet band" score: 100 inside [low, high], falling
    linearly to 0 at min_val (below low) or max_val (above high).
    """
    if low <= value <= high:
        return 100.0
    if value < low:
        span = low - min_val
        return _clamp(100.0 * (value - min_val) / span) if span else 0.0
    span = max_val - high
    return _clamp(100.0 * (max_val - value) / span) if span else 0.0


def _score_cloud_canvas(features: Dict[str, Any]) -> float:
    p = CLOUD_CANVAS_PARAMS
    cloud_mid = features.get("cloud_cover_mid_mean") or 0.0
    cloud_high = features.get("cloud_cover_high_mean") or 0.0
    cloud_low = features.get("cloud_cover_low_mean") or 0.0

    combined_mid_high = (cloud_mid + cloud_high) / 2.0
    base = _band_score(combined_mid_high, p["band_low"], p["band_high"], min_val=0.0, max_val=100.0)

    low_excess = max(0.0, cloud_low - p["low_cloud_penalty_threshold"])
    low_span = 100.0 - p["low_cloud_penalty_threshold"]
    low_cloud_penalty = p["low_cloud_penalty_max"] * (low_excess / low_span) if low_span else 0.0

    return _clamp(base - low_cloud_penalty)


def _score_horizon_access(features: Dict[str, Any]) -> float:
    p = HORIZON_ACCESS_PARAMS
    presunset_low_cloud = features.get("cloud_cover_low_presunset_mean")
    if presunset_low_cloud is None:
        # Fallback if the presunset window happened to have no rows: use
        # the whole-window low-cloud mean rather than crash/assume perfect.
        presunset_low_cloud = features.get("cloud_cover_low_mean") or 0.0

    penalty_full = p["low_cloud_full_penalty"]
    return _clamp(100.0 * (1.0 - presunset_low_cloud / penalty_full)) if penalty_full else 100.0


def _score_aerosol_clarity(features: Dict[str, Any]) -> float:
    p = AEROSOL_PARAMS
    aod = features.get("aerosol_optical_depth_mean") or 0.0
    humidity = features.get("relative_humidity_2m_mean") or 0.0

    base = _band_score(aod, p["band_low"], p["band_high"], min_val=0.0, max_val=p["ceiling"])

    haze_penalty = 0.0
    if aod > p["band_high"] and humidity > p["haze_humidity_threshold"]:
        humidity_fraction = min(1.0, (humidity - p["haze_humidity_threshold"]) / p["haze_humidity_span"])
        aod_fraction = min(1.0, (aod - p["band_high"]) / p["haze_aod_span"])
        haze_penalty = p["haze_penalty_max"] * humidity_fraction * aod_fraction

    return _clamp(base - haze_penalty)


def _score_hygiene(features: Dict[str, Any]) -> float:
    p = HYGIENE_PARAMS
    visibility = features.get("visibility_mean") or 0.0
    precip_sum = features.get("precipitation_sum") or 0.0
    pm25 = features.get("pm2_5_mean") or 0.0

    vis_span = p["visibility_good_m"] - p["visibility_poor_m"]
    visibility_score = (
        _clamp(100.0 * (visibility - p["visibility_poor_m"]) / vis_span) if vis_span else 100.0
    )

    precip_penalty = _clamp(precip_sum * p["precip_penalty_per_mm"], 0.0, p["precip_penalty_max"])

    pm25_excess = max(0.0, pm25 - p["pm25_clean_ugm3"])
    pm25_span = p["pm25_hazardous_ugm3"] - p["pm25_clean_ugm3"]
    pm25_penalty = (
        _clamp(p["pm25_penalty_max"] * pm25_excess / pm25_span, 0.0, p["pm25_penalty_max"])
        if pm25_span
        else 0.0
    )

    return _clamp(visibility_score - precip_penalty - pm25_penalty)


def _grade_for(score: int) -> str:
    for low, high, label in GRADE_BANDS:
        if low <= score <= high:
            return label
    return "poor"  # unreachable given GRADE_BANDS covers 0-100


def _build_drivers(features: Dict[str, Any], subscores: Dict[str, float]) -> List[str]:
    cloud_mid = features.get("cloud_cover_mid_mean") or 0.0
    cloud_high = features.get("cloud_cover_high_mean") or 0.0
    cloud_low = features.get("cloud_cover_low_mean") or 0.0
    combined_mid_high = (cloud_mid + cloud_high) / 2.0

    presunset_low_cloud = features.get("cloud_cover_low_presunset_mean")
    if presunset_low_cloud is None:
        presunset_low_cloud = cloud_low

    aod = features.get("aerosol_optical_depth_mean") or 0.0
    humidity = features.get("relative_humidity_2m_mean") or 0.0
    visibility = features.get("visibility_mean") or 0.0
    precip_sum = features.get("precipitation_sum") or 0.0
    pm25 = features.get("pm2_5_mean") or 0.0

    return [
        (
            f"Cloud canvas: mid/high cloud avg {combined_mid_high:.0f}% "
            f"(sweet band {CLOUD_CANVAS_PARAMS['band_low']:.0f}-{CLOUD_CANVAS_PARAMS['band_high']:.0f}%), "
            f"low cloud avg {cloud_low:.0f}% -> {subscores['cloud_canvas']:.0f}/100"
        ),
        (
            f"Horizon access: low cloud {presunset_low_cloud:.0f}% in the hour(s) "
            f"before sunset (crude proxy) -> {subscores['horizon_access']:.0f}/100"
        ),
        (
            f"Aerosol/clarity: AOD {aod:.2f} with humidity {humidity:.0f}% "
            f"-> {subscores['aerosol_clarity']:.0f}/100"
        ),
        (
            f"Hygiene: visibility {visibility:.0f} m, precip {precip_sum:.1f} mm, "
            f"PM2.5 {pm25:.1f} ug/m3 -> {subscores['hygiene']:.0f}/100"
        ),
    ]


def heuristic_v1(features: Dict[str, Any]) -> Dict[str, Any]:
    """Score a Stage 1 sunset-window feature dict.

    Parameters
    ----------
    features: the dict produced by src.features.aggregate_window(), i.e.
        cloud_cover_mid_mean, cloud_cover_high_mean, cloud_cover_low_mean,
        cloud_cover_low_presunset_mean (optional), relative_humidity_2m_mean,
        visibility_mean, aerosol_optical_depth_mean, pm2_5_mean,
        precipitation_sum.

    Returns
    -------
    dict with score (int 0-100), score_version ("heuristic_v1"),
    grade (poor/fair/good/excellent), and drivers (list[str]).
    """
    subscores = {
        "cloud_canvas": _score_cloud_canvas(features),
        "horizon_access": _score_horizon_access(features),
        "aerosol_clarity": _score_aerosol_clarity(features),
        "hygiene": _score_hygiene(features),
    }

    weighted_total = sum(WEIGHTS[name] * subscores[name] for name in WEIGHTS)
    score = int(round(_clamp(weighted_total)))
    grade = _grade_for(score)
    drivers = _build_drivers(features, subscores)

    return {
        "score": score,
        "score_version": SCORE_VERSION,
        "grade": grade,
        "drivers": drivers,
        "subscores": {name: round(value, 1) for name, value in subscores.items()},
    }
