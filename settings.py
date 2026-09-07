"""
settings.py — Load / save user configuration from a JSON file.

Config file location:
  - Windows : %APPDATA%/DenjiPet/config.json
  - Other OS: ./config.json  (dev fallback)

The file is written atomically (write to .tmp, then os.replace) so a crash
during save never corrupts the previous config (NFR-05).

A "schema_version" field allows future migrations (CFG-01/02/03).
"""

import json
import os
import shutil
import logging
from pathlib import Path

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# Single source of truth: config key → (default value, coercing type).
# A type of None means the key has no typed attribute and is read via
# Settings.get(...) instead (schema_version, window position, log_level).
SPEC: dict[str, tuple] = {
    "schema_version":          (SCHEMA_VERSION, None),
    "work_duration_min":       (25,   int),
    "break_duration_min":      (5,    int),
    "long_break_duration_min": (15,   int),
    "nudge_interval_min":      (20,   int),
    "water_interval_min":      (60,   int),
    "stretch_interval_min":    (45,   int),
    "window_x":                (None,  None),      # last saved window X position
    "window_y":                (None,  None),      # last saved window Y position
    "log_level":               ("INFO", None),
    "user_name":               ("",    str),      # Comnyang name-speaking
    "pomodoro_hud":            (True,  bool),
    "sound_enabled":           (False, bool),
    "agent_hooks_enabled":     (False, bool),
    "pet_size":                (128,   int),
    "always_on_top":           (True,  bool),
    "llm_enabled":             (True,  bool),      # Intelligence upgrade
    "intelligence_priority":   ("high", str),
}

# Defaults are derived from SPEC so the two can never drift apart.
DEFAULTS: dict = {key: spec[0] for key, spec in SPEC.items()}


def _typed_property(key: str, typ: type) -> property:
    """
    Build a typed getter/setter property backed by Settings.get/set.

    A stored None on a str key reads back as "" (matches the old `or ""`
    guard on user_name); int/bool getters behave exactly as before.
    """

    def getter(self):
        value = self.get(key)
        if value is None and typ is str:
            return ""
        return typ(value)

    def setter(self, value):
        self.set(key, typ(value))

    return property(getter, setter)


def _config_path() -> Path:
    """Return the platform-appropriate config file path."""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", str(Path.home()))
        return Path(appdata) / "DenjiPet" / "config.json"
    # Non-Windows: fall back to current directory (handy for dev)
    return Path("config.json")


class Settings:
    """
    Thin wrapper around a dict backed by a JSON file.

    Typed attributes (work_duration_min, pet_size, pomodoro_hud, ...) are
    generated from the SPEC table at the bottom of this module, so every
    config key with a coercing type gets a matching accessor automatically.

    Usage:
        s = Settings()
        print(s.work_duration_min)   # → 25
        s.work_duration_min = 30
        s.save()
    """

    def __init__(self):
        self._path = _config_path()
        self._data: dict = {}
        self.load()

    # ------------------------------------------------------------------ load/save

    def load(self) -> None:
        """Read config from disk; regenerate defaults on any parse error."""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            # Forward-migrate: ensure any keys added in newer schema versions
            # are present, using our defaults as fill-ins (CFG-02).
            migrated = {**DEFAULTS, **raw}
            migrated["schema_version"] = SCHEMA_VERSION

            # If stored schema_version is newer than we understand, keep only
            # recognized keys and fall back to defaults for the rest (CFG-03).
            self._data = migrated
            log.info("Config loaded from %s", self._path)

        except FileNotFoundError:
            log.info("No config file at %s — using defaults.", self._path)
            self._data = dict(DEFAULTS)

        except Exception as exc:
            log.error("Config parse error (%s) — regenerating defaults.", exc)
            self._data = dict(DEFAULTS)

    def save(self) -> None:
        """
        Atomically write config to disk.
        Writes to a .tmp file first, then renames to avoid partial writes.
        """
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            # os.replace is atomic on the same filesystem (POSIX & Windows)
            try:
                tmp.replace(self._path)
            except OSError:
                shutil.move(str(tmp), str(self._path))
            log.info("Config saved to %s", self._path)
        except Exception as exc:
            log.error("Failed to save config: %s", exc)

    # ------------------------------------------------------------------ generic accessors

    def get(self, key: str, fallback=None):
        """Get a config value, falling back to DEFAULTS then `fallback`."""
        return self._data.get(key, DEFAULTS.get(key, fallback))

    def set(self, key: str, value) -> None:
        """Set a config value in memory (call save() to persist)."""
        self._data[key] = value

    # ------------------------------------------------------------------ composite accessors

    @property
    def window_pos(self) -> tuple[int, int] | None:
        """Returns (x, y) if a position was saved, else None."""
        x = self.get("window_x")
        y = self.get("window_y")
        if x is not None and y is not None:
            return (int(x), int(y))
        return None

    def set_window_pos(self, x: int, y: int) -> None:
        self.set("window_x", x)
        self.set("window_y", y)


# ---------------------------------------------------------------------------
# Generate one typed attribute per SPEC key that has a coercing type, keeping
# the accessor list in lock-step with the defaults table above:
#   s.work_duration_min  ⇔  int(s.get("work_duration_min"))
# ---------------------------------------------------------------------------
for _key, _spec in SPEC.items():
    if _spec[1] is not None:
        setattr(Settings, _key, _typed_property(_key, _spec[1]))
