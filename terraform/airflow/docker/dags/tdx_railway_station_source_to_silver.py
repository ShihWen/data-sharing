from __future__ import annotations

import pendulum
import json

from airflow.models.dag import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

from utils.tdx_api import get_tdx_data

def fetch_railway_stations_to_gcs(**context):
    """
    Fetches railway stations from the TDX API and saves the raw JSON to GCS.
    """
    execution_year_month = context["ds"][:7]
    bucket_name = Variable.get("gcs_data_lake_bucket")
    gcs_hook = GCSHook()
    
    file_name = f"reference/bronze/railway/stations_{execution_year_month}.json"
    
    # Check if file already exists in GCS
    if gcs_hook.exists(bucket_name=bucket_name, object_name=file_name):
        print(f"File gs://{bucket_name}/{file_name} already exists. Skipping download.")
        context["ti"].xcom_push(key="gcs_path", value=file_name)
        return
    
    app_id = Variable.get("tdx_client_id")
    app_key = Variable.get("tdx_client_secret")
    auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
    
    url = "https://tdx.transportdata.tw/api/basic/v2/Rail/TRA/Station?%24format=JSON"
        
    print("Fetching railway stations from real TDX API...")
    data = get_tdx_data(app_id, app_key, auth_url, url)
    
    gcs_hook.upload(
        bucket_name=bucket_name,
        object_name=file_name,
        data=json.dumps(data, ensure_ascii=False)
    )
    print(f"Saved raw railway stations data to gs://{bucket_name}/{file_name}")
    context["ti"].xcom_push(key="gcs_path", value=file_name)

def process_railway_stations_to_staging(**context):
    """
    Reads the raw railway station JSON file from GCS, transforms it,
    and loads it into a staging table in the railway_silver dataset.
    """
    gcs_path = context["ti"].xcom_pull(task_ids="fetch_railway_stations_to_gcs", key="gcs_path")
    
    if not gcs_path:
        raise ValueError("GCS path for railway stations not found in XComs.")

    gcs_hook = GCSHook()
    bq_hook = BigQueryHook()
    credentials = bq_hook.get_credentials()
    bucket_name = Variable.get("gcs_data_lake_bucket")
    project_id = Variable.get("gcp_project_id")

    print(f"Downloading railway stations from gs://{bucket_name}/{gcs_path}")
    raw_data = gcs_hook.download_as_byte_array(
        bucket_name=bucket_name,
        object_name=gcs_path,
    ).decode('utf-8')
    
    print("Transforming railway station data...")
    stations_data = json.loads(raw_data)
    
    # Process each station record
    processed_records = []
    current_timestamp = pendulum.now('UTC')
    
    for station in stations_data:
        # Extract nested StationName object
        station_name = station.get('StationName', {})
        
        # Create geometry from PositionLon and PositionLat
        position = station.get('StationPosition', {})
        position_lon = position.get('PositionLon')
        position_lat = position.get('PositionLat')
        
        # Create POINT geometry if coordinates are available
        geometry = None
        if position_lon is not None and position_lat is not None:
            try:
                # Validate coordinates are numeric
                lon_float = float(position_lon)
                lat_float = float(position_lat)
                # Check if coordinates are within reasonable bounds
                if -180 <= lon_float <= 180 and -90 <= lat_float <= 90:
                    geometry = f"POINT({lon_float} {lat_float})"
                else:
                    print(f"Invalid coordinates for station {station.get('StationUID', 'unknown')}: lon={lon_float}, lat={lat_float}")
                    geometry = None
            except (ValueError, TypeError) as e:
                print(f"Error parsing coordinates for station {station.get('StationUID', 'unknown')}: {e}")
                geometry = None
        
        # Parse update_time to timestamp
        update_time = None
        if station.get('UpdateTime'):
            try:
                update_time = pendulum.parse(station['UpdateTime']).to_iso8601_string()
            except:
                update_time = None
        
        # Convert version_id to integer if it exists
        version_id = station.get('VersionID')
        if version_id is not None:
            try:
                version_id = int(version_id)
            except (ValueError, TypeError):
                version_id = None
        
        record = {
            'station_uid': station.get('StationUID'),
            'station_id': station.get('StationID'),
            'station_name_zh_tw': station_name.get('Zh_tw'),
            'station_name_en': station_name.get('En'),
            'station_address': station.get('StationAddress'),
            'station_phone': station.get('StationPhone'),
            'operator_id': station.get('OperatorID'),
            'station_class': station.get('StationClass'),
            'update_time': update_time,
            'version_id': version_id,
            'geometry': geometry,
            'location_city': station.get('LocationCity'),
            'location_city_code': station.get('LocationCityCode'),
            'location_town': station.get('LocationTown'),
            'location_town_code': station.get('LocationTownCode'),
            'processed_at': current_timestamp.to_iso8601_string(),
            'valid_from_ts': current_timestamp.to_iso8601_string(),
            'valid_to_ts': '2099-12-31T23:59:59Z',  # Future date for current records
            'is_current': True,
        }
        processed_records.append(record)

    if not processed_records:
        print("No railway station data to upload. Skipping.")
        return

    # Convert to DataFrame for BigQuery upload
    import pandas as pd
    df = pd.DataFrame(processed_records)
    print(df.info())
    
    # Debug: Print data types and sample values for each column
    print("\nDataFrame dtypes:")
    for col, dtype in df.dtypes.items():
        print(f"{col}: {dtype}")
        # Print first few non-null values to check for type issues
        non_null_values = df[col].dropna().head(3)
        if len(non_null_values) > 0:
            print(f"  Sample values: {non_null_values.tolist()}")
        print()

    print(f"Uploading {len(df)} records to railway_silver.railway_station_staging...")
    
    # Define the schema to match the existing staging table exactly
    table_schema = [
        {'name': 'station_uid', 'type': 'STRING'},
        {'name': 'station_id', 'type': 'STRING'},
        {'name': 'station_name_zh_tw', 'type': 'STRING'},
        {'name': 'station_name_en', 'type': 'STRING'},
        {'name': 'station_address', 'type': 'STRING'},
        {'name': 'station_phone', 'type': 'STRING'},
        {'name': 'operator_id', 'type': 'STRING'},
        {'name': 'station_class', 'type': 'STRING'},
        {'name': 'update_time', 'type': 'TIMESTAMP'},
        {'name': 'version_id', 'type': 'INTEGER'},
        {'name': 'geometry', 'type': 'GEOGRAPHY'},
        {'name': 'location_city', 'type': 'STRING'},
        {'name': 'location_city_code', 'type': 'STRING'},
        {'name': 'location_town', 'type': 'STRING'},
        {'name': 'location_town_code', 'type': 'STRING'},
        {'name': 'processed_at', 'type': 'TIMESTAMP'},
        {'name': 'valid_from_ts', 'type': 'TIMESTAMP'},
        {'name': 'valid_to_ts', 'type': 'TIMESTAMP'},
        {'name': 'is_current', 'type': 'BOOLEAN'},
    ]
    
    try:
        df.to_gbq(
            destination_table="railway_silver.railway_station_staging",
            project_id=project_id,
            credentials=credentials,
            if_exists='replace',
            table_schema=table_schema
        )
        print("Successfully loaded data into railway_silver.railway_station_staging.")
    except Exception as e:
        print(f"Error uploading to BigQuery: {str(e)}")
        print("Attempting to upload without explicit schema...")
        # Try without explicit schema to let BigQuery infer types
        df.to_gbq(
            destination_table="railway_silver.railway_station_staging",
            project_id=project_id,
            credentials=credentials,
            if_exists='replace'
        )
        print("Successfully loaded data into railway_silver.railway_station_staging (schema inferred).")

with DAG(
    dag_id="tdx_railway_station_source_to_silver",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule="@yearly",
    catchup=False,
    tags=["tdx", "silver", "railway", "station"],
    default_args={
        "owner": "data_engineering",
        "retries": 1,
        "retry_delay": pendulum.duration(minutes=5),
    },
) as dag:

    fetch_bronze_data = PythonOperator(
        task_id="fetch_railway_stations_to_gcs",
        python_callable=fetch_railway_stations_to_gcs,
    )

    process_silver_staging = PythonOperator(
        task_id="process_railway_stations_to_staging",
        python_callable=process_railway_stations_to_staging,
    )
    
    # merge_into_silver_scd2 = BigQueryInsertJobOperator(
    #     task_id="merge_into_silver_scd2",
    #     configuration={
    #         "query": {
    #             "query": MERGE_SCD2_TOWNS.format(
    #                 project_id="{{ var.value.gcp_project_id }}",
    #                 dataset_id="reference",
    #             ),
    #             "useLegacySql": False,
    #         }
    #     },
    # )

    # insert_updated_records = BigQueryInsertJobOperator(
    #     task_id="insert_updated_records",
    #     configuration={
    #         "query": {
    #             "query": INSERT_UPDATED_TOWNS.format(
    #                 project_id="{{ var.value.gcp_project_id }}",
    #                 dataset_id="reference",
    #             ),
    #             "useLegacySql": False,
    #         }
    #     },
    # )

    fetch_bronze_data >> process_silver_staging 