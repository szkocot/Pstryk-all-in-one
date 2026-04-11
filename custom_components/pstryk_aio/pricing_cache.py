"""Helpers for reusing cached pricing data across the midnight rollover."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

try:
    from homeassistant.util import dt as dt_util
except ImportError:  # pragma: no cover - Home Assistant not available in isolated unit tests
    dt_util = None


def _parse_frame_start(start_value: Any) -> Optional[datetime]:
    """Parse an ISO datetime string from a pricing frame."""
    if not isinstance(start_value, str) or not start_value:
        return None

    normalized = start_value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _as_local_date(dt_value: datetime) -> date:
    """Convert aware datetimes to the Home Assistant local date when possible."""
    if dt_value.tzinfo is None:
        return dt_value.date()

    if dt_util is not None:
        return dt_util.as_local(dt_value).date()

    return dt_value.astimezone().date()


def has_frames_for_date(response_data: Optional[dict[str, Any]], expected_date: date) -> bool:
    """Return True when the pricing response contains frames for the expected local date."""
    if not isinstance(response_data, dict):
        return False

    frames = response_data.get("frames")
    if not isinstance(frames, list) or not frames:
        return False

    first_frame = frames[0]
    if not isinstance(first_frame, dict):
        return False

    start_dt = _parse_frame_start(first_frame.get("start"))
    if start_dt is None:
        return False

    return _as_local_date(start_dt) == expected_date


def select_today_pricing_response(
    api_response: Optional[dict[str, Any]],
    cached_today: Optional[dict[str, Any]],
    promotable_tomorrow: Optional[dict[str, Any]],
    expected_date: date,
) -> tuple[dict[str, Any], bool]:
    """Pick the best response for today's pricing, preferring fresh data, then promoted tomorrow cache."""
    if has_frames_for_date(api_response, expected_date):
        return api_response or {}, True

    if has_frames_for_date(promotable_tomorrow, expected_date):
        return promotable_tomorrow or {}, True

    if isinstance(cached_today, dict):
        return cached_today, False

    return {}, False
