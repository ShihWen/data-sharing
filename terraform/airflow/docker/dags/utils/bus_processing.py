import pandas as pd
import geopandas as gpd
import json
from shapely.geometry import shape
from shapely import wkt

def process_inter_city_bus_shape(raw_data: str) -> gpd.GeoDataFrame:
    """
    Transforms the raw GeoJSON string for inter city bus shape into a clean GeoDataFrame.
    """
    shape_data = json.loads(raw_data)
    
    records = []
    for feature in shape_data:
        
        geom = wkt.loads(feature['Geometry'])


        version_id = feature['VersionID']
        if version_id is not None:
            try:
                version_id = int(version_id)
            except (ValueError, TypeError):
                version_id = None

        direction = feature['Direction']
        if direction is not None:
            try:
                direction = int(direction)
            except (ValueError, TypeError):
                direction = None

        records.append({
            'route_uid': feature['RouteUID'],
            'route_id': feature['RouteID'],
            'route_name_zh_tw': feature['RouteName']['Zh_tw'],
            'route_name_en': feature['RouteName']['En'],
            'sub_route_uid': feature['SubRouteUID'],
            'sub_route_id': feature['SubRouteID'],
            'sub_route_name_zh_tw': feature['SubRouteName']['Zh_tw'],
            'sub_route_name_en': feature['SubRouteName']['En'],
            'direction': direction,
            'update_time': feature['UpdateTime'],
            'version_id': version_id,
            'geometry': geom
        })
        
    gdf = gpd.GeoDataFrame(records, geometry='geometry', crs="EPSG:4326")

    # gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom.wkt if geom else None)
    
    return gdf