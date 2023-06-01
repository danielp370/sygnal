"""Support for the Livezi/Sygnal Chatterbox HVAC."""
import aiohttp
import async_timeout
import asyncio
import datetime
import logging
import time
import sys
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import async_get_platforms

from .chatterbox import SygnalClient, SygnalApi

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import CONF_HOST, CONF_NAME, TEMP_CELSIUS, Platform
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = datetime.timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
  vol.Optional(CONF_HOST, default='chatterbox.local'): cv.string,
  vol.Optional(CONF_NAME, default='chatterbox'): cv.string,
})

HVAC_MODE_TO_SYGNAL = {
    HVAC_MODE_OFF       : 'off',
    HVAC_MODE_FAN_ONLY  : 'vent',
    HVAC_MODE_HEAT      : 'heat',
    HVAC_MODE_COOL      : 'cool',
    HVAC_MODE_HEAT_COOL : 'auto',
}
HVAC_MODE_FROM_SYGNAL = {v:k for k,v in HVAC_MODE_TO_SYGNAL.items()}

FAN_MODE_TO_SYGNAL = {
    FAN_AUTO:   'auto',
    FAN_LOW:    'low',
    FAN_MEDIUM: 'medium',
    FAN_HIGH:   'high',
}
FAN_MODE_FROM_SYGNAL = {v:k for k,v in FAN_MODE_TO_SYGNAL.items()}

def get_platform(hass, name):
    platform_list = async_get_platforms(hass, name)

    for platform in platform_list:
        if platform.domain == name:
            return platform

    return None

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    host = config[CONF_HOST]
    name = config[CONF_NAME]
    client = SygnalClient(host, async_get_clientsession(hass, verify_ssl=False))
    api = SygnalApi(client)

    # Poll at setup time to get unique id and zone info
    await api.async_update()

    async_add_entities([SygnalClimate(name, api)])

    # TODO: possible race here if switch does not (yet) exist
    switch_platform = get_platform(hass, Platform.SWITCH)
    zones = []
    for zone in api.zones:
      zones.append(SygnalZone(name, zone, api))
    await switch_platform.async_add_entities(zones)


class SygnalZone(SwitchEntity):
    """Represents a single zone switch on a Livezi/Sygnal HVAC."""
    def __init__(self, name, zone, api):
      self._name = name
      self._zone = zone
      self._api = api

    @property
    def name(self):
      return '%s_%s' % (self._name, self._zone)

    @property
    def is_on(self):
      return self._api.zone_is_enabled(self._zone)

    @property
    def unique_id(self):
      return '%s_%s' % (self._api.unique_id, self._zone)

    async def async_turn_on(self, **kwargs):
      await self._api.async_set_zone_enabled(self._zone, True)

    async def async_turn_off(self, **kwargs):
      await self._api.async_set_zone_enabled(self._zone, False)

    async def async_update(self):
        await self._api.async_update()


class SygnalClimate(ClimateEntity):
    """Represents a Livezi/Sygnal HVAC."""

    def __init__(self, name, api):
        self._name = name
        self._api = api

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

    @property
    def icon(self):
        return "mdi:air-conditioner";

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def unique_id(self):
        return self._api.unique_id

    @property
    def device_state_attributes(self):
        return {
          'outside_coil_temperature': self._api.outside_coil_temperature,
          'inside_coil_temperature': self._api.inside_coil_temperature,
          'compressor_loading': self._api.compressor_loading,
        }

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def precision(self):
        # All temps have 0.5C precision
        return 0.5

    @property
    def min_temp(self):
        return 15

    @property
    def max_temp(self):
        return 30

    @property
    def target_temperature_step(self):
        return 0.5

    @property
    def current_temperature(self):
        return self._api.current_temperature

    @property
    def target_temperature(self):
        return self._api.target_temperature

    @property
    def hvac_mode(self):
        if self._api.hvac_mode in HVAC_MODE_FROM_SYGNAL:
          return HVAC_MODE_FROM_SYGNAL[self._api.hvac_mode]
        else:
          return HVAC_MODE_HEAT_COOL

    @property
    def hvac_modes(self):
        return list(HVAC_MODE_TO_SYGNAL.keys())

    @property
    def hvac_action(self):
        return self._api.status

    @property
    def fan_mode(self):
        if self._api.fan_mode in FAN_MODE_FROM_SYGNAL:
          return FAN_MODE_FROM_SYGNAL[self._api.fan_mode]
        else:
      
          return FAN_LOW

    @property
    def fan_modes(self):
        return list(FAN_MODE_TO_SYGNAL.keys())

    @property
    def device_info(self):
        return self._api.device_info

    async def async_set_temperature(self, **kwargs):
        await self._api.async_set_temperature(kwargs['temperature'])

    async def async_set_hvac_mode(self, hvac_mode):
        await self._api.async_set_hvac_mode(HVAC_MODE_TO_SYGNAL[hvac_mode])

    async def async_set_fan_mode(self, fan_mode):
        await self._api.async_set_fan_mode(FAN_MODE_TO_SYGNAL[fan_mode])

    async def async_turn_on(self):
        await self._api.async_turn_on()

    async def async_turn_off(self):
        await self._api.async_turn_off()

    async def async_update(self):
        await self._api.async_update()

