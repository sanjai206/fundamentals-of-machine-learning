"""
ML Productivity Tracker — Phase 1
Synthetic Activity Data Generator

Generates realistic laptop activity logs (apps + browser)
Output: activity_logs.csv  (~10,000+ rows, 30 days)

Run:
    python generate_data.py

Author: Your project
"""

import csv
import random
from datetime import datetime, timedelta

# ──────────────────────────────────────────────
# 1. APP / URL PROFILES
#    Each entry: (app_name, window_title, url, category, label, avg_duration_sec)
# ──────────────────────────────────────────────

APP_PROFILES = [
    # Coding / Dev
    {"app": "Code.exe",        "title": "Visual Studio Code",         "url": "",                          "category": "Coding",         "label": "Productive",   "avg_dur": 900,  "weight": 14},
    {"app": "Code.exe",        "title": "main.py - VS Code",          "url": "",                          "category": "Coding",         "label": "Productive",   "avg_dur": 720,  "weight": 10},
    {"app": "Terminal",        "title": "bash — ~/projects",          "url": "",                          "category": "Coding",         "label": "Productive",   "avg_dur": 300,  "weight": 8},
    {"app": "PyCharm64.exe",   "title": "PyCharm — ml_tracker",       "url": "",                          "category": "Coding",         "label": "Productive",   "avg_dur": 840,  "weight": 6},
    {"app": "Postman.exe",     "title": "Postman — API Testing",      "url": "",                          "category": "Coding",         "label": "Productive",   "avg_dur": 240,  "weight": 4},
    {"app": "DBeaver.exe",     "title": "DBeaver — activity.db",      "url": "",                          "category": "Coding",         "label": "Productive",   "avg_dur": 300,  "weight": 3},

    # Learning
    {"app": "chrome.exe",      "title": "Coursera — Machine Learning", "url": "coursera.org",             "category": "Learning",       "label": "Productive",   "avg_dur": 1200, "weight": 8},
    {"app": "chrome.exe",      "title": "Stack Overflow",              "url": "stackoverflow.com",        "category": "Learning",       "label": "Productive",   "avg_dur": 180,  "weight": 9},
    {"app": "chrome.exe",      "title": "GitHub",                      "url": "github.com",               "category": "Learning",       "label": "Productive",   "avg_dur": 240,  "weight": 7},
    {"app": "chrome.exe",      "title": "Medium — Python Articles",    "url": "medium.com",               "category": "Learning",       "label": "Productive",   "avg_dur": 300,  "weight": 5},
    {"app": "chrome.exe",      "title": "MDN Web Docs",                "url": "developer.mozilla.org",    "category": "Learning",       "label": "Productive",   "avg_dur": 200,  "weight": 4},
    {"app": "Notion.exe",      "title": "Notion — Study Notes",       "url": "",                          "category": "Learning",       "label": "Productive",   "avg_dur": 600,  "weight": 6},

    # Communication (Neutral)
    {"app": "Slack.exe",       "title": "Slack — #general",           "url": "",                          "category": "Communication",  "label": "Neutral",      "avg_dur": 120,  "weight": 8},
    {"app": "Slack.exe",       "title": "Slack — #dev-team",          "url": "",                          "category": "Communication",  "label": "Neutral",      "avg_dur": 90,   "weight": 6},
    {"app": "chrome.exe",      "title": "Gmail — Inbox",               "url": "mail.google.com",          "category": "Communication",  "label": "Neutral",      "avg_dur": 180,  "weight": 7},
    {"app": "Zoom.exe",        "title": "Zoom Meeting",               "url": "",                          "category": "Communication",  "label": "Neutral",      "avg_dur": 1800, "weight": 4},
    {"app": "Teams.exe",       "title": "Microsoft Teams",            "url": "",                          "category": "Communication",  "label": "Neutral",      "avg_dur": 900,  "weight": 3},

    # Docs / Planning (Neutral)
    {"app": "chrome.exe",      "title": "Google Docs — Report",       "url": "docs.google.com",          "category": "Documents",      "label": "Neutral",      "avg_dur": 480,  "weight": 5},
    {"app": "chrome.exe",      "title": "Google Sheets — Data",       "url": "sheets.google.com",        "category": "Documents",      "label": "Neutral",      "avg_dur": 360,  "weight": 4},
    {"app": "WINWORD.EXE",     "title": "Word — project_plan.docx",   "url": "",                          "category": "Documents",      "label": "Neutral",      "avg_dur": 420,  "weight": 4},
    {"app": "Trello.exe",      "title": "Trello — Sprint Board",      "url": "",                          "category": "Documents",      "label": "Neutral",      "avg_dur": 180,  "weight": 3},

    # Entertainment (Unproductive)
    {"app": "chrome.exe",      "title": "YouTube — Gaming Videos",    "url": "youtube.com",              "category": "Entertainment",  "label": "Unproductive", "avg_dur": 600,  "weight": 8},
    {"app": "chrome.exe",      "title": "Netflix",                    "url": "netflix.com",              "category": "Entertainment",  "label": "Unproductive", "avg_dur": 1800, "weight": 4},
    {"app": "Spotify.exe",     "title": "Spotify — Music",            "url": "",                          "category": "Entertainment",  "label": "Neutral",      "avg_dur": 900,  "weight": 5},
    {"app": "VLC.exe",         "title": "VLC — Movie",                "url": "",                          "category": "Entertainment",  "label": "Unproductive", "avg_dur": 5400, "weight": 2},

    # Social Media (Unproductive)
    {"app": "chrome.exe",      "title": "Twitter / X",                "url": "twitter.com",              "category": "Social Media",   "label": "Unproductive", "avg_dur": 240,  "weight": 7},
    {"app": "chrome.exe",      "title": "Reddit — r/programming",     "url": "reddit.com",               "category": "Social Media",   "label": "Unproductive", "avg_dur": 360,  "weight": 7},
    {"app": "chrome.exe",      "title": "Instagram Web",              "url": "instagram.com",            "category": "Social Media",   "label": "Unproductive", "avg_dur": 300,  "weight": 5},
    {"app": "chrome.exe",      "title": "LinkedIn — Feed",            "url": "linkedin.com",             "category": "Social Media",   "label": "Neutral",      "avg_dur": 180,  "weight": 4},
    {"app": "chrome.exe",      "title": "WhatsApp Web",               "url": "web.whatsapp.com",         "category": "Communication",  "label": "Neutral",      "avg_dur": 150,  "weight": 5},

    # System / Idle
    {"app": "explorer.exe",    "title": "File Explorer",              "url": "",                          "category": "System",         "label": "Neutral",      "avg_dur": 90,   "weight": 4},
    {"app": "IDLE",            "title": "Screen Lock / Idle",         "url": "",                          "category": "Idle",           "label": "Neutral",      "avg_dur": 600,  "weight": 6},
    {"app": "Settings.exe",    "title": "Windows Settings",           "url": "",                          "category": "System",         "label": "Neutral",      "avg_dur": 60,   "weight": 2},
]


# ──────────────────────────────────────────────
# 2. TIME-OF-DAY PRODUCTIVITY BIAS
#    More productive in morning, distracted in afternoon
# ──────────────────────────────────────────────

def get_hour_weight(hour):
    """Return a multiplier for productive vs unproductive activity by hour."""
    if 8 <= hour <= 11:    # Morning focus
        return {"productive_bias": 0.65, "distraction_bias": 0.10}
    elif 12 <= hour <= 13: # Lunch slump
        return {"productive_bias": 0.25, "distraction_bias": 0.40}
    elif 14 <= hour <= 16: # Afternoon dip
        return {"productive_bias": 0.40, "distraction_bias": 0.30}
    elif 17 <= hour <= 19: # Evening work
        return {"productive_bias": 0.50, "distraction_bias": 0.20}
    elif 20 <= hour <= 23: # Night browsing
        return {"productive_bias": 0.20, "distraction_bias": 0.50}
    else:                  # Early morning / very late
        return {"productive_bias": 0.10, "distraction_bias": 0.60}


# ──────────────────────────────────────────────
# 3. CORE GENERATOR
# ──────────────────────────────────────────────

def generate_sessions(num_days=365, seed=42):
    """
    Simulate 30 days of laptop usage.
    Returns a list of session dicts.
    """
    random.seed(seed)
    sessions = []

    start_date = datetime(2024, 9, 1, 8, 0, 0)  # Start: Sep 1 2024, 8 AM

    for day in range(num_days):
        current_day = start_date + timedelta(days=day)

        # Skip some weekends (realistic)
        if current_day.weekday() in [5, 6]:
            if random.random() < 0.55:  # 55% chance to skip weekend
                continue

        # Randomize work start time: 7:30 AM to 9:30 AM
        work_start_hour = random.randint(7, 9)
        work_start_min  = random.randint(0, 59)
        current_time    = current_day.replace(hour=work_start_hour, minute=work_start_min, second=0)

        # Each day: 5 to 10 hours of screen time
        total_screen_seconds = random.randint(5 * 3600, 10 * 3600)
        day_elapsed = 0

        while day_elapsed < total_screen_seconds:
            hour = current_time.hour
            bias = get_hour_weight(hour)

            # Pick an app weighted by category + time bias
            weights = []
            for p in APP_PROFILES:
                w = p["weight"]
                if p["label"] == "Productive":
                    w *= (1 + bias["productive_bias"])
                elif p["label"] == "Unproductive":
                    w *= (1 + bias["distraction_bias"])
                weights.append(w)

            profile = random.choices(APP_PROFILES, weights=weights, k=1)[0]

            # Duration: log-normal around avg_dur (natural variation)
            sigma = 0.6
            raw_dur = int(random.lognormvariate(0, sigma) * profile["avg_dur"])
            duration = max(10, min(raw_dur, 7200))  # clamp 10s – 2h

            # Idle: higher chance if previous session was long
            idle_prob = 0.08 if duration < 300 else 0.20
            is_idle = profile["category"] == "Idle" or random.random() < idle_prob

            # Keyboard/mouse activity (approx)
            if is_idle:
                keystrokes = 0
                mouse_clicks = 0
            else:
                keystrokes   = random.randint(5, 300) if duration < 120 else random.randint(50, 1200)
                mouse_clicks = random.randint(2, 50)  if duration < 120 else random.randint(20, 200)

            session = {
                "timestamp":    current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "date":         current_time.strftime("%Y-%m-%d"),
                "hour":         current_time.hour,
                "day_of_week":  current_time.strftime("%A"),
                "app_name":     profile["app"],
                "window_title": profile["title"],
                "url":          profile["url"],
                "category":     profile["category"],
                "label":        profile["label"],
                "duration_sec": duration,
                "is_idle":      int(is_idle),
                "keystrokes":   keystrokes,
                "mouse_clicks": mouse_clicks,
            }

            sessions.append(session)

            # Advance time
            current_time += timedelta(seconds=duration + random.randint(0, 15))
            day_elapsed  += duration

            # Random short break (bathroom, coffee) — 5% chance
            if random.random() < 0.05:
                break_seconds = random.randint(180, 900)
                current_time += timedelta(seconds=break_seconds)
                day_elapsed  += break_seconds

    return sessions


# ──────────────────────────────────────────────
# 4. SAVE TO CSV
# ──────────────────────────────────────────────

def save_to_csv(sessions, filepath="activity_logs.csv"):
    if not sessions:
        print("No sessions generated!")
        return

    fieldnames = list(sessions[0].keys())

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sessions)

    print(f"Saved {len(sessions):,} rows → {filepath}")


# ──────────────────────────────────────────────
# 5. QUICK STATS SUMMARY
# ──────────────────────────────────────────────

def print_summary(sessions):
    from collections import Counter

    total = len(sessions)
    labels = Counter(s["label"]    for s in sessions)
    cats   = Counter(s["category"] for s in sessions)
    apps   = Counter(s["app_name"] for s in sessions)
    days   = len(set(s["date"]     for s in sessions))

    total_hrs = sum(s["duration_sec"] for s in sessions) / 3600

    print("\n" + "="*50)
    print("  SYNTHETIC DATA SUMMARY")
    print("="*50)
    print(f"  Total sessions : {total:,}")
    print(f"  Days covered   : {days}")
    print(f"  Total hours    : {total_hrs:.1f} hrs")
    print()
    print("  Label distribution:")
    for lbl, cnt in labels.most_common():
        pct = cnt / total * 100
        print(f"    {lbl:<15} {cnt:>5,}  ({pct:.1f}%)")
    print()
    print("  Top categories:")
    for cat, cnt in cats.most_common(5):
        print(f"    {cat:<15} {cnt:>5,}")
    print()
    print("  Top apps:")
    for app, cnt in apps.most_common(5):
        print(f"    {app:<20} {cnt:>5,}")
    print("="*50)


# ──────────────────────────────────────────────
# 6. ENTRY POINT
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating synthetic activity data...")
    sessions = generate_sessions(num_days=30, seed=42)
    print_summary(sessions)
    save_to_csv(sessions, "activity_logs.csv")
    print("\nDone! Next step: Phase 2 — load into SQLite database.")