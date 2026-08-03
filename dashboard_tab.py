# dashboard_tab.py
import socket
import psutil
import platform
import time
import random
import subprocess
from collections import deque
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QPushButton, QLineEdit, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QDateTime
from PyQt5.QtGui import QColor

# Thresholds
CPU_WARNING = 50
CPU_ALERT = 80
MEM_WARNING = 50
MEM_ALERT = 70

SYSTEM_MOODS = [
    "All systems nominal 😊",
    "Running smoothly 👍",
    "High CPU detected ⚡",
    "Memory usage rising 🔥",
    "Disk space sufficient 💾",
    "Network stable 🌐",
]

class DashboardTab(QWidget):
    def __init__(self):
        super().__init__()
        self.hostname = socket.gethostname()
        self.prev_net = psutil.net_io_counters(pernic=True)
        self._setup_ui()
        self._start_updater()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Banner
        self.banner_label = QLabel()
        self.banner_label.setAlignment(Qt.AlignCenter)
        self.banner_label.setStyleSheet("font-family: monospace; color: cyan; font-size: 16px;")
        layout.addWidget(self.banner_label)

        # CPU & Memory
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setFormat("CPU Usage: %p%")
        layout.addWidget(self.cpu_bar)

        self.mem_bar = QProgressBar()
        self.mem_bar.setRange(0, 100)
        self.mem_bar.setFormat("Memory Usage: %p%")
        layout.addWidget(self.mem_bar)

        # Disk
        self.disk_table = QTableWidget()
        self.disk_table.setColumnCount(5)
        self.disk_table.setHorizontalHeaderLabels(['Mount', 'Total', 'Used', 'Free', 'Usage %'])
        self.disk_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("<b>Disk Usage</b>"))
        layout.addWidget(self.disk_table)

        # Network
        self.net_table = QTableWidget()
        self.net_table.setColumnCount(4)
        self.net_table.setHorizontalHeaderLabels(['Interface', 'IP', 'Upload/s', 'Download/s'])
        self.net_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("<b>Network Interfaces</b>"))
        layout.addWidget(self.net_table)

        # Uptime
        self.uptime_label = QLabel()
        self.uptime_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(QLabel("<b>System Uptime</b>"))
        layout.addWidget(self.uptime_label)

        # Bottom terminal & buttons
        bottom_layout = QHBoxLayout()

        # Terminal
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setStyleSheet("background-color: black; color: red; font-family: monospace;")
        bottom_layout.addWidget(self.terminal, 3)

        # Buttons and input
        button_layout = QVBoxLayout()
        self.update_btn = QPushButton("Update & Upgrade")
        self.autoremove_btn = QPushButton("Autoremove")
        self.install_input = QLineEdit()
        self.install_input.setPlaceholderText("Package name")
        self.install_btn = QPushButton("Install Package")

        for w in [self.update_btn, self.autoremove_btn, self.install_input, self.install_btn]:
            w.setFixedHeight(36)
            button_layout.addWidget(w)

        button_layout.addStretch()
        bottom_layout.addLayout(button_layout, 1)
        layout.addLayout(bottom_layout)

        # System mood
        self.mood_label = QLabel()
        self.mood_label.setAlignment(Qt.AlignCenter)
        self.mood_label.setStyleSheet("font-size: 14px; color: orange;")
        layout.addWidget(self.mood_label)

        # Connect buttons
        self.update_btn.clicked.connect(lambda: self.run_command(""))
        self.autoremove_btn.clicked.connect(lambda: self.run_command("sudo apt autoremove -y"))
        self.install_btn.clicked.connect(self.install_package)

        self.setLayout(layout)

    def _start_updater(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(2000)

        self.mood_timer = QTimer(self)
        self.mood_timer.timeout.connect(self.update_mood)
        self.mood_timer.start(30000)

    def update_dashboard(self):
        now = QDateTime.currentDateTime().toString("hh:mm:ss")

        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.5)
        self.cpu_bar.setValue(int(cpu_percent))
        self._update_bar_color(self.cpu_bar, cpu_percent, CPU_WARNING, CPU_ALERT)
        if cpu_percent > CPU_ALERT:
            self._log_alert(f"[{now}] CPU critical: {cpu_percent:.1f}%")

        # Memory
        mem = psutil.virtual_memory()
        self.mem_bar.setValue(int(mem.percent))
        self._update_bar_color(self.mem_bar, mem.percent, MEM_WARNING, MEM_ALERT)
        if mem.percent > MEM_ALERT:
            self._log_alert(f"[{now}] Memory critical: {mem.percent:.1f}%")

        # Disk
        self.disk_table.setRowCount(0)
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except PermissionError:
                continue
            row = self.disk_table.rowCount()
            self.disk_table.insertRow(row)
            for col, val in enumerate([
                part.mountpoint,
                self._format_bytes(usage.total),
                self._format_bytes(usage.used),
                self._format_bytes(usage.free),
                f"{usage.percent:.1f}%"
            ]):
                self.disk_table.setItem(row, col, QTableWidgetItem(str(val)))

        # Network
        self.net_table.setRowCount(0)
        addrs = psutil.net_if_addrs()
        io_counters = psutil.net_io_counters(pernic=True)
        for iface, addr_list in addrs.items():
            ip_list = [a.address for a in addr_list if a.family.name == 'AF_INET']
            ip_str = ', '.join(ip_list) if ip_list else 'N/A'
            prev = self.prev_net.get(iface)
            io = io_counters.get(iface)
            upload = download = 0
            if prev and io:
                upload = io.bytes_sent - prev.bytes_sent
                download = io.bytes_recv - prev.bytes_recv
            row = self.net_table.rowCount()
            self.net_table.insertRow(row)
            for col, val in enumerate([iface, ip_str, self._format_bytes(upload) + "/s", self._format_bytes(download) + "/s"]):
                self.net_table.setItem(row, col, QTableWidgetItem(str(val)))

        self.prev_net = io_counters

        # Uptime
        uptime_sec = time.time() - psutil.boot_time()
        self.uptime_label.setText(self._format_time(uptime_sec))

        # Banner ASCII
        self.banner_label.setText(f"""
Hi!: {self.hostname} Welcome!
        """)

    def _update_bar_color(self, bar, percent, warning, alert):
        if percent >= alert:
            bar.setStyleSheet("QProgressBar::chunk { background-color: red; }")
        elif percent >= warning:
            bar.setStyleSheet("QProgressBar::chunk { background-color: yellow; }")
        else:
            bar.setStyleSheet("QProgressBar::chunk { background-color: green; }")

    def _log_alert(self, msg):
        self.terminal.append(msg)

    def _format_bytes(self, num):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if num < 1024.0:
                return f"{num:.2f} {unit}"
            num /= 1024.0
        return f"{num:.2f} TB"

    def _format_time(self, seconds):
        mins, sec = divmod(int(seconds), 60)
        hrs, mins = divmod(mins, 60)
        days, hrs = divmod(hrs, 24)
        return f"{days}d {hrs}h {mins}m {sec}s"

    def update_mood(self):
        mood = random.choice(SYSTEM_MOODS)
        self.mood_label.setText(f"💬 System Mood: {mood}")

    def run_command(self, command):
        self.terminal.append(f"$ {command}")
        try:
            proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                self.terminal.append(line.strip())
        except Exception as e:
            self.terminal.append(f"Error: {str(e)}")

    def install_package(self):
        pkg = self.install_input.text().strip()
        if pkg:
            self.run_command(f"sudo apt install {pkg} -y")
            self.install_input.clear()

def create_dashboard_tab():
    return DashboardTab()
