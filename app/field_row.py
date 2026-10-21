import tkinter as tk
from tkinter import ttk, messagebox

from hid_protocol import (
    AnticoggingFailReason,
    AnticoggingPhase,
    CalibrationFailReason,
    CalibrationPhase,
    HomingFailReason,
    ParamId,
    ProtocolError,
    Status,
    ValueType,
)

HEX_PARAMS = {ParamId.DRV_STATUS1, ParamId.DRV_STATUS2, ParamId.DRV_CONTROL1, ParamId.DRV_CONTROL2}
ENUM_PARAMS = {
    ParamId.ALIGNMENT_FAIL_REASON: CalibrationFailReason,
    ParamId.HOMING_FAIL_REASON: HomingFailReason,
    ParamId.ANTICOGGING_FAIL_REASON: AnticoggingFailReason,
    ParamId.ENCODER_CALIBRATION_PHASE: CalibrationPhase,
    ParamId.ANTICOGGING_PHASE: AnticoggingPhase,
}


class FieldRow:
    def __init__(self, parent, row, client_getter, label, param_id, value_type, read_only,
                 choices=None, on_dirty_change=None):
        self.client_getter = client_getter
        self.param_id = param_id
        self.value_type = value_type
        self.read_only = read_only
        self.on_dirty_change = on_dirty_change
        self._dirty = False
        self._setting = False

        self.label = ttk.Label(parent, text=label, style="Card.TLabel", anchor="w")
        self.label.grid(row=row, column=0, padx=(0, 16), pady=4, sticky="w")

        self.var = tk.StringVar(value="—")

        if choices is not None:
            self.entry = ttk.Combobox(parent, textvariable=self.var, width=16,
                                      values=[self._format(c) for c in choices],
                                      state="disabled" if read_only else "readonly")
        elif value_type == ValueType.BOOL:
            self.entry = ttk.Checkbutton(parent, variable=self.var, onvalue="True", offvalue="False",
                                         state="disabled" if read_only else "normal")
        else:
            self.entry = ttk.Entry(parent, textvariable=self.var, width=22,
                                   state="readonly" if read_only else "normal")
        self.entry.grid(row=row, column=1, pady=4, sticky="w")

        if not read_only:
            if choices is not None:
                self.entry.bind("<<ComboboxSelected>>", self._on_edit)
            else:
                self.var.trace_add("write", self._on_edit)
            self.revert_btn = ttk.Button(parent, text="↺", width=3, style="Small.TButton", command=self.revert)
            self.revert_btn.grid(row=row, column=2, padx=(6, 0))
            self.revert_btn.grid_remove()

    @property
    def dirty(self) -> bool:
        return self._dirty

    @dirty.setter
    def dirty(self, value: bool):
        if value == self._dirty:
            return
        self._dirty = value
        self.label.after(0, self._paint_dirty)
        if self.on_dirty_change:
            self.on_dirty_change()

    def _paint_dirty(self):
        self.label.configure(style="Card.Dirty.TLabel" if self._dirty else "Card.TLabel")
        if isinstance(self.entry, ttk.Entry) and not isinstance(self.entry, ttk.Combobox):
            self.entry.configure(style="Dirty.TEntry" if self._dirty else "TEntry")
        if not self.read_only:
            if self._dirty:
                self.revert_btn.grid()
            else:
                self.revert_btn.grid_remove()

    def _on_edit(self, *_args):
        if not self._setting:
            self.dirty = True

    def _client(self):
        client = self.client_getter()
        if client is None or not client.is_connected():
            raise ProtocolError("not connected")
        return client

    def _format(self, value):
        if isinstance(value, bool) or value is None:
            return str(value)
        if self.param_id in HEX_PARAMS and isinstance(value, int):
            return f"0x{value:04X}"
        enum = ENUM_PARAMS.get(self.param_id)
        if enum is not None and isinstance(value, int):
            try:
                return f"{enum(value).name} ({value})"
            except ValueError:
                return str(value)
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    def _show(self, text):
        self._setting = True
        try:
            self.var.set(text)
        finally:
            self._setting = False

    def revert(self):
        self.dirty = False
        try:
            self._fetch(self._client())
        except ProtocolError:
            pass

    def refresh(self):
        if self._dirty:
            return
        try:
            self._fetch(self._client())
        except ProtocolError:
            return

    def _fetch(self, client):
        try:
            resp = client.get(self.param_id)
            text = self._format(resp.value()) if resp.status == Status.OK else resp.status.name
            self.entry.after(0, self._show, text)
        except ProtocolError:
            pass

    def parse_value(self):
        raw = self.var.get().strip()
        if self.value_type == ValueType.BOOL:
            return raw.lower() in ("1", "true", "yes", "on")
        try:
            return float(raw) if self.value_type == ValueType.F32 else int(raw, 0)
        except ValueError:
            messagebox.showerror("Invalid value", f"'{raw}' isn't a valid {self.value_type.name} for {self.label.cget('text')}.")
            return None
