import socket
import time
from PySide6.QtCore import QThread, Signal

class UdpReceiver(QThread):
    # Signals to communicate with the main thread
    data_received = Signal(float, float, float, float)  # elapsed_time, x, y, z
    error_occurred = Signal(str)                        # error message
    status_changed = Signal(bool)                       # True: listening, False: inactive

    def __init__(self, ip="0.0.0.0", port=1234):
        super().__init__()
        self.ip = ip
        self.port = port
        self._running = False

    def run(self):
        self._running = True
        self.status_changed.emit(True)
        sock = None
        start_time = time.time()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Allow address reuse
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.ip, self.port))
            sock.settimeout(0.5)  # Moderate timeout to allow breaking out of loop
        except Exception as e:
            self.error_occurred.emit(f"Port binding error: {e}")
            self._running = False
            self.status_changed.emit(False)
            return

        while self._running:
            try:
                data, addr = sock.recvfrom(1024)
                message = data.decode('utf-8').strip()
                
                # Parse message. Expected format: "X:10 Y:-5 Z:20"
                # Remove prefixes and split to extract values
                clean_msg = message.replace('X:', '').replace('Y:', '').replace('Z:', '')
                parts = clean_msg.split()
                
                if len(parts) == 3:
                    try:
                        x = float(parts[0])
                        y = float(parts[1])
                        z = float(parts[2])
                        elapsed_t = time.time() - start_time
                        self.data_received.emit(elapsed_t, x, y, z)
                    except ValueError:
                        self.error_occurred.emit(f"Invalid numeric data in message: '{message}'")
            except socket.timeout:
                continue
            except Exception as e:
                self.error_occurred.emit(f"Packet receiving error: {e}")

        if sock:
            try:
                sock.close()
            except Exception:
                pass
        self.status_changed.emit(False)

    def stop(self):
        self._running = False
        # Block until the socket thread terminates
        self.wait()
