# qingping-api-influxdb-forwarder

Forward data from [Qingping API](https://developer.qingping.co/main/openApi) to InfluxDB (v1.x).

## Usage

```bash
python3 -m pip install -r requirements.txt # skip if using nix
cp config.example.py config.py
vim config.py # fill in your own config
python3 main.py # ./main.py in Nix
```

You can use systemd to daemonize this script.

## Configuration

All configuration items are in `config.py`. Specifically:

* `QINGPING_API_{KEY,SECRET}` can be obtained from [Qingping developer console](https://developer.qingping.co/personal/permissionApply).
* `POLL_INTERVAL` should be at least the upload interval of your device, which can be modified by `/v1/apis/devices/settings` API described in [documentation](https://developer.qingping.co/main/openApi).
