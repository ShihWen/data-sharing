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
from typing import Union


# The path to the boundary file, relative to the DAGs folder
BOUNDARY_FILE_PATH = Path(os.path.dirname(__file__)).parent / "data/taipei_boundary.json"

# Remove the get_taipei_boundary function as it's no longer needed.

class WayHandler(osmium.SimpleHandler):
    def __init__(self, bbox: Union[tuple, None] = None):
        super(WayHandler, self).__init__()
        self.ways = []
        self.bbox = bbox
        # Unpack for slightly faster access in the loop
        self.min_lon, self.min_lat, self.max_lon, self.max_lat = bbox if bbox else (None, None, None, None)
        logging.info(f"WayHandler initialized with bbox: {self.bbox}")

    def way(self, w):
        if 'highway' in w.tags:
            # If a bounding box is provided, perform a quick check to see if at least one
            # of the way's nodes is inside the box. This is a major optimization to
            # avoid processing ways that are clearly outside our area of interest.
            if self.bbox:
                in_box = False
                for n in w.nodes:
                    if self.min_lon <= n.lon <= self.max_lon and \
                       self.min_lat <= n.lat <= self.max_lat:
                        in_box = True
                        break  # Found a node in the box, so we process the whole way
                
                if not in_box:
                    return # Skip this way entirely

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

def process_pbf_to_dataframe(pbf_file_path: str, boundaries_gdf: gpd.GeoDataFrame, bbox: tuple) -> pd.DataFrame:
    """
    Processes a PBF file and clips the road network data to the provided boundaries.

    Args:
        pbf_file_path: The local path to the OSM PBF file.
        boundaries_gdf: A GeoDataFrame containing the town/district boundaries to clip against.
                        It must include 'geometry', 'city', and 'town' columns.
        bbox: A tuple representing the bounding box (min_lon, min_lat, max_lon, max_lat)
              to pre-filter the PBF data, reducing memory usage.
    """
    logging.info("Processing PBF file into DataFrame...")

    # Instantiate the handler with the bounding box for pre-filtering.
    handler = WayHandler(bbox=bbox)
    logging.info(f"Applying PBF file to WayHandler with bounding box pre-filter.")
    
    # apply_file does not take a 'box' argument; the filtering is done inside the handler.
    handler.apply_file(pbf_file_path, locations=True)
    logging.info(f"Processed {len(handler.ways)} ways from the PBF file after pre-filtering.")

    if not handler.ways:
        logging.warning("No ways with 'highway' tag found in the PBF file after pre-filtering.")
        return pd.DataFrame()

    gdf = gpd.GeoDataFrame(handler.ways, geometry='geometry', crs="EPSG:4326")
    gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty]

    if gdf.empty:
        logging.warning("GeoDataFrame is empty after filtering invalid geometries.")
        return pd.DataFrame()

    logging.info("Spatially joining road network with all town boundaries...")
    # Process each boundary individually to ensure we get roads from all cities
    # The previous approach used a single spatial join with how="inner", which only
    # returned roads that intersected ALL boundaries simultaneously. This meant
    # we were missing roads that only existed in individual cities.
    # By processing each boundary separately, we ensure all cities are represented.
    all_clipped_results = []
    
    for idx, boundary in boundaries_gdf.iterrows():
        city_name = boundary.get('city', f'city_{idx}')
        town_name = boundary.get('town', f'town_{idx}')
        town_code = boundary.get('town_code', f'code_{idx}')
        
        logging.info(f"Processing boundary {idx}: city={city_name}, town={town_name}, town_code={town_code}")
        
        # Create a single-row GeoDataFrame for this boundary
        single_boundary = gpd.GeoDataFrame([boundary], geometry='geometry', crs="EPSG:4326")
        
        # Perform spatial join for this specific boundary
        boundary_clipped = gpd.sjoin(gdf, single_boundary, how="inner", predicate='intersects')
        
        if not boundary_clipped.empty:
            # Add city, town, and town_code information
            boundary_clipped['city'] = city_name
            boundary_clipped['town'] = town_name
            boundary_clipped['town_code'] = town_code
            
            # Drop the index_right column added by sjoin
            boundary_clipped = boundary_clipped.drop(columns=['index_right'])
            
            all_clipped_results.append(boundary_clipped)
            logging.info(f"Found {len(boundary_clipped)} road segments for {city_name}/{town_name}")
        else:
            logging.info(f"No road segments found for {city_name}/{town_name}")
    
    if not all_clipped_results:
        logging.warning("No road segments found within any of the provided boundaries.")
        return pd.DataFrame()
    
    # Combine all results
    clipped_gdf = pd.concat(all_clipped_results, ignore_index=True)
    
    # Log the available columns after spatial join for debugging
    logging.info(f"Columns available after spatial join: {clipped_gdf.columns.tolist()}")
    logging.info(f"Total road segments found across all boundaries: {len(clipped_gdf)}")
    
    # Log distribution by city
    city_counts = clipped_gdf['city'].value_counts()
    logging.info(f"Road segments per city: {city_counts.to_dict()}")

    # --- Data Cleaning and Type Conversion ---
    bool_map = {'yes': True, 'true': True, '1': True, 'no': False, 'false': False, '0': False}
    clipped_gdf['oneway'] = clipped_gdf['oneway'].str.lower().map(bool_map).fillna(False).astype(bool)
    clipped_gdf['reversed'] = clipped_gdf['reversed'].replace({'yes': True, 'true': True, '1': True, 1: True, 'no': False, 'false': False, '0': False, 0: False, None: False}).astype(bool)

    clipped_gdf['lanes'] = pd.to_numeric(clipped_gdf['lanes'], errors='coerce').astype('Int64')
    clipped_gdf['maxspeed'] = pd.to_numeric(clipped_gdf['maxspeed'], errors='coerce').astype('Int64')
    clipped_gdf['length'] = pd.to_numeric(clipped_gdf['length'], errors='coerce').astype('float')
    clipped_gdf['width'] = pd.to_numeric(clipped_gdf['width'], errors='coerce').astype('float')

    # The 'city' and 'district' columns are now populated directly from the spatial join.

    # Convert geometry to Well-Known Text (WKT) for BigQuery using the idiomatic method
    # that avoids raising a UserWarning.
    df_for_bq = pd.DataFrame(clipped_gdf.drop(columns='geometry'))
    df_for_bq['geometry'] = clipped_gdf.geometry.to_wkt()
    logging.info("Converted geometry to WKT format.")
    
    # Ensure final columns match the BigQuery schema
    final_columns = [
        'osmid', 'u', 'v', 'highway', 'name', 'lanes', 'oneway', 'reversed', 
        'length', 'bridge', 'maxspeed', 'ref', 'service', 'width', 'access', 
        'tunnel', 'junction', 'geometry', 'city', 'town', 'town_code'
    ]
    
    # Check if all required columns are present
    missing_columns = [col for col in final_columns if col not in df_for_bq.columns]
    if missing_columns:
        logging.warning(f"Missing columns in DataFrame: {missing_columns}")
        logging.info(f"Available columns: {df_for_bq.columns.tolist()}")
        
        # Add missing columns with default values
        for col in missing_columns:
            if col == 'town_code':
                df_for_bq[col] = None  # or some default value
            elif col in ['lanes', 'maxspeed', 'length', 'width']:
                df_for_bq[col] = None
            elif col in ['oneway', 'reversed']:
                df_for_bq[col] = False
            else:
                df_for_bq[col] = None
    
    # Ensure the DataFrame has all required columns in the correct order
    final_df = df_for_bq[final_columns]
    
    # Log final DataFrame info
    logging.info(f"Final DataFrame shape: {final_df.shape}")
    logging.info(f"Final DataFrame columns: {final_df.columns.tolist()}")
    logging.info(f"Sample of town_code values: {final_df['town_code'].head().tolist() if 'town_code' in final_df.columns else 'town_code column not found'}")

    return final_df 