# -*- coding: utf-8 -*-
#
# ══════════════════════════════════════════════════════════════════════════════
#  Supabase SQL — run this ONCE in your Supabase SQL editor before syncing
# ══════════════════════════════════════════════════════════════════════════════
#
#  CREATE TABLE entries (
#      id            BIGSERIAL PRIMARY KEY,
#      sync_id       UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
#      date          TEXT NOT NULL,
#      start_time    TEXT NOT NULL,
#      end_time      TEXT NOT NULL,
#      duration_secs INTEGER NOT NULL,
#      duration_str  TEXT NOT NULL,
#      label         TEXT DEFAULT '',
#      tag_color     TEXT DEFAULT '',
#      comment       TEXT DEFAULT '',
#      created_at    TIMESTAMPTZ DEFAULT NOW()
#  );
#  ALTER TABLE entries ENABLE ROW LEVEL SECURITY;
#  CREATE POLICY "anon all" ON entries FOR ALL USING (true) WITH CHECK (true);
#
# ══════════════════════════════════════════════════════════════════════════════

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import os
import sys
import json
import uuid
import threading
import math
import random

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Resolve the app directory correctly when running as a PyInstaller .exe
_APP_DIR    = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
               else os.path.dirname(os.path.abspath(__file__)))
DB_PATH     = os.path.join(_APP_DIR, "timetracker.db")
CONFIG_PATH = os.path.join(_APP_DIR, "config.json")

# ── Color palette ─────────────────────────────────────────────────────────────
PALETTE = [
    {"name": "Blue",   "hex": "#4A90D9"},
    {"name": "Green",  "hex": "#2ECC71"},
    {"name": "Red",    "hex": "#E74C3C"},
    {"name": "Orange", "hex": "#F39C12"},
    {"name": "Purple", "hex": "#9B59B6"},
    {"name": "Pink",   "hex": "#E91E8C"},
    {"name": "Teal",   "hex": "#1ABC9C"},
    {"name": "Yellow", "hex": "#F1C40F"},
]

# ── Theme colors ──────────────────────────────────────────────────────────────
BG      = "#1A1B2E"
BG2     = "#16213E"
BG3     = "#0F3460"
ACCENT  = "#E94560"
TEXT    = "#EAEAEA"
TEXT2   = "#8A8AA0"
GREEN   = "#27AE60"
RED_BTN = "#C0392B"


class TimeTrackerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Freelance Time Tracker")
        self.root.geometry("960x720")
        self.root.minsize(760, 580)
        self.root.configure(bg=BG)

        self.running        = False
        self.start_dt       = None
        self.elapsed_secs   = 0
        self._tick_job      = None
        self.selected_color = PALETTE[0]
        self._color_btns    = []

        # Sync state
        self._supabase_client = None
        self._sync_lock       = threading.Lock()
        self._config          = self._load_config()

        # Animation state
        self._particles  = []
        self._scan_y     = 0.0
        self._anim_frame = 0

        self._init_db()
        self._build_ui()
        self._update_clock()
        self._load_entries()
        self._sync_push_pending()   # background sweep on startup
        self._sync_pull_remote()    # pull remote entries from Supabase on startup
        self._startup_connect()     # test saved credentials, update sync dot
        self._start_animations()    # decorative canvas loop
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Database ──────────────────────────────────────────────────────────────

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    date          TEXT    NOT NULL,
                    start_time    TEXT    NOT NULL,
                    end_time      TEXT    NOT NULL,
                    duration_secs INTEGER NOT NULL,
                    duration_str  TEXT    NOT NULL,
                    label         TEXT    DEFAULT '',
                    tag_color     TEXT    DEFAULT '',
                    comment       TEXT    DEFAULT ''
                )
            """)
        self._migrate_db()

    def _migrate_db(self):
        """Safely add sync_id / synced columns to existing databases."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            existing = {row[1] for row in conn.execute("PRAGMA table_info(entries)")}

            if "sync_id" not in existing:
                conn.execute("ALTER TABLE entries ADD COLUMN sync_id TEXT")

            if "synced" not in existing:
                conn.execute("ALTER TABLE entries ADD COLUMN synced INTEGER DEFAULT 0")

            # Backfill sync_id for rows that don't have one yet
            rows = conn.execute(
                "SELECT id FROM entries WHERE sync_id IS NULL OR sync_id = ''"
            ).fetchall()
            for (row_id,) in rows:
                conn.execute(
                    "UPDATE entries SET sync_id = ? WHERE id = ?",
                    (str(uuid.uuid4()), row_id),
                )

    def _save_entry(self, end_dt: datetime):
        h, rem = divmod(self.elapsed_secs, 3600)
        m, s   = divmod(rem, 60)
        dur_str   = f"{h:02d}:{m:02d}:{s:02d}"
        date      = self.start_dt.strftime("%Y-%m-%d")
        start_str = self.start_dt.strftime("%H:%M:%S")
        end_str   = end_dt.strftime("%H:%M:%S")
        label     = self.label_var.get().strip()
        comment   = self.comment_var.get().strip()
        tag_color = self.selected_color["hex"]
        sync_id   = str(uuid.uuid4())

        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    INSERT INTO entries
                      (date, start_time, end_time, duration_secs, duration_str,
                       label, tag_color, comment, sync_id, synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (date, start_str, end_str, self.elapsed_secs, dur_str,
                      label, tag_color, comment, sync_id))
        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to save entry:\n{exc}", parent=self.root)
            return

        self._load_entries()
        threading.Thread(
            target=self._sync_push_entry, args=(sync_id,), daemon=True
        ).start()

    def _update_entry(self, db_id, date, start_str, end_str,
                      duration_secs, duration_str, label, tag_color, comment):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    UPDATE entries SET
                        date=?, start_time=?, end_time=?,
                        duration_secs=?, duration_str=?,
                        label=?, tag_color=?, comment=?, synced=0
                    WHERE id=?
                """, (date, start_str, end_str, duration_secs, duration_str,
                      label, tag_color, comment, db_id))
                row = conn.execute(
                    "SELECT sync_id FROM entries WHERE id=?", (db_id,)
                ).fetchone()
        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to update entry:\n{exc}", parent=self.root)
            return

        self._load_entries()
        if row and row[0]:
            threading.Thread(
                target=self._sync_push_entry, args=(row[0],), daemon=True
            ).start()

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        item  = sel[0]
        db_id = self.tree.item(item, "values")[0]
        if not messagebox.askyesno("Delete Entry", "Delete this time entry?", parent=self.root):
            return

        try:
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute(
                    "SELECT sync_id FROM entries WHERE id=?", (db_id,)
                ).fetchone()
                conn.execute("DELETE FROM entries WHERE id = ?", (db_id,))
        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to delete entry:\n{exc}", parent=self.root)
            return

        self.tree.delete(item)
        self._refresh_total()

        if row and row[0]:
            sync_id = row[0]
            threading.Thread(
                target=self._sync_delete_entry, args=(sync_id,), daemon=True
            ).start()

    def _load_entries(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute("""
                    SELECT id, date, start_time, end_time, duration_str,
                           label, tag_color, comment
                    FROM entries
                    ORDER BY id DESC
                """).fetchall()
        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"Failed to load entries:\n{exc}", parent=self.root)
            return

        for row in rows:
            db_id, date, start, end, dur, label, color, comment = row
            tag_key = f"clr_{color.replace('#', '')}" if color else "default"
            self.tree.insert(
                "", "end",
                values=(db_id, date, start, end, dur, label or "", comment or ""),
                tags=(tag_key,),
            )
            if color:
                row_bg = self._tint(color)
                self.tree.tag_configure(tag_key, background=row_bg, foreground=TEXT)

        self._refresh_total()
        self._refresh_label_totals()

    def _refresh_label_totals(self):
        """Rebuild the sidebar with color-coded per-project hour totals."""
        for w in self._sidebar_rows.winfo_children():
            w.destroy()

        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute("""
                    SELECT e.label,
                           (SELECT tag_color FROM entries e2
                            WHERE e2.label = e.label
                            ORDER BY e2.id DESC LIMIT 1) AS color,
                           SUM(e.duration_secs)
                    FROM entries e
                    WHERE e.label IS NOT NULL AND e.label != ''
                    GROUP BY e.label
                    ORDER BY SUM(e.duration_secs) DESC
                """).fetchall()
        except sqlite3.Error:
            return

        grand_secs = 0
        for label, color, total_secs in rows:
            secs = total_secs or 0
            grand_secs += secs
            h, rem = divmod(secs, 3600)
            m, s   = divmod(rem, 60)
            dur    = f"{h:02d}:{m:02d}:{s:02d}"
            fg     = color if color else TEXT2

            row = tk.Frame(self._sidebar_rows, bg=BG2)
            row.pack(fill="x", padx=6, pady=1)
            tk.Label(row, text="●", fg=fg, bg=BG2,
                     font=("Helvetica", 8)).pack(side="left")
            lbl_text = label if len(label) <= 18 else label[:17] + "…"
            tk.Label(row, text=lbl_text, fg=fg, bg=BG2,
                     font=("Helvetica", 8), anchor="w").pack(
                         side="left", padx=(3, 0), fill="x", expand=True)
            tk.Label(row, text=dur, fg=fg, bg=BG2,
                     font=("Courier", 8), anchor="e").pack(side="right")

        gh, grem = divmod(grand_secs, 3600)
        gm, gs   = divmod(grem, 60)
        self._sidebar_total_var.set(f"TOTAL  {gh:02d}:{gm:02d}:{gs:02d}")

    def _refresh_total(self):
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            with sqlite3.connect(DB_PATH) as conn:
                result = conn.execute(
                    "SELECT SUM(duration_secs) FROM entries WHERE date = ?", (today,)
                ).fetchone()
        except sqlite3.Error:
            return   # non-critical display; fail silently
        total_secs = result[0] or 0
        h, rem = divmod(total_secs, 3600)
        m, s   = divmod(rem, 60)
        self.total_var.set(f"Today's total: {h:02d}:{m:02d}:{s:02d}")

    # ── Config I/O ────────────────────────────────────────────────────────────

    def _load_config(self) -> dict:
        defaults = {"supabase_url": "", "supabase_key": ""}
        if not os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "w") as f:
                    json.dump(defaults, f, indent=2)
            except OSError:
                pass
            return defaults
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
            return {**defaults, **data}
        except (json.JSONDecodeError, OSError):
            return defaults

    def _save_config(self):
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(self._config, f, indent=2)
        except OSError:
            pass
        with self._sync_lock:
            self._supabase_client = None   # force re-init on next use

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_timer_section()
        self._build_input_section()
        self._build_log_section()
        self._build_statusbar()

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=BG2, pady=10)
        hdr.pack(fill="x")

        tk.Label(
            hdr, text="FREELANCE TIME TRACKER",
            bg=BG2, fg=TEXT, font=("Helvetica", 13, "bold"), padx=20,
        ).pack(side="left")

        # ── right-side controls (pack before canvas so it fills the middle) ──
        self.clock_var = tk.StringVar(value="00:00:00")
        tk.Label(
            hdr, textvariable=self.clock_var,
            bg=BG2, fg=TEXT2, font=("Courier", 13), padx=20,
        ).pack(side="right")

        self.sync_dot = tk.Label(
            hdr, text="●", bg=BG2, fg="#555577",
            font=("Helvetica", 14), padx=6, cursor="hand2",
        )
        self.sync_dot.pack(side="right")

        tk.Button(
            hdr, text="⚙", bg=BG2, fg=TEXT2,
            activebackground=BG3, activeforeground=TEXT,
            font=("Helvetica", 13), relief="flat", bd=0,
            padx=8, cursor="hand2",
            command=self._open_settings_dialog,
        ).pack(side="right")

        # ── animated particle canvas (fills remaining header space) ──
        self._deco_canvas = tk.Canvas(
            hdr, bg=BG2, highlightthickness=0, height=36,
        )
        self._deco_canvas.pack(side="left", fill="x", expand=True, padx=(8, 8))

        def _draw_grid(event=None):
            self._deco_canvas.delete("grid")
            cw = self._deco_canvas.winfo_width()
            ch = self._deco_canvas.winfo_height()
            for x in range(0, cw, 28):
                self._deco_canvas.create_line(
                    x, 0, x, ch, fill="#1C2148", width=1, tags="grid"
                )
            for y in range(0, ch, 9):
                self._deco_canvas.create_line(
                    0, y, cw, y, fill="#1C2148", width=1, tags="grid"
                )

        self._deco_canvas.bind("<Configure>", _draw_grid)

    def _build_timer_section(self):
        frame = tk.Frame(self.root, bg=BG, pady=10)
        frame.pack(fill="x")

        # ── top bracket ──────────────────────────────────────────────────────
        top_brk = tk.Canvas(frame, bg=BG, highlightthickness=0, height=14)
        top_brk.pack(fill="x", padx=60, pady=(4, 0))

        def _draw_top(event=None):
            top_brk.delete("all")
            w = top_brk.winfo_width()
            # Corner L-brackets
            top_brk.create_line(0,  14, 0,  0,    fill=ACCENT, width=2)
            top_brk.create_line(0,  0,  22, 0,    fill=ACCENT, width=2)
            top_brk.create_line(w,  14, w,  0,    fill=ACCENT, width=2)
            top_brk.create_line(w,  0,  w-22, 0,  fill=ACCENT, width=2)
            # Center dashed guide line
            top_brk.create_line(30, 7, w-30, 7, fill="#1E2540", width=1, dash=(3, 9))

        top_brk.bind("<Configure>", _draw_top)

        # ── timer display ─────────────────────────────────────────────────────
        self.timer_var = tk.StringVar(value="00:00:00")
        self._timer_lbl = tk.Label(
            frame, textvariable=self.timer_var,
            bg=BG, fg=ACCENT, font=("Courier", 58, "bold"),
        )
        self._timer_lbl.pack()

        # ── bottom bracket ────────────────────────────────────────────────────
        bot_brk = tk.Canvas(frame, bg=BG, highlightthickness=0, height=14)
        bot_brk.pack(fill="x", padx=60, pady=(0, 4))

        def _draw_bot(event=None):
            bot_brk.delete("all")
            w = bot_brk.winfo_width()
            bot_brk.create_line(0,  0,  0,  14,   fill=ACCENT, width=2)
            bot_brk.create_line(0,  14, 22, 14,   fill=ACCENT, width=2)
            bot_brk.create_line(w,  0,  w,  14,   fill=ACCENT, width=2)
            bot_brk.create_line(w,  14, w-22, 14, fill=ACCENT, width=2)
            bot_brk.create_line(30, 7, w-30, 7, fill="#1E2540", width=1, dash=(3, 9))

        bot_brk.bind("<Configure>", _draw_bot)

        btn_row = tk.Frame(frame, bg=BG, pady=8)
        btn_row.pack()

        self.start_btn = tk.Button(
            btn_row, text="▶  START",
            bg=GREEN, fg="white", activebackground="#2ECC71", activeforeground="white",
            font=("Helvetica", 12, "bold"), relief="flat",
            padx=26, pady=8, cursor="hand2", command=self._start,
        )
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = tk.Button(
            btn_row, text="■  STOP",
            bg=RED_BTN, fg="white", activebackground="#E74C3C", activeforeground="white",
            font=("Helvetica", 12, "bold"), relief="flat",
            padx=26, pady=8, cursor="hand2", command=self._stop, state="disabled",
        )
        self.stop_btn.pack(side="left", padx=10)

    def _build_input_section(self):
        outer = tk.Frame(self.root, bg=BG, padx=28, pady=0)
        outer.pack(fill="x")

        card = tk.Frame(outer, bg=BG2, padx=20, pady=14)
        card.pack(fill="x")

        def field_row(parent, label_text, var):
            row = tk.Frame(parent, bg=BG2)
            row.pack(fill="x", pady=4)
            tk.Label(
                row, text=label_text, bg=BG2, fg=TEXT2,
                font=("Helvetica", 10), width=16, anchor="w",
            ).pack(side="left")
            entry = tk.Entry(
                row, textvariable=var,
                bg=BG3, fg=TEXT, insertbackground=TEXT,
                font=("Helvetica", 11), relief="flat", bd=5,
            )
            entry.pack(side="left", fill="x", expand=True)
            return entry

        self.label_var   = tk.StringVar()
        self.comment_var = tk.StringVar()
        label_entry = field_row(card, "Project / Client:", self.label_var)
        field_row(card, "Comment:", self.comment_var)
        self._attach_autocomplete(label_entry, self.label_var)

        # Color tag row
        color_row = tk.Frame(card, bg=BG2)
        color_row.pack(fill="x", pady=(8, 2))
        tk.Label(
            color_row, text="Color Tag:", bg=BG2, fg=TEXT2,
            font=("Helvetica", 10), width=16, anchor="w",
        ).pack(side="left")

        for c in PALETTE:
            btn = tk.Button(
                color_row, text="  ", bg=c["hex"],
                relief="flat", bd=2, cursor="hand2", width=2,
                command=lambda col=c: self._select_color(col),
                activebackground=c["hex"],
            )
            btn.pack(side="left", padx=3)
            self._color_btns.append(btn)

        self.color_label = tk.Label(
            color_row, bg=BG2,
            font=("Helvetica", 10, "bold"), padx=10,
        )
        self.color_label.pack(side="left")
        self._select_color(PALETTE[0])

    def _build_log_section(self):
        frame = tk.Frame(self.root, bg=BG, padx=28, pady=12)
        frame.pack(fill="both", expand=True)

        # ── header row ────────────────────────────────────────────────────────
        hdr = tk.Frame(frame, bg=BG)
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(
            hdr, text="TIME LOG  (double-click to edit)",
            bg=BG, fg=TEXT2, font=("Helvetica", 10, "bold"),
        ).pack(side="left")

        tk.Button(
            hdr, text="Delete Selected",
            bg=BG3, fg=TEXT2, activebackground=RED_BTN, activeforeground="white",
            font=("Helvetica", 9), relief="flat", padx=10, pady=3,
            cursor="hand2", command=self._delete_selected,
        ).pack(side="right")
        tk.Button(
            hdr, text="Create Invoice",
            bg=BG3, fg="#F1C40F", activebackground=BG2, activeforeground="#F1C40F",
            font=("Helvetica", 9, "bold"), relief="flat", padx=10, pady=3,
            cursor="hand2", command=self._create_invoice_dialog,
        ).pack(side="right", padx=(0, 6))
        tk.Button(
            hdr, text="Pull Hours",
            bg=BG3, fg=TEXT2, activebackground=BG2, activeforeground=TEXT,
            font=("Helvetica", 9), relief="flat", padx=10, pady=3,
            cursor="hand2", command=self._pull_hours_pdf,
        ).pack(side="right", padx=(0, 6))

        # ── Treeview style ────────────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "TT.Treeview",
            background=BG2, foreground=TEXT,
            fieldbackground=BG2, rowheight=28,
            font=("Helvetica", 10),
        )
        style.configure(
            "TT.Treeview.Heading",
            background=BG3, foreground=TEXT,
            font=("Helvetica", 10, "bold"), relief="flat",
        )
        style.map("TT.Treeview", background=[("selected", "#2A4070")])

        # ── body: sidebar (right) then tree area (left) ───────────────────────
        body = tk.Frame(frame, bg=BG)
        body.pack(fill="both", expand=True)

        # Sidebar — pack RIGHT first so tree expands into remaining space
        sidebar = tk.Frame(body, bg=BG2, width=178)
        sidebar.pack(side="right", fill="y", padx=(8, 0))
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar, text="HOURS BY PROJECT",
            bg=BG2, fg=TEXT2, font=("Helvetica", 7, "bold"),
            pady=7, padx=8, anchor="w",
        ).pack(fill="x")
        tk.Frame(sidebar, bg=BG3, height=1).pack(fill="x")

        self._sidebar_rows = tk.Frame(sidebar, bg=BG2)
        self._sidebar_rows.pack(fill="both", expand=True, pady=4)

        tk.Frame(sidebar, bg=BG3, height=1).pack(fill="x", side="bottom")
        self._sidebar_total_var = tk.StringVar(value="TOTAL  00:00:00")
        tk.Label(
            sidebar, textvariable=self._sidebar_total_var,
            bg=BG2, fg="#00D4FF", font=("Courier", 9, "bold"),
            pady=6, padx=8, anchor="e",
        ).pack(fill="x", side="bottom")

        # Tree area — pack LEFT, expands to fill remainder
        tree_area = tk.Frame(body, bg=BG)
        tree_area.pack(side="left", fill="both", expand=True)

        cols = ("id", "date", "start", "end", "duration", "label", "comment")
        self.tree = ttk.Treeview(
            tree_area, columns=cols, show="headings",
            style="TT.Treeview", selectmode="browse",
        )
        col_defs = [
            ("id",       "",          0,   "center"),
            ("date",     "Date",     100,  "center"),
            ("start",    "Start",     75,  "center"),
            ("end",      "End",       75,  "center"),
            ("duration", "Duration",  85,  "center"),
            ("label",    "Label",    150,  "center"),
            ("comment",  "Comment",  999,  "w"),
        ]
        for cid, cname, cwidth, anchor in col_defs:
            self.tree.heading(cid, text=cname)
            self.tree.column(cid, width=cwidth, minwidth=cwidth, anchor=anchor)

        scroll_y = ttk.Scrollbar(tree_area, orient="vertical",   command=self.tree.yview)
        scroll_x = ttk.Scrollbar(tree_area, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side="right",  fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left",  fill="both", expand=True)

        self.tree.bind("<Double-1>", self._open_edit_dialog)

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=BG3, pady=5)
        bar.pack(fill="x", side="bottom")

        self.total_var = tk.StringVar(value="Today's total: 00:00:00")
        tk.Label(
            bar, textvariable=self.total_var,
            bg=BG3, fg=TEXT2, font=("Helvetica", 10), padx=16,
        ).pack(side="left")

        tk.Label(
            bar, text="timetracker.db", bg=BG3, fg=TEXT2,
            font=("Helvetica", 9), padx=16,
        ).pack(side="right")

    # ── Timer logic ───────────────────────────────────────────────────────────

    def _start(self):
        if self.running:
            return
        self.running    = True
        self.start_dt   = datetime.now()
        self.elapsed_secs = 0
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self._tick()
        self._pulse_running()

    def _stop(self):
        if not self.running:
            return
        self.running = False
        if self._tick_job:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None
        end_dt = datetime.now()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self._save_entry(end_dt)
        self.timer_var.set("00:00:00")
        self._timer_lbl.config(fg=ACCENT)   # reset pulse color

    def _on_close(self):
        """Save any running session before closing."""
        if self.running:
            self._stop()
        self.root.destroy()

    def _tick(self):
        if not self.running:
            return
        self.elapsed_secs = int((datetime.now() - self.start_dt).total_seconds())
        h, rem = divmod(self.elapsed_secs, 3600)
        m, s   = divmod(rem, 60)
        self.timer_var.set(f"{h:02d}:{m:02d}:{s:02d}")
        self._tick_job = self.root.after(1000, self._tick)

    def _update_clock(self):
        self.clock_var.set(datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._update_clock)

    # ── Color selection ───────────────────────────────────────────────────────

    def _select_color(self, color: dict):
        self.selected_color = color
        for i, btn in enumerate(self._color_btns):
            if PALETTE[i]["hex"] == color["hex"]:
                btn.config(relief="solid", bd=3,
                           highlightthickness=2, highlightbackground="white")
            else:
                btn.config(relief="flat", bd=1,
                           highlightthickness=0)
        self.color_label.config(
            text=f"● {color['name']}", fg=color["hex"]
        )

    # ── Edit Dialog ───────────────────────────────────────────────────────────

    def _open_edit_dialog(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        item   = sel[0]
        values = self.tree.item(item, "values")
        db_id, date, start, end, dur, label, comment = values

        # Fetch tag_color from DB (not stored in Treeview values)
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT tag_color FROM entries WHERE id=?", (db_id,)
            ).fetchone()
        tag_color = row[0] if row else ""

        dlg = tk.Toplevel(self.root)
        dlg.title("Edit Entry")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        # Center on parent
        dlg.update_idletasks()
        pw = self.root.winfo_x() + self.root.winfo_width()  // 2
        ph = self.root.winfo_y() + self.root.winfo_height() // 2
        dlg.geometry(f"460x400+{pw - 230}+{ph - 200}")

        pad = {"padx": 18, "pady": 6}

        def lbl_entry(parent, text, sv, readonly=False):
            row = tk.Frame(parent, bg=BG)
            row.pack(fill="x", **pad)
            tk.Label(row, text=text, bg=BG, fg=TEXT2,
                     font=("Helvetica", 10), width=14, anchor="w").pack(side="left")
            state = "readonly" if readonly else "normal"
            e = tk.Entry(row, textvariable=sv, bg=BG3, fg=TEXT,
                         insertbackground=TEXT, font=("Helvetica", 11),
                         relief="flat", bd=5, state=state,
                         readonlybackground=BG2)
            e.pack(side="left", fill="x", expand=True)
            return e

        sv_date    = tk.StringVar(value=date)
        sv_start   = tk.StringVar(value=start)
        sv_end     = tk.StringVar(value=end)
        sv_dur     = tk.StringVar(value=dur)
        sv_label   = tk.StringVar(value=label)
        sv_comment = tk.StringVar(value=comment)

        tk.Label(dlg, text="Edit Entry", bg=BG, fg=TEXT,
                 font=("Helvetica", 13, "bold")).pack(pady=(14, 4))

        lbl_entry(dlg, "Date (YYYY-MM-DD):", sv_date)
        e_start = lbl_entry(dlg, "Start (HH:MM:SS):", sv_start)
        e_end   = lbl_entry(dlg, "End (HH:MM:SS):",   sv_end)
        lbl_entry(dlg, "Duration:", sv_dur, readonly=True)
        e_label = lbl_entry(dlg, "Label:", sv_label)
        lbl_entry(dlg, "Comment:", sv_comment)
        self._attach_autocomplete(e_label, sv_label, dlg)

        def on_time_change(*_):
            self._calc_duration_from_fields(sv_start, sv_end, sv_dur)

        e_start.bind("<FocusOut>", on_time_change)
        e_end.bind("<FocusOut>",   on_time_change)

        # Color picker
        color_row = tk.Frame(dlg, bg=BG)
        color_row.pack(fill="x", padx=18, pady=6)
        tk.Label(color_row, text="Color Tag:", bg=BG, fg=TEXT2,
                 font=("Helvetica", 10), width=14, anchor="w").pack(side="left")

        selected_color_var = {"hex": tag_color}

        def pick_color(c):
            selected_color_var["hex"] = c["hex"]
            for btn, pal in zip(color_btns, PALETTE):
                if pal["hex"] == c["hex"]:
                    btn.config(relief="solid", bd=3,
                               highlightthickness=2, highlightbackground="white")
                else:
                    btn.config(relief="flat", bd=1, highlightthickness=0)

        color_btns = []
        for c in PALETTE:
            b = tk.Button(
                color_row, text="  ", bg=c["hex"],
                relief="flat", bd=2, cursor="hand2", width=2,
                command=lambda col=c: pick_color(col),
                activebackground=c["hex"],
            )
            b.pack(side="left", padx=3)
            color_btns.append(b)

        # Pre-select current color
        cur = next((c for c in PALETTE if c["hex"] == tag_color), None)
        if cur:
            pick_color(cur)

        # Status label
        status_lbl = tk.Label(dlg, text="", bg=BG, fg=RED_BTN,
                               font=("Helvetica", 9))
        status_lbl.pack()

        # Buttons
        btn_row = tk.Frame(dlg, bg=BG)
        btn_row.pack(pady=8)

        def save():
            d   = sv_date.get().strip()
            s   = sv_start.get().strip()
            e   = sv_end.get().strip()
            lbl = sv_label.get().strip()
            cmt = sv_comment.get().strip()
            clr = selected_color_var["hex"]

            # Validate date
            try:
                datetime.strptime(d, "%Y-%m-%d")
            except ValueError:
                status_lbl.config(text="Invalid date — use YYYY-MM-DD")
                return

            # Validate times
            try:
                dt_s = datetime.strptime(s, "%H:%M:%S")
                dt_e = datetime.strptime(e, "%H:%M:%S")
            except ValueError:
                status_lbl.config(text="Invalid time — use HH:MM:SS")
                return

            if dt_e <= dt_s:
                status_lbl.config(text="End time must be after start time")
                return

            delta = int((dt_e - dt_s).total_seconds())
            h2, r2 = divmod(delta, 3600)
            m2, s2 = divmod(r2, 60)
            dur_str = f"{h2:02d}:{m2:02d}:{s2:02d}"

            self._update_entry(db_id, d, s, e, delta, dur_str, lbl, clr, cmt)
            dlg.destroy()

        tk.Button(
            btn_row, text="Save",
            bg=GREEN, fg="white", activebackground="#2ECC71", activeforeground="white",
            font=("Helvetica", 11, "bold"), relief="flat",
            padx=22, pady=6, cursor="hand2", command=save,
        ).pack(side="left", padx=10)

        tk.Button(
            btn_row, text="Cancel",
            bg=BG3, fg=TEXT2, activebackground=BG2, activeforeground=TEXT,
            font=("Helvetica", 11), relief="flat",
            padx=22, pady=6, cursor="hand2", command=dlg.destroy,
        ).pack(side="left", padx=10)

    def _calc_duration_from_fields(self, sv_start, sv_end, sv_dur):
        try:
            dt_s = datetime.strptime(sv_start.get().strip(), "%H:%M:%S")
            dt_e = datetime.strptime(sv_end.get().strip(),   "%H:%M:%S")
            delta = int((dt_e - dt_s).total_seconds())
            if delta < 0:
                raise ValueError
            h, rem = divmod(delta, 3600)
            m, s   = divmod(rem, 60)
            sv_dur.set(f"{h:02d}:{m:02d}:{s:02d}")
        except ValueError:
            sv_dur.set("--:--:--")

    # ── Label Autocomplete ────────────────────────────────────────────────────

    def _get_known_labels(self):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute(
                    "SELECT DISTINCT label FROM entries"
                    " WHERE label != '' ORDER BY label COLLATE NOCASE"
                ).fetchall()
            return [r[0] for r in rows]
        except sqlite3.Error:
            return []

    def _attach_autocomplete(self, entry_widget, string_var, parent=None):
        if parent is None:
            parent = self.root

        popup_state = {"win": None, "lb": None}

        def hide():
            w = popup_state["win"]
            if w:
                try:
                    w.destroy()
                except Exception:
                    pass
            popup_state["win"] = None
            popup_state["lb"]  = None

        def show(suggestions):
            hide()
            if not suggestions:
                return

            win = tk.Toplevel(parent)
            win.wm_overrideredirect(True)
            win.configure(bg=BG3)

            lb = tk.Listbox(
                win, bg=BG3, fg=TEXT,
                selectbackground=ACCENT, selectforeground="white",
                font=("Helvetica", 11), relief="flat", bd=0,
                activestyle="none", exportselection=False,
            )
            lb.pack(fill="both", expand=True)
            for s in suggestions:
                lb.insert("end", s)

            entry_widget.update_idletasks()
            x = entry_widget.winfo_rootx()
            y = entry_widget.winfo_rooty() + entry_widget.winfo_height()
            w = entry_widget.winfo_width()
            h = min(len(suggestions), 6) * 26 + 4
            win.geometry(f"{w}x{h}+{x}+{y}")

            popup_state["win"] = win
            popup_state["lb"]  = lb

            def pick(event=None):
                sel = lb.curselection()
                if sel:
                    string_var.set(lb.get(sel[0]))
                hide()
                entry_widget.focus_set()

            def lb_key(event):
                if event.keysym in ("Return", "Tab"):
                    pick()
                elif event.keysym == "Escape":
                    hide()
                    entry_widget.focus_set()

            lb.bind("<ButtonRelease-1>", pick)
            lb.bind("<KeyPress>", lb_key)

        def on_change(*_):
            text = string_var.get()
            if not text:
                hide()
                return
            matches = [
                lbl for lbl in self._get_known_labels()
                if lbl.lower().startswith(text.lower()) and lbl != text
            ]
            show(matches)

        def on_focus_out(event):
            parent.after(150, hide)

        def on_down(event):
            lb = popup_state["lb"]
            if lb:
                lb.focus_set()
                lb.selection_set(0)
                lb.activate(0)

        string_var.trace_add("write", on_change)
        entry_widget.bind("<FocusOut>", on_focus_out)
        entry_widget.bind("<Down>",     on_down)
        entry_widget.bind("<Escape>",   lambda e: hide())

    # ── Settings Dialog ───────────────────────────────────────────────────────

    def _open_settings_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Supabase Sync Settings")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        dlg.update_idletasks()
        pw = self.root.winfo_x() + self.root.winfo_width()  // 2
        ph = self.root.winfo_y() + self.root.winfo_height() // 2
        dlg.geometry(f"500x290+{pw - 250}+{ph - 145}")

        tk.Label(dlg, text="Supabase Sync", bg=BG, fg=TEXT,
                 font=("Helvetica", 13, "bold")).pack(pady=(14, 2))

        tk.Label(
            dlg,
            text="1. Create a free project at supabase.com\n"
                 "2. Open the SQL editor and run the CREATE TABLE\n"
                 "   block at the top of timetracker.py\n"
                 "3. Paste your Project URL and Anon Key below",
            bg=BG, fg=TEXT2, font=("Helvetica", 9), justify="left",
        ).pack(padx=20, pady=(0, 8), anchor="w")

        def field(lbl_text, default, masked=False):
            row = tk.Frame(dlg, bg=BG)
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=lbl_text, bg=BG, fg=TEXT2,
                     font=("Helvetica", 10), width=14, anchor="w").pack(side="left")
            sv = tk.StringVar(value=default)
            kw = {"show": "*"} if masked else {}
            tk.Entry(row, textvariable=sv, bg=BG3, fg=TEXT,
                     insertbackground=TEXT, font=("Helvetica", 10),
                     relief="flat", bd=5, **kw).pack(side="left", fill="x", expand=True)
            return sv

        sv_url = field("Project URL:", self._config.get("supabase_url", ""))
        sv_key = field("Anon Key:",    self._config.get("supabase_key", ""), masked=True)

        if not SUPABASE_AVAILABLE:
            tk.Label(
                dlg,
                text="⚠  supabase package not found — run: pip install supabase",
                bg=BG, fg="#F1C40F", font=("Helvetica", 9),
            ).pack(pady=2)

        status_lbl = tk.Label(dlg, text="", bg=BG, fg=TEXT2,
                               font=("Helvetica", 9))
        status_lbl.pack()

        def save_and_test():
            self._config["supabase_url"] = sv_url.get().strip()
            self._config["supabase_key"] = sv_key.get().strip()
            self._save_config()

            if not SUPABASE_AVAILABLE:
                status_lbl.config(text="Install supabase package first.", fg=RED_BTN)
                return

            if not self._config["supabase_url"] or not self._config["supabase_key"]:
                status_lbl.config(text="Please enter both URL and key.", fg=RED_BTN)
                return

            status_lbl.config(text="Testing connection…", fg=TEXT2)
            dlg.update_idletasks()

            try:
                client = create_client(
                    self._config["supabase_url"],
                    self._config["supabase_key"],
                )
                client.table("entries").select("id").limit(1).execute()
                with self._sync_lock:
                    self._supabase_client = client
                self._set_sync_status("synced")
                status_lbl.config(text="Connected successfully!", fg=GREEN)
                dlg.after(1500, dlg.destroy)
            except Exception as exc:
                self._set_sync_status("error")
                status_lbl.config(text=f"Error: {exc}", fg=RED_BTN)

        btn_row = tk.Frame(dlg, bg=BG)
        btn_row.pack(pady=10)

        tk.Button(
            btn_row, text="Save & Test",
            bg=GREEN, fg="white", activebackground="#2ECC71", activeforeground="white",
            font=("Helvetica", 11, "bold"), relief="flat",
            padx=20, pady=6, cursor="hand2", command=save_and_test,
        ).pack(side="left", padx=10)

        tk.Button(
            btn_row, text="Cancel",
            bg=BG3, fg=TEXT2, activebackground=BG2, activeforeground=TEXT,
            font=("Helvetica", 11), relief="flat",
            padx=20, pady=6, cursor="hand2", command=dlg.destroy,
        ).pack(side="left", padx=10)

    # ── Supabase Sync Engine ──────────────────────────────────────────────────

    def _set_sync_status(self, status: str):
        colors = {
            "idle":    "#555577",
            "syncing": "#F1C40F",
            "synced":  "#27AE60",
            "error":   "#E74C3C",
        }
        color = colors.get(status, "#555577")
        self.root.after(0, lambda: self.sync_dot.config(fg=color))

    def _get_supabase_client(self):
        if not SUPABASE_AVAILABLE:
            return None
        with self._sync_lock:
            if self._supabase_client is not None:
                return self._supabase_client
            url = self._config.get("supabase_url", "").strip()
            key = self._config.get("supabase_key", "").strip()
            if not url or not key:
                return None
            try:
                client = create_client(url, key)
                self._supabase_client = client
                return client
            except Exception:
                return None

    def _sync_push_entry(self, sync_id: str):
        """Fire-and-forget: called from daemon threads."""
        client = self._get_supabase_client()
        if client is None:
            return

        self.root.after(0, lambda: self._set_sync_status("syncing"))

        try:
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute("""
                    SELECT sync_id, date, start_time, end_time,
                           duration_secs, duration_str, label, tag_color, comment
                    FROM entries WHERE sync_id=?
                """, (sync_id,)).fetchone()

            if row is None:
                return

            payload = {
                "sync_id":       row[0],
                "date":          row[1],
                "start_time":    row[2],
                "end_time":      row[3],
                "duration_secs": row[4],
                "duration_str":  row[5],
                "label":         row[6] or "",
                "tag_color":     row[7] or "",
                "comment":       row[8] or "",
            }
            client.table("entries").upsert(payload, on_conflict="sync_id").execute()

            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "UPDATE entries SET synced=1 WHERE sync_id=?", (sync_id,)
                )

            self.root.after(0, lambda: self._set_sync_status("synced"))

        except Exception:
            self.root.after(0, lambda: self._set_sync_status("error"))

    def _sync_delete_entry(self, sync_id: str):
        """Fire-and-forget: delete from Supabase."""
        client = self._get_supabase_client()
        if client is None:
            return
        try:
            client.table("entries").delete().eq("sync_id", sync_id).execute()
        except Exception:
            pass

    def _sync_push_pending(self):
        """On startup, push any locally-saved rows that weren't synced yet."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute(
                    "SELECT sync_id FROM entries WHERE synced=0 OR synced IS NULL"
                ).fetchall()
        except Exception:
            return

        for (sync_id,) in rows:
            if sync_id:
                threading.Thread(
                    target=self._sync_push_entry, args=(sync_id,), daemon=True
                ).start()

    def _sync_pull_remote(self):
        """On startup, pull all remote Supabase entries into local DB."""
        threading.Thread(target=self._bg_sync_pull_remote, daemon=True).start()

    def _bg_sync_pull_remote(self):
        client = self._get_supabase_client()
        if client is None:
            return
        try:
            rows = client.table("entries").select("*").execute().data
        except Exception:
            return
        if not rows:
            return
        with sqlite3.connect(DB_PATH) as conn:
            for r in rows:
                conn.execute("""
                    INSERT OR REPLACE INTO entries
                        (sync_id, date, start_time, end_time,
                         duration_secs, duration_str, label, tag_color, comment, synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, (
                    r.get("sync_id", ""),
                    r.get("date", ""),
                    r.get("start_time", ""),
                    r.get("end_time", ""),
                    r.get("duration_secs", 0),
                    r.get("duration_str", ""),
                    r.get("label", ""),
                    r.get("tag_color", ""),
                    r.get("comment", ""),
                ))
        self.root.after(0, self._load_entries)

    def _startup_connect(self):
        """If credentials are saved, test the connection in a background thread
        and update the sync dot — no user action required."""
        url = self._config.get("supabase_url", "").strip()
        key = self._config.get("supabase_key", "").strip()
        if not url or not key or not SUPABASE_AVAILABLE:
            return
        threading.Thread(target=self._bg_startup_connect, daemon=True).start()

    def _bg_startup_connect(self):
        """Background: ping Supabase and reflect result in the sync dot."""
        client = self._get_supabase_client()
        if client is None:
            self.root.after(0, lambda: self._set_sync_status("error"))
            return
        try:
            client.table("entries").select("id").limit(1).execute()
            self.root.after(0, lambda: self._set_sync_status("synced"))
        except Exception:
            self.root.after(0, lambda: self._set_sync_status("error"))

    # ── PDF Export ────────────────────────────────────────────────────────────

    def _check_reportlab(self) -> bool:
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror(
                "Missing Package",
                "ReportLab is required for PDF export.\n\nRun:  pip install reportlab",
                parent=self.root,
            )
        return REPORTLAB_AVAILABLE

    def _pdf_save_path(self, filename: str) -> str:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        out_dir = desktop if os.path.isdir(desktop) else _APP_DIR
        return os.path.join(out_dir, filename)

    def _open_pdf(self, filepath: str):
        messagebox.showinfo("PDF Ready", f"Saved to:\n{filepath}", parent=self.root)
        try:
            os.startfile(filepath)
        except Exception:
            pass

    # ── Pull Hours ─────────────────────────────────────────────────────────────

    def _pull_hours_pdf(self):
        if not self._check_reportlab():
            return
        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute("""
                    SELECT date, start_time, end_time, duration_secs,
                           duration_str, label, comment
                    FROM entries ORDER BY date ASC, start_time ASC
                """).fetchall()
        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"{exc}", parent=self.root)
            return
        if not rows:
            messagebox.showinfo("No Data", "No time entries to export.", parent=self.root)
            return
        filepath = self._pdf_save_path(
            f"TimeReport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        self._build_hours_pdf(rows, filepath)
        self._open_pdf(filepath)

    def _build_hours_pdf(self, rows, filepath):
        doc = SimpleDocTemplate(
            filepath, pagesize=letter,
            topMargin=0.75*inch, bottomMargin=0.75*inch,
            leftMargin=0.75*inch, rightMargin=0.75*inch,
        )
        avail_w = letter[0] - 1.5*inch

        DARK  = rl_colors.HexColor("#1A1B2E")
        LGREY = rl_colors.HexColor("#E0E0E0")
        ALT   = rl_colors.HexColor("#F4F5FA")

        h1   = ParagraphStyle("H1",   fontSize=26, fontName="Helvetica-Bold",
                               textColor=DARK, spaceAfter=2)
        sub  = ParagraphStyle("Sub",  fontSize=10, fontName="Helvetica",
                               textColor=rl_colors.HexColor("#8A8AA0"), spaceAfter=16)
        note = ParagraphStyle("Note", fontSize=8,  fontName="Helvetica",
                               textColor=rl_colors.HexColor("#444444"), leading=11)
        summ = ParagraphStyle("Summ", fontSize=11, fontName="Helvetica-Bold",
                               textColor=DARK, alignment=TA_RIGHT)

        story = []
        story.append(Paragraph("TIME REPORT", h1))
        story.append(Paragraph(
            f"Generated {datetime.now().strftime('%B %d, %Y  ·  %H:%M')}", sub
        ))
        story.append(HRFlowable(width="100%", thickness=2, color=DARK, spaceAfter=10))

        # Build table
        table_data = [["Date", "Start", "End", "Duration", "Label", "Notes"]]
        total_secs = 0
        for date, start, end, dur_secs, dur_str, label, comment in rows:
            table_data.append([
                date, start, end, dur_str,
                Paragraph(label or "", note),
                Paragraph(comment or "", note),
            ])
            total_secs += dur_secs or 0

        fixed_w  = [0.88*inch, 0.70*inch, 0.70*inch, 0.75*inch, 1.45*inch]
        col_w    = fixed_w + [avail_w - sum(fixed_w)]

        tbl = Table(table_data, colWidths=col_w, repeatRows=1)
        cmds = [
            ("BACKGROUND",    (0, 0), (-1,  0), DARK),
            ("TEXTCOLOR",     (0, 0), (-1,  0), rl_colors.white),
            ("FONTNAME",      (0, 0), (-1,  0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1,  0), 9),
            ("ALIGN",         (0, 0), (-1,  0), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1,  0), 8),
            ("BOTTOMPADDING", (0, 0), (-1,  0), 8),
            ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 1), (-1, -1), 9),
            ("ALIGN",         (0, 1), (3,  -1), "CENTER"),
            ("ALIGN",         (4, 1), (5,  -1), "LEFT"),
            ("TOPPADDING",    (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 7),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW",     (0, 0), (-1,  0), 1.0, DARK),
            ("LINEBELOW",     (0, 1), (-1, -2), 0.3, LGREY),
            ("LINEBELOW",     (0,-1), (-1, -1), 0.5, LGREY),
        ] + [("BACKGROUND", (0, i), (-1, i), ALT) for i in range(2, len(table_data), 2)]
        tbl.setStyle(TableStyle(cmds))
        story.append(tbl)
        story.append(Spacer(1, 0.15*inch))

        # Summary line
        th, rem = divmod(total_secs, 3600)
        tm, ts  = divmod(rem, 60)
        n = len(rows)
        story.append(HRFlowable(width="100%", thickness=1, color=LGREY))
        story.append(Spacer(1, 0.08*inch))
        story.append(Paragraph(
            f"{n} session{'s' if n != 1 else ''} &nbsp;·&nbsp; "
            f"Total: <b>{th:02d}:{tm:02d}:{ts:02d}</b> &nbsp;·&nbsp; "
            f"<b>{total_secs / 3600:.2f} billable hours</b>",
            summ,
        ))
        doc.build(story)

    # ── Create Invoice ─────────────────────────────────────────────────────────

    def _create_invoice_dialog(self):
        if not self._check_reportlab():
            return
        try:
            with sqlite3.connect(DB_PATH) as conn:
                label_rows = conn.execute("""
                    SELECT DISTINCT label FROM entries
                    WHERE label IS NOT NULL AND label != ''
                    ORDER BY label
                """).fetchall()
        except sqlite3.Error as exc:
            messagebox.showerror("Database Error", f"{exc}", parent=self.root)
            return
        labels = [r[0] for r in label_rows]
        if not labels:
            messagebox.showinfo(
                "No Labels Found",
                "No labeled entries found.\n"
                "Add a Project / Client label when logging time.",
                parent=self.root,
            )
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Create Invoice")
        dlg.configure(bg=BG)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.update_idletasks()
        pw = self.root.winfo_x() + self.root.winfo_width()  // 2
        ph = self.root.winfo_y() + self.root.winfo_height() // 2
        dlg.geometry(f"440x370+{pw - 220}+{ph - 185}")

        tk.Label(dlg, text="Create Invoice", bg=BG, fg=TEXT,
                 font=("Helvetica", 13, "bold")).pack(pady=(18, 10))

        def add_field(label_text, sv):
            row = tk.Frame(dlg, bg=BG)
            row.pack(fill="x", padx=24, pady=4)
            tk.Label(row, text=label_text, bg=BG, fg=TEXT2,
                     font=("Helvetica", 10), width=16, anchor="w").pack(side="left")
            tk.Entry(row, textvariable=sv, bg=BG3, fg=TEXT,
                     insertbackground=TEXT, font=("Helvetica", 11),
                     relief="flat", bd=5).pack(side="left", fill="x", expand=True)

        # Label combobox
        sv_label = tk.StringVar(value=labels[0])
        lbl_row  = tk.Frame(dlg, bg=BG)
        lbl_row.pack(fill="x", padx=24, pady=4)
        tk.Label(lbl_row, text="Project / Client:", bg=BG, fg=TEXT2,
                 font=("Helvetica", 10), width=16, anchor="w").pack(side="left")
        cb = ttk.Combobox(lbl_row, textvariable=sv_label, values=labels,
                           state="readonly", font=("Helvetica", 11))
        cb.pack(side="left", fill="x", expand=True)

        sv_rate    = tk.StringVar(value="0.00")
        sv_your    = tk.StringVar()
        sv_client  = tk.StringVar()
        sv_inv_num = tk.StringVar(value=f"INV-{datetime.now().strftime('%Y%m%d')}")

        add_field("Hourly Rate ($):", sv_rate)
        add_field("Your Name:", sv_your)
        add_field("Client Name:", sv_client)
        add_field("Invoice #:", sv_inv_num)

        status = tk.Label(dlg, text="", bg=BG, fg=RED_BTN, font=("Helvetica", 9))
        status.pack(pady=(4, 0))

        def generate():
            label   = sv_label.get().strip()
            rate_s  = sv_rate.get().strip().lstrip("$")
            your    = sv_your.get().strip()
            client  = sv_client.get().strip()
            inv_num = sv_inv_num.get().strip() or f"INV-{datetime.now().strftime('%Y%m%d')}"
            try:
                rate = float(rate_s)
                if rate < 0:
                    raise ValueError
            except ValueError:
                status.config(text="Enter a valid hourly rate (e.g. 75.00)")
                return
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    inv_rows = conn.execute("""
                        SELECT date, start_time, end_time, duration_secs,
                               duration_str, comment
                        FROM entries WHERE label = ?
                        ORDER BY date ASC, start_time ASC
                    """, (label,)).fetchall()
            except sqlite3.Error as exc:
                status.config(text=f"DB error: {exc}")
                return
            if not inv_rows:
                status.config(text=f"No entries found for '{label}'")
                return
            safe_num = "".join(c for c in inv_num if c.isalnum() or c in "-_")
            filepath = self._pdf_save_path(f"Invoice_{safe_num}.pdf")
            self._build_invoice_pdf(inv_rows, rate, label, your, client, inv_num, filepath)
            dlg.destroy()
            self._open_pdf(filepath)

        btn_row = tk.Frame(dlg, bg=BG)
        btn_row.pack(pady=12)
        tk.Button(btn_row, text="Generate PDF",
                  bg=GREEN, fg="white", activebackground="#2ECC71", activeforeground="white",
                  font=("Helvetica", 11, "bold"), relief="flat", padx=20, pady=6,
                  cursor="hand2", command=generate).pack(side="left", padx=10)
        tk.Button(btn_row, text="Cancel",
                  bg=BG3, fg=TEXT2, activebackground=BG2, activeforeground=TEXT,
                  font=("Helvetica", 11), relief="flat", padx=20, pady=6,
                  cursor="hand2", command=dlg.destroy).pack(side="left", padx=10)

    def _build_invoice_pdf(self, rows, rate, label, your_name, client_name, inv_num, filepath):
        doc = SimpleDocTemplate(
            filepath, pagesize=letter,
            topMargin=0.75*inch, bottomMargin=0.75*inch,
            leftMargin=0.75*inch, rightMargin=0.75*inch,
        )
        avail_w = letter[0] - 1.5*inch
        now_str = datetime.now().strftime("%B %d, %Y")

        DARK    = rl_colors.HexColor("#1A1B2E")
        LGREY   = rl_colors.HexColor("#E0E0E0")
        ALT     = rl_colors.HexColor("#F4F5FA")
        ACCENT_C = rl_colors.HexColor("#E94560")

        lbl_s  = ParagraphStyle("Lbl",  fontSize=7,  fontName="Helvetica-Bold",
                                 textColor=rl_colors.HexColor("#8A8AA0"),
                                 spaceBefore=8, spaceAfter=1)
        body_s = ParagraphStyle("Body", fontSize=11, fontName="Helvetica",
                                 textColor=DARK)
        inv_t  = ParagraphStyle("InvT", fontSize=32, fontName="Helvetica-Bold",
                                 textColor=DARK, alignment=TA_RIGHT, spaceAfter=3)
        inv_s  = ParagraphStyle("InvS", fontSize=10, fontName="Helvetica",
                                 textColor=rl_colors.HexColor("#555577"),
                                 alignment=TA_RIGHT, spaceAfter=2)
        note_s = ParagraphStyle("Note", fontSize=8,  fontName="Helvetica",
                                 textColor=rl_colors.HexColor("#444444"), leading=11)
        tot_l  = ParagraphStyle("TotL", fontSize=10, fontName="Helvetica",
                                 textColor=rl_colors.HexColor("#555577"), alignment=TA_RIGHT)
        tot_v  = ParagraphStyle("TotV", fontSize=10, fontName="Helvetica-Bold",
                                 textColor=DARK, alignment=TA_RIGHT)
        due_l  = ParagraphStyle("DueL", fontSize=13, fontName="Helvetica-Bold",
                                 textColor=DARK, alignment=TA_RIGHT)
        due_v  = ParagraphStyle("DueV", fontSize=13, fontName="Helvetica-Bold",
                                 textColor=ACCENT_C, alignment=TA_RIGHT)
        foot_s = ParagraphStyle("Foot", fontSize=8,  fontName="Helvetica",
                                 textColor=rl_colors.HexColor("#8A8AA0"),
                                 alignment=TA_CENTER)

        story = []

        # ── top header: left info | right INVOICE ──────────────────────────────
        lw = avail_w * 0.55
        rw = avail_w * 0.45

        left_items  = []
        if your_name:
            left_items += [Paragraph("FROM",     lbl_s), Paragraph(your_name,  body_s)]
        if client_name:
            left_items += [Paragraph("BILL TO",  lbl_s), Paragraph(client_name, body_s)]
        left_items  += [Paragraph("PROJECT",     lbl_s), Paragraph(label,        body_s)]

        right_items = [
            Paragraph("INVOICE",          inv_t),
            Paragraph(f"#{inv_num}",      inv_s),
            Paragraph(now_str,            inv_s),
        ]
        if rows:
            fd, ld = rows[0][0], rows[-1][0]
            if fd != ld:
                right_items.append(Paragraph(f"{fd} – {ld}", inv_s))

        def _stack(items, width, align="LEFT"):
            t = Table([[it] for it in items], colWidths=[width])
            t.setStyle(TableStyle([
                ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                ("TOPPADDING",    (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("ALIGN",         (0, 0), (-1, -1), align),
            ]))
            return t

        hdr_tbl = Table([[_stack(left_items, lw, "LEFT"),
                          _stack(right_items, rw, "RIGHT")]],
                        colWidths=[lw, rw])
        hdr_tbl.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(hdr_tbl)
        story.append(Spacer(1, 0.25*inch))
        story.append(HRFlowable(width="100%", thickness=2, color=DARK, spaceAfter=14))

        # ── line items ────────────────────────────────────────────────────────
        tbl_data   = [["Date", "Description", "Hours", "Rate", "Amount"]]
        total_secs = 0
        for date, start, end, dur_secs, dur_str, comment in rows:
            hrs    = (dur_secs or 0) / 3600
            amount = hrs * rate
            total_secs += dur_secs or 0
            tbl_data.append([
                date,
                Paragraph(comment or "—", note_s),
                f"{hrs:.2f}",
                f"${rate:,.2f}",
                f"${amount:,.2f}",
            ])

        fixed   = [0.9*inch, None, 0.65*inch, 0.85*inch, 0.9*inch]
        fixed[1] = avail_w - sum(w for w in fixed if w)
        itbl = Table(tbl_data, colWidths=fixed, repeatRows=1)
        istyle = [
            ("BACKGROUND",    (0, 0), (-1,  0), DARK),
            ("TEXTCOLOR",     (0, 0), (-1,  0), rl_colors.white),
            ("FONTNAME",      (0, 0), (-1,  0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1,  0), 9),
            ("ALIGN",         (0, 0), (0,   0), "CENTER"),
            ("ALIGN",         (1, 0), (1,   0), "LEFT"),
            ("ALIGN",         (2, 0), (4,   0), "RIGHT"),
            ("TOPPADDING",    (0, 0), (-1,  0), 8),
            ("BOTTOMPADDING", (0, 0), (-1,  0), 8),
            ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 1), (-1, -1), 9),
            ("ALIGN",         (0, 1), (0,  -1), "CENTER"),
            ("ALIGN",         (1, 1), (1,  -1), "LEFT"),
            ("ALIGN",         (2, 1), (4,  -1), "RIGHT"),
            ("TOPPADDING",    (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 7),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW",     (0, 0), (-1,  0), 1.0, DARK),
            ("LINEBELOW",     (0, 1), (-1, -2), 0.3, LGREY),
            ("LINEBELOW",     (0,-1), (-1, -1), 1.0, DARK),
        ] + [("BACKGROUND", (0, i), (-1, i), ALT) for i in range(2, len(tbl_data), 2)]
        itbl.setStyle(TableStyle(istyle))
        story.append(itbl)
        story.append(Spacer(1, 0.2*inch))

        # ── totals block ──────────────────────────────────────────────────────
        total_hrs    = total_secs / 3600
        total_amount = total_hrs * rate
        tot_rows = [
            [Paragraph("Total Hours:", tot_l), Paragraph(f"{total_hrs:.2f} hrs",     tot_v)],
            [Paragraph("Hourly Rate:", tot_l), Paragraph(f"${rate:,.2f} / hr",       tot_v)],
            [Paragraph("",            tot_l), Paragraph("",                           tot_v)],
            [Paragraph("AMOUNT DUE:", due_l), Paragraph(f"${total_amount:,.2f}",     due_v)],
        ]
        tot_col_w = [2.1*inch, 1.5*inch]
        tot_tbl   = Table(tot_rows, colWidths=tot_col_w)
        tot_tbl.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEABOVE",     (0, 3), (-1,  3), 1.0, DARK),
            ("TOPPADDING",    (0, 3), (-1,  3), 8),
            ("BOTTOMPADDING", (0, 3), (-1,  3), 8),
        ]))
        spacer_w = avail_w - sum(tot_col_w)
        wrap_tbl = Table([[Spacer(1, 1), tot_tbl]], colWidths=[spacer_w, sum(tot_col_w)])
        wrap_tbl.setStyle(TableStyle([
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(wrap_tbl)

        # ── footer ────────────────────────────────────────────────────────────
        story.append(Spacer(1, 0.5*inch))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LGREY, spaceAfter=8))
        story.append(Paragraph(
            "Thank you for your business.  Payment due upon receipt.", foot_s
        ))
        doc.build(story)

    # ── Decorations / Animations ──────────────────────────────────────────────

    def _start_animations(self):
        """Seed particles and kick off the canvas animation loop."""
        cw = self.root.winfo_width()
        self._particles = [
            {
                "x":     random.uniform(0, cw),
                "y":     random.uniform(3, 30),
                "speed": random.uniform(0.5, 2.2),
                "cidx":  i % len(PALETTE),
                "size":  random.uniform(1.5, 3.5),
            }
            for i in range(16)
        ]
        self._anim_tick()

    def _anim_tick(self):
        """30-fps animation loop: moves particles + scan line across the header canvas."""
        c = self._deco_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 4:
            self.root.after(100, self._anim_tick)
            return

        c.delete("p")
        self._anim_frame += 1

        # Horizontal scan line (moves top → bottom, repeats)
        self._scan_y = (self._scan_y + 0.45) % h
        c.create_line(0, self._scan_y, w, self._scan_y,
                      fill="#252B5A", width=1, tags="p")

        # Particles with fading trails
        for p in self._particles:
            p["x"] -= p["speed"]
            if p["x"] < -30:
                p["x"]     = w + random.uniform(5, 50)
                p["y"]     = random.uniform(3, h - 3)
                p["cidx"]  = random.randint(0, len(PALETTE) - 1)
                p["speed"] = random.uniform(0.5, 2.2)
                p["size"]  = random.uniform(1.5, 3.5)

            color        = PALETTE[p["cidx"]]["hex"]
            r, x, y      = p["size"], p["x"], p["y"]
            cr, cg, cb   = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)

            for i in range(1, 11):          # 10-segment trail behind head
                tx   = x + i * 2.6
                fade = (1 - i / 11) ** 1.4
                tc   = (f"#{int(cr * fade):02x}"
                        f"{int(cg * fade):02x}"
                        f"{int(cb * fade):02x}")
                tr   = max(0.5, r * fade)
                c.create_oval(tx - tr, y - tr, tx + tr, y + tr,
                              fill=tc, outline="", tags="p")

            c.create_oval(x - r, y - r, x + r, y + r,   # bright head
                          fill=color, outline="", tags="p")

        self.root.after(33, self._anim_tick)

    def _pulse_running(self):
        """Gently oscillate the timer text color between ACCENT and a brighter shade."""
        if not self.running:
            return
        t = datetime.now().microsecond / 1_000_000   # 0..1 per second
        f = (math.sin(t * math.pi * 2) + 1) / 2     # 0..1 sinusoidal
        col = (f"#{int(0xE9 + 0x16 * f):02x}"
               f"{int(0x45 + 0x3B * f):02x}"
               f"{int(0x60 + 0x40 * f):02x}")
        self._timer_lbl.config(fg=col)
        self.root.after(50, self._pulse_running)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _tint(self, hex_color: str, factor: float = 0.50) -> str:
        """Blend hex_color with BG2 (#16213E) to create a clearly tinted row bg."""
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        br, bg_, bb = 0x16, 0x21, 0x3E          # BG2
        r = int(r * factor + br * (1 - factor))
        g = int(g * factor + bg_ * (1 - factor))
        b = int(b * factor + bb * (1 - factor))
        return f"#{r:02x}{g:02x}{b:02x}"


def main():
    root = tk.Tk()
    TimeTrackerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
