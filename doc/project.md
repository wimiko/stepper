# ESP32 + TMC2209 WiFi Stepper Motor Driver

## Project Overview
A stepper motor driver controlled over WiFi. Commands are sent to an ESP32 which drives a TMC2209 stepper motor driver.

---

## ESP32-C3 Board (ABRobot 0.42" OLED)

### Overview
| Property | Value |
|----------|-------|
| Board | ABRobot ESP32-C3 with 0.42" OLED |
| Dimensions | 24.8mm × 20.45mm, 2.54mm pitch |
| Supply voltage | 3.3V–6V |
| Flash | 4MB |
| Connectivity | WiFi 802.11b/g/n (2.4GHz), Bluetooth 5.0 |
| Display | 0.42" OLED, SSD1306 controller, 72×40 effective pixels (128×64 buffer) |
| I2C address | 0x3C |
| USB | Native USB CDC (shows up as `/dev/ttyACM0` on Linux) |

### Pinout
| Function | GPIO | Notes |
|----------|------|-------|
| I2C SDA (OLED) | 5 | Shared with external I2C devices |
| I2C SCL (OLED) | 6 | Shared with external I2C devices |
| Blue LED | 8 | Active LOW (LOW = on) |
| BOOT button | 9 | Pull-up to 3.3V |
| TX (UART0) | 21 | |
| RX (UART0) | 20 | |
| USB D−/D+ | 18/19 | Reserved — do not use |
| ADC capable | 0–5 | |
| SPI/GPIO | 10–17 | Some reserved for flash |

### Display
The SSD1306 has a 128×64 buffer but only a 72×40 pixel area is physically visible. In ESPHome use `model: "SSD1306 72x40"` — this handles the offset automatically.

The display on this board is **not interchangeable** with other 0.42" SSD1306 displays; the pixel mapping differs.

### Flashing via USB

**First-time flash (or if device is unresponsive):**
1. Hold the `BOOT` button
2. Press and release `RESET` (or plug in USB while holding `BOOT`)
3. Release `BOOT` — board is now in bootloader mode
4. Run: `esphome run esp32-c3.yaml --device /dev/ttyACM0`

**Linux permissions** — add yourself to the `dialout` group (one-time):
```bash
sudo usermod -a -G dialout $USER
# log out and back in
```

**Important:** Use a data-capable USB cable. Many cables are charge-only and the device will not appear in `dmesg` or `lsusb`.

After a successful first flash, subsequent OTA updates work over WiFi.

### ESPHome Notes
- Logger via USB: add `hardware_uart: USB_SERIAL_JTAG` under `logger:`
- Board identifier: `esp32-c3-devkitm-1`
- Framework: `arduino`

### Resources
- Blog with detailed setup: [emalliab.wordpress.com — ESP32-C3 0.42 OLED](https://emalliab.wordpress.com/2025/02/12/esp32-c3-0-42-oled/)
- Schematic: [github.com/zhuhai-esp/ESP32-C3-ABrobot-OLED](https://github.com/zhuhai-esp/ESP32-C3-ABrobot-OLED)
- Fritzing part: [Fritzing forum](https://forum.fritzing.org/t/esp32-c3-oled-0-42-mini-board-part/25830)

---

## Components

### Core Electronics
| Component | Description | Notes |
|-----------|-------------|-------|
| [Wemos S2 Mini V1.0.0](https://www.wemos.cc/en/latest/s2/s2_mini.html) | Main microcontroller | ESP32-S2FN4R2, 240MHz, 4MB flash, 2MB PSRAM, USB-C, 3.3V logic — [schematic](https://www.wemos.cc/en/latest/_static/files/sch_s2_mini_v1.0.0.pdf) · [pinout](https://www.studiopieters.nl/s2-mini-pinout/) |
| [BigTreeTech TMC2209 V1.3](https://github.com/bigtreetech/BIGTREETECH-Stepper-Motor-Driver/tree/master/TMC2209/V1.3) | Stepper motor driver module | 2A RMS / 2.8A peak, 4.75–28V VM, StealthChop2 — [manual](https://github.com/bigtreetech/BIGTREETECH-Stepper-Motor-Driver/blob/master/TMC2209/V1.3/manual/BIGTREETECH%20TMC2209%20V1.3%20User%20Manual.pdf) · [datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/tmc2209_datasheet_rev1.09.pdf) · [pinout](https://learn.watterott.com/silentstepstick/pinconfig/tmc2209/) |
| Stepper Motor | NEMA 17 (recommended) | e.g. 1.7A, 1.8°/step, 200 steps/rev |

### Power
| Component | Description | Notes |
|-----------|-------------|-------|
| Motor PSU | 24V DC power supply | Current rating ≥ motor peak current + headroom |
| [HW-133 Step-Down Module](https://www.amazon.com/HW-133-Step-Down-Module-Ultra-Small-24V-9V/dp/B0CNTBWHZD) | 24V → 5V converter for logic | MP1584EN-based, 4.5–28V in, 3A max — output set to 5V via solder jumper — [IC datasheet](https://www.monolithicpower.com/en/documentview/productdocument/index/version/2/document_type/Datasheet/lang/en/sku/MP1584EN-LF-Z/document_id/204/) |
| Decoupling capacitors | 100µF + 100nF near TMC2209 VM pin | Protects driver from voltage spikes |

### Wiring & Passives
| Component | Description | Notes |
|-----------|-------------|-------|
| Resistors | UART line resistor (~1kΩ on TX→PDN_UART) | Required for TMC2209 single-wire UART |
| Jumper wires / PCB | For connecting components | Prototype: breadboard/wires; final: custom PCB |
| Connectors | For motor coils and power | e.g. JST or screw terminals |

### Optional / Recommended
| Component | Description | Notes |
|-----------|-------------|-------|
| Endstop switch | Homing / limit detection | Mechanical or optical |
| Encoder | Closed-loop feedback | Optional, for position verification |
| Heat sink | For TMC2209 if running high current | Stick-on or clip-on |
| Status LED | Visual feedback | Optional |

---

## Wiring Overview (to be expanded)

| TMC2209 Pin | Connects to | Notes |
|-------------|-------------|-------|
| PDN_UART | ESP32 TX + ESP32 RX (via 1kΩ on TX) | Single-wire half-duplex UART |
| STEP | ESP32 GPIO | Step pulse output |
| DIR | ESP32 GPIO | Direction output |
| EN | ESP32 GPIO (or GND) | Active LOW; pull to GND to always enable |
| VM | Motor PSU + (12–24V) | Motor power; add 100µF + 100nF decoupling cap to GND |
| GND | Common GND | ESP32, TMC2209, and PSU share ground |
| VIO | 3.3V from S2 Mini | Logic supply |
| MS1/MS2 | Leave floating or GND | Not needed in UART mode |

### UART wiring detail
The TMC2209 PDN_UART pin is single-wire half-duplex. To connect to the ESP32's full-duplex UART:
- Connect PDN_UART → ESP32 RX directly
- Connect ESP32 TX → PDN_UART via a **1kΩ resistor** (the resistor prevents TX from fighting RX when reading)

### BigTreeTech TMC2209 specific notes
- UART address is set by MS1/MS2 pins: both LOW = address `0x00` (ESPHome default)
- The sense resistor is **110mΩ** — needed for accurate current calculation in ESPHome
- SPREAD pin: pull LOW for StealthChop (silent), HIGH for SpreadCycle (more torque at speed)
- DIAG pin can be used for StallGuard (sensorless homing)

---

## System Architecture

```
Raspberry Pi
├── Mosquitto MQTT broker  (localhost)
└── Python control script  (paho-mqtt)
        ↕ MQTT over WiFi
ESP32 S2 Mini (ESPHome)
        ↕ UART
TMC2209 V1.3
        ↕
NEMA 17 stepper motor
```

### MQTT Topics (proposed)
| Topic | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `stepper/command/position` | RPi → ESP32 | integer (steps) | Move to absolute position |
| `stepper/command/speed` | RPi → ESP32 | integer (steps/s) | Set max speed |
| `stepper/command/home` | RPi → ESP32 | `1` | Trigger homing routine |
| `stepper/command/stop` | RPi → ESP32 | `1` | Emergency stop |
| `stepper/status/position` | ESP32 → RPi | integer (steps) | Current position |
| `stepper/status/state` | ESP32 → RPi | `idle`/`moving`/`homing` | Current state |

---

## Software Plan

### ESP32 — ESPHome

**Framework: [ESPHome](https://esphome.io)**

Relevant docs:
- [TMC2209 stepper component](https://esphome.io/components/stepper/tmc2209.html)
- [Stepper component overview](https://esphome.io/components/stepper/)
- [ESP32 platform (S2 supported)](https://esphome.io/components/esp32.html)
- [WiFi component](https://esphome.io/components/wifi.html)
- [MQTT component](https://esphome.io/components/mqtt.html)
- [OTA updates](https://esphome.io/components/ota/esphome.html)

Tasks:
- [ ] ESPHome YAML config skeleton for S2 Mini
- [ ] TMC2209 UART config (current, microstepping)
- [ ] Subscribe to MQTT command topics
- [ ] Publish position and state to MQTT status topics
- [ ] Homing routine (endstop / StallGuard)
- [ ] OTA update setup

### Raspberry Pi — MQTT Broker

- **Broker:** [Mosquitto](https://mosquitto.org/) — `sudo apt install mosquitto mosquitto-clients`
- Runs as a systemd service, connects on `localhost`
- No network hop needed since Python script runs on the same Pi

Tasks:
- [ ] Install and enable Mosquitto
- [ ] Configure broker (auth, port — TBD)

### Raspberry Pi — Python Control Script

- **Library:** [paho-mqtt](https://pypi.org/project/paho-mqtt/) — `pip install paho-mqtt`
- Publishes commands to `stepper/command/*`
- Subscribes to `stepper/status/*` for feedback

Tasks:
- [ ] Basic publish/subscribe scaffold
- [ ] Position command interface
- [ ] Status feedback handling

---

## Open Questions / Decisions

- ~~Motor power supply voltage?~~ **→ 24V**
- ~~Using TMC2209 in UART mode or standalone?~~ **→ UART mode**
- ~~Control via Home Assistant API or MQTT?~~ **→ MQTT**
