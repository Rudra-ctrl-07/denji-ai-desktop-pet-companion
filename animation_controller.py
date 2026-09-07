"""
animation_controller.py — Frame-cycling sprite animation for the pet window.

How it works:
  1. Point it at a folder containing `frame_0.png`, `frame_1.png`, … PNGs.
  2. Call start() — a QTimer fires every (1000/fps) ms and advances the frame.
  3. Each tick emits frame_changed(QPixmap), which the PetWindow connects to
     its set_frame() slot to update the display.
  4. Call set_state(state_name) to swap the active sprite folder when the
     Pomodoro engine changes state.

Fallback: if the folder is missing or empty, no frames are loaded and the
PetWindow will draw its built-in placeholder shape instead.
"""

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QPixmap

log = logging.getLogger(__name__)


def _resolve_asset_root() -> Path:
    """
    Resolve the sprite root folder in both dev (`python main.py` from project)
    and PyInstaller-bundled (`DenjiPet.exe`) contexts.

    PyInstaller sets sys._MEIPASS to the temp dir where bundled datas live
    (assets/, configs, etc.). In dev, we fall back to the literal "assets"
    relative to the current working directory.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "assets"
    return Path("assets")

# Maps Pomodoro state strings (emitted by PomodoroEngine) and emotion names
# (passed to set_emotion) to sub-folder names inside the sprite root.
STATE_FOLDER_MAP: dict[str, str] = {
    # Pomodoro states
    "IDLE":       "idle",
    "WORKING":    "working",
    "BREAK":      "break",
    "LONG_BREAK": "tired",
    "CELEBRATE":  "celebrate",
    # Emotion states
    "SAD":        "sad",
    "ANGRY":      "angry",
    "LOVE":       "love",
    "SLEEPY":     "sleepy",
    "DIZZY":      "dizzy",
    "CURIOUS":    "curious",
    "HYDRATE":    "hydrate",
    "CONFIDENT":  "confident",
    # New Comnyang-parity states
    "STRETCH":      "stretch",
    "SCROLL_PAPER": "scroll_paper",
    "SHOCK":        "shock",
    "FIST":         "fist",
    "CHAIN_REV":    "chain_rev",
    "HEAD_BLADE":   "head_blade",
    "WAITING":      "waiting",
    "PURR":         "purr",
}


class AnimationController(QObject):
    """
    Manages frame-cycling sprite animation.

    Signals:
        frame_changed(QPixmap): Emitted every timer tick with the next frame.
            Connect this to PetWindow.set_frame().
    """

    frame_changed = Signal(QPixmap)

    def __init__(self, sprite_root: str | Path | None = None, fps: int = 6, parent=None):
        super().__init__(parent)
        self._sprite_root = Path(sprite_root) if sprite_root else _resolve_asset_root()
        self._fps = max(1, fps)           # guard against zero-division
        self._frames: list[QPixmap] = []
        self._current_index = 0
        self._locked = False              # when True, emotion timer won't revert
        self._emotion_timer: QTimer | None = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)

    # ------------------------------------------------------------------ public API

    def set_state(self, state: str) -> None:
        """
        Switch animation to the sprite folder for the given Pomodoro state.
        Called automatically when PomodoroEngine.state_changed is emitted.
        """
        if self._emotion_timer and self._emotion_timer.isActive():
            self._emotion_timer.stop()
        sub_dir = STATE_FOLDER_MAP.get(state, "idle")
        folder = self._sprite_root / sub_dir
        log.debug("Switching animation state → %s (%s)", state, folder)
        self._load_folder(folder)

    def set_emotion(self, emotion: str, duration_ms: int | None = None) -> None:
        """
        Switch to an emotion sprite for a temporary duration.
        After `duration_ms` (default 4000), returns to idle.
        """
        if self._emotion_timer and self._emotion_timer.isActive():
            self._emotion_timer.stop()
        sub_dir = STATE_FOLDER_MAP.get(emotion, emotion)
        folder = self._sprite_root / sub_dir
        log.debug("Emotion → %s (%s, %sms)", emotion, folder, duration_ms)
        self._load_folder(folder)
        if duration_ms:
            self._emotion_timer = QTimer(self)
            self._emotion_timer.setSingleShot(True)
            self._emotion_timer.timeout.connect(
                lambda: self.set_state("IDLE") if not self._locked else None
            )
            self._emotion_timer.start(duration_ms)

    def start(self) -> None:
        """Start the animation timer."""
        interval_ms = int(1000 / self._fps)
        self._timer.start(interval_ms)
        log.debug("Animation started — %d fps, interval %d ms", self._fps, interval_ms)

    def stop(self) -> None:
        """Stop the animation timer."""
        self._timer.stop()
        log.debug("Animation stopped.")

    @property
    def has_frames(self) -> bool:
        """True if at least one sprite frame is loaded."""
        return bool(self._frames)

    # ------------------------------------------------------------------ private

    def _load_folder(self, folder: Path) -> None:
        """
        Scan `folder` for frame_N.png files, load them as QPixmaps, and
        restart the animation from frame 0.

        If `assets/custom/pet.png` exists, it replaces ALL state / emotion
        sprites with that single image (no frame cycling). Drop your own PNG
        there to use a custom pet without touching the other sprite folders.
        """
        self._frames = []
        self._current_index = 0

        custom = self._sprite_root / "custom" / "pet.png"
        if custom.is_file():
            px = QPixmap(str(custom))
            if not px.isNull():
                self._frames = [px]
                log.info("Using custom sprite %s", custom)
                self._emit_current()
                return
            log.warning("Could not load custom sprite: %s", custom)

        if not folder.is_dir():
            log.warning("Sprite folder not found: %s — falling back to placeholder.", folder)
            return

        # Collect all frame_N.png files sorted by their numeric index.
        png_files = sorted(
            folder.glob("frame_*.png"),
            key=lambda p: self._parse_frame_index(p.name),
        )

        for path in png_files:
            px = QPixmap(str(path))
            if not px.isNull():
                self._frames.append(px)
            else:
                log.warning("Could not load sprite: %s", path)

        if self._frames:
            log.info("Loaded %d frames from '%s'", len(self._frames), folder)
            self._emit_current()   # immediately show first frame
        else:
            log.warning("No valid PNG frames in '%s' — fallback shape will render.", folder)

    @staticmethod
    def _parse_frame_index(filename: str) -> int:
        """
        Extract the integer N from 'frame_N.png' for numeric sorting.
        Returns 0 on any parse failure so the file still appears in the list.
        """
        try:
            stem = filename.removeprefix("frame_").removesuffix(".png")
            return int(stem)
        except ValueError:
            return 0

    def _advance_frame(self) -> None:
        """Called by QTimer every tick — move to the next frame and emit it."""
        if not self._frames:
            return
        self._current_index = (self._current_index + 1) % len(self._frames)
        self._emit_current()

    def _emit_current(self) -> None:
        if self._frames:
            self.frame_changed.emit(self._frames[self._current_index])

    def refresh_frame(self) -> None:
        """Re-emit current frame signal (useful when pet size or scale changes)."""
        self._emit_current()

