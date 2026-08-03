import psutil
from collections import deque
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QHeaderView, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer, QDateTime
import pyqtgraph as pg

# Import your database handler here
from database.db_handler import DatabaseHandler

def format_bytes(bytes_num: float) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.2f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.2f} TB"

def format_rate(bps: float) -> str:
    return f"{format_bytes(bps)}/s"

class NetworkTab(QWidget):
    def __init__(self):
        super().__init__()
        self.db = DatabaseHandler()  # Initialize DB handler here

        self.prev_counters = psutil.net_io_counters()
        self.prev_pernic = {name: (io.bytes_sent, io.bytes_recv) for name, io in psutil.net_io_counters(pernic=True).items()}
        self.in_history = deque(maxlen=60)  # last 60 seconds
        self.out_history = deque(maxlen=60)
        self.rce_records = set()
        self._setup_ui()
        self._start_updater()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("<h2><center>Network Monitor</center></h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Connections Table
        self.conn_table = QTableWidget()
        self.conn_table.setColumnCount(7)
        self.conn_table.setHorizontalHeaderLabels(['Time', 'PID', 'Process', 'Port', 'Local Address', 'Remote Address', 'Status'])
        self.conn_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.conn_table)

        # Interface Table
        self.iface_table = QTableWidget()
        self.iface_table.setColumnCount(4)
        self.iface_table.setHorizontalHeaderLabels(['Interface', 'Usage %', 'Sent/s', 'Recv/s'])
        self.iface_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(QLabel("<b>Interface Usage</b>"))
        layout.addWidget(self.iface_table)

        # Bottom layout: Connection Alerts + Terminal
        bottom = QHBoxLayout()

        # Alerts Table
        rce_layout = QVBoxLayout()
        rce_label = QLabel("<b>Connection Alerts</b>")
        rce_label.setAlignment(Qt.AlignCenter)
        rce_layout.addWidget(rce_label)
        self.rce_table = QTableWidget()
        self.rce_table.setColumnCount(3)
        self.rce_table.setHorizontalHeaderLabels(['Time', 'PID', 'Alert'])
        self.rce_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rce_table.setStyleSheet(
            "QTableWidget { background-color: black; color: red; } "
            "QHeaderView::section { background-color: #330000; color: red; }"
        )
        rce_layout.addWidget(self.rce_table)
        bottom.addLayout(rce_layout, 1)

        # Terminal
        term_layout = QVBoxLayout()
        term_label = QLabel("<b>Connection Terminal</b>")
        term_label.setAlignment(Qt.AlignCenter)
        term_layout.addWidget(term_label)
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setStyleSheet("background-color: black; color: red; font-family: monospace;")
        term_layout.addWidget(self.terminal)
        bottom.addLayout(term_layout, 1)

        layout.addLayout(bottom)

        # Traffic Graphs (smaller)
        graph_layout = QVBoxLayout()
        self.incoming_label = QLabel("Incoming: 0 B")
        self.outgoing_label = QLabel("Outgoing: 0 B")
        graph_layout.addWidget(self.incoming_label)
        graph_layout.addWidget(self.outgoing_label)

        self.graph_widget = pg.PlotWidget(title="Network Traffic (MB/s)")
        self.graph_widget.setFixedHeight(150)  # smaller graph
        self.graph_widget.setBackground("k")
        self.graph_widget.addLegend()
        self.graph_widget.showGrid(x=True, y=True, alpha=0.3)
        self.in_curve = self.graph_widget.plot(pen=pg.mkPen('r', width=2), name='Incoming')
        self.out_curve = self.graph_widget.plot(pen=pg.mkPen('g', width=2), name='Outgoing')
        graph_layout.addWidget(self.graph_widget)
        layout.addLayout(graph_layout)

    def _start_updater(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_all)
        self.timer.start(1000)

    def update_all(self):
        now = QDateTime.currentDateTime().toString("hh:mm:ss")
        try:
            conns = psutil.net_connections(kind='inet')
        except Exception:
            conns = []

        # Update connections table and alerts
        self.conn_table.setRowCount(0)
        for c in conns:
            if c.status in ('ESTABLISHED', 'LISTEN'):
                row = self.conn_table.rowCount()
                self.conn_table.insertRow(row)
                pid = c.pid or 0
                try:
                    name = psutil.Process(c.pid).name() if c.pid else "N/A"
                except Exception:
                    name = "N/A"
                port = c.laddr.port if c.laddr else None
                laddr = c.laddr.ip if c.laddr else ""
                raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else ""
                status = c.status
                for col, val in enumerate([now, str(pid), name, str(port), laddr, raddr, status]):
                    self.conn_table.setItem(row, col, QTableWidgetItem(val))

                # Alert for all new connections
                if port is not None:
                    record = (pid, port, laddr, raddr)
                    if record not in self.rce_records:
                        alert = f"Port {port} active on PID {pid}"
                        if port < 1024 or port > 49151:
                            alert += " ⚠️"
                        self.rce_records.add(record)
                        self._add_rce_alert(now, pid, alert)
                        # Save alert to database
                        self.db.insert_alert(now, pid, alert)

        # Interface usage
        io_now = psutil.net_io_counters(pernic=True)
        stats = psutil.net_if_stats()
        self.iface_table.setRowCount(0)
        for iface, io in io_now.items():
            prev = self.prev_pernic.get(iface, (io.bytes_sent, io.bytes_recv))
            dsent = max(0, io.bytes_sent - prev[0])
            drecv = max(0, io.bytes_recv - prev[1])
            speed = 0.0
            try:
                s = stats.get(iface)
                if s and s.isup and s.speed > 0:
                    speed = float(s.speed) * 1_000_000 / 8.0
            except Exception:
                pass
            usage_pct = 0.0
            if speed > 0:
                usage_pct = min(100.0, ((dsent + drecv) / speed) * 100.0)
            row = self.iface_table.rowCount()
            self.iface_table.insertRow(row)
            self.iface_table.setItem(row, 0, QTableWidgetItem(iface))
            self.iface_table.setItem(row, 1, QTableWidgetItem(f"{usage_pct:.1f}%" if speed > 0 else "N/A"))
            self.iface_table.setItem(row, 2, QTableWidgetItem(format_rate(dsent)))
            self.iface_table.setItem(row, 3, QTableWidgetItem(format_rate(drecv)))
            self.prev_pernic[iface] = (io.bytes_sent, io.bytes_recv)

        # Traffic history
        b = psutil.net_io_counters()
        in_rate = max(0, b.bytes_recv - self.prev_counters.bytes_recv)
        out_rate = max(0, b.bytes_sent - self.prev_counters.bytes_sent)
        self.in_history.append(in_rate)
        self.out_history.append(out_rate)
        self.prev_counters = b

        # Labels
        self.incoming_label.setText(f"Incoming: {format_bytes(b.bytes_recv)} (+{format_rate(in_rate)})")
        self.outgoing_label.setText(f"Outgoing: {format_bytes(b.bytes_sent)} (+{format_rate(out_rate)})")

        # Update graph
        x = list(range(-len(self.in_history)+1, 1))
        self.in_curve.setData(x, [v/(1024*1024) for v in self.in_history])
        self.out_curve.setData(x, [v/(1024*1024) for v in self.out_history])

    def _add_rce_alert(self, time_str, pid, alert):
        row = self.rce_table.rowCount()
        self.rce_table.insertRow(row)
        self.rce_table.setItem(row, 0, QTableWidgetItem(time_str))
        self.rce_table.setItem(row, 1, QTableWidgetItem(str(pid)))
        self.rce_table.setItem(row, 2, QTableWidgetItem(alert))
        self.terminal.append(f"[ALERT] [{time_str}] {alert}\n")

def create_network_tab():
    return NetworkTab()
