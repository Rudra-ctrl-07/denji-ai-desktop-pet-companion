"""
intelligence.py — Context-aware decision layer for DenjiPet.

This module subscribes to every signal available in the runtime graph
(Pomodoro state, typing, clicks, agent status, hydration/stretch reminders)
and emits higher-signal `wants_reaction` / `wants_emotion` triggers that
override the random ambient reactivity of PetAI.

The brain is purely additive — PetAI keeps running alongside it, but the
brain's reactions win whenever there's a meaningful context event
(affection burst, typing burst during WORKING, late-night silence, etc.)

Public surface:
    Intelligence(settings, pet_window, name_speaker, pet_ai, parent=None)
        .on_pomodoro_state(str)
        .on_session_completed(int)
        .on_typing_event(int)
        .on_overheat(bool)
        .on_mouse_activity(int, int)
        .on_scroll_activity(int)
        .on_click()
        .on_rapid_pet(int)
        .on_action(str)
        .on_hydration()
        .on_stretch()
        .on_agent_status(str)

        Signals:
            wants_reaction(str)        — bubble text
            wants_emotion(str)         — sprite emotion name (matches animation_controller STATE_FOLDER_MAP)
"""

from __future__ import annotations

import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from pet_ai import (
    AGENT_REACTION_BUBBLES,
    CURIOUS_REACTIONS,
    GRUMPY_REACTIONS,
    JOY_REACTIONS,
    LATE_NIGHT_REACTIONS,
    POMODORO_BREAK_REACTIONS,
    POMODORO_FOCUS_REACTIONS,
    POMODORO_TIRED_REACTIONS,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunables (kept on the class so they're trivial to retune)
# ---------------------------------------------------------------------------

# Interaction / idle heuristics
INTERACTION_TIMEOUT_MS      = 5  * 60 * 1000   # 5 min silence → "curious"
LATE_NIGHT_IDLE_MS          = 10 * 60 * 1000   # 10 min + late-night → "sleepy"
GRUMPY_IDLE_MS              = 30 * 60 * 1000   # 30 min silence → "grumpy" mood

# Affection thresholds (rolling windows)
AFFECTION_WINDOW_MS         = 10 * 1000        # 10s rolling
AFFECTION_THRESHOLD         = 5                # 5+ clicks/10s → LOVE
JOY_WINDOW_MS               = 5  * 1000
JOY_THRESHOLD               = 3                # 3+ clicks/5s → HAPPY bubble

# Typing burst
TYPING_BURST_CPM            = 120              # >120 CPM = burst
TYPING_BURST_HOLD_MS        = 5  * 1000        # must sustain 5s

# Session focus milestones (minutes into a WORKING state)
FOCUS_LONG_MIN              = 25               # WORKING ≥25min → TIRED

# Late-night band (local time)
LATE_NIGHT_START_HOUR       = 22               # 22:00–04:00 = late night
LATE_NIGHT_END_HOUR         = 4

# Reaction de-duplication
RECENT_REACTIONS_MAX        = 5                # last 5 reactions cached

# Mood update cadence (matches pet_ai._tick)
MOOD_TICK_MS                = 60 * 1000

# Energy dynamics
ENERGY_RECOVER              = 0.05             # per mood tick when no negative events
ENERGY_AFFECTION            = 0.10             # +0.10 when affection in window
ENERGY_OVERHEAT             = -0.15            # big drop on overheat
ENERGY_LONG_IDLE            = -0.20            # big drop when grumpy kicks in
ENERGY_FATIGUE              = -0.05            # sustained focus
ENERGY_FLOOR                = 0.0
ENERGY_CEIL                 = 1.0
ENERGY_TARGET               = 0.7              # idle/playful resting point


# ---------------------------------------------------------------------------
# Context state
# ---------------------------------------------------------------------------

@dataclass
class ContextState:
    """Live snapshot of what the pet knows about the user's current moment."""

    # Pomodoro
    pomodoro_state:    str   = "IDLE"
    pomodoro_running:  bool  = False
    session_started_ms: int  = 0                 # when current WORKING session began
    session_focus_min: int  = 0                 # updated each tick

    # Typing
    typing_cpm:        int   = 0
    typing_burst:      bool  = False
    typing_burst_started_ms: int = 0

    # Overheat
    overheat:          bool  = False

    # Interaction
    last_interaction_ms: int = 0                 # any user event
    click_times:        deque = field(default_factory=lambda: deque(maxlen=64))

    # Mood / energy
    mood:              str   = "playful"
    energy:            float = 0.7

    # Recent reactions (dedupe)
    recent_reactions:   deque = field(default_factory=lambda: deque(maxlen=RECENT_REACTIONS_MAX))

    # Affection bursts (separate from raw click_times)
    affection_window_started_ms: int = 0
    affection_count_in_window:    int = 0

    # Drag-suppression
    is_being_dragged:  bool  = False

    # Agent status (one of "working"/"waiting"/"done"/"error"/None)
    last_agent_status: str | None = None


def _now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Reaction library — short, punchy bubbles (voice-cued not user-friendly).
# Single source of truth lives in pet_ai.py and is imported above so the two
# modules can't drift apart.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Brain
# ---------------------------------------------------------------------------

class Intelligence(QObject):
    """
    Subscribes to user-context signals and emits higher-priority reactions
    than PetAI's random ambient baseline.

    The brain is intentionally side-effect free besides emitting its own
    signals — it never calls QPixmap methods, never opens windows. It's a
    thin layer that picks the *what*, then defers rendering to existing
    `pet.trigger_reaction` / `animation_controller.set_emotion`.
    """

    wants_reaction = Signal(str)        # bubble text
    wants_emotion  = Signal(str)        # emotion name

    def __init__(
        self,
        settings,
        pet_window=None,
        name_speaker=None,
        pet_ai=None,
        parent=None,
    ):
        super().__init__(parent)
        self._settings     = settings
        self._pet_window   = pet_window
        self._speaker      = name_speaker
        self._pet_ai       = pet_ai

        self._ctx = ContextState()
        self._ctx.last_interaction_ms = _now_ms()

        self._affection_window_timer = QTimer(self)
        self._affection_window_timer.setSingleShot(True)
        self._affection_window_timer.timeout.connect(self._maybe_fire_affection)

        self._burst_hold_timer = QTimer(self)
        self._burst_hold_timer.setSingleShot(True)
        self._burst_hold_timer.timeout.connect(self._check_burst_hold)

        self._mood_timer = QTimer(self)
        self._mood_timer.setInterval(MOOD_TICK_MS)
        self._mood_timer.timeout.connect(self._on_mood_tick)

        # Re-entrancy guard — global mute for noisy intervals
        self._suppressed_until_ms = 0

        # Per-key throttle for "did we recently say a curious / grumpy thing?"
        self._throttle: dict[str, int] = {}

    # ------------------------------------------------------------------ public lifecycle

    def start(self) -> None:
        """Begin the brain's background mood/idle tick. Call once after construction."""
        self._mood_timer.start()
        log.info("Intelligence started (priority=%s)",
                 self._settings.get("intelligence_priority", "high"))

    def stop(self) -> None:
        self._mood_timer.stop()
        self._affection_window_timer.stop()
        self._burst_hold_timer.stop()

    # ------------------------------------------------------------------ input listeners

    def on_pomodoro_state(self, state: str) -> None:
        """PomodoroEngine.state_changed."""
        self._ctx.pomodoro_state = state
        self._ctx.pomodoro_running = state in ("WORKING", "BREAK", "LONG_BREAK")

        if state == "WORKING":
            self._ctx.session_started_ms = _now_ms()
            self._ctx.session_focus_min  = 0
            # Nudge reaction so the user knows the pet noticed.
            self._emit_unique(self._pick(POMODORO_FOCUS_REACTIONS), emotion="CONFIDENT")
        elif state == "BREAK":
            self._emit_unique(self._pick(POMODORO_BREAK_REACTIONS), emotion="HAPPY")
        elif state == "LONG_BREAK":
            self._emit_unique(self._pick(POMODORO_BREAK_REACTIONS), emotion="SLEEPY")
        elif state == "IDLE":
            self._ctx.session_focus_min = 0

    def on_session_completed(self, count: int) -> None:
        """PomodoroEngine.session_completed — celebrate milestone."""
        # Every 4th is long_break; we celebrate every one but especially milestones.
        if count % 4 == 0:
            self._emit_unique(f"🎉 Session #{count} done — long break earned!",
                              emotion="CELEBRATE")
        else:
            self._emit_unique(f"💪 Session #{count} in the books!", emotion="CONFIDENT")

    def on_typing_event(self, cpm: int) -> None:
        """InputListener.typing_event (CPM)."""
        self._ctx.typing_cpm = int(cpm)
        if cpm >= TYPING_BURST_CPM and not self._ctx.typing_burst:
            self._ctx.typing_burst_started_ms = _now_ms()
            self._burst_hold_timer.start(TYPING_BURST_HOLD_MS)
        elif cpm < TYPING_BURST_CPM:
            self._ctx.typing_burst = False
            self._burst_hold_timer.stop()

    def on_overheat(self, overheat: bool) -> None:
        """InputListener.overheat_triggered — already emits sprite change, but mark state."""
        self._ctx.overheat = bool(overheat)
        self._ctx.last_interaction_ms = _now_ms()

    def on_mouse_activity(self, _x: int, _y: int) -> None:
        """InputListener.mouse_moved — generic liveness update."""
        self._ctx.last_interaction_ms = _now_ms()

    def on_scroll_activity(self, _delta: int) -> None:
        """InputListener.scroll_event — generic liveness update."""
        self._ctx.last_interaction_ms = _now_ms()

    def on_click(self, *_args) -> None:
        """PetWindow.clicked + double_clicked — track for joy/affection bursts."""
        now = _now_ms()
        self._ctx.last_interaction_ms = now
        self._ctx.click_times.append(now)

        # Roll the affection window
        if self._ctx.affection_window_started_ms == 0:
            self._ctx.affection_window_started_ms = now
            self._ctx.affection_count_in_window = 0
            self._affection_window_timer.start(AFFECTION_WINDOW_MS)

        self._ctx.affection_count_in_window += 1

        # Joy burst (≥3 clicks in 5s) — fire a quick happy bubble + maybe emotion
        if len(self._ctx.click_times) >= JOY_THRESHOLD:
            # Use only clicks within the JOY window
            recent = [t for t in self._ctx.click_times if now - t <= JOY_WINDOW_MS]
            if len(recent) >= JOY_THRESHOLD:
                self._emit_unique(self._pick(JOY_REACTIONS), emotion="HAPPY")

    def on_rapid_pet(self, count: int) -> None:
        """PetWindow.rapid_pet — strong affection signal."""
        now = _now_ms()
        self._ctx.last_interaction_ms = now
        # bypass the affection-window timer if user is rapid-petting
        self._ctx.affection_count_in_window += count
        if self._ctx.affection_count_in_window >= AFFECTION_THRESHOLD:
            self._ctx.mood = "affectionate"
            self._emit_unique(self._pick(["( ♡‿♡ ) ...do that again.",
                                           "*melts*",
                                           "So many pets!",
                                           "💕 Heh."]),
                              emotion="LOVE")
            self._ctx.affection_count_in_window = 0  # reset so it doesn't fire endlessly

    def on_action(self, action: str) -> None:
        """PetWindow.action_triggered — track intentional pet/rev actions."""
        self._ctx.last_interaction_ms = _now_ms()
        if action == "pet":
            self._ctx.affection_count_in_window += 1

    def on_hydration(self) -> None:
        """HydrationReminder.wants_hydrate — pet reacts to a hydration event."""
        # The reminder module already triggers HYDRATE sprite. Here we
        # personalise / add a bubble.
        msg = "💧 Water break!"
        if self._speaker and getattr(self._speaker, "has_name", False):
            msg = self._speaker.personalize(msg)
        self._emit_unique(msg, emotion=None)  # emotion is handled elsewhere
        self._ctx.last_interaction_ms = _now_ms()

    def on_stretch(self) -> None:
        """StretchReminder.wants_stretch — pet reacts to a stretch event."""
        msg = "🧘 Stretch time — touch your toes!"
        if self._speaker and getattr(self._speaker, "has_name", False):
            msg = self._speaker.personalize(msg)
        self._emit_unique(msg, emotion=None)
        self._ctx.last_interaction_ms = _now_ms()

    def on_agent_status(self, status: str) -> None:
        """AgentHook.reaction — pet reacts when external AI agent changes state."""
        self._ctx.last_agent_status = status
        msg = AGENT_REACTION_BUBBLES.get(status.lower())
        if msg:
            self._emit_unique(msg, emotion=status.upper())

    def set_being_dragged(self, dragging: bool) -> None:
        """Pet window should call this when drag/release happens."""
        self._ctx.is_being_dragged = bool(dragging)

    # ------------------------------------------------------------------ mood cascade

    def _on_mood_tick(self) -> None:
        """60-second background tick: update mood, focus duration, idle reactions."""
        now = _now_ms()

        # 1. Session focus minutes (only meaningful while WORKING)
        if self._ctx.pomodoro_state == "WORKING" and self._ctx.session_started_ms:
            minutes = (now - self._ctx.session_started_ms) // 60_000
            if minutes != self._ctx.session_focus_min:
                self._ctx.session_focus_min = int(minutes)
                # Long-focus nudge (once per threshold crossing)
                if minutes == FOCUS_LONG_MIN:
                    self._emit_unique(self._pick(POMODORO_TIRED_REACTIONS),
                                      emotion="TIRED")

        # 2. Idle cascade — if no interaction for a long time
        idle_ms = now - self._ctx.last_interaction_ms
        if idle_ms > LATE_NIGHT_IDLE_MS and self._is_late_night():
            self._emit_unique(self._pick(LATE_NIGHT_REACTIONS), emotion="SLEEPY")
            self._ctx.mood = "tired"
        elif idle_ms > INTERACTION_TIMEOUT_MS:
            # Periodic curious nudges, throttled
            if not self._suppressed("curious", cooldown_ms=120_000):
                self._suppress("curious", 120_000)
                self._emit_unique(self._pick(CURIOUS_REACTIONS), emotion="CURIOUS")
        if idle_ms > GRUMPY_IDLE_MS:
            self._ctx.mood = "grumpy"
            self._ctx.energy = max(ENERGY_FLOOR, self._ctx.energy + ENERGY_LONG_IDLE)

        # 3. Mood + energy shift on affection
        now_clicks = list(self._ctx.click_times)
        recent_clicks = [t for t in now_clicks if now - t <= 60_000]
        if len(recent_clicks) >= 3:
            self._ctx.mood = "affectionate"
            self._ctx.energy = min(ENERGY_CEIL, self._ctx.energy + ENERGY_AFFECTION)

        # 4. Overheat → tired mood
        if self._ctx.overheat:
            self._ctx.mood = "tired"
            self._ctx.energy = max(ENERGY_FLOOR, self._ctx.energy + ENERGY_OVERHEAT)

        # 5. Slow drift toward target when no negative event
        if self._ctx.mood not in ("tired", "grumpy"):
            drift = (ENERGY_TARGET - self._ctx.energy) * 0.05
            self._ctx.energy = max(ENERGY_FLOOR, min(ENERGY_CEIL,
                                                     self._ctx.energy + drift))
            if self._ctx.mood != "affectionate":
                self._ctx.mood = "playful"

        # 6. Drop *very* old clicks (last 64 is plenty of room but be safe)
        cutoff = now - 60_000
        while self._ctx.click_times and self._ctx.click_times[0] < cutoff:
            self._ctx.click_times.popleft()

        # 7. Periodic grumpy grumble
        if self._ctx.mood == "grumpy" and not self._suppressed("grumpy", cooldown_ms=180_000):
            self._suppress("grumpy", 180_000)
            self._emit_unique(self._pick(GRUMPY_REACTIONS), emotion="ANGRY")

    def _maybe_fire_affection(self) -> None:
        """The 10s affection-window timer expired — promote to LOVE if ≥5."""
        if self._ctx.affection_count_in_window >= AFFECTION_THRESHOLD:
            self._ctx.mood = "affectionate"
            self._emit_unique(self._pick(["( ♡‿♡ ) ...do that again.",
                                           "*melts*",
                                           "💕 You remembered me!"]),
                              emotion="LOVE")
        # Reset
        self._ctx.affection_window_started_ms = 0
        self._ctx.affection_count_in_window = 0

    def _check_burst_hold(self) -> None:
        """5s elapsed after first high-CPM event — confirm burst and react."""
        if self._ctx.typing_cpm >= TYPING_BURST_CPM and \
                self._ctx.pomodoro_state == "WORKING":
            self._ctx.typing_burst = True
            self._emit_unique(self._pick(POMODORO_FOCUS_REACTIONS),
                              emotion="CONFIDENT")

    # ------------------------------------------------------------------ helpers

    def _is_late_night(self) -> bool:
        h = datetime.now().hour
        return h >= LATE_NIGHT_START_HOUR or h < LATE_NIGHT_END_HOUR

    def _pick(self, options: list[str]) -> str:
        if not options:
            return ""
        return random.choice(options)

    def _emit_unique(self, text: str, emotion: str | None = None) -> None:
        """Emit bubble text + optional emotion, but skip if we've said it recently
        or if the pet is currently being dragged."""
        if not text:
            return
        now = _now_ms()
        if self._ctx.is_being_dragged:
            return
        if now < self._suppressed_until_ms:
            return
        if text in self._ctx.recent_reactions:
            return  # already said this — stay quiet
        self._ctx.recent_reactions.append(text)
        log.debug("Intelligence emits: text=%r emotion=%r", text, emotion)
        self.wants_reaction.emit(text)
        if emotion:
            self.wants_emotion.emit(emotion)

    def _suppressed(self, key: str, cooldown_ms: int) -> bool:
        return _now_ms() < self._throttle.get(key, 0)

    def _suppress(self, key: str, cooldown_ms: int) -> None:
        self._throttle[key] = _now_ms() + cooldown_ms

    # ------------------------------------------------------------------ status (for test/debug)

    @property
    def context(self) -> ContextState:
        return self._ctx

    def snapshot(self) -> dict:
        """Read-only diagnostic dump — used by tests / debugging."""
        return {
            "pomodoro_state":    self._ctx.pomodoro_state,
            "pomodoro_running":  self._ctx.pomodoro_running,
            "session_focus_min": self._ctx.session_focus_min,
            "typing_cpm":        self._ctx.typing_cpm,
            "typing_burst":      self._ctx.typing_burst,
            "overheat":          self._ctx.overheat,
            "mood":              self._ctx.mood,
            "energy":            round(self._ctx.energy, 3),
            "recent_reactions":  list(self._ctx.recent_reactions),
            "last_interaction_ms": self._ctx.last_interaction_ms,
            "is_late_night":     self._is_late_night(),
            "last_agent_status": self._ctx.last_agent_status,
        }
