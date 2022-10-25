import streamlit as st
from zillow_functions import *

#streamlit set-up
st.set_page_config(page_title="Real Estate Dashboard", page_icon=":bar_chart:", layout="centered")
st.markdown("<h1 style='color: black;'>Real Estate Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='color: black;'>Average ZHVI <a href='https://www.zillow.com/research/data/'>(Zillow Combined Home Value Index)<a></h3>", unsafe_allow_html=True)
st.markdown("Written by <a href='https://ericsamson.com/'>Eric Samson</a>", unsafe_allow_html=True)

# User Inputs
form = st.sidebar.form(key='my_form')

user_geom = form.selectbox(
    'State Or County Geometry Level',
    ('State', 'County'))

hometype = form.selectbox(
    'Choose Home Type:',
    ('combined', 'home', 'condo'))

year_selection = form.selectbox(
    'Year:',
    ('2022', '2021', '2020', '2019', '2018'))

submit_button = form.form_submit_button(label='Submit')
# User Inputs

hometype_dict = {'combined': 'sfrcondo', 'home': 'sfr', 'condo':'condo'}
hometype_query = hometype_dict[hometype]

statistics_df = get_zillow_dataframe(year_selection, user_geom.lower(), hometype_query, hometype)

columns_needed = get_list_columns(statistics_df)

if user_geom.lower() == "state":
    state_geoms = gpd.read_file("assets/states_geom.json")
    gdf_for_map = join_fields(state_geoms, 
                            statistics_df, 
                            "NAME", "RegionName", 
                            columns_needed
                            )
    map_output = create_folium_map(gdf_for_map, user_geom, year_selection, hometype, "RegionName")
    fig_top_geoms, fig_bot_geoms = get_state_charts(hometype, gdf_for_map, year_selection)
else:
    county_geoms = gpd.read_file("assets/county_geom.json")
    gdf_for_map = join_fields(county_geoms, 
                            statistics_df, 
                            "County_FIPS", "County_FIPS", 
                            columns_needed
                            )
    map_output = create_folium_map(gdf_for_map, user_geom, year_selection, hometype, "County_FIPS")
    fig_top_geoms, fig_bot_geoms = get_county_charts(hometype, gdf_for_map, year_selection)

fig_monthly_line = get_monthly_chart(gdf_for_map, hometype, year_selection)

folium_static(map_output, width=700)

st.plotly_chart(fig_top_geoms, use_container_width=True)
st.plotly_chart(fig_monthly_line, use_container_width=True)

# HIDE STREAMLIT STYLE
hide_st_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                header {visibility: hidden;}
                </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)
