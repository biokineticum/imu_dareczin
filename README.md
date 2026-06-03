# High-G Wireless Impact Logger (±200g)

This project is a wireless, high-speed impact and crash data logger. It uses a Seeed Studio XIAO ESP32-C3 microcontroller and a DFRobot H3LIS200DL accelerometer to measure extreme forces up to ±200g. The system samples data at 1000 Hz and transmits it wirelessly via UDP to a local computer, where a Python script logs the data to a CSV file and displays a real-time plot.

## Hardware Requirements

| Component | Description |
| :--- | :--- |
| **Microcontroller** | Seeed Studio XIAO ESP32-C3 |
| **Accelerometer** | DFRobot Fermion: H3LIS200DL (SEN0405) |
| **Battery (Optional)** | 3.7V LiPo Battery (e.g., 150mAh) |
| **Charger** | Safe 50mA LiPo Charger (e.g., DFRobot DFR0668) |

> **Safety Warning regarding LiPo Batteries:** > Do not solder a small LiPo battery (like 150mAh) directly to the XIAO ESP32-C3 without a physical switch. The built-in charging circuit on the XIAO delivers ~380mA, which will permanently damage and potentially ignite small capacity batteries. Always use a dedicated, low-current charger (like 50mA) for small cells.

## Wiring Diagram (SPI Interface)

To ensure stable 1000 Hz SPI communication, **do not use loose jumper wires in the sensor's holes.** You must solder header pins to the sensor or solder the wires directly to the pads. 

| H3LIS200DL (Sensor) | XIAO ESP32-C3 | Function |
| :--- | :--- | :--- |
| **VCC** | **3V3** | Power (3.3V) |
| **GND** | **GND** | Ground |
| **SCL** | **D8** | SPI Clock (SCK) |
| **SDO** | **D9** | SPI MISO |
| **SDA** | **D10** | SPI MOSI |
| **CS** | **D7** | Chip Select |
| **INT1 / INT2** | *Not Connected* | Interrupts (Not used) |

---

## Software Setup (Arduino IDE)

To flash the firmware to the XIAO ESP32-C3, you need to configure the Arduino IDE with the correct board definitions and libraries.

1. **Install Arduino IDE:** Download and install the latest version from [arduino.cc](https://www.arduino.cc/en/software).
2. **Add ESP32 Board Support:**
   * Open Arduino IDE, go to `File` > `Preferences`.
   * Paste the following URL into the "Additional Boards Manager URLs" field:
     `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
   * Click OK.
3. **Install ESP32 Boards:**
   * Go to `Tools` > `Board` > `Boards Manager...`
   * Search for `esp32` and install the package by **Espressif Systems**.
4. **Select Your Board:**
   * Go to `Tools` > `Board` > `esp32` and select **XIAO_ESP32C3**.
5. **Install Sensor Library:**
   * Go to `Sketch` > `Include Library` > `Manage Libraries...`
   * Search for `H3LIS200DL` and install the **DFRobot_LIS** library.

---

## 1. Microcontroller Firmware (C++)

This code sets up the ESP32-C3 as an independent Wi-Fi Access Point and broadcasts the accelerometer data using UDP. 

```cpp
#include <DFRobot_LIS.h>
#include <WiFi.h>
#include <WiFiUdp.h>

// CS pin definition for the SPI interface
#define H3LIS200DL_CS D7

// --- WI-FI ACCESS POINT SETTINGS ---
const char *ssid = "CrashSensor_AP";
const char *password = "123456789"; // Must be at least 8 characters

// --- UDP BROADCAST SETTINGS ---
const int udpPort = 1234;
const char *udpAddress = "192.168.4.255"; // Default broadcast IP for ESP32 AP

WiFiUDP udp;
DFRobot_H3LIS200DL_SPI acce(H3LIS200DL_CS);

void setup(void){
  Serial.begin(115200);
  
  // 1. Start Wi-Fi Access Point
  Serial.println("Starting Wi-Fi AP...");
  WiFi.softAP(ssid, password);
  Serial.print("AP Ready. Sensor IP: ");
  Serial.println(WiFi.softAPIP());

  // 2. Start UDP
  udp.begin(udpPort);

  // 3. Initialize Sensor
  Serial.println("Initializing H3LIS200DL...");
  while(!acce.begin()){
     Serial.println("Sensor not found! Check wiring.");
     delay(1000);
  }
  
  // Set range to +/- 200g and sample rate to 1000 Hz
  acce.setRange(DFRobot_LIS::eH3lis200dl_200g);
  acce.setAcquireRate(DFRobot_LIS::eNormal_1000HZ);
  
  Serial.println("Sensor ready! Broadcasting UDP packets...");
}

void loop(void){
  // Read raw acceleration in 'g'
  long ax = acce.readAccX();
  long ay = acce.readAccY();
  long az = acce.readAccZ();

  // Format data packet
  String packet = "X:" + String(ax) + " Y:" + String(ay) + " Z:" + String(az);

  // Broadcast via UDP
  udp.beginPacket(udpAddress, udpPort);
  udp.print(packet);
  udp.endPacket();

  // Print to Serial for debugging via USB
  Serial.println(packet);

  // 1ms delay for ~1000Hz loop rate
  delay(1);
}
```

---

## 2. PC Data Logger & Visualizer (Python)

This script connects to the UDP stream, logs every single data point to a CSV file in the background, and displays a live, smooth plot of the last 200 data points.

**Dependencies:** You must have Python installed. Open your terminal/command prompt and run:
`pip install matplotlib`

```python
import socket
import threading
import time
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque

# --- CONFIGURATION ---
UDP_IP = "0.0.0.0"  
UDP_PORT = 1234
MAX_POINTS = 200    

# Data queues for plotting
data_x = deque(maxlen=MAX_POINTS)
data_y = deque(maxlen=MAX_POINTS)
data_z = deque(maxlen=MAX_POINTS)
data_t = deque(maxlen=MAX_POINTS)

# Generate unique filename for the session
filename = datetime.now().strftime("crash_test_%Y%m%d_%H%M%S.csv")

running = True
start_time = time.time()

# --- BACKGROUND THREAD: UDP LISTENER & CSV WRITER ---
def udp_listener():
    global running
    with open(filename, "w") as f:
        f.write("Time[s],X[g],Y[g],Z[g]\n")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((UDP_IP, UDP_PORT))
        sock.settimeout(1.0)
        print(f"[*] Listening for UDP packets... Logging to: {filename}")

        while running:
            try:
                data, addr = sock.recvfrom(1024)
                message = data.decode('utf-8').strip()
                
                # Parse the incoming string "X:10 Y:-5 Z:20"
                parts = message.replace('X:', '').replace('Y:', '').replace('Z:', '').split()
                
                if len(parts) == 3:
                    x = float(parts[0])
                    y = float(parts[1])
                    z = float(parts[2])
                    current_t = time.time() - start_time
                    
                    # Write immediately to CSV
                    f.write(f"{current_t:.4f},{x},{y},{z}\n")
                    
                    # Append to queues for the live plot
                    data_t.append(current_t)
                    data_x.append(x)
                    data_y.append(y)
                    data_z.append(z)
                    
            except socket.timeout:
                continue 
            except Exception as e:
                print(f"Packet decode error: {e}")

# Start the background thread
thread = threading.Thread(target=udp_listener)
thread.start()

# --- FOREGROUND THREAD: LIVE PLOTTING ---
fig, ax = plt.subplots(figsize=(10, 6))
fig.canvas.manager.set_window_title('H3LIS200DL Data Logger')
ax.set_title('Live High-G Impact Data')
ax.set_xlabel('Time [s]')
ax.set_ylabel('Acceleration [g]')
ax.grid(True, linestyle='--', alpha=0.6)

line_x, = ax.plot([], [], 'r-', label='X Axis')
line_y, = ax.plot([], [], 'g-', label='Y Axis')
line_z, = ax.plot([], [], 'b-', label='Z Axis')
ax.legend(loc='upper left')

def update(frame):
    if len(data_t) > 0:
        line_x.set_data(data_t, data_x)
        line_y.set_data(data_t, data_y)
        line_z.set_data(data_t, data_z)
        
        ax.set_xlim(data_t[0], data_t[-1])
        ax.set_ylim(-210, 210) # Fixed scale to sensor's maximum limits
        
    return line_x, line_y, line_z

# Update plot every 50ms (20 FPS)
ani = animation.FuncAnimation(fig, update, interval=50, blit=False, cache_frame_data=False)

try:
    plt.show()
except KeyboardInterrupt:
    pass
finally:
    print("\n[*] Shutting down...")
    running = False
    thread.join()
    print(f"[*] Session saved successfully to: {filename}")
```

## How to run the system

1. Flash the C++ firmware to the XIAO ESP32-C3 via Arduino IDE.
2. Disconnect the microcontroller from your PC and power it via the battery.
3. Connect your PC's Wi-Fi to the `CrashSensor_AP` network (Password: `123456789`).
4. Run the Python script (`python logger.py`).
5. Perform the drop/crash test.
6. Close the plot window to safely save the `.csv` file with all recorded data.
