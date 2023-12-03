#! /usr/bin/env nix-shell
#! nix-shell -i python3 ./shell.nix

import base64
import datetime
import logging

from influxdb import InfluxDBClient
import requests
import click

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
    assert r.status_code == 200, f'Error getting token: {r.text}'
    results = r.json()
    assert 'access_token' in results
    token = results['access_token']
    expires_in = results['expires_in']
    global TOKEN, TOKEN_EXPIRY_TIME
    TOKEN = token
    TOKEN_EXPIRY_TIME = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
    logger.debug(f'Got new token \'{TOKEN}\' with expire time {TOKEN_EXPIRY_TIME}')


def get_history_data(start_time, end_time, mac_addr, offset, limit):
    r = requests.get(f'{QINGPING_API_BASE_URL}/devices/data?mac={mac_addr}&start_time={start_time}&end_time={end_time}&timestamp={int(datetime.datetime.now().timestamp() * 1000)}&limit={limit}&offset={offset}', headers={
        'Authorization': 'Bearer ' + TOKEN,
        'Content-Type': 'application/json'
    })
    assert r.status_code == 200, f'Error getting data: {r.text}'
    results = r.json()
    logger.info(f'Data has {results["total"]} items, current query has {len(results["data"])} items.')
    return results


def upload_batch_data(data, mac_addr):
    points = []
    for d in data:
        if 'timestamp' not in d:
            logger.warning(f'No timestamp in data item: {d}')
            continue
        points.append({
            'measurement': INFLUX_MEASUREMENT,
            'tags': {
                'mac': mac_addr
            },
            'time': d['timestamp']['value'],
            'fields': {k: float(v['value']) for k, v in d.items() if k != 'timestamp'}
        })
    
    logger.info(f'Writing data for device with MAC {mac_addr}: {len(points)} items')
    INFLUX_CLIENT.write_points(points, time_precision='s')


@click.command()
@click.option('--begin', type=click.DateTime(), help='Begin time (UTC+8)')
@click.option('--end', type=click.DateTime(), help='End time in format, default to now (UTC+8)', default=datetime.datetime.now())
# @click.option('--interval', help='Data interval in seconds, used to partition time range and avoid exceeding API limit', default=60)
@click.option('--batch-size', help='Batch size for each query & upload', default=200)
@click.argument('mac_addr', nargs=1)
def upload_data(begin, end, mac_addr, batch_size):

    if begin is None:
        logger.error('You must specify begin time.')
        exit(1)

    if begin > end:
        logger.error('Begin time must be earlier than end time.')
        exit(1)

    # total_seconds = (end - begin).total_seconds()
    # batches = int(total_seconds / interval / batch_size) + 1
    # logger.info(f'Uploading data from {begin} to {end}: total {total_seconds} seconds / {interval}s / {batch_size} = {batches} batches.')
    
    logger.info(f'Uploading data from {begin} to {end}')

    if TOKEN is None or TOKEN_EXPIRY_TIME is None or datetime.datetime.now() > TOKEN_EXPIRY_TIME:
        refresh_token()

    current_offset = 0
    try:
        results = get_history_data(int(begin.timestamp()), int(end.timestamp()), mac_addr, 0, 1)
        total = results['total']
        if total == 0:
            logger.warning(f'No data fetched: {results}')
            return

        while current_offset < total:
            # start_time = begin + datetime.timedelta(seconds=i * interval * batch_size)
            # end_time = min(begin + datetime.timedelta(seconds=(i + 1) * interval * batch_size), end)
            logger.info(f'Processing batch: {current_offset} to {current_offset + batch_size} / {total}')
            results = get_history_data(int(begin.timestamp()), int(end.timestamp()), mac_addr, current_offset, batch_size)
            data = results['data']
            first_time = datetime.datetime.fromtimestamp(data[0]['timestamp']['value'])
            last_time = datetime.datetime.fromtimestamp(data[-1]['timestamp']['value'])
            logger.info(f'Batch time range: {first_time} to {last_time}')
            upload_batch_data(data, mac_addr)
            current_offset += len(data)
    except Exception as e:
        logger.error(f'Error occurred: {e}')


if __name__ == '__main__':
    INFLUX_CLIENT = InfluxDBClient(INFLUX_HOST, INFLUX_PORT, INFLUX_USERNAME, INFLUX_PASSWORD, INFLUX_DATABASE)
    upload_data()
