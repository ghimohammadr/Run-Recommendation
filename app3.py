import streamlit as st
import pandas as pd
import numpy as np
import folium
import matplotlib.pyplot as plt
import requests
import plotly.graph_objects as go

from io import BytesIO
from plotly.subplots import make_subplots
from streamlit_folium import folium_static
from folium.plugins import FastMarkerCluster
from branca.element import Element


# =====================================================
# Streamlit setup
# =====================================================
st.set_page_config(page_title="Route Recommendation Tool", layout="wide")
st.title("File Upload and Analysis Tool")


# =====================================================
# Inputs
# =====================================================
upload_1 = st.file_uploader("Upload Route Stats CSV File", type=["csv"])
upload_2 = st.file_uploader("Upload Drop Stats CSV File", type=["csv"])

sheet_url = "https://docs.google.com/spreadsheets/d/1rw7xX_Mk81a-9n5ke1WsY2drWBXX_8Qu/export?format=xlsx"


# =====================================================
# Helper functions
# =====================================================
def check_columns(df, required_cols, file_name):
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        st.warning(f"{file_name} is missing these columns: {missing}")
        return False
    return True


def safe_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def route_label(x):
    try:
        x_float = float(x)
        if x_float.is_integer():
            return str(int(x_float))
        return str(x)
    except Exception:
        return str(x)


@st.cache_data(ttl=3600, show_spinner=False)
def load_historical_data(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return pd.read_excel(BytesIO(response.content))


@st.cache_data(show_spinner=False)
def read_csv_bytes(file_bytes):
    return pd.read_csv(BytesIO(file_bytes))


@st.cache_data(show_spinner=False)
def clean_historical_data(hist_df):
    hist_df = hist_df.copy()

    required_cols = [
        "Round",
        "Pln Finish Date",
        "Pln Start Date",
        "Completed",
        "Planned Distance",
        "Slot",
    ]

    missing = [col for col in required_cols if col not in hist_df.columns]
    if missing:
        return None, missing

    hist_df = hist_df.dropna(subset=["Round"]).reset_index(drop=True)

    hist_df = hist_df[
        hist_df["Planned Distance"].astype(str).str.lower().str.strip() != "nankm"
    ].reset_index(drop=True)

    completed_split = hist_df["Completed"].astype(str).str.split("/", expand=True)

    hist_df["completed Drops"] = pd.to_numeric(completed_split[0], errors="coerce")

    if completed_split.shape[1] > 1:
        hist_df["Total Drops"] = pd.to_numeric(completed_split[1], errors="coerce")
    else:
        hist_df["Total Drops"] = np.nan

    hist_df = hist_df[
        (hist_df["completed Drops"].notna()) &
        (hist_df["completed Drops"] != 0)
    ].reset_index(drop=True)

    hist_df["distance"] = (
        hist_df["Planned Distance"]
        .astype(str)
        .str.replace("km", "", regex=False)
        .str.strip()
    )

    hist_df["distance"] = pd.to_numeric(hist_df["distance"], errors="coerce")
    hist_df = hist_df.dropna(subset=["distance"]).reset_index(drop=True)

    hist_df["Pln Start Date"] = pd.to_datetime(hist_df["Pln Start Date"], errors="coerce")
    hist_df["Day of Week"] = hist_df["Pln Start Date"].dt.day_name()

    hist_df["KM Cost"] = np.maximum((hist_df["distance"] - 200) * 1, 0)
    hist_df["Drop Cost"] = np.maximum((hist_df["completed Drops"] - 70) * 4.5, 0)
    hist_df["Flat rate Cost"] = 370
    hist_df["Total Cost"] = hist_df["KM Cost"] + hist_df["Drop Cost"] + hist_df["Flat rate Cost"]
    hist_df["Cost per Drop"] = hist_df["Total Cost"] / hist_df["completed Drops"]

    return hist_df, []


def build_day_stats(dow_hist_df):
    runs_by_date = dow_hist_df.groupby("Pln Start Date")["Round"].nunique()

    slot_counts = (
        dow_hist_df
        .groupby(["Pln Start Date", "Slot"])["Round"]
        .nunique()
        .reset_index(name="No. of Runs")
    )

    am_counts = slot_counts[slot_counts["Slot"] == "AM"]["No. of Runs"].tolist()
    pm_counts = slot_counts[slot_counts["Slot"] == "PM"]["No. of Runs"].tolist()

    dict_dow = {
        "Total No. of runs": len(dow_hist_df.groupby(["Round", "Pln Finish Date"])),
        "Min No. of runs": runs_by_date.min() if not runs_by_date.empty else 0,
        "Max No. of runs": runs_by_date.max() if not runs_by_date.empty else 0,

        "Averge No. of AM runs": round(np.mean(am_counts) if am_counts else 0, 2),
        "Min No. of AM runs": min(am_counts) if am_counts else 0,
        "Max No. of AM runs": max(am_counts) if am_counts else 0,

        "Averge No. of PM runs": round(np.mean(pm_counts) if pm_counts else 0, 2),
        "Min No. of PM runs": min(pm_counts) if pm_counts else 0,
        "Max No. of PM runs": max(pm_counts) if pm_counts else 0,

        "Total No. of Drops": int(dow_hist_df["completed Drops"].sum()),
        "Min No. of Drops": dow_hist_df["completed Drops"].min(),
        "Max No. of Drops": dow_hist_df["completed Drops"].max(),

        "Max Km Bonus Cost": dow_hist_df["KM Cost"].max(),
        "Avg Km Bonus Cost": round(dow_hist_df["KM Cost"].mean(), 2),
        "Max Drop Bonus Cost": dow_hist_df["Drop Cost"].max(),
        "Avg Drop Bonus Cost": round(dow_hist_df["Drop Cost"].mean(), 2),

        "Total Cost": round(dow_hist_df["Total Cost"].sum(), 2),
        "Max Cost per Drop": round(dow_hist_df["Cost per Drop"].max(), 2),
        "Avg Cost per Drop": round(dow_hist_df["Cost per Drop"].mean(), 2),
        "Min Cost per Drop": round(dow_hist_df["Cost per Drop"].min(), 2),
    }

    stats_table_df = pd.DataFrame(dict_dow, index=[0]).T.reset_index()
    stats_table_df.columns = ["Metric", "Value"]

    mid_index = len(stats_table_df) // 2

    stats_table_df1 = stats_table_df.iloc[:mid_index].reset_index(drop=True)
    stats_table_df2 = stats_table_df.iloc[mid_index:].reset_index(drop=True)

    stats_table_df1.columns = ["Metric 1", "Value 1"]
    stats_table_df2.columns = ["Metric 2", "Value 2"]

    display_df = pd.concat([stats_table_df1, stats_table_df2], axis=1)

    display_df["Metric 1"] = display_df["Metric 1"].apply(
        lambda x: f"**{x}**" if pd.notnull(x) else x
    )
    display_df["Metric 2"] = display_df["Metric 2"].apply(
        lambda x: f"**{x}**" if pd.notnull(x) else x
    )

    return display_df


def build_round_stats(dow_hist_df):
    valid_df = dow_hist_df.dropna(subset=["Cost per Drop", "completed Drops", "distance"]).copy()

    if valid_df.empty:
        return pd.DataFrame(columns=[
            "Round",
            "Min Cost per Drop",
            "Associated Drops",
            "Total Driving Distance",
        ])

    idx = valid_df.groupby("Round")["Cost per Drop"].idxmin()
    best_rows = valid_df.loc[idx].copy()

    round_stats_df = pd.DataFrame({
        "Round": best_rows["Round"].apply(route_label),
        "Min Cost per Drop": best_rows["Cost per Drop"],
        "Associated Drops": best_rows["completed Drops"],
        "Total Driving Distance": best_rows["distance"],
    })

    round_stats_df = round_stats_df.sort_values(
        by="Total Driving Distance",
        ascending=True
    ).reset_index(drop=True)

    return round_stats_df


def plot_round_stats(round_stats_df):
    if round_stats_df.empty:
        st.warning("No valid round statistics available for this day.")
        return

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    round_stats_df["Distance Group"] = np.where(
        round_stats_df["Total Driving Distance"] > 200,
        "Cost per Drop - Distance > 200 KM",
        "Cost per Drop - Distance ≤ 200 KM",
    )

    high_df = round_stats_df[round_stats_df["Total Driving Distance"] > 200]
    low_df = round_stats_df[round_stats_df["Total Driving Distance"] <= 200]

    if not high_df.empty:
        fig.add_trace(
            go.Bar(
                x=high_df["Round"],
                y=high_df["Min Cost per Drop"],
                marker_color="red",
                name="Cost per Drop - Distance > 200 KM",
                customdata=high_df["Total Driving Distance"],
                hovertemplate=(
                    "<b>Round:</b> %{x}<br>"
                    "<b>Min Cost per Drop:</b> %{y:.2f}<br>"
                    "<b>Total Driving Distance:</b> %{customdata:.2f} KM<br>"
                    "<extra></extra>"
                ),
            ),
            secondary_y=False,
        )

    if not low_df.empty:
        fig.add_trace(
            go.Bar(
                x=low_df["Round"],
                y=low_df["Min Cost per Drop"],
                marker_color="green",
                name="Cost per Drop - Distance ≤ 200 KM",
                customdata=low_df["Total Driving Distance"],
                hovertemplate=(
                    "<b>Round:</b> %{x}<br>"
                    "<b>Min Cost per Drop:</b> %{y:.2f}<br>"
                    "<b>Total Driving Distance:</b> %{customdata:.2f} KM<br>"
                    "<extra></extra>"
                ),
            ),
            secondary_y=False,
        )

    fig.add_trace(
        go.Scatter(
            x=round_stats_df["Round"],
            y=round_stats_df["Associated Drops"],
            mode="lines+markers",
            line=dict(color="black"),
            name="Associated Drops",
            customdata=list(zip(
                round_stats_df["Min Cost per Drop"],
                round_stats_df["Total Driving Distance"],
            )),
            hovertemplate=(
                "<b>Round:</b> %{x}<br>"
                "<b>Associated Drops:</b> %{y}<br>"
                "<b>Min Cost per Drop:</b> %{customdata[0]:.2f}<br>"
                "<b>Total Driving Distance:</b> %{customdata[1]:.2f} KM<br>"
                "<extra></extra>"
            ),
        ),
        secondary_y=True,
    )

    fig.update_layout(
        xaxis=dict(
            title="Round",
            type="category",
            tickangle=-45,
            categoryorder="array",
            categoryarray=round_stats_df["Round"].tolist(),
        ),
        yaxis=dict(title="Min Cost per Drop", showgrid=True),
        yaxis2=dict(title="Associated Drops", overlaying="y", side="right"),
        legend=dict(x=0.0, y=1.25),
        barmode="group",
        height=600,
        margin=dict(l=40, r=40, t=60, b=120),
    )

    st.plotly_chart(fig, use_container_width=True)


@st.cache_data(show_spinner=False)
def process_current_routes(route_stats):
    route_stats = route_stats.copy()

    required_cols = [
        "zone",
        "routeClient",
        "vehicle",
        "rateZone",
        "drivingDistance",
        "drivingTime",
        "totalTime",
        "co2",
        "d1",
        "d2",
    ]

    missing = [col for col in required_cols if col not in route_stats.columns]
    if missing:
        return None, None, None, None, None, missing

    route_stats["zone"] = route_stats["zone"].astype(str)
    route_stats["routeClient"] = route_stats["routeClient"].astype(str).str.strip()

    metro_mask = route_stats["zone"].str.contains("metro", case=False, na=False)
    routes_metro = route_stats[metro_mask].copy().reset_index(drop=True)

    if routes_metro.empty:
        return routes_metro, [], [], [], None, []

    for col in ["drivingDistance", "drivingTime", "totalTime", "co2", "d1", "d2"]:
        routes_metro[col] = pd.to_numeric(routes_metro[col], errors="coerce")

    routes_metro = routes_metro.dropna(
        subset=["routeClient", "drivingDistance", "d1", "d2"]
    ).reset_index(drop=True)

    routes_metro["KM Cost"] = np.maximum((routes_metro["drivingDistance"] / 1000 - 200) * 1, 0)
    routes_metro["No. of overloaded drops"] = np.maximum(routes_metro["d2"] - 70, 0)
    routes_metro["Drop Cost"] = np.maximum((routes_metro["d2"] - 70) * 4.5, 0)
    routes_metro["Flat Rate"] = 370
    routes_metro["Total Cost"] = routes_metro["KM Cost"] + routes_metro["Drop Cost"] + routes_metro["Flat Rate"]

    routes_metro["Cost per Drop"] = np.where(
        routes_metro["d1"] > 0,
        routes_metro["Total Cost"] / routes_metro["d1"],
        np.nan,
    )

    need_mask = (
        ((routes_metro["d2"] < 70) & (routes_metro["Cost per Drop"] > 370 / 70)) |
        (routes_metro["Cost per Drop"] > 6)
    )

    good_mask = (
        (routes_metro["d2"] >= 70) &
        (routes_metro["Cost per Drop"] < 370 / 70) &
        (routes_metro["drivingDistance"] / 1000 < 200)
    )

    need_to_be_refined = routes_metro[need_mask]["routeClient"].astype(str).tolist()
    good = routes_metro[good_mask]["routeClient"].astype(str).tolist()

    all_routes = set(routes_metro["routeClient"].astype(str))
    can_be_refined = sorted(
        list(all_routes - set(need_to_be_refined) - set(good))
    )

    max_length = max(
        len(need_to_be_refined),
        len(can_be_refined),
        len(good),
        1,
    )

    table_df = pd.DataFrame({
        "Need to be refined": need_to_be_refined + [""] * (max_length - len(need_to_be_refined)),
        "Can be refined": can_be_refined + [""] * (max_length - len(can_be_refined)),
        "Good": good + [""] * (max_length - len(good)),
    })

    return routes_metro, need_to_be_refined, can_be_refined, good, table_df, []


def style_classification_table(table_df):
    styled_df = (
        table_df.style
        .set_properties(
            subset=["Need to be refined"],
            **{"background-color": "red", "color": "white"},
        )
        .set_properties(
            subset=["Can be refined"],
            **{"background-color": "orange", "color": "white"},
        )
        .set_properties(
            subset=["Good"],
            **{"background-color": "lightgreen", "color": "black"},
        )
    )

    return styled_df


@st.cache_data(show_spinner=False)
def prepare_map_data(drops_stats, route_clients):
    drops_stats = drops_stats.copy()

    required_cols = ["RouteId", "Latitude", "Longitude"]
    missing = [col for col in required_cols if col not in drops_stats.columns]
    if missing:
        return pd.DataFrame(), missing

    drops_stats["RouteId"] = drops_stats["RouteId"].astype(str).str.strip()
    drops_stats["Latitude"] = pd.to_numeric(drops_stats["Latitude"], errors="coerce")
    drops_stats["Longitude"] = pd.to_numeric(drops_stats["Longitude"], errors="coerce")

    route_clients = set(pd.Series(route_clients).astype(str).str.strip())

    drops_metro = drops_stats[
        drops_stats["RouteId"].isin(route_clients)
    ].copy().reset_index(drop=True)

    drops_metro = drops_metro.dropna(
        subset=["Latitude", "Longitude"]
    ).reset_index(drop=True)

    drops_metro = drops_metro[
        drops_metro["Latitude"].between(-90, 90) &
        drops_metro["Longitude"].between(-180, 180)
    ].reset_index(drop=True)

    return drops_metro, []


def create_route_colors(route_ids):
    route_ids = sorted(pd.Series(route_ids).dropna().astype(str).unique())
    colors = plt.cm.gist_ncar(np.linspace(0, 1, max(len(route_ids), 1)))

    route_colors = {
        route: f"#{int(c[0] * 255):02x}{int(c[1] * 255):02x}{int(c[2] * 255):02x}"
        for route, c in zip(route_ids, colors)
    }

    return route_colors


def add_route_legend(m, route_colors, max_legend_routes=100):
    legend_html = """
    <div style="position: fixed;
                bottom: 50px;
                left: 50px;
                max-height: 300px;
                overflow-y: auto;
                background-color: white;
                z-index: 9999;
                padding: 10px;
                font-size: 14px;
                border-radius: 5px;
                box-shadow: 0px 0px 5px gray;">
        <b>Route ID Legend</b><br>
    """

    for i, (route, color) in enumerate(route_colors.items()):
        if i >= max_legend_routes:
            remaining = len(route_colors) - max_legend_routes
            legend_html += f"<br><b>+ {remaining} more routes</b>"
            break

        legend_html += f"""
        <div style="display: flex; align-items: center; padding: 2px;">
            <div style="width: 12px; height: 12px; background: {color}; margin-right: 5px;"></div>
            <span>{route}</span>
        </div>
        """

    legend_html += "</div>"
    m.get_root().html.add_child(Element(legend_html))


def create_folium_map(drops_metro, map_mode, max_points, show_hulls):
    if drops_metro.empty:
        st.warning("No valid Latitude/Longitude values found for the map.")
        return None

    map_df = drops_metro.copy()

    if len(map_df) > max_points:
        map_df = map_df.sample(n=max_points, random_state=42).reset_index(drop=True)
        st.info(f"Map is showing a sample of {max_points:,} drops from {len(drops_metro):,} valid drops.")

    map_center = [
        map_df["Latitude"].mean(),
        map_df["Longitude"].mean(),
    ]

    m = folium.Map(
        location=map_center,
        zoom_start=10,
        tiles="CartoDB positron",
        prefer_canvas=True,
    )

    if map_mode == "Fast clustered map":
        point_data = map_df[["Latitude", "Longitude"]].values.tolist()
        FastMarkerCluster(point_data).add_to(m)

    else:
        route_colors = create_route_colors(map_df["RouteId"])

        for _, row in map_df.iterrows():
            route_id = str(row["RouteId"])
            color = route_colors.get(route_id, "#3388ff")

            folium.CircleMarker(
                location=[row["Latitude"], row["Longitude"]],
                radius=4,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                popup=f"Route ID: {route_id}",
            ).add_to(m)

        add_route_legend(m, route_colors)

    if show_hulls:
        try:
            from scipy.spatial import ConvexHull

            route_colors = create_route_colors(map_df["RouteId"])

            for route_id, group in map_df.groupby("RouteId"):
                if len(group) >= 3:
                    points = group[["Latitude", "Longitude"]].values

                    try:
                        hull = ConvexHull(points)
                        hull_points = [points[i].tolist() for i in hull.vertices]
                        hull_points.append(hull_points[0])

                        folium.Polygon(
                            locations=hull_points,
                            color=route_colors.get(str(route_id), "#3388ff"),
                            weight=2,
                            fill=True,
                            fill_opacity=0.12,
                            popup=f"Route hull: {route_id}",
                        ).add_to(m)

                    except Exception:
                        continue

        except ImportError:
            st.warning("Convex hulls need scipy. Add scipy to requirements.txt if you want hull polygons.")

    return m


# =====================================================
# Main app
# =====================================================
if upload_1 is not None and upload_2 is not None:

    # =================================================
    # Load files
    # =================================================
    try:
        route_stats = read_csv_bytes(upload_1.getvalue())
        drops_stats = read_csv_bytes(upload_2.getvalue())
    except Exception as e:
        st.error(f"Could not read uploaded CSV files: {e}")
        route_stats = pd.DataFrame()
        drops_stats = pd.DataFrame()

    # =================================================
    # Historical data
    # =================================================
    try:
        hist_raw = load_historical_data(sheet_url)
        hist_df, hist_missing = clean_historical_data(hist_raw)

        if hist_missing:
            st.warning(f"Historical Google Sheet is missing these columns: {hist_missing}")
            hist_df = None

    except Exception as e:
        st.warning(f"Could not load historical data from Google Sheets: {e}")
        hist_df = None

    if hist_df is not None and not hist_df.empty:

        st.write("### 📈 Historical Data Stats")

        day_order = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        available_days = [
            day for day in day_order
            if day in hist_df["Day of Week"].dropna().unique()
        ]

        day_of_week = st.selectbox("Select Day of Week", available_days)

        dow_hist_df = hist_df[
            hist_df["Day of Week"] == day_of_week
        ].copy().reset_index(drop=True)

        if dow_hist_df.empty:
            st.warning(f"No historical data available for {day_of_week}.")
        else:
            display_df = build_day_stats(dow_hist_df)

            st.write(f"#### Cost Statistics for {day_of_week}")
            st.markdown(display_df.to_markdown(index=False))

            st.write("#### Data Visualizations")

            round_stats_df = build_round_stats(dow_hist_df)
            plot_round_stats(round_stats_df)

            st.write("#### Minimum Run cost Statistics for", day_of_week)
            st.dataframe(round_stats_df, use_container_width=True)

    # =================================================
    # Current route data
    # =================================================
    routes_metro = pd.DataFrame()

    if not route_stats.empty:

        routes_metro, need_to_be_refined, can_be_refined, good, table_df, route_missing = process_current_routes(route_stats)

        if route_missing:
            st.warning(f"Route Stats CSV is missing these columns: {route_missing}")

        elif routes_metro is None or routes_metro.empty:
            st.warning("No metro routes found in the current route file.")

        else:
            st.subheader("💰 Current Cost Table")

            current_cost_cols = [
                "zone",
                "routeClient",
                "vehicle",
                "rateZone",
                "drivingDistance",
                "drivingTime",
                "totalTime",
                "co2",
                "d1",
                "d2",
                "KM Cost",
                "No. of overloaded drops",
                "Drop Cost",
                "Flat Rate",
                "Total Cost",
                "Cost per Drop",
            ]

            st.dataframe(
                routes_metro[current_cost_cols],
                use_container_width=True,
            )

            st.subheader("📊 Route Client Classification Table")
            st.dataframe(
                style_classification_table(table_df),
                use_container_width=True,
            )

    # # =================================================
    # # Optimised map section
    # # =================================================
    # st.subheader("📍 Drops on Map")

    # if routes_metro is not None and not routes_metro.empty and not drops_stats.empty:

    #     drops_metro, map_missing = prepare_map_data(
    #         drops_stats,
    #         routes_metro["routeClient"].astype(str).tolist(),
    #     )

    #     if map_missing:
    #         st.warning(f"Drop Stats CSV is missing these columns: {map_missing}")

    #     elif drops_metro.empty:
    #         st.warning("No valid matching drops found for metro routes.")

    #     else:
    #         st.info(
    #             f"{len(drops_metro):,} valid matching drops are available for mapping. "
    #             "The map will only run when you click Generate map."
    #         )

    #         with st.form("map_controls"):
    #             map_mode = st.selectbox(
    #                 "Map mode",
    #                 [
    #                     "Fast clustered map",
    #                     "Coloured points by route",
    #                 ],
    #                 index=0,
    #                 help="Fast clustered map is recommended for large files. Coloured points by route is slower.",
    #             )

    #             max_points = st.slider(
    #                 "Maximum points to draw on map",
    #                 min_value=500,
    #                 max_value=50000,
    #                 value=10000,
    #                 step=500,
    #                 help="Lower this if the map is slow.",
    #             )

    #             show_hulls = st.checkbox(
    #                 "Show convex hulls by route",
    #                 value=False,
    #                 help="This can be slow for many routes. Leave off unless needed.",
    #             )

    #             generate_map = st.form_submit_button("Generate map")

    #         if generate_map:
    #             with st.spinner("Generating map. This can take longer for large files..."):
    #                 route_map = create_folium_map(
    #                     drops_metro=drops_metro,
    #                     map_mode=map_mode,
    #                     max_points=max_points,
    #                     show_hulls=show_hulls,
    #                 )

    #                 if route_map is not None:
    #                     folium_static(route_map, width=1200, height=700)

    #         else:
    #             st.caption("Map is not generated yet, so the tables and plots above load faster.")

    # else:
    #     st.warning("Map skipped because route or drop data is not available.")

else:
    st.info("Please upload both CSV files to start the analysis.")
