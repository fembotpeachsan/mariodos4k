#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HALTMANN WORKS CO / Flames Co Presents — MariOS 64 (Tribute)
=================================================================
A self‑contained, files‑off Python/Tkinter desktop "room" environment
inspired by Microsoft Bob and Nintendo castle rooms. Includes:
  • Startup splash: "HALTMANN WORKS CO / Flames Co Presents"
  • Bob-like rooms (Foyer, Library, Workshop, Throne) with draggable icons
  • Unremovable "special" app icons that launch:
      - TextPad (mini notepad)
      - Calendar (month view)
      - HALT-DOS (terminal-like shell)
      - Web (simple search launcher via default browser)
      - Settings (theme + edit mode)
      - Assistant Maker (custom chatter)
      - Mario Tech Demo (Tkinter 60 FPS platformer, no external assets)
  • Decorate/Edit mode with duplication, removal (if removable), resize, animate toggle
  • Save/Load room layouts as JSON snapshots

Pure Python standard library + Tkinter only.
Tested on CPython 3.10+; should work on Windows 11.
This is a non-commercial fan homage; no Nintendo assets are included.
"""

import os
import sys
import json
import math
import time
import random
import webbrowser
import datetime
import calendar
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

APP_TITLE = "HALTMANN WORKS CO — MariOS 64 (Tribute)"
FRAME_MS = 16  # ~60 FPS
RNG_SEED = 1337  # determinism for any randomized decorations

# ----------------------------- Utility helpers -----------------------------

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ----------------------------- Icon/Room Model -----------------------------

class Icon:
    """A canvas-based icon made from shapes+text, representing either an app or a decoration."""
    def __init__(self, tag, title, kind, app_id=None, x=100, y=100, w=96, h=72,
                 fill="#2c3e50", fg="#ecf0f1", unremovable=False, animate=False):
        self.tag = tag            # per-icon tag e.g., "icon_5"
        self.title = title        # label drawn on icon
        self.kind = kind          # "app" | "decor"
        self.app_id = app_id      # optional app id if kind == "app"
        self.x, self.y = x, y     # top-left
        self.w, self.h = w, h
        self.fill, self.fg = fill, fg
        self.unremovable = unremovable
        self.animate = animate
        self.items = []           # canvas item ids
        self.vphase = random.random() * math.tau  # for bob animation

    def to_dict(self):
        return {
            "tag": self.tag, "title": self.title, "kind": self.kind,
            "app_id": self.app_id, "x": self.x, "y": self.y, "w": self.w, "h": self.h,
            "fill": self.fill, "fg": self.fg, "unremovable": self.unremovable, "animate": self.animate
        }

    @staticmethod
    def from_dict(d):
        return Icon(
            tag=d["tag"], title=d["title"], kind=d["kind"],
            app_id=d.get("app_id"), x=d["x"], y=d["y"], w=d["w"], h=d["h"],
            fill=d.get("fill", "#2c3e50"), fg=d.get("fg", "#ecf0f1"),
            unremovable=bool(d.get("unremovable", False)),
            animate=bool(d.get("animate", False))
        )

class Room:
    """A room in the desktop, with background rendering + a set of icons."""
    def __init__(self, name, theme="foyer"):
        self.name = name
        self.theme = theme
        self.icons = []  # list[Icon]

    def to_dict(self):
        return {"name": self.name, "theme": self.theme, "icons": [ic.to_dict() for ic in self.icons]}

    @staticmethod
    def from_dict(d):
        r = Room(d["name"], d.get("theme", "foyer"))
        r.icons = [Icon.from_dict(ic) for ic in d.get("icons", [])]
        return r

# ----------------------------- Desktop Application -----------------------------

class HaltmannDesktop(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x720")
        self.minsize(980, 640)
        self.configure(bg="#151515")
        self.icon_counter = 0
        random.seed(RNG_SEED)

        # State
        self.rooms = {}
        self.current_room = None
        self.edit_mode = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")
        self.assistant_name = tk.StringVar(value="Toad (Assistant)")
        self.assistant_persona = ["Hi! Click an icon to open an app.", "Tip: Right‑click icons for options.",
                                  "Type 'help' in HALT‑DOS for commands."]

        # Drag state
        self.dragging = False
        self.drag_tag = None
        self.drag_offx = 0
        self.drag_offy = 0

        self._build_menu()
        self._build_ui()
        self._seed_rooms()
        self._show_splash_then_start()

        # Animation loop for icon "bob" and ambient effects
        self.after(FRAME_MS, self._tick)

    # ----------------------------- UI Construction -----------------------------

    def _build_menu(self):
        m = tk.Menu(self)
        self.config(menu=m)

        fm = tk.Menu(m, tearoff=False)
        fm.add_command(label="Save Layout…", command=self.save_layout)
        fm.add_command(label="Load Layout…", command=self.load_layout)
        fm.add_separator()
        fm.add_command(label="Exit", command=self.destroy)
        m.add_cascade(label="File", menu=fm)

        vm = tk.Menu(m, tearoff=False)
        vm.add_checkbutton(label="Edit/Decorate Mode", variable=self.edit_mode, command=self._refresh_status)
        rooms_menu = tk.Menu(vm, tearoff=False)
        # will populate later after rooms exist
        self.rooms_menu = rooms_menu
        vm.add_cascade(label="Rooms", menu=rooms_menu)
        m.add_cascade(label="View", menu=vm)

        am = tk.Menu(m, tearoff=False)
        am.add_command(label="TextPad", command=self.open_textpad)
        am.add_command(label="Calendar", command=self.open_calendar)
        am.add_command(label="HALT‑DOS Terminal", command=self.open_terminal)
        am.add_command(label="Web Search", command=self.open_web_search)
        am.add_command(label="Settings", command=self.open_settings)
        am.add_command(label="Assistant Maker", command=self.open_assistant_maker)
        am.add_separator()
        am.add_command(label="Mario Tech Demo (60 FPS)", command=self.open_mario_demo)
        m.add_cascade(label="Apps", menu=am)

        hm = tk.Menu(m, tearoff=False)
        hm.add_command(label="About", command=self._about)
        hm.add_command(label="Keys/Help", command=self._keys_help)
        m.add_cascade(label="Help", menu=hm)

    def _build_ui(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Left panel: room list + toggles
        left = ttk.Frame(self, padding=8)
        left.grid(row=0, column=0, sticky="nsw")
        ttk.Label(left, text="Rooms", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.room_list = tk.Listbox(left, height=10, activestyle="dotbox", exportselection=False)
        self.room_list.pack(fill="y", expand=False, pady=(4, 8))
        self.room_list.bind("<<ListboxSelect>>", self._on_room_select)

        ttk.Checkbutton(left, text="Edit/Decorate Mode", variable=self.edit_mode,
                        command=self._refresh_status).pack(anchor="w", pady=4)

        ttk.Button(left, text="New Room…", command=self._new_room_dialog).pack(fill="x", pady=2)
        ttk.Button(left, text="Duplicate Room", command=self._duplicate_current_room).pack(fill="x", pady=2)
        ttk.Button(left, text="Delete Room", command=self._delete_current_room).pack(fill="x", pady=2)

        # Center: canvas room
        center = ttk.Frame(self, padding=(0, 6, 0, 0))
        center.grid(row=0, column=1, sticky="nsew")
        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(center, bg="#202020", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double)
        self.canvas.bind("<Button-3>", self._on_canvas_right)

        # Right: assistant chat
        right = ttk.Frame(self, padding=8)
        right.grid(row=0, column=2, sticky="nse")
        ttk.Label(right, textvariable=self.assistant_name, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.assistant_log = tk.Text(right, width=32, height=24, state="disabled", wrap="word")
        self.assistant_log.pack(fill="both", expand=True, pady=(4, 6))
        self.assistant_entry = ttk.Entry(right)
        self.assistant_entry.pack(fill="x")
        self.assistant_entry.bind("<Return>", lambda e: self._assistant_send())
        ttk.Button(right, text="Send", command=self._assistant_send).pack(anchor="e", pady=(4,0))

        # Status bar
        status = ttk.Frame(self, padding=(8, 2, 8, 4))
        status.grid(row=1, column=0, columnspan=3, sticky="ew")
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self.theme_var = tk.StringVar(value="Foyer")
        ttk.Label(status, textvariable=self.theme_var).grid(row=0, column=1, sticky="e")

        # Context menu for icons
        self.icon_menu = tk.Menu(self, tearoff=False)
        self.icon_menu.add_command(label="Open", command=lambda: self._open_icon(self._ctx_icon_tag))
        self.icon_menu.add_command(label="Duplicate", command=lambda: self._duplicate_icon(self._ctx_icon_tag))
        self.icon_menu.add_command(label="Remove", command=lambda: self._remove_icon(self._ctx_icon_tag))
        self.icon_menu.add_command(label="Resize…", command=lambda: self._resize_icon_dialog(self._ctx_icon_tag))
        self.icon_menu.add_checkbutton(label="Animate", command=lambda: self._toggle_icon_anim(self._ctx_icon_tag))
        self._ctx_icon_tag = None

    # ----------------------------- Splash -----------------------------

    def _show_splash_then_start(self):
        splash = tk.Toplevel(self)
        splash.overrideredirect(True)
        splash.configure(bg="#000000")
        w, h = 560, 300
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 3
        splash.geometry(f"{w}x{h}+{x}+{y}")
        c = tk.Canvas(splash, bg="#000000", highlightthickness=0, width=w, height=h)
        c.pack(fill="both", expand=True)

        # Startup text
        c.create_text(w//2, 80, text="HALTMANN WORKS CO", fill="#FFD166", font=("Segoe UI", 20, "bold"))
        c.create_text(w//2, 120, text="/ Flames Co Presents /", fill="#EF476F", font=("Segoe UI", 14, "bold"))
        c.create_text(w//2, 170, text="MariOS 64 — Tribute Build", fill="#06D6A0", font=("Segoe UI", 16, "bold"))
        c.create_text(w//2, 220, text="Press any key to begin", fill="#FFFFFF", font=("Segoe UI", 11))
        c.create_text(w//2, 260, text="(Fan-made. Not affiliated with Nintendo.)", fill="#AAAAAA", font=("Segoe UI", 9))

        def close_splash(*_):
            splash.destroy()
            self.deiconify()
            self._render_room()

        splash.bind("<Key>", close_splash)
        splash.bind("<Button-1>", close_splash)
        self.withdraw()  # hide main during splash
        # Auto close after 3 seconds in case user doesn't press anything
        self.after(3000, close_splash)

    # ----------------------------- Rooms/Seeding -----------------------------

    def _seed_rooms(self):
        # Create default rooms with some special app icons
        for rn, theme in [("Foyer", "foyer"), ("Library", "library"), ("Workshop", "workshop"), ("Throne", "throne")]:
            self.rooms[rn] = Room(rn, theme)

        self.current_room = "Foyer"
        self._rebuild_rooms_menu()
        self._refresh_room_list()

        # Place special app icons in foyer
        r = self.rooms["Foyer"]
        r.icons.extend([
            self._mk_app_icon("Mario Demo", "mario", 120, 120, fill="#e74c3c"),
            self._mk_app_icon("HALT‑DOS", "terminal", 260, 120, fill="#2ecc71"),
            self._mk_app_icon("TextPad", "textpad", 400, 120, fill="#3498db"),
            self._mk_app_icon("Web", "web", 540, 120, fill="#9b59b6"),
            self._mk_app_icon("Calendar", "calendar", 680, 120, fill="#f1c40f", fg="#000000"),
            self._mk_app_icon("Settings", "settings", 820, 120, fill="#e67e22"),
            self._mk_app_icon("Assistant", "assistant", 960, 120, fill="#95a5a6"),
        ])

        # Some decorations (removable)
        for i in range(5):
            x = 160 + i*160
            r.icons.append(self._mk_decor_icon(f"Coin {i+1}", x, 320, w=40, h=40, fill="#f39c12", animate=True))

        # Other rooms get a few basics
        self.rooms["Library"].icons.append(self._mk_app_icon("TextPad", "textpad", 140, 150, fill="#3498db"))
        self.rooms["Workshop"].icons.append(self._mk_app_icon("Settings", "settings", 140, 150, fill="#e67e22"))
        self.rooms["Throne"].icons.append(self._mk_app_icon("HALT‑DOS", "terminal", 140, 150, fill="#2ecc71"))

    def _mk_app_icon(self, title, app_id, x, y, fill="#2c3e50", fg="#ecf0f1"):
        self.icon_counter += 1
        tag = f"icon_{self.icon_counter}"
        return Icon(tag, title, "app", app_id=app_id, x=x, y=y, w=110, h=80,
                    fill=fill, fg=fg, unremovable=True, animate=False)

    def _mk_decor_icon(self, title, x, y, w=80, h=60, fill="#2c3e50", fg="#ecf0f1", animate=False):
        self.icon_counter += 1
        tag = f"icon_{self.icon_counter}"
        return Icon(tag, title, "decor", app_id=None, x=x, y=y, w=w, h=h,
                    fill=fill, fg=fg, unremovable=False, animate=animate)

    def _rebuild_rooms_menu(self):
        self.rooms_menu.delete(0, "end")
        for rn in sorted(self.rooms.keys()):
            self.rooms_menu.add_command(label=rn, command=lambda rnn=rn: self._switch_room(rnn))

    def _refresh_room_list(self):
        self.room_list.delete(0, "end")
        for rn in sorted(self.rooms.keys()):
            self.room_list.insert("end", rn)
        try:
            idx = list(sorted(self.rooms.keys())).index(self.current_room)
            self.room_list.select_set(idx)
        except Exception:
            pass

    # ----------------------------- Canvas Rendering -----------------------------

    def _render_room(self):
        self.canvas.delete("all")
        rm = self.rooms[self.current_room]
        self.theme_var.set(f"Room: {rm.name} / Theme: {rm.theme}")
        self._draw_room_background(rm.theme)

        for ic in rm.icons:
            self._draw_icon(ic)

        self._refresh_status()

    def _draw_room_background(self, theme):
        W = self.canvas.winfo_width() or self.canvas.winfo_reqwidth()
        H = self.canvas.winfo_height() or self.canvas.winfo_reqheight()
        # Simple gradient/backdrop suggestions per theme
        if theme == "foyer":
            top, bottom = "#2b2d42", "#8d99ae"
        elif theme == "library":
            top, bottom = "#3b2f2f", "#a67c52"
        elif theme == "workshop":
            top, bottom = "#1b262c", "#0f4c75"
        elif theme == "throne":
            top, bottom = "#3d1e6d", "#c44536"
        else:
            top, bottom = "#202020", "#404040"

        # vertical gradient by rectangles
        steps = 32
        for i in range(steps):
            t = i / (steps-1)
            r = int((1-t)*int(top[1:3],16) + t*int(bottom[1:3],16))
            g = int((1-t)*int(top[3:5],16) + t*int(bottom[3:5],16))
            b = int((1-t)*int(top[5:7],16) + t*int(bottom[5:7],16))
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.canvas.create_rectangle(0, int(H*(i/steps)), W, int(H*((i+1)/steps))+2, fill=color, outline=color)

        # simple castle floor
        self.canvas.create_rectangle(0, H-80, W, H, fill="#3b3b3b", outline="")

        # pillars
        for px in range(80, W, 220):
            self.canvas.create_rectangle(px-20, 100, px+20, H-80, fill="#dfe6e9", outline="#636e72")
            self.canvas.create_oval(px-25, 70, px+25, 120, fill="#dfe6e9", outline="#636e72")

        # title banner
        self.canvas.create_rectangle(0, 0, W, 36, fill="#000000", outline="")
        self.canvas.create_text(W//2, 18, text=f"Princess Peach's Castle — {self.current_room}",
                                fill="#ffffff", font=("Segoe UI", 12, "bold"))

    def _draw_icon(self, ic: Icon):
        # Draw rounded rectangle + title
        x, y, w, h = ic.x, ic.y, ic.w, ic.h
        tag = ic.tag
        base = "icon"
        # Rounded rectangle via 4 arcs + rects
        r = 12
        items = []
        items.append(self.canvas.create_rectangle(x+r, y, x+w-r, y+h, fill=ic.fill, outline="#000000", width=2, tags=(base, tag)))
        items.append(self.canvas.create_rectangle(x, y+r, x+w, y+h-r, fill=ic.fill, outline="#000000", width=2, tags=(base, tag)))
        items.append(self.canvas.create_oval(x, y, x+2*r, y+2*r, fill=ic.fill, outline="#000000", width=2, tags=(base, tag)))
        items.append(self.canvas.create_oval(x+w-2*r, y, x+w, y+2*r, fill=ic.fill, outline="#000000", width=2, tags=(base, tag)))
        items.append(self.canvas.create_oval(x, y+h-2*r, x+2*r, y+h, fill=ic.fill, outline="#000000", width=2, tags=(base, tag)))
        items.append(self.canvas.create_oval(x+w-2*r, y+h-2*r, x+w, y+h, fill=ic.fill, outline="#000000", width=2, tags=(base, tag)))

        # Inner glyph: draw a minimalist icon based on app_id or decor
        self._draw_icon_glyph(ic, items)

        # Title
        items.append(self.canvas.create_text(x+w//2, y+h-12, text=ic.title, fill=ic.fg,
                                             font=("Segoe UI", 9, "bold"), tags=(base, tag)))
        ic.items = items

    def _draw_icon_glyph(self, ic: Icon, items_accum):
        # draw a simple glyph in the icon area
        x, y, w, h = ic.x, ic.y, ic.w, ic.h
        cx, cy = x + w//2, y + h//2 - 8
        tag = ic.tag
        base = "icon"

        def add(item_id):
            items_accum.append(item_id)

        aid = ic.app_id if ic.kind == "app" else "decor"

        if aid == "mario":
            # A very simple plumber silhouette: cap + face rectangle
            add(self.canvas.create_oval(cx-22, cy-24, cx+22, cy-2, fill="#c0392b", outline="", tags=(base, tag)))
            add(self.canvas.create_rectangle(cx-10, cy-12, cx+10, cy+14, fill="#fce5cd", outline="", tags=(base, tag)))
            add(self.canvas.create_rectangle(cx-22, cy-20, cx+22, cy-14, fill="#e74c3c", outline="", tags=(base, tag)))
        elif aid == "terminal":
            add(self.canvas.create_rectangle(cx-26, cy-18, cx+26, cy+18, fill="#1e272e", outline="#d2dae2", tags=(base, tag)))
            add(self.canvas.create_text(cx-12, cy, text=">", fill="#d2dae2", font=("Consolas", 16, "bold"), tags=(base, tag)))
            add(self.canvas.create_line(cx-4, cy+8, cx+16, cy+8, fill="#d2dae2", width=2, tags=(base, tag)))
        elif aid == "textpad":
            add(self.canvas.create_rectangle(cx-22, cy-20, cx+22, cy+20, fill="#ecf0f1", outline="#2c3e50", tags=(base, tag)))
            for i in range(5):
                add(self.canvas.create_line(cx-18, cy-12 + i*8, cx+18, cy-12 + i*8, fill="#2c3e50", tags=(base, tag)))
        elif aid == "web":
            add(self.canvas.create_oval(cx-24, cy-24, cx+24, cy+24, outline="#ffffff", width=2, tags=(base, tag)))
            add(self.canvas.create_line(cx-24, cy, cx+24, cy, fill="#ffffff", width=2, tags=(base, tag)))
            add(self.canvas.create_line(cx, cy-24, cx, cy+24, fill="#ffffff", width=2, tags=(base, tag)))
            add(self.canvas.create_arc(cx-24, cy-24, cx+24, cy+24, start=30, extent=120, style="arc", outline="#ffffff", width=2, tags=(base, tag)))
            add(self.canvas.create_arc(cx-24, cy-24, cx+24, cy+24, start=210, extent=120, style="arc", outline="#ffffff", width=2, tags=(base, tag)))
        elif aid == "calendar":
            add(self.canvas.create_rectangle(cx-24, cy-18, cx+24, cy+20, fill="#ecf0f1", outline="#c0392b", width=3, tags=(base, tag)))
            add(self.canvas.create_rectangle(cx-24, cy-18, cx+24, cy-6, fill="#c0392b", outline="", tags=(base, tag)))
            add(self.canvas.create_text(cx, cy+6, text=str(datetime.datetime.now().day), fill="#2c3e50", font=("Segoe UI", 16, "bold"), tags=(base, tag)))
        elif aid == "settings":
            # gear
            for i in range(8):
                ang = i * (math.tau/8)
                ax = cx + math.cos(ang) * 20
                ay = cy + math.sin(ang) * 20
                add(self.canvas.create_rectangle(ax-4, ay-12, ax+4, ay-4, fill="#2c3e50", outline="", tags=(base, tag)))
            add(self.canvas.create_oval(cx-14, cy-14, cx+14, cy+14, fill="#95a5a6", outline="#2c3e50", tags=(base, tag)))
        elif aid == "assistant":
            add(self.canvas.create_oval(cx-22, cy-18, cx+22, cy+18, fill="#1abc9c", outline="", tags=(base, tag)))
            add(self.canvas.create_text(cx, cy-2, text=":)", fill="#ffffff", font=("Segoe UI", 16, "bold"), tags=(base, tag)))
        else:
            # decor coin/star
            add(self.canvas.create_oval(cx-16, cy-16, cx+16, cy+16, fill="#f1c40f", outline="#e67e22", width=2, tags=(base, tag)))
            add(self.canvas.create_text(cx, cy, text="★", fill="#7f8c8d", font=("Segoe UI", 16, "bold"), tags=(base, tag)))

    # ----------------------------- Interaction -----------------------------

    def _icon_under_cursor(self, event):
        x, y = event.x, event.y
        items = self.canvas.find_overlapping(x, y, x, y)
        # return most recent with "icon" tag
        for it in reversed(items):
            tags = self.canvas.gettags(it)
            if "icon" in tags:
                # second tag is per-icon
                for tg in tags:
                    if tg.startswith("icon_"):
                        return tg
        return None

    def _get_icon_by_tag(self, tag):
        rm = self.rooms[self.current_room]
        for ic in rm.icons:
            if ic.tag == tag:
                return ic
        return None

    def _on_canvas_click(self, event):
        tag = self._icon_under_cursor(event)
        if tag:
            ic = self._get_icon_by_tag(tag)
            if ic is None:
                return
            if self.edit_mode.get():
                self.dragging = True
                self.drag_tag = tag
                self.drag_offx = event.x - ic.x
                self.drag_offy = event.y - ic.y
            else:
                # selection feedback
                self.canvas.scale(tag, ic.x + ic.w/2, ic.y + ic.h/2, 1.05, 1.05)
                self.after(90, lambda: self.canvas.scale(tag, ic.x + ic.w/2, ic.y + ic.h/2, 1/1.05, 1/1.05))
        else:
            # empty space click: maybe drop a decor in edit mode
            if self.edit_mode.get():
                self._add_random_decor(event.x, event.y)

    def _on_canvas_drag(self, event):
        if self.dragging and self.drag_tag:
            ic = self._get_icon_by_tag(self.drag_tag)
            if ic:
                nx = event.x - self.drag_offx
                ny = event.y - self.drag_offy
                ic.x = nx
                ic.y = ny
                self._render_room()

    def _on_canvas_release(self, event):
        if self.dragging:
            self.dragging = False
            self.drag_tag = None

    def _on_canvas_double(self, event):
        tag = self._icon_under_cursor(event)
        if tag:
            self._open_icon(tag)

    def _on_canvas_right(self, event):
        tag = self._icon_under_cursor(event)
        if not tag:
            return
        self._ctx_icon_tag = tag
        ic = self._get_icon_by_tag(tag)
        self.icon_menu.entryconfig("Remove", state=("disabled" if ic and ic.unremovable else "normal"))
        # update Animate check
        # Tk menu checkbuttons don't show state easily; we just toggle on click.
        self.icon_menu.tk_popup(event.x_root, event.y_root)

    def _open_icon(self, tag):
        ic = self._get_icon_by_tag(tag)
        if not ic:
            return
        if ic.kind == "decor":
            # fun sparkle
            self._sparkle(ic)
            return
        aid = ic.app_id
        if aid == "mario":
            self.open_mario_demo()
        elif aid == "terminal":
            self.open_terminal()
        elif aid == "textpad":
            self.open_textpad()
        elif aid == "web":
            self.open_web_search()
        elif aid == "calendar":
            self.open_calendar()
        elif aid == "settings":
            self.open_settings()
        elif aid == "assistant":
            self._assistant_say(random.choice(self.assistant_persona))
        else:
            messagebox.showinfo("Open", f"App '{ic.title}' is not wired yet.")

    def _duplicate_icon(self, tag):
        ic = self._get_icon_by_tag(tag)
        if not ic:
            return
        new_ic = Icon(
            tag=f"icon_{self.icon_counter+1}", title=ic.title, kind=ic.kind, app_id=ic.app_id,
            x=ic.x+24, y=ic.y+24, w=ic.w, h=ic.h, fill=ic.fill, fg=ic.fg,
            unremovable=False if ic.kind == "decor" else ic.unremovable, animate=ic.animate
        )
        self.icon_counter += 1
        self.rooms[self.current_room].icons.append(new_ic)
        self._render_room()

    def _remove_icon(self, tag):
        ic = self._get_icon_by_tag(tag)
        if not ic or ic.unremovable:
            return
        rm = self.rooms[self.current_room]
        rm.icons = [k for k in rm.icons if k.tag != tag]
        self._render_room()

    def _resize_icon_dialog(self, tag):
        ic = self._get_icon_by_tag(tag)
        if not ic:
            return
        w = simpledialog.askinteger("Resize", "Width (px):", initialvalue=ic.w, minvalue=40, maxvalue=320, parent=self)
        if w is None: return
        h = simpledialog.askinteger("Resize", "Height (px):", initialvalue=ic.h, minvalue=40, maxvalue=240, parent=self)
        if h is None: return
        ic.w, ic.h = int(w), int(h)
        self._render_room()

    def _toggle_icon_anim(self, tag):
        ic = self._get_icon_by_tag(tag)
        if not ic: return
        ic.animate = not ic.animate

    def _add_random_decor(self, x, y):
        colors = ["#f39c12", "#1abc9c", "#e67e22", "#9b59b6", "#2ecc71", "#3498db", "#e74c3c"]
        title = random.choice(["Coin", "Star", "Lamp", "Block", "Mush", "Shell"])
        ic = self._mk_decor_icon(title, x, y, w=random.randint(48, 88), h=random.randint(40, 72),
                                 fill=random.choice(colors), animate=random.choice([True, False]))
        self.rooms[self.current_room].icons.append(ic)
        self._render_room()

    # ----------------------------- Assistant -----------------------------

    def _assistant_log(self, who, text):
        self.assistant_log.configure(state="normal")
        self.assistant_log.insert("end", f"{now_str()}  {who}: {text}\n")
        self.assistant_log.configure(state="disabled")
        self.assistant_log.see("end")

    def _assistant_say(self, text):
        self._assistant_log(self.assistant_name.get(), text)

    def _assistant_send(self):
        msg = self.assistant_entry.get().strip()
        if not msg:
            return
        self.assistant_entry.delete(0, "end")
        self._assistant_log("You", msg)
        # simple intent detection
        lower = msg.lower()
        if "open" in lower and "mario" in lower:
            self._assistant_say("Opening Mario Tech Demo…")
            self.open_mario_demo()
        elif "help" in lower:
            self._assistant_say("Try: 'open mario', 'tell a joke', or 'what can you do?'")
        elif "joke" in lower:
            self._assistant_say("Why did the Koopa cross the road? To get to the other side‑quest.")
        elif "what can you do" in lower or "capabilities" in lower:
            self._assistant_say("I can open apps, give tips, and brighten your day.")
        else:
            self._assistant_say(random.choice(self.assistant_persona))

    # ----------------------------- Status/Rooms ops -----------------------------

    def _refresh_status(self):
        em = "ON" if self.edit_mode.get() else "OFF"
        self.status_var.set(f"Edit/Decorate Mode: {em} — Room: {self.current_room} — {len(self.rooms[self.current_room].icons)} items")

    def _switch_room(self, rn):
        if rn not in self.rooms:
            return
        self.current_room = rn
        self._refresh_room_list()
        self._render_room()

    def _on_room_select(self, _e):
        try:
            idx = self.room_list.curselection()[0]
            rn = list(sorted(self.rooms.keys()))[idx]
            self._switch_room(rn)
        except Exception:
            pass

    def _new_room_dialog(self):
        rn = simpledialog.askstring("New Room", "Room name:", initialvalue="New Room", parent=self)
        if not rn: return
        if rn in self.rooms:
            messagebox.showerror("Exists", "A room with that name already exists.")
            return
        theme = random.choice(["foyer", "library", "workshop", "throne"])
        self.rooms[rn] = Room(rn, theme)
        self._rebuild_rooms_menu()
        self._refresh_room_list()
        self._switch_room(rn)

    def _duplicate_current_room(self):
        rn = self.current_room
        nrn = rn + " (Copy)"
        i = 1
        while nrn in self.rooms:
            i += 1
            nrn = f"{rn} (Copy {i})"
        src = self.rooms[rn]
        clone = Room(nrn, src.theme)
        clone.icons = [Icon.from_dict(ic.to_dict()) for ic in src.icons]
        self.rooms[nrn] = clone
        self._rebuild_rooms_menu()
        self._refresh_room_list()

    def _delete_current_room(self):
        if len(self.rooms) <= 1:
            messagebox.showinfo("Can't Delete", "At least one room must exist.")
            return
        rn = self.current_room
        if messagebox.askyesno("Delete Room", f"Delete room '{rn}'?"):
            del self.rooms[rn]
            self.current_room = sorted(self.rooms.keys())[0]
            self._rebuild_rooms_menu()
            self._refresh_room_list()
            self._render_room()

    # ----------------------------- Persistence -----------------------------

    def save_layout(self):
        data = {
            "app_title": APP_TITLE,
            "time": now_str(),
            "rooms": [self.rooms[r].to_dict() for r in sorted(self.rooms.keys())]
        }
        path = filedialog.asksaveasfilename(title="Save Layout", defaultextension=".json",
                                            filetypes=[("JSON Files", "*.json")], initialfile="haltmann_layout.json")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.status_var.set(f"Saved layout to {path}")

    def load_layout(self):
        path = filedialog.askopenfilename(title="Load Layout", defaultextension=".json",
                                          filetypes=[("JSON Files", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.rooms.clear()
            for rd in data.get("rooms", []):
                r = Room.from_dict(rd)
                self.rooms[r.name] = r
            if not self.rooms:
                raise ValueError("No rooms found in file")
            self.current_room = sorted(self.rooms.keys())[0]
            self._rebuild_rooms_menu()
            self._refresh_room_list()
            self._render_room()
            self.status_var.set(f"Loaded layout from {path}")
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load: {e}")

    # ----------------------------- Tickers/FX -----------------------------

    def _tick(self):
        # icon bob + simple sparkle anim
        rm = self.rooms.get(self.current_room)
        if rm:
            changed = False
            for ic in rm.icons:
                if ic.animate:
                    ic.vphase += 0.08
                    dy = math.sin(ic.vphase) * 0.6
                    ic.y += dy
                    ic.y -= dy  # net zero per tick; we only want redraw shimmer; minor shift for effect
                    changed = True
            if changed:
                self._render_room()
        self.after(FRAME_MS, self._tick)

    def _sparkle(self, ic: Icon):
        # brief sparkle effect over the icon
        if not ic.items:
            return
        bbox = (ic.x-8, ic.y-8, ic.x+ic.w+8, ic.y+ic.h+8)
        for _ in range(12):
            x = random.randint(bbox[0], bbox[2])
            y = random.randint(bbox[1], bbox[3])
            s = self.canvas.create_oval(x-2, y-2, x+2, y+2, fill="#ffffff", outline="")
            self.canvas.after(random.randint(60, 240), lambda sid=s: self.canvas.delete(sid))

    # ----------------------------- Apps -----------------------------

    def open_textpad(self):
        TextPad(self)

    def open_calendar(self):
        CalendarWin(self)

    def open_terminal(self):
        HaltDOS(self)

    def open_web_search(self):
        WebSearch(self)

    def open_settings(self):
        SettingsWin(self)

    def open_assistant_maker(self):
        AssistantMaker(self)

    def open_mario_demo(self):
        MarioDemo(self)

    # ----------------------------- Help -----------------------------

    def _about(self):
        messagebox.showinfo("About",
            "HALTMANN WORKS CO / Flames Co Presents\n"
            "MariOS 64 — Tribute Build (Tkinter)\n\n"
            "Fan-made homage to Microsoft Bob x Nintendo castle desktops.\n"
            "Includes a 60 FPS Mario-style tech demo with synthetic shapes.\n"
            "No Nintendo assets are included.")

    def _keys_help(self):
        messagebox.showinfo("Keys/Help",
            "General:\n"
            " • Double-click an icon to open it.\n"
            " • Right-click an icon for options (Duplicate/Remove/Resize/Animate).\n"
            " • Toggle Edit/Decorate Mode from View menu or left sidebar.\n"
            " • In Edit Mode, click empty space to drop a random decoration.\n\n"
            "Mario Demo:\n"
            " • Left/Right = Move, Space/Z = Jump, R = Reset level, Esc = Close demo.\n"
            " • 60 FPS with deterministic step.")

# ----------------------------- TextPad -----------------------------

class TextPad(tk.Toplevel):
    def __init__(self, app: HaltmannDesktop):
        super().__init__(app)
        self.title("TextPad")
        self.geometry("720x480")
        self.text = tk.Text(self, wrap="word", undo=True)
        self.text.pack(fill="both", expand=True)
        self._build_menu()

    def _build_menu(self):
        m = tk.Menu(self)
        self.config(menu=m)
        fm = tk.Menu(m, tearoff=False)
        fm.add_command(label="Open…", command=self._open)
        fm.add_command(label="Save As…", command=self._save_as)
        fm.add_separator()
        fm.add_command(label="Exit", command=self.destroy)
        m.add_cascade(label="File", menu=fm)

    def _open(self):
        path = filedialog.askopenfilename(title="Open", filetypes=[("Text Files","*.txt"),("All Files","*.*")])
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            self.text.delete("1.0", "end")
            self.text.insert("1.0", data)
        except Exception as e:
            messagebox.showerror("Open Error", str(e))

    def _save_as(self):
        path = filedialog.asksaveasfilename(title="Save As", defaultextension=".txt",
                                            filetypes=[("Text Files","*.txt"),("All Files","*.*")])
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text.get("1.0", "end-1c"))
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

# ----------------------------- Calendar -----------------------------

class CalendarWin(tk.Toplevel):
    def __init__(self, app: HaltmannDesktop):
        super().__init__(app)
        self.title("Calendar")
        self.geometry("360x360")
        self.resizable(False, False)
        self.lbl = ttk.Label(self, font=("Segoe UI", 12, "bold"))
        self.lbl.pack(pady=8)
        self.txt = tk.Text(self, width=34, height=12, state="disabled")
        self.txt.pack(padx=8, pady=8)
        self._refresh()

    def _refresh(self):
        today = datetime.date.today()
        cal = calendar.TextCalendar(calendar.SUNDAY)
        s = cal.formatmonth(theyear=today.year, themonth=today.month)
        self.lbl.config(text=f"{today.strftime('%B %Y')}")
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", s)
        self.txt.configure(state="disabled")

# ----------------------------- HALT-DOS Terminal -----------------------------

class HaltDOS(tk.Toplevel):
    def __init__(self, app: HaltmannDesktop):
        super().__init__(app)
        self.app = app
        self.title("HALT‑DOS Terminal")
        self.geometry("800x440")
        self.text = tk.Text(self, bg="#111", fg="#ddd", insertbackground="#ddd")
        self.text.pack(fill="both", expand=True)
        self.entry = ttk.Entry(self)
        self.entry.pack(fill="x")
        self.entry.bind("<Return>", lambda e: self._run_cmd())
        self._println("HALT‑DOS v0.64 — type 'help' for commands")
        self.entry.focus_set()

    def _println(self, s=""):
        self.text.insert("end", s + "\n")
        self.text.see("end")

    def _run_cmd(self):
        cmd = self.entry.get().strip()
        self.entry.delete(0, "end")
        self._println(f"> {cmd}")
        if not cmd:
            return
        parts = cmd.split()
        name = parts[0].lower()
        args = parts[1:]

        try:
            if name in ("help", "?"):
                self._println("Commands: help, time, apps, rooms, open <app>, room <name>, echo <msg>, clear, about, exit")
            elif name == "time":
                self._println(now_str())
            elif name == "apps":
                self._println("Apps: mario, terminal, textpad, web, calendar, settings, assistant")
            elif name == "rooms":
                self._println("Rooms: " + ", ".join(sorted(self.app.rooms.keys())))
            elif name == "open" and args:
                self._open_app(args[0])
            elif name == "room" and args:
                rn = " ".join(args)
                if rn in self.app.rooms:
                    self.app._switch_room(rn)
                    self._println(f"Switched to room '{rn}'")
                else:
                    self._println(f"No such room: {rn}")
            elif name == "echo":
                self._println(" ".join(args))
            elif name == "clear":
                self.text.delete("1.0", "end")
            elif name == "about":
                self._println("HALTMANN WORKS CO / Flames Co Presents — MariOS 64 Tribute")
                self._println("Fan-made room desktop with Mario-style demo. No external assets.")
            elif name == "exit":
                self.destroy()
            else:
                self._println("Unknown command. Try 'help'.")
        except Exception as e:
            self._println(f"Error: {e}")

    def _open_app(self, key):
        key = key.lower()
        mapping = {
            "mario": self.app.open_mario_demo,
            "terminal": self.app.open_terminal,
            "textpad": self.app.open_textpad,
            "web": self.app.open_web_search,
            "calendar": self.app.open_calendar,
            "settings": self.app.open_settings,
            "assistant": self.app.open_assistant_maker,
        }
        fn = mapping.get(key)
        if fn:
            fn()
            self._println(f"Opened {key}.")
        else:
            self._println(f"No such app: {key}")

# ----------------------------- Web Search -----------------------------

class WebSearch(tk.Toplevel):
    def __init__(self, app: HaltmannDesktop):
        super().__init__(app)
        self.title("Web Search")
        self.geometry("420x120")
        ttk.Label(self, text="Search the web:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(10,4))
        self.q = ttk.Entry(self)
        self.q.pack(fill="x", padx=8)
        btn = ttk.Button(self, text="Search", command=self._go)
        btn.pack(pady=8)
        self.q.bind("<Return>", lambda e: self._go())
        self.q.focus_set()

    def _go(self):
        q = self.q.get().strip()
        if not q:
            return
        try:
            url = f"https://www.google.com/search?q={q.replace(' ', '+')}"
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open browser: {e}")

# ----------------------------- Settings -----------------------------

class SettingsWin(tk.Toplevel):
    def __init__(self, app: HaltmannDesktop):
        super().__init__(app)
        self.app = app
        self.title("Settings")
        self.geometry("360x260")
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Room Theme:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.theme = tk.StringVar(value=self.app.rooms[self.app.current_room].theme)
        for i, th in enumerate(["foyer", "library", "workshop", "throne"]):
            ttk.Radiobutton(frm, text=th.title(), variable=self.theme, value=th).grid(row=1, column=i, padx=4, pady=6)

        ttk.Checkbutton(frm, text="Edit/Decorate Mode",
                        variable=self.app.edit_mode, command=self.app._refresh_status).grid(row=2, column=0, columnspan=2, sticky="w", pady=6)

        ttk.Label(frm, text="Assistant Name:", font=("Segoe UI", 10, "bold")).grid(row=3, column=0, sticky="w")
        self.aname = ttk.Entry(frm, textvariable=self.app.assistant_name)
        self.aname.grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)

        frm.columnconfigure(0, weight=1)

        ttk.Button(frm, text="Apply to Current Room", command=self._apply).grid(row=5, column=0, sticky="w", pady=8)
        ttk.Button(frm, text="Close", command=self.destroy).grid(row=5, column=1, sticky="e", pady=8)

    def _apply(self):
        rn = self.app.current_room
        self.app.rooms[rn].theme = self.theme.get()
        self.app._render_room()

# ----------------------------- Assistant Maker -----------------------------

class AssistantMaker(tk.Toplevel):
    def __init__(self, app: HaltmannDesktop):
        super().__init__(app)
        self.app = app
        self.title("Assistant Maker")
        self.geometry("400x280")
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Create a simple assistant persona.").pack(anchor="w")
        ttk.Label(frm, text="Assistant Name:").pack(anchor="w", pady=(8,2))
        self.name_entry = ttk.Entry(frm)
        self.name_entry.insert(0, "Yoshi (Assistant)")
        self.name_entry.pack(fill="x")
        ttk.Label(frm, text="Phrases (one per line):").pack(anchor="w", pady=(8,2))
        self.phrases = tk.Text(frm, height=8)
        self.phrases.insert("1.0", "I'm here to help!\nClick icons to explore.\nHave you tried Edit Mode?\nLet's-a go!")
        self.phrases.pack(fill="both", expand=True)
        ttk.Button(frm, text="Apply", command=self._apply).pack(pady=8)

    def _apply(self):
        name = self.name_entry.get().strip() or "Assistant"
        lines = [ln.strip() for ln in self.phrases.get("1.0", "end-1c").splitlines() if ln.strip()]
        if not lines:
            lines = ["Hello!"]
        self.app.assistant_name.set(name)
        self.app.assistant_persona = lines
        self.app._assistant_say("Persona updated.")
        self.destroy()

# ----------------------------- Mario Tech Demo (60 FPS) -----------------------------

class MarioDemo(tk.Toplevel):
    """A minimal Mario-like platformer rendered on Tkinter Canvas at ~60 FPS.
    Rectangle player, axis-aligned collisions, coins, one enemy, goal flag.
    """
    def __init__(self, app: HaltmannDesktop):
        super().__init__(app)
        self.title("Mario Tech Demo — 60 FPS (Tkinter)")
        self.geometry("800x480")
        self.resizable(False, False)

        self.W, self.H = 800, 480
        self.canvas = tk.Canvas(self, width=self.W, height=self.H, bg="#87ceeb", highlightthickness=0)
        self.canvas.pack()

        # Game state
        self.reset_level()

        # Input
        self.bind("<KeyPress>", self._on_key)
        self.bind("<KeyRelease>", self._on_key_up)
        self.focus_set()

        # Loop
        self._last = time.time()
        self._running = True
        self.after(FRAME_MS, self._tick)

    def reset_level(self):
        random.seed(RNG_SEED)
        self.keys = {"left": False, "right": False, "jump": False}
        self.canvas.delete("all")
        self.scroll_x = 0.0
        self.player = {"x": 80.0, "y": 320.0, "w": 24, "h": 32, "vx": 0.0, "vy": 0.0, "on_ground": False}
        self.platforms = []  # list of rects (x,y,w,h)
        self.coins = []      # list of (x,y,r, alive)
        self.enemies = []    # list of dicts
        self.goal = {"x": 1400, "y": 280, "w": 12, "h": 120}

        # Generate level (simple blocks)
        ground_y = 360
        for i in range(0, 1600, 80):
            self.platforms.append((i, ground_y, 80, 120))  # ground blocks

        # Some floating platforms
        self.platforms += [
            (220, 300, 80, 16), (320, 260, 80, 16), (420, 220, 80, 16),
            (600, 300, 80, 16), (700, 260, 80, 16), (820, 220, 80, 16),
            (980, 280, 80, 16), (1080, 240, 80, 16), (1180, 200, 80, 16),
        ]

        # Coins
        for x in [260, 360, 460, 620, 720, 840, 1000, 1100, 1200]:
            self.coins.append([x, 180, 8, True])

        # One enemy (goomba-like)
        self.enemies.append({"x": 520.0, "y": ground_y-20, "w": 28, "h": 20, "vx": -1.0, "alive": True})

        self.score = 0
        self.win = False
        self._draw_static()

    def _draw_static(self):
        self.canvas.delete("bg")
        # Sky gradient
        for i in range(8):
            c = 135 - i*8
            self.canvas.create_rectangle(0, i*(self.H/8), self.W, (i+1)*(self.H/8),
                                         fill=f"#{c:02x}{(206-i*8):02x}{(235-i*12):02x}", outline="", tags="bg")
        # Hills
        self.canvas.create_oval(-80, 300, 200, 520, fill="#77dd77", outline="", tags="bg")
        self.canvas.create_oval(220, 280, 560, 560, fill="#77dd77", outline="", tags="bg")
        self.canvas.create_oval(520, 320, 900, 620, fill="#77dd77", outline="", tags="bg")

    def _draw_world(self):
        self.canvas.delete("world")
        sx = self.scroll_x
        # Platforms
        for (x,y,w,h) in self.platforms:
            self.canvas.create_rectangle(x - sx, y, x + w - sx, y + h, fill="#8b4513", outline="#5d3310", tags="world")
        # Coins
        for cx, cy, r, alive in self.coins:
            if not alive: continue
            self.canvas.create_oval(cx-r - sx, cy-r, cx+r - sx, cy+r, fill="#ffd700", outline="#c59d00", tags="world")
        # Enemy
        for e in self.enemies:
            if not e["alive"]: continue
            x,y,w,h = e["x"]-sx, e["y"], e["w"], e["h"]
            self.canvas.create_oval(x, y, x+w, y+h, fill="#8e5a2b", outline="#5d3310", tags="world")
            self.canvas.create_oval(x+6, y-10, x+w-6, y, fill="#8e5a2b", outline="#5d3310", tags="world")

        # Goal flag
        g = self.goal
        self.canvas.create_rectangle(g["x"] - sx, g["y"]-g["h"], g["x"]+g["w"] - sx, g["y"], fill="#2c3e50", outline="", tags="world")
        self.canvas.create_polygon(g["x"]+g["w"] - sx, g["y"]-g["h"]+10, g["x"]+g["w"]+32 - sx, g["y"]-g["h"]+26,
                                   g["x"]+g["w"] - sx, g["y"]-g["h"]+42, fill="#e74c3c", outline="#c0392b", tags="world")

        # HUD
        self.canvas.delete("hud")
        self.canvas.create_text(8, 8, anchor="nw", text=f"Score: {self.score}", font=("Consolas", 12, "bold"), tags="hud")
        if self.win:
            self.canvas.create_text(self.W//2, 40, text="YOU WIN! Press R to restart, Esc to exit.",
                                    font=("Segoe UI", 14, "bold"), fill="#2c3e50", tags="hud")

    def _draw_player(self):
        self.canvas.delete("player")
        p = self.player
        x, y, w, h = p["x"]-self.scroll_x, p["y"], p["w"], p["h"]
        # Body
        self.canvas.create_rectangle(x, y, x+w, y+h, fill="#ff4136", outline="#85144b", tags="player")
        # Head
        self.canvas.create_oval(x-2, y-18, x+w+2, y+2, fill="#fce5cd", outline="#b5651d", tags="player")
        # Cap
        self.canvas.create_rectangle(x-4, y-18, x+w+4, y-12, fill="#ff4136", outline="", tags="player")

    def _on_key(self, e):
        k = e.keysym.lower()
        if k in ("left", "a"): self.keys["left"] = True
        if k in ("right", "d"): self.keys["right"] = True
        if k in ("space", "z", "w", "up"):
            self.keys["jump"] = True
        if k == "r":
            self.reset_level()
        if k == "escape":
            self.destroy()

    def _on_key_up(self, e):
        k = e.keysym.lower()
        if k in ("left", "a"): self.keys["left"] = False
        if k in ("right", "d"): self.keys["right"] = False
        if k in ("space", "z", "w", "up"):
            self.keys["jump"] = False

    def _tick(self):
        if not self._running:
            return
        # physics step (fixed-ish)
        self._update_physics()
        # draw
        self._draw_world()
        self._draw_player()
        self.after(FRAME_MS, self._tick)

    def _update_physics(self):
        p = self.player
        # Movement input
        ax = 0.0
        if self.keys["left"]: ax -= 0.8
        if self.keys["right"]: ax += 0.8
        p["vx"] += ax
        p["vx"] *= 0.9  # friction
        p["vx"] = clamp(p["vx"], -4.0, 4.0)

        # Gravity
        p["vy"] += 0.8
        p["vy"] = clamp(p["vy"], -12.0, 12.0)

        # Integrate X, Y with simple AABB collisions
        self._move_and_collide(p, p["vx"], 0)
        self._move_and_collide(p, 0, p["vy"])

        # Jump
        if self.keys["jump"] and p["on_ground"]:
            p["vy"] = -10.0
            p["on_ground"] = False

        # Scrolling
        center = p["x"] - self.scroll_x
        if center > self.W*0.6:
            self.scroll_x = p["x"] - self.W*0.6
        if center < self.W*0.3:
            self.scroll_x = p["x"] - self.W*0.3
        self.scroll_x = clamp(self.scroll_x, 0, 1600 - self.W)

        # Coins
        pr = (p["x"], p["y"], p["x"]+p["w"], p["y"]+p["h"])
        for c in self.coins:
            if not c[3]: continue
            if _rect_circle_overlap(pr, (c[0], c[1], c[2])):
                c[3] = False
                self.score += 100

        # Enemy AI
        for e in self.enemies:
            if not e["alive"]: continue
            e["x"] += e["vx"]
            # bounce on edges/platform edges
            if self._enemy_hits_edge(e):
                e["vx"] *= -1

            # Player stomp check
            er = (e["x"], e["y"], e["x"]+e["w"], e["y"]+e["h"])
            if _rects_overlap(pr, er):
                # If player is falling and above enemy -> stomp
                if p["vy"] > 0 and p["y"] + p["h"] - 6 <= e["y"]:
                    e["alive"] = False
                    self.score += 200
                    p["vy"] = -8.0
                else:
                    # hit -> reset
                    self.reset_level()
                    return

        # Goal check
        gr = (self.goal["x"], self.goal["y"]-self.goal["h"], self.goal["x"]+self.goal["w"], self.goal["y"])
        if _rects_overlap(pr, gr):
            self.win = True

    def _move_and_collide(self, p, dx, dy):
        # Move axis and resolve against platforms
        p["x"] += dx
        p["y"] += dy
        p["on_ground"] = False
        pr = [p["x"], p["y"], p["x"]+p["w"], p["y"]+p["h"]]

        for (x,y,w,h) in self.platforms:
            r = (x, y, x+w, y+h)
            if not _rects_overlap(pr, r):
                continue
            # resolve
            overlap_x = min(pr[2], r[2]) - max(pr[0], r[0])
            overlap_y = min(pr[3], r[3]) - max(pr[1], r[1])
            if abs(overlap_x) < abs(overlap_y):
                # resolve along x
                if dx > 0:
                    p["x"] -= overlap_x
                else:
                    p["x"] += overlap_x
                p["vx"] = 0.0
            else:
                # resolve along y
                if dy > 0:
                    p["y"] -= overlap_y
                    p["vy"] = 0.0
                    p["on_ground"] = True
                else:
                    p["y"] += overlap_y
                    p["vy"] = 0.0

    def _enemy_hits_edge(self, e):
        # Simple edge detection: if nothing under next step or colliding with wall
        next_x = e["x"] + e["vx"]
        er = (next_x, e["y"], next_x + e["w"], e["y"] + e["h"])

        # If colliding with wall/platform side
        for (x,y,w,h) in self.platforms:
            r = (x, y, x+w, y+h)
            if _rects_overlap(er, r):
                # allow standing on ground; if significant side overlap then "edge"
                if e["y"] + e["h"] <= y + 2:  # on top
                    continue
                return True

        # if stepping into void (no ground underneath future pos)
        below = False
        for (x,y,w,h) in self.platforms:
            if next_x + e["w"]/2 >= x and next_x + e["w"]/2 <= x+w:
                if e["y"] + e["h"] + 2 >= y and e["y"] + e["h"] <= y + 6:
                    below = True
                    break
        return not below

# ----------------------------- Geometry helpers -----------------------------

def _rects_overlap(a, b):
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])

def _rect_circle_overlap(rect, circle):
    # rect: (x1,y1,x2,y2), circle: (cx, cy, r)
    x1,y1,x2,y2 = rect
    cx,cy,r = circle
    nearest_x = clamp(cx, x1, x2)
    nearest_y = clamp(cy, y1, y2)
    dx = cx - nearest_x
    dy = cy - nearest_y
    return (dx*dx + dy*dy) <= r*r

# ----------------------------- Entry -----------------------------

def main():
    app = HaltmannDesktop()
    # render initial view after widgets laid out
    app.after(10, app._render_room)
    app.mainloop()

if __name__ == "__main__":
    main()
