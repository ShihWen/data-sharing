from pathlib import Path
import os
import osmium
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
import json

# The path to the boundary file, relative to the DAGs folder
BOUNDARY_FILE_PATH = Path(os.path.dirname(__file__)).parent / "data/taipei_boundary.json"

def get_taipei_boundary() -> gpd.GeoDataFrame:
    """
    Loads the GeoJSON boundary for Taipei City from a local file.
    """
    with open(BOUNDARY_FILE_PATH, 'r') as f:
        geojson_data = json.load(f)
    
    gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
    gdf.crs = "EPSG:4326"
    return gdf

class WayHandler(osmium.SimpleHandler):
    def __init__(self):
        super(WayHandler, self).__init__()
        self.ways = []

    def way(self, w):
        if 'highway' in w.tags:
            try:
                # Build the linestring geometry from the node locations
                # A valid LineString requires at least two points.
                if len(w.nodes) < 2:
                    return

                line = LineString([(n.lon, n.lat) for n in w.nodes])
                
                self.ways.append({
                    'osmid': w.id,
                    'u': w.nodes[0].ref,
                    'v': w.nodes[-1].ref,
                    'highway': w.tags.get('highway'),
                    'name': w.tags.get('name'),
                    'lanes': w.tags.get('lanes'),
                    'oneway': w.tags.get('oneway', 'no'),
                    'reversed': w.tags.get('reversed', 'no'),
                    'length': w.tags.get('length'),
                    'bridge': w.tags.get('bridge'),
                    'maxspeed': w.tags.get('maxspeed'),
                    'ref': w.tags.get('ref'),
                    'service': w.tags.get('service'),
                    'width': w.tags.get('width'),
                    'access': w.tags.get('access'),
                    'tunnel': w.tags.get('tunnel'),
                    'junction': w.tags.get('junction'),
                    'geometry': line
                })
            except osmium.InvalidLocationError:
                # This can happen for nodes that are not in the PBF file
                # (e.g., at the boundary of the extract). We can safely ignore them.
                pass

def process_pbf_to_dataframe(pbf_file_path: str) -> pd.DataFrame:
    """
    Processes an OSM PBF file, clips the road network to the Taipei boundary,
    and returns a clean DataFrame ready for BigQuery.
    """
    print("Getting Taipei boundary...")
    taipei_boundary = get_taipei_boundary()
    
    print("Processing PBF file...")
    handler = WayHandler()
    # The PBF file is parsed in its entirety. The clipping to the boundary happens later.
    handler.apply_file(pbf_file_path, locations=True)
    
    if not handler.ways:
        print("Warning: No ways were processed. The PBF file might not cover the Taipei area.")
        return pd.DataFrame()

    print(f"Processed {len(handler.ways)} ways from the PBF file.")

    # Convert the list of dictionaries to a GeoDataFrame
    gdf = gpd.GeoDataFrame(handler.ways, geometry='geometry', crs="EPSG:4326")

    print("Clipping road network to the precise Taipei boundary...")
    # Perform a spatial join (intersection) to keep only roads that are within the Taipei polygon
    clipped_gdf = gpd.sjoin(gdf, taipei_boundary, how="inner", predicate='intersects')
    
    # The sjoin adds columns from the boundary file (e.g., 'index_right'), so we drop them
    # to keep the schema clean.
    clipped_gdf = clipped_gdf[gdf.columns]
    
    if clipped_gdf.empty:
        print("Warning: No roads were found within the Taipei boundary after clipping.")
        return pd.DataFrame()

    print(f"Found {len(clipped_gdf)} road segments within Taipei.")

    # For now, we hardcode the city and use a placeholder for the district.
    # A future implementation would use a reverse geocoding service or a spatial join
    # with a district-level boundary file to determine the correct district for each road.
    clipped_gdf['city'] = 'Taipei City'
    clipped_gdf['district'] = 'Unknown' 

    # Perform data type conversions and handle potential missing values
    clipped_gdf['lanes'] = pd.to_numeric(clipped_gdf['lanes'], errors='coerce').astype('Int64')
    clipped_gdf['maxspeed'] = pd.to_numeric(clipped_gdf['maxspeed'], errors='coerce').astype('Int64')
    clipped_gdf['length'] = pd.to_numeric(clipped_gdf['length'], errors='coerce').astype('float')
    clipped_gdf['width'] = pd.to_numeric(clipped_gdf['width'], errors='coerce').astype('float')
    
    # Convert the shapely geometry objects to Well-Known Text (WKT) strings,
    # which is the format BigQuery expects for GEOGRAPHY data.
    clipped_gdf['geometry'] = clipped_gdf['geometry'].apply(lambda geom: geom.wkt if geom else None)

    # Ensure all columns from the BigQuery schema are present
    final_columns = [
        'osmid', 'u', 'v', 'highway', 'name', 'lanes', 'oneway', 'reversed', 
        'length', 'bridge', 'maxspeed', 'ref', 'service', 'width', 'access', 
        'tunnel', 'junction', 'geometry', 'city', 'district'
    ]
    for col in final_columns:
        if col not in clipped_gdf.columns:
            clipped_gdf[col] = None

    return clipped_gdf[final_columns] 