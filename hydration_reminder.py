"""
hydration_reminder.py — Hourly water-drink reminder (separate from nudge manager).

Fires every `interval_min` minutes (default 60) and shows a prominent water-bottle
notification anchored to the pet window. Uses the hydrate sprite state so the pet
visually responds to the reminder too.

Snooze: dismisses a single reminder for `snooze_min` minutes when the pet is clicked.

Implementation lives in periodic_reminder.PeriodicReminder — this class only
provides the message pool, timing, and its reminder signal.
"""

import logging

from PySide6.QtCore import Signal

from periodic_reminder import PeriodicReminder

log = logging.getLogger(__name__)

HYDRATE_MESSAGES: list[str] = [
    "💧 Hydration check! Drink some water 💧",
    "💧 Time for a water break — stay sharp!",
    "💧 Water = focus. Take a sip!",
    "💧 Dehydration = headaches. Drink up!",
    "💧 Your brain is 75% water. Refill it!",
    "💧 One glass now = better focus for the next hour.",
    "💧 Sip sip! Don't let yourself dry out.",
]


class HydrationReminder(PeriodicReminder):
    """
    Fires a water-drink reminder every `interval_min` minutes.

    Signals:
        wants_hydrate()    — pet should switch to hydrate sprite for a few seconds
    """

    wants_hydrate = Signal()

    MESSAGES = HYDRATE_MESSAGES
    DEFAULT_INTERVAL_MIN = 60
    BUBBLE_DURATION_MS = 8_000

    def _notify(self) -> None:
        self.wants_hydrate.emit()
