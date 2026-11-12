"""Global-hotkey clipboard TTS reader."""

from __future__ import annotations

import argparse
import threading
import time

import pyperclip
from pynput import keyboard

from audio_player import StreamingTTSPlayer
from tts_engines import create_tts_engine


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="talktalk",
        description="TalkTalk: read highlighted text or clipboard aloud on a global hotkey and stop on toggle.",
    )
    parser.add_argument(
        "--engine",
        choices=["kokoro", "babelvox"],
        default="kokoro",
        help="TTS engine to use (default: kokoro).",
    )
    parser.add_argument(
        "--voice",
        default="af_heart",
        help="Kokoro voice name (default: af_heart).",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.4,
        help="Kokoro speech speed multiplier (default: 1.4).",
    )
    parser.add_argument(
        "--lang",
        default="en-us",
        help="Kokoro language code (default: en-us).",
    )
    parser.add_argument(
        "--device",
        default="CPU",
        choices=["CPU", "NPU"],
        help="BabelVox OpenVINO device (default: CPU).",
    )
    parser.add_argument(
        "--language",
        default="English",
        help="BabelVox language name (default: English).",
    )
    parser.add_argument(
        "--ref-audio",
        default=None,
        help="Optional 3-10s reference WAV path for BabelVox voice cloning.",
    )
    parser.add_argument(
        "--ref-text",
        default=None,
        help="Optional transcript of --ref-audio for BabelVox voice cloning.",
    )
    parser.add_argument(
        "--read-hotkey",
        default="<ctrl>+<shift>+<space>",
        help="Global hotkey to read clipboard (default: <ctrl>+<shift>+<space>).",
    )
    parser.add_argument(
        "--stop-hotkey",
        default="<ctrl>+<shift>+<space>",
        help="Global hotkey to stop reading (default: <ctrl>+<shift>+<space>, toggles when same as --read-hotkey).",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Do not simulate Ctrl+C before reading the clipboard.",
    )
    return parser


def copy_selection_to_clipboard(controller: keyboard.Controller) -> str:
    """Release held hotkey modifiers, send Ctrl+C, and return clipboard text."""
    try:
        previous_text = pyperclip.paste()
    except Exception:
        previous_text = ""

    for key in (
        keyboard.Key.shift,
        keyboard.Key.shift_l,
        keyboard.Key.shift_r,
        keyboard.Key.alt,
        keyboard.Key.alt_l,
        keyboard.Key.alt_r,
        keyboard.Key.ctrl,
        keyboard.Key.ctrl_l,
        keyboard.Key.ctrl_r,
        keyboard.Key.space,
    ):
        try:
            controller.release(key)
        except Exception:
            pass

    time.sleep(0.06)
    with controller.pressed(keyboard.Key.ctrl_l):
        controller.tap("c")

    # Poll briefly so fast apps update clipboard immediately, slow apps still get 150ms
    for _ in range(6):
        time.sleep(0.025)
        try:
            current_text = pyperclip.paste()
        except Exception:
            continue
        if current_text and current_text != previous_text:
            return current_text

    return pyperclip.paste()


def main() -> None:
    args = build_arg_parser().parse_args()

    print(f"Loading TTS engine '{args.engine}'...")
    t0 = time.perf_counter()
    engine = create_tts_engine(
        args.engine,
        voice=args.voice,
        speed=args.speed,
        lang=args.lang,
        device=args.device,
        language=args.language,
        ref_audio=args.ref_audio,
        ref_text=args.ref_text,
    )
    print(f"Engine ready in {time.perf_counter() - t0:.2f}s.")

    player = StreamingTTSPlayer(engine)
    key_controller = keyboard.Controller()

    def read_clipboard_worker() -> None:
        try:
            if args.no_copy:
                text = pyperclip.paste()
            else:
                text = copy_selection_to_clipboard(key_controller)
        except Exception as exc:
            print(f"[Clipboard] Failed to read clipboard: {exc}")
            return
        preview = text.strip().replace("\n", " ")[:80]
        print(f"[Hotkey] Read clipboard ({len(text)} chars): {preview!r}")
        player.speak(text)

    def on_read_clipboard() -> None:
        threading.Thread(target=read_clipboard_worker, daemon=True).start()

    def on_stop_reading() -> None:
        print("[Hotkey] Stop reading.")
        player.stop()

    def on_toggle_reading() -> None:
        if player.is_playing:
            on_stop_reading()
        else:
            on_read_clipboard()

    if args.read_hotkey == args.stop_hotkey:
        hotkey_map = {args.read_hotkey: on_toggle_reading}
        print("Active hotkey:")
        print(f"  Start/Stop toggle : {args.read_hotkey}")
    else:
        hotkey_map = {
            args.read_hotkey: on_read_clipboard,
            args.stop_hotkey: on_stop_reading,
        }
        print("Active hotkeys:")
        print(f"  Read clipboard : {args.read_hotkey}")
        print(f"  Stop reading   : {args.stop_hotkey}")
    print("Press Ctrl+C in this terminal to quit.")

    listener = keyboard.GlobalHotKeys(hotkey_map)
    listener.start()
    try:
        while listener.is_alive():
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        player.stop()
        listener.stop()


if __name__ == "__main__":
    main()

