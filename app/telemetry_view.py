import struct
import threading
import tkinter as tk
from collections import deque
from tkinter import ttk

from app import theme
from hid_protocol import TELEMETRY_CHANNELS, TELEMETRY_MAX_CHANNELS, ProtocolError, Status

COLORS = ["#2563eb", "#22c55e", "#f59e0b", "#e7000b", "#a855f7", "#06b6d4", "#ec4899", "#eab308",
          "#84cc16", "#f97316", "#14b8a6", "#8b5cf6", "#f43f5e"]
WINDOWS_S = (0.5, 1, 2, 5, 10)
DEFAULT_CHANNELS = (0, 1, 2)  # Ia Ib Ic
FPS = 30
MAX_BUFFER_S = 10
MIN_SPAN = {"A": 1.0, "V": 2.0, "rad": 1.0, "deg": 10.0, "rad/s": 2.0}


class TelemetryView(ttk.Frame):
    def __init__(self, parent, client_getter, log):
        super().__init__(parent, style="Card.TFrame", padding=theme.PAD + 4)
        self.client_getter = client_getter
        self.log = log

        self.streaming = False
        self.rate_hz = 0.0
        self._mask_streaming = 0
        self._buffers_mask = 0
        self._lock = threading.Lock()
        self._buffers: dict[int, deque] = {}
        self._channels_in_stream: list[int] = []
        self._last_seq = None
        self._lost = 0
        self._busy = False

        head = ttk.Frame(self, style="Card.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="Live signals", style="Card.Section.TLabel").pack(side="left")
        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(head, textvariable=self.status_var, style="Card.Mono.TLabel").pack(side="left", padx=12)

        self.paused = tk.BooleanVar(value=False)
        ttk.Checkbutton(head, text="Pause", variable=self.paused).pack(side="right")
        self.window_var = tk.StringVar(value="2")
        ttk.Combobox(head, textvariable=self.window_var, values=[f"{w:g}" for w in WINDOWS_S], width=5,
                     state="readonly").pack(side="right", padx=(4, 16))
        ttk.Label(head, text="Window (s)", style="Card.Muted.TLabel").pack(side="right")

        picks = ttk.Frame(self, style="Card.TFrame")
        picks.pack(fill="x", pady=(10, 6))
        self.channel_vars: dict[int, tk.BooleanVar] = {}
        for ch in TELEMETRY_CHANNELS:
            var = tk.BooleanVar(value=ch.index in DEFAULT_CHANNELS)
            var.trace_add("write", lambda *_a: self._on_channels_changed())
            self.channel_vars[ch.index] = var
            cb = tk.Checkbutton(picks, text=ch.name, variable=var, bg=theme.CARD, fg=COLORS[ch.index],
                                selectcolor=theme.FIELD, activebackground=theme.CARD,
                                activeforeground=COLORS[ch.index], highlightthickness=0, bd=0,
                                font=("", 9, "bold"))
            cb.pack(side="left", padx=(0, 8))
        self.hint_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.hint_var, style="Card.Muted.TLabel").pack(anchor="w")

        self.canvas = tk.Canvas(self, height=300, background=theme.BG, highlightthickness=1,
                                highlightbackground=theme.BORDER)
        self.canvas.pack(fill="x", pady=(6, 0))

        self.after(int(1000 / FPS), self._redraw)

    def selected_mask(self) -> int:
        return sum(1 << i for i, v in self.channel_vars.items() if v.get())

    def tick(self, wanted: bool):
        if self._busy:
            return
        client = self.client_getter()
        connected = client is not None and client.is_connected()
        wanted = wanted and connected and not self.paused.get() and self.selected_mask() != 0

        if not wanted:
            if self.streaming:
                self._run(lambda c: self._stop(c))
            elif not connected:
                self.status_var.set("Idle")
            return
        if not self.streaming or self._mask_streaming != self.selected_mask():
            self._run(lambda c: self._start(c))
        else:
            self._run(lambda c: self._keepalive(c))

    def _run(self, fn):
        client = self.client_getter()
        if client is None:
            return
        self._busy = True

        def task():
            try:
                fn(client)
            except ProtocolError as exc:
                self.streaming = False
                self.log(f"Live signals: restarting after error ({exc})")
                self.after(0, self.status_var.set, f"Stream error: {exc}")
            finally:
                self._busy = False

        threading.Thread(target=task, daemon=True).start()

    def _start(self, client):
        mask = self.selected_mask()
        client.on_telemetry = self._on_packet
        resp = client.telemetry_start(mask)
        if resp.status != Status.OK:
            self.streaming = False
            self.after(0, self.status_var.set, f"Can't stream ({resp.status.name})")
            return
        rate = float(resp.value() or 0.0)
        with self._lock:
            same = mask == self._buffers_mask and rate == self.rate_hz
            self._channels_in_stream = [i for i in range(len(TELEMETRY_CHANNELS)) if mask & (1 << i)]
            if not same:
                self.rate_hz = rate
                maxlen = max(1, int(rate * MAX_BUFFER_S))
                self._buffers = {i: deque(maxlen=maxlen) for i in self._channels_in_stream}
                self._buffers_mask = mask
                self._lost = 0
            self._last_seq = None
            self._mask_streaming = mask
        self.streaming = True
        self.after(0, self.status_var.set, f"Streaming · {self.rate_hz:,.0f} Hz · {len(self._channels_in_stream)} ch")

    def _keepalive(self, client):
        try:
            resp = client.telemetry_keepalive()
        except ProtocolError:
            if client.is_connected():
                return
            raise
        if resp.status != Status.OK:
            self.streaming = False
            self.log(f"Live signals: base stopped the stream ({resp.status.name}), restarting")

    def _stop(self, client):
        try:
            client.telemetry_stop()
        finally:
            self.streaming = False
            self._mask_streaming = 0
            self.after(0, self.status_var.set, "Paused" if self.paused.get() else "Idle")

    def _on_channels_changed(self):
        n = sum(v.get() for v in self.channel_vars.values())
        self.hint_var.set(f"Up to {TELEMETRY_MAX_CHANNELS} channels at once -- uncheck some." if n > TELEMETRY_MAX_CHANNELS
                          else "")

    HEADER = struct.Struct("<HBBH")

    def _on_packet(self, payload: bytes):
        try:
            self._decode(payload)
        except Exception:
            with self._lock:
                self._lost += 1

    def _decode(self, payload: bytes):
        if len(payload) < self.HEADER.size:
            return
        seq, frames, flags, mask = self.HEADER.unpack_from(payload, 0)
        with self._lock:
            chans = self._channels_in_stream
            n = len(chans)
            if not n or mask != self._mask_streaming:
                return
            if self.HEADER.size + frames * n * 2 > len(payload):
                self._lost += 1
                return
            if self._last_seq is not None and seq != (self._last_seq + 1) & 0xFFFF:
                self._lost += (seq - self._last_seq - 1) & 0xFFFF
            self._last_seq = seq
            if flags & 0x01:
                self._lost += 1
            values = struct.unpack_from(f"<{frames * n}h", payload, self.HEADER.size)
            for f in range(frames):
                for k, ch in enumerate(chans):
                    self._buffers[ch].append(values[f * n + k] / TELEMETRY_CHANNELS[ch].scale)

    def _redraw(self):
        try:
            if not self.paused.get():
                self._draw()
        finally:
            self.after(int(1000 / FPS), self._redraw)

    def _draw(self):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50 or h < 50:
            return
        legend_w = 170
        plot_w = w - legend_w - 16
        top, bottom = 10, h - 10

        for frac in (0.25, 0.5, 0.75):
            y = top + (bottom - top) * frac
            c.create_line(8, y, 8 + plot_w, y, fill="#1c1c1c")

        with self._lock:
            series = {ch: list(buf) for ch, buf in self._buffers.items()}
            rate = self.rate_hz
            lost = self._lost
        if not series or rate <= 0:
            c.create_text(w / 2, h / 2, text="Open this tab with the base connected to see live signals.",
                          fill=theme.MUTED)
            return

        try:
            window_s = float(self.window_var.get())
        except ValueError:
            window_s = 2.0
        n_window = max(2, int(window_s * rate))

        ranges: dict[str, list[float]] = {}
        clipped = {}
        for ch, data in series.items():
            data = data[-n_window:]
            clipped[ch] = data
            if data:
                unit = TELEMETRY_CHANNELS[ch].unit
                lo, hi = min(data), max(data)
                r = ranges.setdefault(unit, [lo, hi])
                r[0], r[1] = min(r[0], lo), max(r[1], hi)

        legend_y = top
        for ch, data in clipped.items():
            if not data:
                continue
            meta = TELEMETRY_CHANNELS[ch]
            lo, hi = ranges[meta.unit]
            min_span = MIN_SPAN.get(meta.unit, 1.0)
            if hi - lo < min_span:
                mid = (hi + lo) / 2
                lo, hi = mid - min_span / 2, mid + min_span / 2
            span = hi - lo
            lo, hi = lo - span * 0.05, hi + span * 0.05

            def y_of(v, lo=lo, hi=hi):
                return bottom - (v - lo) / (hi - lo) * (bottom - top)

            n = len(data)
            span_px = plot_w * n / n_window
            cols = max(1, min(int(span_px), n))
            col_w = span_px / cols
            x_start = 8 + plot_w - span_px
            pts = []
            for i in range(cols):
                a = int(i * n / cols)
                seg = data[a: max(int((i + 1) * n / cols), a + 1)]
                x = x_start + (i + 0.5) * col_w
                pts += [x, y_of(min(seg)), x, y_of(max(seg))]
            if len(pts) >= 4:
                c.create_line(*pts, fill=COLORS[ch], width=1)

            c.create_text(w - legend_w, legend_y, anchor="nw", fill=COLORS[ch], font=("", 9, "bold"),
                          text=f"{meta.name}")
            c.create_text(w - 8, legend_y, anchor="ne", fill=theme.FG, font=("Consolas", 9),
                          text=f"{data[-1]:+.3f} {meta.unit}")
            c.create_text(w - 8, legend_y + 15, anchor="ne", fill=theme.MUTED, font=("Consolas", 8),
                          text=f"{min(data):+.2f} … {max(data):+.2f}")
            legend_y += 34

        c.create_text(w - 8, h - 8, anchor="se", fill=theme.MUTED, font=("Consolas", 8),
                      text=f"{window_s:g} s window · lost {lost}")
