# System Architecture

## Layered Architecture

The Smart HVAC Control System follows a clean three-layer architecture with strict separation of concerns. This ensures modularity, testability, and scalability.

```
┌─────────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER                         │
│                   (Streamlit Dashboard)                          │
│   ┌───────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────┐   │
│   │Gauges │ │Time-series│ │Energy     │ │Controller        │   │
│   │       │ │Charts     │ │Reports    │ │Comparison        │   │
│   └───┬───┘ └────┬─────┘ └─────┬─────┘ └────────┬─────────┘   │
├───────┴──────────┴─────────────┴────────────────┴──────────────┤
│                      PROCESSING LAYER                           │
│              (Controllers + AI Optimization)                    │
│                                                                 │
│   ┌──────────────────┐    ┌──────────────────────────┐         │
│   │ Rule-Based       │    │ AI / Optimization Layer   │         │
│   │ Controller       │    │ ┌────────────────────┐   │         │
│   │ ┌──────────────┐ │    │ │ Pattern Learner    │   │         │
│   │ │Three-Zone    │ │    │ │ Temperature        │   │         │
│   │ │Control Logic │ │    │ │ Predictor          │   │         │
│   │ │Hysteresis    │ │    │ │ Energy Optimizer   │   │         │
│   │ │Occupancy     │ │    │ └────────────────────┘   │         │
│   │ │Setbacks      │ │    │                          │         │
│   │ └──────────────┘ │    │ ┌────────────────────┐   │         │
│   └──────────────────┘    │ │ Q-Learning         │   │         │
│                           │ │ Adaptive Controller│   │         │
│                           │ └────────────────────┘   │         │
│                           └──────────────────────────┘         │
├─────────────────────────────────────────────────────────────────┤
│                      PHYSICAL LAYER                             │
│              (Sensors + HVAC Plant + Environment)               │
│                                                                 │
│   ┌──────────┐ ┌──────────┐ ┌───────┐ ┌──────────────────┐    │
│   │DHT22     │ │PIR       │ │Weather│ │HVAC Plant        │    │
│   │Temp/Hum  │ │Occupancy │ │Gen    │ │Bidirectional     │    │
│   │Sensor    │ │Sensor    │ │       │ │Heat Pump         │    │
│   └──────┬───┘ └────┬─────┘ └───┬───┘ └────────┬─────────┘    │
│          │          │           │              │               │
│          └──────────┴───────────┴──────────────┘               │
│                         │                                       │
│              ┌──────────▼──────────┐                           │
│              │ RC Thermal Model    │                           │
│              │ (Room Physics)      │                           │
│              └─────────────────────┘                           │
├─────────────────────────────────────────────────────────────────┤
│                      DATA LAYER                                 │
│              (SQLite + Data Export)                             │
│   ┌─────────────────┐  ┌──────────┐  ┌───────────────────┐    │
│   │ simulation_data  │  │ CSV      │  │ Q-table           │    │
│   │ (SQLite table)   │  │ Export   │  │ (NumPy .npy)      │    │
│   └─────────────────┘  └──────────┘  └───────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
Outdoor Weather ──►┐
                   │
Occupancy ─────────┼──► Thermal Model ──► Sensor Simulation ──► Controller
                   │        ▲                                       │
Solar Gain ────────┘        │                                       │
                            │                                       ▼
                    HVAC Plant ◄──────────── Action (HVAC Command) ──┘
                        │
                        ▼
                   Data Logger ──► SQLite ──► Dashboard
```

## Component Interaction

### Simulation Loop (1 iteration = 1 minute)

1. **Weather Generator** provides outdoor T and humidity
2. **Occupancy Generator** provides occupancy state and motion events
3. **Controller** reads sensor state and computes an HVAC action
4. **HVAC Plant** applies the action with compressor protection
5. **Thermal Model** integrates the physics (envelope + HVAC + solar + internal)
6. **Sensors** add noise to the true values
7. **Data Logger** records everything to SQLite
8. **AI Layer** updates patterns and predictions
9. Repeat

### Embedded System (ESP32)

The ESP32 firmware mirrors the simulation's control logic:

```
Sensor Read (2s) ──► Average Filter ──► Control Logic ──► Relay Output
       │                                    │
       └──────► MQTT Publish ◄──────────────┘
                    │
                    ▼
              Remote Dashboard / Home Assistant
```
