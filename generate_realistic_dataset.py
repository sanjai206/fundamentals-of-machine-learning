import csv
import datetime as dt
import math
import random
from pathlib import Path


OUTPUT_PATH = Path("activity_logs_realistic.csv")
ROW_COUNT = 6000
SEED = 42


APP_PROFILES = [
    {
        "app_name": "chrome.exe",
        "category": "Learning",
        "titles": [
            "Python docs - async IO",
            "MDN Web Docs - Fetch API",
            "Coursera - Machine Learning",
            "Kaggle Notebook - Feature engineering",
            "Internal wiki - deployment checklist",
        ],
        "urls": [
            "docs.python.org",
            "developer.mozilla.org",
            "coursera.org",
            "kaggle.com",
            "wiki.company.local",
        ],
        "base": 12,
    },
    {
        "app_name": "chrome.exe",
        "category": "Social Media",
        "titles": [
            "Reddit - programming thread",
            "LinkedIn feed",
            "X - timeline",
            "YouTube - conference talk",
            "Instagram - messages",
        ],
        "urls": [
            "reddit.com",
            "linkedin.com",
            "x.com",
            "youtube.com",
            "instagram.com",
        ],
        "base": -15,
    },
    {
        "app_name": "PyCharm64.exe",
        "category": "Coding",
        "titles": [
            "PyCharm - ml tracker",
            "PyCharm - failing tests",
            "PyCharm - refactor auth module",
            "PyCharm - exploratory notebook",
        ],
        "urls": [""],
        "base": 14,
    },
    {
        "app_name": "Code.exe",
        "category": "Coding",
        "titles": [
            "VS Code - api server",
            "VS Code - bugfix branch",
            "VS Code - writing unit tests",
            "VS Code - reviewing logs",
        ],
        "urls": [""],
        "base": 13,
    },
    {
        "app_name": "Terminal",
        "category": "Coding",
        "titles": [
            "PowerShell - pytest",
            "PowerShell - docker compose logs",
            "PowerShell - git rebase",
            "PowerShell - data cleanup",
        ],
        "urls": [""],
        "base": 10,
    },
    {
        "app_name": "Slack.exe",
        "category": "Communication",
        "titles": [
            "Slack - release war room",
            "Slack - #dev-team",
            "Slack - support escalations",
            "Slack - planning thread",
        ],
        "urls": [""],
        "base": -2,
    },
    {
        "app_name": "Teams.exe",
        "category": "Communication",
        "titles": [
            "Teams meeting - sprint sync",
            "Teams meeting - customer call",
            "Teams chat - handoff",
            "Teams - interview panel",
        ],
        "urls": [""],
        "base": -1,
    },
    {
        "app_name": "Zoom.exe",
        "category": "Communication",
        "titles": [
            "Zoom - architecture review",
            "Zoom - workshop",
            "Zoom - all hands",
            "Zoom - pair debugging",
        ],
        "urls": [""],
        "base": -3,
    },
    {
        "app_name": "Notion.exe",
        "category": "Documents",
        "titles": [
            "Notion - weekly plan",
            "Notion - project notes",
            "Notion - retrospective",
            "Notion - personal reading list",
        ],
        "urls": [""],
        "base": 4,
    },
    {
        "app_name": "WINWORD.EXE",
        "category": "Documents",
        "titles": [
            "Word - PRD draft",
            "Word - incident postmortem",
            "Word - personal notes",
            "Word - requirements review",
        ],
        "urls": [""],
        "base": 2,
    },
    {
        "app_name": "EXCEL.EXE",
        "category": "Documents",
        "titles": [
            "Excel - sprint metrics",
            "Excel - budget tracker",
            "Excel - ad hoc analysis",
            "Excel - backlog exports",
        ],
        "urls": [""],
        "base": 1,
    },
    {
        "app_name": "DBeaver.exe",
        "category": "Coding",
        "titles": [
            "DBeaver - query tuning",
            "DBeaver - production readonly checks",
            "DBeaver - schema diff",
            "DBeaver - data validation",
        ],
        "urls": [""],
        "base": 8,
    },
    {
        "app_name": "Spotify.exe",
        "category": "Entertainment",
        "titles": [
            "Spotify - focus playlist",
            "Spotify - podcast",
            "Spotify - music discovery",
            "Spotify - ambient mix",
        ],
        "urls": [""],
        "base": -6,
    },
    {
        "app_name": "VLC.exe",
        "category": "Entertainment",
        "titles": [
            "VLC - recorded training",
            "VLC - movie clip",
            "VLC - conference session",
            "VLC - webinar replay",
        ],
        "urls": [""],
        "base": -5,
    },
    {
        "app_name": "Explorer.exe",
        "category": "System",
        "titles": [
            "Explorer - project folder",
            "Explorer - downloads cleanup",
            "Explorer - screenshots",
            "Explorer - logs bundle",
        ],
        "urls": [""],
        "base": -4,
    },
    {
        "app_name": "Settings.exe",
        "category": "System",
        "titles": [
            "Settings - audio devices",
            "Settings - network issue",
            "Settings - updates",
            "Settings - display setup",
        ],
        "urls": [""],
        "base": -8,
    },
    {
        "app_name": "Postman.exe",
        "category": "Coding",
        "titles": [
            "Postman - auth endpoints",
            "Postman - regression suite",
            "Postman - exploratory API checks",
            "Postman - payload validation",
        ],
        "urls": [""],
        "base": 7,
    },
    {
        "app_name": "IDLE",
        "category": "Idle",
        "titles": [
            "Screen Lock / Idle",
            "Away from keyboard",
            "Lunch break",
            "Context switch pause",
        ],
        "urls": [""],
        "base": -18,
    },
]


SCENARIOS = [
    {"name": "deep_work", "weight": 17, "focus": 16, "switch": -6, "meeting": -8, "idle": -10},
    {"name": "debugging", "weight": 12, "focus": 9, "switch": -2, "meeting": -5, "idle": -8},
    {"name": "research", "weight": 12, "focus": 8, "switch": -1, "meeting": -6, "idle": -10},
    {"name": "planning", "weight": 9, "focus": 4, "switch": -1, "meeting": -2, "idle": -6},
    {"name": "admin", "weight": 8, "focus": -4, "switch": -1, "meeting": 2, "idle": -4},
    {"name": "meeting_heavy", "weight": 10, "focus": -3, "switch": -3, "meeting": 8, "idle": -5},
    {"name": "support_firefight", "weight": 8, "focus": 3, "switch": -7, "meeting": 1, "idle": -8},
    {"name": "learning_block", "weight": 10, "focus": 7, "switch": -2, "meeting": -5, "idle": -7},
    {"name": "break_time", "weight": 7, "focus": -10, "switch": 2, "meeting": -2, "idle": 3},
    {"name": "low_energy", "weight": 7, "focus": -8, "switch": -2, "meeting": -3, "idle": 5},
]


DAY_WEIGHTS = {
    0: 1.05,
    1: 1.08,
    2: 1.0,
    3: 1.0,
    4: 0.95,
    5: 0.72,
    6: 0.68,
}


def weighted_choice(rng, items, weight_key="weight"):
    total = sum(item[weight_key] for item in items)
    pick = rng.uniform(0, total)
    upto = 0
    for item in items:
        upto += item[weight_key]
        if upto >= pick:
            return item
    return items[-1]


def truncated_gauss(rng, mean, stddev, low, high):
    for _ in range(12):
        value = rng.gauss(mean, stddev)
        if low <= value <= high:
            return value
    return min(high, max(low, value))


def choose_profile(rng, scenario_name):
    weights = []
    for profile in APP_PROFILES:
        weight = 1.0
        cat = profile["category"]
        if scenario_name in {"deep_work", "debugging"} and cat == "Coding":
            weight *= 5.0
        if scenario_name == "research" and cat in {"Learning", "Coding"}:
            weight *= 3.4
        if scenario_name == "planning" and cat in {"Documents", "Communication"}:
            weight *= 3.0
        if scenario_name == "admin" and cat in {"Documents", "System", "Communication"}:
            weight *= 3.2
        if scenario_name == "meeting_heavy" and cat == "Communication":
            weight *= 5.5
        if scenario_name == "support_firefight" and cat in {"Communication", "Coding", "System"}:
            weight *= 3.0
        if scenario_name == "learning_block" and cat == "Learning":
            weight *= 5.0
        if scenario_name == "break_time" and cat in {"Entertainment", "Idle", "Social Media"}:
            weight *= 5.0
        if scenario_name == "low_energy" and cat in {"Idle", "Entertainment", "Social Media"}:
            weight *= 3.5
        weights.append(weight)

    total = sum(weights)
    pick = rng.uniform(0, total)
    upto = 0
    for profile, weight in zip(APP_PROFILES, weights):
        upto += weight
        if upto >= pick:
            return profile
    return APP_PROFILES[-1]


def context_switch_penalty(duration_sec):
    if duration_sec < 90:
        return -12
    if duration_sec < 240:
        return -6
    if duration_sec > 3600:
        return -2
    return 0


def interaction_score(keystrokes, mouse_clicks, duration_sec):
    intensity = (keystrokes + mouse_clicks * 2) / max(duration_sec / 60.0, 1.0)
    if intensity < 2:
        return -7
    if intensity < 6:
        return -2
    if intensity < 25:
        return 5
    if intensity < 70:
        return 8
    return 2


def hour_effect(hour):
    if 9 <= hour <= 11:
        return 5
    if 13 <= hour <= 16:
        return 4
    if 7 <= hour <= 8 or 17 <= hour <= 19:
        return 1
    return -4


def meeting_penalty(title, category):
    lower = title.lower()
    if "meeting" in lower or "call" in lower or "sync" in lower or "review" in lower:
        return -4 if category != "Communication" else 2
    return 0


def derive_label(score):
    if score >= 18:
        return "Productive"
    if score <= -8:
        return "Unproductive"
    return "Neutral"


def build_row(rng, index, timestamp):
    scenario = weighted_choice(rng, SCENARIOS)
    profile = choose_profile(rng, scenario["name"])
    title = rng.choice(profile["titles"])
    url = rng.choice(profile["urls"])
    hour = timestamp.hour
    day_idx = timestamp.weekday()

    if profile["category"] == "Idle":
        duration_sec = int(truncated_gauss(rng, 480, 360, 60, 3600))
        keystrokes = 0
        mouse_clicks = 0
        is_idle = 1
    elif profile["category"] == "Communication":
        duration_sec = int(truncated_gauss(rng, 900, 700, 60, 5400))
        is_idle = 1 if rng.random() < 0.22 else 0
        keystrokes = max(0, int(truncated_gauss(rng, 170 if "chat" in title.lower() else 55, 120, 0, 1300)))
        mouse_clicks = max(0, int(truncated_gauss(rng, 35 if is_idle else 90, 60, 0, 500)))
    elif profile["category"] in {"Coding", "Learning"}:
        duration_sec = int(truncated_gauss(rng, 1200, 900, 45, 7200))
        is_idle = 1 if rng.random() < 0.08 else 0
        keystrokes = max(0, int(truncated_gauss(rng, 260 if profile["category"] == "Coding" else 90, 220, 0, 2200)))
        mouse_clicks = max(0, int(truncated_gauss(rng, 85, 65, 0, 900)))
    elif profile["category"] == "Documents":
        duration_sec = int(truncated_gauss(rng, 700, 500, 45, 5400))
        is_idle = 1 if rng.random() < 0.12 else 0
        keystrokes = max(0, int(truncated_gauss(rng, 120, 110, 0, 1500)))
        mouse_clicks = max(0, int(truncated_gauss(rng, 70, 55, 0, 700)))
    elif profile["category"] in {"Entertainment", "Social Media"}:
        duration_sec = int(truncated_gauss(rng, 540, 520, 30, 5400))
        is_idle = 1 if rng.random() < 0.2 else 0
        keystrokes = max(0, int(truncated_gauss(rng, 40, 80, 0, 900)))
        mouse_clicks = max(0, int(truncated_gauss(rng, 55, 65, 0, 850)))
    else:
        duration_sec = int(truncated_gauss(rng, 420, 350, 30, 3600))
        is_idle = 1 if rng.random() < 0.18 else 0
        keystrokes = max(0, int(truncated_gauss(rng, 35, 55, 0, 700)))
        mouse_clicks = max(0, int(truncated_gauss(rng, 45, 50, 0, 500)))

    if scenario["name"] == "support_firefight":
        duration_sec = int(duration_sec * rng.uniform(0.45, 1.15))
        mouse_clicks = int(mouse_clicks * rng.uniform(1.0, 1.8))
    if scenario["name"] == "deep_work":
        duration_sec = int(duration_sec * rng.uniform(1.1, 1.8))
        keystrokes = int(keystrokes * rng.uniform(1.0, 1.7))
    if scenario["name"] == "break_time":
        duration_sec = int(duration_sec * rng.uniform(0.4, 1.2))
        keystrokes = int(keystrokes * rng.uniform(0.0, 0.6))

    duration_sec = max(30, min(7200, duration_sec))
    keystrokes = max(0, min(2500, keystrokes))
    mouse_clicks = max(0, min(1200, mouse_clicks))

    score = 0.0
    score += profile["base"]
    score += scenario["focus"]
    score += hour_effect(hour)
    score += context_switch_penalty(duration_sec)
    score += interaction_score(keystrokes, mouse_clicks, duration_sec)
    score += meeting_penalty(title, profile["category"])
    score += scenario["meeting"] if profile["category"] == "Communication" else 0
    score += scenario["idle"] if is_idle else 0
    score += (DAY_WEIGHTS[day_idx] - 1.0) * 10

    if profile["category"] == "Learning" and is_idle and duration_sec > 1500:
        score -= 14
    if profile["category"] == "Learning" and keystrokes < 20 and mouse_clicks < 20 and duration_sec > 2200:
        score -= 12
    if profile["category"] == "Coding" and duration_sec < 180:
        score -= 8
    if profile["category"] == "Coding" and scenario["name"] in {"low_energy", "support_firefight"} and keystrokes < 40:
        score -= 11
    if profile["category"] == "Communication" and ("pair debugging" in title.lower() or "war room" in title.lower()):
        score += 10
    if profile["category"] == "Communication" and duration_sec > 2400 and keystrokes < 15:
        score -= 6
    if profile["category"] == "Documents" and scenario["name"] == "admin" and duration_sec > 1500:
        score -= 8
    if profile["category"] == "Entertainment" and any(term in title.lower() for term in ["training", "conference", "webinar", "focus playlist"]):
        score += 11
    if profile["category"] == "Social Media" and url == "reddit.com" and scenario["name"] in {"research", "debugging"}:
        score += 8
    if profile["category"] == "System" and "network issue" in title.lower():
        score += 5
    if url == "youtube.com" and "conference" in title.lower():
        score += 9
    if url == "linkedin.com" and scenario["name"] in {"research", "planning"}:
        score += 6
    if profile["category"] == "Entertainment" and "focus playlist" in title.lower():
        score += 10
    if profile["category"] == "Documents" and duration_sec > 1800 and keystrokes > 150:
        score += 8
    if profile["category"] == "Coding" and is_idle:
        score -= 7
    if profile["category"] == "Idle" and duration_sec > 1800:
        score -= 8
    if profile["category"] == "Idle" and duration_sec < 300:
        score += 8

    score += rng.gauss(0, 10.5)
    label = derive_label(score)

    return {
        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "date": timestamp.date().isoformat(),
        "hour": timestamp.hour,
        "day_of_week": timestamp.strftime("%A"),
        "app_name": profile["app_name"],
        "window_title": title,
        "url": url,
        "category": profile["category"],
        "label": label,
        "duration_sec": duration_sec,
        "is_idle": is_idle,
        "keystrokes": keystrokes,
        "mouse_clicks": mouse_clicks,
        "scenario": scenario["name"],
        "latent_score": round(score, 2),
        "session_id": index + 1,
    }


def generate_dataset():
    rng = random.Random(SEED)
    start = dt.datetime(2025, 1, 1, 6, 30, 0)
    rows = []
    current = start

    for index in range(ROW_COUNT):
        day_offset = index // 65
        base_date = start + dt.timedelta(days=day_offset)

        active_hours = [7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 19, 21]
        hour = rng.choice(active_hours)
        minute = rng.randint(0, 59)
        second = rng.randint(0, 59)
        timestamp = base_date.replace(hour=hour, minute=minute, second=second)

        # Preserve some local temporal continuity.
        if rows and rng.random() < 0.35:
            previous = dt.datetime.strptime(rows[-1]["timestamp"], "%Y-%m-%d %H:%M:%S")
            timestamp = previous + dt.timedelta(seconds=rng.randint(45, 2400))

        current = timestamp
        rows.append(build_row(rng, index, current))

    fieldnames = [
        "timestamp",
        "date",
        "hour",
        "day_of_week",
        "app_name",
        "window_title",
        "url",
        "category",
        "label",
        "duration_sec",
        "is_idle",
        "keystrokes",
        "mouse_clicks",
        "scenario",
        "latent_score",
        "session_id",
    ]

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    generate_dataset()
