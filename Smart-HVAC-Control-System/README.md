# Smart HVAC Control System

A production-grade **bidirectional Smart HVAC Control System** prototype for residential rooms, featuring a physics-based thermal simulation, AI-powered adaptive control, and a premium Streamlit monitoring dashboard.

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SMART HVAC CONTROL SYSTEM                        │
├──────────────┬──────────────────┬────────────────────────────────────┤
│  SENSING     │   PROCESSING     │   ACTUATION                       │
│  LAYER       │   LAYER          │   LAYER                           │
├──────────────┼──────────────────┼────────────────────────────────────┤
│ DHT22        │ Rule-Based       │ Relay Module (Cooling)            │
│ (Temp/Hum)   │ Controller       │ Relay Module (Heating)            │
│              │                  │                                    │
│ PIR/mmWave   │ Q-Learning       │ Compressor Protection             │
│ (Occupancy)  │ Adaptive Ctrl    │ Short-Cycle Prevention            │
│              │                  │                                    │
│ Weather API  │ Prediction       │                                    │
│ (Outdoor)    │ Engine           │                                    │
├──────────────┴──────────────────┴────────────────────────────────────┤
│  DATA LAYER: SQLite Logging │ Streamlit Dashboard │ Energy Reports  │
└─────────────────────────────────────────────────────────────────────┘
```

## ✨ Key Features

- **Bidirectional Control**: Cooling (❄️ >26°C) + Heating (🔥 <20°C) + Idle deadband (20–26°C)
- **Two Control Strategies**: Rule-based baseline vs Q-Learning adaptive controller
- **RC Thermal Model**: Physics-based room simulation with solar gain, occupancy heat, and humidity
- **AI Layer**: Pattern learning, temperature prediction, and energy optimization
- **Compressor Protection**: 3-minute minimum cycle time prevents short-cycling
- **Premium Dashboard**: Streamlit app with dark theme, Plotly charts, and real-time gauges
- **ESP32 Firmware**: Complete Arduino code with WiFi, MQTT, OTA updates
- **Energy Analysis**: Detailed comparison with annual savings projections

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.9+ required
python --version

# Install dependencies
pip install -r requirements.txt
```

### Run Simulation

```bash
# Rule-based controller (summer, 7 days)
python run_simulation.py

# Adaptive Q-Learning controller
python run_simulation.py --controller adaptive

# Winter scenario
python run_simulation.py --season winter

# Custom duration
python run_simulation.py --days 14 --season spring
```

### Compare Controllers

```bash
# Side-by-side comparison with energy analysis
python run_comparison.py

# Winter comparison
python run_comparison.py --season winter --days 7
```

### Launch Dashboard

```bash
# Start the Streamlit monitoring dashboard
streamlit run dashboard/app.py
```

## 📁 Project Structure

```
HVAC/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
│
├── simulation/                        # Physics simulation engine
│   ├── thermal_model.py               # RC thermal model
│   ├── environment.py                 # Gym-style simulation environment
│   ├── sensors.py                     # Simulated DHT22 + PIR sensors
│   ├── hvac_plant.py                  # Bidirectional HVAC plant model
│   ├── weather.py                     # Outdoor weather generator
│   ├── occupancy.py                   # Occupancy pattern generator
│   └── data_logger.py                 # SQLite data logging
│
├── controllers/                       # Control strategies
│   ├── base_controller.py             # Abstract controller interface
│   ├── rule_based.py                  # Three-zone rule-based controller
│   ├── adaptive_qlearning.py          # Q-Learning adaptive controller
│   └── utils.py                       # Shared utilities
│
├── ai/                                # AI / Optimization layer
│   ├── pattern_learner.py             # Temperature pattern recognition
│   ├── predictor.py                   # Short-term temperature prediction
│   └── energy_optimizer.py            # Comfort vs energy trade-off
│
├── dashboard/                         # Streamlit monitoring dashboard
│   ├── app.py                         # Main dashboard application
│   ├── components/
│   │   ├── gauges.py                  # Temperature/humidity gauges
│   │   ├── charts.py                  # Time-series charts
│   │   ├── controls.py                # Sidebar control panel
│   │   └── energy_report.py           # Energy consumption reports
│   └── styles/
│       └── theme.py                   # Premium dark theme
│
├── firmware/                          # ESP32 embedded firmware
│   ├── esp32_hvac_controller/
│   │   └── esp32_hvac_controller.ino  # Complete Arduino sketch
│   └── wiring_diagram.md             # Hardware connection guide
│
├── docs/                              # Engineering documentation
│   ├── architecture.md                # System architecture
│   ├── control_logic.md               # Control strategy explanation
│   ├── energy_analysis.md             # Energy efficiency discussion
│   └── improvements.md                # Future improvements
│
├── data/                              # Generated data (auto-created)
├── run_simulation.py                  # Main simulation entry point
└── run_comparison.py                  # Controller comparison tool
```

## 🌡️ Control Logic

### Three-Zone Bidirectional Control

| Zone | Temperature | Action | Purpose |
|------|------------|--------|---------|
| ❄️ Cooling | T > 26°C | AC compressor ON | Remove excess heat |
| ⚖️ Idle | 20–26°C | System OFF | Energy conservation |
| 🔥 Heating | T < 20°C | Heat pump ON | Maintain warmth |

### Hysteresis (Anti-Oscillation)

```
Cooling ON  at T > 26.5°C  (threshold + 0.5°C hysteresis)
Cooling OFF at T < 25.5°C  (threshold - 0.5°C hysteresis)
Heating ON  at T < 19.5°C
Heating OFF at T > 20.5°C
```

### Occupancy-Aware Setbacks

| State | Cooling Threshold | Heating Threshold |
|-------|------------------|------------------|
| Occupied | 26°C | 20°C |
| Unoccupied | 28°C | 18°C |
| Night (11pm–6am) | 27°C | 19°C |

## 🧠 AI Layer

1. **Pattern Learner** — Identifies daily temperature/occupancy patterns
2. **Temperature Predictor** — Linear regression model predicting T at 15/30/60 min ahead
3. **Energy Optimizer** — Pareto-optimal comfort/energy trade-off analysis

## 📊 Expected Results

| Metric | Rule-Based | Adaptive Q-Learning |
|--------|-----------|-------------------|
| Daily Energy (kWh) | ~12-15 | ~8-11 |
| Comfort Score (%) | ~88-92 | ~90-95 |
| Energy Savings | baseline | **20-35%** |

## ⚡ ESP32 Hardware

See [`firmware/wiring_diagram.md`](firmware/wiring_diagram.md) for complete hardware setup.

**Required components:**
- ESP32 DevKit v1
- DHT22 sensor + 10kΩ pull-up resistor
- PIR motion sensor (HC-SR501)
- 2-channel opto-isolated relay module
- 5V/2A power supply

## 📄 License

MIT License — See LICENSE file for details.
