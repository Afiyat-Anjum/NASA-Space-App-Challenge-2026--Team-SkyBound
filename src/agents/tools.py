# Copyright 2026 Space Apps Challenge Team
# Licensed under the Apache License, Version 2.0
"""
AGENT TOOLS & JSON SCHEMAS: Agents sit beside src/api/ and reach cached
fire datasets strictly through these typed tool definitions.
"""

from src.api.cache_service import LocalFireCacheService

TOOL_SCHEMAS = [
    {
        "name": "check_seasonal_anomaly",
        "description": "Evaluate whether burning activity on a given date in South Asia is unusual compared to the ±7-day multi-decade historical baseline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string", "description": "South Asian country or 'All South Asia'"},
                "target_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "mode": {"type": "string", "enum": ["harmonised", "raw"]},
                "window_days": {"type": "integer", "default": 7},
            },
            "required": ["country", "target_date"],
        },
    },
    {
        "name": "compare_sensor_harmonisation",
        "description": "Retrieve raw vs. harmonised MODIS-VIIRS Pearson correlation metrics for a South Asian country.",
        "input_schema": {
            "type": "object",
            "properties": {
                "country": {"type": "string"},
            },
            "required": ["country"],
        },
    },
]


class FireAgentToolkit:
    def __init__(self, cache_service: LocalFireCacheService):
        self.api = cache_service

    def check_seasonal_anomaly(
        self, country: str, target_date: str, mode: str = "harmonised", window_days: int = 7
    ) -> dict:
        return self.api.check_seasonal_anomaly(country, target_date, mode, window_days)

    def compare_sensor_harmonisation(self, country: str) -> dict:
        metrics = self.api.get_metrics()
        c_m = metrics.get("by_country", {}).get(country, metrics)
        return {
            "country": country,
            "r_raw": c_m["r_raw"],
            "r_harmonised": c_m["r_harmonised"],
            "gain": round(c_m["r_harmonised"] - c_m["r_raw"], 4),
            "overlap_days": c_m["overlap_days"],
        }
