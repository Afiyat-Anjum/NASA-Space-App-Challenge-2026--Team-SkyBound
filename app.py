import numpy as np
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


@st.cache_resource
def get_services():
    svc = LocalFireCacheService()
    return svc, FireContinuityAgent(svc)


@st.cache_data
def cached_cells(country: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp):
    svc, _ = get_services()
    return svc.get_map_cells(country, start_ts, end_ts)


svc, agent = get_services()
metrics = svc.get_metrics()

st.sidebar.header("Region, Date & Visual Style")
selected_country = st.sidebar.selectbox(
    "Study Area (South Asia)", options=metrics["countries"], index=0, format_func=lambda x: x.replace("_", " ")
)
sub_daily = svc.get_daily_series(selected_country)
selected_date = st.sidebar.date_input(
    "Target Inspection Date",
    value=sub_daily["date"].max().date(),
    min_value=sub_daily["date"].min().date(),
    max_value=sub_daily["date"].max().date(),
)
window_days = st.sidebar.slider("Map Aggregation Window (Days)", 1, 30, 7)
palette = PALETTES[st.sidebar.selectbox("Fire Intensity Color Ramp", list(PALETTES.keys()), index=0)]
map_style = "carto-darkmatter" if st.sidebar.radio("Map Theme", ["Dark Basemap", "Light Basemap"]) == "Dark Basemap" else "carto-positron"

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

c_metrics = metrics["by_country"].get(selected_country, metrics)
v1, v2, v3, v4 = st.columns(4)
v1.metric("Raw MODIS vs. VIIRS (r)", f"{c_metrics['r_raw']:.4f}")
v2.metric("Harmonised MODIS vs. VIIRS (r)", f"{c_metrics['r_harmonised']:.4f}", delta=f"{c_metrics['r_harmonised'] - c_metrics['r_raw']:+.4f}")
v3.metric("Sensor Overlap Days", f"{c_metrics['overlap_days']:,}")
v4.metric("Grid & Confidence Rule", f"{metrics['cell_size_km']} km | Conf ≥ {metrics['confidence_min']}")

st.subheader("Is this unusual for this place and this time of year?")
briefing = agent.generate_situational_briefing(
    country=selected_country, target_date=str(selected_date), mode="harmonised" if is_harm else "raw"
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

col_map, col_cal = st.columns([1.05, 1.35])
with col_map:
    st.subheader(f"Active Fire Grid Map ({window_days}-Day Window)")
    target_ts = pd.Timestamp(selected_date)
    map_df = cached_cells(selected_country, target_ts - pd.Timedelta(days=window_days - 1), target_ts)
    if not map_df.empty:
        agg = map_df.groupby(["cell_id", "grid_lat", "grid_lon"], as_index=False).agg(activity=(cell_col, "sum"), total_frp=("frp", "sum"))
        if len(agg) > 8000:
            agg = agg.nlargest(8000, "activity")
        clat, clon, czoom = COUNTRY_CENTERS.get(selected_country, (22.5, 79.0, 3.8))
        map_fn = px.scatter_map if hasattr(px, "scatter_map") else px.scatter_mapbox
        style_kw = {"map_style": map_style} if hasattr(px, "scatter_map") else {"mapbox_style": map_style}
        fig_map = map_fn(
            agg, lat="grid_lat", lon="grid_lon", color="activity", size="activity", size_max=14,
            hover_data={"grid_lat": True, "grid_lon": True, "activity": True, "total_frp": ":.1f"},
            color_continuous_scale=palette, center={"lat": clat, "lon": clon}, zoom=czoom, height=460, **style_kw
        )
        fig_map.update_layout(margin=dict(l=0, r=0, t=5, b=0))
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("No detections in this window.")

with col_cal:
    st.subheader("Year-by-Day Burning Activity Calendar (2000–2026)")
    cal_pivot = sub_daily.pivot_table(index="year", columns="doy", values=val_col, aggfunc="sum", fill_value=0)
    fig_cal = px.imshow(cal_pivot, aspect="auto", color_continuous_scale=palette, height=460)
    fig_cal.update_layout(margin=dict(l=0, r=0, t=5, b=0))
    st.plotly_chart(fig_cal, use_container_width=True)

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

with st.expander("Methods, Validation & Sensor Continuity Notes", expanded=True):
    st.markdown(f"- {briefing['continuity_note']}\n- **Validation:** Pearson correlation improved from **r = {metrics['r_raw']:.4f}** to **r = {metrics['r_harmonised']:.4f}** across {metrics['overlap_days']:,} overlap days.\n- **Attribution:** NASA FIRMS MODIS Collection 6.1 & VIIRS (S-NPP, NOAA-20, NOAA-21). Apache-2.0.")
