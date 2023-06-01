"""
Library for controlling a Livezi/Sygnal Chatterbox via it's Web UI JSON interface.

The interface here is the same as that used by a 2015 JQuery web interface.
This may not work with more recent devices. YMMV.

This is provided without warranty and I take no responsibility for what you do
with this code.
 """
import datetime
import aiohttp
import asyncio
import json
import logging
import time
from typing import Dict, List, Text
import sys

_LOGGER = logging.getLogger(__name__)

_DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

HVAC_OFF  = 'off'
HVAC_VENT = 'vent'
HVAC_HEAT = 'heat'
HVAC_COOL = 'cool'
HVAC_AUTO = 'auto'

FAN_OFF = 'off'  # generally interpret this as 'undefined'.
FAN_ULTRA_LOW = 'ultra low'
FAN_LOW = 'low'
FAN_MEDIUM = 'medium'
FAN_HIGH = 'high'
FAN_AUTO = 'auto'

# zone fan speeds seem to be from 10%, with increments of 5%
ZONE_FANSPEED_RANGE = range(10,100+1,5)

class InvalidArgument(ValueError):
    pass

class SygnalClient(object):
    def __init__(self, hostname: Text, client_session):
        self._hostname = hostname
        self._client_session = client_session

    @property
    def hostname(self): 
        return self._hostname

    async def _post(self, data):
        try:
            response = await self._client_session.post("http://%s/ZPlus/file.lvjson" % self._hostname, data=data)
            data = json.loads(await response.text())
            return data
        except (aiohttp.ClientError, IndexError) as error:
          _LOGGER.error("Failed to read/write to chatterbox: %s", error)

    async def get_device_info(self) -> Dict:
        try:
            response = await self._client_session.get("http://%s/lv-lan-cboxes.json" % self._hostname)
            data = json.loads(await response.text())
            return data
        except (aiohttp.ClientError, IndexError) as error:
          _LOGGER.error("Failed to read chatterbox device info: %s", error)

    async def async_read_vram(self, offset : int, length : int) -> List[int]:
        # Only if the *entire* value being read is in valid cache will we use it.
        end = offset + length
        if offset < 0:
          raise InvalidArgument('Offset out of range: %s' % offset)
        if end < offset or end > 69:
          raise InvalidArgument('Length out of range: %s' % length)
        data = json.dumps({'method': "fetch", 'params': [{'table': "paray", 'start': offset, 'marker': "rot0", 'length': length, 'datatype': "bytes"}]})
        ret = (await self._post(data))[0]
        return ret['values']

    async def async_write_vram(self, offset : int, bitmask : int, value : int):
        """Set some bits of a byte at a specific offset in vram."""
        if offset < 0 or offset >= 69:
          raise InvalidArgument('Invalid offset %d' % offset)
        if bitmask <= 0 or bitmask > 255:
          raise InvalidArgument('Invalid bitmask %d' % bitmask)
        if value < 0 or value > 255:
          raise InvalidArgument('Invalid value %d' % value)
        data = json.dumps({'method': 'send_packet', 'id': 1, 'params' : [{'marker': "paw", 'cmd': 0, 'data': [offset,bitmask,value]}]})
        await self._post(data)
   
    async def async_read_eeprom(self, offset: int, length : int) -> List[int]:
        end = offset + length
        if offset < 0:
          raise InvalidArgument('Offset out of range: %s' % offset)
        if end < offset or end > 150:
          raise InvalidArgument('Length out of range: %s' % length)
        data = json.dumps({'method': "fetch", 'params': [{'table': "ee", 'start': offset, 'marker': "rot1", 'length': length, 'datatype': "bytes"}]})
        ret = await self._post(data)
        return ret

    async def async_write_eeprom(self, offset : int, length : int, value : List[int]) -> bool:
        end = offset + length
        if offset < 0:
          raise InvalidArgument('Invalid offset %d' % offset)
        if end < offset or end > 150:
          raise InvalidArgument('Invalid length %d' % length)
        # Can only write 4-byte aligned blocks. 
        if length != 4 or offset % 4 or len(value) != 4:
          raise InvalidArgument('Can only write 4 byte aligned blocks.')
        data = json.dumps({'method': 'send_packet', 'id': 1, 'params' : [{'marker': "eew", 'cmd': 7, 'data': value}]})
        await self._post(data)
   
    async def async_read_rtc(self) -> datetime.datetime:
        data = json.dumps({'method': "fetch", 'params': [{'table': "rtc", 'start': 0, 'marker': "rot3", 'length': 4, 'datatype': "bytes"}]})
        ret = await self._post(data)
        try: 
          ret = ret[0]['values']
        # TODO: We should subtract 'age' from time to be more accurate.
          return '%s %02d:%02d:%02d' % (_DAYS[ret[3]], ret[2], ret[1], ret[0])
        except Exception as e:
          print("Error reading RTC: %s" % e)
          return None

    async def async_write_rtc(self, now : datetime.datetime) -> bool:
        raise NotImplemented()

class SygnalApi(object):
    def __init__(self, client):
        self._client = client
        self._vram = [0]*69
        self._ee = [0]*150
        #self._rtc = "Mon 00:00:00"
        self._device_info = {}

    async def async_update(self):
        self._vram = await self._client.async_read_vram(0, 69)
        self._ee = []
        ofs = 0
        while ofs < 150:
          end = min(150, ofs + 64)
          try:
            data = await self._client.async_read_eeprom(ofs, end - ofs)
            self._ee += data[0]['values']
            ofs = end
          except Exception as e:
            print("Exception reading EEPROM range [%d:%d): %s" % (
              ofs, end, e))
        #try:
          #self._rtc = await self._client.async_read_rtc()
        #except Exception as e:
          #print("Exception reading RTC: %s" % e)
        try:
          self._device_info = await self._client.get_device_info()
        except Exception as e:
          println("Exception reading device info: %s" % e)
        self._zones = dict()
        for i in range(8):
          if self._zone_mask & (1 << i):
            name = ''.join([chr(c) for c in self._ee[i*8:(i+1)*8]]).rstrip()
            self._zones[name] = i

    async def async_write_vram(self, offset, mask, value):
        await self._client.async_write_vram(offset, mask, value)
        self._vram[offset] = self._vram[offset] & (0xff ^ mask)
        self._vram[offset] = self._vram[offset] | (mask & value)

    @property
    def name(self):
        return self._client.hostname

    @property
    def unique_id(self):
        try:
          return self._device_info['local']['mac'].replace(':','')
        except:
          println("unique_id() called before device info updated.")
          return None

    @property 
    def device_info(self):
        return self._device_info

    @property
    def status(self):
        STATES = {
          0x01: 'Cooling',
          0x02: 'Heating',
          0x04: 'Run Timer',
          0x08: 'TC Running',
          0x10: 'Compressor Running',
          0x20: 'Compressor Fan Running',
          0x40: 'RV Running',              # RV = Relief Valve? Surely not...
          0x80: 'Crank Heater',
        }
        status = [STATES[1 << i] for i in range(8) if self._vram[60]&(1 << i)]
        return 'Idle' if not status else ', '.join(status)

    @property
    def fan_override_state(self):
        return self._vram[61]

    @property
    def compressor_loading(self):
        return self._vram[62]

    @property
    def outside_coil_temperature(self):
        return self._vram[63] / 2.0

    @property
    def inside_coil_temperature(self):
        return self._vram[64] / 2.0

    @property
    def discharge_temperature(self):
        return self._vram[65] / 2.0

    @property
    def current_temperature(self):
        return self._vram[67] / 2.0

    @property
    def target_temperature(self):
        v = self._vram[1]
        if v > 128: v -= 256
        return 22.5 + v / 2

    async def async_set_temperature(self, target_temp):
        v = float(target_temp)
        t = int((v - 22.5) * 2)
        if t < 0: t += 256
        await self.async_write_vram(1, 255, t) 

    async def async_turn_on(self):
        await self.async_write_vram(0,1,1)

    async def async_turn_off(self):
        await self.async_write_vram(0,1,0)

    @classmethod
    def hvac_modes(cls):
      return [HVAC_OFF, HVAC_VENT, HVAC_COOL, HVAC_HEAT, HVAC_AUTO]

    @property
    def hvac_mode(self):
       VAL_TO_MODE = {
         0x00: HVAC_VENT,
         0x40: HVAC_COOL,
         0x80: HVAC_HEAT,
         0xc0: HVAC_AUTO,
       }
       if not self._vram[0]&0x01:
         return HVAC_OFF
       return VAL_TO_MODE[self._vram[0]&0xc0]

    async def async_set_hvac_mode(self, hvac_mode):
        HVAC_MODE_TO_CMD = {
          HVAC_OFF:  [0, 0x01, 0x00],
          HVAC_VENT: [0, 0xc1, 0x01],
          HVAC_COOL: [0, 0xc1, 0x41],
          HVAC_HEAT: [0, 0xc1, 0x81],
          HVAC_AUTO: [0, 0xc1, 0xc1],
        }
        await self.async_write_vram(*HVAC_MODE_TO_CMD[hvac_mode])

    @classmethod
    def fan_modes(cls):
      return [FAN_ULTRA_LOW, FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_AUTO]

    @property
    def fan_mode(self):
        CMD_TO_FAN_MODE = {
          0x00: FAN_OFF,
          0x02: FAN_ULTRA_LOW,
          0x04: FAN_LOW,
          0x06: FAN_MEDIUM,
          0x08: FAN_HIGH,
          0x20: FAN_AUTO,
        }
        return CMD_TO_FAN_MODE[self._vram[0]&0x3e]

    async def async_set_fan_mode(self, fan_mode):
        FAN_MODE_TO_CMD = {
          FAN_ULTRA_LOW: [0, 0x3e, 0x02],
          FAN_LOW:       [0, 0x3e, 0x04],
          FAN_MEDIUM:    [0, 0x3e, 0x06],
          FAN_HIGH:      [0, 0x3e, 0x08],
          FAN_AUTO:      [0, 0x3e, 0x20],
        }
        await self.async_write_vram(*FAN_MODE_TO_CMD[fan_mode])

    @property
    def _zone_mask(self):
      return self._vram[39]

    @property
    def zones(self):
      return self._zones.keys()

    def zone_is_enabled(self, name: Text):
      if name not in self._zones:
        raise InvalidArgument('Bad zone IX %s - %s' % (name,str(self._zones)))
      ix = self._zones[name]
      return True if self._vram[2+ix]&0x80 else False

    async def async_set_zone_enabled(self, name: str, state: bool):
      if name not in self._zones:
        raise InvalidArgument('Bad zone IX')
      ix = self._zones[name]
      await self.async_write_vram(2 + ix, 0x80, 0x80 if state else 0x00)

    def zone_fanspeed(self, name: Text):
      if name not in self._zones:
        raise InvalidArgument('Bad zone IX')
      ix = self._zones[name]
      return self._vram[2+ix]&0x7f

    def zone_speed_count(self, name: Text):
      return len(ZONE_FANSPEED_RANGE)

    async def async_set_zone_fanspeed(self, name: str, state: int):
      if name not in self._zones:
        raise InvalidArgument('Bad zone IX')
      ix = self._zones[name]
      if state < 0 or state > 100: return
      # map state value to an allowed step
      state = min(ZONE_FANSPEED_RANGE, key=lambda x:abs(x-state))
      # dont write to eeprom if it is already set to this value
      if self.zone_fanspeed(name) == state: return
      await self.async_write_vram(2 + ix, 0x7f, state & 0x7f)

if __name__ == "__main__":
    async def main():
        async with aiohttp.ClientSession() as session:
            l = SygnalClient('chatterbox', session)
            api = SygnalApi(l)
    
            await api.async_update()
    
            print('id', api.unique_id)
            print('device_info', api.device_info)
            print('status', api.status)
            print('current_temperature', api.current_temperature)
            print('target_temperature', api.target_temperature)
            print('compressor_loading', api.compressor_loading)
            print('outside_coil_temperature', api.outside_coil_temperature)
            print('inside_coil_temperature', api.inside_coil_temperature)
            print('discharge_temperature', api.discharge_temperature)
            print('hvac_mode', api.hvac_mode)
            print('fan_mode', api.fan_mode)
            print('zones', api.zones)
            for z in api.zones:
              print('  %s: %s' % (z, api.zone_is_enabled(z)))
   

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
  

