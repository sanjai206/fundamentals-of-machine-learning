"""
ML Productivity Tracker — Desktop App
======================================
A single-file Python desktop application that:
  1. Collects real-time activity (active window, idle, keystrokes)
  2. Stores everything in SQLite
  3. Trains an XGBoost classifier on your activity history
  4. Shows a live Tkinter dashboard with 4 tabs:
       - Live Monitor   → current app, score, recent activity feed
       - Today's Report → pie chart, bar chart, summary stats
       - Weekly Charts  → 7-day productivity trend
       - ML Analysis    → model accuracy, feature importance, predictions

Requirements (install once):
    pip install matplotlib scikit-learn xgboost pandas

Run:
    python productivity_app.py

On first launch it trains the ML model on synthetic data (activity_logs.csv).
After that it tracks your real activity in real time.

Author: Your project
"""

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
import threading
import time
import sqlite3
import os
import sys
import csv
import json
import queue
import datetime
import platform
import collections
import subprocess

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import xgboost as xgb
import joblib

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS & PATHS
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DB_PATH       = os.path.join(BASE_DIR, "activity.db")
MODEL_PATH    = os.path.join(BASE_DIR, "model.pkl")
ENCODER_PATH  = os.path.join(BASE_DIR, "label_encoder.pkl")
CSV_PATH      = os.path.join(BASE_DIR, "activity_logs.csv")
REPORT_PATH   = os.path.join(BASE_DIR, "report_today.csv")
META_PATH     = os.path.join(BASE_DIR, "model_meta.json")

POLL_INTERVAL    = 2      # seconds between activity polls
FLUSH_INTERVAL   = 5      # seconds between DB flushes
ML_INTERVAL      = 30     # seconds between ML re-scoring
CHART_REFRESH    = 15     # seconds between chart refreshes

# App → category mapping (extend as needed)
APP_CATEGORY = {
    "code"       : "Coding",       "pycharm"    : "Coding",
    "terminal"   : "Coding",       "bash"       : "Coding",
    "postman"    : "Coding",       "dbeaver"    : "Coding",
    "vim"        : "Coding",       "nvim"       : "Coding",
    "slack"      : "Communication","teams"      : "Communication",
    "zoom"       : "Communication","discord"    : "Communication",
    "outlook"    : "Communication","thunderbird": "Communication",
    "notion"     : "Learning",     "obsidian"   : "Learning",
    "anki"       : "Learning",     "kindle"     : "Learning",
    "word"       : "Documents",    "excel"      : "Documents",
    "powerpoint" : "Documents",    "libreoffice": "Documents",
    "acrobat"    : "Documents",    "spotify"    : "Entertainment",
    "vlc"        : "Entertainment","steam"      : "Entertainment",
    "explorer"   : "System",       "finder"     : "System",
    "settings"   : "System",       "system"     : "System",
}

URL_CATEGORY = {
    "github.com"         : ("Learning",      "Productive"),
    "stackoverflow.com"  : ("Learning",      "Productive"),
    "coursera.org"       : ("Learning",      "Productive"),
    "udemy.com"          : ("Learning",      "Productive"),
    "medium.com"         : ("Learning",      "Productive"),
    "developer.mozilla"  : ("Learning",      "Productive"),
    "docs.python.org"    : ("Learning",      "Productive"),
    "mail.google.com"    : ("Communication", "Neutral"),
    "gmail.com"          : ("Communication", "Neutral"),
    "docs.google.com"    : ("Documents",     "Neutral"),
    "sheets.google.com"  : ("Documents",     "Neutral"),
    "notion.so"          : ("Learning",      "Productive"),
    "youtube.com"        : ("Entertainment", "Unproductive"),
    "netflix.com"        : ("Entertainment", "Unproductive"),
    "twitter.com"        : ("Social Media",  "Unproductive"),
    "x.com"              : ("Social Media",  "Unproductive"),
    "reddit.com"         : ("Social Media",  "Unproductive"),
    "instagram.com"      : ("Social Media",  "Unproductive"),
    "facebook.com"       : ("Social Media",  "Unproductive"),
    "tiktok.com"         : ("Social Media",  "Unproductive"),
    "linkedin.com"       : ("Social Media",  "Neutral"),
    "web.whatsapp.com"   : ("Communication", "Neutral"),
}

LABEL_COLOR = {
    "Productive"   : "#1D9E75",  # teal
    "Neutral"      : "#888780",  # gray
    "Unproductive" : "#D85A30",  # coral/red
}

CATEGORY_COLOR = {
    "Coding"        : "#534AB7",
    "Learning"      : "#1D9E75",
    "Communication" : "#378ADD",
    "Documents"     : "#BA7517",
    "Entertainment" : "#D85A30",
    "Social Media"  : "#D4537E",
    "System"        : "#888780",
    "Idle"          : "#B4B2A9",
}


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 1 — DATABASE
# ─────────────────────────────────────────────────────────────────────────────
class Database:
    """Manages SQLite storage. Thread-safe via connection-per-call pattern."""

    def __init__(self, path=DB_PATH):
        self.path = path
        self._init_schema()

    def _conn(self):
        return sqlite3.connect(self.path, timeout=10)

    def _init_schema(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp    TEXT    NOT NULL,
                    date         TEXT    NOT NULL,
                    hour         INTEGER NOT NULL,
                    day_of_week  TEXT    NOT NULL,
                    app_name     TEXT,
                    window_title TEXT,
                    url          TEXT,
                    category     TEXT,
                    label        TEXT,
                    duration_sec REAL,
                    is_idle      INTEGER DEFAULT 0,
                    keystrokes   INTEGER DEFAULT 0,
                    mouse_clicks INTEGER DEFAULT 0,
                    score        REAL    DEFAULT NULL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    score     REAL,
                    label     TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_date ON sessions(date)")

    def insert_session(self, session: dict):
        with self._conn() as c:
            c.execute("""
                INSERT INTO sessions
                (timestamp, date, hour, day_of_week, app_name, window_title,
                 url, category, label, duration_sec, is_idle, keystrokes, mouse_clicks)
                VALUES
                (:timestamp,:date,:hour,:day_of_week,:app_name,:window_title,
                 :url,:category,:label,:duration_sec,:is_idle,:keystrokes,:mouse_clicks)
            """, session)

    def insert_many(self, sessions: list):
        if not sessions:
            return
        with self._conn() as c:
            c.executemany("""
                INSERT INTO sessions
                (timestamp,date,hour,day_of_week,app_name,window_title,
                 url,category,label,duration_sec,is_idle,keystrokes,mouse_clicks)
                VALUES
                (:timestamp,:date,:hour,:day_of_week,:app_name,:window_title,
                 :url,:category,:label,:duration_sec,:is_idle,:keystrokes,:mouse_clicks)
            """, sessions)

    def update_scores(self, updates: list):
        """updates = [(score, label, id), ...]"""
        with self._conn() as c:
            c.executemany(
                "UPDATE sessions SET score=?, label=? WHERE id=?", updates)

    def fetch_today(self) -> pd.DataFrame:
        today = datetime.date.today().isoformat()
        with self._conn() as c:
            return pd.read_sql_query(
                "SELECT * FROM sessions WHERE date=? ORDER BY timestamp",
                c, params=(today,))

    def fetch_last_n_days(self, n=7) -> pd.DataFrame:
        since = (datetime.date.today() - datetime.timedelta(days=n)).isoformat()
        with self._conn() as c:
            return pd.read_sql_query(
                "SELECT * FROM sessions WHERE date>=? ORDER BY timestamp",
                c, params=(since,))

    def fetch_all(self) -> pd.DataFrame:
        with self._conn() as c:
            return pd.read_sql_query(
                "SELECT * FROM sessions ORDER BY timestamp", c)

    def fetch_recent(self, limit=20) -> list:
        with self._conn() as c:
            cur = c.execute(
                "SELECT timestamp,app_name,window_title,category,label,duration_sec,score "
                "FROM sessions ORDER BY id DESC LIMIT ?", (limit,))
            return cur.fetchall()

    def log_prediction(self, score, label):
        with self._conn() as c:
            c.execute(
                "INSERT INTO predictions(timestamp,score,label) VALUES(?,?,?)",
                (datetime.datetime.now().isoformat(), score, label))


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 2 — ACTIVITY COLLECTOR
# ─────────────────────────────────────────────────────────────────────────────
class ActivityCollector:
    """
    Background daemon thread.
    Polls the active window every POLL_INTERVAL seconds.
    Works on Windows, macOS, Linux (graceful fallback if tools missing).
    """

    def __init__(self, db: Database, event_queue: queue.Queue):
        self.db          = db
        self.queue       = event_queue
        self._stop       = threading.Event()
        self._buffer     = []
        self._last_flush = time.time()
        self._session_start = time.time()
        self._prev_app   = None
        self._keystrokes = 0
        self._clicks     = 0
        self._os         = platform.system()

        # Try to import pynput for keystroke tracking
        try:
            from pynput import keyboard as kb, mouse as ms
            kb.Listener(on_press=self._on_key).start()
            ms.Listener(on_click=self._on_click).start()
            self._pynput = True
        except Exception:
            self._pynput = False

    def _on_key(self, key):
        self._keystrokes += 1

    def _on_click(self, x, y, button, pressed):
        if pressed:
            self._clicks += 1

    # ── Platform-specific window title getters ──────────────────────────────

    def _get_active_window_windows(self):
        try:
            import ctypes
            import ctypes.wintypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            # Get process name
            pid = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            h = ctypes.windll.kernel32.OpenProcess(0x0400, False, pid.value)
            name_buf = ctypes.create_unicode_buffer(1024)
            ctypes.windll.psapi.GetModuleFileNameExW(h, None, name_buf, 1024)
            app = os.path.basename(name_buf.value)
            return app, title, ""
        except Exception:
            return "unknown", "", ""

    def _get_active_window_mac(self):
        try:
            script = 'tell application "System Events" to get name of first application process whose frontmost is true'
            app = subprocess.check_output(["osascript", "-e", script],
                                          timeout=1).decode().strip()
            script2 = 'tell application "System Events" to get title of front window of (first application process whose frontmost is true)'
            title = subprocess.check_output(["osascript", "-e", script2],
                                            timeout=1).decode().strip()
            return app, title, ""
        except Exception:
            return "unknown", "", ""

    def _get_active_window_linux(self):
        try:
            wid = subprocess.check_output(
                ["xdotool", "getactivewindow"], timeout=1).decode().strip()
            title = subprocess.check_output(
                ["xdotool", "getwindowname", wid], timeout=1).decode().strip()
            pid = subprocess.check_output(
                ["xdotool", "getwindowpid", wid], timeout=1).decode().strip()
            app_path = subprocess.check_output(
                ["cat", f"/proc/{pid}/comm"], timeout=1).decode().strip()
            return app_path, title, ""
        except Exception:
            return "unknown", "", ""

    def get_active_window(self):
        if self._os == "Windows":
            return self._get_active_window_windows()
        elif self._os == "Darwin":
            return self._get_active_window_mac()
        else:
            return self._get_active_window_linux()

    # ── Classify activity ───────────────────────────────────────────────────

    def classify(self, app_name: str, title: str, url: str):
        app_lower = app_name.lower()

        # URL-based classification (most specific)
        for domain, (cat, lbl) in URL_CATEGORY.items():
            if domain in url.lower():
                return cat, lbl

        # App-based classification
        for keyword, cat in APP_CATEGORY.items():
            if keyword in app_lower:
                label = "Productive" if cat in ("Coding", "Learning", "Documents") else \
                        "Neutral"    if cat in ("Communication", "System") else \
                        "Unproductive"
                return cat, label

        # Title-based fallback
        title_lower = title.lower()
        if any(k in title_lower for k in ["youtube", "netflix", "reddit", "twitter", "instagram"]):
            return "Entertainment", "Unproductive"
        if any(k in title_lower for k in ["stackoverflow", "github", "docs", "tutorial"]):
            return "Learning", "Productive"

        return "Other", "Neutral"

    # ── Main poll loop ───────────────────────────────────────────────────────

    def _poll(self):
        app, title, url = self.get_active_window()
        now = datetime.datetime.now()

        # Detect session change
        if app != self._prev_app and self._prev_app is not None:
            duration = time.time() - self._session_start
            cat, lbl = self.classify(self._prev_app, title, url)
            session = {
                "timestamp"   : now.isoformat(timespec="seconds"),
                "date"        : now.date().isoformat(),
                "hour"        : now.hour,
                "day_of_week" : now.strftime("%A"),
                "app_name"    : self._prev_app,
                "window_title": title,
                "url"         : url,
                "category"    : cat,
                "label"       : lbl,
                "duration_sec": round(duration, 1),
                "is_idle"     : 0,
                "keystrokes"  : self._keystrokes,
                "mouse_clicks": self._clicks,
            }
            self._buffer.append(session)
            self.queue.put(("session", session))
            # Reset counters
            self._keystrokes = 0
            self._clicks = 0
            self._session_start = time.time()

        self._prev_app = app

        # Flush buffer to DB
        if time.time() - self._last_flush > FLUSH_INTERVAL:
            if self._buffer:
                self.db.insert_many(self._buffer)
                self._buffer.clear()
            self._last_flush = time.time()

    def run(self):
        while not self._stop.is_set():
            try:
                self._poll()
            except Exception as e:
                self.queue.put(("error", str(e)))
            time.sleep(POLL_INTERVAL)

    def start(self):
        t = threading.Thread(target=self.run, daemon=True)
        t.start()
        return t

    def stop(self):
        self._stop.set()


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 3 — ML ENGINE
# ─────────────────────────────────────────────────────────────────────────────
class MLEngine:
    """
    Trains XGBoost on CSV data, then scores live sessions every ML_INTERVAL sec.
    Produces a productivity score 0–100.
    """

    FEATURES = [
        "hour", "duration_sec", "is_idle", "keystrokes", "mouse_clicks",
        "category_enc", "day_enc", "session_idx",
    ]

    def __init__(self, db: Database, event_queue: queue.Queue):
        self.db      = db
        self.queue   = event_queue
        self.model   = None
        self.le_cat  = LabelEncoder()
        self.le_day  = LabelEncoder()
        self.le_lbl  = LabelEncoder()
        self.trained = False
        self.report  = {}
        self.category_priors = {}
        self._stop   = threading.Event()
        self._fit_feature_encoders()

    def _fit_feature_encoders(self):
        all_cats = list(CATEGORY_COLOR.keys()) + ["Other"]
        all_days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        self.le_cat.fit(all_cats)
        self.le_day.fit(all_days)

    def _compute_category_priors(self, df: pd.DataFrame):
        priors = {}
        for category, group in df.groupby("category"):
            counts = group["label"].fillna("Neutral").value_counts(normalize=True)
            priors[category] = {
                "Neutral": float(counts.get("Neutral", 0.0)),
                "Productive": float(counts.get("Productive", 0.0)),
                "Unproductive": float(counts.get("Unproductive", 0.0)),
            }
        self.category_priors = priors

    def _save_meta(self):
        payload = {
            "category_priors": self.category_priors,
            "report": self.report,
        }
        with open(META_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def _load_meta(self):
        if not os.path.exists(META_PATH):
            return False
        with open(META_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.category_priors = payload.get("category_priors", {})
        self.report = payload.get("report", {})
        return True

    def _blended_probabilities(self, row: pd.Series, proba):
        class_list = list(self.le_lbl.classes_)
        proba_map = {label: float(value) for label, value in zip(class_list, proba)}
        category = row.get("category", "Other")
        duration = float(row.get("duration_sec", 0) or 0)
        keystrokes = float(row.get("keystrokes", 0) or 0)
        mouse_clicks = float(row.get("mouse_clicks", 0) or 0)

        prior = self.category_priors.get(category)
        if not prior:
            return proba_map

        low_signal = duration < 180 or (keystrokes == 0 and mouse_clicks == 0)
        if not low_signal:
            return proba_map

        if duration < 30:
            model_weight = 0.2
        elif duration < 120:
            model_weight = 0.35
        else:
            model_weight = 0.55

        blended = {}
        for label in ("Neutral", "Productive", "Unproductive"):
            blended[label] = model_weight * proba_map.get(label, 0.0) + (1 - model_weight) * prior.get(label, 0.0)
        total = sum(blended.values()) or 1.0
        for label in blended:
            blended[label] /= total
        return blended

    # ── Feature engineering ─────────────────────────────────────────────────

    def _engineer(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        all_cats = list(CATEGORY_COLOR.keys()) + ["Other"]
        all_days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

        df["category"] = df["category"].apply(
            lambda x: x if x in all_cats else "Other")
        df["day_of_week"] = df["day_of_week"].apply(
            lambda x: x if x in all_days else "Monday")

        df["category_enc"] = self.le_cat.transform(df["category"])
        df["day_enc"]      = self.le_day.transform(df["day_of_week"])
        df["session_idx"]  = range(len(df))
        df["duration_sec"] = df["duration_sec"].fillna(30).clip(0, 7200)
        df["keystrokes"]   = df["keystrokes"].fillna(0)
        df["mouse_clicks"] = df["mouse_clicks"].fillna(0)
        df["is_idle"]      = df["is_idle"].fillna(0)
        return df

    # ── Training ────────────────────────────────────────────────────────────

    def train(self, csv_path=CSV_PATH):
        """Train on synthetic (or real) CSV data."""
        if not os.path.exists(csv_path):
            self.queue.put(("ml_status", "CSV not found — skipping training"))
            return False

        df = pd.read_csv(csv_path)
        required = {"label", "category", "day_of_week", "hour",
                    "duration_sec", "is_idle", "keystrokes", "mouse_clicks"}
        if not required.issubset(df.columns):
            self.queue.put(("ml_status", "CSV missing columns"))
            return False

        df = self._engineer(df)
        self._compute_category_priors(df)

        # Encode labels
        self.le_lbl.fit(["Productive", "Neutral", "Unproductive"])
        y = self.le_lbl.transform(df["label"].fillna("Neutral"))
        X = df[self.FEATURES]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y)

        self.model = xgb.XGBClassifier(
            n_estimators=150, max_depth=5, learning_rate=0.1,
            use_label_encoder=False, eval_metric="mlogloss",
            random_state=42, n_jobs=-1)
        self.model.fit(X_train, y_train)

        y_pred = self.model.predict(X_test)
        acc    = accuracy_score(y_test, y_pred)
        report = classification_report(
            y_test, y_pred,
            target_names=self.le_lbl.classes_, output_dict=True)

        self.report = {
            "accuracy"   : round(acc * 100, 1),
            "report"     : report,
            "n_samples"  : len(df),
            "feature_imp": dict(zip(
                self.FEATURES,
                self.model.feature_importances_.tolist())),
        }

        joblib.dump(self.model, MODEL_PATH)
        joblib.dump(self.le_lbl, ENCODER_PATH)
        self._save_meta()
        self.trained = True
        self.queue.put(("ml_status", f"Model trained — accuracy {acc*100:.1f}%"))
        self.queue.put(("ml_report", self.report))
        return True

    def load(self):
        if os.path.exists(MODEL_PATH) and os.path.exists(ENCODER_PATH):
            self.model   = joblib.load(MODEL_PATH)
            self.le_lbl  = joblib.load(ENCODER_PATH)
            self._load_meta()
            self.trained = True
            return True
        return False

    # ── Live scoring ─────────────────────────────────────────────────────────

    def score_session(self, session: dict) -> tuple:
        """Returns (score 0-100, label)."""
        if not self.trained or self.model is None:
            return 50, "Neutral"

        row = pd.DataFrame([session])
        row = self._engineer(row)

        # Ensure all features present
        for f in self.FEATURES:
            if f not in row.columns:
                row[f] = 0

        proba = self.model.predict_proba(row[self.FEATURES])[0]
        blended = self._blended_probabilities(row.iloc[0], proba)
        label = max(blended, key=blended.get)

        # Score: productive prob * 100, adjusted by neutral
        score = (
            blended.get("Productive", 0.0) * 100
            + blended.get("Neutral", 0.0) * 50
        )
        score  = round(min(100, max(0, score)), 1)
        return score, label

    def score_today(self):
        """Score all unscore sessions from today and update DB."""
        if not self.trained:
            return None, None

        df = self.db.fetch_today()
        if df.empty:
            return None, None

        df = self._engineer(df)
        for f in self.FEATURES:
            if f not in df.columns:
                df[f] = 0

        proba = self.model.predict_proba(df[self.FEATURES])
        labels = []
        scores = []
        for idx, raw_proba in enumerate(proba):
            blended = self._blended_probabilities(df.iloc[idx], raw_proba)
            labels.append(max(blended, key=blended.get))
            score = (
                blended.get("Productive", 0.0) * 100
                + blended.get("Neutral", 0.0) * 50
            )
            scores.append(round(min(100, max(0, score)), 1))

        scores = np.array(scores, dtype=float)
        avg_score = round(float(scores.mean()), 1)
        avg_label = labels[np.argmax(scores)]

        # Update DB
        updates = [(round(float(s), 1), str(l), int(i))
                   for s, l, i in zip(scores, labels, df["id"])]
        self.db.update_scores(updates)
        self.db.log_prediction(avg_score, avg_label)
        return avg_score, avg_label

    # ── Background loop ─────────────────────────────────────────────────────

    def run(self):
        # Load or train
        if not self.load():
            self.queue.put(("ml_status", "Training model on CSV..."))
            self.train()
        else:
            self.queue.put(("ml_status", f"Model loaded from disk"))
            self.queue.put(("ml_report", self.report))

        while not self._stop.is_set():
            try:
                score, label = self.score_today()
                if score is not None:
                    self.queue.put(("score", (score, label)))
            except Exception as e:
                self.queue.put(("error", f"ML error: {e}"))
            time.sleep(ML_INTERVAL)

    def start(self):
        t = threading.Thread(target=self.run, daemon=True)
        t.start()
        return t

    def stop(self):
        self._stop.set()


# ─────────────────────────────────────────────────────────────────────────────
# MODULE 4 — TKINTER DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
class ProductivityApp(tk.Tk):

    # ── Palette ─────────────────────────────────────────────────────────────
    BG         = "#1A1A2E"   # dark navy background
    SURFACE    = "#16213E"   # card surface
    SURFACE2   = "#0F3460"   # slightly lighter card
    ACCENT     = "#1D9E75"   # teal accent
    TEXT       = "#E0E0E0"
    TEXT_MUTED = "#9090A0"
    BORDER     = "#2A2A4A"
    RED        = "#D85A30"
    YELLOW     = "#BA7517"
    GREEN      = "#1D9E75"

    def __init__(self, db: Database, ml: MLEngine, event_queue: queue.Queue):
        super().__init__()
        self.db      = db
        self.ml      = ml
        self.queue   = event_queue

        self.title("ML Productivity Tracker")
        self.geometry("1100x720")
        self.configure(bg=self.BG)
        self.resizable(True, True)

        self._current_score  = 0.0
        self._current_label  = "—"
        self._current_app    = "—"
        self._ml_report      = {}
        self._last_chart_refresh = 0

        self._setup_styles()
        self._build_ui()
        self._start_queue_poll()
        self._start_chart_refresh()

    # ── Styles ───────────────────────────────────────────────────────────────

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook",
            background=self.BG, borderwidth=0)
        style.configure("TNotebook.Tab",
            background=self.SURFACE2, foreground=self.TEXT_MUTED,
            padding=[16, 8], font=("Helvetica", 10))
        style.map("TNotebook.Tab",
            background=[("selected", self.ACCENT)],
            foreground=[("selected", "#FFFFFF")])
        style.configure("TFrame", background=self.BG)
        style.configure("Card.TFrame",
            background=self.SURFACE, relief="flat")
        style.configure("TLabel",
            background=self.BG, foreground=self.TEXT, font=("Helvetica", 10))
        style.configure("Header.TLabel",
            background=self.BG, foreground=self.TEXT,
            font=("Helvetica", 22, "bold"))
        style.configure("Score.TLabel",
            background=self.SURFACE, foreground=self.ACCENT,
            font=("Helvetica", 48, "bold"))
        style.configure("SmallMuted.TLabel",
            background=self.SURFACE, foreground=self.TEXT_MUTED,
            font=("Helvetica", 9))
        style.configure("Card.TLabel",
            background=self.SURFACE, foreground=self.TEXT,
            font=("Helvetica", 10))

    # ── Top bar ──────────────────────────────────────────────────────────────

    def _build_topbar(self, parent):
        bar = tk.Frame(parent, bg=self.SURFACE, pady=10)
        bar.pack(fill="x", padx=0, pady=(0, 2))

        tk.Label(bar, text="ML Productivity Tracker",
                 bg=self.SURFACE, fg=self.TEXT,
                 font=("Helvetica", 16, "bold")).pack(side="left", padx=20)

        # Status pill
        self._status_var = tk.StringVar(value="Starting…")
        tk.Label(bar, textvariable=self._status_var,
                 bg=self.SURFACE, fg=self.TEXT_MUTED,
                 font=("Helvetica", 9)).pack(side="right", padx=20)

        # Clock
        self._clock_var = tk.StringVar()
        tk.Label(bar, textvariable=self._clock_var,
                 bg=self.SURFACE, fg=self.ACCENT,
                 font=("Helvetica", 11, "bold")).pack(side="right", padx=10)
        self._tick_clock()

    def _tick_clock(self):
        self._clock_var.set(datetime.datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick_clock)

    # ── Full UI build ─────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar(self)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=4, pady=4)

        # Tab frames
        self._tab_live   = ttk.Frame(nb)
        self._tab_today  = ttk.Frame(nb)
        self._tab_weekly = ttk.Frame(nb)
        self._tab_ml     = ttk.Frame(nb)

        nb.add(self._tab_live,   text="  Live monitor  ")
        nb.add(self._tab_today,  text="  Today's report  ")
        nb.add(self._tab_weekly, text="  Weekly charts  ")
        nb.add(self._tab_ml,     text="  ML analysis  ")

        self._build_tab_live()
        self._build_tab_today()
        self._build_tab_weekly()
        self._build_tab_ml()

        # Bind tab switch to refresh charts
        nb.bind("<<NotebookTabChanged>>", lambda e: self._refresh_charts())

    # ────────────────────────────────────────────────────
    # TAB 1: LIVE MONITOR
    # ────────────────────────────────────────────────────

    def _build_tab_live(self):
        p = self._tab_live
        p.configure(style="TFrame")

        # Top row: score card + current app card + distraction alert
        top = tk.Frame(p, bg=self.BG)
        top.pack(fill="x", padx=16, pady=12)

        # Score card
        score_card = tk.Frame(top, bg=self.SURFACE, bd=0,
                              highlightthickness=1,
                              highlightbackground=self.BORDER)
        score_card.pack(side="left", padx=(0, 12), ipadx=20, ipady=12)

        tk.Label(score_card, text="PRODUCTIVITY SCORE",
                 bg=self.SURFACE, fg=self.TEXT_MUTED,
                 font=("Helvetica", 9, "bold")).pack(pady=(8, 0))
        self._score_label = tk.Label(score_card, text="—",
                 bg=self.SURFACE, fg=self.ACCENT,
                 font=("Helvetica", 56, "bold"))
        self._score_label.pack()
        self._score_sublabel = tk.Label(score_card, text="awaiting data",
                 bg=self.SURFACE, fg=self.TEXT_MUTED,
                 font=("Helvetica", 10))
        self._score_sublabel.pack(pady=(0, 8))

        # Score bar canvas
        self._score_bar_cv = tk.Canvas(score_card, bg=self.SURFACE,
                                       height=8, width=200,
                                       highlightthickness=0)
        self._score_bar_cv.pack(pady=(0, 10))

        # Current app card
        app_card = tk.Frame(top, bg=self.SURFACE, bd=0,
                            highlightthickness=1,
                            highlightbackground=self.BORDER)
        app_card.pack(side="left", fill="both", expand=True, ipady=12)

        tk.Label(app_card, text="CURRENT ACTIVITY",
                 bg=self.SURFACE, fg=self.TEXT_MUTED,
                 font=("Helvetica", 9, "bold")).pack(anchor="w", padx=16, pady=(8,0))

        self._app_label = tk.Label(app_card, text="—",
                 bg=self.SURFACE, fg=self.TEXT,
                 font=("Helvetica", 14, "bold"))
        self._app_label.pack(anchor="w", padx=16)

        self._title_label = tk.Label(app_card, text="",
                 bg=self.SURFACE, fg=self.TEXT_MUTED,
                 font=("Helvetica", 9))
        self._title_label.pack(anchor="w", padx=16)

        # Stats row (today totals)
        stat_frame = tk.Frame(app_card, bg=self.SURFACE)
        stat_frame.pack(fill="x", padx=16, pady=(16, 8))

        self._stat_vars = {}
        for key, label in [("productive_pct","Productive %"),
                            ("focus_hrs","Focus hrs"),
                            ("distracted_mins","Distracted mins"),
                            ("sessions_today","Sessions today")]:
            col = tk.Frame(stat_frame, bg=self.SURFACE)
            col.pack(side="left", expand=True)
            v = tk.StringVar(value="—")
            self._stat_vars[key] = v
            tk.Label(col, textvariable=v,
                     bg=self.SURFACE, fg=self.ACCENT,
                     font=("Helvetica", 18, "bold")).pack()
            tk.Label(col, text=label,
                     bg=self.SURFACE, fg=self.TEXT_MUTED,
                     font=("Helvetica", 8)).pack()

        # Activity feed
        feed_label = tk.Label(p, text="Recent activity",
                 bg=self.BG, fg=self.TEXT_MUTED,
                 font=("Helvetica", 9, "bold"))
        feed_label.pack(anchor="w", padx=16)

        feed_frame = tk.Frame(p, bg=self.SURFACE, bd=0,
                              highlightthickness=1,
                              highlightbackground=self.BORDER)
        feed_frame.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        # Header row
        hdr = tk.Frame(feed_frame, bg=self.SURFACE2)
        hdr.pack(fill="x")
        for col, w in [("Time",10),("App",18),("Title",32),("Category",14),("Label",14),("Score",8)]:
            tk.Label(hdr, text=col, bg=self.SURFACE2, fg=self.TEXT_MUTED,
                     font=("Helvetica", 8, "bold"),
                     width=w, anchor="w").pack(side="left", padx=4, pady=4)

        self._feed_frame_inner = tk.Frame(feed_frame, bg=self.SURFACE)
        self._feed_frame_inner.pack(fill="both", expand=True)

        # Refresh feed button
        tk.Button(p, text="Refresh feed",
                  command=self._refresh_feed,
                  bg=self.SURFACE2, fg=self.TEXT,
                  relief="flat", font=("Helvetica", 9),
                  padx=12, pady=4).pack(pady=(0, 8))

    def _update_score_display(self, score, label):
        self._current_score = score
        self._current_label = label
        color = self.GREEN if score >= 65 else (self.YELLOW if score >= 35 else self.RED)
        self._score_label.configure(text=str(int(score)), fg=color)
        self._score_sublabel.configure(text=label,
            fg=LABEL_COLOR.get(label, self.TEXT_MUTED))
        # Draw score bar
        cv = self._score_bar_cv
        cv.delete("all")
        cv.create_rectangle(0, 0, 200, 8, fill=self.BORDER, outline="")
        cv.create_rectangle(0, 0, int(score * 2), 8, fill=color, outline="")

    def _update_today_stats(self):
        df = self.db.fetch_today()
        if df.empty:
            return
        total = len(df)
        prod  = (df["label"] == "Productive").sum()
        pct   = round(prod / total * 100) if total else 0
        focus = round(df[df["label"] == "Productive"]["duration_sec"].sum() / 3600, 1)
        dist  = round(df[df["label"] == "Unproductive"]["duration_sec"].sum() / 60)
        self._stat_vars["productive_pct"].set(f"{pct}%")
        self._stat_vars["focus_hrs"].set(f"{focus}h")
        self._stat_vars["distracted_mins"].set(f"{dist}m")
        self._stat_vars["sessions_today"].set(str(total))

    def _refresh_feed(self):
        for w in self._feed_frame_inner.winfo_children():
            w.destroy()
        rows = self.db.fetch_recent(20)
        for i, row in enumerate(rows):
            ts, app, title, cat, label, dur, score = row
            bg = self.SURFACE if i % 2 == 0 else "#1C1C32"
            r = tk.Frame(self._feed_frame_inner, bg=bg)
            r.pack(fill="x")
            lbl_color = LABEL_COLOR.get(label, self.TEXT_MUTED) if label else self.TEXT_MUTED
            score_txt = f"{score:.0f}" if score else "—"
            for val, w, color in [
                (ts[:19] if ts else "—",         10, self.TEXT_MUTED),
                (str(app)[:16]  if app else "—",  18, self.TEXT),
                (str(title)[:30] if title else "—", 32, self.TEXT_MUTED),
                (str(cat)[:12]  if cat else "—",  14, self.TEXT_MUTED),
                (str(label)[:12] if label else "—",14, lbl_color),
                (score_txt,                         8, self.ACCENT),
            ]:
                tk.Label(r, text=val, bg=bg, fg=color,
                         font=("Helvetica", 8), width=w, anchor="w"
                         ).pack(side="left", padx=4, pady=2)

    # ────────────────────────────────────────────────────
    # TAB 2: TODAY'S REPORT
    # ────────────────────────────────────────────────────

    def _build_tab_today(self):
        p = self._tab_today
        p.configure(style="TFrame")

        self._fig_today = Figure(figsize=(11, 5), facecolor=self.BG)
        self._canvas_today = FigureCanvasTkAgg(self._fig_today, master=p)
        self._canvas_today.get_tk_widget().pack(fill="both", expand=True,
                                                 padx=8, pady=8)

    def _draw_today_charts(self):
        fig = self._fig_today
        fig.clear()
        df = self.db.fetch_today()

        ax1 = fig.add_subplot(1, 3, 1)  # Pie: label breakdown
        ax2 = fig.add_subplot(1, 3, 2)  # Bar: category time
        ax3 = fig.add_subplot(1, 3, 3)  # Hourly score

        for ax in [ax1, ax2, ax3]:
            ax.set_facecolor(self.SURFACE)
            for spine in ax.spines.values():
                spine.set_edgecolor(self.BORDER)
            ax.tick_params(colors=self.TEXT_MUTED, labelsize=8)
            ax.title.set_color(self.TEXT)

        if df.empty:
            ax1.text(0.5, 0.5, "No data today yet",
                     ha="center", va="center",
                     color=self.TEXT_MUTED, transform=ax1.transAxes)
            self._canvas_today.draw()
            return

        # ── Pie: label distribution ───────────────────────────────────────
        lbl_counts = df.groupby("label")["duration_sec"].sum()
        labels     = lbl_counts.index.tolist()
        sizes      = lbl_counts.values
        colors     = [LABEL_COLOR.get(l, self.TEXT_MUTED) for l in labels]
        ax1.pie(sizes, labels=labels, colors=colors,
                autopct="%1.0f%%", textprops={"color": self.TEXT, "fontsize": 8},
                startangle=140, wedgeprops={"edgecolor": self.BG, "linewidth": 1.5})
        ax1.set_title("Label split", fontsize=10, color=self.TEXT)

        # ── Bar: category time ─────────────────────────────────────────────
        cat_time = (df.groupby("category")["duration_sec"].sum() / 3600).sort_values()
        bar_colors = [CATEGORY_COLOR.get(c, "#888780") for c in cat_time.index]
        bars = ax2.barh(cat_time.index, cat_time.values, color=bar_colors,
                        edgecolor=self.BG, linewidth=0.5)
        ax2.set_xlabel("Hours", color=self.TEXT_MUTED, fontsize=8)
        ax2.set_title("Time by category", fontsize=10, color=self.TEXT)
        for bar, val in zip(bars, cat_time.values):
            ax2.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
                     f"{val:.1f}h", va="center", color=self.TEXT_MUTED, fontsize=7)

        # ── Hourly score line ─────────────────────────────────────────────
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
        hourly = df.dropna(subset=["score"]).groupby("hour")["score"].mean()
        if not hourly.empty:
            ax3.plot(hourly.index, hourly.values,
                     color=self.ACCENT, linewidth=2, marker="o", markersize=4)
            ax3.fill_between(hourly.index, hourly.values,
                             alpha=0.15, color=self.ACCENT)
            ax3.set_ylim(0, 100)
            ax3.set_xlim(0, 23)
            ax3.set_xlabel("Hour of day", color=self.TEXT_MUTED, fontsize=8)
            ax3.set_ylabel("Avg score", color=self.TEXT_MUTED, fontsize=8)
        ax3.set_title("Hourly productivity", fontsize=10, color=self.TEXT)

        fig.tight_layout(pad=2)
        self._canvas_today.draw()

    # ────────────────────────────────────────────────────
    # TAB 3: WEEKLY CHARTS
    # ────────────────────────────────────────────────────

    def _build_tab_weekly(self):
        p = self._tab_weekly
        self._fig_weekly = Figure(figsize=(11, 5), facecolor=self.BG)
        self._canvas_weekly = FigureCanvasTkAgg(self._fig_weekly, master=p)
        self._canvas_weekly.get_tk_widget().pack(fill="both", expand=True,
                                                  padx=8, pady=8)

    def _draw_weekly_charts(self):
        fig = self._fig_weekly
        fig.clear()
        df = self.db.fetch_last_n_days(7)

        ax1 = fig.add_subplot(1, 2, 1)
        ax2 = fig.add_subplot(1, 2, 2)

        for ax in [ax1, ax2]:
            ax.set_facecolor(self.SURFACE)
            for spine in ax.spines.values():
                spine.set_edgecolor(self.BORDER)
            ax.tick_params(colors=self.TEXT_MUTED, labelsize=8)

        if df.empty:
            ax1.text(0.5, 0.5, "No data yet (tracking will populate this)",
                     ha="center", va="center",
                     color=self.TEXT_MUTED, transform=ax1.transAxes)
            self._canvas_weekly.draw()
            return

        # ── Daily productivity score trend ────────────────────────────────
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
        daily_score = df.dropna(subset=["score"]).groupby("date")["score"].mean()
        dates  = [d[-5:] for d in daily_score.index]  # MM-DD
        values = daily_score.values
        colors = [self.GREEN if v >= 65 else (self.YELLOW if v >= 35 else self.RED)
                  for v in values]
        ax1.bar(dates, values, color=colors, edgecolor=self.BG, linewidth=0.5)
        ax1.axhline(65, color=self.GREEN,  linestyle="--", linewidth=0.8, alpha=0.6)
        ax1.axhline(35, color=self.RED,    linestyle="--", linewidth=0.8, alpha=0.6)
        ax1.set_ylim(0, 100)
        ax1.set_ylabel("Avg score", color=self.TEXT_MUTED, fontsize=8)
        ax1.set_title("7-day productivity score", fontsize=10, color=self.TEXT)

        # ── Stacked bar: productive / neutral / unproductive mins per day ─
        daily_lbl = df.groupby(["date", "label"])["duration_sec"].sum().unstack(fill_value=0) / 60
        for col in ["Productive", "Neutral", "Unproductive"]:
            if col not in daily_lbl.columns:
                daily_lbl[col] = 0

        d_labels = [d[-5:] for d in daily_lbl.index]
        ax2.bar(d_labels, daily_lbl["Productive"],
                label="Productive",   color=self.GREEN,  edgecolor=self.BG, linewidth=0.3)
        ax2.bar(d_labels, daily_lbl["Neutral"],
                bottom=daily_lbl["Productive"],
                label="Neutral",      color=self.YELLOW, edgecolor=self.BG, linewidth=0.3)
        ax2.bar(d_labels, daily_lbl["Unproductive"],
                bottom=daily_lbl["Productive"] + daily_lbl["Neutral"],
                label="Unproductive", color=self.RED,    edgecolor=self.BG, linewidth=0.3)
        ax2.set_ylabel("Minutes", color=self.TEXT_MUTED, fontsize=8)
        ax2.set_title("Daily time breakdown", fontsize=10, color=self.TEXT)
        ax2.legend(fontsize=7, labelcolor=self.TEXT,
                   facecolor=self.SURFACE, edgecolor=self.BORDER)

        fig.tight_layout(pad=2)
        self._canvas_weekly.draw()

    # ────────────────────────────────────────────────────
    # TAB 4: ML ANALYSIS
    # ────────────────────────────────────────────────────

    def _build_tab_ml(self):
        p = self._tab_ml

        # Status bar at top
        self._ml_status_var = tk.StringVar(value="Loading ML engine…")
        tk.Label(p, textvariable=self._ml_status_var,
                 bg=self.BG, fg=self.TEXT_MUTED,
                 font=("Helvetica", 9)).pack(anchor="w", padx=16, pady=(8, 4))

        # Accuracy card
        acc_frame = tk.Frame(p, bg=self.SURFACE,
                             highlightthickness=1,
                             highlightbackground=self.BORDER)
        acc_frame.pack(fill="x", padx=16, pady=4)

        self._acc_var = tk.StringVar(value="—")
        tk.Label(acc_frame, text="Model accuracy",
                 bg=self.SURFACE, fg=self.TEXT_MUTED,
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=16, pady=8)
        tk.Label(acc_frame, textvariable=self._acc_var,
                 bg=self.SURFACE, fg=self.ACCENT,
                 font=("Helvetica", 20, "bold")).pack(side="left", padx=8)

        self._n_samples_var = tk.StringVar(value="")
        tk.Label(acc_frame, textvariable=self._n_samples_var,
                 bg=self.SURFACE, fg=self.TEXT_MUTED,
                 font=("Helvetica", 9)).pack(side="left", padx=8)

        # Retrain button
        tk.Button(acc_frame, text="Retrain model",
                  command=self._retrain,
                  bg=self.SURFACE2, fg=self.TEXT,
                  relief="flat", font=("Helvetica", 9),
                  padx=12, pady=3).pack(side="right", padx=12)

        # Export button
        tk.Button(acc_frame, text="Export today CSV",
                  command=self._export_csv,
                  bg=self.SURFACE2, fg=self.TEXT,
                  relief="flat", font=("Helvetica", 9),
                  padx=12, pady=3).pack(side="right", padx=4)

        # Charts row
        self._fig_ml = Figure(figsize=(11, 4.5), facecolor=self.BG)
        self._canvas_ml = FigureCanvasTkAgg(self._fig_ml, master=p)
        self._canvas_ml.get_tk_widget().pack(fill="both", expand=True,
                                              padx=8, pady=8)

    def _draw_ml_charts(self):
        if not self._ml_report:
            return
        fig = self._fig_ml
        fig.clear()

        ax1 = fig.add_subplot(1, 2, 1)
        ax2 = fig.add_subplot(1, 2, 2)

        for ax in [ax1, ax2]:
            ax.set_facecolor(self.SURFACE)
            for spine in ax.spines.values():
                spine.set_edgecolor(self.BORDER)
            ax.tick_params(colors=self.TEXT_MUTED, labelsize=8)
            ax.title.set_color(self.TEXT)

        # ── Feature importance bar ────────────────────────────────────────
        fi = self._ml_report.get("feature_imp", {})
        if fi:
            names  = list(fi.keys())
            values = list(fi.values())
            sorted_pairs = sorted(zip(values, names), reverse=True)
            sv, sn = zip(*sorted_pairs)
            bar_c = [self.ACCENT if v == max(sv) else self.SURFACE2 for v in sv]
            ax1.barh(sn, sv, color=bar_c, edgecolor=self.BG)
            ax1.set_xlabel("Importance", color=self.TEXT_MUTED, fontsize=8)
            ax1.set_title("Feature importance", fontsize=10)
            ax1.invert_yaxis()

        # ── Per-class precision/recall bars ───────────────────────────────
        report = self._ml_report.get("report", {})
        classes = ["Productive", "Neutral", "Unproductive"]
        existing = [c for c in classes if c in report]
        if existing:
            x     = np.arange(len(existing))
            prec  = [report[c]["precision"] * 100 for c in existing]
            rec   = [report[c]["recall"]    * 100 for c in existing]
            width = 0.35
            ax2.bar(x - width/2, prec, width, label="Precision",
                    color=self.ACCENT,  edgecolor=self.BG, alpha=0.9)
            ax2.bar(x + width/2, rec,  width, label="Recall",
                    color=self.YELLOW, edgecolor=self.BG, alpha=0.9)
            ax2.set_xticks(x)
            ax2.set_xticklabels(existing, fontsize=8, color=self.TEXT_MUTED)
            ax2.set_ylim(0, 110)
            ax2.set_ylabel("%", color=self.TEXT_MUTED, fontsize=8)
            ax2.set_title("Per-class precision & recall", fontsize=10)
            ax2.legend(fontsize=8, labelcolor=self.TEXT,
                       facecolor=self.SURFACE, edgecolor=self.BORDER)

        fig.tight_layout(pad=2)
        self._canvas_ml.draw()

    def _retrain(self):
        self._ml_status_var.set("Retraining…")
        def _do():
            self.ml.train()
        threading.Thread(target=_do, daemon=True).start()

    def _export_csv(self):
        df = self.db.fetch_today()
        df.to_csv(REPORT_PATH, index=False)
        messagebox.showinfo("Exported", f"Today's report saved to:\n{REPORT_PATH}")

    # ────────────────────────────────────────────────────
    # CHART REFRESH LOOP
    # ────────────────────────────────────────────────────

    def _refresh_charts(self):
        self._draw_today_charts()
        self._draw_weekly_charts()
        self._draw_ml_charts()
        self._refresh_feed()
        self._update_today_stats()

    def _start_chart_refresh(self):
        def _loop():
            self._refresh_charts()
            self.after(CHART_REFRESH * 1000, _loop)
        self.after(3000, _loop)

    # ────────────────────────────────────────────────────
    # EVENT QUEUE POLLING (bridges threads → UI)
    # ────────────────────────────────────────────────────

    def _start_queue_poll(self):
        self._poll_queue()

    def _poll_queue(self):
        try:
            while True:
                event, data = self.queue.get_nowait()

                if event == "session":
                    self._current_app = data.get("app_name", "—")
                    title = data.get("window_title", "")
                    self._app_label.configure(text=self._current_app[:40])
                    self._title_label.configure(text=title[:60])
                    self._status_var.set(
                        f"Tracking · last event {datetime.datetime.now().strftime('%H:%M:%S')}")

                elif event == "score":
                    score, label = data
                    self._update_score_display(score, label)
                    self._update_today_stats()

                elif event == "ml_status":
                    self._ml_status_var.set(data)
                    self._status_var.set(f"ML: {data}")

                elif event == "ml_report":
                    self._ml_report = data
                    acc = data.get("accuracy", 0)
                    n   = data.get("n_samples", 0)
                    self._acc_var.set(f"{acc}%")
                    self._n_samples_var.set(f"trained on {n:,} sessions")
                    self._draw_ml_charts()

                elif event == "error":
                    self._status_var.set(f"Error: {str(data)[:60]}")

        except queue.Empty:
            pass
        self.after(500, self._poll_queue)

    def on_close(self):
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("="*55)
    print("  ML Productivity Tracker — Desktop App")
    print("="*55)
    print(f"  Database : {DB_PATH}")
    print(f"  Model    : {MODEL_PATH}")
    print(f"  CSV      : {CSV_PATH}")
    print()

    # Check CSV exists; warn if not
    if not os.path.exists(CSV_PATH):
        print(f"  WARNING: {CSV_PATH} not found.")
        print("  Run generate_data.py first to create synthetic training data.")
        print()

    # Shared event queue (thread → UI)
    event_q = queue.Queue()

    # Initialise modules
    db = Database(DB_PATH)
    ml = MLEngine(db, event_q)

    # Start background threads
    collector = ActivityCollector(db, event_q)
    collector.start()
    ml.start()

    # Launch GUI
    app = ProductivityApp(db, ml, event_q)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    print("  Dashboard launched. Close window to exit.")
    app.mainloop()

    # Cleanup
    collector.stop()
    ml.stop()
    print("  Stopped. Goodbye.")


if __name__ == "__main__":
    main()
