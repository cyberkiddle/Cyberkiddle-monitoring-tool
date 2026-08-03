"""
live_scan_tab.py
-----------------
Runs LinPEAS (a privilege-escalation enumeration script) and streams its
output into the GUI.

Fix from the previous version: LinPEAS output is heavily ANSI-colored and
uses carriage returns for progress bars/spinners. The old implementation
dumped raw bytes into a QPlainTextEdit, which cannot interpret ANSI codes
and does not collapse \\r-driven redraws — the result was pages of raw
escape-code garbage (see: literal "[1;34mBlue[0m" text, and thousands of
near-duplicate progress-bar lines).

This version:
  - Converts ANSI SGR colour codes (16-colour, 256-colour, and truecolor)
    into real HTML colour via AnsiToHtmlStreamer.
  - Correctly collapses \\r-driven redraws into a single in-place line
    instead of spamming the widget.
  - Batches UI updates on a timer instead of updating on every single
    process read, so a very "chatty" scan doesn't freeze the interface.
  - Builds a lightweight section index (best-effort heuristic) so the
    user can jump to a section instead of scrolling a wall of text.
  - Keeps the full raw (un-truncated) output in memory for export, even
    though the on-screen widget caps its block count for performance.
"""
import re
import html as html_lib

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QListWidget, QSplitter, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QProcess, QTimer
from PyQt5.QtGui import QTextCursor, QFont

from ansi_stream import AnsiToHtmlStreamer


# Best-effort heuristic for LinPEAS-style section headers: short lines,
# capitalised, made of readable words. Not perfect, but useful enough to
# give a jump-to list instead of nothing.
SECTION_PATTERN = re.compile(r'^[A-Z][A-Za-z0-9 /&\-]{2,40}:?\s*$')


def create_live_scan_tab():
    page = QWidget()
    layout = QVBoxLayout()
    layout.setContentsMargins(15, 15, 15, 15)
    layout.setSpacing(12)

    # ---------------- header row ----------------
    header_row = QHBoxLayout()
    title = QLabel("<h2>Host Scanner</h2>")
    header_row.addWidget(title)
    header_row.addStretch()

    status_label = QLabel("Idle")
    status_label.setStyleSheet("color:#999999; font-weight:600;")
    header_row.addWidget(status_label)
    layout.addLayout(header_row)

    # ---------------- section index + terminal ----------------
    splitter = QSplitter(Qt.Horizontal)

    section_list = QListWidget()
    section_list.setFixedWidth(220)
    section_list.setStyleSheet("""
        QListWidget { background:#151515; color:#9fb0aa; border:1px solid #2a2a2a; border-radius:8px; }
        QListWidget::item { padding:6px 8px; }
        QListWidget::item:selected { background:#2f5233; color:#baffc9; }
        QListWidget::item:hover { background:#1f1f1f; }
    """)
    section_placeholder = "Sections will appear here once a scan is running"
    section_list.addItem(section_placeholder)
    section_list.setEnabled(False)

    terminal = QTextEdit()
    terminal.setReadOnly(True)
    terminal.setFont(QFont("monospace", 10))
    terminal.setStyleSheet("""
        QTextEdit {
            background-color: #0b0b0b;
            color: #d0d0d0;
            border-radius: 8px;
            padding: 8px;
            border: 1px solid #262626;
        }
    """)
    # Cap on-screen blocks so a very long/chatty scan doesn't slow rendering.
    # Full raw output is still kept separately (raw_log) for export.
    terminal.document().setMaximumBlockCount(4000)

    splitter.addWidget(section_list)
    splitter.addWidget(terminal)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    layout.addWidget(splitter, stretch=1)

    # ---------------- buttons ----------------
    button_row = QHBoxLayout()

    start_button = QPushButton("Start Scan")
    start_button.setFixedHeight(46)
    start_button.setFixedWidth(180)
    start_button.setCursor(Qt.PointingHandCursor)
    start_button.setStyleSheet("""
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #6a85b6, stop:1 #bac8e0);
            color: black;
            border-radius: 22px;
            font-weight: bold;
            font-size: 16px;
            border: 0.1px solid #4a69ad;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #1a1a1a, stop:1 #333333);
            color: #00FF00;
        }
        QPushButton:pressed {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #5a6ea6, stop:1 #a0b8d0);
        }
        QPushButton:disabled {
            background: #3a3a3a;
            color: #888888;
        }
    """)

    plain_btn_style = """
        QPushButton {
            background: #2a2a2a; color: #d0d0d0; border-radius: 8px;
            border: 1px solid #3a3a3a; padding: 8px 16px; font-weight: 600;
        }
        QPushButton:hover { background: #363636; }
        QPushButton:disabled { color: #666666; }
    """
    clear_button = QPushButton("Clear")
    clear_button.setStyleSheet(plain_btn_style)
    clear_button.setCursor(Qt.PointingHandCursor)

    export_button = QPushButton("Export Log")
    export_button.setStyleSheet(plain_btn_style)
    export_button.setCursor(Qt.PointingHandCursor)
    export_button.setEnabled(False)

    button_row.addStretch()
    button_row.addWidget(start_button)
    button_row.addWidget(clear_button)
    button_row.addWidget(export_button)
    button_row.addStretch()
    layout.addLayout(button_row)

    page.setLayout(layout)

    # ---------------- streaming state ----------------
    process = QProcess(page)
    streamer = AnsiToHtmlStreamer()
    raw_log = []             # full raw text (ANSI stripped on export), unbounded
    pending_committed = []   # lines finished since the last UI flush
    pending_current = {"html": None}
    page._has_open_line = False
    seen_sections = set()

    flush_timer = QTimer(page)
    flush_timer.setInterval(100)  # batch UI updates instead of one per process read

    def flush_ui():
        if not pending_committed and pending_current["html"] is None:
            return

        cursor = terminal.textCursor()
        cursor.movePosition(QTextCursor.End)

        # Erase whatever in-progress line was shown last flush — it's about
        # to be replaced by either the finalized committed line(s) below,
        # or an updated in-progress line.
        if page._has_open_line:
            cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()

        for line_html in pending_committed:
            cursor.insertHtml(line_html)
            cursor.insertBlock()

            plain = html_lib.unescape(re.sub('<[^<]+?>', '', line_html)).strip()
            if plain and plain not in seen_sections and SECTION_PATTERN.match(plain) and 3 <= len(plain) <= 40:
                seen_sections.add(plain)
                if section_list.count() == 1 and not section_list.isEnabled():
                    section_list.clear()
                    section_list.setEnabled(True)
                section_list.addItem(plain)

        pending_committed.clear()

        if pending_current["html"] is not None:
            cursor.insertHtml(pending_current["html"])
            page._has_open_line = True
            pending_current["html"] = None
        else:
            page._has_open_line = False

        terminal.setTextCursor(cursor)
        terminal.ensureCursorVisible()

    flush_timer.timeout.connect(flush_ui)

    def handle_output(data: bytes):
        text = data.decode(errors="replace")
        raw_log.append(text)
        committed, current = streamer.feed(text)
        pending_committed.extend(committed)
        pending_current["html"] = current

    process.readyReadStandardOutput.connect(
        lambda: handle_output(bytes(process.readAllStandardOutput()))
    )
    process.readyReadStandardError.connect(
        lambda: handle_output(bytes(process.readAllStandardError()))
    )

    def on_finished():
        tail = streamer.flush_remaining()
        if tail:
            pending_committed.append(tail)
        flush_ui()
        flush_timer.stop()
        start_button.setEnabled(True)
        start_button.setText("Start Scan")
        export_button.setEnabled(bool(raw_log))
        status_label.setText("Scan finished")
        status_label.setStyleSheet("color:#7ee787; font-weight:600;")

    process.finished.connect(on_finished)

    def reset_streamer():
        streamer.fg = None
        streamer.bg = None
        streamer.bold = False
        streamer._pending = ""
        streamer._current_line = []

    def start_scan():
        start_button.setEnabled(False)
        start_button.setText("Scanning...")
        export_button.setEnabled(False)
        status_label.setText("Running...")
        status_label.setStyleSheet("color:#e5c07b; font-weight:600;")

        terminal.clear()
        section_list.clear()
        section_list.addItem(section_placeholder)
        section_list.setEnabled(False)
        seen_sections.clear()
        raw_log.clear()
        pending_committed.clear()
        pending_current["html"] = None
        reset_streamer()
        page._has_open_line = False

        flush_timer.start()

        # Downloads LinPEAS fresh each run and removes it afterward.
        # Note: this fetches and executes a remote script with no
        # integrity check (no checksum/signature verification) — fine for
        # a personal lab tool, but worth flagging as a limitation in a
        # security-focused report.
        cmd = (
            "bash -c 'tmp=$(mktemp); "
            "curl -fsSL https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh -o \"$tmp\" && "
            "chmod +x \"$tmp\" && bash \"$tmp\"; "
            "rm -f \"$tmp\"'"
        )
        process.start("bash", ["-c", cmd])

    start_button.clicked.connect(start_scan)

    def clear_terminal():
        if process.state() != QProcess.NotRunning:
            return
        terminal.clear()
        section_list.clear()
        section_list.addItem(section_placeholder)
        section_list.setEnabled(False)
        seen_sections.clear()
        raw_log.clear()
        status_label.setText("Idle")
        status_label.setStyleSheet("color:#999999; font-weight:600;")
        export_button.setEnabled(False)

    clear_button.clicked.connect(clear_terminal)

    def export_log():
        if not raw_log:
            QMessageBox.information(page, "Nothing to export", "Run a scan first.")
            return
        path, _ = QFileDialog.getSaveFileName(page, "Save scan log", "linpeas_output.txt", "Text Files (*.txt)")
        if not path:
            return
        clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', "".join(raw_log))
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(clean)
            QMessageBox.information(page, "Exported", f"Saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(page, "Export failed", str(e))

    export_button.clicked.connect(export_log)

    def jump_to_section(item):
        if not section_list.isEnabled():
            return
        cursor = terminal.document().find(item.text())
        if not cursor.isNull():
            terminal.setTextCursor(cursor)
            terminal.ensureCursorVisible()

    section_list.itemClicked.connect(jump_to_section)

    return page