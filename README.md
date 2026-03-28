Ledding
=======

Fancy LED project

<!-- vim-markdown-toc GFM -->

* [Hardware](#hardware)
    * [LED stripe WS2812B and WS2815](#led-stripe-ws2812b-and-ws2815)
        * [Timing:](#timing)
    * [Power considerations](#power-considerations)
        * [WS2812B](#ws2812b)
        * [WS2815](#ws2815)
        * [Cabling](#cabling)
    * [Level shifters](#level-shifters)
* [Software](#software)
    * [Installation](#installation)
    * [Important commands](#important-commands)
    * [Programming](#programming)
    * [Debugging using JTAG](#debugging-using-jtag)
        * [Make the physical connection](#make-the-physical-connection)
        * [One time setup configuration](#one-time-setup-configuration)
        * [Start a debugging session](#start-a-debugging-session)
* [Raspberry Pi Audio FFT](#raspberry-pi-audio-fft)
    * [How it works](#how-it-works)
    * [Raspberry Pi setup with Ansible](#raspberry-pi-setup-with-ansible)
* [Specifics for Partyraum Installation](#specifics-for-partyraum-installation)
    * [I/O](#io)
* [Specifics for Maite Installation](#specifics-for-maite-installation)
    * [Box interfaces](#box-interfaces)
    * [Buttons](#buttons)
* [TODO](#todo)
* [Lessons learned](#lessons-learned)

<!-- vim-markdown-toc -->

## Hardware
1. MCU is the ESP32

Feature | Description
---------- | ------
SoM | from Broodio (quite unknown, selecting the ESP32 Development Kit (DevKitC) is suitable)
SoC | ESP-WROOM-32D
CPU | ESP32-D0WD
Flash | 4 MiB
RAM | 320 KiB

1. LED stripes are WS2812B and WS2815 with 30 LEDs per meter and WS2812B with 60 LEDs per meter.

### LED stripe WS2812B and WS2815
Consists of a 5050 SMD and a WS2812B or WS2815 chip.

#### Timing:
Clock of the stripe is at 800 kHz. Writing one bit takes
```
t_b = 1 / 800 kHz = 1.25 µs
```
Writing one pixel takes
```
t_B = 24 bit * 1.25 µs/bit = 30 µs`
```
Writing 10m stripe of 30 LED/m takes
```
T = 10 m * 30 px/m * 30 µs = 9 ms
```
This would give a maximum refresh rate of
```
f = 1 / 9 ms ≈ 111 Hz
```

### Power considerations
#### WS2812B
For the 5V strips each LED pulls max. ~20 mA (realistic max is 15 mA) per color, so 60 mA (45 mA) per pixel.
For 10 m of the 30 px/m stripe, we have at maximum brightness
```
Theoretical:
I_t5 = 10 m * 30 px/m * 60 mA/px = 18 A
P_t5 = 18 A * 5V = 90 W

Realistic:
I_r5 = 10 m * 30 px/m * 45 mA/px = 13.5 A
P_r5 = 13.5 A * 5V = 67.5 W
```

#### WS2815
For the 12V strips each LED pulls max. 15 mA per color, but also max. 15 mA for the full pixel (they are in series). Power is burnt for non-white.
For 10 m of the 30 LED/m stripe, we have at maximum brightness
```
I_r12 = 10 m * 30 px/m * 15 mA/px = 4.5 A
P_r12 = 15 A * 12V = 54 W
```

#### Cabling
For the cable the resistance is
```
R = l / (\kappa * A)
```
where l is the cable length in m, kappa is the conductivity in (m / (\ohm * mm^2)) and A is the cross-section in mm^2.
Longest length is 18 m (twice that to account for GND back) with copper `\gamma = 57.18 (m / (\ohm * mm^2))`
```
R_2.5 = 36 m / 57.18 (m / (\ohm * mm^2)) / 2.5 mm^2 ≈ 0.252 \Ohm
R_1.5 = 36 m / 57.18 (m / (\ohm * mm^2)) / 1.5 mm^2 ≈ 0.420 \Ohm
```
Assuming to power 5 m of the LED strip with the 18m of cable leads to
```
I = 5 m * 30 px/m * 45 mA = 6.75 A
U = 0.252 * 6.75 A = 1.701 V
```
leaving only `5 - 1.701 = 3.299 V` for the LEDs with 2.5 mm^2 copper cable. Not really enough...\
With the WS2815 it would be:
```
I = 5 m * 30px/m * 15 mA = 2.25 A
U_c2.5 = 0.252 * 2.25 A = 0.567 V for 2.5 mm^2 copper or
U_c1.5 = 0.420 * 2.25 A = 0.945 V for 1.5 mm^2 copper
```
leaving > 11 V for the LEDs in both cases. This should enough for equal color rendering on all LEDs (to be confirmed).

### Level shifters
Available (should be fast enough):
- 74AHCT125 (quad level shifter)
- TXB0108 (eight channel bi-directional)

## Software
### Installation
This project uses platformio (https://platformio.org/) as its build system.
Library dependencies are declared in `platformio.ini` and installed automatically on first build.

To install platformio, download and execute the `get-platformio.py` script
```
wget https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py -O get-platformio.py
python3 get-platformio.py
```

To be able to upload, the user needs to be able to open the USB device, thus being in the `dialout` group
```
sudo usermod -aG dialout <user>
```

### Important commands
Important platformio commands (next to those in the Makefile which are described there):

Start serial console:
```
pio device monitor -b 115200
```

Generate `compile_commands.json`:
```
make compilecommands
```

### Programming
Important configuration is passed via environment variables (such as WLAN_SSID, PSK and IPs).
To work with a specific enviroment, we can source the relevant enviroment:
```
source env-partyraum
```
After that, we can use the Makefile targets for programming:
- To program the ESP32 via USB cable, issue `make upload`, then hold down the `BOOT` button on the ESP32-board until the upload starts.
- For OTA programming, issue `make ota`

The `env-partyraum` is the default environment and doesn't need to be sourced, but we can use this file to create custom
environments such as `env-maite` or `env-testbed` (not commited due to secret WLAN PSK).


### Debugging using JTAG
On-target debugging with GDB is possible using JTAG. I have the `FT4232H-56Q MiniModule` as the USB2JTAG adapter. The following steps are necessary:

#### Make the physical connection
| JTAG function | ESP32 pin | FT4232H pin |
| ---------------------- | ------ | --- |
| TDI (Test Data In)     | GPIO12 | AD1 |
| TDO (Test Data Out)    | GPIO15 | AD2 |
| TCK (Test Clock)       | GPIO13 | AD0 |
| TMS (Test Mode Select) | GPIO14 | AD3 |
| TRST (Test Reset)      | EN     | RT# |
| GND                    | GND    | GND |

Furthermore the jumpers on the MiniModule need to be set to provide the reference voltage.

#### One time setup configuration
This module is not recognized correctly by `OpenOCD` (Open On-Chip-Debugger) used by `platformio` which is why
we need to tell it. Connect the MiniModule to USB and get the description and IDs:
```
$ pio device list

/dev/ttyUSB3
------------
Hardware ID: USB VID:PID=0403:6011 SER=FT2AWE2C LOCATION=1-5:1.3
Description: FT4232H-56Q MiniModule

/dev/ttyUSB2
------------
Hardware ID: USB VID:PID=0403:6011 SER=FT2AWE2C LOCATION=1-5:1.2
Description: FT4232H-56Q MiniModule

/dev/ttyUSB1
------------
Hardware ID: USB VID:PID=0403:6011 SER=FT2AWE2C LOCATION=1-5:1.1
Description: FT4232H-56Q MiniModule

/dev/ttyUSB0
------------
Hardware ID: USB VID:PID=0403:6011 SER=FT2AWE2C LOCATION=1-5:1.0
Description: FT4232H-56Q MiniModule
```

For this module, we need to add (or change the existing values) in `~/.platformio/packages/tool-openocd-esp32/share/openocd/scripts/interface/ftdi/minimodule.cfg`
Add or change the following:
```
ftdi_device_desc "FT4232H-56Q MiniModule"
ftdi_vid_pid 0x0403 0x6011
```

This should eliminate the following errors on a debug run
```
$ pio debug --interface gdb -x .pioinit

[...]
Error: no device found
Error: unable to open ftdi device with vid 0403, pid 6011, description 'FT2232H MiniModule', serial '*' at bus location '*'
```

This is valid for the `debug_tool = minimodule` (see `platformio.ini`).
We would only need to repeat those steps if the `platformio` update replaced this files with the originals again.

#### Start a debugging session
**Potential pitfall first**:
The GPIOs for JTAG (12 - 15) are also used for touch buttons. When they are actually used for this functionality,
the debugger cannot initiate the debugging session.
TODO add error msg here

That's why we must flash a firmware not using those buttons first using the normal flashing mechanisms. It can basically be any firmware because during beginning of the JTAG session the firmware to be debugged will be loaded anyway.

Building a debug version of the firmware will define `DEBUG_JTAG` and hence not use those touch buttons, so `make debug` will work.

To actually start a debugging session with GDB, use
```
pio debug --interface gdb -x .pioinit
```

## Raspberry Pi Audio FFT

A Raspberry Pi captures audio via microphone, performs FFT analysis and sends the resulting frequency levels to the ESP32 over a serial connection (`/dev/serial0` at 115200 baud). The ESP32 uses this data to drive the LED strips in a music-reactive mode.

### How it works

- `pyaudio.py` — Captures audio, computes FFT, sends per-LED brightness levels over serial. Runs as a systemd service (`pyaudio.service`).
- `pyaudio-webserver.py` — Same FFT logic but additionally exposes a web interface on port 8000 to switch modes.

Requirements: Python 3, pyaudio, numpy, pyserial.

### Raspberry Pi setup with Ansible

An Ansible playbook in `.ansible/` automates the Raspberry Pi setup (installs dependencies, clones the repo, enables the pyaudio systemd service).

1. Edit `.ansible/hosts` and set the Pi's IP address
2. Adjust `.ansible/group_vars/all.yml` if needed (e.g. `deploy_user`)
3. Run the playbook:
```
cd .ansible
ansible-playbook -i hosts play_raspberry.yml
```

The playbook connects via SSH and uses `sudo` (`become: yes`). Make sure SSH access to the Pi is set up with key-based authentication.

## Specifics for Partyraum Installation
LED stripes of
- 2x 10 m
- 4x  2 m

results in `28 m * 30 px/m = 840 px`. Safety margin: `900 px`

We choose the WS2815 for less current and therefore easier cabeling
Theoretically, we need
```
900 px * 15 mA/px = 13.5 A
13.5 A * 12 V = 162 W
```

The Meanwell LRS-200-12 is a good fit.

### I/O

- Button 1: Brightness
- Button 2: Mode
- Button 3: Color
- Button 4: Intensity
- LED 1: WiFi connected?
- LED 2: Serial FFT data from Raspberry Pi received last second
- LED 3: TODO
- LED 4: TODO

## Specifics for Maite Installation
LED stripes WS2812B
```
5 m * 30 px/m = 150 px
```
Power consumption (realistic maximum)
```
I_r5 = 5 m * 30 px/m * 45 mA/px = 6.75 A
P_r5 = 6.75 A * 5V = 33.75 W
```

Cable is J-Y(ST)Y:
```
R_0.6 = 12 m / 57.18 (m / (\ohm * mm^2)) / 0.6 mm^2 ≈ 0.350 \Ohm
R_1.2 = 12 m / 57.18 (m / (\ohm * mm^2)) / 1.2 mm^2 ≈ 0.175 \Ohm
```
Assuming to power half of the LED strip:
```
I = 2.5 m * 30 px/m * 45 mA = 3.375 A
U_0.6 = 0.350 * 3.375 A = 1.181 V
U_1.2 = 0.175 * 3.375 A = 0.591 V
```

### Box interfaces
- Power Input
- µUSB
- Led OUT 5-port:
    - Data
    - GND front
    - VCC front
    - GND back
    - VCC back
- Status LED
- 3 Buttons
- Power switch
- 2 Potis for speed and brightness

### Buttons
1. Brightness +
2. Brightness -
3. Speed +
4. Speed -
5. Color next
6. Color prev
7. Mode next
8. Mode prev


## TODO
1. Add schematics
    1. Add a RPI connection to the `BOOT` button to be able to flash without manual interaction
1. Use ESP Log functions instead of serial directly for more finegrained logging

## Lessons learned
1. When creating a new environment in `platformio.ini`, dependencies from `lib_deps` are installed automatically on the first build for that environment.
