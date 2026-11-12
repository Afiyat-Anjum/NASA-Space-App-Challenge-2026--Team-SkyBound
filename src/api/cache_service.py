# Copyright 2026 Space Apps Challenge Team
# Licensed under the Apache License, Version 2.0
"""
LOCAL CACHE SERVICE: Reads strictly from demo_fixtures/ (or local cache).
Never calls NASA FIRMS during runtime or demos.
"""

import json
import os
import numpy as np
import pandas as pd

FIXTURES_DIR = (
    "demo_fixtures"
    if os.path.exists("demo_fixtures/daily_series.parquet")
    else "/content/drive/MyDrive/firms_hackathon/processed"
)


class LocalFireCacheService:
    def __init__(self, data_dir: str = FIXTURES_DIR):
        self.data_dir = data_dir
        self.daily = pd.read_parquet(f"{data_dir}/daily_series.parquet")
        self.baseline = pd.read_parquet(f"{data_dir}/baseline_doy.parquet")
        self.overlap = pd.read_parquet(f"{data_dir}/overlap_daily.parquet")
        with open(f"{data_dir}/metrics.json", encoding="utf-8") as f:
            self.metrics = json.load(f)
        self.daily["date"] = pd.to_datetime(self.daily["date"])
        self.overlap["date"] = pd.to_datetime(self.overlap["date"])

    def get_metrics(self) -> dict:
        return self.metrics

    def get_daily_series(self, country: str) -> pd.DataFrame:
        return self.daily[self.daily["country"] == country].sort_values("date").copy()

    def get_overlap_series(self, country: str) -> pd.DataFrame:
        return self.overlap[self.overlap["country"] == country].copy()

    def get_map_cells(self, country: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.DataFrame:
        filters = [("date", ">=", start_ts), ("date", "<=", end_ts)]
        if country != "All South Asia":
            filters.append(("country", "==", country))
        return pd.read_parquet(f"{self.data_dir}/cell_daily.parquet", filters=filters)

    def check_seasonal_anomaly(
        self, country: str, target_date: str, mode: str = "harmonised", window_days: int = 7
    ) -> dict:
        sub = self.get_daily_series(country)
        if sub.empty:
            return {"status": "UNKNOWN_COUNTRY", "country": country}

        val_col = "harmonised_count" if mode == "harmonised" else "raw_count"
        target_ts = pd.Timestamp(target_date)
        target_doy = min(target_ts.dayofyear, 365)

        row_now = sub[sub["date"] == target_ts]
        current_val = int(row_now[val_col].iloc[0]) if not row_now.empty else 0

        doy_diff = np.abs(sub["doy"] - target_doy)
        doy_diff = np.minimum(doy_diff, 365 - doy_diff)
        hist_win = sub[(doy_diff <= window_days) & (sub["year"] < target_ts.year)]

        if hist_win.empty:
            return {"status": "INSUFFICIENT_HISTORY", "current_value": current_val}

        pct_rank = float((hist_win[val_col] <= current_val).mean() * 100.0)
        med_val = float(hist_win[val_col].median())
        p90_val = float(np.percentile(hist_win[val_col], 90))

        if pct_rank >= 90:
            verdict = "UNUSUAL / EXTREME BURNING ACTIVITY"
        elif pct_rank >= 75:
            verdict = "ELEVATED / ABOVE SEASONAL NORMAL"
        else:
            verdict = "WITHIN NORMAL SEASONAL RANGE"

        return {
            "status": "OK",
            "country": country,
            "date": str(target_ts.date()),
            "doy": int(target_doy),
            "mode": mode,
            "current_value": current_val,
            "percentile": round(pct_rank, 1),
            "baseline_median": round(med_val, 1),
            "baseline_p90": round(p90_val, 1),
            "baseline_window_days": int(len(hist_win)),
            "baseline_years": f"{int(hist_win['year'].min())}–{int(hist_win['year'].max())}",
            "verdict": verdict,
        }
