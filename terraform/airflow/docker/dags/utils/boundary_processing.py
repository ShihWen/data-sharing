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
            'city_id': properties['City'],
            'city_name': properties['CityName'],
            'update_date': pd.to_datetime(properties['UpdateDate']),
            'check_date': pd.to_datetime(properties['CheckDate']),
            'geometry': geom
        })
        
    gdf = gpd.GeoDataFrame(records, geometry='geometry', crs="EPSG:4326")

    # Convert shapely geometry to WKT for BigQuery
    gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom.wkt if geom else None)
    
    return gdf 