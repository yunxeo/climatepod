"""EcoLogits API 클라이언트"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from constants import (
    DEFAULT_REQUEST_LATENCY_SEC,
    ECOLOGITS_API_URL,
    ELECTRICITY_MIX_ZONE,
)


@dataclass
class CarbonImpact:
    energy_kwh_min: float
    energy_kwh_max: float
    gwp_kg_min: float
    gwp_kg_max: float
    water_l_min: float
    water_l_max: float
    warnings: list[str]

    @property
    def energy_kwh_mid(self) -> float:
        return (self.energy_kwh_min + self.energy_kwh_max) / 2

    @property
    def gwp_kg_mid(self) -> float:
        return (self.gwp_kg_min + self.gwp_kg_max) / 2

    @property
    def water_l_mid(self) -> float:
        return (self.water_l_min + self.water_l_max) / 2


class EcoLogitsError(Exception):
    pass


def _interval_value(block: dict[str, Any] | None) -> tuple[float, float]:
    if not block:
        return 0.0, 0.0
    value = block.get("value") or {}
    return float(value.get("min", 0)), float(value.get("max", 0))


async def fetch_carbon_impact(
    *,
    provider: str,
    model_name: str,
    output_token_count: int,
    request_latency: float = DEFAULT_REQUEST_LATENCY_SEC,
    electricity_mix_zone: str = ELECTRICITY_MIX_ZONE,
) -> CarbonImpact:
    payload = {
        "provider": provider,
        "model_name": model_name,
        "output_token_count": max(1, output_token_count),
        "request_latency": request_latency,
        "electricity_mix_zone": electricity_mix_zone,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(ECOLOGITS_API_URL, json=payload)

    if response.status_code >= 400:
        raise EcoLogitsError(f"EcoLogits API error {response.status_code}: {response.text[:200]}")

    data = response.json()
    impacts = data.get("impacts") or {}

    e_min, e_max = _interval_value(impacts.get("energy"))
    g_min, g_max = _interval_value(impacts.get("gwp"))
    w_min, w_max = _interval_value(impacts.get("wcf"))

    warnings = []
    for w in impacts.get("warnings") or []:
        if isinstance(w, dict) and w.get("message"):
            warnings.append(str(w["message"]))

    return CarbonImpact(
        energy_kwh_min=e_min,
        energy_kwh_max=e_max,
        gwp_kg_min=g_min,
        gwp_kg_max=g_max,
        water_l_min=w_min,
        water_l_max=w_max,
        warnings=warnings,
    )
