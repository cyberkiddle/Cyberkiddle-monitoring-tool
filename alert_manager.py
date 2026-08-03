import subprocess
import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QPushButton, QFileDialog, QHBoxLayout
)
from PyQt5.QtCore import QTimer
from database.db_handler import DatabaseHandler
import csv
import json
import os

def create_alerts_tab():
    widget = QWidget()
    main_layout = QVBoxLayout(widget)

    # Table widget
    table = QTableWidget()
    table.setColumnCount(3)
    table.setHorizontalHeaderLabels(["Timestamp", "PID", "Alert"])
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.setEditTriggers(QTableWidget.NoEditTriggers)  # Read-only

    # Buttons layout (Export buttons + toggle + remote monitor)
    btn_layout = QHBoxLayout()

    btn_export_csv = QPushButton("Export CSV")
    btn_export_json = QPushButton("Export JSON")

    # Toggle button for alerts popup on/off
    btn_toggle_alerts = QPushButton("Enable Alert Popups")
    btn_toggle_alerts.setCheckable(True)
    btn_toggle_alerts.setChecked(False)  # 🚨 Start DISABLED by default

    # New toggle button for remote monitor
    btn_toggle_remote = QPushButton("Enable Remote Monitoring")
    btn_toggle_remote.setCheckable(True)
    btn_toggle_remote.setChecked(False)  # Start disabled

    btn_layout.addWidget(btn_export_csv)
    btn_layout.addWidget(btn_export_json)
    btn_layout.addWidget(btn_toggle_alerts)
    btn_layout.addWidget(btn_toggle_remote)
    btn_layout.addStretch()  # Push buttons to the left

    main_layout.addLayout(btn_layout)
    main_layout.addWidget(table)

    # --- Existing functions ---
    def refresh_table():
        db = DatabaseHandler()
        alerts = db.get_alerts()
        db.close()

        table.setRowCount(len(alerts))

        for row_idx, alert in enumerate(alerts):
            time_str, pid, alert_text = alert
            table.setItem(row_idx, 0, QTableWidgetItem(time_str))
            table.setItem(row_idx, 1, QTableWidgetItem(str(pid)))
            table.setItem(row_idx, 2, QTableWidgetItem(alert_text))

    def export_csv():
        path, _ = QFileDialog.getSaveFileName(widget, "Save CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Timestamp", "PID", "Alert"])
                for row in range(table.rowCount()):
                    rowdata = [
                        table.item(row, col).text() if table.item(row, col) else ""
                        for col in range(table.columnCount())
                    ]
                    writer.writerow(rowdata)
            QMessageBox.information(widget, "Export Successful", f"Alerts exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(widget, "Export Failed", f"Error exporting CSV:\n{str(e)}")

    def export_json():
        path, _ = QFileDialog.getSaveFileName(widget, "Save JSON", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            data = []
            for row in range(table.rowCount()):
                data.append({
                    "Timestamp": table.item(row, 0).text() if table.item(row, 0) else "",
                    "PID": table.item(row, 1).text() if table.item(row, 1) else "",
                    "Alert": table.item(row, 2).text() if table.item(row, 2) else ""
                })
            with open(path, 'w', encoding='utf-8') as jsonfile:
                json.dump(data, jsonfile, indent=4)
            QMessageBox.information(widget, "Export Successful", f"Alerts exported to:\n{path}")
        except Exception as e:
            QMessageBox.critical(widget, "Export Failed", f"Error exporting JSON:\n{str(e)}")

    btn_export_csv.clicked.connect(export_csv)
    btn_export_json.clicked.connect(export_json)

    last_alert_count = 0

    def check_new_alerts():
        nonlocal last_alert_count
        db = DatabaseHandler()
        alerts = db.get_alerts()
        db.close()

        current_count = len(alerts)

        if current_count > last_alert_count:
            new_alerts = alerts[:current_count - last_alert_count]
            if btn_toggle_alerts.isChecked():
                for alert in reversed(new_alerts):
                    time_str, pid, alert_text = alert
                    msg = QMessageBox(widget)
                    if "high" in alert_text.lower() or "*" in alert_text:
                        msg.setIcon(QMessageBox.Critical)
                    else:
                        msg.setIcon(QMessageBox.Warning)
                    msg.setWindowTitle(f"New Alert - PID {pid}")
                    msg.setText(f"{alert_text}\n\nPID: {pid}\nTime: {time_str}")
                    msg.setStandardButtons(QMessageBox.Ok)
                    msg.exec_()

            refresh_table()
            last_alert_count = current_count

    refresh_table()
    last_alert_count = len(DatabaseHandler().get_alerts())

    timer = QTimer(widget)
    timer.timeout.connect(check_new_alerts)
    timer.start(100)

    def toggle_alerts():
        if btn_toggle_alerts.isChecked():
            btn_toggle_alerts.setText("Disable Alert Popups")
        else:
            btn_toggle_alerts.setText("Enable Alert Popups")

    btn_toggle_alerts.toggled.connect(toggle_alerts)

    # --- Remote monitor subprocess management ---
    remote_process = {"proc": None}  # Use dict to keep reference inside nested function

    def toggle_remote_monitoring():
        if btn_toggle_remote.isChecked():
            btn_toggle_remote.setText("Disable Remote Monitoring")
            remote_script_path = os.path.join("remote", "remote_monitor.py")

            if not os.path.exists(remote_script_path):
                QMessageBox.critical(widget, "Error", f"Remote monitor script not found:\n{remote_script_path}")
                btn_toggle_remote.setChecked(False)
                return

            remote_process["proc"] = subprocess.Popen([sys.executable, remote_script_path])
        else:
            btn_toggle_remote.setText("Enable Remote Monitoring")
            if remote_process["proc"]:
                remote_process["proc"].terminate()
                remote_process["proc"].wait()
                remote_process["proc"] = None

    btn_toggle_remote.toggled.connect(toggle_remote_monitoring)

    widget.refresh_table = refresh_table

    return widget
