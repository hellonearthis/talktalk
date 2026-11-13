"""TalkTalk tray entry point: windowless exe-friendly launcher (the script version stays in app.py)."""

from __future__ import annotations

import os
import sys
import threading
import time

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
HOTKEY = "<ctrl>+<shift>+<space>"
DEFAULT_SPEED = 1.3


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


def main() -> None:
    redirect_output_to_log()
    print(f"\n--- TalkTalk started {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    engine = KokoroTTSEngine(speed=DEFAULT_SPEED, model_dir=MODEL_DIR)
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

    menu = pystray.Menu(
        pystray.MenuItem(f"TalkTalk ({HOTKEY})", None, enabled=False),
        pystray.MenuItem("Open log folder", on_open_log),
        pystray.MenuItem("Quit", on_quit),
    )
    pystray.Icon("TalkTalk", build_icon_image(), "TalkTalk", menu).run()


if __name__ == "__main__":
    main()

