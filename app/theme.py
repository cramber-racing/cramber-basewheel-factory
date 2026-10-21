import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

BG = "#050505"
CARD = "#111111"
CARD_HOVER = "#1a1a1a"
FIELD = "#181818"
BORDER = "#262626"
FG = "#f2f2f2"
MUTED = "#8a8a8a"
PRIMARY = "#2563eb"
PRIMARY_HOVER = "#3b74f0"
DANGER = "#e7000b"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"

PAD = 12


def _family(*candidates: str) -> str:
    available = set(tkfont.families())
    return next((f for f in candidates if f in available), "TkDefaultFont")


def apply(root: tk.Tk) -> dict[str, tuple]:
    sans = _family("Segoe UI Variable Text", "Segoe UI", "Helvetica")
    mono = _family("JetBrains Mono", "Cascadia Mono", "Consolas", "Courier New")
    fonts = {
        "body": (sans, 10),
        "small": (sans, 9),
        "title": (sans, 16, "bold"),
        "section": (sans, 11, "bold"),
        "mono": (mono, 9),
        "mono_big": (mono, 14, "bold"),
    }

    root.configure(bg=BG)
    root.option_add("*Font", fonts["body"])
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", PRIMARY)
    root.option_add("*TCombobox*Listbox.font", fonts["body"])

    s = ttk.Style(root)
    s.theme_use("clam")

    s.configure(".", background=BG, foreground=FG, fieldbackground=FIELD, bordercolor=BORDER,
                lightcolor=BORDER, darkcolor=BORDER, troughcolor=CARD, focuscolor=PRIMARY,
                selectbackground=PRIMARY, selectforeground=FG, insertcolor=FG, font=fonts["body"])

    s.configure("TFrame", background=BG)
    s.configure("Card.TFrame", background=CARD)
    s.configure("Bar.TFrame", background=CARD)

    s.configure("TLabel", background=BG, foreground=FG)
    for parent, bg in (("", BG), ("Card.", CARD)):
        s.configure(f"{parent}Muted.TLabel", background=bg, foreground=MUTED, font=fonts["small"])
        s.configure(f"{parent}Section.TLabel", background=bg, foreground=FG, font=fonts["section"])
        s.configure(f"{parent}Mono.TLabel", background=bg, foreground=MUTED, font=fonts["mono"])
        s.configure(f"{parent}Dirty.TLabel", background=bg, foreground=PRIMARY)
        s.configure(f"{parent}Ok.TLabel", background=bg, foreground=SUCCESS)
        s.configure(f"{parent}Warn.TLabel", background=bg, foreground=WARNING)
        s.configure(f"{parent}Error.TLabel", background=bg, foreground=DANGER)
        s.configure(f"{parent}Primary.TLabel", background=bg, foreground=PRIMARY)
    s.configure("Card.TLabel", background=CARD, foreground=FG)
    s.configure("Title.TLabel", background=BG, foreground=FG, font=fonts["title"])
    s.configure("BarTitle.TLabel", background=CARD, foreground=FG, font=fonts["section"])
    s.configure("Value.TLabel", background=CARD, foreground=FG, font=fonts["mono_big"])

    s.configure("TButton", background=CARD_HOVER, foreground=FG, bordercolor=BORDER, focusthickness=1,
                focuscolor=PRIMARY, padding=(14, 6), relief="solid", borderwidth=1)
    s.map("TButton", background=[("disabled", CARD), ("active", "#242424")],
          foreground=[("disabled", "#5c5c5c")], bordercolor=[("disabled", "#2c2c2c"), ("active", MUTED)],
          lightcolor=[("disabled", CARD)], darkcolor=[("disabled", CARD)])
    s.configure("Primary.TButton", background=PRIMARY, foreground="#ffffff", bordercolor=PRIMARY)
    s.map("Primary.TButton", background=[("disabled", "#1c2a4a"), ("active", PRIMARY_HOVER)],
          foreground=[("disabled", "#6b7a99")],
          bordercolor=[("disabled", "#1c2a4a"), ("active", PRIMARY_HOVER)])
    s.configure("Danger.TButton", background=CARD_HOVER, foreground=DANGER, bordercolor="#5a1a1a")
    s.map("Danger.TButton", background=[("active", "#2a0d0d"), ("disabled", CARD)],
          foreground=[("disabled", "#5a3a3a")])
    s.configure("Small.TButton", padding=(8, 2), font=fonts["small"])

    s.configure("TEntry", fieldbackground=FIELD, foreground=FG, bordercolor=BORDER, padding=(6, 4))
    s.map("TEntry", bordercolor=[("focus", PRIMARY)], fieldbackground=[("readonly", CARD)],
          foreground=[("readonly", MUTED)])
    s.configure("Dirty.TEntry", fieldbackground=FIELD, bordercolor=PRIMARY, lightcolor=PRIMARY, darkcolor=PRIMARY)
    s.configure("TCombobox", fieldbackground=FIELD, background=CARD_HOVER, foreground=FG, arrowcolor=FG,
                bordercolor=BORDER, padding=(6, 4))
    s.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", FG)],
          bordercolor=[("focus", PRIMARY)])
    s.configure("TCheckbutton", background=CARD, foreground=FG, indicatorbackground=FIELD,
                indicatorforeground=FG, focuscolor=CARD)
    s.map("TCheckbutton", background=[("active", CARD)],
          indicatorbackground=[("selected", PRIMARY), ("disabled", CARD)])

    s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
    s.configure("TNotebook.Tab", background=BG, foreground=MUTED, padding=(16, 8), borderwidth=0,
                bordercolor=BG, lightcolor=BG, darkcolor=BG)
    s.map("TNotebook.Tab", background=[("selected", CARD), ("active", CARD_HOVER)],
          foreground=[("selected", FG), ("active", FG)],
          lightcolor=[("selected", CARD)], bordercolor=[("selected", CARD)], darkcolor=[("selected", CARD)])
    s.configure("TNotebook", bordercolor=BG, lightcolor=BG, darkcolor=BG)

    s.configure("Vertical.TScrollbar", background=CARD_HOVER, troughcolor=BG, bordercolor=BG,
                arrowcolor=MUTED, gripcount=0, relief="flat")
    s.map("Vertical.TScrollbar", background=[("active", BORDER)])

    s.configure("TSeparator", background=BORDER)
    _dark_title_bar(root)
    return fonts


def _dark_title_bar(root: tk.Tk):
    try:
        import ctypes

        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        value = ctypes.c_int(1)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:
        pass
