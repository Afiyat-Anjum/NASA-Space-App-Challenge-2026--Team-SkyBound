import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from src.agents.orchestrator import FireContinuityAgent
from src.api.cache_service import LocalFireCacheService

st.set_page_config(
    page_title="Team SkyBound | FIRMS South Asia Burn Calendar",
    layout="wide",
    initial_sidebar_state="expanded",
)

COUNTRY_CENTERS = {
    "All South Asia": (22.5, 79.0, 3.6),
    "India": (22.0, 79.0, 4.2),
    "Pakistan": (30.0, 69.5, 4.6),
    "Nepal": (28.3, 84.1, 6.0),
    "Bangladesh": (23.7, 90.3, 6.2),
    "Sri_Lanka": (7.8, 80.7, 6.8),
    "Afghanistan": (33.9, 66.0, 5.0),
    "Bhutan": (27.5, 90.4, 7.5),
    "Maldives": (3.2, 73.2, 6.0),
}

PALETTES = {
    "Fire (Yellow → Orange → Red)": "YlOrRd",
    "Inferno (Dark → Red → Yellow)": "Inferno",
    "Orange-Red (High Contrast)": "OrRd",
    "Cividis (Colorblind-Safe)": "Cividis",
    "Viridis (Colorblind-Safe)": "Viridis",
}

AUDIENCE_GUIDES = {
    "All Operational Roles": (
        "**Built for Early Warning Responders, Firefighters, Land Managers & Scientists:** "
        "Track active fire fronts, benchmark daily counts against 26-year historical averages, "
        "and inspect perimeter spread risk across South Asia."
    ),
    "Early Warning & Emergency Responders": (
        "**Early Warning Focus:** Monitor the **Seasonal Anomaly Verdict** and **% Departure vs. Multi-Year Average** "
        "to trigger regional smoke advisories and resource pre-positioning when burning exceeds the 90th percentile."
    ),
    "Firefighters & Incident Command": (
        "**Tactical Perimeter Focus:** Toggle **Custom Lat / Lon Coordinates** to zoom into an active incident radius, "
        "inspect **FRP-weighted active fronts**, and export **Projected 7-Day Spread Risk Cells** for flank containment."
    ),
    "Land & Forestry Managers": (
        "**Seasonal Regime Focus:** Use the **Year-by-Month Burning Activity Calendar** to pinpoint recurring "
        "agricultural residue burning and pre-monsoon forest fire windows for prescribed burn and patrol scheduling."
    ),
    "Earth & Climate Scientists": (
        "**Sensor Continuity Focus:** Toggle the **Master Series Switch** to verify how 5.5 km spatial cell-collapse "
        "eliminates the 2012 VIIRS resolution step-change (**r = 0.8244 → 0.8503**) across MODIS and VIIRS S-NPP/NOAA-20/NOAA-21."
    ),
}

MONTH_TICKS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@st.cache_resource
def get_services():
    svc = LocalFireCacheService()
    return svc, FireContinuityAgent(svc)


@st.cache_data
def cached_cells(country: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp):
    svc, _ = get_services()
    return svc.get_map_cells(country, start_ts, end_ts)


@st.cache_data
def cached_aoi_cells(lat: float, lon: float, radius_km: float, start_ts: pd.Timestamp, end_ts: pd.Timestamp):
    svc, _ = get_services()
    return svc.get_aoi_cells(lat, lon, radius_km, start_ts, end_ts)


@st.cache_data
def cached_aoi_daily(lat: float, lon: float, radius_km: float):
    svc, _ = get_services()
    return svc.get_aoi_daily_series(lat, lon, radius_km)


@st.cache_data
def cached_spread_risk(country: str, end_ts: pd.Timestamp, aoi: tuple | None = None):
    svc, _ = get_services()
    return svc.predict_spread_risk(country, end_ts, aoi=aoi)


svc, agent = get_services()
metrics = svc.get_metrics()

# --- SIDEBAR: BRANDING, AUDIENCE LENS, AOI / LAT-LON & DATE RANGE ---
st.sidebar.markdown("### Team SkyBound")
st.sidebar.caption("NASA Space Apps Challenge 2026 • South Asia Fire Continuity")

audience_role = st.sidebar.selectbox("Target Audience Operational Lens", list(AUDIENCE_GUIDES.keys()), index=0)

st.sidebar.header("1. Area of Interest (Region or Lat/Lon)")
aoi_mode = st.sidebar.radio(
    "Location Selection Mode",
    ["Country / Region (2000–2026)", "Custom Lat / Lon Coordinates"],
    index=0,
)

if aoi_mode == "Country / Region (2000–2026)":
    selected_country = st.sidebar.selectbox(
        "Study Area (South Asia)", options=metrics["countries"], index=0, format_func=lambda x: x.replace("_", " ")
    )
    sub_daily = svc.get_daily_series(selected_country)
    area_label = selected_country.replace("_", " ")
    aoi_tuple = None
else:
    selected_country = "All South Asia"
    custom_lat = st.sidebar.number_input("Center Latitude (°N)", min_value=0.0, max_value=40.0, value=29.50, step=0.10, format="%.4f")
    custom_lon = st.sidebar.number_input("Center Longitude (°E)", min_value=60.0, max_value=100.0, value=76.50, step=0.10, format="%.4f")
    custom_rad = st.sidebar.slider("Search Radius (km)", min_value=15, max_value=250, value=75, step=5)
    sub_daily = cached_aoi_daily(float(custom_lat), float(custom_lon), float(custom_rad))
    area_label = f"Custom AOI ({custom_lat:.2f}°N, {custom_lon:.2f}°E, {custom_rad} km radius)"
    aoi_tuple = (float(custom_lat), float(custom_lon), float(custom_rad))

st.sidebar.header("2. Date Range & Visual Style")
min_d = sub_daily["date"].min().date()
max_d = sub_daily["date"].max().date()
default_start = max(min_d, (pd.Timestamp(max_d) - pd.Timedelta(days=6)).date())

start_date = st.sidebar.date_input("Search Start Date", value=default_start, min_value=min_d, max_value=max_d)
end_date = st.sidebar.date_input("Search End Date (Anomaly Target)", value=max_d, min_value=min_d, max_value=max_d)

if start_date > end_date:
    st.sidebar.warning("Start Date is after End Date; adjusting Start Date to match End Date.")
    start_date = end_date

span_days = (end_date - start_date).days + 1
show_spread = st.sidebar.checkbox("Overlay Predicted Next-7-Day Spread Risk", value=True)
palette = PALETTES[st.sidebar.selectbox("Accessible Fire Color Ramp", list(PALETTES.keys()), index=0)]
map_style = "carto-darkmatter" if st.sidebar.radio("Map Theme", ["Dark Basemap", "Light Basemap"]) == "Dark Basemap" else "carto-positron"

# --- HEADER & TEAM SKYBOUND BANNER ---
st.markdown("**TEAM SKYBOUND** • *NASA Space Apps Challenge 2026*")
st.title(f"Active Fire Continuity & Burn Calendar — {area_label}")
st.caption("Harmonised Multi-Decade NASA FIRMS MODIS & VIIRS (S-NPP, NOAA-20, NOAA-21) Decision Support for Responders, Firefighters, Land Managers & Scientists")
st.info(AUDIENCE_GUIDES[audience_role])

mode = st.radio(
    "Master Series Switch (updates every map, calendar, chart, and anomaly metric):",
    ["Harmonised (5.5 km Collapsed Cell-Days)", "Raw Detections (Unadjusted Sensor Counts)"],
    horizontal=True,
)
is_harm = mode.startswith("Harmonised")
val_col = "harmonised_count" if is_harm else "raw_count"
cell_col = "harmonised_hits" if is_harm else "raw_hits"

# --- DATA QUERIES & MULTI-YEAR AVERAGE ANOMALY ---
start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)

if aoi_tuple is not None:
    map_df = cached_aoi_cells(aoi_tuple[0], aoi_tuple[1], aoi_tuple[2], start_ts, end_ts)
    anom = svc.compute_anomaly_from_series(
        sub_daily, area_label, str(end_date), mode="harmonised" if is_harm else "raw", window_days=7
    )
else:
    map_df = cached_cells(selected_country, start_ts, end_ts)
    briefing = agent.generate_situational_briefing(
        country=selected_country, target_date=str(end_date), mode="harmonised" if is_harm else "raw"
    )
    anom = briefing["anomaly_assessment"]

spread_df = cached_spread_risk(selected_country, end_ts, aoi=aoi_tuple) if show_spread else pd.DataFrame()
high_risk_cells = int((spread_df["spread_risk_pct"] >= 65.0).sum()) if not spread_df.empty else 0

c_metrics = metrics["by_country"].get(selected_country, metrics)
range_mask = (sub_daily["date"].dt.date >= start_date) & (sub_daily["date"].dt.date <= end_date)
range_total = int(sub_daily.loc[range_mask, val_col].sum())

# --- KEY INDICES & FIGURES (KPI CARDS) ---
v1, v2, v3, v4, v5 = st.columns(5)
v1.metric("MODIS–VIIRS Agreement (r)", f"{c_metrics['r_harmonised']:.4f}", delta=f"{c_metrics['r_harmonised'] - c_metrics['r_raw']:+.4f} vs raw")
v2.metric(f"Fires Detected ({span_days}d Range)", f"{range_total:,}", help=f"Total {'harmonised cell-days' if is_harm else 'raw hotspots'} from {start_date} to {end_date}")
if anom.get("status") == "OK":
    v3.metric(
        "Target Date vs. Multi-Yr Avg",
        f"{anom['current_value']:,}",
        delta=f"{anom['pct_vs_mean']:+.1f}% vs {anom['baseline_mean']:.1f} avg",
    )
    v4.metric("Historical Percentile", f"{anom['percentile']:.1f}th", help=f"Ranked against {anom['baseline_years']} ±7-day window")
else:
    v3.metric("Target Date Activity", "0")
    v4.metric("Historical Percentile", "N/A")
v5.metric("High-Risk Spread Cells (7d)", f"{high_risk_cells:,}", help="Unburned 5.5 km perimeter cells with >= 65% spread risk")

# --- ANOMALY VERDICT BANNER ---
st.subheader("Is this unusual for this place and this time of year?")
if anom.get("status") == "OK":
    box_fn = st.error if anom["percentile"] >= 90 and anom["current_value"] > 0 else (
        st.warning if anom["percentile"] >= 75 and anom["current_value"] > 0 else st.success
    )
    box_fn(
        f"**{anom['verdict']}** — In **{area_label}** on **{anom['date']}** (DOY {anom['doy']}), "
        f"detected burning was **{anom['current_value']:,}** ({'Harmonised Cell-Days' if is_harm else 'Raw Hotspots'}) — "
        f"**{anom['pct_vs_mean']:+.1f}%** relative to the **multi-year average of {anom['baseline_mean']:.1f}** "
        f"({anom['baseline_years']} ±7-day window; **90th percentile = {anom['baseline_p90']:.0f}**, "
        f"current rank = **{anom['percentile']}th percentile**)."
    )

# --- SPATIAL MAP & YEAR-BY-MONTH BURNING ACTIVITY CALENDAR ---
col_map, col_cal = st.columns([1.05, 1.35])

with col_map:
    st.subheader(f"Active Fire & Spread Risk Map ({start_date} to {end_date})")
    if aoi_tuple is not None:
        clat, clon = aoi_tuple[0], aoi_tuple[1]
        czoom = 8.2 if aoi_tuple[2] <= 50 else (7.0 if aoi_tuple[2] <= 120 else 6.0)
    else:
        clat, clon, czoom = COUNTRY_CENTERS.get(selected_country, (22.5, 79.0, 3.8))

    map_fn = px.scatter_map if hasattr(px, "scatter_map") else px.scatter_mapbox
    style_kw = {"map_style": map_style} if hasattr(px, "scatter_map") else {"mapbox_style": map_style}

    if not map_df.empty:
        agg = map_df.groupby(["cell_id", "grid_lat", "grid_lon"], as_index=False).agg(activity=(cell_col, "sum"), total_frp=("frp", "sum"))
        if len(agg) > 6000:
            agg = agg.nlargest(6000, "activity")

        if show_spread and not spread_df.empty:
            active_layer = agg[["grid_lat", "grid_lon", "activity", "total_frp"]].copy()
            active_layer["layer"] = "1. Active Fire Cell"
            active_layer["size_val"] = active_layer["activity"].clip(lower=1, upper=12)
            active_layer["risk_pct"] = 100.0

            risk_layer = spread_df[spread_df["spread_risk_pct"] >= 40.0][
                ["grid_lat", "grid_lon", "spread_risk_pct", "risk_tier"]
            ].copy()
            risk_layer["layer"] = risk_layer["risk_tier"].apply(
                lambda t: "2. High Spread Risk (Next 7d)" if t.startswith("High") else "3. Moderate Spread Risk (Next 7d)"
            )
            risk_layer["activity"] = 0
            risk_layer["total_frp"] = 0.0
            risk_layer["size_val"] = (risk_layer["spread_risk_pct"] / 12.0).clip(lower=3, upper=9)
            risk_layer["risk_pct"] = risk_layer["spread_risk_pct"]

            combined = pd.concat([risk_layer, active_layer], ignore_index=True)
            if aoi_tuple is not None:
                center_pin = pd.DataFrame([{
                    "grid_lat": aoi_tuple[0], "grid_lon": aoi_tuple[1], "layer": "0. Selected AOI Center",
                    "size_val": 11, "risk_pct": 0.0, "activity": 0, "total_frp": 0.0
                }])
                combined = pd.concat([center_pin, combined], ignore_index=True)

            fig_map = map_fn(
                combined,
                lat="grid_lat",
                lon="grid_lon",
                color="layer",
                size="size_val",
                size_max=13,
                color_discrete_map={
                    "0. Selected AOI Center": "#10b981",
                    "1. Active Fire Cell": "#e31a1c",
                    "2. High Spread Risk (Next 7d)": "#feb24c",
                    "3. Moderate Spread Risk (Next 7d)": "#38bdf8",
                },
                hover_data={"grid_lat": True, "grid_lon": True, "risk_pct": ":.1f", "activity": True, "size_val": False},
                center={"lat": clat, "lon": clon},
                zoom=czoom,
                height=460,
                **style_kw,
            )
        else:
            fig_map = map_fn(
                agg, lat="grid_lat", lon="grid_lon", color="activity", size="activity", size_max=14,
                hover_data={"grid_lat": True, "grid_lon": True, "activity": True, "total_frp": ":.1f"},
                color_continuous_scale=palette, center={"lat": clat, "lon": clon}, zoom=czoom, height=460, **style_kw,
                labels={"activity": "Harmonised Cell-Days" if is_harm else "Raw Hotspots"},
            )

        fig_map.update_layout(margin=dict(l=0, r=0, t=5, b=0), legend=dict(orientation="h", yanchor="bottom", y=0.01, x=0.01))
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info(f"No spatial cell detections recorded in {area_label} between {start_date} and {end_date}.")

with col_cal:
    yr_span_label = f"{int(sub_daily['year'].min())}–{int(sub_daily['year'].max())}"
    st.subheader(f"Year-by-Month Burning Activity Calendar ({yr_span_label})")
    cal_pivot = sub_daily.pivot_table(index="year", columns="doy", values=val_col, aggfunc="sum", fill_value=0)
    fig_cal = px.imshow(
        cal_pivot,
        aspect="auto",
        color_continuous_scale=palette,
        height=460,
        labels={"x": "Month of Year", "y": "Year", "color": "Cell-Days" if is_harm else "Raw Hotspots"},
    )
    fig_cal.update_xaxes(tickmode="array", tickvals=MONTH_TICKS, ticktext=MONTH_NAMES)
    fig_cal.update_layout(margin=dict(l=0, r=0, t=5, b=0))
    st.plotly_chart(fig_cal, use_container_width=True)

# --- DOWNLOADABLE CSV OUTPUTS ---
dl1, dl2, dl3 = st.columns(3)
with dl1:
    export_spots = map_df.head(50000).copy()
    if not export_spots.empty:
        export_spots["date"] = pd.to_datetime(export_spots["date"]).dt.strftime("%Y-%m-%d")
    st.download_button(
        label=f"Download Search Hotspots CSV ({start_date} to {end_date})",
        data=export_spots.to_csv(index=False).encode("utf-8"),
        file_name=f"skybound_firms_hotspots_{start_date}_to_{end_date}.csv",
        mime="text/csv",
        disabled=export_spots.empty,
    )

with dl2:
    st.download_button(
        label=f"Download {yr_span_label} Daily Analytics CSV",
        data=sub_daily.to_csv(index=False).encode("utf-8"),
        file_name=f"skybound_firms_daily_analytics_{yr_span_label}.csv",
        mime="text/csv",
    )

with dl3:
    st.download_button(
        label=f"Download Projected Spread Risk CSV ({end_date})",
        data=spread_df.to_csv(index=False).encode("utf-8"),
        file_name=f"skybound_firms_spread_risk_{end_date}.csv",
        mime="text/csv",
        disabled=spread_df.empty,
    )

# --- HISTORICAL COMPARISON CHARTS (ANOMALIES VS MULTI-YEAR AVERAGES) ---
c_clim, c_ts = st.columns([1.05, 1.35])

with c_clim:
    target_year = end_date.year
    st.subheader(f"Anomaly vs. Multi-Year Average ({target_year} vs. Baseline)")
    hist_only = sub_daily[sub_daily["year"] < target_year]
    if not hist_only.empty:
        clim = (
            hist_only.groupby("doy")[val_col]
            .agg(
                multi_year_avg="mean",
                p90=lambda s: float(np.percentile(s, 90)),
            )
            .reset_index()
        )
        clim["avg_7d"] = clim["multi_year_avg"].rolling(7, min_periods=1, center=True).mean()
        clim["p90_7d"] = clim["p90"].rolling(7, min_periods=1, center=True).mean()

        curr_yr = sub_daily[sub_daily["year"] == target_year][["doy", val_col]].copy()
        curr_yr["curr_7d"] = curr_yr[val_col].rolling(7, min_periods=1).mean()
        comp = clim.merge(curr_yr, on="doy", how="left")

        fig_clim = go.Figure()
        fig_clim.add_trace(
            go.Scatter(
                x=comp["doy"], y=comp["p90_7d"], name="90th Percentile (Extreme)",
                line=dict(color="#feb24c", width=1, dash="dot"),
            )
        )
        fig_clim.add_trace(
            go.Scatter(
                x=comp["doy"], y=comp["avg_7d"], name="Multi-Year Average",
                line=dict(color="#38bdf8", width=2),
            )
        )
        fig_clim.add_trace(
            go.Scatter(
                x=comp["doy"], y=comp["curr_7d"], name=f"{target_year} Observed (7d avg)",
                line=dict(color="#e31a1c", width=2.5),
            )
        )
        fig_clim.update_xaxes(tickmode="array", tickvals=MONTH_TICKS, ticktext=MONTH_NAMES, title="Month of Year")
        fig_clim.update_yaxes(title="Harmonised Cell-Days" if is_harm else "Raw Hotspots")
        fig_clim.update_layout(
            height=340, margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        )
        st.plotly_chart(fig_clim, use_container_width=True)
    else:
        st.info("Select a target date after the first baseline year to compare against multi-year averages.")

with c_ts:
    st.subheader(f"Multi-Decade Continuity Series ({yr_span_label}, 7-Day Rolling Mean)")
    sub_daily["rolling_7d"] = sub_daily[val_col].rolling(7, min_periods=1).mean()
    fig_ts = px.line(sub_daily, x="date", y="rolling_7d", height=340)
    fig_ts.update_traces(line_color="#e6550d")
    fig_ts.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_ts, use_container_width=True)

with st.expander("Team SkyBound — Methods, Validation & Sensor Continuity Notes", expanded=True):
    st.markdown(
        f"- **Developed by Team SkyBound (NASA Space Apps Challenge 2026)** for early warning responders, firefighters, land managers, and Earth scientists.\n"
        f"- **Cross-Sensor Harmonisation:** Detections from MODIS (1 km) and VIIRS (375 m S-NPP, NOAA-20, NOAA-21) are binned onto a 5.5 km grid (confidence ≥ 50) with same-day cell duplicates collapsed to 1 event/day, improving cross-sensor Pearson correlation from **r = {metrics['r_raw']:.4f}** to **r = {metrics['r_harmonised']:.4f}** across {metrics['overlap_days']:,} overlap days.\n"
        f"- **Sensor Retirement Continuity:** Bridges the November 2, 2026 Suomi-NPP end-of-delivery transition and aging Terra/Aqua MODIS sensors seamlessly into NOAA-20 and NOAA-21 VIIRS.\n"
        f"- **Data Attribution & License:** Active fire detections courtesy of NASA FIRMS (*Fire Information for Resource Management System*). Released under the **Apache-2.0** license."
    )
