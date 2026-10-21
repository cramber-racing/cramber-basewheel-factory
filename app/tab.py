import threading
import tkinter as tk
from tkinter import messagebox, ttk

from app import theme
from app.field_row import FieldRow
from hid_protocol import ProtocolError, Status


class ScrollFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, background=theme.BG, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas)
        self.body.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._window, width=e.width))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.body.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self._on_wheel))
        self.body.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_wheel(self, event):
        if self.body.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")


def card(parent, title: str, subtitle: str | None = None) -> ttk.Frame:
    outer = ttk.Frame(parent, style="Card.TFrame", padding=theme.PAD + 4)
    ttk.Label(outer, text=title, style="Card.Section.TLabel").pack(anchor="w")
    if subtitle:
        ttk.Label(outer, text=subtitle, style="Card.Muted.TLabel", wraplength=520, justify="left").pack(
            anchor="w", pady=(2, 0))
    inner = ttk.Frame(outer, style="Card.TFrame")
    inner.pack(fill="x", pady=(theme.PAD, 0))
    outer.inner = inner
    return outer


class Tab(ttk.Frame):
    def __init__(self, parent, client_getter, log, sections, on_applied=None, top=None):
        super().__init__(parent)
        self.client_getter = client_getter
        self.log = log
        self.on_applied = on_applied
        self.rows: list[FieldRow] = []
        self._refreshing = False

        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        grid = scroll.body
        grid.columnconfigure((0, 1), weight=1, uniform="col")
        first_row = 0
        self.top = None
        if top is not None:
            self.top = top(grid)
            self.top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
            first_row = 1

        for i, (title, fields) in enumerate(sections):
            box = card(grid, title)
            box.grid(row=first_row + i // 2, column=i % 2, sticky="nsew", padx=(0 if i % 2 == 0 else 8, 0), pady=(0, 8))
            box.inner.columnconfigure(0, minsize=220)
            box.inner.columnconfigure(1, weight=1)
            for r, (label, param_id, value_type, read_only, choices) in enumerate(fields):
                self.rows.append(FieldRow(box.inner, r, client_getter, label, param_id, value_type, read_only,
                                          choices, on_dirty_change=self._update_bar))

        if any(not r.read_only for r in self.rows):
            bar = ttk.Frame(self, style="Bar.TFrame", padding=(theme.PAD, 8))
            bar.pack(fill="x", side="bottom", pady=(8, 0))
            self.pending_var = tk.StringVar(value="No changes")
            ttk.Label(bar, textvariable=self.pending_var, style="Card.Muted.TLabel").pack(side="left")
            self.apply_btn = ttk.Button(bar, text="Apply", style="Primary.TButton", command=self._on_apply,
                                        state="disabled")
            self.apply_btn.pack(side="right")
            self.revert_btn = ttk.Button(bar, text="Revert", command=self._on_revert, state="disabled")
            self.revert_btn.pack(side="right", padx=(0, 8))
        else:
            self.apply_btn = None

    def _update_bar(self):
        if self.apply_btn is None:
            return
        n = sum(r.dirty for r in self.rows)

        def paint():
            self.pending_var.set("No changes" if n == 0 else f"{n} change{'s' if n > 1 else ''} not applied")
            state = "normal" if n else "disabled"
            self.apply_btn.configure(state=state)
            self.revert_btn.configure(state=state)

        self.after(0, paint)

    def refresh_all(self):
        if self._refreshing:
            return
        self._refreshing = True

        def task():
            try:
                for row in self.rows:
                    row.refresh()
            finally:
                self._refreshing = False

        threading.Thread(target=task, daemon=True).start()

    def _client(self):
        client = self.client_getter()
        if client is None or not client.is_connected():
            raise ProtocolError("not connected")
        return client

    def _on_revert(self):
        for row in self.rows:
            if row.dirty:
                row.revert()

    def _on_apply(self):
        try:
            client = self._client()
        except ProtocolError as exc:
            messagebox.showerror("Not connected", str(exc))
            return

        parsed = []
        for row in (r for r in self.rows if r.dirty and not r.read_only):
            value = row.parse_value()
            if value is None:
                return
            parsed.append((row, value))
        if not parsed:
            return

        def task():
            applied = 0
            for row, value in parsed:
                try:
                    resp = client.set(row.param_id, row.value_type, value)
                    self.log(f"SET {row.param_id.name} = {value} -> {resp.status.name}")
                    if resp.status == Status.OK:
                        row.dirty = False
                        applied += 1
                except ProtocolError as exc:
                    self.log(f"SET {row.param_id.name} failed: {exc}")
            if applied and self.on_applied:
                self.on_applied()

        threading.Thread(target=task, daemon=True).start()
