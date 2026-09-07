"""
main.py — DenjiPet application entry point.

Full Comnyang feature parity. Wires every subsystem:

  Settings
    ├─► PomodoroEngine ──state_changed──► AnimationController ──frame_changed──► PetWindow
    │                                ──tick────────────► PomodoroHUD
    ├─► InputListener   ──mouse_moved────► PetWindow (Eye Follow)
    │                  ──typing_event───► PetWindow (Keyboard Kneading)
    │                  ──overheat───────► PetWindow (Overheat Mode)
    │                  ──scroll─────────► AnimationController
    ├─► PetAI          ──autonomous_idle─► PetWindow (random reactions, wandering)
    ├─► NudgeManager   ──periodic────────► NudgeBubble
    ├─► HydrationReminder (1hr) ──► AnimationController (HYDRATE)
    ├─► StretchReminder (45min) ─► AnimationController (STRETCH)
    ├─► AgentHook (Claude Code / Cursor) ──► AnimationController (reactions)
    ├─► ClickDetector  ──single/double/long/rapid──► PetWindow
    ├─► StickyNotesManager ──floating widgets above pet
    ├─► PomodoroHUD ──floating MM:SS above pet
    ├─► SoundPack (optional) ──system beeps on actions
    └─► NameSpeech ──personalise reminders
"""

import sys
import os
import logging
import logging.handlers
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

from settings             import Settings
from animation_controller import AnimationController
from pomodoro_engine      import PomodoroEngine
from pet_window           import PetWindow
from tray_menu            import TrayMenu
from nudge_manager        import NudgeManager
from settings_dialog      import SettingsDialog
from input_listener       import InputListener
from pet_ai               import PetAI
from hydration_reminder   import HydrationReminder
from stretch_reminder     import StretchReminder
from agent_hook           import AgentHook
from pomodoro_hud         import PomodoroHUD
from sticky_notes         import StickyNotesManager
from sound_pack           import SoundPack
from click_detector       import ClickDetector
from name_speech          import NameSpeech
from intelligence         import Intelligence


def _setup_logging(level_name: str = "INFO") -> None:
    log_dir = Path(os.environ.get("APPDATA", ".")) / "DenjiPet"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "log.txt"

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    level = getattr(logging, level_name.upper(), logging.INFO)
    fmt   = "%(asctime)s [%(levelname)-8s] %(name)s - %(message)s"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1_000_000,
            backupCount=1,
            encoding="utf-8",
        ),
    ]
    logging.basicConfig(level=level, format=fmt, handlers=handlers)



def _acquire_lock() -> bool:
    """
    Single-instance guard. Uses an msvcrt file lock on Windows; on other
    platforms falls back to exclusive file creation so the app stays portable.
    """
    lock_path = Path(os.environ.get("APPDATA", ".")) / "DenjiPet" / "running.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import msvcrt  # Windows-only
    except ImportError:
        try:
            _acquire_lock._fh = open(lock_path, "x")
            return True
        except FileExistsError:
            return False
    try:
        _acquire_lock._fh = open(lock_path, "w")
        msvcrt.locking(_acquire_lock._fh.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except (OSError, IOError):
        return False


@dataclass
class AppContext:
    """Every subsystem wired together by _build_app, accessed by name."""

    pet: PetWindow
    tray: TrayMenu
    engine: PomodoroEngine
    anim: AnimationController
    nudge: NudgeManager
    input_listener: InputListener
    pet_ai: PetAI
    hydration: HydrationReminder
    stretch_reminder: StretchReminder
    agent_hook: AgentHook
    hud: PomodoroHUD
    sticky_notes: StickyNotesManager
    sound: SoundPack
    click_detector: ClickDetector
    brain: Intelligence


def _foreground_is_fullscreen() -> bool:
    """
    True when the active (foreground) window covers the entire primary screen
    — i.e. the user is in a fullscreen app (video, game, presentation).
    Windows-only, via the Win32 API.
    """
    try:
        import ctypes

        user32 = ctypes.windll.user32

        class _RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        rect = _RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        screen = QApplication.primaryScreen().geometry()
        return (
            rect.left <= screen.left() and rect.top <= screen.top()
            and rect.right >= screen.right() and rect.bottom >= screen.bottom()
        )
    except Exception:
        return False


def _build_app(settings: Settings) -> AppContext:
    log = logging.getLogger("main.build")

    # ---- Pet window & Animation controller
    anim = AnimationController(fps=6)
    pet = PetWindow()
    pet.set_pet_size(settings.pet_size)
    # Honour the always-on-top setting from launch (not just after opening Settings)
    if not settings.always_on_top:
        pet.setWindowFlags(pet.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
    anim.frame_changed.connect(pet.set_frame)
    anim.set_state("IDLE")


    # ---- Sound pack (Windows-only, off by default)
    sound = SoundPack(settings)

    # ---- Name speaker
    speaker = NameSpeech(settings)

    # ---- Click detector (distinguishes single/double/long/rapid pet)
    click_detector = ClickDetector()
    pet.attach_click_detector(click_detector)

    # ---- Global Input Listener (Comnyang features)
    input_listener = InputListener()
    input_listener.mouse_moved.connect(pet.update_cursor_pos)
    input_listener.typing_event.connect(pet.trigger_typing_punch)
    input_listener.overheat_triggered.connect(lambda b: (pet.set_overheat(b),
                                                        sound.play("overheat") if b else None))

    # ---- Scroll reaction (paper unroll)
    input_listener.scroll_event.connect(
        lambda _delta: anim.set_emotion("SCROLL_PAPER", duration_ms=1_200)
    )

    # ---- Pet AI (autonomous behaviors)
    pet_ai = PetAI(pet_window=pet)
    pet_ai.wants_reaction.connect(pet.trigger_reaction)
    pet_ai.wants_move_to.connect(pet.drift_to)
    pet_ai.wants_emotion.connect(lambda emo: anim.set_emotion(emo, duration_ms=4000))

    # ---- Hydration reminder
    hydration = HydrationReminder(
        pet_window=pet,
        interval_min=settings.water_interval_min,
        personalize=speaker.personalize,
    )
    hydration.wants_hydrate.connect(lambda: anim.set_emotion("HYDRATE", duration_ms=6000))
    pet.clicked.connect(lambda: hydration.snooze(30))
    pet.double_clicked.connect(lambda: hydration.snooze(15))
    pet.rapid_pet.connect(lambda _n: hydration.snooze(20))

    # ---- Stretch reminder (Comnyang feature)
    stretch_reminder = StretchReminder(
        pet_window=pet,
        interval_min=settings.stretch_interval_min,
        personalize=speaker.personalize,
    )
    stretch_reminder.wants_stretch.connect(lambda: (
        anim.set_emotion("STRETCH", duration_ms=3_500),
        pet.start_stretch_grow(duration_ms=3_500),
        sound.play("stretch"),
    ))
    pet.clicked.connect(lambda: stretch_reminder.snooze(30))

    # ---- AI agent hook (Claude Code / Cursor reactions)
    agent_hook = AgentHook(settings)
    agent_hook.reaction.connect(lambda emo: anim.set_emotion(emo, duration_ms=4_000))
    # Comnyang-style: the pet jumps when an agent finishes
    agent_hook.reaction.connect(lambda emo: pet.jump() if emo == "CELEBRATE" else None)

    # ---- Pomodoro engine
    engine = PomodoroEngine(
        work_min       = settings.work_duration_min,
        break_min      = settings.break_duration_min,
        long_break_min = settings.long_break_duration_min,
    )
    engine.state_changed.connect(anim.set_state)

    # ---- Pomodoro HUD (floating pixel timer)
    hud = PomodoroHUD(pet_window=pet)
    hud.set_enabled(settings.pomodoro_hud)
    engine.tick.connect(hud.update_time)
    engine.state_changed.connect(
        lambda s: hud.update_state(s, engine.is_running)
    )
    engine.state_changed.connect(
        lambda s: sound.play("celebrate") if s == "CELEBRATE" else None
    )

    # ---- Sticky notes
    sticky_notes = StickyNotesManager(settings, pet_window=pet)

    # ---- Context-aware "brain" (Intelligence) — wires into every signal
    # Constructed AFTER all producers exist so we can bind them now.
    brain = Intelligence(
        settings=settings,
        pet_window=pet,
        name_speaker=speaker,
        pet_ai=pet_ai,
    )
    engine.state_changed.connect(brain.on_pomodoro_state)
    engine.session_completed.connect(brain.on_session_completed)
    input_listener.typing_event.connect(brain.on_typing_event)
    input_listener.overheat_triggered.connect(brain.on_overheat)
    input_listener.mouse_moved.connect(brain.on_mouse_activity)
    input_listener.scroll_event.connect(brain.on_scroll_activity)
    pet.clicked.connect(brain.on_click)
    pet.double_clicked.connect(brain.on_click)
    pet.rapid_pet.connect(brain.on_rapid_pet)
    pet.dragging_changed.connect(brain.set_being_dragged)
    pet.action_triggered.connect(brain.on_action)
    hydration.wants_hydrate.connect(brain.on_hydration)
    stretch_reminder.wants_stretch.connect(brain.on_stretch)
    agent_hook.reaction.connect(brain.on_agent_status)
    brain.wants_emotion.connect(lambda emo: anim.set_emotion(emo, duration_ms=4000))
    brain.wants_reaction.connect(pet.trigger_reaction)

    # ---- System tray
    tray = TrayMenu(settings=settings)

    # ---- Nudge manager
    nudge = NudgeManager(pet_window=pet, interval_min=settings.nudge_interval_min)

    # ---- Fullscreen guard: while a fullscreen app is active, hide the pet
    # (and the HUD) so it never floats over fullscreen content or the taskbar.
    fullscreen_timer = QTimer(pet)
    fullscreen_timer.setInterval(1_500)

    def _check_fullscreen() -> None:
        if _foreground_is_fullscreen():
            if pet.isVisible():
                pet.hide()
                hud.hide()
        elif not pet.isVisible():
            pet.show()
            pet.raise_()
            # Bring the timer HUD back if a Pomodoro is mid-run.
            if hud.is_enabled() and engine.state != "IDLE":
                hud.update_state(engine.state, engine.is_running)

    fullscreen_timer.timeout.connect(_check_fullscreen)

    # ------------------------------------------------------------------
    # Quit / Settings handlers
    # ------------------------------------------------------------------
    def _quit() -> None:
        log.info("Shutting down DenjiPet.")
        pos = pet.pos()
        settings.set_window_pos(pos.x(), pos.y())
        settings.save()

        input_listener.stop()
        pet_ai.stop()
        brain.stop()
        hydration.stop()
        stretch_reminder.stop()
        anim.stop()
        nudge.stop()
        agent_hook.stop()
        fullscreen_timer.stop()
        hud.hide()
        tray.hide()
        QApplication.quit()

    def _toggle_start_pause() -> None:
        if engine.is_running:
            engine.pause()
        else:
            engine.start()
        tray.update_state(engine.state, engine.is_running)

    def _reset() -> None:
        engine.reset()
        anim.set_state("IDLE")
        tray.update_state("IDLE", False)
        hud.update_state("IDLE", False)

    def _open_settings() -> None:
        dlg = SettingsDialog(settings)

        def _apply(data: dict) -> None:
            engine.update_durations(data["work"], data["break"], data["long_break"])
            nudge.set_interval_min(data["nudge"])
            hydration.set_interval_min(data["water"])
            stretch_reminder.set_interval_min(data["stretch"])
            hud.set_enabled(data["pomodoro_hud"])
            sound.set_enabled(data["sound_enabled"])
            agent_hook.set_enabled(data["agent_hooks"])
            # Always-on-top
            flags = pet.windowFlags()
            if data["always_on_top"]:
                flags = flags | Qt.WindowType.WindowStaysOnTopHint
            else:
                flags = flags & ~Qt.WindowType.WindowStaysOnTopHint
            pet.setWindowFlags(flags)
            pet.show()
            pet.set_pet_size(data["pet_size"])
            anim.refresh_frame()
            tray.refresh_from_settings()
            log.info("Live settings applied: %s", data)

        dlg.settings_applied.connect(_apply)
        dlg.exec()

    def _add_sticky() -> None:
        sticky_notes.add_note()

    def _toggle_sound() -> None:
        sound.set_enabled(not sound.enabled)
        tray.refresh_from_settings()
        if sound.enabled:
            sound.play("startup")

    def _toggle_hud() -> None:
        hud.set_enabled(not hud.is_enabled())
        settings.pomodoro_hud = hud.is_enabled()
        if hud.is_enabled():
            hud.update_state(engine.state, engine.is_running)
        tray.refresh_from_settings()

    def _change_size(px: int) -> None:
        settings.pet_size = px
        pet.set_pet_size(px)
        anim.refresh_frame()
        tray.refresh_from_settings()

    def _on_pet_action(action: str) -> None:
        pet.trigger_action(action)
        sound.play(action if action in ("pet", "rev") else "pet")

    # ------------------------------------------------------------------
    # Wire signals
    # ------------------------------------------------------------------
    tray.start_pause_requested.connect(_toggle_start_pause)
    tray.reset_requested.connect(_reset)
    tray.settings_requested.connect(_open_settings)
    tray.action_requested.connect(_on_pet_action)
    tray.new_sticky_requested.connect(_add_sticky)
    tray.toggle_sound_requested.connect(_toggle_sound)
    tray.toggle_hud_requested.connect(_toggle_hud)
    tray.change_size_requested.connect(_change_size)
    tray.quit_requested.connect(_quit)

    pet.toggle_pomodoro_requested.connect(_toggle_start_pause)
    pet.settings_requested.connect(_open_settings)
    pet.quit_requested.connect(_quit)
    pet.action_triggered.connect(sound.play)

    engine.state_changed.connect(
        lambda s: tray.update_state(s, engine.is_running)
    )

    _NOTIF: dict[str, tuple[str, str]] = {
        "WORKING":    ("🔥 Focus time!",   "Pomodoro session started — let's go!"),
        "BREAK":      ("☕ Break time!",    "Short break — you've earned it."),
        "LONG_BREAK": ("😴 Long break!",   "Great work — enjoy a longer rest."),
        "IDLE":       ("↺  Reset",         "Pomodoro has been reset."),
    }

    def _notify(state: str) -> None:
        if state in _NOTIF:
            title, msg = _NOTIF[state]
            tray.showMessage(title, msg)

    engine.state_changed.connect(_notify)

    return AppContext(
        pet=pet,
        tray=tray,
        engine=engine,
        anim=anim,
        nudge=nudge,
        input_listener=input_listener,
        pet_ai=pet_ai,
        hydration=hydration,
        stretch_reminder=stretch_reminder,
        agent_hook=agent_hook,
        hud=hud,
        sticky_notes=sticky_notes,
        sound=sound,
        click_detector=click_detector,
        brain=brain,
    )


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    settings = Settings()
    _setup_logging(settings.get("log_level", "INFO"))
    log = logging.getLogger("main")
    log.info("DenjiPet starting up (Comnyang feature suite enabled).")

    if not _acquire_lock():
        log.info("Another instance is already running — exiting silently.")
        sys.exit(0)

    ctx = _build_app(settings)

    # Position pet: restore the last saved spot (clamped on-screen) so it
    # stays exactly where the user placed it; otherwise default to center-top.
    screen = QApplication.primaryScreen().availableGeometry()
    saved = settings.window_pos
    if saved is not None:
        x = max(screen.left(), min(saved[0], screen.right() - ctx.pet.width()))
        y = max(screen.top(),  min(saved[1], screen.bottom() - ctx.pet.height()))
        ctx.pet.move(x, y)
    else:
        center_x = screen.left() + (screen.width() - ctx.pet.width()) // 2
        center_y = screen.top() + 150
        ctx.pet.move(center_x, center_y)

    # Start services
    ctx.pet.show()
    ctx.pet.raise_()
    ctx.pet.activateWindow()
    ctx.pet.trigger_reaction("🦇 Batman Pet here!")
    ctx.tray.show()
    ctx.tray.refresh_from_settings()
    ctx.anim.start()
    ctx.nudge.start()
    ctx.hydration.start()
    ctx.stretch_reminder.start()
    ctx.input_listener.start()
    ctx.pet_ai.start()
    ctx.brain.start()
    ctx.agent_hook.start()

    log.info("DenjiPet ready (pet-only mode — no timer HUD required, but optional).")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()