# Read4me

Desktop reader (Mac + Windows) that reads textbooks and PDFs aloud for researchers.

1. **Navigate by voice/text** — "read chapter 3", "pages 42 to 50", "read the methods".
2. **Skips side-notes** — footnotes, running headers, captions, bibliography and inline citations.
3. **Natural voice** — pluggable TTS: local neural (Kokoro) by default, optional cloud voices.

## Install (macOS, Apple Silicon)
Open `release/Read4me-0.1.0-arm64.dmg` and drag Read4me to Applications. The app is unsigned: first launch via right-click → Open.

## Status
- [x] Python pipeline: extract -> classify -> structure -> command parser -> reading units (`sidecar/r4m`)
- [x] stdio JSON sidecar (`sidecar/server.py`)
- [x] Electron + React app: chapter/page pickers, player, notes, themes, PDF + EPUB
- [x] Kokoro neural voice + macOS system voices
- [x] macOS packaging (`npm run sidecar && npm run dist`)
- [ ] OCR for scanned PDFs, Windows build, PDF page viewer

## Dev
```
python3 -m venv sidecar/.venv && sidecar/.venv/bin/pip install -r sidecar/requirements.txt
sidecar/.venv/bin/python -m pytest tests
```

## Build
```
npm run sidecar   # bundle Python backend (PyInstaller)
npm run dist      # package the .dmg into release/
```
Kokoro model files (`kokoro-v1.0.onnx`, `voices-v1.0.bin`) go in `sidecar/models/` (not in git).

## Licence
Copyright (c) 2026 Ziwei Luo. All rights reserved. See [LICENSE](LICENSE).
