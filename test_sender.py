import socket
import time
import math
import random

# Target settings matching the dashboard defaults
TARGET_IP = "127.0.0.1"
TARGET_PORT = 1234
SEND_RATE_HZ = 50.0  # Send 50 packets per second (every 20ms)

def run_simulation():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[*] Simulating H3LIS200DL accelerometer...")
    print(f"[*] Sending mock data to {TARGET_IP}:{TARGET_PORT} at {SEND_RATE_HZ} Hz")
    print("[*] Press Ctrl+C to stop simulation.")

    start_time = time.time()
    next_crash_time = start_time + 4.0  # Periodic crashes every 8 seconds
    in_crash = False
    crash_elapsed = 0.0
    crash_duration = 0.4  # Crash impact lasts for 400ms
    
    # Peak impact parameters
    crash_x = 0.0
    crash_y = 0.0
    crash_z = 0.0
    
    interval = 1.0 / SEND_RATE_HZ

    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Base vibration noise and normal movement signals
            noise_x = random.uniform(-0.8, 0.8)
            noise_y = random.uniform(-0.8, 0.8)
            noise_z = random.uniform(-0.8, 0.8)
            
            # Simulated flight/movement (gentle sine waves)
            base_x = 2.0 * math.sin(elapsed * 2.0)
            base_y = 1.5 * math.cos(elapsed * 1.5)
            base_z = 9.81 + 1.0 * math.sin(elapsed * 0.5) # Gravity on Z + small fluctuations
            
            # Handle crash triggers
            if current_time >= next_crash_time and not in_crash:
                in_crash = True
                crash_elapsed = 0.0
                # Generate random directions for high g-force crash vector (up to 180g)
                crash_x = random.choice([-1, 1]) * random.uniform(80.0, 180.0)
                crash_y = random.choice([-1, 1]) * random.uniform(80.0, 180.0)
                crash_z = random.choice([-1, 1]) * random.uniform(80.0, 180.0)
                print(f"\n[!] SIMULATING IMPACT CRASH! X: {crash_x:.1f}g, Y: {crash_y:.1f}g, Z: {crash_z:.1f}g")
                next_crash_time = current_time + 8.0  # Schedule next crash in 8s
                
            if in_crash:
                # Damped oscillation model for crash impact decay
                t = crash_elapsed
                decay = math.exp(-12.0 * t)  # Fast decay
                osc = math.cos(2 * math.pi * 35.0 * t)  # High frequency 35Hz vibration during impact
                
                x_val = base_x + noise_x + crash_x * decay * osc
                y_val = base_y + noise_y + crash_y * decay * osc
                z_val = base_z + noise_z + crash_z * decay * osc
                
                crash_elapsed += interval
                if crash_elapsed >= crash_duration:
                    in_crash = False
            else:
                x_val = base_x + noise_x
                y_val = base_y + noise_y
                z_val = base_z + noise_z
                
            # Create payload in the format "X:val Y:val Z:val"
            payload = f"X:{x_val:.3f} Y:{y_val:.3f} Z:{z_val:.3f}"
            sock.sendto(payload.encode('utf-8'), (TARGET_IP, TARGET_PORT))
            
            # Print a status dot occasionally to show it's active
            if int(elapsed * 5) % 10 == 0:
                print(".", end="", flush=True)
                
            # Sleep to maintain frequency
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n[*] Stopping simulation...")
    finally:
        sock.close()

if __name__ == "__main__":
    run_simulation()
