# TimeTracker Flutter

Flutter mobile/desktop companion to the Python desktop app.
Uses the **same Supabase backend** — entries sync across all devices.

## Prerequisites

| Tool | Install |
|---|---|
| Flutter SDK | https://docs.flutter.dev/get-started/install |
| Android Studio | For Android builds + emulator |
| Xcode (macOS only) | For iOS builds |
| VS Code or Android Studio | IDE |

## Setup

1. **Add Supabase credentials** in `lib/main.dart`:
   ```dart
   const _supabaseUrl = 'https://xxxx.supabase.co';
   const _supabaseKey = 'your-anon-key';
   ```

2. **Install dependencies**:
   ```bash
   flutter pub get
   ```

3. **Run** on a connected device or emulator:
   ```bash
   flutter run
   ```

## Build

```bash
# Android APK
flutter build apk --release

# iOS (requires macOS + Xcode)
flutter build ios --release

# macOS desktop
flutter build macos --release

# Windows desktop
flutter build windows --release
```

## Architecture

```
lib/
  main.dart              # App entry point, router, theme
  models/
    entry.dart           # Entry data model (mirrors SQLite + Supabase schema)
  services/
    db_service.dart      # Local SQLite (sqflite) — offline-first storage
    sync_service.dart    # Supabase sync — push/pull, pending sync on launch
  screens/
    home_screen.dart     # Timer + input
    log_screen.dart      # Scrollable time log with delete
    invoice_screen.dart  # Label selector + hourly rate → invoice PDF
    settings_screen.dart # Supabase credential display
```

## Supabase Schema

Same table used by the Python desktop app — run once in the SQL editor:

```sql
CREATE TABLE entries (
    id            BIGSERIAL PRIMARY KEY,
    sync_id       UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
    date          TEXT NOT NULL,
    start_time    TEXT NOT NULL,
    end_time      TEXT NOT NULL,
    duration_secs INTEGER NOT NULL,
    duration_str  TEXT NOT NULL,
    label         TEXT DEFAULT '',
    tag_color     TEXT DEFAULT '',
    comment       TEXT DEFAULT '',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE entries ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon all" ON entries FOR ALL USING (true) WITH CHECK (true);
```
