# XLSplit — Excel & CSV File Splitter (Litestar edition)

A desktop Windows app built with **Litestar** (ASGI), **Jinja2**, **Tailwind CSS**, and **Alpine.js**.

## Stack

| Layer    | Tech                              |
|----------|-----------------------------------|
| Backend  | Litestar 2.x + Uvicorn (ASGI)    |
| Template | Jinja2                            |
| Frontend | Tailwind CSS + Alpine.js (CDN)    |
| Data     | pandas + openpyxl + xlrd          |
| Build    | PyInstaller → `XLSplit.exe`       |

## Features

- Drag & drop `.xlsx`, `.xls`, or `.csv` upload
- Live 5-row preview table
- Configurable rows per file (min 100) with ± steppers
- Estimated file count updates in real time
- CSV or XLSX output toggle
- Download individual files or all at once as a `.zip`
- Light / dark mode (saved to localStorage)
- Responsive sidebar layout

---

## Run locally (Linux/Mac/Windows)

```bash
pip install -r requirements.txt
python app.py
# Opens http://127.0.0.1:8000 automatically
```

---

## Build Windows .exe

### Option A — On a Windows machine

```cmd
pip install -r requirements.txt
pyinstaller xlsplit.spec
# → dist/XLSplit.exe
```

### Option B — GitHub Actions (no Windows needed)

Push to GitHub; `.github/workflows/build.yml` builds and uploads `XLSplit.exe` as an artifact.

### Option C — Wine on Linux

```bash
winetricks python311
wine python -m pip install -r requirements.txt
wine python -m PyInstaller xlsplit.spec
```

---

## Notes

- `console=False` in the spec suppresses the black terminal window on Windows.
- All processing is local; no data leaves your machine.
- The `.exe` is fully self-contained — no Python required on the target PC.
