# AGENTS.md — Portable Agent Instructions

## Role & Boundaries
- You are assisting with the **South Asia Multi-Decade Active Fire Continuity & Burn Calendar** (2000–2026).
- Never introduce runtime network dependencies on `firms.modaps.eosdis.nasa.gov` inside `src/api/`, `src/agents/`, `web/`, or `app.py`.
- All numeric statistics returned to users must come deterministically from `src/api/cache_service.py` via `src/agents/tools.py`.

## Available Tools (`src/agents/tools.py`)
1. `check_seasonal_anomaly(country, target_date, mode, window_days)` — Evaluates whether fire activity on a date is unusual relative to the circular ±7-day multi-decade baseline.
2. `compare_sensor_harmonisation(country)` — Returns raw vs. harmonised Pearson correlation (`r`) across MODIS and VIIRS overlap days.
3. `get_regional_fire_summary(country, year)` — Summarises annual harmonised cell-days and peak burning Day-of-Year.
