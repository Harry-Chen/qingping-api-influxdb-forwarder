# qingping-api-influxdb-forwarder

Forward data from [Qingping API](https://developer.qingping.co/main/openApi) to InfluxDB (v1.x).

## Usage

```bash
python3 -m pip install -r requirements.txt # skip if using nix
cp config.example.py config.py
vim config.py # fill in your own config
python3 main.py # ./main.py in Nix, or
python3 fetch_history.py --begin 2023-11-27T13:00:00 --end 2023-12-03T12:00:00 --batch-size 1000 YOUR_MAC_ADDR
```

Scripts:

* `main.py` is used to fetch latest data from API and forward to InfluxDB. You can use systemd to daemonize it.
* `fetch_history.py` is used to fetch historical data from API and send to InfluxDB in a batched way. You can use it to fill in the gap of data when `main.py` is not running.

## Configuration

All configuration items are in `config.py`. Specifically:

* `QINGPING_API_{KEY,SECRET}` can be obtained from [Qingping developer console](https://developer.qingping.co/personal/permissionApply).
* `POLL_INTERVAL` should be at least the upload interval of your device, which can be modified by `/v1/apis/devices/settings` API described in [documentation](https://developer.qingping.co/main/openApi).
