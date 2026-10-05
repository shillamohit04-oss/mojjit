# Real-World Improvements & Limitations

## Current Limitations

1. **Single-zone model**: Real buildings have multiple zones with thermal coupling
2. **Simplified thermal model**: RC model omits radiation, stratification, and infiltration dynamics
3. **Tabular Q-learning**: Limited to 9,600 discretized states (coarse resolution)
4. **No weather forecast**: System is reactive to outdoor conditions, not predictive
5. **Fixed COP model**: Real heat pump COP varies with load, refrigerant charge, and airflow
6. **No fault detection**: System assumes all sensors and actuators are functioning correctly

## Proposed Improvements

### Short-Term (Next Iteration)
- **Weather API integration**: Use 24h forecast for predictive pre-conditioning
- **Deep RL upgrade**: Replace tabular Q-learning with PPO/SAC for continuous action space
- **Multi-occupant tracking**: BLE beacons or mmWave radar for precise occupant counting
- **Electricity TOU pricing**: Shift loads to off-peak hours

### Medium-Term (Production System)
- **Multi-zone control**: Coordinate multiple room controllers via central gateway
- **BACnet/Modbus integration**: Interface with commercial BMS infrastructure
- **Fault detection and diagnostics (FDD)**: ML-based anomaly detection on sensor data
- **Cloud dashboard**: Remote monitoring via MQTT → InfluxDB → Grafana pipeline
- **Digital twin**: EnergyPlus model calibrated to actual building for simulation-based optimization

### Long-Term (Research)
- **Model Predictive Control (MPC)**: Optimize over rolling 24h horizon with weather + pricing
- **Federated learning**: Share control policies across similar buildings without sharing data
- **Grid-interactive HVAC**: Participate in demand response programs for utility incentives
- **Thermal storage integration**: Phase-change materials for load shifting

## Safety Considerations

1. Always implement hardware-level temperature limits (independent of software)
2. Use watchdog timers on microcontrollers
3. Implement fail-safe relay states (relays OFF on power loss)
4. Compressor short-cycle protection must be enforced at hardware and software levels
5. Never allow simultaneous heating and cooling activation
