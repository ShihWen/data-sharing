from __future__ import annotations

import pendulum
import json

from airflow.models.dag import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook

from utils.boundary_processing import process_city_boundaries

# This is a placeholder for the TDX API fetching logic you provided
def get_tdx_result(app_id, app_key, auth_url, url):
    # In a real implementation, the Auth and Data classes would be here
    # or in a shared utility file. For simplicity, we simulate the output.
    print(f"Simulating API call to {url}")
    # This is a simplified version of the real API output
    return {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'geometry': {
                'type': 'MultiPolygon',
                'coordinates': [[[[121.569, 25.197], [121.637, 25.173], [121.61, 25.108], [121.583, 24.993], [121.465, 25.048], [121.52, 25.195], [121.569, 25.197]]]]
            },
            'properties': {
                'City': 'Taipei',
                'CityName': '臺北市'
            }
        }]
    }

def fetch_and_save_boundaries_to_gcs(**context):
    """
    Fetches city, district, and village boundaries from the TDX API
    and saves the raw JSON to GCS (Bronze layer).
    """
    execution_date = context["ds"]
    bucket_name = Variable.get("gcs_data_lake_bucket")
    gcs_hook = GCSHook()
    
    # In a real implementation, these would be fetched from Airflow Variables/Secrets
    app_id = "YOUR_APP_ID"
    app_key = "YOUR_APP_KEY"
    auth_url = "YOUR_TDX_AUTH_URL"
    
    urls = {
        "city": "https://tdx.transportdata.tw/api/basic/V3/Map/District/Boundary/City?%24format=GEOJSON",
        "district": "https://tdx.transportdata.tw/api/basic/V3/Map/District/Boundary/Town?%24format=GEOJSON",
        "village": "https://tdx.transportdata.tw/api/basic/V3/Map/District/Boundary/Village?%24format=GEOJSON"
    }
    
    gcs_paths = {}
    for level, url in urls.items():
        print(f"Fetching {level} boundaries...")
        data = get_tdx_result(app_id, app_key, auth_url, url)
        
        file_name = f"reference/bronze/boundaries/{level}_{execution_date}.json"
        gcs_hook.upload(
            bucket_name=bucket_name,
            object_name=file_name,
            data=json.dumps(data, ensure_ascii=False)
        )
        print(f"Saved raw {level} data to gs://{bucket_name}/{file_name}")
        gcs_paths[level] = file_name
    
    context["ti"].xcom_push(key="gcs_paths", value=gcs_paths)


def process_boundaries_to_silver(**context):
    """
    Reads the raw city boundary JSON file from GCS, transforms it,
    and loads it into the reference.dim_cities table.
    """
    gcs_paths = context["ti"].xcom_pull(task_ids="fetch_and_save_boundaries_to_gcs", key="gcs_paths")
    city_gcs_path = gcs_paths.get("city")
    
    if not city_gcs_path:
        raise ValueError("GCS path for city boundaries not found in XComs.")

    gcs_hook = GCSHook()
    bq_hook = BigQueryHook()
    credentials = bq_hook.get_credentials()
    bucket_name = Variable.get("gcs_data_lake_bucket")
    project_id = Variable.get("gcp_project_id")

    print(f"Downloading city boundaries from gs://{bucket_name}/{city_gcs_path}")
    raw_data = gcs_hook.download_as_byte_array(
        bucket_name=bucket_name,
        object_name=city_gcs_path,
    ).decode('utf-8')
    
    print("Transforming city boundaries...")
    gdf = process_city_boundaries(raw_data)

    if gdf.empty:
        print("No city data to upload. Skipping.")
        return

    print(f"Uploading {len(gdf)} records to reference.dim_cities...")
    gdf.to_gbq(
        destination_table="reference.dim_cities",
        project_id=project_id,
        credentials=credentials,
        if_exists='replace'
    )
    print("Successfully loaded data into reference.dim_cities.")


with DAG(
    dag_id="reference_boundaries_source_to_silver",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule="@monthly",
    catchup=False,
    tags=["reference", "silver", "dimensions"],
    default_args={
        "owner": "data_engineering",
        "retries": 1,
        "retry_delay": pendulum.duration(minutes=10),
    },
) as dag:

    fetch_bronze_data = PythonOperator(
        task_id="fetch_and_save_boundaries_to_gcs",
        python_callable=fetch_and_save_boundaries_to_gcs,
    )

    process_silver_data = PythonOperator(
        task_id="process_boundaries_to_silver",
        python_callable=process_boundaries_to_silver,
    )

    fetch_bronze_data >> process_silver_data 