"""Functions to grab ZHVI data from zillow, create charts and graphs"""

from calendar import month_name
from datetime import datetime

import folium
import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st
from numpy import floor
from streamlit_folium import folium_static, st_folium


def convert_float_to_int(in_df):
    """Converts float columns to Int64 columns"""
    float_cols = in_df.select_dtypes(include=['float64'])
    for col in float_cols.columns.values:
        in_df[col] = floor(pd.to_numeric(in_df[col], errors='coerce')).astype('Int64')
    return in_df


def join_fields(og_df, source_df, og_key, source_key, columns):
    '''join fields from one dataframe(source_df) to the original(og_df)'''
    df_list = [og_df, source_df]
    key_list = [og_key, source_key]
    columns.append(source_key)
    columns = list(set(columns))

    for df, key in zip(df_list, key_list):
        if not df[key].is_unique:
            return print('The fields are not unique, join will not be accurate')

    return pd.merge(og_df, source_df[columns], left_on=og_key, right_on=source_key, how='left')


def get_average_homeprice(in_df, in_name):
    """Creates a column with the average homeprice for the current hometype"""
    in_df[f'yr_avg_{in_name}'] = in_df.mean(axis=1, numeric_only=True)
    return in_df


def clean_df_month_cols(in_df, filter_columns, sel_date_cols, date_cols_rename, cat_name):
    return (in_df
            [filter_columns]
            .rename(dict(zip(sel_date_cols,date_cols_rename)), axis='columns')
            .pipe(get_average_homeprice, cat_name)
            .astype({'RegionName':'category', 'StateName':'category'})
        )


def get_zillow_dataframe(in_year, geo, query, hometype_name):
    """ in_year: str, (2018,2019,2020,2021,2022)
        geo: str, (county, state)
        query: str, ('sfrcondo', 'sfr', 'condo')
        hometype_name: str, ('combined', 'home', 'condo')
    """
    csv_url = ("https://files.zillowstatic.com/research/public_csvs/zhvi/"
                f"{geo.title()}_zhvi_uc_{query}_tier_0.33_0.67_sm_sa_month.csv")
    df = pd.read_csv(csv_url)

    date_cols = [column for column in df.columns if in_year in column]
    if geo.lower() == 'state':
        filter_cols = ['RegionID', 'RegionName', 'StateName', *date_cols]
    else:
        df = create_countyFIPs_code(df)
        filter_cols = ['RegionID', 'RegionName', 'StateName',
                        'StateCodeFIPS', 'MunicipalCodeFIPS', 'County_FIPS', *date_cols]

    date_cols_renamed = [f'{datetime.strptime(col, "%Y-%m-%d").strftime("%B")}_{hometype_name}'
                        for col in date_cols]

    df = clean_df_month_cols(df, filter_cols, date_cols, date_cols_renamed, hometype_name)

    return convert_float_to_int(df)


def create_countyFIPs_code(in_df):
    return (in_df
            .assign(
                County_FIPS = in_df['StateCodeFIPS'].astype(str).str.zfill(2)
                + in_df['MunicipalCodeFIPS'].astype(str).str.zfill(3)
            )
        )


def create_folium_map(in_gdf, in_geom, in_year, in_hometype, id_field):
    geom_type = 'State' if in_geom.lower() == 'state' else 'County'

    mymap = folium.Map(
        location=[39.817999, -95.693616],
        zoom_start=4,
        tiles=None
    )

    folium.TileLayer(
        'CartoDB positron',
        name="Light Map",
        control=False
    ).add_to(mymap)

    yr_avg = f'yr_avg_{in_hometype}'

    if geom_type.lower() != 'state':
        in_gdf["temp_yr_avg"] = in_gdf[yr_avg]
        temp_gdf = in_gdf.query("temp_yr_avg == temp_yr_avg")
        myscale = (temp_gdf["temp_yr_avg"].quantile((0,0.2,0.4,0.5,0.7,0.8,0.98,1))).tolist()

        in_gdf[yr_avg] = in_gdf[yr_avg].astype('float64')

        choropleth = folium.Choropleth(
            geo_data = in_gdf,
            data = in_gdf,
            columns=[id_field, yr_avg],
            key_on=f"feature.properties.{id_field}",
            fill_opacity=1,
            fill_color="BuPu",
            line_opacity=1,
            line_color="#FFFFFF",
            nan_fill_color="gray",
            nan_fill_opacity=0.4,
            threshold_scale=myscale,
            highlight=True,
            smooth_factor=0
        )

        for key in choropleth._children:
            if key.startswith('color_map'):
                del(choropleth._children[key])

        choropleth.add_to(mymap)

    else:
        choropleth = folium.Choropleth(
            geo_data = in_gdf,
            data = in_gdf,
            columns=[id_field, yr_avg],
            key_on="feature.properties.NAME",
            fill_opacity=1,
            fill_color="BuPu",
            line_opacity=1,
            line_color="#FFFFFF",
            legend_name = f"Average Zillow {in_hometype.title()} Home Value Index for {in_year}",
            highlight=True,
            smooth_factor=0
        ).add_to(mymap)

    tooltip = folium.features.GeoJsonTooltip(
        fields=["RegionName", yr_avg],
        aliases=[f"{geom_type.title()}:", "Avg ZHVI:"],
        labels=True,
        stick=False,
        localize=True
    )

    choropleth.geojson.add_child(tooltip)
    return mymap


def get_top10_state_records(in_hometype, in_df, top=True):
    """top is true by default, and will return the top ten state records
        if top is False, it will return the bot 10 results"""
    if top:
        top = not top
    yr_avg = f'yr_avg_{in_hometype}'
    return (in_df
                .sort_values(yr_avg, ascending=top)[:10]
                .rename(columns={'NAME': "State_Name", yr_avg: "Average_Price"})
            )[["State_Name", "Average_Price"]]


def get_state_charts(in_hometype, in_df, in_year):

    top_ten_states = get_top10_state_records(in_hometype, in_df, False)
    bot_ten_states = get_top10_state_records(in_hometype, in_df, True)

    fig_top_states = px.bar(
        top_ten_states,
        x="State_Name",
        y="Average_Price",
        orientation="v",
        title= f"<b>The 10 Most Expensive States {in_year}</b>",
        color_discrete_sequence=["#0083B8"] * len(top_ten_states),
        template="plotly_white",
    )

    fig_bot_states = px.bar(
        bot_ten_states,
        x="State_Name",
        y="Average_Price",
        orientation="v",
        title= f"<b>The 10 Least Expensive States {in_year}</b>",
        color_discrete_sequence=["#0083B8"] * len(bot_ten_states),
        template="plotly_white",
    )

    return fig_top_states, fig_bot_states


def get_top10_county_records(in_hometype, in_df, top=True):
    """top is true by default, and will return the top ten state records
        if top is False, it will return the bot 10 results"""
    if top:
        top = not top
    yr_avg = f'yr_avg_{in_hometype}'
    return (in_df
                .sort_values(yr_avg, ascending=top)[:10]
                .assign(County_Name=
                        in_df.RegionName.astype(str) + ', ' + in_df.StateName.astype(str))
                .rename(columns={yr_avg: "Average_Price"})
            )[["County_Name", "Average_Price"]]


def get_county_charts(in_hometype, in_df, in_year):

    top_ten_counties = get_top10_county_records(in_hometype, in_df, True)
    bot_ten_counties = get_top10_county_records(in_hometype, in_df, False)

    fig_top_counties = px.bar(
        top_ten_counties,
        x="County_Name",
        y="Average_Price",
        orientation="v",
        title= f"<b>The 10 Most Expensive Counties {in_year}</b>",
        color_discrete_sequence=["#0083B8"] * len(top_ten_counties),
        template="plotly_white",
    )

    fig_bot_counties = px.bar(
        bot_ten_counties,
        x="County_Name",
        y="Average_Price",
        orientation="v",
        title= f"<b>The 10 Least Expensive Counties {in_year}</b>",
        color_discrete_sequence=["#0083B8"] * len(bot_ten_counties),
        template="plotly_white",
    )

    return fig_top_counties, fig_bot_counties


def get_monthly_chart(in_df, in_hometype, in_year):
    month_cols_list = [x for x in in_df.columns.to_list()
                        if f"_{in_hometype}" in x and "yr_avg" not in x]
    month_name_list = [x.replace(f"_{in_hometype}", '') for x in month_cols_list]
    month_lookup = list(month_name)
    month_sorted = sorted(month_name_list, key=month_lookup.index)

    df = in_df[month_cols_list]
    df.columns = month_name_list
    df = df[month_sorted]

    avg_month_df = (pd.DataFrame(df.mean(axis=0))
                .transpose()
                .astype(int)
                .transpose()
                .reset_index()
                .rename(columns={"index": "Month", 0: "Price"})
                    )

    return px.line(
            avg_month_df,
            x="Month",
            y="Price",
            title= f"<b>Monthly Average Price Changes {in_year} (All of US)</b>",
            color_discrete_sequence=["#0083B8"] * len(avg_month_df),
            template="plotly_white",
    )


def get_list_columns(in_df):
    """Returns a list of column names from an input df"""
    return in_df.columns.values.tolist()

