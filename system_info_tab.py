# system_info_tab.py
import psutil
import platform
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer, QDateTime

MEMORY_ALERT_THRESHOLD = 80  # percent
USAGE_WARNING_THRESHOLD = 50  # percent for coloring

class SystemInfoTab(QWidget):
    def __init__(self):
        super().__init__()
        self.alerted_memory = False
        self._setup_ui()
        self._start_updater()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("<h2><center>System Information</center></h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # CPU Info
        self.cpu_label = QLabel()
        layout.addWidget(QLabel("<b>CPU Information</b>"))
        layout.addWidget(self.cpu_label)

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setFormat("CPU Usage: %p%")
        self.cpu_bar.setTextVisible(True)
        layout.addWidget(self.cpu_bar)

        # Memory Info
        self.mem_label = QLabel()
        layout.addWidget(QLabel("<b>Memory Usage</b>"))
        layout.addWidget(self.mem_label)

        self.mem_bar = QProgressBar()
        self.mem_bar.setRange(0, 100)
        self.mem_bar.setFormat("Memory Usage: %p%")
        self.mem_bar.setTextVisible(True)
        layout.addWidget(self.mem_bar)

        # Disk Info
        self.disk_table = QTableWidget()
        self.disk_table.setColumnCount(5)
        self.disk_table.setHorizontalHeaderLabels(['Mount', 'Total', 'Used', 'Free', 'Usage %'])
        self.disk_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("<b>Disk Usage</b>"))
        layout.addWidget(self.disk_table)

        # OS Info
        self.os_label = QLabel()
        layout.addWidget(QLabel("<b>Operating System</b>"))
        layout.addWidget(self.os_label)

        # Network Info
        self.net_table = QTableWidget()
        self.net_table.setColumnCount(3)
        self.net_table.setHorizontalHeaderLabels(['Interface', 'IP Address', 'Status'])
        self.net_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("<b>Network Interfaces</b>"))
        layout.addWidget(self.net_table)

        # Alerts terminal
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setStyleSheet("background-color: black; color: red; font-family: monospace;")
        layout.addWidget(QLabel("<b>Alerts</b>"))
        layout.addWidget(self.terminal)

        self.setLayout(layout)

    def _start_updater(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_info)
        self.timer.start(2000)

    def update_info(self):
        now = QDateTime.currentDateTime().toString("hh:mm:ss")

        # === CPU Info ===
        cpu_percent = psutil.cpu_percent(interval=0.5)
        cores = psutil.cpu_count(logical=False)
        threads = psutil.cpu_count(logical=True)
        self.cpu_label.setText(f"Cores: {cores}, Threads: {threads}, Usage: {cpu_percent:.1f}%")
        self.cpu_bar.setValue(int(cpu_percent))
        self._update_bar_color(self.cpu_bar, cpu_percent)

        # === Memory Info ===
        mem = psutil.virtual_memory()
        mem_text = f"Total: {self._format_bytes(mem.total)}, Used: {self._format_bytes(mem.used)}, Free: {self._format_bytes(mem.available)}, Usage: {mem.percent:.1f}%"
        self.mem_label.setText(mem_text)
        self.mem_bar.setValue(int(mem.percent))
        self._update_bar_color(self.mem_bar, mem.percent)

        if mem.percent > MEMORY_ALERT_THRESHOLD and not self.alerted_memory:
            alert = f"[{now}] Memory usage high: {mem.percent:.1f}%"
            self.terminal.append(alert)
            self.alerted_memory = True
        elif mem.percent <= MEMORY_ALERT_THRESHOLD:
            self.alerted_memory = False

        # === Disk Info ===
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

        # === OS Info ===
        sys_info = platform.uname()
        os_text = f"System: {sys_info.system}, Release: {sys_info.release}, Version: {sys_info.version}, Architecture: {sys_info.machine}"
        self.os_label.setText(os_text)

        # === Network Info ===
        self.net_table.setRowCount(0)
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        for iface, iface_addrs in addrs.items():
            ip_list = [a.address for a in iface_addrs if a.family.name == 'AF_INET']
            ip_str = ', '.join(ip_list) if ip_list else 'N/A'
            status = 'Up' if stats.get(iface) and stats[iface].isup else 'Down'
            row = self.net_table.rowCount()
            self.net_table.insertRow(row)
            for col, val in enumerate([iface, ip_str, status]):
                self.net_table.setItem(row, col, QTableWidgetItem(str(val)))

    def _update_bar_color(self, bar, percent):
        """Set progress bar color dynamically based on usage"""
        if percent > USAGE_WARNING_THRESHOLD:
            bar.setStyleSheet("QProgressBar::chunk { background-color: red; }")
        else:
            bar.setStyleSheet("QProgressBar::chunk { background-color: green; }")

    def _format_bytes(self, bytes_num):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_num < 1024.0:
                return f"{bytes_num:.2f} {unit}"
            bytes_num /= 1024.0
        return f"{bytes_num:.2f} TB"

def create_system_info_tab():
    return SystemInfoTab()
