import json
import requests
import logging

class Auth():
    def __init__(self, app_id, app_key):
        self.app_id = app_id
        self.app_key = app_key

    def get_auth_header(self):
        content_type = 'application/x-www-form-urlencoded'
        grant_type = 'client_credentials'
        return {
            'content-type': content_type,
            'grant_type': grant_type,
            'client_id': self.app_id,
            'client_secret': self.app_key
        }

class Data():
    def __init__(self, app_id, app_key, auth_response):
        self.app_id = app_id
        self.app_key = app_key
        self.auth_response = auth_response

    def get_data_header(self):
        try:
            auth_JSON = json.loads(self.auth_response.text)
            access_token = auth_JSON.get('access_token')
            return {
                'authorization': 'Bearer ' + access_token,
                'Accept-Encoding': 'gzip'
            }
        except json.JSONDecodeError:
            logging.error("Failed to decode auth response: %s", self.auth_response.text)
            raise

def get_tdx_data(app_id, app_key, auth_url, url=None):
    """
    Authenticates with the TDX API and fetches data from a given URL.
    """
    try:
        a = Auth(app_id, app_key)
        auth_response = requests.post(auth_url, a.get_auth_header())
        auth_response.raise_for_status()

        d = Data(app_id, app_key, auth_response)
        data_response = requests.get(url, headers=d.get_data_header())
        data_response.raise_for_status()
        
        return data_response.json()
    except requests.exceptions.RequestException as e:
        logging.error("TDX API request failed: %s", e)
        if e.response:
            logging.error("Response content: %s", e.response.text)
        raise 