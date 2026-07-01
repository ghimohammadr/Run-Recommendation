# import streamlit as st
# import pandas as pd
# import numpy as np
# import folium
# import matplotlib.pyplot as plt
# from streamlit_folium import folium_static
# from branca.element import Element


# # =====================================================
# # Streamlit UI
# # =====================================================
# st.set_page_config(page_title="Route Recommendation Tool", layout="wide")
# st.title("File Upload and Analysis Tool")


# # =====================================================
# # Upload files
# # =====================================================
# upload_1 = st.file_uploader("Upload Route Stats CSV File", type=["csv"])
# upload_2 = st.file_uploader("Upload Drop Stats CSV File", type=["csv"])
# hist_file = st.file_uploader("Upload Historical Runs File Excel", type=["xlsx"])


# # =====================================================
# # Helper functions
# # =====================================================
# def check_columns(df, required_cols, file_name):
#     missing = [col for col in required_cols if col not in df.columns]
#     if missing:
#         st.warning(f"{file_name} is missing these columns: {missing}")
#         return False
#     return True


# def safe_numeric(series):
#     return pd.to_numeric(series, errors="coerce")


# def make_bar_plot(data, title, xlabel, ylabel):
#     fig, ax = plt.subplots(figsize=(8, 4))
#     ax.bar(data.index.astype(str), data.values)
#     ax.set_title(title)
#     ax.set_xlabel(xlabel)
#     ax.set_ylabel(ylabel)
#     plt.xticks(rotation=45, ha="right")
#     plt.tight_layout()
#     st.pyplot(fig)


# # =====================================================
# # Main app
# # =====================================================
# if upload_1 and upload_2 and hist_file:

#     # =================================================
#     # Read files
#     # =================================================
#     try:
#         route_stats = pd.read_csv(upload_1)
#         drops_stats = pd.read_csv(upload_2)
#         hist_df = pd.read_excel(hist_file)
#     except Exception as e:
#         st.error(f"Could not read one of the files: {e}")
#         route_stats = pd.DataFrame()
#         drops_stats = pd.DataFrame()
#         hist_df = pd.DataFrame()


#     # =================================================
#     # Historical data results
#     # =================================================
#     st.write("## Historical Data Results")

#     hist_required = ["Round", "Pln Finish Date", "Completed", "Planned Distance"]

#     if not hist_df.empty and check_columns(hist_df, hist_required, "Historical Runs File"):

#         try:
#             hist_df = hist_df.copy()

#             hist_df = hist_df.dropna(subset=["Round"]).reset_index(drop=True)

#             hist_df = hist_df[
#                 hist_df["Planned Distance"].astype(str).str.lower() != "nankm"
#             ].reset_index(drop=True)

#             completed_split = hist_df["Completed"].astype(str).str.split("/", expand=True)

#             hist_df["completed Drops"] = pd.to_numeric(completed_split[0], errors="coerce")

#             if completed_split.shape[1] > 1:
#                 hist_df["Total Drops"] = pd.to_numeric(completed_split[1], errors="coerce")
#             else:
#                 hist_df["Total Drops"] = np.nan

#             hist_df["distance"] = (
#                 hist_df["Planned Distance"]
#                 .astype(str)
#                 .str.replace("km", "", regex=False)
#                 .str.strip()
#             )

#             hist_df["distance"] = pd.to_numeric(hist_df["distance"], errors="coerce")

#             hist_df = hist_df.dropna(subset=["distance", "completed Drops"]).reset_index(drop=True)

#             if hist_df.empty:
#                 st.warning("Historical file has no valid rows after cleaning.")
#             else:
#                 hist_df["KM Cost"] = np.maximum((hist_df["distance"] - 200) * 1, 0)
#                 hist_df["Drop Cost"] = np.maximum((hist_df["completed Drops"] - 70) * 4.5, 0)

#                 st.write("### Historical Data Stats")

#                 col1, col2, col3 = st.columns(3)

#                 with col1:
#                     st.metric("No. of runs", len(hist_df.groupby(["Round", "Pln Finish Date"])))
#                     st.metric("No. of drops", int(hist_df["completed Drops"].sum()))

#                 with col2:
#                     st.metric("Max KM Bonus Cost", round(hist_df["KM Cost"].max(), 2))
#                     st.metric("Min KM Bonus Cost", round(hist_df["KM Cost"].min(), 2))
#                     st.metric("Avg KM Bonus Cost", round(hist_df["KM Cost"].mean(), 2))

#                 with col3:
#                     st.metric("Max Drop Bonus Cost", round(hist_df["Drop Cost"].max(), 2))
#                     st.metric("Min Drop Bonus Cost", round(hist_df["Drop Cost"].min(), 2))
#                     st.metric("Avg Drop Bonus Cost", round(hist_df["Drop Cost"].mean(), 2))

#                 st.write("### Historical Runs Table")
#                 st.dataframe(hist_df, use_container_width=True)

#                 st.write("### Historical Cost Plots")

#                 col_plot1, col_plot2 = st.columns(2)

#                 with col_plot1:
#                     fig1, ax1 = plt.subplots(figsize=(7, 4))
#                     ax1.hist(hist_df["KM Cost"].dropna(), bins=20)
#                     ax1.set_title("Historical KM Bonus Cost")
#                     ax1.set_xlabel("KM Cost")
#                     ax1.set_ylabel("Frequency")
#                     st.pyplot(fig1)

#                 with col_plot2:
#                     fig2, ax2 = plt.subplots(figsize=(7, 4))
#                     ax2.hist(hist_df["Drop Cost"].dropna(), bins=20)
#                     ax2.set_title("Historical Drop Bonus Cost")
#                     ax2.set_xlabel("Drop Cost")
#                     ax2.set_ylabel("Frequency")
#                     st.pyplot(fig2)

#         except Exception as e:
#             st.warning(f"Historical results could not be fully generated: {e}")


#     # =================================================
#     # Route results
#     # =================================================
#     st.write("## Route Results")

#     route_required = ["rateZone", "routeClient", "drivingDistance", "d2"]

#     routes_metro = pd.DataFrame()

#     if not route_stats.empty and check_columns(route_stats, route_required, "Route Stats CSV"):

#         try:
#             route_stats = route_stats.copy()

#             route_stats["rateZone"] = route_stats["rateZone"].astype(str).str.strip()
#             route_stats["routeClient"] = route_stats["routeClient"].astype(str).str.strip()
#             route_stats["drivingDistance"] = safe_numeric(route_stats["drivingDistance"])
#             route_stats["d2"] = safe_numeric(route_stats["d2"])

#             routes_metro = route_stats[
#                 route_stats["rateZone"] == "Melbourne Metro"
#             ].copy().reset_index(drop=True)

#             if routes_metro.empty:
#                 st.warning("No routes found where rateZone = Melbourne Metro.")
#             else:
#                 routes_metro = routes_metro.dropna(
#                     subset=["routeClient", "drivingDistance", "d2"]
#                 ).reset_index(drop=True)

#                 routes_metro["distance_km"] = routes_metro["drivingDistance"] / 1000

#                 routes_metro["KM Cost"] = np.maximum((routes_metro["distance_km"] - 200) * 1, 0)
#                 routes_metro["No. of overloaded drops"] = np.maximum(routes_metro["d2"] - 70, 0)
#                 routes_metro["Drop Cost"] = np.maximum((routes_metro["d2"] - 70) * 4.5, 0)
#                 routes_metro["Flat Rate"] = 350
#                 routes_metro["Total Cost"] = (
#                     routes_metro["KM Cost"] +
#                     routes_metro["Drop Cost"] +
#                     routes_metro["Flat Rate"]
#                 )

#                 # Classification
#                 need_to_be_refined = routes_metro[
#                     (routes_metro["d2"] < 70) &
#                     (routes_metro["distance_km"] > 200)
#                 ]["routeClient"].astype(str).tolist()

#                 good = routes_metro[
#                     (routes_metro["d2"] >= 70) &
#                     (routes_metro["distance_km"] <= 200)
#                 ]["routeClient"].astype(str).tolist()

#                 all_routes = set(routes_metro["routeClient"].astype(str))
#                 can_be_refined = sorted(
#                     list(all_routes - set(need_to_be_refined) - set(good))
#                 )

#                 # Classification table
#                 max_length = max(
#                     len(need_to_be_refined),
#                     len(can_be_refined),
#                     len(good),
#                     1
#                 )

#                 table_data = {
#                     "Need to be refined": need_to_be_refined + [""] * (max_length - len(need_to_be_refined)),
#                     "Can be refined": can_be_refined + [""] * (max_length - len(can_be_refined)),
#                     "Good": good + [""] * (max_length - len(good))
#                 }

#                 table_df = pd.DataFrame(table_data)

#                 styled_df = (
#                     table_df.style
#                     .set_properties(
#                         subset=["Need to be refined"],
#                         **{"background-color": "red", "color": "white"}
#                     )
#                     .set_properties(
#                         subset=["Can be refined"],
#                         **{"background-color": "orange", "color": "white"}
#                     )
#                     .set_properties(
#                         subset=["Good"],
#                         **{"background-color": "lightgreen", "color": "black"}
#                     )
#                 )

#                 st.subheader("📊 Route Client Classification Table")
#                 st.dataframe(styled_df, use_container_width=True)

#                 # Metrics
#                 col1, col2, col3, col4 = st.columns(4)

#                 with col1:
#                     st.metric("Metro routes", len(routes_metro))

#                 with col2:
#                     st.metric("Need to be refined", len(need_to_be_refined))

#                 with col3:
#                     st.metric("Can be refined", len(can_be_refined))

#                 with col4:
#                     st.metric("Good", len(good))

#                 # Route cost table
#                 st.subheader("Route Cost Summary Table")

#                 summary_cols = [
#                     "routeClient",
#                     "d2",
#                     "distance_km",
#                     "KM Cost",
#                     "Drop Cost",
#                     "Flat Rate",
#                     "Total Cost",
#                     "No. of overloaded drops"
#                 ]

#                 st.dataframe(routes_metro[summary_cols], use_container_width=True)

#                 # Plots
#                 st.subheader("📈 Route Plots")

#                 classification_counts = pd.Series({
#                     "Need to be refined": len(need_to_be_refined),
#                     "Can be refined": len(can_be_refined),
#                     "Good": len(good)
#                 })

#                 make_bar_plot(
#                     classification_counts,
#                     "Route Classification Counts",
#                     "Classification",
#                     "Number of Routes"
#                 )

#                 top_cost_routes = (
#                     routes_metro
#                     .sort_values("Total Cost", ascending=False)
#                     .set_index("routeClient")["Total Cost"]
#                     .head(20)
#                 )

#                 make_bar_plot(
#                     top_cost_routes,
#                     "Top 20 Routes by Total Cost",
#                     "Route Client",
#                     "Total Cost"
#                 )

#         except Exception as e:
#             st.warning(f"Route results could not be fully generated: {e}")


#     # =================================================
#     # Map results
#     # =================================================
#     st.write("## Runs on Map")

#     drop_required = ["RouteId", "Latitude", "Longitude"]

#     if not drops_stats.empty and not routes_metro.empty and check_columns(drops_stats, drop_required, "Drop Stats CSV"):

#         try:
#             drops_stats = drops_stats.copy()

#             drops_stats["RouteId"] = drops_stats["RouteId"].astype(str).str.strip()
#             drops_stats["Latitude"] = pd.to_numeric(drops_stats["Latitude"], errors="coerce")
#             drops_stats["Longitude"] = pd.to_numeric(drops_stats["Longitude"], errors="coerce")

#             drops_metro = drops_stats[
#                 drops_stats["RouteId"].isin(routes_metro["routeClient"].astype(str))
#             ].copy().reset_index(drop=True)

#             drops_metro_valid = drops_metro.dropna(
#                 subset=["Latitude", "Longitude"]
#             ).reset_index(drop=True)

#             if drops_metro.empty:
#                 st.warning("No matching drops found for Melbourne Metro routes.")
#             elif drops_metro_valid.empty:
#                 st.warning("Matching drops were found, but none had valid Latitude/Longitude.")
#             else:
#                 route_ids = sorted(drops_metro_valid["RouteId"].unique())
#                 num_routes = len(route_ids)

#                 colors = plt.cm.gist_ncar(np.linspace(0, 1, max(num_routes, 1)))

#                 route_colors = {
#                     route: f"#{int(c[0] * 255):02x}{int(c[1] * 255):02x}{int(c[2] * 255):02x}"
#                     for route, c in zip(route_ids, colors)
#                 }

#                 # Create Folium map
#                 m = folium.Map(
#                     location=[
#                         drops_metro_valid["Latitude"].mean(),
#                         drops_metro_valid["Longitude"].mean()
#                     ],
#                     zoom_start=12
#                 )

#                 # Add points
#                 for _, row in drops_metro_valid.iterrows():
#                     route_id = row["RouteId"]
#                     color = route_colors.get(route_id, "#3388ff")

#                     folium.CircleMarker(
#                         location=[row["Latitude"], row["Longitude"]],
#                         radius=5,
#                         color=color,
#                         fill=True,
#                         fill_color=color,
#                         fill_opacity=0.7,
#                         popup=f"Route ID: {route_id}"
#                     ).add_to(m)

#                 # Legend
#                 legend_html = """
#                 <div style="position: fixed;
#                             bottom: 50px;
#                             left: 50px;
#                             max-height: 300px;
#                             overflow-y: auto;
#                             background-color: white;
#                             z-index: 9999;
#                             padding: 10px;
#                             font-size: 14px;
#                             border-radius: 5px;
#                             box-shadow: 0px 0px 5px gray;">
#                     <b>Route ID Legend</b><br>
#                 """

#                 for route, color in route_colors.items():
#                     legend_html += f"""
#                     <div style="display: flex; align-items: center; padding: 2px;">
#                         <div style="width: 12px; height: 12px; background: {color}; margin-right: 5px;"></div>
#                         <span>{route}</span>
#                     </div>
#                     """

#                 legend_html += "</div>"

#                 m.get_root().html.add_child(Element(legend_html))

#                 folium_static(m, width=1200, height=700)

#         except Exception as e:
#             st.warning(f"Map could not be generated: {e}")

#     else:
#         st.warning("Map was skipped because route or drop data was not available.")


import streamlit as st
import pandas as pd
import numpy as np
import folium
import matplotlib.pyplot as plt
from streamlit_folium import folium_static
# from branca.element import Template, MacroElement
from branca.element import Element, Html


# Streamlit UI
st.title("File Upload and Analysis Tool")

# Upload files
upload_1 = st.file_uploader("Upload Route Stats CSV File", type=["csv"])
upload_2 = st.file_uploader("Upload Drop Stats CSV File", type=["csv"])
hist_file = st.file_uploader("Upload Historical Runs File (Excel)", type=["xlsx"])

if upload_1 and upload_2 and hist_file:
    # Read historical runs file
    hist_df = pd.read_excel(hist_file)
    hist_df = hist_df.dropna(subset=['Round']).reset_index(drop=True)
    hist_df = hist_df[hist_df['Planned Distance'] != 'NaNkm'].reset_index(drop=True)
    hist_df[['completed Drops', 'Total Drops']] = hist_df['Completed'].str.split('/', expand=True).apply(pd.to_numeric)
    hist_df['distance'] = hist_df['Planned Distance'].str.replace('km', '', regex=True).astype(int)
    hist_df['KM Cost'] = np.maximum((hist_df['distance'] - 200) * 1, 0)
    hist_df['Drop Cost'] = np.maximum((hist_df['completed Drops'] - 70) * 4.5, 0)
    
    st.write("### Historical Data Stats")
    st.write(f"No. of runs: {len(hist_df.groupby(['Round', 'Pln Finish Date']).count())}")
    st.write(f"No. of drops: {int(hist_df['completed Drops'].sum())}")
    st.write(f"Max Km Bonus cost: {hist_df['KM Cost'].max()}")
    st.write(f"Min Km Bonus cost: {hist_df['KM Cost'].min()}")
    st.write(f"Avg Km Bonus cost: {round(hist_df['KM Cost'].mean(), 2)}")
    st.write(f"Max Drop Bonus cost: {hist_df['Drop Cost'].max()}")
    st.write(f"Min Drop Bonus cost: {hist_df['Drop Cost'].min()}")
    st.write(f"Avg Drop Bonus cost: {round(hist_df['Drop Cost'].mean(), 2)}")
    
    # Read uploaded CSVs
    route_stats = pd.read_csv(upload_1)
    drops_stats = pd.read_csv(upload_2)
    
    routes_metro = route_stats[route_stats['rateZone'] == 'Melbourne Metro'].reset_index(drop=True)
    drops_metro = drops_stats[drops_stats['RouteId'].isin(routes_metro['routeClient'].values.tolist())].reset_index(drop=True)
    
    routes_metro['KM Cost'] = np.maximum((routes_metro['drivingDistance'] / 1000 - 200) * 1, 0)
    routes_metro['No. of overloaded drops'] = np.maximum(routes_metro['d2'] - 70, 0)
    routes_metro['Drop Cost'] = np.maximum((routes_metro['d2'] - 70) * 4.5, 0)
    routes_metro['Flat Rate'] = 350
    routes_metro['Total Cost'] = routes_metro['KM Cost'] + routes_metro['Drop Cost'] + routes_metro['Flat Rate']
    
    # if len(routes_metro[routes_metro['No. of overloaded drops'] <= 0]) > 0:
    #     st.write("Routes with capacity:", routes_metro[routes_metro['No. of overloaded drops'] <= 0][['routeClient', 'No. of overloaded drops']])
    

    # Define categories based on conditions
    need_to_be_refined = routes_metro[(routes_metro['d2'] < 70) & (routes_metro['drivingDistance']/1000 > 200)]['routeClient'].values.tolist()
    good = routes_metro[(routes_metro['d2'] >= 70) & (routes_metro['drivingDistance']/1000 < 200)]['routeClient'].values.tolist()
    # can_be_refined = routes_metro[(routes_metro['d2'] < 70) | (routes_metro['drivingDistance']/1000 > 200)]['routeClient'].values.tolist()

    # Define 'Can be refined' as those that are neither in 'Need to be refined' nor in 'Good'
    all_routes = set(routes_metro['routeClient'])
    can_be_refined = list(all_routes - set(need_to_be_refined) - set(good))

    # Create a DataFrame for display
    max_length = max(len(need_to_be_refined), len(can_be_refined), len(good))
    table_data = {
        "Need to be refined": need_to_be_refined + [''] * (max_length - len(need_to_be_refined)),
        "Can be refined": can_be_refined + [''] * (max_length - len(can_be_refined)),
        "Good": good + [''] * (max_length - len(good))
    }
    table_df = pd.DataFrame(table_data)

    # Apply Styling with Colors
    def highlight_table(val, column_name):
        """Apply background color based on column category."""
        if column_name == "Need to be refined":
            return 'background-color: red; color: white'
        elif column_name == "Can be refined":
            return 'background-color: orange; color: white'
        elif column_name == "Good":
            return 'background-color: lightgreen; color: black'
        return ''

    # Apply the style to the DataFrame
    styled_df = table_df.style.map(lambda val: highlight_table(val, "Need to be refined"), subset=["Need to be refined"]) \
                            .map(lambda val: highlight_table(val, "Can be refined"), subset=["Can be refined"]) \
                            .map(lambda val: highlight_table(val, "Good"), subset=["Good"])

    # Display the table in Streamlit
    st.subheader("📊 Route Client Classification Table")
    st.dataframe(styled_df)



    # st.write("### Runs on Map")

    # Generate unique colors for routes
    route_ids = sorted(drops_metro['RouteId'].unique())
    num_routes = len(route_ids)
    colors = plt.cm.gist_ncar(np.linspace(0, 1, num_routes))
    route_colors = {route: f'#{int(c[0]*255):02x}{int(c[1]*255):02x}{int(c[2]*255):02x}' for route, c in zip(route_ids, colors)}
    



    # Create a Folium map
    m = folium.Map(location=[drops_metro['Latitude'].mean(), drops_metro['Longitude'].mean()], zoom_start=12)

    # Add points with unique colors
    for _, row in drops_metro.iterrows():
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=5,
            color=route_colors[row['RouteId']],
            fill=True,
            fill_color=route_colors[row['RouteId']],
            fill_opacity=0.7,
            popup=f"Route ID: {row['RouteId']}"
        ).add_to(m)

    # Create legend HTML
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: auto; height: auto; 
                overflow-y: auto; background-color: white; z-index:9999; 
                padding: 10px; font-size:14px; border-radius:5px; 
                box-shadow: 0px 0px 5px gray;">
        <b>Route ID Legend</b><br>
    '''
    for route, color in route_colors.items():
        legend_html += f'<div style="display: flex; align-items: center; padding: 2px;">'
        legend_html += f'<div style="width: 12px; height: 12px; background: {color}; margin-right: 5px;"></div>'
        legend_html += f'<span>{route}</span></div>'

    legend_html += '</div>'

    # Add legend as HTML element to map
    legend = Element(legend_html)
    m.get_root().html.add_child(legend)

    # Display the map in Streamlit
    folium_static(m)

# else:
#     st.info("Please upload all three files to start the analysis.")
