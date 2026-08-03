# processes_tab.py
import psutil
from collections import deque
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QHeaderView, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer, QDateTime
import os

CPU_ALERT_THRESHOLD = 50.0  # percent

class ProcessesTab(QWidget):
    def __init__(self):
        super().__init__()
        self.alerted_processes = set()
        self._setup_ui()
        self._start_updater()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("<h2><center>Process Monitor</center></h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # System Processes Table
        self.proc_table = QTableWidget()
        self.proc_table.setColumnCount(5)
        self.proc_table.setHorizontalHeaderLabels(['PID', 'Name', 'User', 'CPU %', 'Memory %'])
        self.proc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("<b>All System Processes</b>"))
        layout.addWidget(self.proc_table)

        # Foreign Processes Table
        self.foreign_table = QTableWidget()
        self.foreign_table.setColumnCount(5)
        self.foreign_table.setHorizontalHeaderLabels(['PID', 'Name', 'User', 'CPU %', 'Memory %'])
        self.foreign_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("<b>Foreign Processes</b>"))
        layout.addWidget(self.foreign_table)

        # Network Processes Table
        self.net_table = QTableWidget()
        self.net_table.setColumnCount(5)
        self.net_table.setHorizontalHeaderLabels(['PID', 'Name', 'Local Address', 'Remote Address', 'Status'])
        self.net_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("<b>Network Processes</b>"))
        layout.addWidget(self.net_table)

        # Remote Processes Table
        self.remote_table = QTableWidget()
        self.remote_table.setColumnCount(5)
        self.remote_table.setHorizontalHeaderLabels(['PID', 'Name', 'Local Address', 'Remote Address', 'Status'])
        self.remote_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("<b>Remote Processes</b>"))
        layout.addWidget(self.remote_table)

        # Alert terminal
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setStyleSheet("background-color: black; color: red; font-family: monospace;")
        layout.addWidget(QLabel("<b>High CPU Alerts</b>"))
        layout.addWidget(self.terminal)

    def _start_updater(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_all)
        self.timer.start(2000)  # update every 2 seconds

    def update_all(self):
        now = QDateTime.currentDateTime().toString("hh:mm:ss")
        current_user = os.getlogin()

        # === All processes ===
        all_procs = []
        foreign_procs = []
        for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
            try:
                all_procs.append(p.info)
                if p.info['username'] != current_user:
                    foreign_procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Update system processes table
        self.proc_table.setRowCount(0)
        for proc in all_procs:
            row = self.proc_table.rowCount()
            self.proc_table.insertRow(row)
            for col, val in enumerate([proc['pid'], proc['name'], proc['username'], f"{proc['cpu_percent']:.1f}", f"{proc['memory_percent']:.1f}"]):
                self.proc_table.setItem(row, col, QTableWidgetItem(str(val)))

        # Update foreign processes table
        self.foreign_table.setRowCount(0)
        for proc in foreign_procs:
            row = self.foreign_table.rowCount()
            self.foreign_table.insertRow(row)
            for col, val in enumerate([proc['pid'], proc['name'], proc['username'], f"{proc['cpu_percent']:.1f}", f"{proc['memory_percent']:.1f}"]):
                self.foreign_table.setItem(row, col, QTableWidgetItem(str(val)))

        # === Network and Remote processes ===
        net_procs = {}
        remote_procs = {}
        try:
            for conn in psutil.net_connections(kind='inet'):
                pid = conn.pid
                if pid is None:
                    continue
                net_procs[pid] = net_procs.get(pid, []) + [conn]
                if conn.raddr:
                    remote_procs[pid] = remote_procs.get(pid, []) + [conn]
        except Exception:
            pass

        # Network table
        self.net_table.setRowCount(0)
        for pid, conns in net_procs.items():
            try:
                pname = psutil.Process(pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pname = "N/A"
            for conn in conns:
                row = self.net_table.rowCount()
                self.net_table.insertRow(row)
                laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
                raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
                status = conn.status
                for col, val in enumerate([pid, pname, laddr, raddr, status]):
                    self.net_table.setItem(row, col, QTableWidgetItem(str(val)))

        # Remote table
        self.remote_table.setRowCount(0)
        for pid, conns in remote_procs.items():
            try:
                pname = psutil.Process(pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pname = "N/A"
            for conn in conns:
                row = self.remote_table.rowCount()
                self.remote_table.insertRow(row)
                laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
                raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
                status = conn.status
                for col, val in enumerate([pid, pname, laddr, raddr, status]):
                    self.remote_table.setItem(row, col, QTableWidgetItem(str(val)))

        # === High CPU alerts ===
        for proc in all_procs:
            if proc['cpu_percent'] > CPU_ALERT_THRESHOLD:
                record = proc['pid']
                if record not in self.alerted_processes:
                    alert = f"[{now}] High CPU usage: PID {proc['pid']} ({proc['name']}) {proc['cpu_percent']:.1f}%"
                    self.alerted_processes.add(record)
                    self.terminal.append(alert + "\n")

def create_processes_tab():
    return ProcessesTab()
