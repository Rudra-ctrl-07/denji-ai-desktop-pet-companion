"""
name_speech.py — Small helper to insert the user's name into reminder
messages when configured (Comnyang's "speaks your name during reminders").

Usage:
    speaker = NameSpeech(settings)          # wraps settings.user_name
    msg = speaker.personalize("Drink water!")
    # → "Hey, Rudra — drink water!"
"""

import logging

log = logging.getLogger(__name__)


class NameSpeech:
    """Personalises generic reminders with the user's name."""

    PREFIX_WITH_NAME = "Hey, {name} — "

    def __init__(self, settings):
        self._settings = settings

    @property
    def user_name(self) -> str:
        return str(self._settings.get("user_name", "") or "").strip()

    @property
    def has_name(self) -> bool:
        return bool(self.user_name)

    def personalize(self, message: str) -> str:
        """Prepend the user's name if set; otherwise return message unchanged."""
        if not self.has_name:
            return message
        prefix = self.PREFIX_WITH_NAME.format(name=self.user_name)
        return prefix + message