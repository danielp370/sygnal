# Livezi/Sygnal Chatterbox Support

This is a[home assistant](https: // home-assistant.io) module for Sygnal/Livezi
branded chatterbox devices, allowing full local integration of these devices with
homeassistant.

This is for personal use, shared in case other people find it of use.

Note that I have a Livezi device. It seems that the Livezi brand was acquired by
Sygnal some time around 2015 and I imagine the firmware on modern chatterbox units
may be significantly different to mine.

This code works for me. It might work for you. I'm not too keen on updating my
firmware to support newer versions while it's working so well but will happily
accept patches.

Default "use at your own risk" and "I make no guarantees" apply.
From what I can tell, the API I am using gives direct read/write access
to RAM(settings), RTC(clock) and EEPROM(name of zones, schedules).

# Installation

1. Put this in your homeassistant `config/custom_components/sygnal` directory.
2. Add this to your configuration.yaml:
    ```
    climate:
        - platform: sygnal
        host: '198.168.1.xxx'  # Chatterbox IP address.
        name: 'chatterbox'     # Whatever you want to call it.
    ```

You should see entities for `climate.chatterbox` and a switch for each zone.
e.g. `climate.chatterbox_bedroom1`. Internal state(coil
                                                   temperatures, compressor loading) are exported as device attributes.


# Limitations

Manipulation of the EEPROM data(zones, schedules, zone baffle settings) are
intentionally left out. I didn't want to risk EEPROM wearout.

I only read the EEPROM at startup because it seems slightly flaky
and potentially slow and wasteful to re-read it on every update when it almost
never changes.

I also don't bother with the RTC as it doesn't track date and is of little use
with this integration.

The data exported by this version is focused on Digital Scroll Compressor
systems. It seems there are other systems that can use the same interface but I
don't have one handy so I can't easily guess the ranges of values for those.

# Entities

The integration exports:
    * one `climate` entity for the central AC unit itself.
    * A `cover` entity for every zone, allowing control of the
    damper settings as well as zone on/off.
    * A `switch` entity for every zone. This provides the equivalent of cover
    up/down but is potentially more ergonomic on dashboards if you don't want
    damper settings to be changed.
    * A set of `sensor` entities for the temperature and internal system states.

# Reverse Engineering

The following is roughly the memory layout for volatile RAM.

```
0: 160  # Bitmask:
# Bits 0: On/Off
# Bits 1-5: fan speed
#   ULOW, LOW, MED, HIGH, X, X, X, X,
#   X, X, X, X, X, X, X, X,
#   AUTO, X, ...
# Bits 6-7: mode (Vent, Cool, Heat, Auto)
1: 5    # Target Temp. 22.5C + val * 0.5 (twos complement)
# 15 --> 22.5 + 15*.5 = 30C
# 241 --> 241-256 = -15 --> 22.5 - 15 * 0.5 = 15C
2: 178  # Zone1, Top bit (128) ‘on/off’ + vent posn (0-100)
3: 50   # Zone2, Top bit (128) ‘on/off’ + vent posn (0-100)
4: 30   # Zone3, Top bit (128) ‘on/off’ + vent posn (0-100)
5: 50   # Zone4, Top bit (128) ‘on/off’ + vent posn (0-100)
6: 80   # Zone5, Top bit (128) ‘on/off’ + vent posn (0-100)
7: 60   # Zone6, Top bit (128) ‘on/off’ + vent posn (0-100)
8: 75   # Zone7, Top bit (128) ‘on/off’ + vent posn (0-100)
9: 10   # Zone8, Top bit (128) ‘on/off’ + vent posn (0-100)
10: 0   # ?
11: 0   # ?
12: 0   # ?
13: 0   # ?
14: 228  # Zone1 Max position
15: 208  # Zone2 Max position
16: 228  # Zone3 Max position
17: 228  # Zone4 Max position
18: 218  # Zone5 Max position
19: 228  # Zone6 Max position
20: 228  # Zone7 Max position
21: 228  # Zone8 Max position
22: 0   # Zone1 Min position
23: 0   # Zone2 Min position
24: 0   # Zone3 Min position
25: 0   # Zone4 Min position
26: 0   # Zone5 Min position
27: 0   # Zone6 Min position
28: 0   # Zone7 Min position
29: 0   # Zone8 Min position
30: 30  # Zone1 Duct Flow Size
31: 10  # Zone2 Duct Flow Size
32: 14  # Zone3 Duct Flow Size
33: 20  # Zone4 Duct Flow Size
34: 13  # Zone5 Duct Flow Size
35: 40  # Zone6 Duct Flow Size
36: 30  # Zone7 Duct Flow Size
37: 20  # Zone8 Duct Flow Size
38: 55  # ??
39: 127  # ??
40: 16  # acMotorTime?
41: 0
42: 0
43: 0
44: 0
45: 0
46: 15  # ??
47: 49  # Zone1 Actual position
48: 0   # Zone2 Actual position
49: 0   # Zone3 Actual position
50: 0   # Zone4 Actual position
51: 0   # Zone5 Actual position
52: 0   # Zone6 Actual position
53: 0   # Zone7 Actual position
54: 0   # Zone8 Actual position
55: 0   # Bitmask for PRM faults.
56: 0   # Bitmask for PRM CSens faults.
57: 31  # Bitmask for PRM phase status.
# Bit 0: LiveziManager.acPH3_PRES_PH2
# Bit 1: LiveziManager.acPH3_PRES_PH3
# Bit 2: XXX
# Bit 3: LiveziManager.acPH3_GOOD_MSK
# Bit 4: LiveziManager.acPH3_WAS_PRES_PH2
# Bit 5: LiveziManager.acPH3_WAS_PRES_PH3
58: 0   # acUnitType 0->Digital, 1-> Inverter
59: 0   # PRM_SINCE_HPLPSENS?
60: 64  # Bitmask:
# 1 acUnitIsCooling
# 2 acUnitIsHeating
# 3 acRunTimerRunning
# 4 acTCRunning
# 5 acCompressorRunning
# 6 acCompFanRunning
# 7 acRVRunning
# 8 acCrankHeater
61: 128  # acFanOverrideState
62: 100  # acCompressorLoading
63: 21  # Outdoor coil temp (half degrees) 21 -> 10.5C
64: 48  # Indoor coil temp (half degrees) 48 -> 24C
65: 0   # acDischargeTemp
66: 0
67: 36  # Control temp (half degrees) 36 -> 18C
# (This is observed somewhere in the unit and updates
# even in the absence of a control panel. I’m not sure if
# the thermister on the control panel is even used!)
# This is also not writable. Changes silently discarded.
68: 0
```

EEPROM:

```
0: 77   # Zone 1 name
1: 115
2: 116
3: 114
4: 32
5: 66
6: 101
7: 100
8: 79   # Zone 2 name
9: 119
10: 101
11: 110
12: 32
13: 66
14: 101
15: 100
16: 73  # Zone 3 name
17: 97
18: 110
19: 32
20: 66
21: 101
22: 100
...
96: 255  # Schedules start here.
97: 255
98: 40
99: 42
100: 127  # ??
101: 255
102: 143
103: 144
104: 127
105: 255
106: 144
107: 144
108: 127
109: 255
110: 144
111: 144
112: 127
113: 255
114: 144
115: 136
116: 127
117: 255
118: 144
119: 144
120: 127
121: 255
122: 144
123: 144
124: 127
125: 255
126: 144
127: 144
... Further obtained via second request
148: 144  # Shutdown count in x5 hours
149: 144  # Reload count in x5 hours
150: 0    # 12 phone digits for support.

```
