import osmium
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
import requests
import json

TAIPEI_BOUNDARY_URL = "https://raw.githubusercontent.com/gipong/p2p-gis/master/taipei.json"

def get_taipei_boundary() -> gpd.GeoDataFrame:
    """
    Downloads the GeoJSON boundary for Taipei City.
    """
    response = requests.get(TAIPEI_BOUNDARY_URL)
    response.raise_for_status()
    geojson_data = json.loads(response.text)
    
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
    and returns a clean DataFrame.
    """
    print("Getting Taipei boundary...")
    taipei_boundary = get_taipei_boundary()
    
    print("Processing PBF file...")
    handler = WayHandler()
    # Use the boundary to pre-filter ways, which is more efficient
    handler.apply_file(pbf_file_path, locations=True, box=taipei_boundary.total_bounds)
    
    if not handler.ways:
        print("Warning: No ways were processed. The PBF file might not cover the Taipei area.")
        return pd.DataFrame()

    print(f"Processed {len(handler.ways)} ways from PBF.")

    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame(handler.ways, geometry='geometry', crs="EPSG:4326")

    print("Clipping road network to Taipei boundary...")
    # Perform a spatial join (intersection) to keep only roads within Taipei
    clipped_gdf = gpd.sjoin(gdf, taipei_boundary, how="inner", predicate='intersects')
    
    # The sjoin might add columns from the boundary file, so we drop them
    clipped_gdf = clipped_gdf[gdf.columns]
    
    print(f"Found {len(clipped_gdf)} roads within Taipei.")

    # A real implementation would do a reverse geocode here to get the 'district'
    clipped_gdf['city'] = 'Taipei City'
    clipped_gdf['district'] = 'Unknown' # Placeholder

    # Basic data type conversion
    clipped_gdf['lanes'] = pd.to_numeric(clipped_gdf['lanes'], errors='coerce')
    clipped_gdf['maxspeed'] = pd.to_numeric(clipped_gdf['maxspeed'], errors='coerce')
    
    # Convert shapely geometry to WKT for BigQuery
    clipped_gdf['geometry'] = clipped_gdf['geometry'].apply(lambda geom: geom.wkt)

    return clipped_gdf 