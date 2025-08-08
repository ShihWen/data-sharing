import pandas as pd
import geopandas as gpd
import json
from shapely.geometry import shape

def process_city_boundaries(raw_data: str) -> gpd.GeoDataFrame:
    """
    Transforms the raw GeoJSON string for city boundaries into a clean GeoDataFrame.
    """
    data = json.loads(raw_data)
    
    records = []
    for feature in data['features']:
        properties = feature['properties']['model']
        
        # Create a shapely geometry object from the GeoJSON geometry
        geom = shape(feature['geometry'])
        
        records.append({
            'city_name_en': properties['City'],
            'city_name_zh': properties['CityName'],
            'update_date': pd.to_datetime(properties['UpdateDate']),
            'check_date': pd.to_datetime(properties['CheckDate']),
            'geometry': geom
        })
        
    gdf = gpd.GeoDataFrame(records, geometry='geometry', crs="EPSG:4326")

    # Convert shapely geometry to WKT for BigQuery
    gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom.wkt if geom else None)
    
    return gdf


def process_town_boundaries(raw_data: str) -> gpd.GeoDataFrame:
    """
    Transforms the raw GeoJSON string for town boundaries into a clean GeoDataFrame.
    """
    data = json.loads(raw_data)
    
    records = []
    for feature in data['features']:
        properties = feature['properties']['model']
        
        geom = shape(feature['geometry'])
        
        records.append({
            'town_code': properties['TownCode'],
            'town_name_zh': properties['TownName'],
            'city_name_en': properties['City'],
            'city_name_zh': properties['CityName'],
            'update_date': pd.to_datetime(properties['UpdateDate']),
            'check_date': pd.to_datetime(properties['CheckDate']),
            'geometry': geom
        })
        
    gdf = gpd.GeoDataFrame(records, geometry='geometry', crs="EPSG:4326")

    gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom.wkt if geom else None)
    
    return gdf 

def process_village_boundaries(raw_data: str) -> gpd.GeoDataFrame:
    """
    Transforms the raw GeoJSON string for village boundaries into a clean GeoDataFrame.
    """
    data = json.loads(raw_data)
    
    records = []
    for feature in data['features']:
        properties = feature['properties']['model']
        
        geom = shape(feature['geometry'])
        
        records.append({
            'village_code': properties['VillageCode'],
            'village_name_zh': properties['VillageName'],
            'town_code': properties['TownCode'],
            'town_name_zh': properties['TownName'],
            'city_name_en': properties['City'],
            'city_name_zh': properties['CityName'],
            'update_date': pd.to_datetime(properties['UpdateDate']),
            'check_date': pd.to_datetime(properties['CheckDate']),
            'geometry': geom
        })
        
    gdf = gpd.GeoDataFrame(records, geometry='geometry', crs="EPSG:4326")

    gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom.wkt if geom else None)
    
    return gdf 