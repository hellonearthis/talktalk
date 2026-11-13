"""TalkTalk tray entry point: windowless exe-friendly launcher (the script version stays in app.py)."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import winreg

import pyperclip
import pystray
from PIL import Image, ImageDraw
from pynput import keyboard

from app import copy_selection_to_clipboard
from audio_player import StreamingTTSPlayer
from tts_engines import KokoroTTSEngine

APP_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "TalkTalk")
MODEL_DIR = os.path.join(APP_DIR, "models", "kokoro")
LOG_PATH = os.path.join(APP_DIR, "talktalk.log")
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")
HOTKEY = "<ctrl>+<shift>+<space>"
DEFAULT_SPEED = 1.3
SPEED_CHOICES = (1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 2.0)
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "TalkTalk"


def load_saved_speed() -> float:
    """Return the speed saved by the tray menu, or the default if missing/invalid."""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as settings_file:
            saved_speed = float(json.load(settings_file)["speed"])
    except (OSError, ValueError, KeyError, TypeError):
        return DEFAULT_SPEED
    return saved_speed if saved_speed in SPEED_CHOICES else DEFAULT_SPEED


def save_speed(speed: float) -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as settings_file:
        json.dump({"speed": speed}, settings_file)


def format_speed_label(speed: float) -> str:
    return f"{speed:g}x"


def build_icon_image() -> Image.Image:
    """Draw a simple speech-bubble tray icon."""
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 6, 60, 46), radius=12, fill=(37, 99, 235, 255))
    draw.polygon([(16, 44), (16, 60), (32, 44)], fill=(37, 99, 235, 255))
    for x in (20, 30, 40):
        draw.ellipse((x, 22, x + 6, 28), fill=(255, 255, 255, 255))
    return image


def redirect_output_to_log() -> None:
    """Windowed exes have no console, so send print/errors to a log file."""
    os.makedirs(APP_DIR, exist_ok=True)
    log_file = open(LOG_PATH, "a", buffering=1, encoding="utf-8")
    sys.stdout = log_file
    sys.stderr = log_file


def is_autostart_enabled() -> bool:
    """Return True if TalkTalk is registered in the per-user Windows Run key."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as run_key:
            winreg.QueryValueEx(run_key, RUN_VALUE_NAME)
            return True
    except FileNotFoundError:
        return False


def set_autostart(enabled: bool) -> None:
    """Add or remove the Run-key entry that launches the exe at login."""
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
    ) as run_key:
        if enabled:
            winreg.SetValueEx(run_key, RUN_VALUE_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
        else:
            try:
                winreg.DeleteValue(run_key, RUN_VALUE_NAME)
            except FileNotFoundError:
                pass


def main() -> None:
    redirect_output_to_log()
    print(f"\n--- TalkTalk started {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    engine = KokoroTTSEngine(speed=load_saved_speed(), model_dir=MODEL_DIR)
    player = StreamingTTSPlayer(engine)
    key_controller = keyboard.Controller()

    def read_worker() -> None:
        try:
            text = copy_selection_to_clipboard(key_controller)
        except Exception as exc:
            print(f"[Clipboard] Failed: {exc}")
            return
        print(f"[Hotkey] Read {len(text)} chars")
        player.speak(text)

    def on_toggle() -> None:
        if player.is_playing:
            print("[Hotkey] Stop")
            player.stop()
        else:
            threading.Thread(target=read_worker, daemon=True).start()

    listener = keyboard.GlobalHotKeys({HOTKEY: on_toggle})
    listener.start()

    def on_quit(icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        player.stop()
        listener.stop()
        icon.stop()

    def on_open_log(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        os.startfile(APP_DIR)

    def on_toggle_autostart(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        set_autostart(not is_autostart_enabled())

    def make_speed_item(speed_choice: float) -> pystray.MenuItem:
        def on_select(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
            engine.speed = speed_choice
            save_speed(speed_choice)
            print(f"[Speed] {speed_choice}")

        return pystray.MenuItem(
            format_speed_label(speed_choice),
            on_select,
            checked=lambda _item: engine.speed == speed_choice,
            radio=True,
        )

    speed_menu = pystray.Menu(*(make_speed_item(choice) for choice in SPEED_CHOICES))

    menu = pystray.Menu(
        pystray.MenuItem(f"TalkTalk ({HOTKEY})", None, enabled=False),
        pystray.MenuItem("Speed", speed_menu),
        pystray.MenuItem(
            "Start with Windows",
            on_toggle_autostart,
            checked=lambda _item: is_autostart_enabled(),
            visible=getattr(sys, "frozen", False),
        ),
        pystray.MenuItem("Open log folder", on_open_log),
        pystray.MenuItem("Quit", on_quit),
    )
    pystray.Icon("TalkTalk", build_icon_image(), "TalkTalk", menu).run()


if __name__ == "__main__":
    main()

