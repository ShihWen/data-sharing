import json
from helper import get_existing_station_file, get_tdx_result
import awswrangler as wr
import pandas as pd
import os


## MRT Station
def mrt_station_file_list(event, context):

    event['mrt_station_file_version'] = get_existing_station_file()

    return event

def mrt_station(event, context):

    downloaded_list = []
    # station data
    jdata_station = get_tdx_result(url=os.environ['station_url'])
    station_version_id = f"station_V{jdata_station[0]['VersionID']}"

    if station_version_id not in event['mrt_station_file_version']:
        print('process station pandas...')
        df_station = pd.json_normalize(jdata_station, sep='_')
        print('process station s3...')
        wr.s3.to_parquet(
            df=df_station,
            path=os.environ['s3_mrt_station_target_bucket'],
            dataset=True,
            filename_prefix=f'mrt_{station_version_id}_'
        )
        downloaded_list.append(station_version_id)
    
    # exit data
    jdata_exit = get_tdx_result(url=os.environ['station_exit_url'])
    station_exit_version_id = f"exit_V{jdata_exit[0]['VersionID']}"

    if station_exit_version_id not in event['mrt_station_file_version']:
        print('process exit pandas...')
        df_exit = pd.json_normalize(jdata_exit, sep='_')
        print('process exit s3...')
        wr.s3.to_parquet(
            df=df_exit,
            path=os.environ['s3_mrt_station_target_bucket'],
            dataset=True,
            filename_prefix=f'mrt_{station_exit_version_id}_'
        )
        downloaded_list.append(station_exit_version_id)
    
    event['station_downloaded_data'] = downloaded_list
    
    return event
