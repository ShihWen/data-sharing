import json
import boto3
import pandas as pd
import os
import awswrangler as wr
# from botocore.exceptions import ClientError
import requests


##### MRT Station ######

# TDX helper class
class Auth():

    def __init__(self, app_id, app_key):
        self.app_id = app_id
        self.app_key = app_key

    def get_auth_header(self):
        content_type = 'application/x-www-form-urlencoded'
        grant_type = 'client_credentials'

        return{
            'content-type' : content_type,
            'grant_type' : grant_type,
            'client_id' : self.app_id,
            'client_secret' : self.app_key
        }


class Data():

    def __init__(self, app_id, app_key, auth_response):
        self.app_id = app_id
        self.app_key = app_key
        self.auth_response = auth_response

    def get_data_header(self):
        auth_JSON = json.loads(self.auth_response.text)
        #print(f"method auth_JSON in class Data, the auth_JSON is {auth_JSON}")
        access_token = auth_JSON.get('access_token')
        #print(f"method get_data_header in class Data, the access_token is {access_token}")

        return{
            'authorization': 'Bearer '+access_token
        }

def get_tdx_result(app_id=os.environ['tdx_client_id'], 
                   app_key=os.environ['tdx_client_secret'], 
                   auth_url=os.environ['tdx_auth_url'],
                   url=None):
  a = Auth(app_id, app_key)
  auth_response = requests.post(auth_url, a.get_auth_header())
  d = Data(app_id, app_key, auth_response)
  data_response = requests.get(url, headers=d.get_data_header()) 
  
  return json.loads(data_response.text)   



def get_existing_station_file()->list:
    '''
    Args: 
        --
    
    Returns:
        A list of existing station and exit file
    '''
    s3 = boto3.resource('s3')
    bucket = s3.Bucket('online-data-lake-thirty-three')

    bucket_object = bucket.objects.filter(Prefix='mrt-station/mrt')
    if bucket_object != []:
        objects = [obj.key.split('_')[1]+'_'+obj.key.split('_')[2] for obj in bucket_object]
        return objects#'_'.join(objects)
    return []


def get_station_file(station_data:list)->list:
    '''
    Get station file
    '''
    jdata = get_tdx_result(url="https://tdx.transportdata.tw/api/basic/v2/Rail/Metro/Station/TRTC?%24top=300&%24format=JSON")
    station_version_id = f"station_V{jdata[0]['VersionID']}"

    if station_version_id not in station_data:
        df_station = pd.json_normalize(jdata, sep='_')

        wr.s3.to_parquet(
            df=df_station,
            path=os.environ['s3_mrt_station_target_bucket'],
            dataset=True,
            filename_prefix=f'mrt_{station_version_id}_'
        )
        return station_version_id
    return 'no updated station file'
    


def get_station_exit_file()->list:
    '''
    Get exit file
    '''