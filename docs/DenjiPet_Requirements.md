# DenjiPet — Requirements Specification
### v0.1 | Covers MVP (v1) and Future Scope

---

## 1. Functional Requirements

### 1.1 MVP (v1) — Now
| ID | Requirement |
|---|---|
| FR-01 | System shall display a transparent, frameless, always-on-top window showing the pet sprite |
| FR-02 | User shall be able to drag the pet window anywhere on screen |
| FR-03 | System shall cycle through idle animation frames continuously (default 6 fps) |
| FR-04 | System shall run a Pomodoro state machine: IDLE → WORKING → BREAK → repeat, with LONG_BREAK every 4th cycle |
| FR-05 | System shall swap the active sprite set based on Pomodoro state (idle/working/break/tired) |
| FR-06 | System shall show a system tray icon with menu: Start/Pause, Reset, Settings, Quit |
| FR-07 | System shall fire periodic health nudges (hydrate, stretch, eye-rest) as speech-bubble popups |
| FR-08 | System shall auto-dismiss nudge popups after ~5 seconds |
| FR-09 | System shall persist settings (work/break duration, nudge interval, sprite path) to a local JSON file |
| FR-10 | System shall load persisted settings on startup, falling back to defaults if none exist |
| FR-11 | System shall fire a native OS notification on every Pomodoro state transition |
| FR-12 | User shall be able to click the pet to trigger a random idle reaction (text bubble) |
| FR-13 | System shall gracefully fall back to a placeholder shape if sprite assets are missing |

### 1.2 Future / Stretch
| ID | Requirement |
|---|---|
| FR-14 | System shall track daily focus stats (sessions completed, current streak) |
| FR-15 | System shall visually evolve the pet's "form" based on consistency/streak |
| FR-16 | System shall support optional sound effects (togglable), e.g. chainsaw-pull SFX on session start |
| FR-17 | System shall support right-click cosmetic interactions (pet/feed animations) |
| FR-18 | System shall support auto-start on OS boot |
| FR-19 | System shall support minimize-to-tray instead of quitting |
| FR-20 | System shall support multiple selectable sprite skins/themes, swappable in Settings |
| FR-21 | System shall support exporting focus stats (CSV) for personal tracking |
| FR-22 | System shall support a "focus mode" that hides the pet and only shows a minimal timer overlay |

---

## 2. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-01 | Performance | Idle animation loop shall not exceed ~2% CPU usage on a typical laptop |
| NFR-02 | Performance | App startup time shall be under 3 seconds |
| NFR-03 | Usability | Settings shall be reachable within 2 clicks from the tray icon |
| NFR-04 | Usability | Dragging the pet shall feel smooth with no visible lag (<50ms input latency) |
| NFR-05 | Reliability | A crash or forced quit shall not corrupt the saved config file |
| NFR-06 | Reliability | Missing/corrupt config shall regenerate defaults rather than crash the app |
| NFR-07 | Portability | App shall run on Windows 10/11 (64-bit) without requiring a separate Python install for end users (via PyInstaller bundle) |
| NFR-08 | Maintainability | Codebase shall follow the single-responsibility folder structure (see architecture doc) |
| NFR-09 | Footprint | Packaged `.exe` shall stay under ~150MB where reasonably achievable |
| NFR-10 | Privacy | App shall make zero network calls in v1 (fully offline, no telemetry) |

---

## 3. System / Technical Requirements

| Category | Requirement |
|---|---|
| OS | Windows 10 or later (64-bit) for v1; cross-platform (macOS/Linux) is future scope |
| Runtime | Python 3.11+ (bundled via PyInstaller for end users — not required to be pre-installed) |
| Disk space | ~150–200MB installed |
| Permissions | No admin rights required to install or run |
| Display | Supports standard DPI scaling (100%–200%) without sprite distortion |

---

## 4. Hardware Requirements

| Component | Minimum |
|---|---|
| RAM | 4GB (app itself uses <100MB) |
| CPU | Any modern dual-core, no special requirement |
| GPU | None required — no 3D rendering |
| Storage | 200MB free space |

---

## 5. Software / Dependency Requirements

See `requirements.txt`. Current:
- `PySide6` — GUI, windowing, tray, timers
- `plyer` — native OS notifications
- `pyinstaller` — packaging

Future (if scope expands):
- `pygame` or `moviepy` — if animations move beyond simple PNG frame-cycling
- `matplotlib` or `plotly` — if focus-stats visualization (FR-14/FR-21) is added
- `requests` — only if any future cloud-sync feature is added (currently out of scope, conflicts with NFR-10 unless explicitly opted in)

---

## 6. User Requirements (plain-language, from user perspective)

- "I want a visible reminder to take breaks without having to check an app."
- "I want the pet to feel alive and reactive, not like a static sticker."
- "I want my settings to persist — I shouldn't have to reconfigure every time I open it."
- "I want it lightweight — it shouldn't slow my laptop down while I work."
- "I want to be able to move it out of the way when it's blocking something."
- *(Future)* "I want to see how consistent I've been with focus sessions over time."

---

## 7. Interface Requirements

| Interface | Requirement |
|---|---|
| System tray | Right-click context menu; left-click toggles pause/resume |
| Notifications | Native OS notification API (Windows toast via `plyer`/Qt) |
| Config file | Local JSON at `%APPDATA%/DenjiPet/config.json`, human-readable/editable |
| Sprite loading | Reads PNG sequences from `assets/<state>/` folders; naming convention `frame_0.png`, `frame_1.png`, etc. |
| *(Future)* Skin packs | Folder-based skin format so new sprite sets can be dropped in without code changes |

---

## 8. Data Requirements

| Data | Storage | Notes |
|---|---|---|
| User settings | Local JSON | Work/break durations, nudge interval, sprite path |
| Focus stats *(future)* | Local JSON or SQLite | Session count, streaks, timestamps |
| Sprite assets | Local filesystem (`assets/`) | User-supplied, not bundled/redistributed |
| No user PII collected | — | App has no accounts, no cloud sync in v1 |

---

## 9. Security & Constraint Requirements

| ID | Requirement |
|---|---|
| SEC-01 | App shall make no outbound network requests in v1 |
| SEC-02 | App shall not collect or transmit any personal data |
| SEC-03 | Sprite assets based on copyrighted characters shall remain for personal use only, not redistributed with the packaged app or shared publicly |
| SEC-04 | Config file shall not store any sensitive data (no credentials, no PII) |
| SEC-05 *(future)* | If cloud sync is ever added, it must be opt-in and clearly disclosed, not default-on |

---

## 10. Future Considerations (parking lot — not committed, just tracked)

- Cross-platform support (macOS `.app`, Linux `.AppImage`)
- Multiple pets/companions running simultaneously
- Community skin-sharing format (would require clear licensing/IP guidelines for shared skins)
- Voice lines (audio) instead of text-only reactions
- Deeper "care" mechanics (hunger/energy meters affecting animation mood)
- Auto-updater for the packaged `.exe`
- Localization (multi-language nudge text)

---

## 11. Traceability Note

This document should be revisited after each milestone in the project doc
(`DenjiPet_ProjectDoc.md`) — mark requirements as Done/In Progress/Deferred
as the build progresses, rather than treating this as fixed scope.
