"""
agent_hook.py — Comnyang-style "AI coding agent" reaction watcher.

File-based IPC: companion scripts in Claude Code / Cursor / Codex drop
status files into %APPDATA%/DenjiPet/agent_status/ and DenjiPet reacts.

Status file format (one line of JSON):
  { "agent": "claude", "status": "working", "session": "...", "ts": 1234567890 }

Status values:
  working   → emit reaction("WORKING")
  waiting   → reaction("CURIOUS")
  done      → reaction("CELEBRATE")
  error     → reaction("ANGRY")
  idle      → no reaction (reset to IDLE)

Off by default — user must opt in via Settings (`agent_hooks_enabled`).
"""

import json
import logging
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger(__name__)


def _agent_status_dir() -> Path:
    import os
    base = Path(os.environ.get("APPDATA", ".")) / "DenjiPet" / "agent_status"
    base.mkdir(parents=True, exist_ok=True)
    return base


class AgentHook(QObject):
    """
    Watches the agent_status directory for status files.
    Emits a reaction Signal whenever a status changes.

    Signals:
        reaction(str)    — map agent status → emotion name
    """

    POLL_INTERVAL_MS = 1_000    # 1 Hz poll (cheap, no fs-events needed)

    # agent_status → emotion_state
    REACTION_MAP: dict[str, str] = {
        "working": "WORKING",
        "waiting": "CURIOUS",
        "done":    "CELEBRATE",
        "error":   "ANGRY",
        # idle is treated as "no reaction" — we just go back to IDLE
    }

    reaction = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._dir = _agent_status_dir()
        self._last_seen: dict[str, str] = {}  # filename → last status

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)

    # ------------------------------------------------------------------ public

    def start(self) -> None:
        if not self._is_enabled():
            log.info("AgentHook disabled by settings.")
            return
        self._poll_timer.start(self.POLL_INTERVAL_MS)
        log.info("AgentHook started — watching %s", self._dir)

    def stop(self) -> None:
        self._poll_timer.stop()
        log.info("AgentHook stopped.")

    def is_enabled(self) -> bool:
        return self._is_enabled()

    def set_enabled(self, value: bool) -> None:
        self._settings.set("agent_hooks_enabled", bool(value))
        if value and not self._poll_timer.isActive():
            self._poll_timer.start(self.POLL_INTERVAL_MS)
            log.info("AgentHook enabled.")
        elif not value and self._poll_timer.isActive():
            self._poll_timer.stop()
            log.info("AgentHook disabled.")

    def write_status(self, agent: str, status: str, session: str = "default") -> None:
        """
        Test helper: write a status file as if a companion script emitted it.
        Also exposed for users who want to drive the pet from shell:
          python -c "from agent_hook import AgentHook; \
                     AgentHook(None).write_status('claude', 'working')"
        """
        ts = int(time.time() * 1000)
        data = {"agent": agent, "status": status, "session": session, "ts": ts}
        path = self._dir / f"{agent}_{session}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            log.debug("Wrote agent status: %s", data)
        except Exception as exc:
            log.warning("Failed to write agent status: %s", exc)

    # ------------------------------------------------------------------ private

    def _is_enabled(self) -> bool:
        return bool(self._settings.get("agent_hooks_enabled", False))

    def _poll(self) -> None:
        try:
            current_files = list(self._dir.glob("*.json"))
        except Exception as exc:
            log.debug("Agent status poll failed: %s", exc)
            return

        seen_now: set[str] = set()
        for path in current_files:
            seen_now.add(path.name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            status = data.get("status", "idle")
            if self._last_seen.get(path.name) == status:
                continue  # no change

            self._last_seen[path.name] = status
            emotion = self.REACTION_MAP.get(status)
            if emotion:
                log.info("Agent status: %s -> emotion %s", path.name, emotion)

                self.reaction.emit(emotion)

        # Forget deleted files
        for name in list(self._last_seen.keys()):
            if name not in seen_now:
                del self._last_seen[name]