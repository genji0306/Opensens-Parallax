<p align="center">
  <img src="Opensens ICON.jpg" alt="Opensens Logo" width="120"/>
</p>

<h1 align="center">Opensens Velo — Project Plan</h1>

<p align="center">
  <b>The AI Communication Hub for the E-Bike</b><br/>
  ESP32 Firmware · iOS App · C2X Platform · Qualcomm Vietnam Innovation Challenge
</p>

---

## Context

**Opensens Velo** is an AI-powered communication hub for e-bikes, developed as part of the **Qualcomm Vietnam Innovation Challenge**. With Hanoi's government mandate restricting gasoline vehicles in core districts starting **July 2026**, millions of riders will migrate to electric alternatives. The problem: today's e-bikes are isolated, inefficient, and unintelligent.

**Opensens Velo gives them a central nervous system** — transforming simple vehicles into active, intelligent data nodes in the **Internet of Moving Things (IoMT)**.

The project has three pillars: **ESP32 Firmware**, a **native iOS App**, and the **C2X (Cycle-to-Everything) Platform**. Phase 1 is complete (11 MCP tools deployed, 5 riding modes, full ride data, AI-powered auto-adjust). This plan covers the full system architecture, current progress, and what lies ahead.

---

## 1. Project Summary & Goals

**Mission**: Transform any e-bike into a smart, connected mobility node through an ESP32-based onboard AI module, a branded mobile app, and a cloud-connected social ecosystem.

| Goal | Description |
|------|-------------|
| **ESP32 Firmware** | Gateway bridge for ESP32-C3/C6/S3 — connects to the LVBU pedal assist motor via BLE, adds IMU sensing, voice AI, LCD display, and V2V broadcasting |
| **Opensens iOS App** | Native Swift/SwiftUI iPhone app with Opensens branding — replaces the generic WePower app for controlling the LVBU system, viewing ride data, and accessing the C2X network |
| **C2X Platform** | Cycle-to-Everything ecosystem — connects cyclists via WiFi/5G for safety alerts, smart navigation, healthcare tracking, and social ride sharing |

---

## 2. System Architecture

```
                    OPENSENS C2X CLOUD
           MQTT  /  V2X  /  Social  /  Analytics
                         |
            WiFi/MQTT    |    WebSocket
                         |
     +-----------+       |       +-------------------+
     | ESP32     |       |       | Opensens App      |
     | GATEWAY   |<------+------>| iOS (SwiftUI)     |
     | (C3/C6/S3)|               | + Web (Next.js)   |
     |           |               |                   |
     | BLE Central|               | Web Bluetooth /   |
     | Sensor Hub |               | CoreBluetooth     |
     | AI Voice   |               | Bento Grid UI     |
     | V2V (ESP-NOW)|             | Social Features   |
     | LCD Display |              +--------+----------+
     +------+------+                       |
            |  BLE                         | BLE (Direct)
            v                              v
     +---------------------------------------------+
     |         LVBU MOTOR CONTROLLER                |
     |   Service: 0xFFE0  /  Char: 0xFFE1          |
     |   Proprietary JSON-Binary (CRC16-CCITT)     |
     +---------------------------------------------+
```

**Three connection paths to the LVBU motor:**

1. **ESP32 Gateway** — BLE Central on the bike frame, always-on, sensor fusion + AI
2. **iOS App (CoreBluetooth)** — Direct BLE from iPhone for ride control and monitoring
3. **WebApp (Web Bluetooth)** — Browser-based fallback, no install required

---

## 3. Component Descriptions

### 3.1 ESP32 Firmware

The firmware turns an ESP32 module into an **onboard AI communication hub** mounted on the e-bike. It connects via BLE to the LVBU motor controller and acts as the bike's "brain" — collecting sensor data, managing power intelligently, and enabling vehicle-to-vehicle communication.

#### Supported Hardware Targets

| Target | SoC | Use Case | Dev Platform |
|--------|-----|----------|--------------|
| `esp32_c3_velo` | ESP32-C3 | **Primary production target** — low-power RISC-V with WiFi + BLE | ESP-IDF |
| `esp32_c6_velo` | ESP32-C6 | WiFi 6 + BLE 5.3 + 1.47" LCD display (ST7789) | ESP-IDF |
| `esp32_s3_velo` | ESP32-S3 | Dual-core + AI acceleration for voice processing | ESP-IDF |
| `arduino_esp32_velo` | C3/C6 | Rapid prototyping Arduino sketch | Arduino IDE |

#### Implemented Features

- BLE Central mode — auto-scans and connects to LVBU service `0xFFE0`
- CRC16-CCITT packet builder (Poly `0x1021`, Init `0x0000`)
- JSON-binary protocol: `0x7F | Len_Lo | Len_Hi | {"M":1,"S":0,"F":func,"D":{...}} | CRC_Lo | CRC_Hi`
- 3-second polling loop for voltage, speed, temperature, distance, power, and lock queries
- Hardware pin mapping for LCD, RGB LED, I2C sensors

#### Planned Features (Phases 2–5)

- IMU sensor fusion (MPU6050/ICM20600) for climbing detection and fall alerts
- Xiaozhi AI voice assistant — hands-free Vietnamese voice commands
- LCD 1.47" ST7789 display — speed, battery, mode shown on handlebars
- ESP-NOW V2V broadcasting — real-time safety alerts to nearby cyclists
- NEO-6M/8M GPS module integration for smart routing
- MQTT telemetry to C2X Cloud

#### LVBU BLE Protocol (JSON Protocol — Header 0x7F)

| Command Key | Name | Description |
|-------------|------|-------------|
| `7` | Power Mode | 1=Manual, 2=Leisure, 3=Exercise, 4=Commute, 5=Climbing |
| `8` | Power Level | Assist level 0–255 |
| `30` | Speed | km/h (float, direct value) |
| `38` | Battery | Battery percentage 0–100% (direct value) |
| `37` | Temperature | °C (direct value from motor) |
| `16` | Trip Distance | Current trip in meters |
| `23` | Total Distance | Odometer in meters |
| `31` | Power Output | Watts |
| `36` | Gyro Angle | Accelerometer/gyro data |
| `39` | Lock | 0=unlocked, 1=locked |
| `43` | Gyro Calibrate | Send 1 to trigger calibration |

Function codes: `1` = SET, `2` = QUERY, `3` = ADJUST

#### Source Code Locations

| Item | Path |
|------|------|
| Arduino Sketch | `firmware/arduino_esp32_velo/arduino_esp32_velo.ino` |
| ESP32-C3 | `firmware/esp32_c3_velo/main/` |
| ESP32-C6 | `firmware/esp32_c6_velo/main/` |
| ESP32-S3 | `firmware/esp32_s3_velo/main/` |

#### Hardware: ESP32-C6-LCD-1.47 Pin Map

| Pin | Function | Description |
|-----|----------|-------------|
| GPIO 8 | `PIN_RGB_IO` | WS2812B RGB LED |
| GPIO 23 | `PIN_LCD_BL` | LCD Backlight |
| GPIO 21 | `PIN_LCD_RST` | LCD Reset |
| GPIO 15 | `PIN_LCD_DC` | LCD Data/Command |
| GPIO 14 | `PIN_LCD_CS` | LCD Chip Select |
| GPIO 19 | `PIN_LCD_CLK` | SPI Clock |
| GPIO 20 | `PIN_LCD_MOSI` | SPI MOSI (DIN) |
| GPIO 6/7 | `I2C SDA/SCL` | IMU / Sensor expansion |

---

### 3.2 Opensens iOS App — BUILT & FUNCTIONAL

A native iPhone app built with **Xcode / Swift / SwiftUI** featuring Opensens branding. It replaces the generic WePower app to give riders a premium, branded control interface for their LVBU-powered e-bike — and connects them to the C2X social ecosystem.

#### Implemented Features

- **CoreBluetooth Integration** — Direct BLE connection to LVBU motor (Service `0xFFE0`, Write on `0xFFE1`, Read on `0xFFE2`)
- **Dashboard UI** — Speedometer, battery level, trip distance, current mode — "Limelight" design (neon lime `#ccff00` on deep black `#0a0a0a`)
- **5 Riding Modes** — Commute, Leisure, Manual, Exercise, Climbing — selectable from the app
- **Manual Assist Slider** — Fine-grained power control (0–255 mapped to 0–100%)
- **Motor Lock/Unlock** — Toggle lock state directly from the app
- **Gyro Calibration** — With real-time horizon visualizer showing gyro angle
- **Ride Recording** — Start/stop ride with GPS route tracking, speed sampling every second, and SwiftData persistence
- **Ride History** — Browsable list of past rides with detail view (stats, speed chart, route map)
- **Route Map** — MapKit polyline of GPS route displayed in ride detail view
- **Overspeed Alarm** — Haptic feedback + red banner when speed exceeds configurable threshold
- **Wheel Size Correction** — Distance adjusted for 700C / 26" / 24" wheel circumferences
- **Settings** — Wheel size picker, overspeed alarm slider, firmware version display

#### Planned Features (C2X Integration)

- **Apple HealthKit** — Sync cycling data (calories, heart rate, distance) for healthcare analytics
- **Social Ride Sharing** — Share routes, join group rides, leaderboards via the C2X network
- **Apple Watch Companion** — Glanceable speed, battery, and navigation on the wrist
- **Multi-Device Piconet** — Cadence sensor, heart rate monitor, display unit (UI exists, BLE scanner pending)
- **Ride Data Export** — CSV/GPX export of ride history
- **Statistics Dashboard** — Aggregated analytics across rides

#### Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Swift 5.9+ |
| UI Framework | SwiftUI (iOS 17+) |
| Persistence | SwiftData |
| BLE | CoreBluetooth |
| Maps | MapKit |
| GPS | CoreLocation |
| Build Tool | XcodeGen + Xcode 15+ |
| Architecture | MVVM with @Observable |
| Bundle ID | `io.opensens.velo` |

#### Source Code Locations

| Item | Path |
|------|------|
| App Entry | `ios/VeloApp/VeloApp/VeloApp.swift` |
| BLE Manager | `ios/VeloApp/VeloApp/Services/BLEManager.swift` |
| BLE Protocol | `ios/VeloApp/VeloApp/Services/BLEProtocol.swift` |
| Protocol Keys | `ios/VeloApp/VeloApp/Models/BLEKeys.swift` |
| Dashboard | `ios/VeloApp/VeloApp/Views/Dashboard/DashboardView.swift` |
| XcodeGen Config | `ios/VeloApp/project.yml` |

#### Known Issue

The motor intermittently responds with `81 01` (error code 1 = "Illegal JSON package") instead of telemetry data. The JSON key ordering fix (manual M,S,F,D construction) has been applied. A 50ms command queue spacing (per LVBU demo pattern) may further improve reliability.

**Status:** Built and functional. BLE telemetry works but has intermittent reliability issue under investigation.

---

### 3.3 Opensens C2X Platform

**C2X (Cycle-to-Everything)** is the connected ecosystem layer that transforms individual e-bikes into nodes in an intelligent mobility network. Inspired by automotive V2X standards, adapted for the cycling world with a focus on safety, navigation, and community.

#### Three Pillars

| Pillar | Full Name | Description |
|--------|-----------|-------------|
| **C2P** | Cycle-to-Personal | AI co-pilot — voice control, adaptive power modes, personalized performance tracking |
| **C2I** | Cycle-to-Infrastructure | Smart city integration — traffic light timing (SPAT), congestion avoidance, route optimization |
| **C2V** | Cycle-to-Vehicle | Vehicle mesh network — real-time safety alerts, group ride sync, predictive analytics |

#### Connectivity Layers

| Layer | Protocol | Purpose |
|-------|----------|---------|
| **V2V** | ESP-NOW | Peer-to-peer safety alerts between nearby cyclists (low latency, no WiFi needed) |
| **V2I** | MQTT / Open-V2X | Traffic signal timing (SPAT), green wave optimization |
| **V2C** | WiFi + MQTT | Telemetry upload, cloud analytics, AI route computation |
| **V2S** | WebSocket | Social features — ride sharing, community, leaderboards |

#### Intelligent Features

| Feature | How It Works |
|---------|-------------|
| **Climbing Boost** | IMU detects pitch > 5 degrees + cadence drop → auto 100% assist |
| **Economy Mode** | Battery < 34V → clamp assist to 30%, pulsed acceleration |
| **Fatigue Detection** | HR sensor + power output analysis (cardiac drift > 5%) |
| **Smart Routing** | Low battery → auto-switch to flattest route via Cloud MCP |
| **Voice Control** | Xiaozhi AI — "Set speed limit to 25", "Switch to exercise mode" (Vietnamese + English) |
| **Predictive Maintenance** | Aggregate performance data for battery longevity predictions |

#### AI Framework

The system uses the **Model Context Protocol (MCP)** as its AI control framework. MCP tools like `set_power_level`, `get_full_status`, and `auto_adjust_power` allow the AI to discover and control hardware features through a standardized interface. **11 MCP tools are already deployed** (Phase 1 complete).

---

## 4. Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Firmware** | C (ESP-IDF v5.0+), Arduino C++ | FreeRTOS, NVS Flash, BLE GAP/GATT APIs |
| **iOS App** | Swift 5.9+, SwiftUI, CoreBluetooth | Xcode 15+, iOS 17+, MVVM architecture |
| **WebApp** | Next.js 16, React 19, TypeScript 5 | Tailwind CSS 4, Web Bluetooth API, Lucide icons |
| **AI Framework** | Model Context Protocol (MCP) | 11 tools deployed — voice control, power management, ride stats |
| **Voice AI** | Xiaozhi (ESP32-S3) | On-device Vietnamese/English voice recognition |
| **Communication** | BLE 5.0+, WiFi 6 (C6), ESP-NOW, MQTT | CRC16-CCITT for packet integrity |
| **Hardware** | ESP32-C3/C6/S3, ST7789 LCD, MPU6050 IMU, NEO-6M GPS | I2C/SPI peripherals |
| **Cloud** | MQTT broker, WebSocket server | Planned — telemetry, analytics, social features |

### Key Dependencies

- **LVBU Smart E-Bike Kit** — BLE protocol documented in `LvBuBleDemo/`
- **ESP-IDF toolchain v5.0+** — for C3/C6/S3 firmware builds
- **Xcode 15+** with iOS 17 SDK — for the native iPhone app
- **Node.js 18+** — for the Next.js WebApp

---

## 5. Setup & Installation

### 5.1 ESP32 Firmware (ESP-IDF)

```bash
# Prerequisites: Install ESP-IDF v5.0+
# https://docs.espressif.com/projects/esp-idf/en/latest/esp32c3/get-started/

# Clone and build for ESP32-C6 (recommended target with LCD)
cd firmware/esp32_c6_velo
idf.py set-target esp32c6

# Build and flash
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

### 5.2 ESP32 Firmware (Arduino IDE)

1. Install Arduino IDE with ESP32 board package v3.0+
2. Open `firmware/arduino_esp32_velo/arduino_esp32_velo.ino`
3. Select board: **ESP32C3 Dev Module** or **ESP32C6 Dev Module**
4. Click **Upload**

### 5.3 iOS App (Xcode)

```bash
# Prerequisites: Xcode 15+, macOS Sonoma+, physical iPhone with iOS 17+
# Note: BLE requires a physical device — Simulator does not support CoreBluetooth

# Once the app is created:
open VeloApp.xcodeproj
# Select your iPhone as the build target
# Build & Run (Cmd+R)
```

### 5.4 WebApp (Next.js)

```bash
cd velo-web
npm install
npm run dev
# Open http://localhost:3000 on a device with Bluetooth
# Use Chrome or Edge (Web Bluetooth requires a Chromium-based browser)
```

---

## 6. How the System Enables Connectivity & Social Sharing

### Rider-Level (C2P)

Each rider's ESP32 module + app creates a **personal mobility profile**: riding patterns, preferred routes, fitness data, battery usage. The AI co-pilot adapts in real-time — switching to "Commute" mode during rush hour, activating "Climbing Boost" on inclines, conserving battery on long routes.

### City-Level (C2I)

When connected to WiFi or 5G, bikes share **anonymized telemetry** with city infrastructure. Traffic signals can optimize timing for cyclists (SPAT/green wave). Cloud MCP computes **context-aware routes** — for example, a rider with low battery is automatically routed to avoid steep hills.

### Network-Level (C2V)

Nearby cyclists form **ad-hoc mesh networks** via ESP-NOW. Safety alerts propagate instantly: "Vehicle approaching from behind", "Pothole ahead", "Group ride forming at intersection". Aggregated data enables **predictive maintenance** alerts and battery longevity predictions across the fleet.

### Social Layer (V2S)

The app and cloud platform provide:

- **Ride Sharing** — Share completed routes with the community
- **Group Rides** — Join or create group rides with real-time position tracking
- **Leaderboards** — Distance, elevation, and efficiency rankings
- **Safety Score** — Community-driven road safety ratings
- **Healthcare Insights** — HealthKit integration for personal wellness tracking

---

## 7. Development Roadmap

### Phase 1: Core Intelligence — COMPLETE

- [x] 11 MCP tools deployed (`set_power_level`, `get_full_status`, `auto_adjust_power`, etc.)
- [x] 5 intelligent riding modes (Commute, Leisure, Manual, Exercise, Climbing)
- [x] Full ride data & statistics (speed, distance, uphill distance, avg/max speed)
- [x] AI-powered auto-adjust (Economy Mode, Climbing Boost)
- [x] Next.js WebApp with Web Bluetooth
- [x] ESP32 firmware (Arduino + ESP-IDF, 4 targets)

### Phase 2: iOS App & Protocol Sync — COMPLETE

- [x] **iOS App development** (Swift/SwiftUI + CoreBluetooth) — full MVVM app with 4-tab navigation
- [x] BLE telemetry polling (speed, battery, temperature, distances, power, lock)
- [x] Ride recording with GPS route tracking and speed sampling
- [x] Ride history with SwiftData persistence, speed chart, and route map
- [x] Overspeed alarm with haptic feedback
- [x] Wheel size correction for distance calculations
- [x] Protocol header sync (0x7F) across all platforms (iOS, Web, ESP32)
- [x] Battery percentage fix (key "38" returns % directly)
- [x] Auto Mode Selection — AI recommends mode changes based on battery, speed, terrain, and motor temperature
- [x] Advanced Battery Analysis and Range Prediction — Li-ion discharge curve modeling, Wh/km efficiency tracking, confidence-rated estimates

### Phase 3: C2I Hardware Integration — MEDIUM PRIORITY

- [x] NEO-6M/8M GPS module integration (`velo_gps` component, NMEA parsing, position/velocity/satellite tracking)
- [ ] `GpsManager` class and `get_location` MCP tool (pending firmware-WebApp bridge)
- [x] IMU sensor fusion (MPU6050/ICM20600 via `velo_imu` component, pitch/roll/yaw, step detection)
- [x] LCD 1.47" display integration (ST7789 via `velo_lcd`, speedometer/battery/mode UI)

### Phase 4: C2I Smart Routing — MEDIUM PRIORITY

- [ ] Cloud MCP integration for context-aware routing
- [ ] Turn-by-turn voice navigation instructions
- [ ] Xiaozhi AI voice assistant integration

### Phase 5: C2V Predictive Network — FUTURE FOCUS

- [ ] ESP-NOW V2V safety broadcasting
- [ ] Predictive maintenance alerts
- [ ] Aggregate performance data for network-level optimization
- [ ] Social ride sharing features
- [ ] Open-V2X SPAT integration

---

## 8. Limitations & Future Considerations

### Current Limitations

- **iOS BLE reliability** — Motor intermittently sends error responses (`81 01`) instead of telemetry; under investigation
- **BLE range** is limited (~10–30m); V2V via ESP-NOW extends to ~200m line-of-sight
- **Web Bluetooth** only works in Chromium-based browsers (not Safari or Firefox)
- **Voice AI** (Xiaozhi) requires ESP32-S3 for on-device processing
- **C2X Cloud** infrastructure (MQTT broker, analytics backend) is not yet deployed
- **GPS module** hardware integration is pending (Phase 3)

### Future Improvements

- Android app (Kotlin/Jetpack Compose) for broader market reach
- 5G/LTE module integration for always-connected operation
- Machine learning models for predictive power management trained on ride data
- Integration with third-party e-bike controllers beyond LVBU
- Open API for third-party developers to build on the C2X platform

### Contribution Guidelines

This is a proprietary project by **Opensens**. Please contact the team for access and contribution guidelines.

---

## 9. References

| Resource | Location |
|----------|----------|
| Main README | `README.md` |
| C2X Vision Deck | `Opensens Cycle-to-Everything_E-Bike_Intelligence.pdf` |
| LVBU BLE Protocol Docs | `LvBuBleDemo/Lvbu Smart E-Bike Kit Bluetooth Communication Development Documentation.md` |
| LVBU Demo App (APK) | `LvBuBleDemo/app-release.apk` |
| LVBU Demo Source (Flutter) | `LvBuBleDemo/lvbubledemo/lvbu_ble_demo/` |
| WePower iOS Screenshots | `Iphone LVBU app/` |
| IceNav GPS Reference | `IceNav-v3-master/` |

---

<p align="center">
  All rights reserved &copy; Opensens 2026
</p>
