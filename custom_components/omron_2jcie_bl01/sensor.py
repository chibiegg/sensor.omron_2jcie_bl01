"""Omron Electronics 2JCIE-BL01 BLE Environmental Sensor Integration"""
import logging
import struct
from threading import Thread

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, ENTITY_ID_FORMAT
from homeassistant.const import (CONF_MAC, CONF_FRIENDLY_NAME,
                                 DEVICE_CLASS_BATTERY, DEVICE_CLASS_HUMIDITY,
                                 DEVICE_CLASS_PRESSURE,
                                 DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_SIGNAL_STRENGTH,
                                 DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity

from bluepy.btle import (BTLEException, DefaultDelegate, Scanner)

_LOGGER = logging.getLogger(__name__)

# regex constants for configuration schema
MAC_REGEX = "(?i)^(?:[0-9A-F]{2}[:]){5}(?:[0-9A-F]{2})$"

CONF_DEVICES = "devices"

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_DEVICES): cv.schema_with_slug_keys(DEVICE_SCHEMA)}
)

devices = {}

class BLEScanDelegate(DefaultDelegate):

    def __init__(self):
        super().__init__()

    def parseAdvatiseData(self, data):
        pack_format = '<BhhhhhhhhhB'
        (seq, temp, humid, light, uv, press, noise, discomfort, heat, rfu, batt) = struct.unpack(pack_format, bytes.fromhex(data[4:]))
        return {
            "sequence": seq,
            "temperature": temp / 100.0, # [deg C]
            "humidity": humid / 100.0, # Relative humidity [%]
            "illuminance": light, # [lx]
            "uv": uv / 100.0,
            "pressure": press / 10.0, # [hPa]
            "sound_noise": noise / 100.0, # [dB]
            "discomfort_index": discomfort / 100.0,
            "heat_stroke": heat / 100.0,
            "battery_voltage": (batt + 100.0) / 100.0, # [V]
        }

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev or isNewData:
            for (adtype, desc, value) in dev.getScanData():
                # print(adtype, desc, value)
                if desc == 'Manufacturer' and value[0:4] == 'd502':
                    addr = dev.addr.lower()
                    parsed_data = self.parseAdvatiseData(value)
                    parsed_data.update({
                        "rssi": dev.rssi,
                        "mac": addr,
                    })
                    print(addr, parsed_data)

                    if addr in devices:
                        entities = devices[addr]
                        for key, value in parsed_data.items():
                            if key in entities:
                                setattr(entities[key], "_state", value)
                                entities[key].schedule_update_ha_state()



class BLEScanThread(Thread):
    def __init__(self, config):
        """Initiate BLEScanThread thread."""
        _LOGGER.debug("BLEScanThread thread: Init")
        super().__init__()
        self.config = config
        _LOGGER.debug("BLEScanThread thread: Init finished")


    def run(self):
        """Run BLEScanThread thread."""
        _LOGGER.debug("BLEScanThread thread: Run")

        scanner = Scanner().withDelegate(BLEScanDelegate())
        while True:
            try:
                scanner.scan(10)
            except BTLEException:
                _LOGGER.exception('BTLE Exception while scannning.')


        _LOGGER.debug("BLEScanThread thread: Run finished")

    def shutdown(self, *args, **kwargs):
        pass


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    _LOGGER.debug("Starting")
    firstrun = True


    scanner = BLEScanThread(config)
    hass.bus.listen("homeassistant_stop", scanner.shutdown)
    scanner.start()

    sensors = []

    for object_id, device_config in config[CONF_DEVICES].items():

        device_sensors = {
            "temperature": TemperatureSensor(object_id, device_config[CONF_FRIENDLY_NAME]),
            "humidity": HumiditySensor(object_id, device_config[CONF_FRIENDLY_NAME]),
            "pressure": PressureSensor(object_id, device_config[CONF_FRIENDLY_NAME]),
            "uv": UVSensor(object_id, device_config[CONF_FRIENDLY_NAME]),
            "sound_noise": SoundNoiseSensor(object_id, device_config[CONF_FRIENDLY_NAME]),
            "illuminance": IlluminanceSensor(object_id, device_config[CONF_FRIENDLY_NAME]),
            "discomfort_index": DiscomfortIndexSensor(object_id, device_config[CONF_FRIENDLY_NAME]),
            "battery_voltage": BatterySensor(object_id, device_config[CONF_FRIENDLY_NAME]),
            "heat_stroke": HeatStrokeSensor(object_id, device_config[CONF_FRIENDLY_NAME]),
            "rssi": RSSISensor(object_id, device_config[CONF_FRIENDLY_NAME]),
        }

        devices[device_config[CONF_MAC].lower()] = device_sensors
        sensors += list(device_sensors.values())


    print(sensors)
    add_entities(sensors)

    # Return successful setup
    return True


class BaseEntity(Entity):
    def __init__(self, object_id, name):
        """Initialize the sensor."""
        self._state = None
        self._battery = None
        self._name = name
        self._unique_id = object_id
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._device_state_attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ""

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device_state_attributes

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def force_update(self):
        """Force update."""
        return True

class TemperatureSensor(BaseEntity):
    """Representation of a sensor."""

    def __init__(self, object_id, name):
        """Initialize the sensor."""
        super().__init__(object_id + "_temp", name + " 温度")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TEMPERATURE


class HumiditySensor(BaseEntity):
    """Representation of a Sensor."""

    def __init__(self, object_id, name):
        """Initialize the sensor."""
        super().__init__(object_id + "_humid", name + " 湿度")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "%"

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_HUMIDITY

class PressureSensor(BaseEntity):
    """Representation of a Sensor."""

    def __init__(self, object_id, name):
        """Initialize the sensor."""
        super().__init__(object_id + "_press", name + " 気圧")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "hPa"

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_PRESSURE

class UVSensor(BaseEntity):
    """Representation of a Sensor."""

    def __init__(self, object_id, name):
        """Initialize the sensor."""
        super().__init__(object_id + "_uv", name + " UV")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "pt"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:weather-sunny"

class SoundNoiseSensor(BaseEntity):
    """Representation of a Sensor."""

    def __init__(self, object_id, name):
        """Initialize the sensor."""
        super().__init__(object_id + "_noise", name + " ノイズ")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "dB"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:microphone"


class DiscomfortIndexSensor(BaseEntity):
    """Representation of a Sensor."""

    def __init__(self, object_id, name):
        """Initialize the sensor."""
        super().__init__(object_id + "_discomfort", name + " 不快指数")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "pt"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:emoticon-sad"

class HeatStrokeSensor(BaseEntity):
    """Representation of a Sensor."""

    def __init__(self, object_id, name):
        """Initialize the sensor."""
        super().__init__(object_id + "_heat_stroke", name + " 熱中症指数")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "pt"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:exclamation"

class IlluminanceSensor(BaseEntity):
    """Representation of a Sensor."""

    def __init__(self, object_id, name):
        """Initialize the sensor."""
        super().__init__(object_id + "_illumi", name + " 照度")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "lx"

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_ILLUMINANCE

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:white-balance-sunny"

class BatterySensor(BaseEntity):
    """Representation of a Sensor."""

    def __init__(self, object_id, name):
        """Initialize the sensor."""
        super().__init__(object_id + "_batt", name + " 電池")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "V"

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_BATTERY

class RSSISensor(BaseEntity):
    """Representation of a Sensor."""

    def __init__(self, object_id, name):
        """Initialize the sensor."""
        super().__init__(object_id + "_rssi", name + " RSSI")

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "dBm"

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_SIGNAL_STRENGTH
