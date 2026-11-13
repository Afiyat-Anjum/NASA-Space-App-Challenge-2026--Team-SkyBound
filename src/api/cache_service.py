import json
import os
import numpy as np
import pandas as pd

FIXTURES_DIR = (
    "demo_fixtures"
    if os.path.exists("demo_fixtures/daily_series.parquet")
    else "/content/drive/MyDrive/firms_hackathon/processed"
)
CELL_SIZE_KM = 5.5
DEG_STEP = CELL_SIZE_KM / 111.32


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

    def predict_spread_risk(self, country: str, end_ts: pd.Timestamp) -> pd.DataFrame:
        """
        Empirical Next-7-Day Fire Spread Risk: combines active fire front proximity,
        FRP intensity, 48h progression heading, and multi-year seasonal burn susceptibility
        on adjacent 5.5 km grid cells using only cached Parquet history.
        """
        start_front = end_ts - pd.Timedelta(days=1)
        active = self.get_map_cells(country, start_front, end_ts)
        if active.empty:
            return pd.DataFrame()

        active = active.copy()
        active["lat_idx"] = np.round(active["grid_lat"].astype(float) / DEG_STEP).astype(int)
        active["lon_idx"] = np.round(active["grid_lon"].astype(float) / DEG_STEP).astype(int)

        fronts = (
            active.groupby(["lat_idx", "lon_idx", "grid_lat", "grid_lon"], as_index=False)
            .agg(frp=("frp", "sum"))
            .nlargest(250, "frp")
        )

        # Estimate recent 48h progression vector (day t-1 -> day t)
        d_prev = active[active["date"] < end_ts]
        d_curr = active[active["date"] == end_ts]
        vec_lat, vec_lon = 0.0, 0.0
        if not d_prev.empty and not d_curr.empty:
            vec_lat = float(d_curr["grid_lat"].mean() - d_prev["grid_lat"].mean())
            vec_lon = float(d_curr["grid_lon"].mean() - d_prev["grid_lon"].mean())
        norm = float(np.hypot(vec_lat, vec_lon))
        if norm > 1e-6:
            vec_lat, vec_lon = vec_lat / norm, vec_lon / norm

        active_idx_set = set(zip(fronts["lat_idx"], fronts["lon_idx"]))
        max_frp = max(float(fronts["frp"].max()), 1.0)
        candidates = {}

        for _, row in fronts.iterrows():
            li, lj = int(row["lat_idx"]), int(row["lon_idx"])
            frp_norm = float(row["frp"]) / max_frp
            for di in range(-2, 3):
                for dj in range(-2, 3):
                    if di == 0 and dj == 0:
                        continue
                    dist_cells = float(np.hypot(di, dj))
                    if dist_cells > 2.25:
                        continue
                    ni, nj = li + di, lj + dj
                    if (ni, nj) in active_idx_set:
                        continue
                    align = ((di * vec_lat + dj * vec_lon) / dist_cells) if norm > 1e-6 else 0.0
                    dir_boost = 1.0 + 0.25 * align
                    prox_score = (1.0 / dist_cells) * (0.65 + 0.35 * frp_norm) * dir_boost
                    key = (ni, nj)
                    if key not in candidates or prox_score > candidates[key]["prox_score"]:
                        candidates[key] = {
                            "lat_idx": ni,
                            "lon_idx": nj,
                            "grid_lat": round(ni * DEG_STEP, 4),
                            "grid_lon": round(nj * DEG_STEP, 4),
                            "distance_km": round(dist_cells * CELL_SIZE_KM, 1),
                            "prox_score": prox_score,
                        }

        if not candidates:
            return pd.DataFrame()

        cand_df = pd.DataFrame(list(candidates.values()))

        # Load historical seasonal burn susceptibility (next 14 DOYs in prior years)
        filters = [("country", "==", country)] if country != "All South Asia" else None
        hist = pd.read_parquet(
            f"{self.data_dir}/cell_daily.parquet",
            columns=["grid_lat", "grid_lon", "date"],
            filters=filters,
        )
        hist_dates = pd.to_datetime(hist["date"])
        hist = hist[hist_dates.dt.year < end_ts.year].copy()

        if not hist.empty:
            hist_doy = pd.to_datetime(hist["date"]).dt.dayofyear.clip(upper=365)
            target_doy = min(end_ts.dayofyear, 365)
            fwd_diff = (hist_doy - target_doy) % 365
            hist_win = hist[(fwd_diff >= 0) & (fwd_diff <= 14)].copy()
            n_years = max(int(pd.to_datetime(hist["date"]).dt.year.nunique()), 1)

            hist_win["lat_idx"] = np.round(hist_win["grid_lat"].astype(float) / DEG_STEP).astype(int)
            hist_win["lon_idx"] = np.round(hist_win["grid_lon"].astype(float) / DEG_STEP).astype(int)
            hist_win["year"] = pd.to_datetime(hist_win["date"]).dt.year

            hist_freq = (
                hist_win.groupby(["lat_idx", "lon_idx"])["year"]
                .nunique()
                .reset_index(name="hist_burn_years")
            )
            cand_df = cand_df.merge(hist_freq, on=["lat_idx", "lon_idx"], how="left")
            cand_df["hist_burn_years"] = cand_df["hist_burn_years"].fillna(0).astype(int)
            cand_df["seasonal_susceptibility_pct"] = (
                (cand_df["hist_burn_years"] / n_years).clip(upper=1.0) * 100.0
            ).round(1)
        else:
            cand_df["hist_burn_years"] = 0
            cand_df["seasonal_susceptibility_pct"] = 0.0

        prox_norm = (cand_df["prox_score"] / max(float(cand_df["prox_score"].max()), 1e-6)).clip(upper=1.0)
        sus_norm = cand_df["seasonal_susceptibility_pct"] / 100.0
        cand_df["spread_risk_pct"] = ((0.55 * prox_norm + 0.45 * sus_norm) * 100.0).round(1)
        cand_df["risk_tier"] = np.where(
            cand_df["spread_risk_pct"] >= 65.0,
            "High Spread Risk (Next 7d)",
            np.where(
                cand_df["spread_risk_pct"] >= 40.0,
                "Moderate Spread Risk (Next 7d)",
                "Perimeter Watch Zone",
            ),
        )
        return (
            cand_df.drop(columns=["lat_idx", "lon_idx", "prox_score"])
            .sort_values("spread_risk_pct", ascending=False)
            .head(800)
            .reset_index(drop=True)
        )
