# Freelance Time Tracker

A dark-themed desktop time tracker built with Python + Tkinter, with cloud sync via Supabase and PDF export for client billing.

---

## Features

| Feature | Description |
|---|---|
| **Timer** | Start/stop with one click — saves date, start, end, duration automatically |
| **Resume Last Job** | Restore the previous session's label, color, and elapsed time — picks up exactly where you left off, even after a crash or accidental close |
| **Labels & Color Tags** | Tag sessions by project/client with 8 color codes |
| **Add Entry** | Manually log time for a past session via the **+ Add Entry** button in the Time Log |
| **Edit Entries** | Double-click any row to correct times or labels after the fact |
| **Pull Hours** | Export all sessions to a clean, client-ready PDF time report |
| **Create Invoice** | Select a label + hourly rate → generates a professional invoice PDF |
| **Supabase Sync** | Automatic cloud backup; offline-first with pending-sync on reconnect |
| **Animated UI** | Particle stream header, pulsing timer, corner bracket decorations |

---

## Quick Start

### Run from source

```bash
pip install -r requirements.txt
python timetracker.py
```

### Build a standalone Windows .exe

```bat
build.bat
```

The executable is output to `dist\TimeTracker.exe` — single file, no Python install needed.

### Build a macOS .app

```bash
chmod +x build_mac.sh
./build_mac.sh
```

The `.app` bundle is output to `dist/TimeTracker.app`.

---

## Requirements

- Python 3.9+
- `supabase` — cloud sync (optional; app works fully offline without it)
- `reportlab` — PDF export
- `pyinstaller` — only needed to build the executable

Install all:
```bash
pip install -r requirements.txt
```

---

## Supabase Cloud Sync (optional)

Enables automatic backup and is the shared backend for the future Flutter mobile app.

### One-time setup

1. Create a free project at [supabase.com](https://supabase.com)
2. Open the **SQL Editor** and run the schema at the top of `timetracker.py`
3. In the app, click **⚙** → paste your **Project URL** and **Anon Key** → Save & Test
4. The sync dot (●) in the header turns green when connected

### Sync behavior

| State | Dot color | Meaning |
|---|---|---|
| Not configured | dim grey | No URL/key entered |
| Syncing | yellow | Push in progress |
| Synced | green | All entries backed up |
| Error | red | Connection failed (entries saved locally) |

Entries saved while offline are automatically pushed on next launch.

---

## PDF Export

### Pull Hours

Exports **all** time entries to a formatted PDF:

- Includes: Date, Start, End, Duration, Label, Notes
- Summary line: total sessions + billable hours
- Saved to your Desktop

### Create Invoice

Click **Create Invoice** → fill in:

| Field | Required | Notes |
|---|---|---|
| Project / Client | Yes | Dropdown of all used labels |
| Hourly Rate | Yes | Decimal (e.g. `75.00`) |
| Your Name | No | Appears in "From" section |
| Client Name | No | Appears in "Bill To" |
| Invoice # | No | Auto-generates from today's date |

Generates an itemized invoice with per-session line items and a bold **Amount Due** total. Saved to your Desktop.

---

## Data

All data is stored locally in `timetracker.db` (SQLite, WAL mode).
`config.json` stores your Supabase credentials and resume state — excluded from git.

### Resume state

When you stop a timer or close the app mid-session, the current job's elapsed time, label, comment, and color tag are written to `config.json` under a `"resume"` key. On the next launch the **⏎ RESUME LAST JOB** button becomes active — clicking it restores all fields and continues the timer from where it left off. Accidental closes do **not** save a partial entry to the log; the time is only committed once you hit **STOP** after resuming.

---

## Mobile (Android / iOS)

The Python/Tkinter desktop app cannot run on mobile. The roadmap is:

1. **Flutter** app (Dart) — single codebase for Android, iOS, macOS, Windows, Linux
2. Uses the **same Supabase backend** — data syncs across all devices
3. Flutter scaffold is in `timetracker_flutter/`

See [`timetracker_flutter/README.md`](timetracker_flutter/README.md) to get started.

---

## License

MIT
