from pathlib import Path
import os
import osmium
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
import json
import logging
from shapely.geometry import LineString, shape
from shapely import wkt


# The path to the boundary file, relative to the DAGs folder
BOUNDARY_FILE_PATH = Path(os.path.dirname(__file__)).parent / "data/taipei_boundary.json"

# Remove the get_taipei_boundary function as it's no longer needed.

class WayHandler(osmium.SimpleHandler):
    def __init__(self):
        super(WayHandler, self).__init__()
        self.ways = []
        logging.info("WayHandler initialized.")

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
                # Node location not found, skipping this way
                pass

def process_pbf_to_dataframe(pbf_file_path: str, boundary_wkt: str) -> pd.DataFrame:
    """
    Processes a PBF file and clips the road network data to the provided boundary.

    Args:
        pbf_file_path: The local path to the OSM PBF file.
        boundary_wkt: The WKT representation of the boundary to clip against.
    """
    logging.info("Processing PBF file into DataFrame...")
    
    # Load the boundary from WKT
    boundary_geom = wkt.loads(boundary_wkt)
    boundary_gdf = gpd.GeoDataFrame([{'geometry': boundary_geom}], crs="EPSG:4326")

    handler = WayHandler()
    logging.info("Applying PBF file to WayHandler...")
    # The box argument is not needed as we are clipping with the exact boundary later
    handler.apply_file(pbf_file_path, locations=True)
    logging.info(f"Processed {len(handler.ways)} ways from the PBF file.")

    if not handler.ways:
        logging.warning("No ways with 'highway' tag found in the PBF file.")
        return pd.DataFrame()

    gdf = gpd.GeoDataFrame(handler.ways, geometry='geometry', crs="EPSG:4326")

    # Filter out invalid or empty geometries which can cause issues with spatial operations
    gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty]

    if gdf.empty:
        logging.warning("GeoDataFrame is empty after filtering invalid geometries.")
        return pd.DataFrame()

    logging.info("Clipping road network to the precise boundary...")
    # Use sjoin with 'intersects' to find all roads that touch or cross the boundary
    clipped_gdf = gpd.sjoin(gdf, boundary_gdf, how="inner", predicate='intersects')

    if clipped_gdf.empty:
        logging.warning("No road segments found within the provided boundary.")
        return pd.DataFrame()

    # Drop the 'index_right' column added by sjoin
    clipped_gdf = clipped_gdf.drop(columns=['index_right'])

    logging.info(f"Found {len(clipped_gdf)} road segments within the boundary.")

    # --- Data Cleaning and Type Conversion ---

    # Standardize 'oneway' and 'reversed' columns to boolean
    # The 'oneway' and 'reversed' tags can have values like 'yes', 'no', 'true', 'false', '1', '0'.
    # This mapping handles the common cases and defaults any other value to False.
    bool_map = {'yes': True, 'true': True, '1': True, 'no': False, 'false': False, '0': False}
    clipped_gdf['oneway'] = clipped_gdf['oneway'].str.lower().map(bool_map).fillna(False).astype(bool)
    clipped_gdf['reversed'] = clipped_gdf['reversed'].replace({'yes': True, 'true': True, '1': True, 1: True, 'no': False, 'false': False, '0': False, 0: False, None: False}).astype(bool)

    # Convert numeric columns, coercing errors to NaN and then filling with a default (e.g., 0 or None)
    # Using Int64 (capital I) to allow for pandas' nullable integer type
    clipped_gdf['lanes'] = pd.to_numeric(clipped_gdf['lanes'], errors='coerce').astype('Int64')
    clipped_gdf['maxspeed'] = pd.to_numeric(clipped_gdf['maxspeed'], errors='coerce').astype('Int64')
    clipped_gdf['length'] = pd.to_numeric(clipped_gdf['length'], errors='coerce').astype('float')
    clipped_gdf['width'] = pd.to_numeric(clipped_gdf['width'], errors='coerce').astype('float')

    # Add dummy columns for city and district for now.
    # A future improvement could be to perform a spatial join against district boundaries.
    clipped_gdf['city'] = 'Taipei'
    clipped_gdf['district'] = 'Unknown'

    # Convert geometry to Well-Known Text (WKT) for BigQuery
    # Ensure this is one of the last steps
    clipped_gdf['geometry'] = clipped_gdf['geometry'].apply(lambda geom: geom.wkt if geom else None)
    logging.info("Converted geometry to WKT format.")
    
    # Ensure final columns match the BigQuery schema
    final_columns = [
        'osmid', 'u', 'v', 'highway', 'name', 'lanes', 'oneway', 'reversed', 
        'length', 'bridge', 'maxspeed', 'ref', 'service', 'width', 'access', 
        'tunnel', 'junction', 'geometry', 'city', 'district'
    ]
    clipped_gdf = clipped_gdf.reindex(columns=final_columns)

    return clipped_gdf 