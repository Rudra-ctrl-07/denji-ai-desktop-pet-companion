"""
pomodoro_engine.py — Pomodoro timer state machine.

States
------
  IDLE        Not started / manually paused before the first session
  WORKING     Active focus session (default 25 min)
  BREAK       Short rest between sessions (default 5 min)
  LONG_BREAK  Extended rest every 4th cycle (default 15 min)

Transitions
-----------
  IDLE      --[start()]--> WORKING
  WORKING   --[timer up]--> BREAK  (or LONG_BREAK every 4th)
  BREAK /
  LONG_BREAK --[timer up]--> WORKING
  any       --[reset()]--> IDLE

Signals
-------
  state_changed(str)      Fired on every state transition — connect to
                          AnimationController.set_state() and TrayMenu.update_state().
  tick(int, int)          Fires every second: (remaining_seconds, total_seconds).
                          Use for a future timer overlay / HUD.
  session_completed(int)  Fires when a WORKING session ends; carries the
                          cumulative completed-session count.
"""

import logging
from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger(__name__)


class PomodoroEngine(QObject):
    """Pomodoro timer as a Qt state machine."""

    # ---- signals ----
    state_changed    = Signal(str)   # emits new state name
    tick             = Signal(int, int)  # (remaining_sec, total_sec)
    session_completed = Signal(int)  # (total sessions completed so far)

    def __init__(
        self,
        work_min:       int = 25,
        break_min:      int = 5,
        long_break_min: int = 15,
        parent=None,
    ):
        super().__init__(parent)
        # Store durations in seconds for arithmetic convenience.
        self._work_sec       = work_min       * 60
        self._break_sec      = break_min      * 60
        self._long_break_sec = long_break_min * 60

        self._state          = "IDLE"
        self._remaining_sec  = 0
        self._total_sec      = 0
        self._sessions_done  = 0
        self._running        = False

        self._timer = QTimer(self)
        self._timer.setInterval(1_000)   # 1-second resolution
        self._timer.timeout.connect(self._on_tick)

    # ------------------------------------------------------------------ read-only props

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def sessions_completed(self) -> int:
        return self._sessions_done

    @property
    def remaining_sec(self) -> int:
        return self._remaining_sec

    @property
    def total_sec(self) -> int:
        return self._total_sec

    # ------------------------------------------------------------------ public control

    def start(self) -> None:
        """Start from IDLE or resume from a paused state."""
        if self._state == "IDLE":
            self._enter_state("WORKING", self._work_sec)
        else:
            # Resuming from a pause — just restart the timer.
            self._running = True
            self._timer.start()
        log.info("Pomodoro started/resumed (state=%s)", self._state)

    def pause(self) -> None:
        """Pause the countdown without losing the current state."""
        self._running = False
        self._timer.stop()
        log.info("Pomodoro paused (state=%s, remaining=%ds)", self._state, self._remaining_sec)

    def reset(self) -> None:
        """Return to IDLE and reset the session counter."""
        self._timer.stop()
        self._running    = False
        self._sessions_done = 0
        self._set_state("IDLE")
        self._remaining_sec = 0
        self._total_sec     = 0
        log.info("Pomodoro reset.")

    def update_durations(
        self,
        work_min:       int,
        break_min:      int,
        long_break_min: int,
    ) -> None:
        """
        Update timer durations from Settings.
        Takes effect at the next state transition, not mid-session.
        """
        self._work_sec       = work_min       * 60
        self._break_sec      = break_min      * 60
        self._long_break_sec = long_break_min * 60
        log.info(
            "Durations updated — work=%dm, break=%dm, long_break=%dm",
            work_min, break_min, long_break_min,
        )

    # ------------------------------------------------------------------ private

    def _on_tick(self) -> None:
        """Called every second by QTimer while running."""
        if self._remaining_sec > 0:
            self._remaining_sec -= 1
            self.tick.emit(self._remaining_sec, self._total_sec)
        else:
            # Timer expired — move to the next state.
            self._advance()

    def _advance(self) -> None:
        """Determine the next state when the current countdown hits zero."""
        if self._state == "WORKING":
            self._sessions_done += 1
            self.session_completed.emit(self._sessions_done)
            log.info("Session %d complete.", self._sessions_done)
            # Every 4th completed session → long break (FR-04).
            if self._sessions_done % 4 == 0:
                self._enter_state("LONG_BREAK", self._long_break_sec)
            else:
                self._enter_state("BREAK", self._break_sec)

        elif self._state in ("BREAK", "LONG_BREAK"):
            self._enter_state("WORKING", self._work_sec)

    # ---- state-entry helpers ----

    def _enter_state(self, state: str, total_sec: int) -> None:
        """
        Load a timed state's duration and start its countdown.

        `_running` is set True unconditionally — every timed state implies a
        running timer (break states were already running when reached).
        """
        self._total_sec     = total_sec
        self._remaining_sec = total_sec
        self._set_state(state)
        self._running = True
        self._timer.start()

    def _set_state(self, state: str) -> None:
        self._state = state
        self.state_changed.emit(state)
        log.info("→ State: %s", state)
