# -*- coding: utf-8 -*-
"""
Tyre Pressure tracker sending data over MQTT.

    Target homeassistant MQTT integration.
"""

import asyncio
import datetime
import json
import logging
import time

import paho.mqtt.client as mqtt
from bleak import BleakScanner

discoveryPayload = {
    "name": "Pressure Sensor",
    "stat_t": "~SENSOR",
    "avty_t": "pressureSensor/tele/LWT",
    "pl_avail": "Online",
    "pl_not_avail": "Offline",
    "unit_of_meas": "\xb0C",
    "val_tpl": "{{value_json.Temperature}}",
    # "dev_cla":"generic",
    "uniq_id": "a_unique_id",
    "device": {
        "identifiers": ["a_unique_id"],
        "name": "Pressure sensor",
        "model": "Pressure",
        "sw_version": "1.0",
        "manufacturer": "RipCup",
    },
    "~": "pressureSensor/tele/",
}


# create logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("scanner")
logger.setLevel(logging.DEBUG)

devList = {}


class presSensor(object):
    """Container for pressure sensor data."""

    def __init__(self, name, p, t, b, u):
        """Inialize the pressure sensor container.

        Args:
         b: battery voltage
         p: Pressure
         t: temperature
         u: last update time
        """
        self.__name = name  # name
        self.__b = b  # battery voltage
        self.__p = p  # pressure
        self.__t = t  # temperature
        self.__u = u  # update time

    def __str__(self):
        """Return formatred string."""
        return "| {} | {:.2f} | {:.2f} |  {:03d} | {} |\n".format(
            self.name, self.p, self.t, self.b, self.u
        )

    @property
    def name(self):
        """Name property."""
        return self.__name

    @property
    def b(self):
        """Battery level property."""
        return self.__b

    @property
    def p(self):
        """Pressure property."""
        return self.__p

    @property
    def t(self):
        """Temperature property."""
        return self.__t

    @property
    def u(self):
        """Update time property."""
        return self.__u

    @u.setter
    def u(self, u):
        self.__u = u

    def toJSON(self):
        """Convert object to JSON."""
        return {
            "name": self.name,
            "Pressure": int(1000 * self.p),
            "Temperature": self.t,
            "Battery": self.b,
            "updated": str(self.u),
        }


def set_online(client):
    """Publish on MQTT the device is online."""
    client.publish(discoveryPayload["avty_t"], discoveryPayload["pl_avail"], 0, True)


def postStatus(client, dev):
    """Publish on MQTT telemetry update."""
    client.publish(
        "{}/tele/SENSOR".format(devList[dev].name), json.dumps(devList[dev].toJSON())
    )


def postConfig(client, device):
    """Publish newt device on MQTT."""
    devConfig = {
        "Temperature": {
            "class": "temperature",
            "unit": "\xb0C",
            "tpl": "{{value_json.Temperature}}",
        },
        "Pressure": {
            "class": "pressure",
            "unit": "mbar",
            "tpl": "{{value_json.Pressure}}",
        },
        "Battery": {"class": "battery", "unit": "%", "tpl": "{{value_json.Battery}}"},
    }

    dev = devList[device].name
    print("publish config for {}".format(dev))
    discoveryPayload["device"]["identifiers"] = [dev]
    discoveryPayload["~"] = "{}/tele/".format(dev)

    for conf in devConfig:
        discoveryPayload["device"]["name"] = "{} {}".format(dev, conf)
        discoveryPayload["name"] = "{} {}".format(dev, conf)
        discoveryPayload["uniq_id"] = "{}_{}".format(dev, conf)
        discoveryPayload["dev_cla"] = devConfig[conf]["class"]
        discoveryPayload["unit_of_meas"] = devConfig[conf]["unit"]
        discoveryPayload["val_tpl"] = devConfig[conf]["tpl"]

        client.publish(
            "homeassistant/sensor/{}_{}/config".format(dev, conf),
            json.dumps(discoveryPayload),
            0,
            True,
        )
        set_online(client)
        time.sleep(1)


async def run():
    """Asyncio runner."""
    mqttLogger = logging.getLogger("mqttClient")
    mqttLogger.setLevel(logging.DEBUG)

    # Connect to the MQTT broker
    client = mqtt.Client()

    def on_connect(client, userdata, flags, rc):
        set_online(client)

    client.enable_logger(logger=mqttLogger)
    client.on_connect = on_connect
    client.will_set(
        discoveryPayload["avty_t"], discoveryPayload["pl_not_avail"], 0, retain=False
    )
    client.connect("192.168.1.10", 1883, 60)

    scanner = BleakScanner()

    def display_status():
        def add_line():
            return "-" * 66 + "\n"

        buf = "\n"
        buf += add_line()
        buf += "| Name        | P (B)| T (C) | B (%)| Update                     |\n"
        buf += "|================================================================|\n"

        for dev in devList:
            buf += str(devList[dev])

        buf += "|================================================================|\n"
        logger.info(buf)

    def decodeMftData(name, mftData):
        pressure = mftData[1] / 32
        temp = mftData[2] - 55
        battery = mftData[0] * 0.01 + 1.23
        if battery >= 3.0:
            battery = 3.0
        # 3.0V is 100%, 2.6V is 0%
        battery = int(100 * (battery - 2.6) / 0.4)
        return presSensor(name, pressure, temp, battery, datetime.datetime.now())

    def detection_callback(*args):

        msg = args[0]
        if msg.member == "InterfacesAdded":
            # print('================InterfacesAdded========================')
            devList[msg.body[0]] = decodeMftData(
                msg.body[1]["org.bluez.Device1"]["Name"],
                msg.body[1]["org.bluez.Device1"]["ManufacturerData"][172],
            )
            postConfig(client, msg.body[0])
            postStatus(client, msg.body[0])

        elif msg.member == "PropertiesChanged":
            # print('================PropertiesChanged========================')
            # print(msg.body)
            if msg.path in devList:
                if "ManufacturerData" in msg.body[1]:
                    # get name
                    name = devList[msg.path].name
                    # update the data
                    devList[msg.path] = decodeMftData(
                        name, msg.body[1]["ManufacturerData"][172]
                    )

                else:
                    # update the timestamp
                    devList[msg.path].u = datetime.datetime.now()

                postStatus(client, msg.path)
            else:
                print("Properties changed for unknown devices")
                # for att in dir(msg):
                #     print(att,getattr(msg,att))
                pass

        elif msg.member == "InterfacesRemoved":
            # we don't care
            return
        else:
            print("================else========================")
            print("{}, {}, {}".format(datetime.datetime.now(), msg.member, msg.body))
            pass

        display_status()

    scanner.register_detection_callback(detection_callback)
    await scanner.set_scanning_filter(
        filters={"UUIDs": ["0000fbb0-0000-1000-8000-00805f9b34fb"]}
    )
    await scanner.start()
    print("scan started", datetime.datetime.now())

    while True:
        # run mqtt client loop
        client.loop()
        await asyncio.sleep(1)


asyncio.run(run())
