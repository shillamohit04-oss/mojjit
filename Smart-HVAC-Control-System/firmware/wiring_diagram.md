# ESP32 HVAC Controller — Wiring Diagram

## Component List

| # | Component | Specification | Qty |
|---|-----------|--------------|-----|
| 1 | ESP32 DevKit v1 | 30-pin, USB-C | 1 |
| 2 | DHT22 | Temperature + Humidity sensor | 1 |
| 3 | PIR Motion Sensor | HC-SR501 (or mmWave for better accuracy) | 1 |
| 4 | 5V Relay Module (2-ch) | Opto-isolated, active-low | 1 |
| 5 | 10kΩ Resistor | Pull-up for DHT22 data line | 1 |
| 6 | Breadboard + Jumper Wires | For prototyping | 1 set |
| 7 | 5V Power Supply | 2A minimum | 1 |

## Pin Connections

```
                    ESP32 DevKit v1
                   ┌───────────────┐
                   │     USB-C     │
              3V3 ─┤ 3V3      VIN ├─ 5V (from power supply)
              GND ─┤ GND      GND ├─ GND (common ground)
                   │               │
     DHT22 Data ──►┤ GPIO 4       │
                   │               │
     PIR Signal ──►┤ GPIO 14      │
                   │               │
  Cooling Relay ◄──┤ GPIO 26      │
  Heating Relay ◄──┤ GPIO 27      │
                   │               │
   Onboard LED ────┤ GPIO 2       │
                   │               │
                   └───────────────┘
```

## DHT22 Wiring

```
    DHT22 Module
    ┌─────────┐
    │  ┌───┐  │
    │  │   │  │
    │  └───┘  │
    └─┬─┬─┬─┬┘
      │ │ │ │
     VCC│ │GND
      │ │ │
      │ │ └──── GND (ESP32 GND)
      │ │
      │ └────── Not connected (pin 3)
      │ │
      │ └────── DATA → GPIO 4 (with 10kΩ pull-up to 3.3V)
      │
      └──────── VCC → 3.3V (ESP32 3V3)

    Pull-up Resistor:
    3.3V ──┤10kΩ├── GPIO 4 (DATA)
```

## PIR Sensor (HC-SR501)

```
    HC-SR501
    ┌─────────────┐
    │   ┌─────┐   │
    │   │Fresnel│  │
    │   │ Lens  │  │
    │   └─────┘   │
    └──┬──┬──┬────┘
       │  │  │
      VCC OUT GND
       │  │   │
       │  │   └── GND (ESP32 GND)
       │  │
       │  └────── OUT → GPIO 14
       │
       └───────── VCC → 5V (ESP32 VIN)

    Adjustments (on back of module):
    - Sensitivity pot: Turn clockwise for max range (~7m)
    - Time delay pot: Set to minimum (~3 seconds)
    - Jumper: Set to "H" (repeatable trigger mode)
```

## Relay Module (2-Channel, Opto-Isolated)

```
    2-Channel Relay Module
    ┌─────────────────────────────────┐
    │  [Relay 1]       [Relay 2]     │
    │  COOLING          HEATING      │
    │                                │
    │  NO COM NC        NO COM NC    │
    └──┬──┬──┬──┬──┬─────────────────┘
       │  │  │  │  │
      VCC GND IN1 IN2

    Low-voltage side:
       VCC ──── 5V (ESP32 VIN)
       GND ──── GND (ESP32 GND)
       IN1 ──── GPIO 26 (Cooling)
       IN2 ──── GPIO 27 (Heating)

    ⚠️  HIGH-VOLTAGE SIDE (24V AC HVAC):
    ┌────────────────────────────────────┐
    │  CAUTION: 24V AC thermostat wires  │
    │  Only qualified personnel should   │
    │  connect to HVAC system wiring.    │
    ├────────────────────────────────────┤
    │                                    │
    │  Relay 1 (Cooling):               │
    │    COM ──── R (24V common)         │
    │    NO  ──── Y (cooling call)       │
    │                                    │
    │  Relay 2 (Heating):               │
    │    COM ──── R (24V common)         │
    │    NO  ──── W (heating call)       │
    │                                    │
    │  Fan control (optional):           │
    │    G terminal ──── Always on or    │
    │                    via 3rd relay    │
    └────────────────────────────────────┘
```

## Safety Warnings

> ⚠️ **HIGH VOLTAGE**: Never connect the relay directly to mains AC (120V/240V).
> Only connect to the 24V AC thermostat wiring of your HVAC system.

> ⚠️ **ISOLATION**: Use opto-isolated relay modules to protect the ESP32
> from electrical noise and inductive spikes from the HVAC contactor.

> ⚠️ **DEAD TIME**: The firmware enforces a 100ms dead time between
> switching heating and cooling relays. Never activate both simultaneously.

> ⚠️ **COMPRESSOR PROTECTION**: A minimum 3-minute cycle time is enforced
> in firmware to prevent compressor damage from short cycling.

## Power Supply Notes

1. Use a dedicated 5V/2A power supply for the ESP32 + relay module
2. Do NOT power the relay module from the ESP32's 3.3V pin
3. Ensure common ground between ESP32, relay module, and sensors
4. Add a 100μF capacitor across the 5V rail for relay switching stability

## MQTT Broker Setup (Optional)

For remote monitoring, install Mosquitto on a Raspberry Pi or server:

```bash
# Install Mosquitto
sudo apt install mosquitto mosquitto-clients

# Test subscription
mosquitto_sub -h localhost -t "hvac/#" -v
```

Update `WIFI_SSID`, `WIFI_PASSWORD`, and `MQTT_SERVER` in the firmware.
