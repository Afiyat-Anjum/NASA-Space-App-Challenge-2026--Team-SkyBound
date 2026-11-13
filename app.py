import pandas as pd
import plotly.express as px
import streamlit as st
from src.agents.orchestrator import FireContinuityAgent
from src.api.cache_service import LocalFireCacheService

st.set_page_config(page_title="FIRMS South Asia Harmonised Burn Calendar", layout="wide")

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
def cached_spread_risk(country: str, end_ts: pd.Timestamp):
    svc, _ = get_services()
    return svc.predict_spread_risk(country, end_ts)


svc, agent = get_services()
metrics = svc.get_metrics()

# --- SIDEBAR: REGION, DATE RANGE & VISUAL ACCESSIBILITY ---
st.sidebar.header("Search Region, Date Range & Style")
selected_country = st.sidebar.selectbox(
    "Study Area (South Asia)", options=metrics["countries"], index=0, format_func=lambda x: x.replace("_", " ")
)
sub_daily = svc.get_daily_series(selected_country)
min_d = sub_daily["date"].min().date()
max_d = sub_daily["date"].max().date()
default_start = max(min_d, (pd.Timestamp(max_d) - pd.Timedelta(days=6)).date())

start_date = st.sidebar.date_input("Search Start Date", value=default_start, min_value=min_d, max_value=max_d)
end_date = st.sidebar.date_input("Search End Date (Anomaly Target)", value=max_d, min_value=min_d, max_value=max_d)

if start_date > end_date:
    st.sidebar.warning("Start Date is after End Date; adjusting Start Date to match End Date.")
    start_date = end_date

span_days = (end_date - start_date).days + 1
show_spread = st.sidebar.checkbox("Overlay Predicted Next-7-Day Spread Risk Zones", value=True)
palette = PALETTES[st.sidebar.selectbox("Fire Intensity Color Ramp", list(PALETTES.keys()), index=0)]
map_style = "carto-darkmatter" if st.sidebar.radio("Map Theme", ["Dark Basemap", "Light Basemap"]) == "Dark Basemap" else "carto-positron"

# --- HEADER & SINGLE MASTER TOGGLE ---
st.title(f"Active Fire Continuity & Burn Calendar — {selected_country.replace('_', ' ')}")
st.caption("Harmonised Multi-Decade NASA FIRMS MODIS & VIIRS (S-NPP, NOAA-20, NOAA-21) Fire Monitoring")

mode = st.radio(
    "Master Series Switch (updates every map, calendar, chart, and anomaly metric):",
    ["Harmonised (5.5 km Collapsed Cell-Days)", "Raw Detections (Unadjusted Sensor Counts)"],
    horizontal=True,
)
is_harm = mode.startswith("Harmonised")
val_col = "harmonised_count" if is_harm else "raw_count"
cell_col = "harmonised_hits" if is_harm else "raw_hits"

# --- VALIDATION CORRELATION & SEARCH SUMMARY ---
c_metrics = metrics["by_country"].get(selected_country, metrics)
range_mask = (sub_daily["date"].dt.date >= start_date) & (sub_daily["date"].dt.date <= end_date)
range_total = int(sub_daily.loc[range_mask, val_col].sum())

start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)
map_df = cached_cells(selected_country, start_ts, end_ts)
spread_df = cached_spread_risk(selected_country, end_ts) if show_spread else pd.DataFrame()
high_risk_cells = int((spread_df["spread_risk_pct"] >= 65.0).sum()) if not spread_df.empty else 0

v1, v2, v3, v4 = st.columns(4)
v1.metric("Raw MODIS vs. VIIRS (r)", f"{c_metrics['r_raw']:.4f}")
v2.metric("Harmonised MODIS vs. VIIRS (r)", f"{c_metrics['r_harmonised']:.4f}", delta=f"{c_metrics['r_harmonised'] - c_metrics['r_raw']:+.4f}")
v3.metric(f"Selected Range Total ({span_days}d)", f"{range_total:,}", help=f"{start_date} to {end_date}")
v4.metric("High-Risk Spread Cells (Next 7d)", f"{high_risk_cells:,}", help="Unburned 5.5 km perimeter cells with >= 65% empirical spread risk")

# --- SEASONAL ANOMALY CHECK ---
st.subheader("Is this unusual for this place and this time of year?")
briefing = agent.generate_situational_briefing(
    country=selected_country, target_date=str(end_date), mode="harmonised" if is_harm else "raw"
)
anom = briefing["anomaly_assessment"]
if anom.get("status") == "OK":
    box_fn = st.error if anom["percentile"] >= 90 else (st.warning if anom["percentile"] >= 75 else st.success)
    box_fn(
        f"**{anom['verdict']}** — In **{selected_country.replace('_', ' ')}** on **{anom['date']}** (DOY {anom['doy']}), "
        f"activity was **{anom['current_value']:,}** ({'Harmonised Cell-Days' if is_harm else 'Raw Hotspots'}), "
        f"ranking at the **{anom['percentile']}th percentile** vs. the **±7-day baseline** "
        f"({anom['baseline_years']}, median = **{anom['baseline_median']:.0f}**, 90th pct = **{anom['baseline_p90']:.0f}**)."
    )

# --- SPATIAL MAP & YEAR-BY-MONTH BURNING ACTIVITY CALENDAR ---
col_map, col_cal = st.columns([1.05, 1.35])

with col_map:
    st.subheader(f"Active Fire & Spread Risk Map ({start_date} to {end_date})")
    if not map_df.empty:
        agg = map_df.groupby(["cell_id", "grid_lat", "grid_lon"], as_index=False).agg(activity=(cell_col, "sum"), total_frp=("frp", "sum"))
        if len(agg) > 6000:
            agg = agg.nlargest(6000, "activity")

        clat, clon, czoom = COUNTRY_CENTERS.get(selected_country, (22.5, 79.0, 3.8))
        map_fn = px.scatter_map if hasattr(px, "scatter_map") else px.scatter_mapbox
        style_kw = {"map_style": map_style} if hasattr(px, "scatter_map") else {"mapbox_style": map_style}

        if show_spread and not spread_df.empty:
            active_layer = agg[["grid_lat", "grid_lon", "activity", "total_frp"]].copy()
            active_layer["layer"] = "1. Active Fire Cell"
            active_layer["size_val"] = active_layer["activity"].clip(lower=1, upper=12)
            active_layer["risk_pct"] = 100.0

            risk_layer = spread_df[spread_df["spread_risk_pct"] >= 40.0][
                ["grid_lat", "grid_lon", "spread_risk_pct", "risk_tier", "distance_km", "seasonal_susceptibility_pct"]
            ].copy()
            risk_layer["layer"] = risk_layer["risk_tier"].apply(
                lambda t: "2. High Spread Risk (Next 7d)" if t.startswith("High") else "3. Moderate Spread Risk (Next 7d)"
            )
            risk_layer["activity"] = 0
            risk_layer["total_frp"] = 0.0
            risk_layer["size_val"] = (risk_layer["spread_risk_pct"] / 12.0).clip(lower=3, upper=9)
            risk_layer["risk_pct"] = risk_layer["spread_risk_pct"]

            combined = pd.concat([risk_layer, active_layer], ignore_index=True)
            fig_map = map_fn(
                combined,
                lat="grid_lat",
                lon="grid_lon",
                color="layer",
                size="size_val",
                size_max=13,
                color_discrete_map={
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
        st.info(f"No spatial cell detections recorded between {start_date} and {end_date}.")

with col_cal:
    st.subheader("Year-by-Month Burning Activity Calendar (2000–2026)")
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

# --- DOWNLOADABLE CSV OUTPUTS (SEARCH HOTSPOTS, ANALYTICS & SPREAD RISK) ---
dl1, dl2, dl3 = st.columns(3)
with dl1:
    export_spots = map_df.head(50000).copy()
    if not export_spots.empty:
        export_spots["date"] = pd.to_datetime(export_spots["date"]).dt.strftime("%Y-%m-%d")
    st.download_button(
        label=f"Download Search Hotspots CSV ({start_date} to {end_date})",
        data=export_spots.to_csv(index=False).encode("utf-8"),
        file_name=f"firms_{selected_country.lower()}_hotspots_{start_date}_to_{end_date}.csv",
        mime="text/csv",
        disabled=export_spots.empty,
    )

with dl2:
    st.download_button(
        label="Download 2000–2026 Daily Analytics CSV",
        data=sub_daily.to_csv(index=False).encode("utf-8"),
        file_name=f"firms_{selected_country.lower()}_daily_analytics_2000_2026.csv",
        mime="text/csv",
    )

with dl3:
    st.download_button(
        label=f"Download Projected Spread Risk CSV ({end_date})",
        data=spread_df.to_csv(index=False).encode("utf-8"),
        file_name=f"firms_{selected_country.lower()}_spread_risk_{end_date}.csv",
        mime="text/csv",
        disabled=spread_df.empty,
    )

# --- MULTI-DECADE CONTINUITY SERIES & OVERLAP SCATTER ---
c_ts, c_sc = st.columns([1.4, 1.0])
with c_ts:
    st.subheader("Multi-Decade Continuity Series (7-Day Rolling Mean)")
    sub_daily["rolling_7d"] = sub_daily[val_col].rolling(7, min_periods=1).mean()
    fig_ts = px.line(sub_daily, x="date", y="rolling_7d", height=330)
    fig_ts.update_traces(line_color="#e6550d")
    fig_ts.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_ts, use_container_width=True)

with c_sc:
    st.subheader("MODIS vs. VIIRS Overlap Agreement")
    ov_sub = svc.get_overlap_series(selected_country)
    x_col = "modis_harm" if is_harm else "modis_raw"
    y_col = "viirs_harm" if is_harm else "viirs_raw"
    fig_sc = px.scatter(ov_sub, x=x_col, y=y_col, opacity=0.45, height=330)
    fig_sc.update_traces(marker_color="#d94801")
    fig_sc.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_sc, use_container_width=True)

with st.expander("Methods, Spread Risk Model & Sensor Continuity Notes", expanded=True):
    st.markdown(
        f"- {briefing['continuity_note']}\n"
        f"- **Validation:** Pearson correlation improved from **r = {metrics['r_raw']:.4f}** to **r = {metrics['r_harmonised']:.4f}** across {metrics['overlap_days']:,} overlap days.\n"
        f"- **Empirical Fire Spread Risk Model:** Evaluates unburned 5.5 km perimeter cells within 11 km of active fire fronts by combining active front proximity/FRP intensity (55%) with 14-day historical seasonal burn susceptibility (45%) and 48h progression heading. *Caveat: Uses cached satellite detections only without live surface wind or terrain slope inputs; pair with local meteorological wind forecasts.*\n"
        f"- **Attribution:** NASA FIRMS MODIS Collection 6.1 & VIIRS (S-NPP, NOAA-20, NOAA-21). Apache-2.0."
    )
