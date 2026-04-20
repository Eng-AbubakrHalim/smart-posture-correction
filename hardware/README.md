# Hardware Files

## PCB Design — CAPSTONE-C2G05 (KiCad)

The full KiCad project (schematic + 4-layer PCB layout + Gerbers) is located on the project workstation at:

```
CAPSTONE/Capstone pcb/
├── Capstone pcb.kicad_pro
├── Capstone pcb.kicad_sch
├── Capstone pcb.kicad_pcb
└── Gerbers/
```

### Key Components
| Ref | Part | Function |
|-----|------|----------|
| U1  | Seeed XIAO ESP32-C3-SMD | Main MCU — WiFi + BLE |
| U2  | LM7805 (TO-220) | 5V linear voltage regulator |
| Q1  | S8050 BJT (NPN) | Vibration motor driver |
| U3  | ACC1 (MPU6050-compatible) | 3-axis accelerometer / IMU |
| M1  | DC vibration motor | Haptic feedback actuator |

### Schematic Highlights
- Input: 9V battery → LM7805 → 5V rail → XIAO (3.3V internal LDO)
- Motor drive: S8050 BJT, base driven by GPIO 21 via 1kΩ resistor, flyback diode across motor
- IMU: I2C on SDA=GPIO6, SCL=GPIO7 (XIAO D4/D5)
- Flex sensor + FSR: resistor divider to ADC1 (GPIO 2 & 3, safe with WiFi)
- Push-button I/O for manual calibration override

### Ordering Gerbers
Send the `Gerbers/` folder to your preferred PCB fab (JLCPCB, PCBWay, etc.).
Recommended spec: 4-layer, 1.6mm, HASL finish.

---

## Enclosure Design (SolidWorks → STL)

Compact ergonomic casing designed to house the PCB on the upper back.

```
CAPSTONE/
├── Casing - lowerhalf-1.STL
├── Casing - lowerhalf-2.STL
├── Casing - magnet-1.STL
├── Casing - magnet-5.STL
├── Casing - pcb-1.STL
└── Casing - batteryholder-1.STL
```

Print settings: PLA, 0.2mm layer height, 20% infill.  
Magnets used for tool-free assembly — compatible with 8mm × 2mm neodymium disc magnets.
