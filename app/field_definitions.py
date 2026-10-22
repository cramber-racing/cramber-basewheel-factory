from hid_protocol import ParamId, ValueType

F32, U32, I32, BOOL = ValueType.F32, ValueType.U32, ValueType.I32, ValueType.BOOL

CURRENT_AMP_GAIN_CHOICES = (10.0, 20.0, 40.0, 80.0)

MOTOR_DRIVE = [
    ("Motor", [
        ("Pole pairs", ParamId.MOTOR_POLE_PAIRS, U32, False, None),
        ("Phase resistance (ohm)", ParamId.PHASE_RESISTANCE, F32, False, None),
        ("Phase inductance (H)", ParamId.PHASE_INDUCTANCE, F32, False, None),
        ("Flux linkage (Wb)", ParamId.MOTOR_FLUX_LINKAGE, F32, False, None),
        ("Calibration max voltage (V)", ParamId.CALIBRATION_MAX_VOLTAGE, F32, False, None),
        ("Calibration test current (A)", ParamId.CALIBRATION_TEST_CURRENT, F32, False, None),
        ("Motor calibrated", ParamId.MOTOR_CALIBRATED, BOOL, False, None),
    ]),
    ("Current loop", [
        ("Bandwidth (rad/s)", ParamId.CURRENT_BANDWIDTH_RAD_S, F32, False, None),
        ("Kp", ParamId.CURRENT_KP, F32, False, None),
        ("Ki", ParamId.CURRENT_KI, F32, False, None),
    ]),
    ("PWM", [
        ("Frequency (Hz)", ParamId.PWM_FREQ_HZ, U32, False, None),
        ("Deadtime (ns)", ParamId.PWM_DEADTIME_NS, U32, False, None),
    ]),
    ("Current sensing", [
        ("Shunt resistance (ohm)", ParamId.SHUNT_RESISTANCE, F32, False, None),
        ("Amplifier gain (V/V)", ParamId.CURRENT_AMP_GAIN, F32, False, CURRENT_AMP_GAIN_CHOICES),
    ]),
]

ENCODER = [
    ("Encoder", [
        ("Counts per rev (CPR)", ParamId.ENCODER_CPR, U32, False, None),
        ("Reverse direction", ParamId.ENCODER_REVERSE, BOOL, False, None),
        ("Electrical offset (rad)", ParamId.ENCODER_OFFSET_RAD, F32, False, None),
        ("Encoder calibrated", ParamId.ENCODER_CALIBRATED, BOOL, False, None),
    ]),
    ("Homing & center", [
        ("Use index (Z) pulse", ParamId.ENCODER_USE_INDEX_Z, BOOL, False, None),
        ("Home on boot", ParamId.ENCODER_HOME_ON_BOOT, BOOL, False, None),
        ("Center offset (counts)", ParamId.ENCODER_MECHANICAL_OFFSET, I32, False, None),
    ]),
    ("Anticogging", [
        ("Enabled", ParamId.ANTICOGGING_ENABLED, BOOL, False, None),
        ("Calibrated", ParamId.ANTICOGGING_CALIBRATED, BOOL, True, None),
        ("Scan velocity (rad/s)", ParamId.ANTICOGGING_SCAN_VELOCITY_RAD_S, F32, False, None),
    ]),
]

POWER = [
    ("Supply", [
        ("Max current (A)", ParamId.MAX_CURRENT, F32, False, None),
        ("VBUS divider ratio", ParamId.VBUS_DIVIDER_RATIO, F32, False, None),
        ("VBUS min voltage (V)", ParamId.VBUS_MIN_VOLTAGE, F32, False, None),
        ("VBUS max voltage (V)", ParamId.VBUS_MAX_VOLTAGE, F32, False, None),
    ]),
    ("Brake resistor", [
        ("Enabled", ParamId.BRAKE_RESISTOR_ENABLED, BOOL, False, None),
        ("Resistance (ohm)", ParamId.BRAKE_RESISTOR_RESISTANCE_OHM, F32, False, None),
        ("Power rating (W)", ParamId.BRAKE_RESISTOR_POWER_RATING_W, F32, False, None),
        ("Max regen current (A)", ParamId.BRAKE_RESISTOR_MAX_REGEN_CURRENT, F32, False, None),
        ("Trigger voltage (V)", ParamId.BRAKE_RESISTOR_TRIGGER_VOLTAGE, F32, False, None),
    ]),
]

USER_DEFAULTS = [
    ("Force feedback", [
        ("Steering range (deg)", ParamId.STEERING_RANGE_DEG, F32, False, None),
        ("Gain (0-1)", ParamId.FFB_GAIN, F32, False, None),
        ("Detail (0-1)", ParamId.FFB_DETAIL, F32, False, None),
        ("FFB on at boot", ParamId.FFB_ENABLED_ON_BOOT, BOOL, False, None),
        ("Slew rate (A/s)", ParamId.FFB_SLEW_RATE_A_PER_S, F32, False, None),
        ("Max velocity (rad/s)", ParamId.MAX_VELOCITY_RAD_S, F32, False, None),
        ("Max acceleration (rad/s^2)", ParamId.MAX_ACCELERATION_RAD_S2, F32, False, None),
    ]),
    ("Effects", [
        ("Damping (0-1)", ParamId.NATURAL_DAMPING, F32, False, None),
        ("Friction (0-1)", ParamId.NATURAL_FRICTION, F32, False, None),
        ("Inertia (0-1)", ParamId.NATURAL_INERTIA, F32, False, None),
    ]),
    ("Idle spring", [
        ("Enabled", ParamId.IDLE_SPRING_ENABLED, BOOL, False, None),
        ("Strength (0-1)", ParamId.IDLE_SPRING_STIFFNESS, F32, False, None),
        ("Smoothing (0-1)", ParamId.IDLE_SPRING_DAMPING, F32, False, None),
    ]),
    ("End stops", [
        ("Enabled", ParamId.BUMPSTOP_ENABLED, BOOL, False, None),
        ("Wall width (deg)", ParamId.BUMPSTOP_RANGE_DEG, F32, False, None),
        ("Hardness (0-1)", ParamId.BUMPSTOP_STIFFNESS, F32, False, None),
        ("Cushion (0-1)", ParamId.BUMPSTOP_DAMPING, F32, False, None),
    ]),
    ("Startup sound", [
        ("Enabled", ParamId.STARTUP_SOUND_ENABLED, BOOL, False, None),
        ("Volume (A)", ParamId.STARTUP_SOUND_VOLUME_A, F32, False, None),
    ]),
]

DIAGNOSTICS = [
    ("Live", [
        ("Wheel angle (deg)", ParamId.WHEEL_ANGLE_DEG, F32, True, None),
        ("Encoder position (counts)", ParamId.ENCODER_POSITION_COUNTS, I32, True, None),
        ("Homed (index found)", ParamId.POSITION_REFERENCED, BOOL, True, None),
        ("Game driving FFB", ParamId.GAME_FFB_ACTIVE, BOOL, True, None),
        ("Encoder calibration phase", ParamId.ENCODER_CALIBRATION_PHASE, U32, True, None),
        ("Anticogging phase", ParamId.ANTICOGGING_PHASE, U32, True, None),
    ]),
    ("FFB link (last second)", [
        ("FFB reports from game (/s)", ParamId.FFB_REPORT_RATE_HZ, U32, True, None),
        ("Constant force updates (/s)", ParamId.FFB_FORCE_RATE_HZ, U32, True, None),
        ("Longest gap between updates (us)", ParamId.FFB_MAX_FORCE_GAP_US, U32, True, None),
    ]),
    ("Motor driver (DRV8301)", [
        ("nFAULT active", ParamId.DRV_HAS_FAULT, BOOL, True, None),
        ("STATUS_1", ParamId.DRV_STATUS1, U32, True, None),
        ("STATUS_2", ParamId.DRV_STATUS2, U32, True, None),
        ("CONTROL_1 readback", ParamId.DRV_CONTROL1, U32, True, None),
        ("CONTROL_2 readback", ParamId.DRV_CONTROL2, U32, True, None),
    ]),
    ("Last errors", [
        ("arm() fail reason", ParamId.ARM_FAIL_REASON, U32, True, None),
        ("Motor calibration fail reason", ParamId.CALIBRATION_FAIL_REASON, U32, True, None),
        ("Encoder calibration fail reason", ParamId.ALIGNMENT_FAIL_REASON, U32, True, None),
        ("Homing fail reason", ParamId.HOMING_FAIL_REASON, U32, True, None),
        ("Anticogging fail reason", ParamId.ANTICOGGING_FAIL_REASON, U32, True, None),
        ("Startup sound peak current (A)", ParamId.SOUND_PEAK_CURRENT, F32, True, None),
    ]),
]

PARAM_TABS = [
    ("Motor & Drive", MOTOR_DRIVE),
    ("Encoder", ENCODER),
    ("Power", POWER),
    ("User Defaults", USER_DEFAULTS),
    ("Diagnostics", DIAGNOSTICS),
]
