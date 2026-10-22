import random
import struct
import threading
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Union

import pywinusb.hid as hid

USB_VID = 0x1209
USB_PID = 0x4FFB

REPORT_ID_COMMAND = 21  # OUT
REPORT_ID_RESPONSE = 23  # IN
REPORT_SIZE = 16


class Command(IntEnum):
    GET = 0x01
    SET = 0x02
    SAVE = 0x03
    CALIBRATE = 0x04
    GET_STATUS = 0x05
    FACTORY_RESET = 0x06
    REBOOT = 0x07
    CLEAR_FAULT = 0x08
    FACTORY_MODE = 0x09
    GET_DEFAULT = 0x0A
    TELEMETRY = 0x0B


REPORT_ID_TELEMETRY = 25


@dataclass(frozen=True)
class TelemetryChannel:
    index: int
    name: str
    unit: str
    scale: float


TELEMETRY_CHANNELS = [
    TelemetryChannel(0, "Ia", "A", 1000.0),
    TelemetryChannel(1, "Ib", "A", 1000.0),
    TelemetryChannel(2, "Ic", "A", 1000.0),
    TelemetryChannel(3, "Id", "A", 1000.0),
    TelemetryChannel(4, "Iq", "A", 1000.0),
    TelemetryChannel(5, "Iq target", "A", 1000.0),
    TelemetryChannel(6, "Vd", "V", 100.0),
    TelemetryChannel(7, "Vq", "V", 100.0),
    TelemetryChannel(8, "Vbus", "V", 100.0),
    TelemetryChannel(9, "Ibus", "A", 1000.0),
    TelemetryChannel(10, "Elec angle", "rad", 5000.0),
    TelemetryChannel(11, "Wheel angle", "deg", 10.0),
    TelemetryChannel(12, "Velocity", "rad/s", 100.0),
]
TELEMETRY_MAX_CHANNELS = 8


class Status(IntEnum):
    OK = 0x00
    ERR_UNKNOWN_PARAM = 0x01
    ERR_BUSY = 0x02
    ERR_INVALID_VALUE = 0x03
    ERR_NOT_CALIBRATED = 0x04
    ERR_CALIBRATION_FAILED = 0x05
    IN_PROGRESS = 0x06
    ERR_POWER_FAULT = 0x07
    ERR_DRIVER_FAULT = 0x08
    ERR_ACCESS_DENIED = 0x09


class CalibrationPhase(IntEnum):
    SETTLE = 0
    SCAN_FWD = 1
    SCAN_REV = 2
    COMPUTE = 3
    DONE = 4
    FAILED = 5


class AxisState(IntEnum):
    IDLE = 0
    CALIBRATING_ENCODER = 1
    HOMING = 2
    CALIBRATING_ANTICOGGING = 3
    RUNNING = 4
    ERROR = 5


class CalibrationFailReason(IntEnum):
    NONE = 0
    ENCODER_DIRECTION_UNCLEAR = 1
    CPR_POLE_PAIRS_MISMATCH = 2
    ENCODER_DIRECTION_REVERSED = 3
    NOT_HOMED = 4


class HomingFailReason(IntEnum):
    NONE = 0
    NOT_READY = 1
    ARM_FAILED = 2
    INDEX_NOT_FOUND = 3


class AnticoggingPhase(IntEnum):
    SETTLE = 0
    SCAN = 1
    COMPUTE = 2
    DONE = 3
    FAILED = 4


class AnticoggingFailReason(IntEnum):
    NONE = 0
    NOT_READY = 1
    ARM_FAILED = 2
    VELOCITY_NOT_REACHED = 3
    NOT_HOMED = 4


class ValueType(IntEnum):
    NONE = 0x00
    U32 = 0x01
    I32 = 0x02
    F32 = 0x03
    BOOL = 0x04


class ParamId(IntEnum):
    # 0x0000-0x00FF: meta
    FW_VERSION = 0x0001
    CONFIG_SCHEMA_VERSION = 0x0002

    # 0x0100-0x01FF: current and bus limits
    MAX_CURRENT = 0x0100
    VBUS_DIVIDER_RATIO = 0x0101
    VBUS_MIN_VOLTAGE = 0x0102
    VBUS_MAX_VOLTAGE = 0x0103

    # 0x0200-0x02FF: pwm
    PWM_FREQ_HZ = 0x0200
    PWM_DEADTIME_NS = 0x0201

    # 0x0300-0x03FF: current sensing
    SHUNT_RESISTANCE = 0x0300
    CURRENT_AMP_GAIN = 0x0301

    # 0x0400-0x04FF: motor parameters
    MOTOR_POLE_PAIRS = 0x0400
    MOTOR_FLUX_LINKAGE = 0x0401
    PHASE_RESISTANCE = 0x0402
    PHASE_INDUCTANCE = 0x0403

    # 0x0500-0x05FF: current loop
    CURRENT_BANDWIDTH_RAD_S = 0x0500
    CURRENT_KP = 0x0501
    CURRENT_KI = 0x0502

    # 0x0600-0x06FF: motor calibration
    CALIBRATION_MAX_VOLTAGE = 0x0600
    CALIBRATION_TEST_CURRENT = 0x0601
    MOTOR_CALIBRATED = 0x0602

    # 0x0700-0x07FF: encoder
    ENCODER_CPR = 0x0700
    ENCODER_REVERSE = 0x0701
    ENCODER_MECHANICAL_OFFSET = 0x0702
    ENCODER_OFFSET_RAD = 0x0703
    ENCODER_CALIBRATED = 0x0704

    # 0x0800-0x08FF: homing
    ENCODER_USE_INDEX_Z = 0x0800
    ENCODER_HOME_ON_BOOT = 0x0801

    # 0x0900-0x09FF: anticogging
    ANTICOGGING_ENABLED = 0x0900
    ANTICOGGING_CALIBRATED = 0x0901
    ANTICOGGING_SCAN_VELOCITY_RAD_S = 0x0902

    # 0x0A00-0x0AFF: motion limits
    MAX_VELOCITY_RAD_S = 0x0A00
    MAX_ACCELERATION_RAD_S2 = 0x0A01
    STEERING_RANGE_DEG = 0x0A02

    # 0x0B00-0x0BFF: brake resistor
    BRAKE_RESISTOR_ENABLED = 0x0B00
    BRAKE_RESISTOR_RESISTANCE_OHM = 0x0B01
    BRAKE_RESISTOR_POWER_RATING_W = 0x0B02
    BRAKE_RESISTOR_MAX_REGEN_CURRENT = 0x0B03
    BRAKE_RESISTOR_TRIGGER_VOLTAGE = 0x0B04

    # 0x0C00-0x0CFF: force feedback
    FFB_ENABLED_ON_BOOT = 0x0C00
    FFB_ACTIVE = 0x0C01
    FFB_SLEW_RATE_A_PER_S = 0x0C02
    IDLE_SPRING_ENABLED = 0x0C03
    IDLE_SPRING_STIFFNESS = 0x0C04
    IDLE_SPRING_DAMPING = 0x0C05
    FFB_GAIN = 0x0C06
    FFB_DETAIL = 0x0C07
    NATURAL_DAMPING = 0x0C08
    NATURAL_FRICTION = 0x0C09
    NATURAL_INERTIA = 0x0C0A

    # 0x0D00-0x0DFF: bumpstop
    BUMPSTOP_ENABLED = 0x0D00
    BUMPSTOP_RANGE_DEG = 0x0D01
    BUMPSTOP_STIFFNESS = 0x0D02
    BUMPSTOP_DAMPING = 0x0D03

    # 0x0E00-0x0EFF: startup sound
    STARTUP_SOUND_ENABLED = 0x0E00
    STARTUP_SOUND_VOLUME_A = 0x0E01
    STARTUP_SOUND_PLAY = 0x0E02

    # 0xFE00-0xFEFF: calibration type selectors
    CALTYPE_MOTOR = 0xFE00
    CALTYPE_ENCODER = 0xFE01
    CALTYPE_HOME = 0xFE02
    CALTYPE_ANTICOGGING = 0xFE03

    # 0xFF00-0xFFFF: diagnostics
    DRV_STATUS1 = 0xFF00
    DRV_STATUS2 = 0xFF01
    DRV_HAS_FAULT = 0xFF02
    DRV_CONTROL1 = 0xFF03
    DRV_CONTROL2 = 0xFF04
    ARM_FAIL_REASON = 0xFF05
    CALIBRATION_FAIL_REASON = 0xFF06
    ALIGNMENT_FAIL_REASON = 0xFF07
    ENCODER_POSITION_COUNTS = 0xFF08
    ENCODER_CALIBRATION_PHASE = 0xFF09
    HOMING_FAIL_REASON = 0xFF0A
    HOMING_IN_PROGRESS = 0xFF0B
    ANTICOGGING_FAIL_REASON = 0xFF0C
    ANTICOGGING_PHASE = 0xFF0D
    AXIS_STATE = 0xFF0E
    POSITION_REFERENCED = 0xFF0F
    CALIBRATION_SCAN_DELTA_COUNTS = 0xFF10
    SOUND_PEAK_VOLTAGE = 0xFF11
    SOUND_PEAK_CURRENT = 0xFF12
    GAME_FFB_ACTIVE = 0xFF13
    WHEEL_ANGLE_DEG = 0xFF14
    FFB_REPORT_RATE_HZ = 0xFF15
    FFB_FORCE_RATE_HZ = 0xFF16
    FFB_MAX_FORCE_GAP_US = 0xFF17


READ_ONLY_PARAMS = {
    ParamId.FW_VERSION,
    ParamId.CONFIG_SCHEMA_VERSION,
}


@dataclass
class Response:
    status: Status
    command: int
    param_id: int
    value_type: ValueType
    raw_value: bytes
    sequence: int

    def value(self) -> Union[int, float, bool, None]:
        if self.value_type == ValueType.F32:
            return struct.unpack("<f", self.raw_value)[0]
        if self.value_type == ValueType.U32:
            return struct.unpack("<I", self.raw_value)[0]
        if self.value_type == ValueType.I32:
            return struct.unpack("<i", self.raw_value)[0]
        if self.value_type == ValueType.BOOL:
            return self.raw_value[0] != 0
        return None


class ProtocolError(RuntimeError):
    pass


class _NoReply(ProtocolError):
    pass


def _pack_value(value_type: ValueType, value) -> bytes:
    if value_type == ValueType.F32:
        return struct.pack("<f", float(value))
    if value_type == ValueType.U32:
        return struct.pack("<I", int(value))
    if value_type == ValueType.I32:
        return struct.pack("<i", int(value))
    if value_type == ValueType.BOOL:
        return bytes([1 if value else 0, 0, 0, 0])
    return b"\x00\x00\x00\x00"


class ConfigClient:
    _REPLY_TIMEOUT_S = 0.1

    def __init__(self):
        self._dev = None
        self.serial: str | None = None
        self._sequence = 0
        self._lock = threading.RLock()
        self._client_tag = random.randint(1, 0xFFFF)
        self._waiting_seq: int | None = None
        self._reply: bytes | None = None
        self._reply_event = threading.Event()

    def connect(self, vid: int = USB_VID, pid: int = USB_PID) -> None:
        devices = hid.HidDeviceFilter(vendor_id=vid, product_id=pid).get_devices()
        if not devices:
            raise ProtocolError("device not found")

        vendor_dev = None
        for dev in devices:
            dev.open()
            if dev.hid_caps.usage_page == 0xFF00:
                vendor_dev = dev
            else:
                dev.close()

        if vendor_dev is None:
            raise ProtocolError("Vendor config interface (usage page 0xFF00) not found")

        self._dev = vendor_dev
        self.serial = (vendor_dev.serial_number or "").removeprefix("CRAMBER-DD-") or None
        vendor_dev.set_raw_data_handler(self._on_input_report)

    on_telemetry = None

    def _on_input_report(self, data) -> None:
        try:
            if not data:
                return
            if data[0] == REPORT_ID_RESPONSE and len(data) > REPORT_SIZE:
                raw = bytes(data[1 : REPORT_SIZE + 1])
                tag = struct.unpack_from("<H", raw, 10)[0]
                if tag == self._client_tag and raw[9] == self._waiting_seq:
                    self._reply = raw
                    self._reply_event.set()
            elif data[0] == REPORT_ID_TELEMETRY and self.on_telemetry is not None:
                self.on_telemetry(bytes(data[1:]))
        except Exception:
            pass

    def telemetry_start(self, mask: int) -> Response:
        return self._transact(Command.TELEMETRY, mask, ValueType.NONE, b"\x01\x00\x00\x00")

    def telemetry_keepalive(self) -> Response:
        return self._transact(Command.TELEMETRY, 0, ValueType.NONE, b"\x02\x00\x00\x00")

    def telemetry_stop(self) -> Response:
        return self._transact(Command.TELEMETRY, 0, ValueType.NONE, b"\x00\x00\x00\x00")

    def close(self) -> None:
        if self._dev is not None:
            self._dev.close()
            self._dev = None

    def is_connected(self) -> bool:
        return self._dev is not None and self._dev.is_plugged()

    def _next_sequence(self) -> int:
        self._sequence = (self._sequence + 1) & 0xFF
        return self._sequence

    def _transact(
        self, command: Command, param_id: int, value_type: ValueType, value_bytes: bytes
    ) -> Response:
        with self._lock:
            return self._transact_locked(command, param_id, value_type, value_bytes)

    _RESENDABLE = {Command.GET, Command.GET_STATUS, Command.GET_DEFAULT, Command.TELEMETRY}

    def _transact_locked(
        self, command: Command, param_id: int, value_type: ValueType, value_bytes: bytes
    ) -> Response:
        attempts = 3 if command in self._RESENDABLE else 1
        for attempt in range(attempts):
            try:
                return self._transact_once(command, param_id, value_type, value_bytes)
            except _NoReply:
                if attempt == attempts - 1:
                    raise

    def _transact_once(
        self, command: Command, param_id: int, value_type: ValueType, value_bytes: bytes
    ) -> Response:
        if self._dev is None:
            raise ProtocolError("not connected")

        sequence = self._next_sequence()

        payload = bytearray(REPORT_SIZE)
        payload[0] = int(command)
        payload[1:3] = struct.pack("<H", param_id)
        payload[3] = int(value_type)
        payload[4:8] = value_bytes
        payload[8] = sequence
        payload[9:11] = struct.pack("<H", self._client_tag)

        report = bytes([REPORT_ID_COMMAND]) + bytes(payload)

        self._reply = None
        self._reply_event.clear()
        self._waiting_seq = sequence
        try:
            self._dev.send_output_report(report)
            got_reply = self._reply_event.wait(self._REPLY_TIMEOUT_S)
        except Exception as exc:
            self.close()
            raise ProtocolError(f"device disconnected: {exc}") from exc
        finally:
            self._waiting_seq = None
        if not got_reply or self._reply is None:
            raise _NoReply(f"no reply from the base (command {command.name}, sequence {sequence})")

        raw = self._reply
        status = Status(raw[0])
        resp_command = raw[1]
        resp_param_id = struct.unpack("<H", bytes(raw[2:4]))[0]
        resp_value_type = ValueType(raw[4])
        resp_value = bytes(raw[5:9])
        resp_sequence = raw[9]

        return Response(
            status,
            resp_command,
            resp_param_id,
            resp_value_type,
            resp_value,
            resp_sequence,
        )

    def get(self, param_id: ParamId) -> Response:
        return self._transact(
            Command.GET, int(param_id), ValueType.NONE, b"\x00\x00\x00\x00"
        )

    def set(self, param_id: ParamId, value_type: ValueType, value) -> Response:
        value_bytes = _pack_value(value_type, value)
        return self._transact(Command.SET, int(param_id), value_type, value_bytes)

    def save(self) -> Response:
        return self._transact(Command.SAVE, 0, ValueType.NONE, b"\x00\x00\x00\x00")

    def calibrate(self, caltype: ParamId) -> Response:
        return self._transact(
            Command.CALIBRATE, int(caltype), ValueType.NONE, b"\x00\x00\x00\x00"
        )

    def clear_fault(self) -> Response:
        return self._transact(
            Command.CLEAR_FAULT, 0, ValueType.NONE, b"\x00\x00\x00\x00"
        )

    def set_factory_mode(self, enabled: bool) -> Response:
        value = b"\x01\x00\x00\x00" if enabled else b"\x00\x00\x00\x00"
        return self._transact(Command.FACTORY_MODE, 0, ValueType.BOOL, value)

    def get_status(self) -> Response:
        return self._transact(
            Command.GET_STATUS, 0, ValueType.NONE, b"\x00\x00\x00\x00"
        )

    def factory_reset(self) -> Response:
        return self._transact(
            Command.FACTORY_RESET, 0, ValueType.NONE, b"\x00\x00\x00\x00"
        )

    def reboot(self) -> Response:
        return self._transact(Command.REBOOT, 0, ValueType.NONE, b"\x00\x00\x00\x00")

    def poll_until_done(
        self, timeout_s: float = 5.0, interval_s: float = 0.2
    ) -> Response:
        deadline = time.monotonic() + timeout_s
        last = self.get_status()
        while last.status == Status.IN_PROGRESS and time.monotonic() < deadline:
            time.sleep(interval_s)
            last = self.get_status()
        return last

    def poll_encoder_calibration(
        self, timeout_s: float = 300.0, interval_s: float = 0.5
    ) -> CalibrationPhase:
        deadline = time.monotonic() + timeout_s
        phase = CalibrationPhase(self.get(ParamId.ENCODER_CALIBRATION_PHASE).value())
        while (
            phase not in (CalibrationPhase.DONE, CalibrationPhase.FAILED)
            and time.monotonic() < deadline
        ):
            time.sleep(interval_s)
            phase = CalibrationPhase(self.get(ParamId.ENCODER_CALIBRATION_PHASE).value())

        if phase not in (CalibrationPhase.DONE, CalibrationPhase.FAILED):
            raise ProtocolError(
                f"encoder calibration poll timed out after {timeout_s}s (phase={phase.name})"
            )

        return phase

    def poll_homing(
        self, timeout_s: float = 30.0, interval_s: float = 0.2
    ) -> HomingFailReason:
        deadline = time.monotonic() + timeout_s
        in_progress = bool(self.get(ParamId.HOMING_IN_PROGRESS).value())
        while in_progress and time.monotonic() < deadline:
            time.sleep(interval_s)
            in_progress = bool(self.get(ParamId.HOMING_IN_PROGRESS).value())

        if in_progress:
            raise ProtocolError(f"homing poll timed out after {timeout_s}s")

        return HomingFailReason(self.get(ParamId.HOMING_FAIL_REASON).value())

    def poll_anticogging_calibration(
        self, timeout_s: float = 60.0, interval_s: float = 0.5
    ) -> AnticoggingPhase:
        deadline = time.monotonic() + timeout_s
        phase = AnticoggingPhase(self.get(ParamId.ANTICOGGING_PHASE).value())
        while (
            phase not in (AnticoggingPhase.DONE, AnticoggingPhase.FAILED)
            and time.monotonic() < deadline
        ):
            time.sleep(interval_s)
            phase = AnticoggingPhase(self.get(ParamId.ANTICOGGING_PHASE).value())

        if phase not in (AnticoggingPhase.DONE, AnticoggingPhase.FAILED):
            raise ProtocolError(
                f"anticogging calibration poll timed out after {timeout_s}s (phase={phase.name})"
            )

        return phase
