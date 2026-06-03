import sys
from PySide6.QtWidgets import QApplication
from gui_window import GuiWindow

def main():
    # Set high DPI scaling properties for modern screens (especially on Windows)
    # Qt6 enables high-DPI scaling automatically by default.
    
    app = QApplication(sys.argv)
    app.setApplicationName("H3LIS200DL Telemetry Dashboard")
    app.setApplicationDisplayName("H3LIS200DL Telemetry Dashboard")
    
    window = GuiWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
