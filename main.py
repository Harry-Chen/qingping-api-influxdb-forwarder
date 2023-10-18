#! /usr/bin/env nix-shell
#! nix-shell -i python3 ./shell.nix

import base64
import time
import datetime
import logging

from influxdb import InfluxDBClient
import requests
import schedule

from config import *


QINGPING_OAUTH_API_URL = 'https://oauth.cleargrass.com/oauth2/token'
QINGPING_API_BASE_URL = 'https://apis.cleargrass.com/v1/apis'

FORMAT = '%(asctime)s :: %(levelname)s :: %(message)s'
logging.root.setLevel(logging.INFO)
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)

TOKEN = None
TOKEN_EXPIRY_TIME = None
INFLUX_CLIENT = None


def refresh_token():
    auth_encoded = base64.b64encode((QINGPING_API_KEY + ':' + QINGPING_API_SECRET).encode('utf-8')).decode('utf-8')
    r = requests.post(QINGPING_OAUTH_API_URL, data={
        'grant_type': 'client_credentials',
        'scope': 'device_full_access'
    }, headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic ' + auth_encoded
    })
    assert r.status_code == 200
    results = r.json()
    assert 'access_token' in results
    token = results['access_token']
    expires_in = results['expires_in']
    global TOKEN, TOKEN_EXPIRY_TIME
    TOKEN = token
    TOKEN_EXPIRY_TIME = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
    logger.debug(f'Got new token \'{TOKEN}\' with expire time {TOKEN_EXPIRY_TIME}')


def get_data():
    r = requests.get(f'{QINGPING_API_BASE_URL}/devices?timestamp={int(datetime.datetime.now().timestamp() * 1000)}', headers={
        'Authorization': 'Bearer ' + TOKEN,
        'Content-Type': 'application/json'
    })
    assert r.status_code == 200
    results = r.json()
    logger.info(f'Got data from {results["total"]} devices')
    return results


def upload_device_data(device):
    info, data = device['info'], device['data']
    logger.info(f'Device info: {info}')
    status, name, mac = info['status'], info['name'], info['mac']
    # remove timestamp, keep data fields only
    if 'timestamp' not in data:
        timestamp = int(datetime.datetime.now().timestamp())
    else:
        timestamp = data['timestamp']['value']
        del data['timestamp']
    data_time = datetime.datetime.fromtimestamp(timestamp)
    
    # check existence
    r = INFLUX_CLIENT.query(f'SELECT COUNT(*) FROM {INFLUX_MEASUREMENT} WHERE mac=$mac AND time=$time', bind_params={
        'mac': mac,
        'time': timestamp * 1000000000
    })
    if len(r.keys()) != 0:
        logger.warning(f'Already have data for device \'{name}\' MAC {mac} at {data_time}, skipping...')
        return

    # upload to database
    fields = {k: float(v['value']) for k, v in data.items() if k != 'timestamp'}
    logger.info(f'Writing data for device \'{name}\' MAC {mac} at {data_time} with data: {fields}')
    INFLUX_CLIENT.write_points([{
        'measurement': INFLUX_MEASUREMENT,
        'tags': {
            'name': name,
            'mac': mac
        },
        'time': timestamp,
        'fields': fields
    }], time_precision='s')


@schedule.repeat(schedule.every(POLL_INTERVAL).seconds)
def qingping_forward():
    try:
        if TOKEN is None or TOKEN_EXPIRY_TIME is None or datetime.datetime.now() > TOKEN_EXPIRY_TIME:
            refresh_token()
        data = get_data()
        for d in data['devices']:
            upload_device_data(d)
    except Exception as e:
        logger.error(f'Error occurred: {e}')


if __name__ == '__main__':
    INFLUX_CLIENT = InfluxDBClient(INFLUX_HOST, INFLUX_PORT, INFLUX_USERNAME, INFLUX_PASSWORD, INFLUX_DATABASE)
    
    qingping_forward()
    while True:
        schedule.run_pending()
        time.sleep(1)
