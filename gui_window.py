import os
import time
import math
import subprocess
from collections import deque
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QCheckBox,
    QFileDialog, QFrame, QMessageBox, QSlider
)
from PySide6.QtCore import QTimer, Slot, Qt, QUrl
from PySide6.QtGui import QFont, QDesktopServices

# Matplotlib embedding in Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from udp_receiver import UdpReceiver
from data_logger import DataLogger

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=8, height=5, dpi=100):
        # Deep dark theme matching the GUI
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#121214')
        self.axes = self.fig.add_subplot(111)
        self.axes.set_facecolor('#1e1e24')
        
        # Color axes ticks and labels
        self.axes.tick_params(colors='#a4b0be', which='both', labelsize=9)
        for spine in self.axes.spines.values():
            spine.set_color('#2f303a')
            
        self.axes.xaxis.label.set_color('#a4b0be')
        self.axes.yaxis.label.set_color('#a4b0be')
        self.axes.set_xlabel('Czas [s]', fontsize=10)
        self.axes.set_ylabel('Przeciążenie [g]', fontsize=10)
        self.axes.set_title('Wykres przeciążenia na żywo', color='#ffffff', fontsize=12, pad=12)
        self.axes.grid(True, color='#2f303a', linestyle='--', alpha=0.5)
        
        # Initialize lines with empty data and high contrast neon colors
        self.line_x, = self.axes.plot([], [], color='#ff4757', label='Oś X (Czerwona)', linewidth=2.0)
        self.line_y, = self.axes.plot([], [], color='#2ed573', label='Oś Y (Zielona)', linewidth=2.0)
        self.line_z, = self.axes.plot([], [], color='#1e90ff', label='Oś Z (Niebieska)', linewidth=2.0)
        
        self.axes.legend(loc='upper left', facecolor='#1e1e24', edgecolor='#2f303a', labelcolor='#ffffff', fontsize=9)
        self.axes.set_ylim(-210, 210)
        self.axes.set_xlim(0, 10)
        
        super().__init__(self.fig)
        
    def update_data(self, times, xs, ys, zs, window_seconds=5.0, show_x=True, show_y=True, show_z=True, autoscale=True):
        t_data = list(times)
        
        # Configure trace visibility
        self.line_x.set_visible(show_x)
        self.line_y.set_visible(show_y)
        self.line_z.set_visible(show_z)
        
        if len(t_data) > 0:
            # Find slicing index for the time window
            max_t = t_data[-1]
            min_t = max_t - window_seconds
            start_idx = 0
            for i, t in enumerate(t_data):
                if t >= min_t:
                    start_idx = i
                    break
                    
            plot_t = t_data[start_idx:]
            plot_x = list(xs)[start_idx:]
            plot_y = list(ys)[start_idx:]
            plot_z = list(zs)[start_idx:]
            
            if len(plot_t) > 0:
                if show_x:
                    self.line_x.set_data(plot_t, plot_x)
                if show_y:
                    self.line_y.set_data(plot_t, plot_y)
                if show_z:
                    self.line_z.set_data(plot_t, plot_z)
                    
                # Set time axis boundaries
                if len(plot_t) > 1:
                    self.axes.set_xlim(plot_t[0], plot_t[-1])
                else:
                    self.axes.set_xlim(plot_t[0] - 0.5, plot_t[0] + 0.5)
                
                # Set Y axis limits based on scaling options
                if autoscale:
                    all_vals = []
                    if show_x: all_vals.extend(plot_x)
                    if show_y: all_vals.extend(plot_y)
                    if show_z: all_vals.extend(plot_z)
                    if all_vals:
                        ymin, ymax = min(all_vals), max(all_vals)
                        margin = max(abs(ymax - ymin) * 0.1, 2.0)
                        self.axes.set_ylim(ymin - margin, ymax + margin)
                    else:
                        self.axes.set_ylim(-210, 210)
                else:
                    self.axes.set_ylim(-210, 210)
            else:
                self.line_x.set_data([], [])
                self.line_y.set_data([], [])
                self.line_z.set_data([], [])
                self.axes.set_xlim(max_t - window_seconds, max_t)
                self.axes.set_ylim(-210, 210)
        else:
            self.line_x.set_data([], [])
            self.line_y.set_data([], [])
            self.line_z.set_data([], [])
            self.axes.set_xlim(0, window_seconds)
            self.axes.set_ylim(-210, 210)
            
        self.draw()


class GuiWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Basic Window Config
        self.setWindowTitle("H3LIS200DL - Rejestrator Telemetrii")
        self.resize(1100, 700)
        self.setMinimumSize(950, 600)
        
        # Apply premium dark theme styling stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121214;
            }
            QWidget {
                color: #e2e2e8;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QGroupBox {
                background-color: #1e1e24;
                border: 1px solid #2f303a;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                font-weight: bold;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 15px;
                padding: 0 5px;
            }
            QLabel {
                background: transparent;
            }
            QLineEdit {
                background-color: #2a2b36;
                border: 1px solid #3c3d4c;
                border-radius: 4px;
                padding: 5px 8px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #0a84ff;
            }
            QPushButton {
                background-color: #2a2b36;
                border: 1px solid #3c3d4c;
                border-radius: 4px;
                padding: 6px 12px;
                color: #ffffff;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #353646;
                border: 1px solid #4e4f64;
            }
            QPushButton:pressed {
                background-color: #20212b;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #3c3d4c;
                border-radius: 4px;
                background-color: #2a2b36;
            }
            QCheckBox::indicator:hover {
                border-color: #4e4f64;
            }
            QCheckBox::indicator:checked {
                background-color: #0a84ff;
                border-color: #0a84ff;
            }
            QFrame#line_sep {
                background-color: #2f303a;
                max-height: 1px;
            }
        """)

        # Core Logics and Buffers
        self.window_seconds = 5.0
        self.max_points = 10000  # High limit to hold several seconds at high data rates (e.g. 600Hz)
        self.data_x = deque(maxlen=self.max_points)
        self.data_y = deque(maxlen=self.max_points)
        self.data_z = deque(maxlen=self.max_points)
        self.data_t = deque(maxlen=self.max_points)
        
        # Buffers for visually smoothed values
        self.smooth_x = deque(maxlen=self.max_points)
        self.smooth_y = deque(maxlen=self.max_points)
        self.smooth_z = deque(maxlen=self.max_points)
        self.smoothing_factor = 0.70  # Default to 70% smoothing (LPF)
        
        # Statistics variables
        self.reset_peaks()
        
        # Logger
        self.logger = DataLogger()
        self.log_directory = os.path.abspath(os.getcwd())
        
        # Thread handles
        self.receiver_thread = None
        self.packet_count = 0
        self.last_packet_time = 0.0
        
        # UI Setup
        self.init_ui()
        
        # Set up a 1-second timer to update packet rate and duration
        self.timer_1s = QTimer(self)
        self.timer_1s.timeout.connect(self.update_slow_stats)
        self.timer_1s.start(1000)
        
        # Plot refresh timer (refreshes graph 20 times a second to matches 50ms)
        self.plot_timer = QTimer(self)
        self.plot_timer.timeout.connect(self.refresh_plot)
        self.plot_timer.start(50)
        
    def reset_peaks(self):
        self.peak_x_max = -9999.0
        self.peak_x_min = 9999.0
        self.peak_y_max = -9999.0
        self.peak_y_min = 9999.0
        self.peak_z_max = -9999.0
        self.peak_z_min = 9999.0
        self.peak_res = 0.0
        
        # Live display updates if UI is built
        if hasattr(self, 'lbl_stat_x_min'):
            self.update_stats_ui(0, 0, 0, 0)
            
    def init_ui(self):
        # Main central widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # =====================================================================
        # LEFT PANEL: Controls, Logging & Statistics
        # =====================================================================
        left_panel = QWidget()
        left_panel.setFixedWidth(330)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Group 1: Connection Info
        grp_conn = QGroupBox("Połączenie UDP")
        grid_conn = QGridLayout(grp_conn)
        grid_conn.setSpacing(10)
        
        grid_conn.addWidget(QLabel("IP nasłuchu:"), 0, 0)
        self.input_ip = QLineEdit("0.0.0.0")
        grid_conn.addWidget(self.input_ip, 0, 1)
        
        grid_conn.addWidget(QLabel("Port UDP:"), 1, 0)
        self.input_port = QLineEdit("1234")
        grid_conn.addWidget(self.input_port, 1, 1)
        
        self.btn_listen = QPushButton("Uruchom nasłuch")
        self.btn_listen.setStyleSheet("""
            QPushButton {
                background-color: #30d158;
                border-color: #24b045;
                font-weight: bold;
                height: 32px;
            }
            QPushButton:hover {
                background-color: #2bc150;
            }
            QPushButton:pressed {
                background-color: #1f9e3d;
            }
        """)
        self.btn_listen.clicked.connect(self.toggle_connection)
        grid_conn.addWidget(self.btn_listen, 2, 0, 1, 2)
        
        left_layout.addWidget(grp_conn)
        
        # Group 2: Logging Session
        grp_log = QGroupBox("Zapis sesji (CSV)")
        grid_log = QGridLayout(grp_log)
        grid_log.setSpacing(10)
        
        grid_log.addWidget(QLabel("Prefiks nazwy:"), 0, 0)
        self.input_prefix = QLineEdit("sesja_testowa")
        grid_log.addWidget(self.input_prefix, 0, 1)
        
        grid_log.addWidget(QLabel("Status zapisu:"), 1, 0)
        self.lbl_log_status = QLabel("Nieaktywny")
        self.lbl_log_status.setStyleSheet("color: #ff453a; font-weight: bold;")
        grid_log.addWidget(self.lbl_log_status, 1, 1)
        
        grid_log.addWidget(QLabel("Plik:"), 2, 0)
        self.lbl_log_file = QLabel("Brak")
        self.lbl_log_file.setStyleSheet("color: #aeaeb2;")
        self.lbl_log_file.setWordWrap(True)
        grid_log.addWidget(self.lbl_log_file, 2, 1)
        
        self.btn_open_folder = QPushButton("Otwórz folder zapisu")
        self.btn_open_folder.clicked.connect(self.open_log_folder)
        grid_log.addWidget(self.btn_open_folder, 3, 0, 1, 2)
        
        left_layout.addWidget(grp_log)
        
        # Group 3: Live & Peak Statistics
        grp_stats = QGroupBox("Statystyki przeciążeń [g]")
        grid_stats = QGridLayout(grp_stats)
        grid_stats.setSpacing(8)
        
        # Headers
        grid_stats.addWidget(QLabel("Oś"), 0, 0, Qt.AlignCenter)
        grid_stats.addWidget(QLabel("Aktualne"), 0, 1, Qt.AlignCenter)
        grid_stats.addWidget(QLabel("Min (Peak)"), 0, 2, Qt.AlignCenter)
        grid_stats.addWidget(QLabel("Max (Peak)"), 0, 3, Qt.AlignCenter)
        
        # Row X
        lbl_x = QLabel("X")
        lbl_x.setStyleSheet("color: #ff4757; font-weight: bold;")
        grid_stats.addWidget(lbl_x, 1, 0, Qt.AlignCenter)
        self.lbl_stat_x_live = QLabel("0.0")
        self.lbl_stat_x_live.setStyleSheet("font-weight: bold;")
        self.lbl_stat_x_min = QLabel("0.0")
        self.lbl_stat_x_max = QLabel("0.0")
        grid_stats.addWidget(self.lbl_stat_x_live, 1, 1, Qt.AlignCenter)
        grid_stats.addWidget(self.lbl_stat_x_min, 1, 2, Qt.AlignCenter)
        grid_stats.addWidget(self.lbl_stat_x_max, 1, 3, Qt.AlignCenter)
        
        # Row Y
        lbl_y = QLabel("Y")
        lbl_y.setStyleSheet("color: #2ed573; font-weight: bold;")
        grid_stats.addWidget(lbl_y, 2, 0, Qt.AlignCenter)
        self.lbl_stat_y_live = QLabel("0.0")
        self.lbl_stat_y_live.setStyleSheet("font-weight: bold;")
        self.lbl_stat_y_min = QLabel("0.0")
        self.lbl_stat_y_max = QLabel("0.0")
        grid_stats.addWidget(self.lbl_stat_y_live, 2, 1, Qt.AlignCenter)
        grid_stats.addWidget(self.lbl_stat_y_min, 2, 2, Qt.AlignCenter)
        grid_stats.addWidget(self.lbl_stat_y_max, 2, 3, Qt.AlignCenter)
        
        # Row Z
        lbl_z = QLabel("Z")
        lbl_z.setStyleSheet("color: #1e90ff; font-weight: bold;")
        grid_stats.addWidget(lbl_z, 3, 0, Qt.AlignCenter)
        self.lbl_stat_z_live = QLabel("0.0")
        self.lbl_stat_z_live.setStyleSheet("font-weight: bold;")
        self.lbl_stat_z_min = QLabel("0.0")
        self.lbl_stat_z_max = QLabel("0.0")
        grid_stats.addWidget(self.lbl_stat_z_live, 3, 1, Qt.AlignCenter)
        grid_stats.addWidget(self.lbl_stat_z_min, 3, 2, Qt.AlignCenter)
        grid_stats.addWidget(self.lbl_stat_z_max, 3, 3, Qt.AlignCenter)
        
        # Separator line
        sep = QFrame()
        sep.setObjectName("line_sep")
        grid_stats.addWidget(sep, 4, 0, 1, 4)
        
        # Resultant G (total magnitude)
        lbl_res = QLabel("Wektor G")
        lbl_res.setStyleSheet("font-weight: bold; color: #ffffff;")
        grid_stats.addWidget(lbl_res, 5, 0, Qt.AlignCenter)
        self.lbl_stat_res_live = QLabel("0.0")
        self.lbl_stat_res_live.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffa502;")
        self.lbl_stat_res_peak = QLabel("0.0")
        self.lbl_stat_res_peak.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffa502;")
        grid_stats.addWidget(self.lbl_stat_res_live, 5, 1, Qt.AlignCenter)
        grid_stats.addWidget(QLabel("Peak total:"), 5, 2, Qt.AlignRight)
        grid_stats.addWidget(self.lbl_stat_res_peak, 5, 3, Qt.AlignCenter)
        
        self.btn_reset_stats = QPushButton("Resetuj Szczyty")
        self.btn_reset_stats.clicked.connect(self.reset_peaks)
        grid_stats.addWidget(self.btn_reset_stats, 6, 0, 1, 4)
        
        left_layout.addWidget(grp_stats)
        
        # Group 4: Plot options
        grp_plot_opts = QGroupBox("Opcje wykresu")
        grid_plot_opts = QGridLayout(grp_plot_opts)
        grid_plot_opts.setSpacing(10)
        
        grid_plot_opts.addWidget(QLabel("Szerokość okna (sekundy):"), 0, 0)
        self.input_window_sec = QLineEdit(str(self.window_seconds))
        self.input_window_sec.setFixedWidth(60)
        self.input_window_sec.textChanged.connect(self.update_window_seconds)
        grid_plot_opts.addWidget(self.input_window_sec, 0, 1)
        
        grid_plot_opts.addWidget(QLabel("Wygładzanie (LPF):"), 1, 0)
        self.slider_smoothing = QSlider(Qt.Horizontal)
        self.slider_smoothing.setRange(0, 95)
        self.slider_smoothing.setValue(70)
        self.slider_smoothing.valueChanged.connect(self.update_smoothing_factor)
        grid_plot_opts.addWidget(self.slider_smoothing, 1, 1)
        
        self.lbl_smoothing_val = QLabel("70%")
        self.lbl_smoothing_val.setFixedWidth(30)
        grid_plot_opts.addWidget(self.lbl_smoothing_val, 1, 2)
        
        self.chk_autoscale = QCheckBox("Automatyczna skala Y")
        self.chk_autoscale.setChecked(True)
        grid_plot_opts.addWidget(self.chk_autoscale, 2, 0, 1, 3)
        
        self.btn_clear_plot = QPushButton("Wyczyść wykres")
        self.btn_clear_plot.clicked.connect(self.clear_buffers)
        grid_plot_opts.addWidget(self.btn_clear_plot, 3, 0, 1, 3)
        
        left_layout.addWidget(grp_plot_opts)
        
        # Push all contents to the top
        left_layout.addStretch()
        
        # Add left panel to main layout
        main_layout.addWidget(left_panel)
        
        # =====================================================================
        # RIGHT PANEL: Visualizer and filters
        # =====================================================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        
        # Top Dashboard Info Header
        info_bar = QWidget()
        info_bar.setStyleSheet("""
            QWidget {
                background-color: #1e1e24;
                border: 1px solid #2f303a;
                border-radius: 8px;
            }
            QLabel {
                font-weight: 500;
            }
        """)
        info_bar_layout = QHBoxLayout(info_bar)
        info_bar_layout.setContentsMargins(15, 10, 15, 10)
        
        self.lbl_conn_status = QLabel("Stan odbiornika: ROZŁĄCZONY")
        self.lbl_conn_status.setStyleSheet("color: #ff453a; font-weight: bold;")
        info_bar_layout.addWidget(self.lbl_conn_status)
        
        info_bar_layout.addStretch()
        
        self.lbl_rate = QLabel("Prędkość: -- Hz")
        info_bar_layout.addWidget(self.lbl_rate)
        
        info_bar_layout.addSpacing(20)
        
        self.lbl_packet_counter = QLabel("Pakiety: 0")
        info_bar_layout.addWidget(self.lbl_packet_counter)
        
        right_layout.addWidget(info_bar)
        
        # Plot Traces Filter Layout
        filter_bar = QWidget()
        filter_bar.setStyleSheet("background: transparent;")
        filter_bar_layout = QHBoxLayout(filter_bar)
        filter_bar_layout.setContentsMargins(5, 0, 5, 0)
        filter_bar_layout.setSpacing(20)
        
        filter_bar_layout.addWidget(QLabel("Widoczne osie:"))
        
        self.chk_show_x = QCheckBox("Oś X")
        self.chk_show_x.setChecked(True)
        self.chk_show_x.setStyleSheet("QCheckBox { color: #ff4757; font-weight: bold; }")
        filter_bar_layout.addWidget(self.chk_show_x)
        
        self.chk_show_y = QCheckBox("Oś Y")
        self.chk_show_y.setChecked(True)
        self.chk_show_y.setStyleSheet("QCheckBox { color: #2ed573; font-weight: bold; }")
        filter_bar_layout.addWidget(self.chk_show_y)
        
        self.chk_show_z = QCheckBox("Oś Z")
        self.chk_show_z.setChecked(True)
        self.chk_show_z.setStyleSheet("QCheckBox { color: #1e90ff; font-weight: bold; }")
        filter_bar_layout.addWidget(self.chk_show_z)
        
        filter_bar_layout.addStretch()
        right_layout.addWidget(filter_bar)
        
        # Plot Canvas
        self.canvas = MplCanvas(self)
        right_layout.addWidget(self.canvas)
        
        # Add right panel to main layout
        main_layout.addWidget(right_panel, stretch=1)

    # =====================================================================
    # SLOTS & LOGIC ACTIONS
    # =====================================================================
    @Slot()
    def toggle_connection(self):
        if self.receiver_thread and self.receiver_thread.isRunning():
            # Stop receiver thread
            self.receiver_thread.stop()
            self.receiver_thread = None
            
            # Stop logger session
            self.logger.stop_session()
            self.lbl_log_status.setText("Nieaktywny")
            self.lbl_log_status.setStyleSheet("color: #ff453a; font-weight: bold;")
            self.lbl_log_file.setText("Brak")
            
            self.btn_listen.setText("Uruchom nasłuch")
            self.btn_listen.setStyleSheet("""
                QPushButton {
                    background-color: #30d158;
                    border-color: #24b045;
                    font-weight: bold;
                    height: 32px;
                }
                QPushButton:hover {
                    background-color: #2bc150;
                }
                QPushButton:pressed {
                    background-color: #1f9e3d;
                }
            """)
            self.lbl_conn_status.setText("Stan odbiornika: ROZŁĄCZONY")
            self.lbl_conn_status.setStyleSheet("color: #ff453a; font-weight: bold;")
            self.input_ip.setEnabled(True)
            self.input_port.setEnabled(True)
            self.input_prefix.setEnabled(True)
        else:
            # Parse parameters
            ip = self.input_ip.text().strip()
            port_str = self.input_port.text().strip()
            
            try:
                port = int(port_str)
                if not (0 <= port <= 65535):
                    raise ValueError("Port out of bounds")
            except ValueError:
                QMessageBox.warning(self, "Błąd parametrów", "Podaj prawidłowy numer portu (0 - 65535)")
                return
                
            # Start Logger session
            prefix = self.input_prefix.text().strip()
            filepath = self.logger.start_session(directory=self.log_directory, prefix=prefix)
            self.lbl_log_status.setText("Zapisywanie...")
            self.lbl_log_status.setStyleSheet("color: #30d158; font-weight: bold;")
            self.lbl_log_file.setText(os.path.basename(filepath))
            
            # Start receiver thread
            self.receiver_thread = UdpReceiver(ip=ip, port=port)
            self.receiver_thread.data_received.connect(self.handle_telemetry_point)
            self.receiver_thread.error_occurred.connect(self.handle_receiver_error)
            self.receiver_thread.status_changed.connect(self.handle_receiver_status_change)
            self.receiver_thread.start()
            
            self.btn_listen.setText("Zatrzymaj nasłuch")
            self.btn_listen.setStyleSheet("""
                QPushButton {
                    background-color: #ff453a;
                    border-color: #e03b30;
                    font-weight: bold;
                    height: 32px;
                }
                QPushButton:hover {
                    background-color: #ff5e54;
                }
                QPushButton:pressed {
                    background-color: #cf372d;
                }
            """)
            self.input_ip.setEnabled(False)
            self.input_port.setEnabled(False)
            self.input_prefix.setEnabled(False)
            
            self.reset_peaks()

    @Slot(float, float, float, float)
    def handle_telemetry_point(self, t, x, y, z):
        # Accumulate metrics
        self.packet_count += 1
        self.last_packet_time = time.time()
        
        # Log to file (MUST log raw unfiltered data to preserve crash details)
        self.logger.log_point(t, x, y, z)
        
        # Add raw values to raw buffers
        self.data_t.append(t)
        self.data_x.append(x)
        self.data_y.append(y)
        self.data_z.append(z)
        
        # Calculate visually smoothed values (Exponential Moving Average)
        if len(self.smooth_x) == 0:
            sm_x, sm_y, sm_z = x, y, z
        else:
            beta = self.smoothing_factor
            sm_x = (1.0 - beta) * x + beta * self.smooth_x[-1]
            sm_y = (1.0 - beta) * y + beta * self.smooth_y[-1]
            sm_z = (1.0 - beta) * z + beta * self.smooth_z[-1]
            
        self.smooth_x.append(sm_x)
        self.smooth_y.append(sm_y)
        self.smooth_z.append(sm_z)
        
        # Calculate Peak holds (calculated on RAW data to catch actual impact peaks)
        self.peak_x_max = max(self.peak_x_max, x)
        self.peak_x_min = min(self.peak_x_min, x)
        self.peak_y_max = max(self.peak_y_max, y)
        self.peak_y_min = min(self.peak_y_min, y)
        self.peak_z_max = max(self.peak_z_max, z)
        self.peak_z_min = min(self.peak_z_min, z)
        
        res = math.sqrt(x**2 + y**2 + z**2)
        self.peak_res = max(self.peak_res, res)
        
        # Update live values UI (showing smoothed live values for consistency with plot)
        sm_res = math.sqrt(sm_x**2 + sm_y**2 + sm_z**2)
        self.update_stats_ui(sm_x, sm_y, sm_z, sm_res)

    def update_stats_ui(self, x, y, z, res):
        # X Values
        self.lbl_stat_x_live.setText(f"{x:.1f}")
        self.lbl_stat_x_min.setText(f"{self.peak_x_min:.1f}" if self.peak_x_min != 9999.0 else "0.0")
        self.lbl_stat_x_max.setText(f"{self.peak_x_max:.1f}" if self.peak_x_max != -9999.0 else "0.0")
        
        # Y Values
        self.lbl_stat_y_live.setText(f"{y:.1f}")
        self.lbl_stat_y_min.setText(f"{self.peak_y_min:.1f}" if self.peak_y_min != 9999.0 else "0.0")
        self.lbl_stat_y_max.setText(f"{self.peak_y_max:.1f}" if self.peak_y_max != -9999.0 else "0.0")
        
        # Z Values
        self.lbl_stat_z_live.setText(f"{z:.1f}")
        self.lbl_stat_z_min.setText(f"{self.peak_z_min:.1f}" if self.peak_z_min != 9999.0 else "0.0")
        self.lbl_stat_z_max.setText(f"{self.peak_z_max:.1f}" if self.peak_z_max != -9999.0 else "0.0")
        
        # Vector Value
        self.lbl_stat_res_live.setText(f"{res:.1f}")
        self.lbl_stat_res_peak.setText(f"{self.peak_res:.1f}")

    @Slot(str)
    def handle_receiver_error(self, err_msg):
        # Add display or notification
        print(f"UDP Thread Error: {err_msg}")
        self.lbl_conn_status.setText(f"Odbiornik: BŁĄD ({err_msg})")
        self.lbl_conn_status.setStyleSheet("color: #ff453a; font-weight: bold;")

    @Slot(bool)
    def handle_receiver_status_change(self, is_listening):
        if is_listening:
            self.lbl_conn_status.setText("Stan odbiornika: SŁUCHAM")
            self.lbl_conn_status.setStyleSheet("color: #30d158; font-weight: bold;")
        else:
            self.lbl_conn_status.setText("Stan odbiornika: ROZŁĄCZONY")
            self.lbl_conn_status.setStyleSheet("color: #ff453a; font-weight: bold;")
            self.lbl_rate.setText("Prędkość: -- Hz")

    @Slot()
    def update_slow_stats(self):
        """Timer ticking every second to update indicators."""
        if self.receiver_thread and self.receiver_thread.isRunning():
            rate = self.packet_count
            self.packet_count = 0
            self.lbl_rate.setText(f"Prędkość: {rate} Hz")
            
            # Update packets count label (accumulative readout from queues)
            self.lbl_packet_counter.setText(f"Pakiety: {len(self.data_t)}")
            
            # Simple connection heartbeat check (if no packet in 3 seconds, indicate warning)
            if time.time() - self.last_packet_time > 3.0:
                self.lbl_conn_status.setText("Stan odbiornika: BRAK DANYCH (Czekam...)")
                self.lbl_conn_status.setStyleSheet("color: #ff9f0a; font-weight: bold;") # amber warning

    @Slot()
    def refresh_plot(self):
        """Timer ticking every 50ms to refresh lines on plot."""
        show_x = self.chk_show_x.isChecked()
        show_y = self.chk_show_y.isChecked()
        show_z = self.chk_show_z.isChecked()
        autoscale = self.chk_autoscale.isChecked()
        
        self.canvas.update_data(
            self.data_t, self.smooth_x, self.smooth_y, self.smooth_z,
            window_seconds=self.window_seconds,
            show_x=show_x, show_y=show_y, show_z=show_z,
            autoscale=autoscale
        )

    @Slot()
    def open_log_folder(self):
        if os.path.exists(self.log_directory):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.log_directory))

    @Slot()
    def update_window_seconds(self):
        val = self.input_window_sec.text().strip()
        try:
            sec = float(val)
            if sec > 0.1:
                self.window_seconds = sec
        except ValueError:
            pass

    @Slot(int)
    def update_smoothing_factor(self, value):
        self.smoothing_factor = value / 100.0
        self.lbl_smoothing_val.setText(f"{value}%")

    @Slot()
    def clear_buffers(self):
        self.data_t.clear()
        self.data_x.clear()
        self.data_y.clear()
        self.data_z.clear()
        self.smooth_x.clear()
        self.smooth_y.clear()
        self.smooth_z.clear()
        self.lbl_packet_counter.setText("Pakiety: 0")

    def closeEvent(self, event):
        # Graceful cleanup on window close
        self.timer_1s.stop()
        self.plot_timer.stop()
        
        if self.receiver_thread and self.receiver_thread.isRunning():
            self.receiver_thread.stop()
            
        self.logger.stop_session()
        event.accept()
