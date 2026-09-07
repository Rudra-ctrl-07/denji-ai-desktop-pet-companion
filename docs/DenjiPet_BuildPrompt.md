# Build Prompt — paste this into Claude Code

I want to build "DenjiPet," a Python desktop pet app (Windows-first), inspired
by apps like Comnyang and classic Shimeji-style desktop companions. Skin/theme
is Chainsaw Man's Denji, but treat all character art as a pluggable asset
folder — don't generate or hardcode any character artwork yourself, just wire
up the loading logic so I can drop in my own sprite PNGs later.

## Stack
- Python 3.11+
- PySide6 for the GUI
- PyInstaller for packaging (later step, not now)

## Build this incrementally, confirming each step runs before moving to the next:

### Step 1 — Base window
Create a frameless, transparent, always-on-top PySide6 QWidget that:
- Has no taskbar icon
- Displays a single placeholder image (use a simple colored circle or
  fallback icon if no sprite asset exists yet at `assets/idle/frame_0.png`)
- Is draggable anywhere on screen via left-click-drag
- Right-click opens a context menu with "Quit"

### Step 2 — Sprite animation loop
- Build `animation_controller.py`: loads all PNGs from a given folder
  (e.g. `assets/idle/`), cycles frames on a QTimer at a configurable FPS
  (default 6 fps), loops indefinitely
- Wire it into the base window so the idle animation plays automatically

### Step 3 — State machine + Pomodoro engine
- Build `pomodoro_engine.py` as a simple state machine: IDLE → WORKING →
  BREAK → (repeat), with a LONG_BREAK every 4th cycle
- Default durations: 25 min work, 5 min break, 15 min long break
  (all configurable via constructor args)
- Emit a Qt signal on every state transition
- Connect that signal to `animation_controller` so it swaps the active
  sprite folder based on state (idle/working/break/tired mapped from state)

### Step 4 — System tray
- Build `tray_menu.py` using QSystemTrayIcon
- Menu items: Start/Pause Pomodoro, Reset, Settings (placeholder), Quit
- Tray icon click toggles pause/resume of the Pomodoro engine

### Step 5 — Health nudges
- Build `nudge_manager.py`: a separate QTimer firing every N minutes
  (default 20), picks a random reminder from a hardcoded list
  ("Drink water", "Stretch your back", "Blink and look away from the screen")
- Displays it as a small speech-bubble-style popup anchored near the pet
  window, auto-dismisses after ~5 seconds

### Step 6 — Settings persistence
- Build `settings.py`: loads/saves a JSON config at
  `%APPDATA%/DenjiPet/config.json` on Windows (fallback to local dir on
  other OS for dev testing)
- Persist: work/break durations, nudge interval, sprite folder path
- Load these on startup instead of hardcoded defaults

### Step 7 — Packaging (only after everything above works)
- Write a PyInstaller spec/command to bundle this into a single `.exe`
- Make sure the `assets/` folder is included as a data directory

## Constraints
- No character artwork generation — sprite folders may be empty/placeholder
  during dev; code should handle missing assets gracefully (fallback shape)
- Comment the code reasonably since I'm a data science undergrad newer to
  desktop/GUI Python, not a beginner to Python itself
- Keep each file focused/single-responsibility per the folder structure below

## Folder structure to follow
```
DenjiPet/
├── main.py
├── pet_window.py
├── animation_controller.py
├── pomodoro_engine.py
├── nudge_manager.py
├── tray_menu.py
├── settings.py
├── assets/
│   ├── idle/
│   ├── working/
│   ├── break/
│   ├── tired/
│   └── celebrate/
└── requirements.txt
```

Start with Step 1 and show me the running window before moving on.
