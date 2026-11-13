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
DEFAULT_SPEED = 1.3
SPEED_CHOICES = (1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 2.0)
HOTKEY_CTRL_SHIFT_SPACE = "Ctrl+Shift+Space"
HOTKEY_KEYPAD_0 = "Keypad 0"
HOTKEY_CHOICES = (HOTKEY_CTRL_SHIFT_SPACE, HOTKEY_KEYPAD_0)
DEFAULT_HOTKEY = HOTKEY_CTRL_SHIFT_SPACE
VK_NUMPAD0 = 0x60
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
LLKHF_INJECTED = 0x10
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "TalkTalk"


def load_settings() -> dict:
    """Return saved settings, or an empty dict if the file is missing or invalid."""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as settings_file:
            loaded = json.load(settings_file)
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def save_setting(key: str, value: object) -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as settings_file:
        json.dump({**load_settings(), key: value}, settings_file)


def load_saved_speed() -> float:
    """Return the speed saved by the tray menu, or the default if missing/invalid."""
    saved_speed = load_settings().get("speed")
    return saved_speed if saved_speed in SPEED_CHOICES else DEFAULT_SPEED


def load_saved_hotkey() -> str:
    saved_hotkey = load_settings().get("hotkey")
    return saved_hotkey if saved_hotkey in HOTKEY_CHOICES else DEFAULT_HOTKEY


def format_speed_label(speed: float) -> str:
    return f"{speed:g}x"


def start_hotkey_listener(hotkey_name: str, on_toggle) -> keyboard.Listener:
    """Start a global listener for the named hotkey and return it."""
    if hotkey_name == HOTKEY_CTRL_SHIFT_SPACE:
        listener = keyboard.GlobalHotKeys({"<ctrl>+<shift>+<space>": on_toggle})
        listener.start()
        return listener

    # Keypad 0 is a bare key, so it must be swallowed or it would type "0"
    # over the highlighted text before we get to copy it.
    held_keys: set[int] = set()
    listener_holder: list[keyboard.Listener] = []

    def win32_filter(message: int, key_data) -> bool:
        if key_data.vkCode != VK_NUMPAD0 or key_data.flags & LLKHF_INJECTED:
            return True
        if message in (WM_KEYDOWN, WM_SYSKEYDOWN):
            if not held_keys:  # ignore auto-repeat while the key stays down
                held_keys.add(VK_NUMPAD0)
                on_toggle()
        else:
            held_keys.clear()
        listener_holder[0].suppress_event()
        return False

    listener = keyboard.Listener(win32_event_filter=win32_filter)
    listener_holder.append(listener)
    listener.start()
    return listener


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

    # Shell state: the active hotkey name and its listener (swapped from the tray menu)
    active_hotkey = {"name": load_saved_hotkey(), "listener": None}
    active_hotkey["listener"] = start_hotkey_listener(active_hotkey["name"], on_toggle)
    print(f"[Hotkey] {active_hotkey['name']}")

    def on_quit(icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        player.stop()
        active_hotkey["listener"].stop()
        icon.stop()

    def on_open_log(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        os.startfile(APP_DIR)

    def on_toggle_autostart(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        set_autostart(not is_autostart_enabled())

    def make_speed_item(speed_choice: float) -> pystray.MenuItem:
        def on_select(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
            engine.speed = speed_choice
            save_setting("speed", speed_choice)
            print(f"[Speed] {speed_choice}")

        return pystray.MenuItem(
            format_speed_label(speed_choice),
            on_select,
            checked=lambda _item: engine.speed == speed_choice,
            radio=True,
        )

    def make_hotkey_item(hotkey_choice: str) -> pystray.MenuItem:
        def on_select(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
            if hotkey_choice == active_hotkey["name"]:
                return
            player.stop()
            active_hotkey["listener"].stop()
            active_hotkey["listener"] = start_hotkey_listener(hotkey_choice, on_toggle)
            active_hotkey["name"] = hotkey_choice
            save_setting("hotkey", hotkey_choice)
            print(f"[Hotkey] {hotkey_choice}")

        return pystray.MenuItem(
            hotkey_choice,
            on_select,
            checked=lambda _item: active_hotkey["name"] == hotkey_choice,
            radio=True,
        )

    speed_menu = pystray.Menu(*(make_speed_item(choice) for choice in SPEED_CHOICES))
    hotkey_menu = pystray.Menu(*(make_hotkey_item(choice) for choice in HOTKEY_CHOICES))

    menu = pystray.Menu(
        pystray.MenuItem("TalkTalk", None, enabled=False),
        pystray.MenuItem("Hotkey", hotkey_menu),
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

