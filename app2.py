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
            return "background-color: red; color: white"
        elif column_name == "Can be refined":
            return "background-color: orange; color: white"
        elif column_name == "Good":
            return "background-color: lightgreen; color: black"
        return ""


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
