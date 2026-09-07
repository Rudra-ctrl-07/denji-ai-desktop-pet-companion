"""
click_detector.py — Comnyang-style click timing detection.

Distinguishes between:
  • Single click         (released within 200ms, no drag)
  • Double click         (2nd click within 350ms of 1st)
  • Long press           (held >800ms without release)
  • Rapid petting        (≥3 clicks within 1500ms)

Signals:
    single_clicked(int)     — count of consecutive single clicks
    double_clicked()        — exactly 2 clicks in quick succession
    long_pressed()          — held without release
    rapid_pet(int)          — burst of fast clicks (count passed)
"""

import time
import logging

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger(__name__)


class ClickDetector(QObject):
    """Detects click patterns from raw press/release events."""

    DOUBLE_GAP_MS   = 350     # max gap between 1st and 2nd click for "double"
    RAPID_WINDOW_MS = 1_500   # window to count rapid pet
    LONG_PRESS_MS   = 800     # hold duration to count as long-press
    RAPID_THRESHOLD = 3       # ≥3 clicks in window → "rapid pet"

    single_clicked = Signal(int)
    double_clicked = Signal()
    long_pressed   = Signal()
    rapid_pet      = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._click_times: list[float] = []
        self._press_time_ms: int | None = None
        self._long_press_fired = False

        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.timeout.connect(self._on_long_press_fire)

        # Double-click decision is deferred by DOUBLE_GAP_MS so a fast third
        # click can still upgrade the pair into a rapid pet.
        self._double_timer = QTimer(self)
        self._double_timer.setSingleShot(True)
        self._double_timer.timeout.connect(self._on_double_fire)

    # ------------------------------------------------------------------ public

    def on_press(self) -> None:
        """User pressed the mouse down on the pet."""
        self._press_time_ms = int(time.time() * 1000)
        self._long_press_fired = False
        self._long_press_timer.start(self.LONG_PRESS_MS)
        # A new press supersedes any pending double-click decision.
        self._double_timer.stop()

    def on_release(self, was_dragging: bool) -> None:
        """User released the mouse. `was_dragging` = True if a drag happened."""
        self._long_press_timer.stop()

        # A long-press was already emitted while holding.
        if self._long_press_fired:
            return

        # If the user was dragging, ignore the release as a click.
        if was_dragging:
            return

        now_ms = int(time.time() * 1000)
        if self._press_time_ms is None or (now_ms - self._press_time_ms) > 600:
            return  # too long, treat as a separate event

        self._click_times.append(now_ms)
        # Prune old clicks outside the rapid window
        self._click_times = [
            t for t in self._click_times
            if now_ms - t <= self.RAPID_WINDOW_MS
        ]

        # Rapid pet? (≥3 clicks in window)
        if len(self._click_times) >= self.RAPID_THRESHOLD:
            count = len(self._click_times)
            self._click_times.clear()
            self.rapid_pet.emit(count)
            log.debug("Rapid pet detected (%d clicks).", count)
            return

        # Two clicks — defer the double decision by DOUBLE_GAP_MS so a fast
        # third click can still upgrade the pair into a rapid pet.
        if len(self._click_times) == 2:
            self._double_timer.start(self.DOUBLE_GAP_MS)
            return

        # Single click — emit immediately.
        self.single_clicked.emit(1)

    # ------------------------------------------------------------------ private

    def _on_double_fire(self) -> None:
        """The double-click gap elapsed with no third click → it's a double."""
        self._click_times.clear()
        self.double_clicked.emit()
        log.debug("Double click.")

    def _on_long_press_fire(self) -> None:
        if self._press_time_ms is None:
            return
        elapsed = int(time.time() * 1000) - self._press_time_ms
        if elapsed >= self.LONG_PRESS_MS:
            self._long_press_fired = True
            self.long_pressed.emit()
            log.debug("Long press fired (held %d ms).", elapsed)