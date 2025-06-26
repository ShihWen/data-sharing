import os
import json
import requests
import pandas as pd
from google.cloud import storage, secretmanager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

def get_secret(secret_id, project_id, version_id="latest"):
    """
    Retrieves a secret from Google Secret Manager.
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

class Auth:
    def __init__(self, app_id, app_key):
        self.app_id = app_id
        self.app_key = app_key

    def get_auth_header(self):
        return {
            'content-type': 'application/x-www-form-urlencoded',
        }

    def get_auth_data(self):
        return {
            'grant_type': 'client_credentials',
            'client_id': self.app_id,
            'client_secret': self.app_key
        }

class Data:
    def __init__(self, auth_response):
        self.auth_response = auth_response

    def get_data_header(self):
        auth_JSON = json.loads(self.auth_response.text)
        access_token = auth_JSON.get('access_token')
        return {
            'authorization': 'Bearer ' + access_token
        }

def get_tdx_result(app_id, app_key, auth_url, url):
    """
    Authenticates with TDX and fetches data from the specified URL.
    """
    try:
        a = Auth(app_id, app_key)
        
        # Get token
        auth_response = requests.post(auth_url, data=a.get_auth_data(), headers=a.get_auth_header())
        auth_response.raise_for_status()
        
        d = Data(auth_response)
        
        # Get data
        data_response = requests.get(url, headers=d.get_data_header())
        data_response.raise_for_status()
        
        return data_response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during TDX API request: {e}")
        if e.response:
            logging.error(f"Response status: {e.response.status_code}")
            logging.error(f"Response text: {e.response.text}")
        raise

def get_existing_station_file_versions(bucket_name, prefix):
    """
    Lists all file versions from a GCS bucket based on blob names.
    e.g. mrt_station_ntmc_V1_... -> V1
    """
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix)
    
    versions = set()
    for blob in blobs:
        # e.g. mrt_station_ntmc_V22.0_xxxx.parquet -> V22.0
        try:
            version = blob.name.split('_')[3]
            versions.add(version)
        except IndexError:
            # Ignore files that don't match the expected format
            continue
            
    return versions

def main(event, context):
    """
    Cloud Function entry point.
    """
    try:
        project_id = os.environ['GCP_PROJECT']
        gcs_bucket = os.environ['GCS_BUCKET']
        tdx_auth_url = os.environ['TDX_AUTH_URL']
        
        logging.info(f"Project ID: {project_id}, GCS Bucket: {gcs_bucket}")

        tdx_client_id = get_secret("tdx_client_id", project_id)
        tdx_client_secret = get_secret("tdx_client_secret", project_id)
        
        station_url = "https://tdx.transportdata.tw/api/basic/v2/Rail/Metro/Station/NTMC?%24top=300&%24format=JSON"

        logging.info("Fetching data from TDX...")
        jdata_station = get_tdx_result(
            app_id=tdx_client_id,
            app_key=tdx_client_secret,
            auth_url=tdx_auth_url,
            url=station_url
        )

        if not jdata_station:
            logging.info("No station data received from TDX.")
            return "No data from TDX", 200

        station_version_id = f"V{jdata_station[0]['VersionID']}"
        logging.info(f"Current station data version from TDX: {station_version_id}")

        existing_versions = get_existing_station_file_versions(gcs_bucket, prefix='mrt_station_ntmc/mrt_station_ntmc')

        if station_version_id not in existing_versions:
            logging.info(f"New station data version {station_version_id} found. Processing and uploading to GCS.")
            
            df_station = pd.json_normalize(jdata_station, sep='_')
            
            file_name = f'mrt_station_ntmc_{station_version_id}_{pd.Timestamp.now().strftime("%Y%m%d%H%M%S")}.parquet'
            gcs_path = f"gs://{gcs_bucket}/mrt_station_ntmc/{file_name}"

            logging.info(f"Writing data to {gcs_path}...")
            df_station.to_parquet(gcs_path)
            
            logging.info("Upload complete.")
            return "Upload complete.", 200
        else:
            logging.info(f"Station data version {station_version_id} already exists in GCS. No action taken.")
            return "Data already exists", 200
            
    except KeyError as e:
        logging.error(f"Missing environment variable: {e}")
        return f"Missing environment variable: {e}", 500
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
        return "Internal Server Error", 500 