# tyrePressureTracker

## Goal

The target for this project is to be able to collect inexpensive tyre pressure
sensors available from Aliexpress and send those data to home assistant for monitoring and generating automated alerts if necessary

## Architecture

The application runs on a Raspberrypi. It's using [BLEAK](https://github.com/hbldh/bleak) to collect data and [paho-mqtt](http://www.eclipse.org/paho/) to push on the network via MQTT. 

## Getting started

```console
   > git clone https://github.com/blauret/tyrePressureTracker.git
   > cd tyrePressureTracker
   > source bootstrap.sh
   > python tyrePressureTracker.py
```

## LICENSE

See [LICENSE](LICENSE)