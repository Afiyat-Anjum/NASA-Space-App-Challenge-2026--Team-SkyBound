# Copyright 2026 Space Apps Challenge Team
# Licensed under the Apache License, Version 2.0
"""
AGENT ORCHESTRATOR: Coordinates tool calls against LocalFireCacheService
to synthesize emergency-manager situational briefings without direct data access.
"""

from src.agents.tools import TOOL_SCHEMAS, FireAgentToolkit
from src.api.cache_service import LocalFireCacheService


class FireContinuityAgent:
    def __init__(self, cache_service: LocalFireCacheService):
        self.toolkit = FireAgentToolkit(cache_service)
        self.schemas = TOOL_SCHEMAS

    def generate_situational_briefing(
        self, country: str = "All South Asia", target_date: str = "2026-11-12", mode: str = "harmonised"
    ) -> dict:
        anomaly = self.toolkit.check_seasonal_anomaly(country, target_date, mode=mode)
        validation = self.toolkit.compare_sensor_harmonisation(country)
        return {
            "tool_calls_executed": ["check_seasonal_anomaly", "compare_sensor_harmonisation"],
            "anomaly_assessment": anomaly,
            "sensor_validation": validation,
            "continuity_note": (
                "Suomi-NPP VIIRS science delivery ceased on 2 November 2026 ahead of decommissioning; "
                "5.5 km cell harmonisation maintains seamless continuity with NOAA-20 and NOAA-21 VIIRS."
            ),
        }
