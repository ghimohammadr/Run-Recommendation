import streamlit as st
import pandas as pd
import numpy as np
import folium
import matplotlib.pyplot as plt
from streamlit_folium import folium_static
from io import BytesIO
import requests
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.spatial import ConvexHull



from keplergl import KeplerGl
import json


# Streamlit UI
st.title("File Upload and Analysis Tool")

# Upload files
upload_1 = st.file_uploader("Upload Route Stats CSV File", type=["csv"])
upload_2 = st.file_uploader("Upload Drop Stats CSV File", type=["csv"])

# URL of the Google Sheets Excel file
sheet_url = 'https://docs.google.com/spreadsheets/d/1rw7xX_Mk81a-9n5ke1WsY2drWBXX_8Qu/export?format=xlsx'
# sheet_url = 'https://docs.google.com/spreadsheets/d/1rw7xX_Mk81a-9n5ke1WsY2drWBXX_8Qu/edit?usp=sharing&ouid=113938111125227520877&rtpof=true&sd=true'


if upload_1 and upload_2:
    # Read historical runs file from Google Sheets
    @st.cache_data
    def load_historical_data(url):
        response = requests.get(url)
        response.raise_for_status()  # Ensure we notice bad responses
        return pd.read_excel(BytesIO(response.content))

    hist_df = load_historical_data(sheet_url)
    
    # Data cleaning and processing
    hist_df = hist_df.dropna(subset=['Round']).reset_index(drop=True)
    hist_df = hist_df[hist_df['Planned Distance'] != 'NaNkm'].reset_index(drop=True)
    hist_df[['completed Drops', 'Total Drops']] = hist_df['Completed'].str.split('/', expand=True).apply(pd.to_numeric)
    hist_df = hist_df[hist_df['completed Drops'] != 0].reset_index()
    hist_df = hist_df[~hist_df['completed Drops'].isna()].reset_index()
    hist_df['distance'] = hist_df['Planned Distance'].str.replace('km', '', regex=True).astype(int)
    hist_df['KM Cost'] = np.maximum((hist_df['distance'] - 200) * 1, 0)
    hist_df['Drop Cost'] = np.maximum((hist_df['completed Drops'] - 70) * 4.5, 0)

    # Ensure the column is in datetime format
    hist_df['Pln Start Date'] = pd.to_datetime(hist_df['Pln Start Date'], errors='coerce')

    # Create a new column for the day of the week
    hist_df['Day of Week'] = hist_df['Pln Start Date'].dt.day_name()

    hist_df['Flat rate Cost'] = 370
    hist_df['Total Cost'] = hist_df['KM Cost'] + hist_df['Drop Cost']+ hist_df['Flat rate Cost']
    hist_df['Cost per Drop'] = hist_df['Total Cost']/hist_df['completed Drops']
    # Display historical data stats
    st.write("### 📈 Historical Data Stats")

    # Dropdown menu for selecting the day of the week
    day_of_week = st.selectbox("Select Day of Week", hist_df['Day of Week'].unique())

    # Filter data based on selection
    dow_hist_df = hist_df[hist_df['Day of Week'] == day_of_week]

    round_list_am = []
    round_list_pm = []


    for date in dow_hist_df['Pln Start Date'].unique():
        for slot in dow_hist_df['Slot'].unique():
            if slot == 'AM':
                round_list_am.append(len(dow_hist_df[(dow_hist_df['Pln Start Date'] == date) & (dow_hist_df['Slot'] == slot)]['Round'].unique()))
            if slot == 'PM':
                round_list_pm.append(len(dow_hist_df[(dow_hist_df['Pln Start Date'] == date) & (dow_hist_df['Slot'] == slot)]['Round'].unique()))

    dict_dow = {
        'Total No. of runs': len(dow_hist_df.groupby(['Round', 'Pln Finish Date']).count()),
        'Min No. of runs': min(dow_hist_df.groupby('Pln Start Date')['Round'].nunique().tolist()),
        'Max No. of runs':max(dow_hist_df.groupby('Pln Start Date')['Round'].nunique().tolist()),

        'Averge No. of AM runs': round(np.mean(round_list_am) if round_list_am else 0, 2),
        'Min No. of AM runs': min(round_list_am) if round_list_am else 0,
        'Max No. of AM runs': max(round_list_am) if round_list_am else 0,

        'Averge No. of PM runs': round(np.mean(round_list_pm) if round_list_pm else 0, 2),
        'Min No. of PM runs': min(round_list_pm) if round_list_pm else 0,
        'Max No. of PM runs': max(round_list_pm) if round_list_pm else 0,

        # 'No. of drops': int(dow_hist_df['completed Drops'].sum()),

        'Total No. of Drops' : int(dow_hist_df['completed Drops'].sum()),
        'Min No. of Drops' : dow_hist_df['completed Drops'].min(),
        'Max No. of Drops' : dow_hist_df['completed Drops'].max(),

        'Max Km Bonus Cost': dow_hist_df['KM Cost'].max(),
        'Avg Km Bonus Cost': round(dow_hist_df['KM Cost'].mean(), 2),
        'Max Drop Bonus Cost': dow_hist_df['Drop Cost'].max(),
        'Avg Drop Bonus Cost': round(dow_hist_df['Drop Cost'].mean(), 2),
        # 'Total Cost (× 10 ^3 )': round(dow_hist_df['Total Cost'].sum()/1000, 2),
        'Total Cost': round(dow_hist_df['Total Cost'].sum(), 2),
        'Max Cost per Drop': round(dow_hist_df['Cost per Drop'].max(), 2),
        'Avg Cost per Drop': round(dow_hist_df['Cost per Drop'].mean(), 2),
        'Min Cost per Drop': round(dow_hist_df['Cost per Drop'].min(), 2)
    }

    # Convert to DataFrame
    stats_table_df = pd.DataFrame(dict_dow, index=[0]).T.reset_index()
    stats_table_df.columns = ['Metric', 'Value']

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Split dataframe into two halves
    mid_index = len(stats_table_df) // 2
    stats_table_df1 = stats_table_df.iloc[:mid_index]
    stats_table_df2 = stats_table_df.iloc[mid_index:].reset_index(drop=True)

    # Rename columns for two-column display
    stats_table_df1.columns = ['Metric 1', 'Value 1']
    stats_table_df2.columns = ['Metric 2', 'Value 2']

    # Concatenate side-by-side
    display_df = pd.concat([stats_table_df1, stats_table_df2], axis=1)

    # Convert metrics to bold using Markdown syntax
    display_df['Metric 1'] = display_df['Metric 1'].apply(lambda x: f"**{x}**" if pd.notnull(x) else x)
    display_df['Metric 2'] = display_df['Metric 2'].apply(lambda x: f"**{x}**" if pd.notnull(x) else x)


    # Display table in Streamlit
    st.write(f"#### Cost Statistics for {day_of_week}")
    st.write(display_df.to_markdown(index=False), unsafe_allow_html=True)

    # # Display table in Streamlit
    # st.write("#### Cost Statistics for", day_of_week)
    # st.dataframe(display_df)

    # Visualization
    # Compute minimum cost per drop, associated number of drops, and total driving distance per round
    rounds = list(dow_hist_df['Round'].unique())
    min_cost_per_drop = []
    associated_drops = []
    total_driving_distance = []

    for rnd in rounds:
        round_df = dow_hist_df[dow_hist_df['Round'] == rnd]
        min_cost_per_drop.append(round_df['Cost per Drop'].min())
        associated_drops.append(round_df.loc[round_df['Cost per Drop'].idxmin(), 'completed Drops'])
        total_driving_distance.append(round_df.loc[round_df['Cost per Drop'].idxmin(), 'distance'])

    rounds = [str(int(i)) for i in rounds]
    # Create DataFrame for visualization

    round_stats_df = pd.DataFrame({
        'Round': rounds,
        'Min Cost per Drop': min_cost_per_drop,
        'Associated Drops': associated_drops,
        'Total Driving Distance': total_driving_distance
    })



    # Interactive visualization
    # Interactive visualization
    # Interactive visualization with bar plots, custom colors, and x-grid lines
    st.write("#### Data Visualizations")

    # fig1 = px.bar(round_stats_df, x='Round', y='Min Cost per Drop', color='Min Cost per Drop', 
    #             title="Minimum Cost per Drop per Round", color_continuous_scale='Blues')
    # fig1.update_xaxes(type='category', tickangle=-45, showgrid=True)
    # st.plotly_chart(fig1)

    # fig2 = px.bar(round_stats_df, x='Round', y='Associated Drops', color='Associated Drops', 
    #             title="Associated Drops per Round", color_continuous_scale='Greens')
    # fig2.update_xaxes(type='category', tickangle=-45, showgrid=True)
    # st.plotly_chart(fig2)

    # fig3 = px.bar(round_stats_df, x='Round', y='Total Driving Distance', color='Total Driving Distance', 
    #             title="Total Driving Distance per Round", color_continuous_scale='Reds')
    # fig3.update_xaxes(type='category', tickangle=-45, showgrid=True)
    # st.plotly_chart(fig3)

    # Create figure with secondary y-axis

# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # # Create figure with secondary y-axis
    # fig = make_subplots(specs=[[{"secondary_y": True}]])

    # # Bar plot for 'Min Cost per Drop' (left y-axis)
    # fig.add_trace(
    #     go.Bar(
    #         x=round_stats_df['Round'],
    #         y=round_stats_df['Min Cost per Drop'],
    #         marker=dict(color=round_stats_df['Total Driving Distance'], coloraxis="coloraxis"),
    #         name="Min Cost per Drop",
    #         hovertemplate=
    #         "<b>Round:</b> %{x}<br>" +
    #         "<b>Min Cost per Drop:</b> %{y:.2f}<br>" +
    #         "<b>Total Driving Distance:</b> %{marker.color:.2f}<br>" +
    #         "<extra></extra>"
    #     ),
    #     secondary_y=False,
    # )

    # # Line plot for 'Associated Drops' (right y-axis)
    # fig.add_trace(
    #     go.Scatter(
    #         x=round_stats_df['Round'],
    #         y=round_stats_df['Associated Drops'],
    #         mode='lines+markers',
    #         line=dict(color='black'),
    #         name="Associated Drops",
    #         hovertemplate=
    #         "<b>Round:</b> %{x}<br>" +
    #         "<b>Associated Drops:</b> %{y}<br>" +
    #         "<b>Min Cost per Drop:</b> %{customdata[0]:.2f}<br>" +
    #         "<b>Total Driving Distance:</b> %{customdata[1]:.2f}<br>" +
    #         "<extra></extra>",
    #         customdata=list(zip(round_stats_df['Min Cost per Drop'], round_stats_df['Total Driving Distance']))
    #     ),
    #     secondary_y=True,
    # )

    # # Update layout
    # fig.update_layout(
    #     # title_text="Min Cost per Drop & Associated Drops per Round",
    #     # template="plotly_white",  # Light theme
    #     xaxis=dict(title="Round", type='category', tickangle=-45),
    #     yaxis=dict(title="Min Cost per Drop", showgrid=True),
    #     yaxis2=dict(title="Associated Drops", overlaying='y', side='right'),
    #     coloraxis=dict(colorbar_title="Total Driving Distance (KM)", colorscale="Reds"),
    #     legend=dict(x=0.0, y=1.3)
    # )

    # # Show in Streamlit
    # st.plotly_chart(fig)
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    # Assuming round_stats_df is already sorted
    round_stats_df = round_stats_df.sort_values(by='Total Driving Distance', ascending=True)

    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Iterate through rows to preserve order while assigning correct color and legend
    legend_groups = {
        "red": "distance_gt_200",
        "green": "distance_lte_200"
    }

    legend_names = {
        "red": "Cost per Drop (Driving Distance > 200 KM)",
        "green": "Cost per Drop (Driving Distance ≤ 200 KM)"
    }

    # Track which legend groups have been shown
    shown_legends = set()

    for _, row in round_stats_df.iterrows():
        color = 'red' if row["Total Driving Distance"] > 200 else 'green'
        legend_group = legend_groups[color]
        legend_name = legend_names[color]

        # Show legend only once per group
        show_legend = legend_group not in shown_legends
        if show_legend:
            shown_legends.add(legend_group)

        fig.add_trace(
            go.Bar(
                x=[row['Round']],
                y=[row['Min Cost per Drop']],
                marker=dict(color=color),
                name=legend_name,
                legendgroup=legend_group,  # Group legends properly
                showlegend=show_legend,    # Show legend only once per group
                hovertemplate=(
                    "<b>Round:</b> %{x}<br>"
                    "<b>Min Cost per Drop:</b> %{y:.2f}<br>"
                    "<b>Total Driving Distance:</b> %{customdata:.2f} KM<br>"
                    "<extra></extra>"
                ),
                customdata=[row["Total Driving Distance"]],
            ),
            secondary_y=False,
        )

    # Add line plot for 'Associated Drops' (right y-axis)
    fig.add_trace(
        go.Scatter(
            x=round_stats_df['Round'],
            y=round_stats_df['Associated Drops'],
            mode='lines+markers',
            line=dict(color='black'),
            name="Associated Drops",
            legendgroup="associated_drops",  # Separate legend group
            hovertemplate=(
                "<b>Round:</b> %{x}<br>"
                "<b>Associated Drops:</b> %{y}<br>"
                "<b>Min Cost per Drop:</b> %{customdata[0]:.2f}<br>"
                "<b>Total Driving Distance:</b> %{customdata[1]:.2f} KM<br>"
                "<extra></extra>"
            ),
            customdata=list(zip(round_stats_df['Min Cost per Drop'], round_stats_df['Total Driving Distance'])),
        ),
        secondary_y=True,
    )

    # Update layout
    fig.update_layout(
        xaxis=dict(title="Round", type='category', tickangle=-45),
        yaxis=dict(title="Min Cost per Drop", showgrid=True),
        yaxis2=dict(title="Associated Drops", overlaying='y', side='right'),
        legend=dict(x=0.0, y=1.4),  # Adjust legend position
        barmode='group',  # Ensure bars are grouped properly
    )

    # Show in Streamlit
    st.plotly_chart(fig)

#+++++++++++++++++++++++++++++



    # Display table in Streamlit
    st.write("#### Minum Run cost Statistics for", day_of_week)
    st.dataframe(round_stats_df)
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++

    # Display table in Streamlit
    # st.write("### Statistics for", day_of_week)
    # st.dataframe(stats_table_df)

    # st.write(f"No. of runs: {len(hist_df.groupby(['Round', 'Pln Finish Date']).count())}")
    # st.write(f"No. of drops: {int(hist_df['completed Drops'].sum())}")
    # st.write(f"Max Km Bonus cost: {hist_df['KM Cost'].max()}")
    # st.write(f"Min Km Bonus cost: {hist_df['KM Cost'].min()}")
    # st.write(f"Avg Km Bonus cost: {round(hist_df['KM Cost'].mean(), 2)}")
    # st.write(f"Max Drop Bonus cost: {hist_df['Drop Cost'].max()}")
    # st.write(f"Min Drop Bonus cost: {hist_df['Drop Cost'].min()}")
    # st.write(f"Avg Drop Bonus cost: {round(hist_df['Drop Cost'].mean(), 2)}")

    # Read uploaded CSVs
    route_stats = pd.read_csv(upload_1)
    drops_stats = pd.read_csv(upload_2)

    # Filter and process data
    # routes_metro = route_stats[route_stats['rateZone'] == 'Melbourne Metro'].reset_index(drop=True)
    # drops_metro = drops_stats[drops_stats['RouteId'].isin(routes_metro['routeClient'].values.tolist())].reset_index(drop=True)

    list_zone = []

    for zone_val in route_stats['zone'].unique():
        if 'Metro' in zone_val or 'metro' in zone_val:
            list_zone.append(zone_val)
    routes_metro = route_stats[route_stats['zone'].isin(list_zone)].reset_index(drop = True)
    drops_metro = drops_stats[drops_stats['RouteId'].isin(routes_metro['routeClient'].values.tolist())].reset_index(drop = True)

    routes_metro['KM Cost'] = np.maximum((routes_metro['drivingDistance'] / 1000 - 200) * 1, 0)
    routes_metro['No. of overloaded drops'] = np.maximum(routes_metro['d2'] - 70, 0)
    routes_metro['Drop Cost'] = np.maximum((routes_metro['d2'] - 70) * 4.5, 0)
    routes_metro['Flat Rate'] = 370
    routes_metro['Total Cost'] = routes_metro['KM Cost'] + routes_metro['Drop Cost'] + routes_metro['Flat Rate']
    routes_metro['Cost per Drop'] = routes_metro['Total Cost']/routes_metro['d1']


    # Define categories based on conditions
    # need_to_be_refined = routes_metro[(routes_metro['d2'] < 70) & (routes_metro['drivingDistance']/1000 > 200)]['routeClient'].values.tolist()
    # good = routes_metro[(routes_metro['d2'] >= 70) & (routes_metro['drivingDistance']/1000 < 200)]['routeClient'].values.tolist()

    # Define categories based on conditions
    need_to_be_refined = routes_metro[(routes_metro['d2'] < 70) & (routes_metro['Cost per Drop'] > 370/70) | (routes_metro['Cost per Drop'] > 6)]['routeClient'].values.tolist()
    good = routes_metro[(routes_metro['d2'] >= 70) & (routes_metro['Cost per Drop'] < 370/70) & (routes_metro['drivingDistance']/1000 < 200)]['routeClient'].values.tolist()
    # can_be_refined = routes_metro[(routes_metro['d2'] < 70) | (routes_metro['drivingDistance']/1000 > 200)]['routeClient'].values.tolist()
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
    st.subheader("💰 Current Cost Table")
    st.dataframe(routes_metro[['zone', 'routeClient', 'vehicle', 'rateZone',
       'drivingDistance', 'drivingTime', 'totalTime', 'co2', 'd1', 'd2',
       'KM Cost', 'No. of overloaded drops', 'Drop Cost', 'Flat Rate',
       'Total Cost', 'Cost per Drop']], use_container_width=True)

    
    # current_cost_df = routes_metro[['zone', 'routeClient', 'vehicle', 'rateZone',
    #    'drivingDistance', 'drivingTime', 'totalTime', 'co2', 'd1', 'd2',
    #    'KM Cost', 'No. of overloaded drops', 'Drop Cost', 'Flat Rate',
    #    'Total Cost', 'Cost per Drop']]

    # # Create a filter widget for each column
    # st.sidebar.header("Filters")
    # filters = {}

    # for col in current_cost_df.columns:
    #     unique_values = current_cost_df[col].unique().tolist()
    #     selected_value = st.sidebar.multiselect(f"Filter {col}", unique_values, default=unique_values)
    #     filters[col] = selected_value

    # # Apply filters
    # def filter_df(df, filters):
    #     for col, values in filters.items():
    #         df = df[df[col].isin(values)]
    #     return df

    # filtered_df = filter_df(current_cost_df, filters)

    # # Display the table
    # st.dataframe(filtered_df)



    # Display the table in Streamlit
    st.subheader("📊 Route Client Classification Table")
    st.dataframe(styled_df)



    # Generate unique colors for routes
    # drops_metro = drops_metro[~drops_metro['Latitude'].isna()].reset_index(drop = True)
    # drops_metro = drops_metro[~drops_metro['Longitude'].isna()].reset_index(drop = True)


    route_ids = sorted(drops_metro['RouteId'].unique())
    num_routes = len(route_ids)
    colors = plt.cm.gist_ncar(np.linspace(0, 1, num_routes))
    route_colors = {route: f'#{int(c[0]*255):02x}{int(c[1]*255):02x}{int(c[2]*255):02x}' for route, c in zip(route_ids, colors)}
    


    # st.subheader("📍 Drops on Map")
    # # Create a Folium map
    # m = folium.Map(location=[drops_metro['Latitude'].mean(), drops_metro['Longitude'].mean()], zoom_start=12)

    # # Add points with unique colors
    # for _, row in drops_metro.iterrows():
    #     folium.CircleMarker(
    #         location=[row['Latitude'], row['Longitude']],
    #         radius=5,
    #         color=route_colors[row['RouteId']],
    #         fill=True,
    #         fill_color=route_colors[row['RouteId']],
    #         fill_opacity=0.7,
    #         popup=f"Route ID: {row['RouteId']}"
    #     ).add_to(m)

    # # Create legend HTML
    # legend_html = '''
    # <div style="position: fixed; 
    #             bottom: 50px; left: 50px; width: auto; height: auto; 
    #             overflow-y: auto; background-color: white; z-index:9999; 
    #             padding: 10px; font-size:14px; border-radius:5px; 
    #             box-shadow: 0px 0px 5px gray;">
    #     <b>Route ID Legend</b><br>
    # '''
    # for route, color in route_colors.items():
    #     legend_html += f'<div style="display: flex; align-items: center; padding: 2px;">'
    #     legend_html += f'<div style="width: 12px; height: 12px; background: {color}; margin-right: 5px;"></div>'
    #     legend_html += f'<span>{route}</span></div>'

    # legend_html += '</div>'

    # # Add legend as HTML element to map
    # # legend = Element(legend_html)
    # # m.get_root().html.add_child(legend)

    # # Display the map in Streamlit
    # folium_static(m)



    # Sample DataFrame (Replace with actual data)
    # Ensure drops_metro contains ['RouteId', 'Latitude', 'Longitude']

    st.subheader("📍 Drops on Map")

    # Generate unique colors for each RouteId
    route_colors = {route: [np.random.randint(0, 255) for _ in range(3)] for route in drops_metro['RouteId'].unique()}

    # Prepare convex hulls
    convex_hulls = []
    for route_id, group in drops_metro.groupby('RouteId'):
        if len(group) >= 3:
            points = group[['Latitude', 'Longitude']].values
            hull = ConvexHull(points)
            hull_points = [points[i].tolist() for i in hull.vertices]
            hull_points.append(hull_points[0])  # Close the polygon

            convex_hulls.append({
                "RouteId": route_id,
                "Polygon": [hull_points],  # Kepler.gl requires nested lists
                "Color": route_colors[route_id] + [100]  # Add alpha transparency
            })

    # Convert convex hulls to DataFrame
    hull_df = pd.DataFrame(convex_hulls)

    # Create Kepler.gl configuration
    config = {
        "version": "v1",
        "config": {
            "mapState": {"latitude": drops_metro['Latitude'].mean(), "longitude": drops_metro['Longitude'].mean(), "zoom": 10},
            "mapStyle": {"styleType": "dark"},
            "visState": {
                "layers": [
                    {
                        "id": "points",
                        "type": "point",
                        "config": {
                            "dataId": "drops",
                            "label": "Drops",
                            "color": [255, 0, 0],
                            "columns": {"lat": "Latitude", "lng": "Longitude"},
                            "isVisible": True,
                            "radius": 5
                        }
                    },
                    {
                        "id": "hulls",
                        "type": "polygon",
                        "config": {
                            "dataId": "hulls",
                            "label": "Convex Hulls",
                            "color": [0, 255, 0],
                            "columns": {"geojson": "Polygon"},
                            "isVisible": True
                        }
                    }
                ]
            }
        }
    # }

    # # Create Kepler map
    # map_ = KeplerGl(height=600, config=config)
    # map_.add_data(data=drops_metro, name="drops")
    # map_.add_data(data=hull_df, name="hulls")

    # # Display Kepler map in Streamlit
    # st.keplergl_chart(map_)






    # # Convert dict to DataFrame
    # route_colors_df = pd.DataFrame(route_colors.items(), columns=['Route ID', 'Color'])

    # # Function to style the Color column (hide text, keep background)
    # def color_cell(val):
    #     return f'background-color: {val}; color: {val};'  # Text blends with background

    # # Apply styles
    # styled_df = route_colors_df.style.map(color_cell, subset=['Color'])

    # # Streamlit App
    # # st.title("Route Colors Table")

    # # Display styled table in Streamlit
    # st.write(styled_df.to_html(escape=False), unsafe_allow_html=True)
