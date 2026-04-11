import sys
import types
import unittest
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import AsyncMock


def _install_homeassistant_dt_stub() -> None:
    homeassistant_module = types.ModuleType("homeassistant")
    util_module = types.ModuleType("homeassistant.util")
    dt_module = types.ModuleType("homeassistant.util.dt")

    dt_module.utcnow = lambda: datetime.now(timezone.utc)

    sys.modules.setdefault("homeassistant", homeassistant_module)
    sys.modules.setdefault("homeassistant.util", util_module)
    sys.modules["homeassistant.util.dt"] = dt_module


_install_homeassistant_dt_stub()


def _install_aiohttp_stub() -> None:
    aiohttp_module = types.ModuleType("aiohttp")

    class ClientSession:
        pass

    class ClientError(Exception):
        pass

    class ClientResponseError(ClientError):
        def __init__(self, status: int | None = None, message: str = "") -> None:
            super().__init__(message)
            self.status = status
            self.message = message

    aiohttp_module.ClientSession = ClientSession
    aiohttp_module.ClientError = ClientError
    aiohttp_module.ClientResponseError = ClientResponseError
    sys.modules["aiohttp"] = aiohttp_module


_install_aiohttp_stub()

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "pstryk_aio"
    / "api.py"
)
PACKAGE_ROOT = MODULE_PATH.parent
custom_components_pkg = types.ModuleType("custom_components")
custom_components_pkg.__path__ = [str(PACKAGE_ROOT.parent)]
sys.modules.setdefault("custom_components", custom_components_pkg)

pstryk_pkg = types.ModuleType("custom_components.pstryk_aio")
pstryk_pkg.__path__ = [str(PACKAGE_ROOT)]
sys.modules["custom_components.pstryk_aio"] = pstryk_pkg

SPEC = spec_from_file_location(
    "custom_components.pstryk_aio.api",
    MODULE_PATH,
    submodule_search_locations=[str(PACKAGE_ROOT)],
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load spec for {MODULE_PATH}")
api_module = module_from_spec(SPEC)
sys.modules["custom_components.pstryk_aio.api"] = api_module
SPEC.loader.exec_module(api_module)
PstrykApiClientApiKey = api_module.PstrykApiClientApiKey


class ProsumerPricingUnifiedMetricsTests(unittest.IsolatedAsyncioTestCase):
    async def test_prosumer_pricing_uses_unified_metrics_bundle(self) -> None:
        client = PstrykApiClientApiKey.__new__(PstrykApiClientApiKey)
        response_data = {
            "frames": [
                {
                    "start": "2026-04-11T10:00:00Z",
                    "end": "2026-04-11T11:00:00Z",
                    "metrics": {
                        "pricing": {
                            "price_prosumer_net": 0.31,
                            "price_prosumer_gross": 0.38,
                        }
                    },
                }
            ],
            "summary": {
                "metrics": {
                    "pricing": {
                        "price_prosumer_net_avg": 0.31,
                        "price_prosumer_gross_avg": 0.38,
                    }
                }
            },
        }
        client._request_unified_metrics = AsyncMock(return_value=response_data)
        client._request = AsyncMock(side_effect=AssertionError("legacy prosumer endpoint should not be used"))

        start = datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 12, 0, 0, tzinfo=timezone.utc)

        normalized = await client.get_integrations_prosumer_pricing_data(
            resolution="hour",
            window_start=start,
            window_end=end,
        )

        client._request_unified_metrics.assert_awaited_once_with(
            metrics="meter_values,cost,pricing",
            resolution="hour",
            window_start=start,
            window_end=end,
        )
        self.assertEqual(normalized["frames"][0]["price_gross"], 0.38)
        self.assertEqual(normalized["price_gross_avg"], 0.38)


if __name__ == "__main__":
    unittest.main()
