$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

& $python -m pip install -r requirements.txt pyinstaller pystray pillow

& $python -c "from talktalk_tray import build_icon_image; build_icon_image().save('talktalk.ico', sizes=[(16,16),(32,32),(48,48),(64,64)])"

& $python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name TalkTalk `
    --icon talktalk.ico `
    --collect-all kokoro_onnx `
    --collect-all espeakng_loader `
    --collect-all onnxruntime `
    --collect-binaries sounddevice `
    --exclude-module babelvox `
    --exclude-module openvino `
    talktalk_tray.py

Write-Host "Built: dist\TalkTalk\TalkTalk.exe"

