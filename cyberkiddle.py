import sys
import os
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QListWidget, QStackedWidget,
    QHBoxLayout, QVBoxLayout, QPushButton, QSizePolicy, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QPropertyAnimation, pyqtProperty, QEasingCurve
from PyQt5.QtGui import QPainter, QColor, QPen, QIcon, QPixmap

# Import your tab creators
from dashboard_tab import create_dashboard_tab
from system_info_tab import create_system_info_tab
from network_tab import create_network_tab
from processes_tab import create_processes_tab
from about_tab import create_about_tab
from live_scan_tab import create_live_scan_tab
from alert_manager import create_alerts_tab

# Import your database handler
from database.db_handler import DatabaseHandler

# ---------------- Animated Underline List ----------------
class AnimatedUnderlineListWidget(QListWidget):
    def __init__(self):
        super().__init__()
        self._underline_width = 0
        self._underline_target_width = 0
        self.animation = QPropertyAnimation(self, b"underline_width", self)
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.currentRowChanged.connect(self.start_animation)
        self.setMouseTracking(True)

    def start_animation(self, row):
        item = self.item(row)
        if not item:
            return
        rect = self.visualItemRect(item)
        self._underline_target_width = rect.width()
        self.animation.stop()
        self.animation.setStartValue(0)
        self.animation.setEndValue(self._underline_target_width)
        self.animation.start()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        selected_row = self.currentRow()
        if selected_row < 0:
            return
        item = self.item(selected_row)
        rect = self.visualItemRect(item)

        pen = QPen(QColor("#2D2D2E"))  # pale green
        pen.setWidth(3)
        painter.setPen(pen)
        underline_y = rect.bottom() - 2
        x = rect.x() + (rect.width() - self._underline_width) // 2
        painter.drawLine(x, underline_y, x + self._underline_width, underline_y)

    def get_underline_width(self):
        return self._underline_width

    def set_underline_width(self, width):
        self._underline_width = width
        self.viewport().update()

    underline_width = pyqtProperty(int, get_underline_width, set_underline_width)

# ---------------- Main Window ----------------
class CyberKiddle(QWidget):
    def __init__(self):
        super().__init__()

        # Window title and icon
        self.setWindowTitle('Cyberkiddle version 0.1.0')
        self.setGeometry(100, 100, 1000, 650)
        icon_path = os.path.join(os.path.dirname(__file__), 'icon', 'icon.png')
        self.setWindowIcon(QIcon(icon_path))

        # Theme buttons
        self.dark_button = QPushButton("Dark Mode")
        self.light_button = QPushButton("Light Mode")
        for btn in (self.dark_button, self.light_button):
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setStyleSheet(self.button_style_unchecked())
        self.dark_button.clicked.connect(self.set_dark_mode)
        self.light_button.clicked.connect(self.set_light_mode)

        # Sidebar top layout with logo and software name
        self.sidebar_top_layout = QVBoxLayout()
        self.sidebar_top_layout.setAlignment(Qt.AlignCenter)

        logo = QLabel()
        pixmap = QPixmap(icon_path).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo.setPixmap(pixmap)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("border-radius: 50px; border: 0px;")

        software_name = QLabel("Cyberkiddle")
        software_name.setAlignment(Qt.AlignCenter)
        software_name.setStyleSheet("font-size: 18px; font-weight: bold; color: red; margin-top: 10px;")

        self.sidebar_top_layout.addWidget(logo)
        self.sidebar_top_layout.addWidget(software_name)

        # Sidebar with tabs
        self.list_widget = AnimatedUnderlineListWidget()
        self.list_widget.insertItem(0, "Dashboard")
        self.list_widget.insertItem(1, "My system")
        self.list_widget.insertItem(2, "Network")
        self.list_widget.insertItem(3, "Processes")
        self.list_widget.insertItem(4, "Live Scan")
        self.list_widget.insertItem(5, "Alerts")
        self.list_widget.insertItem(6, "Ask AI")
        self.list_widget.insertItem(7, "About")
        self.list_widget.setFixedWidth(220)
        self.list_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # Tab stack
        self.stack = QStackedWidget()
        self.stack.addWidget(create_dashboard_tab())      # index 0
        self.stack.addWidget(create_system_info_tab())    # index 1
        self.stack.addWidget(create_network_tab())        # index 2
        self.stack.addWidget(create_processes_tab())      # index 3
        self.stack.addWidget(create_live_scan_tab())      # index 4
        self.stack.addWidget(create_alerts_tab())         # index 5
        self.stack.addWidget(create_about_tab())          # index 6

        # Handle tab clicks
        def on_tab_clicked(index):
            item_text = self.list_widget.item(index).text()
            if item_text == "Ask AI":
                # Run the command in a background thread
                threading.Thread(target=lambda: os.system("/usr/share/cyberkiddle/venvAI/bin/python3 gui_chat.py"), daemon=True).start()
            else:
                # Map list index to stack index
                mapping = {
                    "Dashboard": 0,
                    "My system": 1,
                    "Network": 2,
                    "Processes": 3,
                    "Live Scan": 4,
                    "Alerts": 5,
                    "About": 6
                }
                stack_index = mapping.get(item_text, 0)
                self.stack.setCurrentIndex(stack_index)

        self.list_widget.currentRowChanged.connect(on_tab_clicked)

        # Set default tab
        self.list_widget.setCurrentRow(0)
        self.list_widget.start_animation(0)

        # Layouts
        sidebar_layout = QVBoxLayout()
        sidebar_layout.addLayout(self.sidebar_top_layout)
        sidebar_layout.addWidget(self.list_widget)

        main_content_layout = QHBoxLayout()
        main_content_layout.addLayout(sidebar_layout, 1)
        main_content_layout.addWidget(self.stack, 4)

        theme_buttons_layout = QHBoxLayout()
        theme_buttons_layout.addStretch()
        theme_buttons_layout.addWidget(self.dark_button)
        theme_buttons_layout.addSpacing(20)
        theme_buttons_layout.addWidget(self.light_button)
        theme_buttons_layout.addStretch()

        main_layout = QVBoxLayout()
        main_layout.addLayout(main_content_layout)
        main_layout.addLayout(theme_buttons_layout)
        self.setLayout(main_layout)

        # Start with dark mode
        self.set_dark_mode()

    # ---------------- Button Styles ----------------
    def button_style_checked(self):
        return """
            QPushButton {
                background: #000;
                color: #fff;
                border-radius: 0px;
                font-weight: bold;
                padding: 12px 0px;
                border: 0px;
                min-width: 0;
                outline: none;
            }
            QPushButton:hover {
                background: #222;
                color: #fff;
                border: 0px;
                outline: none;
            }
            QPushButton:focus {
                outline: none;
                border: 0px;
            }
        """

    def button_style_unchecked(self):
        return """
            QPushButton {
                background: #000;
                color: #fff;
                border-radius: 0px;
                padding: 12px 0px;
                border: 0px;
                min-width: 0;
                outline: none;
            }
            QPushButton:hover {
                background-color: #222;
                color: #fff;
                border: 0px;
                outline: none;
            }
            QPushButton:focus {
                outline: none;
                border: 0px;
            }
        """

    # ---------------- Theme Modes ----------------
    def set_dark_mode(self):
        self.dark_button.setChecked(True)
        self.light_button.setChecked(False)
        self.dark_button.setStyleSheet(self.button_style_checked())
        self.light_button.setStyleSheet(self.button_style_unchecked())

        self.setStyleSheet("""
            QWidget {
                background-color: #1E1E1E;
                color: #ECECEC;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 15px;
            }
            QListWidget {
                background-color: #2A2A2A;
                color: #F0F0F0;
                font-size: 16px;
                border: 1px solid #3A3A3A;
                border-radius: 8px;
                padding-top: 10px;
            }
            QListWidget::item {
                padding: 14px 24px;
                border-radius: 6px;
                margin: 6px 10px;
                transition: background-color 0.3s ease, color 0.3s ease;
            }
            QListWidget::item:hover {
                background-color: #3D3D3D;
                color: #00FFC6;
            }
            QListWidget::item:selected {
                background-color: #4C5CFF;
                color: #FFFFFF;
                font-weight: bold;
            }
            QPushButton {
                font-size: 14px;
                padding: 8px 18px;
                border-radius: 10px;
                border: 1.5px solid #5A5A5A;
                background-color: #2E2E2E;
                color: #F0F0F0;
                font-weight: 600;
                transition: background-color 0.3s ease, color 0.3s ease;
            }
            QPushButton:hover {
                background-color: #00FFC6;
                color: #121212;
                border-color: #00FFC6;
            }
            QPushButton:pressed {
                background-color: #00D1AA;
                border-color: #00D1AA;
            }
        """)

    def set_light_mode(self):
        self.dark_button.setChecked(False)
        self.light_button.setChecked(True)
        self.dark_button.setStyleSheet(self.button_style_unchecked())
        self.light_button.setStyleSheet(self.button_style_checked())

        self.setStyleSheet("""
            QWidget {
                background-color: #F5F7FA;
                color: #212121;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 15px;
            }
            QListWidget {
                background-color: #FFFFFF;
                color: #212121;
                font-size: 16px;
                border: 1px solid #DDDDE1;
                border-radius: 8px;
                padding-top: 10px;
                outline: none;
            }
            QListWidget::item {
                padding: 14px 24px;
                border-radius: 8px;
                margin: 6px 10px;
                transition: background-color 0.3s ease, color 0.3s ease;
            }
            QListWidget::item:hover {
                background-color: #E3E8FF;
                color: #0D1A7A;
            }
            QListWidget::item:selected {
                background-color: #4C6EF5;
                color: #FFFFFF;
                font-weight: 600;
                border: none;
            }
            QPushButton {
                font-size: 14px;
                padding: 8px 18px;
                border-radius: 10px;
                border: 1.5px solid #4C6EF5;
                background-color: #FFFFFF;
                color: #4C6EF5;
                font-weight: 600;
                transition: background-color 0.3s ease, color 0.3s ease;
            }
            QPushButton:hover {
                background-color: #4C6EF5;
                color: #FFFFFF;
                border-color: #3B57D1;
            }
            QPushButton:pressed {
                background-color: #3B57D1;
                border-color: #2B3FA8;
            }
        """)

# ---------------- Main ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CyberKiddle()
    window.show()
    sys.exit(app.exec_())
