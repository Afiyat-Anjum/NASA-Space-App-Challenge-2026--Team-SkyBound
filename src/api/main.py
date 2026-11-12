# Copyright 2026 Space Apps Challenge Team
# Licensed under the Apache License, Version 2.0
"""
FASTAPI APPLICATION: Serves cached fire continuity series, spatial grid cells,
anomaly diagnostics, agent tool invocations, and static web/ frontend files.
"""

import os
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from src.agents.orchestrator import FireContinuityAgent
from src.api.cache_service import LocalFireCacheService

app = FastAPI(
    title="FIRMS South Asia Harmonised Burn Calendar API",
    version="1.0.0",
    description="Local-cache API serving multi-decade harmonised MODIS & VIIRS active fire records.",
)

cache_service = LocalFireCacheService()
agent = FireContinuityAgent(cache_service)


@app.get("/health")
def health():
    return {"status": "ok", "live_nasa_calls": False, "cache_source": cache_service.data_dir}


@app.get("/api/metrics")
def get_metrics():
    return cache_service.get_metrics()


@app.get("/api/daily/{country}")
def get_daily(country: str):
    df = cache_service.get_daily_series(country)
    out = df[["date", "year", "doy", "harmonised_count", "raw_count", "total_frp"]].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out.to_dict(orient="records")


@app.get("/api/anomaly")
def get_anomaly(
    country: str = Query("All South Asia"),
    target_date: str = Query("2026-11-12"),
    mode: str = Query("harmonised"),
    window_days: int = Query(7),
):
    return cache_service.check_seasonal_anomaly(country, target_date, mode, window_days)


@app.get("/api/cells")
def get_cells(
    country: str = Query("All South Asia"),
    end_date: str = Query("2026-11-12"),
    window_days: int = Query(7),
):
    end_ts = pd.Timestamp(end_date)
    start_ts = end_ts - pd.Timedelta(days=window_days - 1)
    df = cache_service.get_map_cells(country, start_ts, end_ts)
    if df.empty:
        return []
    agg = (
        df.groupby(["cell_id", "grid_lat", "grid_lon"], as_index=False)
        .agg(harmonised_hits=("harmonised_hits", "sum"), raw_hits=("raw_hits", "sum"), frp=("frp", "sum"))
        .nlargest(5000, "harmonised_hits")
    )
    return agg.to_dict(orient="records")


@app.get("/api/agent/briefing")
def agent_briefing(
    country: str = Query("All South Asia"),
    target_date: str = Query("2026-11-12"),
    mode: str = Query("harmonised"),
):
    return agent.generate_situational_briefing(country=country, target_date=target_date, mode=mode)


if os.path.isdir("web"):
    app.mount("/", StaticFiles(directory="web", html=True), name="web")
