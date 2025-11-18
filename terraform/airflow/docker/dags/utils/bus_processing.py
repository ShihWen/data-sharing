import pandas as pd
import geopandas as gpd
from shapely import wkt
import json
import pendulum

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
                version_id = str(version_id)
            except (ValueError, TypeError):
                version_id = None

        direction = feature['Direction']
        if direction is not None:
            try:
                direction = str(direction)
            except (ValueError, TypeError):
                direction = None

        records.append({
            'route_uid': feature['RouteUID'],
            'route_id': feature['RouteID'],
            'route_name_zh_tw': feature['RouteName'].get('Zh_tw', ''),
            'route_name_en': feature['RouteName'].get('En', ''),
            'sub_route_uid': feature.get('SubRouteUID', ''),
            'sub_route_id': feature.get('SubRouteID', ''),
            'sub_route_name_zh_tw': feature['SubRouteName'].get('Zh_tw', ''),
            'sub_route_name_en': feature['SubRouteName'].get('En', ''),
            'direction': direction,
            'update_time': feature['UpdateTime'],
            'version_id': version_id,
            'geometry': geom
        })
        
    gdf = gpd.GeoDataFrame(records, geometry='geometry', crs="EPSG:4326")

    # gdf['geometry'] = gdf['geometry'].apply(lambda geom: geom.wkt if geom else None)
    
    return gdf

def process_inter_city_bus_station(raw_data: str) -> pd.DataFrame:
    """
    Transforms the raw JSON string for inter city bus station into a clean DataFrame,
    handling nested structures for BigQuery ingestion.
    """
    station_data = json.loads(raw_data)
    
    processed_records = []
    current_timestamp = pendulum.now('UTC')
    valid_to_ts_default = '9999-12-31T23:59:59Z'
    
    for feature in station_data:
        station_name_dict = feature.get('StationName', {})
        station_position_dict = feature.get('StationPosition', {})

        position_lon = station_position_dict.get('PositionLon')
        position_lat = station_position_dict.get('PositionLat')
        geohash = station_position_dict.get('GeoHash')

        geom = None
        if position_lon is not None and position_lat is not None:
            try:
                lon_float = float(position_lon)
                lat_float = float(position_lat)
                if -180 <= lon_float <= 180 and -90 <= lat_float <= 90:
                    geom = f"POINT({lon_float} {lat_float})"
                else:
                    print(f"Invalid coordinates for station {feature.get('StationUID', 'unknown')}: lon={lon_float}, lat={lat_float}")
            except (ValueError, TypeError) as e:
                print(f"Error parsing coordinates for station {feature.get('StationUID', 'unknown')}: {e}")
        
        processed_stops = []
        stops_data = feature.get('Stops', [])
        for stop in stops_data:
            stop_name_dict = stop.get('StopName', {})
            route_name_dict = stop.get('RouteName', {})
            processed_stops.append({
                'stop_uid': stop.get('StopUID'),
                'stop_id': stop.get('StopID'),
                'stop_name': {
                    'zh_tw': stop_name_dict.get('Zh_tw'),
                    'en': stop_name_dict.get('En', '')
                },
                'route_uid': stop.get('RouteUID'),
                'route_id': stop.get('RouteID'),
                'route_name': {
                    'zh_tw': route_name_dict.get('Zh_tw'),
                    'en': route_name_dict.get('En', '')
                }
            })

        record = {
            'station_uid': feature.get('StationUID'),
            'station_id': feature.get('StationID'),
            'station_name': {
                'zh_tw': station_name_dict.get('Zh_tw'),
                'en': station_name_dict.get('En', '')
            },
            'station_position': {
                'position_lon': position_lon,
                'position_lat': position_lat,
                'geohash': geohash
            },
            'station_group_id': feature.get('StationGroupID'),
            'stops': processed_stops,
            'location_city_code': feature.get('LocationCityCode'),
            'bearing': feature.get('Bearing'),
            'update_time': feature.get('UpdateTime'),
            'version_id': feature.get('VersionID'),
            'geometry': geom,
            # 'processed_at': current_timestamp.to_iso8601_string(),
            # 'valid_from_ts': current_timestamp.to_iso8601_string(),
            # 'valid_to_ts': valid_to_ts_default,
            # 'is_current': True
        }
        processed_records.append(record)
        
    df = pd.DataFrame(processed_records)

    return df

def process_inter_city_bus_stop_of_route(raw_data: str) -> pd.DataFrame:
    """
    Transforms the raw JSON string for inter city bus station into a clean DataFrame,
    handling nested structures for BigQuery ingestion.
    """
    stop_of_route_data = json.loads(raw_data)
    
    processed_records = []
    current_timestamp = pendulum.now('UTC')
    valid_to_ts_default = '9999-12-31T23:59:59Z'
    
    for feature in stop_of_route_data:
        route_uid = feature.get('RouteUID', {})
        route_id = feature.get('RouteID', {})
        
        route_name_dict = feature.get('RouteName', {})
        route_name_zh_tw = route_name_dict.get('Zh_tw', '')
        route_name_en = route_name_dict.get('En', '')
        
        operator_dict = feature.get('Operators', {})
        operator_id = operator_dict.get('OperatorID', '')
        operator_name_dict = operator_dict.get('OperatorName', {})
        operator_name_zh_tw = operator_name_dict.get('Zh_tw', '')
        operator_name_en = operator_name_dict.get('En', '')
        operator_code = operator_dict.get('OperatorCode', '')
        operator_no = operator_dict.get('OperatorNo', '')

        sub_route_uid = feature.get('SubRouteUID', {})
        sub_route_id = feature.get('SubRouteID', {})
        sub_route_name_dict = feature.get('SubRouteName', {})
        sub_route_name_zh_tw = sub_route_name_dict.get('Zh_tw', '')
        sub_route_name_en = sub_route_name_dict.get('En', '')
        direction = feature.get('Direction', '')
        
        stops_dict = feature.get('Stops', {})
        processed_stops = []
        for stop in stops_dict:
            stop_name_dict = stop.get('StopName', {})
            stop_id = stop.get('StopID', '')
            stop_name_zh_tw = stop_name_dict.get('Zh_tw', '')
            stop_name_en = stop_name_dict.get('En', '')

            stop_position_dict = stop.get('StopPosition', {})
            stop_position_lon = stop_position_dict.get('PositionLon', '')
            stop_position_lat = stop_position_dict.get('PositionLat', '')
            stop_position_geohash = stop_position_dict.get('GeoHash', '')
            processed_stops.append({
                'stop_uid': stop.get('StopUID'),
                'stop_id': stop.get('StopID'),
                'stop_name': {
                    'zh_tw': stop_name_dict.get('Zh_tw'),
                    'en': stop_name_dict.get('En', '')
                },
                'stop_position': {
                    'position_lon': stop_position_lon,
                    'position_lat': stop_position_lat,
                    'geohash': stop_position_geohash
                },
                'station_id': stop.get('StationID'),
                'station_group_id': stop.get('StationGroupID'),
                'location_city_code': stop.get('LocationCityCode')
            })

        record = {
            'route_uid': route_uid,
            'route_id': route_id,
            'route_name': {
                'zh_tw': route_name_zh_tw,
                'en': route_name_en
            },
            'operators': {
                'operator_id': operator_id,
                'operator_name': {
                    'zh_tw': operator_name_zh_tw,
                    'en': operator_name_en
                },
                'operator_code': operator_code,
                'operator_no': operator_no
            },
            'sub_route_uid': sub_route_uid,
            'sub_route_id': sub_route_id,
            'sub_route_name': {
                'zh_tw': sub_route_name_zh_tw,
                'en': sub_route_name_en
            },
            'direction': direction,
            'stops': processed_stops,
            'update_time': feature.get('UpdateTime'),
            'version_id': feature.get('VersionID'),
        }
        processed_records.append(record)
        
    df = pd.DataFrame(processed_records)

    return df