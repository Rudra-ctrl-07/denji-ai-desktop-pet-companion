# DenjiPet 🐾

[![CI](https://github.com/Rudra-ctrl-07/denji-ai-desktop-pet-companion/actions/workflows/ci.yml/badge.svg)](https://github.com/Rudra-ctrl-07/denji-ai-desktop-pet-companion/actions/workflows/ci.yml)

A Windows desktop pet app built with Python + PySide6, inspired by Shimeji and Comnyang.
The pet lives on your desktop, runs a Pomodoro focus timer, swaps animations based on
session state, and fires health nudge reminders while you work.

The pet ships as the **classic Batman emblem** — a yellow-oval logo rendered from the
bundled vector artwork (`assets/custom/batman_logo.svg`). To use your own pet instead,
just drop any square PNG over `assets/custom/pet.png` and it replaces the sprite for
every state — no code changes, then rebuild the exe.

---

## Features

| Feature | Status |
|---|---|
| Transparent, always-on-top pet window | ✅ MVP |
| Left-click-drag to move the pet | ✅ MVP |
| Custom pet sprite (single image, all states) | ✅ MVP |
| Pomodoro timer (25/5/15 min) | ✅ MVP |
| Sprite swaps on Pomodoro state change | ✅ MVP |
| System tray icon + context menu | ✅ MVP |
| Health nudge speech-bubble popups | ✅ MVP |
| Click pet → random idle reaction | ✅ MVP |
| Settings dialog (all durations configurable) | ✅ MVP |
| Persistent config at `%APPDATA%/DenjiPet/` | ✅ MVP |
| OS native notifications on state change | ✅ MVP |
| Graceful fallback when sprites are missing | ✅ MVP |
| Single-instance guard | ✅ MVP |
| Off-screen window recovery | ✅ MVP |

---

## Running from Source

### Prerequisites
- Python 3.11 or later
- Install dependencies:

```bash
pip install -r requirements.txt
```

### Start the app

```bash
python main.py
```

The pet appears in the bottom-right corner. A tray icon appears in the system tray.

---

## Adding Your Own Pet Sprite

The pet uses a **single custom sprite**: drop any PNG at `assets/custom/pet.png`
(128×128 recommended, transparent background) and it replaces the sprite for every
state and emotion — no frame cycling, no code changes. If the file is missing, the
app shows a built-in placeholder instead of crashing.

```
assets/
└── custom/
    ├── pet.png            # Your pet sprite (just overwrite this file)
    └── batman_logo.svg    # Bundled artwork — re-render with gen_custom_sprite.py
```

Re-run `pyinstaller DenjiPet.spec` to ship a new sprite in the packaged exe.

> ✨ **Position & fullscreen:** the pet stays exactly where you drag it (position is
> saved on quit and restored on launch, clamped on-screen), and it automatically
> hides while you're in a fullscreen app so it never floats over fullscreen
> content or the taskbar.

> ⚠️ **IP Note:** The bundled Batman emblem and any sprite you add (e.g. a copyrighted logo)
> are for **personal use only** — don't redistribute them commercially (SEC-03).

---

## Configuration

Settings are stored at `%APPDATA%\DenjiPet\config.json` (Windows) and are
human-readable/editable. You can also change them via the Settings dialog
(tray right-click → Settings…).

| Key | Default | Description |
|---|---|---|
| `work_duration_min` | 25 | Pomodoro work session length |
| `break_duration_min` | 5 | Short break length |
| `long_break_duration_min` | 15 | Long break (every 4th session) |
| `nudge_interval_min` | 20 | Health reminder frequency |
| `window_x` / `window_y` | null | Last saved pet position |
| `log_level` | `"INFO"` | Set to `"DEBUG"` for verbose output |

---

## Packaging to .exe

```bash
pyinstaller DenjiPet.spec
```

Output: `dist/DenjiPet.exe` — a self-contained executable that runs without Python
being installed (NFR-07).

---

## Project Structure

```
DenjiPet/
├── main.py               # Entry point — wires all components
├── pet_window.py         # Transparent pet widget + drag + reactions
├── animation_controller.py  # Frame-cycling sprite loader
├── pomodoro_engine.py    # Pomodoro state machine
├── nudge_manager.py      # Health reminder popups
├── tray_menu.py          # System tray icon + menu
├── settings.py           # JSON config load/save (declarative SPEC)
├── settings_dialog.py    # Settings UI dialog
├── periodic_reminder.py  # Shared base for hydration/stretch reminders
├── theme.py              # Shared menu stylesheets
├── DenjiPet.spec         # PyInstaller build spec
├── requirements.txt      # Python dependencies
└── assets/
    └── custom/
        ├── pet.png            # The pet sprite (custom image drops in here)
        └── batman_logo.svg    # Source artwork (rendered by gen_custom_sprite.py)
```

---

## Dependencies

| Package | License | Purpose |
|---|---|---|
| PySide6 | LGPL | GUI, tray, timers, windowing |
| plyer | BSD | Native OS notifications (fallback) |
| pyinstaller | GPL + runtime exception | Packaging to .exe |

See `THIRD_PARTY_LICENSES.txt` (to be added before any public distribution, LIC-03).
