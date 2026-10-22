import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from app import theme
from app.field_definitions import PARAM_TABS
from app.setup_tab import SetupTab
from app.tab import Tab
from app.telemetry_view import TelemetryView
from hid_protocol import ConfigClient

POLL_INTERVAL_MS = 500
ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets"
ERROR_WORDS = ("ERROR", "FAILED", "ERR_", "failed", "couldn't")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cramber Factory Tool")
        try:
            self.iconbitmap(default=str(ASSETS / "icon.ico"))
        except tk.TclError:
            pass
        self.geometry("1180x820")
        self.minsize(960, 640)
        self.fonts = theme.apply(self)

        self.client = ConfigClient()

        self._build_header()
        self._build_tabs()
        self._build_log()

        self.after(POLL_INTERVAL_MS, self._poll)

    def _build_header(self):
        bar = ttk.Frame(self, style="Bar.TFrame", padding=(theme.PAD + 4, 10))
        bar.pack(fill="x")

        ttk.Label(bar, text="CRAMBER", style="BarTitle.TLabel").pack(side="left")
        ttk.Label(bar, text="Factory Tool", style="Card.Muted.TLabel").pack(side="left", padx=(8, 24))

        self.conn_dot = ttk.Label(bar, text="●", style="Card.Muted.TLabel")
        self.conn_dot.pack(side="left")
        self.conn_var = tk.StringVar(value="Searching for the base…")
        ttk.Label(bar, textvariable=self.conn_var, style="Card.TLabel").pack(side="left", padx=(6, 0))
        self.info_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.info_var, style="Card.Mono.TLabel").pack(side="left", padx=16)

        self.save_btn = ttk.Button(bar, text="Save & reboot", style="Primary.TButton", state="disabled",
                                   command=lambda: self.setup_tab._on_save())

        self.unsaved_var = tk.StringVar(value="")
        self.unsaved_label = ttk.Label(bar, textvariable=self.unsaved_var, style="Card.Warn.TLabel")
        self.unsaved_label.pack(side="right", padx=12)

    def _build_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=theme.PAD, pady=(theme.PAD, 0))
        get_client = lambda: self.client

        self.setup_tab = SetupTab(self.notebook, get_client, self._log, on_status=self._on_status,
                                  refresh_tabs=self._refresh_param_tabs)
        self.notebook.add(self.setup_tab, text="Setup")

        self.param_tabs = []
        self.telemetry_view = None
        self.diagnostics_tab = None
        for title, sections in PARAM_TABS:
            top = None
            if title == "Diagnostics":
                def top(parent):
                    self.telemetry_view = TelemetryView(parent, get_client, self._log)
                    return self.telemetry_view
            tab = Tab(self.notebook, get_client, self._log, sections, on_applied=self.setup_tab.mark_unsaved,
                      top=top)
            self.notebook.add(tab, text=title)
            self.param_tabs.append(tab)
            if title == "Diagnostics":
                self.diagnostics_tab = tab

        self.notebook.bind("<<NotebookTabChanged>>", lambda _e: (self._refresh_current(), self._update_stream()))

        self.bind("<Unmap>", lambda e: e.widget is self and self._update_stream())
        self.bind("<Map>", lambda e: e.widget is self and self._update_stream())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_log(self):
        frame = ttk.Frame(self, padding=(theme.PAD, 8, theme.PAD, theme.PAD))
        frame.pack(fill="x")
        head = ttk.Frame(frame)
        head.pack(fill="x")
        ttk.Label(head, text="Log", style="Muted.TLabel").pack(side="left")
        ttk.Button(head, text="Clear", style="Small.TButton", command=self._clear_log).pack(side="right")

        self.log_text = tk.Text(frame, height=6, state="disabled", wrap="word", background=theme.CARD,
                                foreground=theme.FG, insertbackground=theme.FG, relief="flat",
                                highlightthickness=1, highlightbackground=theme.BORDER, padx=10, pady=8,
                                font=self.fonts["mono"])
        self.log_text.pack(fill="x", pady=(6, 0))
        self.log_text.tag_configure("time", foreground=theme.MUTED)
        self.log_text.tag_configure("error", foreground=theme.DANGER)

    def _log(self, message: str):
        self.after(0, self._append_log, message)

    def _append_log(self, message: str):
        tag = "error" if any(w in message for w in ERROR_WORDS) else ""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", time.strftime("%H:%M:%S  "), "time")
        self.log_text.insert("end", message + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _on_status(self, dev: dict, unsaved: bool, working: bool):
        if dev["connected"]:
            self.conn_dot.configure(style="Card.Error.TLabel" if dev["drv_fault"] else "Card.Ok.TLabel")
            self.conn_var.set("Connected · factory mode")
            parts = []
            if dev["fw_version"] is not None:
                v = dev["fw_version"]  # packed (major << 16) | (minor << 8) | patch
                parts.append(f"FW v{v >> 16}.{(v >> 8) & 0xFF}.{v & 0xFF}")
            if self.client.serial:
                parts.append(f"SN {self.client.serial}")
            if dev["axis_state"] is not None:
                parts.append(dev["axis_state"].name.replace("_", " ").lower())
            if dev["drv_fault"]:
                parts.append("DRIVER FAULT")
            self.info_var.set("   ·   ".join(parts))
        else:
            self.conn_dot.configure(style="Card.Muted.TLabel")
            self.conn_var.set("Searching for the base…")
            self.info_var.set("")

        show = unsaved and dev["connected"]
        self.unsaved_var.set("● Unsaved changes" if show else "")
        if show:
            self.save_btn.pack(side="right", before=self.unsaved_label)
            self.save_btn.configure(state="disabled" if working else "normal")
        else:
            self.save_btn.pack_forget()

    def _refresh_param_tabs(self):
        for tab in self.param_tabs:
            tab.refresh_all()

    def _refresh_current(self):
        if not self.client.is_connected():
            return
        current = self.notebook.nametowidget(self.notebook.select())
        if current in self.param_tabs:
            current.refresh_all()

    def _try_connect(self):
        def task():
            try:
                self.client.connect()
                resp = self.client.set_factory_mode(True)
                self._log(f"Connected to the base (factory mode -> {resp.status.name})")
                self.setup_tab.unsaved = False
            except Exception:
                pass

        threading.Thread(target=task, daemon=True).start()

    def _stream_wanted(self) -> bool:
        if self.diagnostics_tab is None or self.state() == "iconic":
            return False
        return self.notebook.nametowidget(self.notebook.select()) is self.diagnostics_tab

    def _update_stream(self):
        if self.telemetry_view is not None:
            self.telemetry_view.tick(self._stream_wanted())

    def _on_close(self):
        if self.telemetry_view is not None and self.telemetry_view.streaming:
            try:
                self.client.telemetry_stop()
            except Exception:
                pass
        self.destroy()

    def _poll(self):
        if not self.client.is_connected():
            self.setup_tab.set_disconnected()
            self._try_connect()
        else:
            self.setup_tab.poll_status()
            self._refresh_current()
        self._update_stream()
        self.after(POLL_INTERVAL_MS, self._poll)
