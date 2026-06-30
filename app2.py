import streamlit as st
import pandas as pd
import numpy as np
import folium
import matplotlib.pyplot as plt
from streamlit_folium import folium_static
from branca.element import Element


# =====================================================
# Page setup
# =====================================================
st.set_page_config(page_title="Route Recommendation Tool", layout="wide")
st.title("File Upload and Analysis Tool")


# =====================================================
# Helper functions
# =====================================================
def has_required_columns(df, required_cols, file_name):
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        st.warning(f"{file_name} is missing these columns: {missing}")
        return False
    return True


def safe_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def clean_historical_data(hist_df):
    hist_df = hist_df.copy()

    required_cols = ["Round", "Pln Finish Date", "Completed", "Planned Distance"]
    if not has_required_columns(hist_df, required_cols, "Historical Runs File"):
        return None

    hist_df = hist_df.dropna(subset=["Round"]).reset_index(drop=True)

    completed_split = hist_df["Completed"].astype(str).str.split("/", expand=True)

    hist_df["completed Drops"] = pd.to_numeric(completed_split[0], errors="coerce")

    if completed_split.shape[1] > 1:
        hist_df["Total Drops"] = pd.to_numeric(completed_split[1], errors="coerce")
    else:
        hist_df["Total Drops"] = np.nan

    hist_df["distance"] = (
        hist_df["Planned Distance"]
        .astype(str)
        .str.replace("km", "", regex=False)
        .str.strip()
    )

    hist_df["distance"] = pd.to_numeric(hist_df["distance"], errors="coerce")

    hist_df = hist_df.dropna(subset=["distance", "completed Drops"]).reset_index(drop=True)

    if hist_df.empty:
        st.warning("Historical file was loaded, but no valid rows were found after cleaning.")
        return None

    hist_df["KM Cost"] = np.maximum((hist_df["distance"] - 200) * 1, 0)
    hist_df["Drop Cost"] = np.maximum((hist_df["completed Drops"] - 70) * 4.5, 0)

    return hist_df


def show_historical_stats(hist_df):
    st.write("### Historical Data Stats")

    col1, col2, col3 = st.columns(3)

    with col1:
        no_runs = len(hist_df.groupby(["Round", "Pln Finish Date"]))
        st.metric("No. of runs", no_runs)
        st.metric("No. of drops", int(hist_df["completed Drops"].sum()))

    with col2:
        st.metric("Max KM Bonus Cost", round(hist_df["KM Cost"].max(), 2))
        st.metric("Min KM Bonus Cost", round(hist_df["KM Cost"].min(), 2))
        st.metric("Avg KM Bonus Cost", round(hist_df["KM Cost"].mean(), 2))

    with col3:
        st.metric("Max Drop Bonus Cost", round(hist_df["Drop Cost"].max(), 2))
        st.metric("Min Drop Bonus Cost", round(hist_df["Drop Cost"].min(), 2))
        st.metric("Avg Drop Bonus Cost", round(hist_df["Drop Cost"].mean(), 2))


def classify_routes(routes_df):
    routes_df = routes_df.copy()

    routes_df["drivingDistance"] = safe_numeric(routes_df["drivingDistance"])
    routes_df["d2"] = safe_numeric(routes_df["d2"])

    routes_df = routes_df.dropna(subset=["drivingDistance", "d2"]).reset_index(drop=True)

    if routes_df.empty:
        st.warning("Route file was loaded, but no valid route rows were found after cleaning.")
        return None, [], [], []

    routes_df["distance_km"] = routes_df["drivingDistance"] / 1000

    routes_df["KM Cost"] = np.maximum((routes_df["distance_km"] - 200) * 1, 0)
    routes_df["No. of overloaded drops"] = np.maximum(routes_df["d2"] - 70, 0)
    routes_df["Drop Cost"] = np.maximum((routes_df["d2"] - 70) * 4.5, 0)
    routes_df["Flat Rate"] = 350
    routes_df["Total Cost"] = (
        routes_df["KM Cost"] +
        routes_df["Drop Cost"] +
        routes_df["Flat Rate"]
    )

    need_to_be_refined = routes_df[
        (routes_df["d2"] < 70) &
        (routes_df["distance_km"] > 200)
    ]["routeClient"].astype(str).tolist()

    good = routes_df[
        (routes_df["d2"] >= 70) &
        (routes_df["distance_km"] <= 200)
    ]["routeClient"].astype(str).tolist()

    all_routes = set(routes_df["routeClient"].astype(str))
    can_be_refined = sorted(
        list(all_routes - set(need_to_be_refined) - set(good)),
        key=str
    )

    return routes_df, need_to_be_refined, can_be_refined, good


def create_classification_table(need_to_be_refined, can_be_refined, good):
    max_length = max(
        len(need_to_be_refined),
        len(can_be_refined),
        len(good),
        1
    )

    table_df = pd.DataFrame({
        "Need to be refined": need_to_be_refined + [""] * (max_length - len(need_to_be_refined)),
        "Can be refined": can_be_refined + [""] * (max_length - len(can_be_refined)),
        "Good": good + [""] * (max_length - len(good)),
    })

    styled_df = (
        table_df.style
        .set_properties(
            subset=["Need to be refined"],
            **{"background-color": "red", "color": "white"}
        )
        .set_properties(
            subset=["Can be refined"],
            **{"background-color": "orange", "color": "white"}
        )
        .set_properties(
            subset=["Good"],
            **{"background-color": "lightgreen", "color": "black"}
        )
    )

    return styled_df


def create_route_map(drops_metro):
    drops_metro = drops_metro.copy()

    if not has_required_columns(
        drops_metro,
        ["RouteId", "Latitude", "Longitude"],
        "Drop Stats CSV"
    ):
        return None

    drops_metro["Latitude"] = pd.to_numeric(drops_metro["Latitude"], errors="coerce")
    drops_metro["Longitude"] = pd.to_numeric(drops_metro["Longitude"], errors="coerce")

    drops_metro = drops_metro.dropna(subset=["Latitude", "Longitude"]).reset_index(drop=True)

    if drops_metro.empty:
        st.warning("No valid latitude/longitude values found for the map.")
        return None

    route_ids = sorted(drops_metro["RouteId"].dropna().astype(str).unique(), key=str)
    num_routes = len(route_ids)

    colors = plt.cm.gist_ncar(np.linspace(0, 1, max(num_routes, 1)))

    route_colors = {
        route: f"#{int(c[0] * 255):02x}{int(c[1] * 255):02x}{int(c[2] * 255):02x}"
        for route, c in zip(route_ids, colors)
    }

    map_center = [
        drops_metro["Latitude"].mean(),
        drops_metro["Longitude"].mean()
    ]

    m = folium.Map(location=map_center, zoom_start=12)

    for _, row in drops_metro.iterrows():
        route_id = str(row["RouteId"])
        color = route_colors.get(route_id, "#3388ff")

        folium.CircleMarker(
            location=[row["Latitude"], row["Longitude"]],
            radius=5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=f"Route ID: {route_id}"
        ).add_to(m)

    legend_html = """
    <div style="
        position: fixed;
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

    for route, color in route_colors.items():
        legend_html += f"""
        <div style="display: flex; align-items: center; padding: 2px;">
            <div style="width: 12px; height: 12px; background: {color}; margin-right: 5px;"></div>
            <span>{route}</span>
        </div>
        """

    legend_html += "</div>"

    m.get_root().html.add_child(Element(legend_html))

    return m


# =====================================================
# Upload files
# =====================================================
upload_1 = st.file_uploader("Upload Route Stats CSV File", type=["csv"])
upload_2 = st.file_uploader("Upload Drop Stats CSV File", type=["csv"])
hist_file = st.file_uploader("Upload Historical Runs File Excel", type=["xlsx"])


# =====================================================
# Main app
# =====================================================
if upload_1 is not None and upload_2 is not None and hist_file is not None:

    try:
        route_stats = pd.read_csv(upload_1)
        drops_stats = pd.read_csv(upload_2)
        hist_raw = pd.read_excel(hist_file)
    except Exception as e:
        st.error(f"Could not read one of the uploaded files: {e}")
        route_stats = None
        drops_stats = None
        hist_raw = None

    # =================================================
    # Historical results
    # =================================================
    if hist_raw is not None:
        hist_df = clean_historical_data(hist_raw)

        if hist_df is not None:
            show_historical_stats(hist_df)

            with st.expander("View cleaned historical data"):
                st.dataframe(hist_df, use_container_width=True)

    # =================================================
    # Route results
    # =================================================
    routes_metro = None
    drops_metro = None

    if route_stats is not None:
        route_required_cols = ["rateZone", "routeClient", "drivingDistance", "d2"]

        if has_required_columns(route_stats, route_required_cols, "Route Stats CSV"):

            routes_metro = route_stats[
                route_stats["rateZone"].astype(str).str.strip() == "Melbourne Metro"
            ].copy().reset_index(drop=True)

            if routes_metro.empty:
                st.warning("No routes found where rateZone = Melbourne Metro.")
            else:
                routes_metro, need_to_be_refined, can_be_refined, good = classify_routes(routes_metro)

                if routes_metro is not None:
                    st.subheader("📊 Route Client Classification Table")

                    styled_df = create_classification_table(
                        need_to_be_refined,
                        can_be_refined,
                        good
                    )

                    st.dataframe(styled_df, use_container_width=True)

                    st.subheader("Route Cost Summary")

                    summary_cols = [
                        "routeClient",
                        "d2",
                        "distance_km",
                        "KM Cost",
                        "Drop Cost",
                        "Flat Rate",
                        "Total Cost",
                        "No. of overloaded drops"
                    ]

                    st.dataframe(
                        routes_metro[summary_cols],
                        use_container_width=True
                    )

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Metro routes", len(routes_metro))

                    with col2:
                        st.metric("Need to be refined", len(need_to_be_refined))

                    with col3:
                        st.metric("Can be refined", len(can_be_refined))

                    with col4:
                        st.metric("Good", len(good))

    # =================================================
    # Map results
    # =================================================
    if drops_stats is not None and routes_metro is not None and not routes_metro.empty:

        if has_required_columns(drops_stats, ["RouteId", "Latitude", "Longitude"], "Drop Stats CSV"):

            drops_metro = drops_stats[
                drops_stats["RouteId"].astype(str).isin(routes_metro["routeClient"].astype(str))
            ].copy().reset_index(drop=True)

            st.subheader("🗺️ Runs on Map")

            if drops_metro.empty:
                st.warning("No matching drops found for the Melbourne Metro routes. Route results are still shown above.")
            else:
                route_map = create_route_map(drops_metro)

                if route_map is not None:
                    folium_static(route_map, width=1200, height=700)
                else:
                    st.warning("Map could not be created, but the tables above are still available.")

else:
    st.info("Please upload all three files to start the analysis.")
