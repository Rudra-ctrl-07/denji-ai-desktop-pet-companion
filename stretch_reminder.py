"""
stretch_reminder.py — Periodic "stretch your back" reminder with a growing
animation. Plays the `stretch/` sprite folder so the pet visibly stretches
taller with arms up.

Snooze behaviour:
  • User clicks the pet → snooze for 30 min
  • User runs `snooze(minutes=N)` manually → snooze for N min

Uses NudgeBubble for the reminder text.

Implementation lives in periodic_reminder.PeriodicReminder — this class only
provides the message pool, timing, and its reminder signal.
"""

import logging

from PySide6.QtCore import Signal

from periodic_reminder import PeriodicReminder

log = logging.getLogger(__name__)

STRETCH_MESSAGES: list[str] = [
    "🧘 Stretch time! Arms up high!",
    "🧘 Stand up, roll those shoulders back.",
    "🧘 Reach for the ceiling — full body stretch!",
    "🧘 30 seconds of stretching = better focus.",
    "🧘 Back crack? Good. You're unlocked.",
    "🧘 Twist left, twist right. Spine says thanks.",
]


class StretchReminder(PeriodicReminder):
    """
    Fires every `interval_min` minutes (default 45) and:
      1. Emits wants_stretch (AnimationController.set_emotion("STRETCH", 4000))
      2. Shows a NudgeBubble with a stretch prompt

    Signals:
        wants_stretch()    — pet should play stretch animation for ~4s
    """

    wants_stretch = Signal()

    MESSAGES = STRETCH_MESSAGES
    DEFAULT_INTERVAL_MIN = 45
    BUBBLE_DURATION_MS = 6_000

    def _notify(self) -> None:
        self.wants_stretch.emit()
