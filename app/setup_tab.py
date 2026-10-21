import threading
import tkinter as tk
from tkinter import messagebox, ttk

from app import theme
from app.tab import ScrollFrame, card
from hid_protocol import (
    AnticoggingFailReason,
    AnticoggingPhase,
    AxisState,
    CalibrationFailReason,
    CalibrationPhase,
    HomingFailReason,
    ParamId,
    ProtocolError,
    Status,
    ValueType,
)


class Step:
    def __init__(self, parent, row, title, description, button_text, command, button_style="TButton"):
        self.marker = ttk.Label(parent, text="○", style="Card.Muted.TLabel", width=2, anchor="center")
        self.marker.grid(row=row, column=0, sticky="n", pady=(10, 0))

        text = ttk.Frame(parent, style="Card.TFrame")
        text.grid(row=row, column=1, sticky="ew", pady=8)
        ttk.Label(text, text=title, style="Card.TLabel", font=("", 10, "bold")).pack(anchor="w")
        self.description = ttk.Label(text, text=description, style="Card.Muted.TLabel", wraplength=460,
                                     justify="left")
        self.description.pack(anchor="w")

        self.status = ttk.Label(parent, text="—", style="Card.Muted.TLabel", anchor="e")
        self.status.grid(row=row, column=2, sticky="e", padx=12)

        self.button = ttk.Button(parent, text=button_text, command=command, style=button_style, state="disabled")
        self.button.grid(row=row, column=3, sticky="e")

    def set(self, *, status: str, tone: str, enabled: bool, done: bool, current: bool):
        self.status.configure(text=status, style=f"Card.{tone}.TLabel")
        self.marker.configure(text="✓" if done else ("→" if current else "○"),
                              style="Card.Ok.TLabel" if done else ("Card.Primary.TLabel" if current else "Card.Muted.TLabel"))
        self.button.configure(state="normal" if enabled else "disabled")


class SetupTab(ttk.Frame):
    def __init__(self, parent, client_getter, log, on_status=None, refresh_tabs=None):
        super().__init__(parent)
        self.client_getter = client_getter
        self.log = log
        self.on_status = on_status
        self.refresh_tabs = refresh_tabs
        self._busy = False
        self.unsaved = False

        self.dev = {
            "connected": False,
            "fw_version": None,
            "axis_state": None,
            "motor_cal": False,
            "encoder_cal": False,
            "referenced": False,
            "anticogging_cal": False,
            "ffb_active": False,
            "drv_fault": False,
            "use_index": True,
            "angle": None,
        }

        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        body = scroll.body
        body.columnconfigure(0, weight=1)

        seq = card(body, "Calibration", "Run the steps in order. Each one unlocks the next; "
                                        "Save stores everything on the base and reboots it.")
        seq.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        s = seq.inner
        s.columnconfigure(1, weight=1)
        self.steps = {
            "motor": Step(s, 0, "1  Motor", "Measures phase resistance and inductance; sets the current loop gains.",
                          "Calibrate", self._on_calibrate_motor),
            "home": Step(s, 1, "2  Find index", "Turns the wheel up to one revolution to find the encoder's index pulse.",
                         "Home", self._on_home),
            "encoder": Step(s, 2, "3  Encoder", "Sweeps one revolution to learn the electrical offset and linearity.",
                            "Calibrate", self._on_calibrate_encoder),
            "center": Step(s, 3, "4  Center", "Hold the wheel perfectly straight, then set this position as 0°.",
                           "Set center", self._on_set_center),
            "anticogging": Step(s, 4, "5  Anticogging (optional)", "Maps the motor's cogging torque so it can be cancelled.",
                                "Calibrate", self._on_calibrate_anticogging),
            "save": Step(s, 5, "6  Save", "Stores the configuration on the base and reboots it.",
                         "Save & reboot", self._on_save, "Primary.TButton"),
        }

        test = card(body, "Test", "Try the base before shipping it.")
        test.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        row = ttk.Frame(test.inner, style="Card.TFrame")
        row.pack(fill="x")
        self.ffb_btn = ttk.Button(row, text="Start FFB", command=self._on_toggle_ffb, state="disabled")
        self.ffb_btn.pack(side="left")
        self.sound_btn = ttk.Button(row, text="Play sound", command=self._on_play_sound, state="disabled")
        self.sound_btn.pack(side="left", padx=8)
        self.clear_btn = ttk.Button(row, text="Clear faults", command=self._on_clear_fault, state="disabled")
        self.clear_btn.pack(side="left")
        self.test_status = ttk.Label(row, text="", style="Card.Muted.TLabel")
        self.test_status.pack(side="right")

        maint = card(body, "Maintenance")
        maint.grid(row=2, column=0, sticky="ew")
        row = ttk.Frame(maint.inner, style="Card.TFrame")
        row.pack(fill="x")
        self.reboot_btn = ttk.Button(row, text="Reboot", command=self._on_reboot, state="disabled")
        self.reboot_btn.pack(side="left")
        self.reset_btn = ttk.Button(row, text="Factory reset", style="Danger.TButton", command=self._on_factory_reset,
                                    state="disabled")
        self.reset_btn.pack(side="left", padx=8)
        ttk.Label(row, text="Factory reset erases every calibration and setting.", style="Card.Muted.TLabel").pack(
            side="left", padx=8)

    def mark_unsaved(self):
        self.unsaved = True
        self.after(0, self._apply_state)

    def _apply_state(self):
        d = self.dev
        connected = d["connected"]
        fw_idle = d["axis_state"] in (None, AxisState.IDLE, AxisState.ERROR)
        working = self._busy or d["axis_state"] in (AxisState.HOMING, AxisState.CALIBRATING_ENCODER,
                                                    AxisState.CALIBRATING_ANTICOGGING)
        free = connected and not working and fw_idle and not d["ffb_active"]

        can = {
            "motor": free,
            "home": free and d["motor_cal"],
            "encoder": free and d["motor_cal"] and d["referenced"],
            "center": free and d["referenced"],
            "anticogging": free and d["motor_cal"] and d["referenced"] and d["encoder_cal"],
            "save": connected and not working,
        }
        done = {
            "motor": d["motor_cal"],
            "home": d["referenced"],
            "encoder": d["encoder_cal"],
            "center": False,
            "anticogging": d["anticogging_cal"],
            "save": connected and not self.unsaved,
        }

        order = ["motor", "home", "encoder", "center", "save"]
        current = next((k for k in order if not done[k] and k != "center"), None)
        if current is None and self.unsaved:
            current = "save"

        angle = d["angle"]
        center_status = "—" if angle is None or not d["referenced"] else f"Wheel at {angle:+.1f}°"
        center_desc = "Hold the wheel perfectly straight, then set this position as 0°."
        if not d["use_index"]:
            center_desc += " Without the index pulse, the center resets at every boot."
        self.steps["center"].description.configure(text=center_desc)

        statuses = {
            "motor": ("Calibrated", "Ok") if d["motor_cal"] else ("Not calibrated", "Warn"),
            "home": ("Index found", "Ok") if d["referenced"] else ("Not homed", "Warn"),
            "encoder": ("Calibrated", "Ok") if d["encoder_cal"] else ("Not calibrated", "Warn"),
            "center": (center_status, "Muted"),
            "anticogging": ("Calibrated", "Ok") if d["anticogging_cal"] else ("Not calibrated", "Muted"),
            "save": ("Unsaved changes", "Warn") if self.unsaved else ("Saved", "Muted"),
        }
        if not connected:
            statuses = {k: ("—", "Muted") for k in statuses}
        for key, step in self.steps.items():
            text, tone = statuses[key]
            step.set(status=text, tone=tone, enabled=can[key], done=done[key] and connected,
                     current=connected and key == current)

        self.ffb_btn.configure(text="Stop FFB" if d["ffb_active"] else "Start FFB",
                               state="normal" if connected and not self._busy and (
                                   d["ffb_active"] or (free and d["motor_cal"] and d["encoder_cal"] and d["referenced"]))
                               else "disabled")
        self.sound_btn.configure(state="normal" if connected and not working and d["motor_cal"] else "disabled")
        self.clear_btn.configure(state="normal" if connected and not self._busy else "disabled")
        self.reboot_btn.configure(state="normal" if connected and not working else "disabled")
        self.reset_btn.configure(state="normal" if connected and not working else "disabled")

        if not connected:
            self.test_status.configure(text="")
        elif d["drv_fault"]:
            self.test_status.configure(text="Motor driver fault", style="Card.Error.TLabel")
        else:
            state = d["axis_state"].name.replace("_", " ").title() if d["axis_state"] is not None else "Unknown"
            self.test_status.configure(text=f"Axis: {state}  ·  FFB {'on' if d['ffb_active'] else 'off'}",
                                       style="Card.Muted.TLabel")

        if self.on_status:
            self.on_status(dict(d), self.unsaved, working)

    def _client(self):
        client = self.client_getter()
        if client is None or not client.is_connected():
            raise ProtocolError("not connected")
        return client

    def _run_async(self, fn):
        if self._busy:
            return
        self._busy = True
        self._apply_state()

        def wrapper():
            try:
                fn()
            except ProtocolError as exc:
                self.log(f"ERROR: {exc}")
            finally:
                self._busy = False
                self.poll_status()

        threading.Thread(target=wrapper, daemon=True).start()

    def _on_calibrate_motor(self):
        def task():
            client = self._client()
            self.log("Calibrating motor…")
            resp = client.calibrate(ParamId.CALTYPE_MOTOR)
            final = resp.status
            if resp.status == Status.IN_PROGRESS:
                final = client.poll_until_done(timeout_s=10.0).status
            self.log(f"Motor calibration -> {final.name}")
            if final == Status.OK:
                self.mark_unsaved()
                if self.refresh_tabs:
                    self.refresh_tabs()

        self._run_async(task)

    def _on_home(self):
        def task():
            client = self._client()
            self.log("Finding the index…")
            resp = client.calibrate(ParamId.CALTYPE_HOME)
            if resp.status != Status.IN_PROGRESS:
                self.log(f"Home -> {resp.status.name}")
                return
            try:
                reason = client.poll_homing()
            except ProtocolError as exc:
                self.log(f"Home -> ERROR: {exc}")
                return
            self.log("Home -> OK (index found)" if reason == HomingFailReason.NONE else f"Home -> FAILED ({reason.name})")

        self._run_async(task)

    def _on_calibrate_encoder(self):
        def task():
            client = self._client()
            self.log("Calibrating encoder (one slow revolution)…")
            resp = client.calibrate(ParamId.CALTYPE_ENCODER)
            if resp.status != Status.IN_PROGRESS:
                self.log(f"Encoder calibration -> {resp.status.name}")
                return
            try:
                phase = client.poll_encoder_calibration(timeout_s=300.0)
            except ProtocolError as exc:
                self.log(f"Encoder calibration -> ERROR: {exc}")
                return

            if phase != CalibrationPhase.FAILED:
                self.log(f"Encoder calibration -> {phase.name}")
                if phase == CalibrationPhase.DONE:
                    self.mark_unsaved()
                return
            try:
                reason = CalibrationFailReason(client.get(ParamId.ALIGNMENT_FAIL_REASON).value())
            except (ProtocolError, ValueError):
                self.log("Encoder calibration -> FAILED")
                return
            self.log(f"Encoder calibration -> FAILED ({reason.name})")
            if reason == CalibrationFailReason.ENCODER_DIRECTION_REVERSED:
                self.log("Encoder direction was flipped automatically -- Home again, then calibrate the encoder.")
            elif reason == CalibrationFailReason.CPR_POLE_PAIRS_MISMATCH:
                delta = client.get(ParamId.CALIBRATION_SCAN_DELTA_COUNTS).value()
                cpr = client.get(ParamId.ENCODER_CPR).value()
                pole_pairs = client.get(ParamId.MOTOR_POLE_PAIRS).value()
                ratio = delta / cpr if cpr else 0.0
                self.log(f"Scan moved {delta} counts, expected {cpr} ({ratio:.3f} rev for {pole_pairs} pole pairs). "
                         f"Smooth turn -> pole pairs ~ {pole_pairs / ratio if ratio else 0:.2f}; "
                         "stuck/skipped -> raise the calibration test current.")

        self._run_async(task)

    def _on_set_center(self):
        def task():
            client = self._client()
            position = client.get(ParamId.ENCODER_POSITION_COUNTS).value()
            if position is None:
                self.log("Set center -> couldn't read the encoder position")
                return
            resp = client.set(ParamId.ENCODER_MECHANICAL_OFFSET, ValueType.I32, int(position))
            self.log(f"Set center (offset = {position} counts) -> {resp.status.name}")
            if resp.status == Status.OK:
                self.mark_unsaved()
                if self.refresh_tabs:
                    self.refresh_tabs()

        self._run_async(task)

    def _on_calibrate_anticogging(self):
        def task():
            client = self._client()
            self.log("Calibrating anticogging (constant-velocity scan)…")
            resp = client.calibrate(ParamId.CALTYPE_ANTICOGGING)
            if resp.status != Status.IN_PROGRESS:
                self.log(f"Anticogging calibration -> {resp.status.name}")
                return
            try:
                phase = client.poll_anticogging_calibration(timeout_s=60.0)
            except ProtocolError as exc:
                self.log(f"Anticogging calibration -> ERROR: {exc}")
                return
            if phase == AnticoggingPhase.FAILED:
                try:
                    reason = AnticoggingFailReason(client.get(ParamId.ANTICOGGING_FAIL_REASON).value())
                    self.log(f"Anticogging calibration -> FAILED ({reason.name})")
                except (ProtocolError, ValueError):
                    self.log("Anticogging calibration -> FAILED")
                return
            self.log(f"Anticogging calibration -> {phase.name}")
            if phase == AnticoggingPhase.DONE:
                self.mark_unsaved()

        self._run_async(task)

    def _on_save(self):
        def task():
            client = self._client()
            self.log("Saving to the base…")
            try:
                resp = client.save()
                self.log(f"Save -> {resp.status.name}")
                ok = resp.status == Status.OK
            except ProtocolError:
                self.log("Save sent -- the base is rebooting.")
                ok = True
            if ok:
                self.unsaved = False

        self._run_async(task)

    def _on_toggle_ffb(self):
        def task():
            client = self._client()
            requested = not self.dev["ffb_active"]
            resp = client.set(ParamId.FFB_ACTIVE, ValueType.BOOL, requested)
            self.log(f"FFB {'start' if requested else 'stop'} -> {resp.status.name}")
            if resp.status == Status.OK:
                self.dev["ffb_active"] = requested

        self._run_async(task)

    def _on_play_sound(self):
        def task():
            resp = self._client().set(ParamId.STARTUP_SOUND_PLAY, ValueType.BOOL, True)
            self.log(f"Play sound -> {resp.status.name}")

        self._run_async(task)

    def _on_clear_fault(self):
        def task():
            resp = self._client().clear_fault()
            self.log(f"Clear faults -> {resp.status.name}")

        self._run_async(task)

    def _on_reboot(self):
        if self.unsaved and not messagebox.askyesno(
                "Reboot", "There are unsaved changes; rebooting discards them. Reboot anyway?"):
            return
        if not self.unsaved and not messagebox.askyesno("Reboot", "Reboot the base?"):
            return

        def task():
            client = self._client()
            self.log("Rebooting the base…")
            try:
                client.reboot()
            except ProtocolError:
                self.log("Reboot sent (connection dropped, as expected).")
                client.close()
            self.unsaved = False

        self._run_async(task)

    def _on_factory_reset(self):
        if not messagebox.askyesno("Factory reset",
                                   "Erase every calibration and setting on the base and reboot it?\n\n"
                                   "The whole calibration sequence will have to be run again."):
            return

        def task():
            client = self._client()
            try:
                resp = client.factory_reset()
                self.log(f"Factory reset -> {resp.status.name}")
            except ProtocolError:
                self.log("Factory reset sent -- the base is rebooting.")
            self.unsaved = False

        self._run_async(task)

    def set_disconnected(self):
        self.dev["connected"] = False
        self.after(0, self._apply_state)

    def poll_status(self):
        try:
            client = self._client()
        except ProtocolError:
            self.set_disconnected()
            return
        if self._busy:
            return

        def read(param, convert=lambda v: v):
            try:
                value = client.get(param).value()
                return None if value is None else convert(value)
            except (ProtocolError, ValueError):
                return None

        def task():
            d = self.dev
            d["connected"] = True
            d["fw_version"] = read(ParamId.FW_VERSION)
            d["axis_state"] = read(ParamId.AXIS_STATE, AxisState)
            for key, param in (("motor_cal", ParamId.MOTOR_CALIBRATED), ("encoder_cal", ParamId.ENCODER_CALIBRATED),
                               ("referenced", ParamId.POSITION_REFERENCED),
                               ("anticogging_cal", ParamId.ANTICOGGING_CALIBRATED),
                               ("ffb_active", ParamId.FFB_ACTIVE), ("drv_fault", ParamId.DRV_HAS_FAULT),
                               ("use_index", ParamId.ENCODER_USE_INDEX_Z)):
                value = read(param, bool)
                if value is not None:
                    d[key] = value
            d["angle"] = read(ParamId.WHEEL_ANGLE_DEG, float)
            self.after(0, self._apply_state)

        threading.Thread(target=task, daemon=True).start()
