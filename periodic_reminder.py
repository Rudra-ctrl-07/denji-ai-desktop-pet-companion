"""
periodic_reminder.py — Shared base class for interval-based health reminders.

Implements the common plumbing of a periodic reminder:
  • a QTimer that fires every `interval_min` minutes
  • a snooze mechanism (skip the next N minutes when the user clicks the pet)
  • a NudgeBubble popup anchored to the pet window
  • a `_notify()` hook for subclasses to emit their own signal / reaction

Subclasses only provide a message pool, timing, and their reminder signal:
    HydrationReminder → wants_hydrate
    StretchReminder   → wants_stretch
"""

import logging
import random
import time

from PySide6.QtCore import QObject, QTimer

from nudge_manager import NudgeBubble

log = logging.getLogger(__name__)


class PeriodicReminder(QObject):
    """Base class for periodic, snoozeable reminder popups."""

    # Override in subclasses
    MESSAGES: list[str] = []
    DEFAULT_INTERVAL_MIN: int = 60
    BUBBLE_DURATION_MS: int = 6_000

    def __init__(self, pet_window, interval_min: int | None = None,
                 personalize=None, parent=None):
        super().__init__(parent)
        self._pet_window = pet_window
        self._interval_ms = (
            (interval_min if interval_min is not None else self.DEFAULT_INTERVAL_MIN)
            * 60 * 1_000
        )
        self._snooze_until_ms = 0
        # Optional callback to prepend the user's name (Comnyang's name-speaking)
        self._personalize = personalize or (lambda m: m)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._fire)

    # ------------------------------------------------------------------ public

    def start(self) -> None:
        self._timer.start(self._interval_ms)
        log.info("%s started — every %d min", type(self).__name__,
                 self._interval_ms // 60_000)

    def stop(self) -> None:
        self._timer.stop()

    def set_interval_min(self, minutes: int) -> None:
        """Update interval; restarts the timer if already running."""
        self._interval_ms = minutes * 60 * 1_000
        if self._timer.isActive():
            self._timer.setInterval(self._interval_ms)
        log.info("%s interval updated to %d min", type(self).__name__, minutes)

    def snooze(self, minutes: int = 30) -> None:
        """Skip the next reminder (called when the user clicks the pet)."""
        self._snooze_until_ms = int(time.time() * 1000) + minutes * 60 * 1000
        log.info("%s snoozed for %d min", type(self).__name__, minutes)

    def fire_now(self) -> None:
        """Manually trigger a reminder (handy for testing)."""
        self._fire()

    # ------------------------------------------------------------------ private

    def _fire(self) -> None:
        now_ms = int(time.time() * 1000)
        if now_ms < self._snooze_until_ms:
            # Reschedule the snooze-expiry check.
            remaining = self._snooze_until_ms - now_ms
            log.debug("%s reminder snoozed — skipping (%d ms left).",
                      type(self).__name__, remaining)
            QTimer.singleShot(remaining, self._fire)
            self._timer.start(self._interval_ms)
            return

        msg = self._personalize(random.choice(self.MESSAGES))
        log.info("%s reminder: %s", type(self).__name__, msg)
        pos = self._pet_window.pos()
        bubble = NudgeBubble(msg, anchor_x=pos.x(), anchor_y=pos.y(),
                             duration_ms=self.BUBBLE_DURATION_MS)
        bubble.show()
        self._notify()

    def _notify(self) -> None:
        """Hook for subclasses — emit their reminder signal."""
