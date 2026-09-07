"""
sound_pack.py — Optional sound effects (Comnyang-style sound packs).

Plays short Windows system sounds via `winsound.PlaySound` (built-in module,
no extra assets). Default OFF — user must enable in Settings.

Sounds (mapped to event names):
  pet        → SystemAsterisk       (gentle)
  overheat   → SystemHand           (warning)
  celebrate  → SystemExclamation    (cheer)
  stretch    → SystemAsterisk       (chime)
  error      → SystemHand           (buzz)
  note_add   → SystemAsterisk
  startup    → SystemStart

Sound is no-op on non-Windows platforms.
"""

import logging
import sys

log = logging.getLogger(__name__)


_SOUND_MAP: dict[str, str] = {
    "pet":       "SystemAsterisk",
    "overheat":  "SystemHand",
    "celebrate": "SystemExclamation",
    "stretch":   "SystemAsterisk",
    "error":     "SystemHand",
    "note_add":  "SystemAsterisk",
    "startup":   "SystemStart",
    "rev":       "SystemExclamation",
}


class SoundPack:
    """Lightweight sound dispatcher, enabled/disabled at runtime."""

    def __init__(self, settings):
        self._settings = settings
        self._available = sys.platform == "win32"
        if not self._available:
            log.info("SoundPack: non-Windows platform — sounds disabled.")

    @property
    def enabled(self) -> bool:
        if not self._available:
            return False
        return bool(self._settings.get("sound_enabled", False))

    def set_enabled(self, value: bool) -> None:
        self._settings.set("sound_enabled", bool(value))
        log.info("Sound enabled = %s", value)

    def play(self, event: str) -> None:
        """Play a sound for the given event. No-op if disabled."""
        if not self.enabled:
            return
        sound_name = _SOUND_MAP.get(event)
        if not sound_name:
            return
        try:
            import winsound
            winsound.PlaySound(sound_name, winsound.SND_ASYNC | winsound.SND_ALIAS)
        except Exception as exc:
            log.debug("Sound '%s' failed: %s", event, exc)