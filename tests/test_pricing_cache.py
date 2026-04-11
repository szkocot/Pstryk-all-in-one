import unittest
from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types


def _install_homeassistant_dt_stub() -> None:
    homeassistant_module = types.ModuleType("homeassistant")
    util_module = types.ModuleType("homeassistant.util")
    dt_module = types.ModuleType("homeassistant.util.dt")

    def as_local(dt_value):
        return dt_value.astimezone()

    dt_module.as_local = as_local

    sys.modules.setdefault("homeassistant", homeassistant_module)
    sys.modules.setdefault("homeassistant.util", util_module)
    sys.modules["homeassistant.util.dt"] = dt_module


_install_homeassistant_dt_stub()


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "pstryk_aio"
    / "pricing_cache.py"
)
SPEC = spec_from_file_location("pricing_cache", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load spec for {MODULE_PATH}")
pricing_cache = module_from_spec(SPEC)
SPEC.loader.exec_module(pricing_cache)
select_today_pricing_response = pricing_cache.select_today_pricing_response


class SelectTodayPricingResponseTests(unittest.TestCase):
    def test_accepts_unified_metrics_utc_frame_for_local_expected_date(self) -> None:
        api_response = {
            "frames": [
                {
                    "start": "2026-04-10T22:00:00Z",
                    "end": "2026-04-10T23:00:00Z",
                    "price_gross": 0.6,
                }
            ]
        }

        response, used_fresh_or_promoted = select_today_pricing_response(
            api_response=api_response,
            cached_today={},
            promotable_tomorrow=None,
            expected_date=date(2026, 4, 11),
        )

        self.assertEqual(response, api_response)
        self.assertTrue(used_fresh_or_promoted)

    def test_uses_previous_tomorrow_cache_when_fresh_today_fetch_fails(self) -> None:
        promoted_tomorrow = {
            "frames": [
                {
                    "start": "2026-04-08T00:00:00+02:00",
                    "end": "2026-04-08T01:00:00+02:00",
                    "price_gross": 0.6,
                }
            ]
        }

        response, used_fresh_or_promoted = select_today_pricing_response(
            api_response=None,
            cached_today={},
            promotable_tomorrow=promoted_tomorrow,
            expected_date=date(2026, 4, 8),
        )

        self.assertEqual(response, promoted_tomorrow)
        self.assertTrue(used_fresh_or_promoted)

    def test_keeps_cached_today_when_promoted_cache_does_not_match_current_date(self) -> None:
        cached_today = {
            "frames": [
                {
                    "start": "2026-04-07T00:00:00+02:00",
                    "end": "2026-04-07T01:00:00+02:00",
                    "price_gross": 0.59,
                }
            ]
        }
        stale_tomorrow = {
            "frames": [
                {
                    "start": "2026-04-09T00:00:00+02:00",
                    "end": "2026-04-09T01:00:00+02:00",
                    "price_gross": 0.61,
                }
            ]
        }

        response, used_fresh_or_promoted = select_today_pricing_response(
            api_response=None,
            cached_today=cached_today,
            promotable_tomorrow=stale_tomorrow,
            expected_date=date(2026, 4, 8),
        )

        self.assertEqual(response, cached_today)
        self.assertFalse(used_fresh_or_promoted)


if __name__ == "__main__":
    unittest.main()
