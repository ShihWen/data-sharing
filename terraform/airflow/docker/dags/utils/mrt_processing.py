import pandas as pd
import geopandas as gpd
from shapely import wkt
import json
import pendulum

def process_mrt_shape(raw_data: str) -> gpd.GeoDataFrame:
    """
    Transforms the raw GeoJSON string for mrt shape into a clean GeoDataFrame.
    """
    shape_data = json.loads(raw_data)
    
    records = []
    for feature in shape_data:
        
        geom = wkt.loads(feature['Geometry'])

        records.append({
            'line_no': feature['LineNo'],
            'line_id': feature['LineID'],
            'line_name_zh_tw': feature['LineName'].get('Zh_tw', ''),
            'line_name_en': feature['LineName'].get('En', ''),
            'UpdateTime': feature['UpdateTime'],
            'geometry': geom
        })
        
    gdf = gpd.GeoDataFrame(records, geometry='geometry', crs="EPSG:4326")
    
    return gdf