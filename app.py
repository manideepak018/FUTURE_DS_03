
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Marketing Funnel Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed"

st.markdown("""
<style>
.block-container {padding-top: 1.7rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {
    background: rgba(128,128,128,.08);
    padding: 15px;
    border-radius: 12px;
    border: 1px solid rgba(128,128,128,.16);
}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data():
    journey = pd.read_csv(DATA_DIR / "journey_tracking.csv")
    funnel = pd.read_csv(DATA_DIR / "funnel_metrics.csv")
    channel = pd.read_csv(DATA_DIR / "channel_performance.csv")
    device = pd.read_csv(DATA_DIR / "device_performance.csv")
    progression = pd.read_csv(DATA_DIR / "stage_progression.csv")

    journey["Stage_Date"] = pd.to_datetime(
        journey["Stage_Date"], errors="coerce"
    )
    journey["Stage_Number"] = pd.to_numeric(
        journey["Stage_Number"], errors="coerce"
    )
    journey["Days_in_Funnel"] = pd.to_numeric(
        journey["Days_in_Funnel"], errors="coerce"
    )
    journey["Converted"] = (
        journey["Converted"].astype(str).str.lower().isin(["true", "1", "yes"])
    )

    for frame, columns in [
        (funnel, ["Leads", "Drop_Off", "Drop_Off_%", "Conv_to_Next_%", "Cumulative_%"]),
        (channel, ["Leads", "Conversions", "Conv_Rate_%", "Share_%"]),
        (device, ["Leads", "Conversions", "Conv_Rate_%"]),
        (progression, ["Start", "End", "Drop_Off", "Drop_Off_%"]),
    ]:
        for column in columns:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")

    return journey, funnel, channel, device, progression


st.title("📈 Marketing Funnel Analytics")
st.caption(
    "Understand lead journeys, conversion performance, marketing channels, "
    "device behavior, and funnel drop-offs."
)

required_files = [
    "journey_tracking.csv",
    "funnel_metrics.csv",
    "channel_performance.csv",
    "device_performance.csv",
    "stage_progression.csv",
]
missing_files = [name for name in required_files if not (DATA_DIR / name).exists()]

if missing_files:
    st.error(
        "Missing required files in data/processed: "
        + ", ".join(missing_files)
    )
    st.stop()

try:
    journey, funnel, channel_data, device_data, progression = load_data()
except Exception as error:
    st.error(f"Could not load the project data: {error}")
    st.stop()

required_columns = {
    "Lead_ID", "Channel", "Device", "Stage", "Stage_Date",
    "Stage_Number", "Converted", "Days_in_Funnel",
}
if not required_columns.issubset(journey.columns):
    st.error("The journey dataset is missing one or more required columns.")
    st.stop()

journey = journey.dropna(subset=["Lead_ID"]).copy()

# ---------------- Sidebar filters ----------------
st.sidebar.header("🔎 Filters")

channels = sorted(journey["Channel"].dropna().astype(str).unique())
devices = sorted(journey["Device"].dropna().astype(str).unique())

selected_channels = st.sidebar.multiselect(
    "Marketing channel", channels, default=channels
)
selected_devices = st.sidebar.multiselect(
    "Device", devices, default=devices
)

valid_dates = journey["Stage_Date"].dropna()

if not valid_dates.empty:
    min_date = valid_dates.min().date()
    max_date = valid_dates.max().date()
    chosen_dates = st.sidebar.date_input(
        "Stage date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
else:
    chosen_dates = ()

filtered = journey[
    journey["Channel"].astype(str).isin(selected_channels)
    & journey["Device"].astype(str).isin(selected_devices)
].copy()

if isinstance(chosen_dates, (tuple, list)) and len(chosen_dates) == 2:
    start_date, end_date = chosen_dates
    filtered = filtered[
        filtered["Stage_Date"].dt.date.between(start_date, end_date)
        | filtered["Stage_Date"].isna()
    ]

if filtered.empty:
    st.warning("No journey records match these filters.")
    st.stop()

# Each lead may have several journey rows, so count unique lead IDs.
lead_summary = (
    filtered.sort_values("Stage_Number")
    .groupby("Lead_ID", as_index=False)
    .agg(
        Channel=("Channel", "first"),
        Device=("Device", "first"),
        Converted=("Converted", "max"),
        Days_in_Funnel=("Days_in_Funnel", "max"),
    )
)

total_leads = lead_summary["Lead_ID"].nunique()
conversions = int(lead_summary["Converted"].sum())
conversion_rate = conversions / total_leads * 100 if total_leads else 0
average_days = lead_summary["Days_in_Funnel"].mean()

# ---------------- Overview ----------------
st.subheader("Business Overview")

a, b, c, d = st.columns(4)
a.metric("Unique Leads", f"{total_leads:,}")
b.metric("Converted Leads", f"{conversions:,}")
c.metric("Conversion Rate", f"{conversion_rate:.2f}%")
d.metric(
    "Average Days in Funnel",
    f"{average_days:.1f}" if pd.notna(average_days) else "N/A",
)

st.caption(
    "Overview metrics are calculated from unique leads represented in the "
    "filtered journey records. The date filter selects stage events, so a "
    "lead may be represented by only part of its journey."
)

st.divider()

# ---------------- Funnel overview ----------------
st.subheader("Marketing Funnel")

if not funnel.empty and {"Stage", "Leads"}.issubset(funnel.columns):
    funnel_chart = funnel.dropna(subset=["Stage", "Leads"]).copy()

    fig = go.Figure(go.Funnel(
        y=funnel_chart["Stage"],
        x=funnel_chart["Leads"],
        textinfo="value+percent initial",
        marker={"line": {"width": 1, "color": "white"}},
    ))
    fig.update_layout(
        title="Lead Volume Across Funnel Stages",
        xaxis_title="Leads",
        height=430,
    )
    st.plotly_chart(fig, use_container_width=True)

    if "Drop_Off_%" in funnel_chart.columns:
        drop_chart = funnel_chart[
            funnel_chart["Drop_Off_%"].notna()
        ]
        if not drop_chart.empty:
            fig = px.bar(
                drop_chart,
                x="Stage",
                y="Drop_Off_%",
                text_auto=".2f",
                title="Drop-off Rate by Stage",
                labels={"Drop_Off_%": "Drop-off (%)"},
            )
            st.plotly_chart(fig, use_container_width=True)

    with st.expander("View original funnel metrics"):
        st.dataframe(funnel, use_container_width=True, hide_index=True)
else:
    st.info("Funnel metrics are unavailable.")

st.divider()

# ---------------- Channel performance ----------------
st.subheader("Channel Performance")

if not channel_data.empty:
    left, right = st.columns(2)

    with left:
        fig = px.bar(
            channel_data.sort_values("Leads", ascending=False),
            x="Channel",
            y="Leads",
            color="Channel",
            text_auto=True,
            title="Leads by Marketing Channel",
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        fig = px.bar(
            channel_data.sort_values("Conv_Rate_%", ascending=False),
            x="Channel",
            y="Conv_Rate_%",
            color="Channel",
            text_auto=".2f",
            title="Conversion Rate by Channel",
            labels={"Conv_Rate_%": "Conversion rate (%)"},
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(channel_data, use_container_width=True, hide_index=True)

st.divider()

# ---------------- Device performance ----------------
st.subheader("Device Performance")

if not device_data.empty:
    left, right = st.columns(2)

    with left:
        fig = px.bar(
            device_data,
            x="Device",
            y="Leads",
            color="Device",
            text_auto=True,
            title="Leads by Device",
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        fig = px.bar(
            device_data,
            x="Device",
            y="Conv_Rate_%",
            color="Device",
            text_auto=".2f",
            title="Conversion Rate by Device",
            labels={"Conv_Rate_%": "Conversion rate (%)"},
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(device_data, use_container_width=True, hide_index=True)

st.divider()

# ---------------- Stage progression ----------------
st.subheader("Stage-to-Stage Progression")

if not progression.empty:
    if {"From", "To", "Drop_Off_%"}.issubset(progression.columns):
        progression_view = progression.copy()
        progression_view["Transition"] = (
            progression_view["From"].astype(str)
            + " → "
            + progression_view["To"].astype(str)
        )

        fig = px.bar(
            progression_view,
            x="Transition",
            y="Drop_Off_%",
            text_auto=".2f",
            title="Drop-off Between Consecutive Stages",
            labels={"Drop_Off_%": "Drop-off (%)"},
        )
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(progression, use_container_width=True, hide_index=True)

st.divider()

# ---------------- Lead explorer ----------------
st.subheader("Lead Journey Explorer")

lead_view = filtered.sort_values(
    ["Lead_ID", "Stage_Number"]
).copy()

st.dataframe(lead_view, use_container_width=True, hide_index=True)

st.download_button(
    "⬇️ Download filtered journey records",
    data=lead_view.to_csv(index=False).encode("utf-8"),
    file_name="marketing_journey_filtered.csv",
    mime="text/csv",
)

st.download_button(
    "⬇️ Download funnel metrics",
    data=funnel.to_csv(index=False).encode("utf-8"),
    file_name="funnel_metrics.csv",
    mime="text/csv",
)

st.caption(
    "Channel, device, funnel and progression charts use the project's "
    "precomputed CSV summaries. Overview metrics use filtered journey records. "
    "Results may differ because the files use different aggregation methods."
)
