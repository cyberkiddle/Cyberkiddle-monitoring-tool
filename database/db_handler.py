import sqlite3
import os


class DatabaseHandler:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), '..', 'cyberkiddle.db')
            db_path = os.path.abspath(db_path)  # absolute path for clarity
        print(f"[DatabaseHandler] Using DB path: {db_path}")  # debug print
        self.conn = sqlite3.connect(db_path)
        self.create_alerts_table()

    def create_alerts_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            pid INTEGER NOT NULL,
            alert TEXT NOT NULL
        )
        """
        self.conn.execute(query)
        self.conn.commit()

    def insert_alert(self, time, pid, alert):
        query = "INSERT INTO alerts (time, pid, alert) VALUES (?, ?, ?)"
        self.conn.execute(query, (time, pid, alert))
        self.conn.commit()

    def get_alerts(self):
        """Existing method — kept unchanged so alert_manager.py / old dashboard keep working."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT time, pid, alert FROM alerts ORDER BY id DESC")
        return cursor.fetchall()

    # ---------- New methods added for live web dashboard polling ----------

    def get_latest_id(self):
        """Highest alert id currently in the table (0 if empty). Used as a cheap change-detector."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM alerts")
        return cursor.fetchone()[0]

    def get_alerts_since(self, since_id, limit=200):
        """All alerts with id > since_id, oldest first (so toasts pop in the order they happened)."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, time, pid, alert FROM alerts WHERE id > ? ORDER BY id ASC LIMIT ?",
            (since_id, limit)
        )
        return cursor.fetchall()

    def get_recent(self, limit=100, search=None):
        """Paged/searchable fetch for the dashboard table, newest first, includes id."""
        cursor = self.conn.cursor()
        if search:
            like = f"%{search}%"
            cursor.execute(
                "SELECT id, time, pid, alert FROM alerts "
                "WHERE CAST(pid AS TEXT) LIKE ? OR alert LIKE ? "
                "ORDER BY id DESC LIMIT ?",
                (like, like, limit)
            )
        else:
            cursor.execute(
                "SELECT id, time, pid, alert FROM alerts ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        return cursor.fetchall()

    def close(self):
        self.conn.close()