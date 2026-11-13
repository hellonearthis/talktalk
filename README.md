# TalkTalk

A lightweight, CPU-only Windows text-to-speech reader that speaks highlighted text or clipboard contents on a global hotkey and stops immediately when toggled again.

Uses **Kokoro ONNX** on CPU (leaving your GPU free for other workloads) and streams audio directly in memory without writing temporary audio files to disk.

---

## Features

- **Global toggle hotkey (`Ctrl+Shift+Space`):**
  - **When idle:** Automatically sends `Ctrl+C` to copy your highlighted selection (or falls back to existing clipboard text) and starts reading within ~200ms.
  - **When reading:** Immediately aborts playback and stops synthesis.
- **Zero GPU usage:** Runs on CPU via `onnxruntime`.
- **No leftover audio files:** Audio is streamed in memory through `sounddevice`.
- **Configurable defaults:** `1.3x` speech speed, `af_heart` voice, customizable hotkeys.

---

## Setup & Install

1. **Create and activate a virtual environment** (Python 3.12 recommended):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Models:**
   On first run, `kokoro-v1.0.onnx` and `voices-v1.0.bin` are automatically downloaded into `./models/kokoro/`.

---

## Running

Start TalkTalk with the PowerShell launcher:

```powershell
.\start_talktalk.ps1
```

Or run Python directly:

```powershell
.\.venv\Scripts\python.exe app.py
```

Press `Ctrl+C` in the terminal window to exit.

---

## Windows exe (optional)

The script version above keeps working as-is. To also build a windowless tray app:

```powershell
.\build_exe.ps1
```

This produces `dist\TalkTalk\TalkTalk.exe` (a folder build; keep the whole `TalkTalk` folder together) and, if [Inno Setup](https://jrsoftware.org/isinfo.php) is installed (`winget install JRSoftware.InnoSetup`), an installer at `installer\TalkTalk-Setup.exe` (per-user install, no admin needed, optional "Start with Windows" and desktop shortcut).

The tray app runs `Ctrl+Shift+Space` at `1.3x`. Right-click the tray icon for **Speed** (1x, 1.1x, 1.2x, 1.3x, 1.4x, 1.5x, 2x; remembered between launches, applies from the next sentence), **Start with Windows** (toggle), **Open log folder** and **Quit**. Models are stored in `%LOCALAPPDATA%\TalkTalk\models\kokoro` (downloaded on first launch), and the log is `%LOCALAPPDATA%\TalkTalk\talktalk.log`.

The pre-exe script version is also tagged `script-v1`.

---

## Options

You can pass any CLI flag through `start_talktalk.ps1`:

```powershell
# Change speech speed or voice
.\start_talktalk.ps1 --speed 1.15 --voice af_heart

# Use separate read and stop hotkeys
.\start_talktalk.ps1 --read-hotkey "<ctrl>+<alt>+r" --stop-hotkey "<ctrl>+<alt>+s"

# Read existing clipboard without simulating Ctrl+C first
.\start_talktalk.ps1 --no-copy
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--speed` | `1.3` | Speech speed multiplier |
| `--voice` | `af_heart` | Kokoro voice name |
| `--lang` | `en-us` | Kokoro language code |
| `--read-hotkey` | `<ctrl>+<shift>+<space>` | Global hotkey to start reading |
| `--stop-hotkey` | `<ctrl>+<shift>+<space>` | Global hotkey to stop reading (toggles when same as `--read-hotkey`) |
| `--no-copy` | `False` | Skip simulating `Ctrl+C` before reading clipboard |

---

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest test_text_chunker.py -v
```

