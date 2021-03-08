# ZWaveJS to OpenZWave migration/renaming script

Note: This is very experimental!!! Use at your own risk! Make a snapshot first!! Report bugs!!!!

Hopefully will help make your transition from OpenZWave to ZWaveJS a little easier.

This script can be run on any device with network access to your Home Assistant instance and Python 3.8 or above. It does not have to run on the same device as your Home Assistant.

Also for real, you should really take a snapshot before you run this script.

## Get prerequisites

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

You'll also need to get an access token from you Home Assistant (Profile -> Long-Lived Access Tokens -> Create Token). Then set it as an environment variable before running this script.

```bash
export HA_ACCESS_TOKEN=yoursuperlongsupersecretaccesstoken
```

## Usage

### Run the thing (dry run)

Stop your OpenZWave addon. Set up the ZWaveJS (or ZWaveJS2Mqtt). Add the ZWaveJS integration. Then run the following to see what will happen.

```bash
python3 migrate_to_zwavejs.py
```

Consider modifying your `manual_rename_dict` to add any things that didn't get detected automatically.

### Run the thing (for real this time)

When you're feeling brave run:

```bash
python3 migrate_to_zwavejs.py --commit
```

### Abandon ship and roll back

First delete your ZWaveJS integration. Then run:

```bash
python3 migrate_to_zwavejs.py --rollback --commit
```

## License

MIT -- do what you want with it but I give you no warranties or guarantees it will do what you want.

I'd be delighted if this is helpful to other people.