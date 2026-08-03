# about_tab.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
import os

def create_about_tab():
    page = QWidget()
    vbox = QVBoxLayout()

    # Create web view
    webview = QWebEngineView()

    # Load the local HTML file
    html_path = os.path.join(os.path.dirname(__file__), "assets", "about.html")
    if os.path.exists(html_path):
        webview.load(QUrl.fromLocalFile(html_path))
    else:
        # If file not found, show error
        html_content = "<h2><center>Error: about.html not found</center></h2>"
        webview.setHtml(html_content)

    vbox.addWidget(webview)
    page.setLayout(vbox)
    return page
