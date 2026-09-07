"""
pet_ai.py — Autonomous intelligence layer for the pet.

The pet has its own life between user interactions:

  • Wandering — drifts around the screen smoothly on its own (idle state only).
  • Random reactions — periodically pops a speech-bubble comment.
  • LLM reactions — uses local Ollama (qwen2.5:0.5b) for intelligent responses.
  • Mood state — a hidden "energy" level that drives sprite selection.
  • Time-of-day — reacts to morning / afternoon / evening / night.
  • Personality — biases reaction selection toward a personality vector
                  (currently "playful" — can be extended later).

The pet will never do anything destructive; all behaviors are non-blocking
and stop instantly when the user grabs / drags the pet.
"""

import random
import logging
import threading
import urllib.request
import json
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, QPoint, Signal
from PySide6.QtWidgets import QApplication

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fallback reaction pool — used when Ollama is offline
# ---------------------------------------------------------------------------
AMBIENT_REACTIONS: list[str] = [
    "*sniff sniff* ...something smells good.",
    "*leans back*",
    "The bat wonders what you're up to.",
    "*yawns*",
    "☀️ Nice weather today.",
    "🌙 Getting late...",
    "💭 Thinking about bread.",
    "*stretches arms*",
    "Heh. Cool.",
    "*looks around curiously*",
    "Bat thoughts.",
    "🍞 ...do you have any food?",
    "*blinks slowly*",
    "✨ Decent moment.",
    "*bounces a little*",
    "🤔 Hmm.",
    "*tilts head*",
]

TIME_GREETINGS = {
    "morning":   ["☀️ Morning.", "Rise & shine!", "Breakfast time?"],
    "afternoon": ["☕ Afternoon vibes.", "Halfway through the day."],
    "evening":   ["🌅 Evening chill.", "Almost dinner time..."],
    "night":     ["🌙 Getting sleepy.", "*yawns* late night thoughts."],
}

# ---------------------------------------------------------------------------
# Contextual reactions consumed by intelligence.py
# ---------------------------------------------------------------------------
POMODORO_FOCUS_REACTIONS = [
    "🦇 Type harder!", "💪 Big brain energy.", "🔥 On fire!",
    "Yeah, yeah, focus...", "Pretend I'm working too.",
    "*sniff* smelled productivity...",
]
POMODORO_BREAK_REACTIONS = [
    "☕ Break time!", "Stretch! Stand up!", "👀 Look out a window.",
    "*splashes water on face in solidarity*",
    "🧘 Touch your toes for me.",
]
POMODORO_TIRED_REACTIONS = [
    "🥱 You've been grinding...", "💤 Take a break soon.",
    "🏋️ Big brain... tired brain...", "I can still fight! (can you?)",
]
LATE_NIGHT_REACTIONS = [
    "🌙 Late night thoughts.", "🌙 Go sleep.", "🦉 We are owls now.",
    "*yawns* Even a bat needs rest.",
]
GRUMPY_REACTIONS = [
    "Hmph.", "Whatever.", "🤨 Did you forget me?",
    "*glares at productivity*", "🐈 ...rude.",
]
CURIOUS_REACTIONS = [
    "💭 What are you up to?", "👀 Looking mysterious over there.",
    "Hmm...?", "*tilts head*",
]
JOY_REACTIONS = [
    "( ♡‿♡ ) So nice!", "Heh, do that again!",
    "✨ Don't stop!", "*purrs*",
]
AGENT_REACTION_BUBBLES = {
    "working": "🪚 Your AI is working — go rest!",
    "waiting": "👀 AI is waiting on input.",
    "done":    "🎉 Agent says: finished!",
    "error":   "😬 AI hit an error — check log.",
}


# ---------------------------------------------------------------------------
# Ollama integration — tiny local LLM for intelligent reactions
# ---------------------------------------------------------------------------
OLLAMA_URL    = "http://localhost:11434/api/generate"
OLLAMA_MODEL  = "qwen2.5:0.5b"
# ponytail: single global lock — per-request queuing if concurrency matters
_ollama_lock  = threading.Lock()

SYSTEM_PROMPT = (
    "You are a tiny desktop pet — a Batman stress ball with a big personality. "
    "You are curious, playful, and occasionally dramatic. "
    "When asked to react, respond with ONE short sentence (max 8 words), "
    "in-character. No quotes. No explanation. Just the reaction."
)


def _ask_ollama(context: str, fallback: list[str]) -> str:
    """
    Call Ollama synchronously (run this in a thread).
    Returns a short pet reaction string, or a random fallback on failure.
    """
    if not _ollama_lock.acquire(blocking=False):
        return random.choice(fallback)  # already busy
    try:
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": f"{SYSTEM_PROMPT}\n\nContext: {context}\nReact:",
            "stream": False,
            "options": {"num_predict": 20, "temperature": 0.9},
        }).encode()
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read())
            text = data.get("response", "").strip()
            # Truncate to reasonable bubble length
            if len(text) > 60:
                text = text[:57] + "…"
            return text or random.choice(fallback)
    except Exception as exc:
        log.debug("Ollama unavailable: %s", exc)
        return random.choice(fallback)
    finally:
        _ollama_lock.release()


def _time_bucket() -> str:
    h = datetime.now().hour
    if 5  <= h < 12: return "morning"
    if 12 <= h < 17: return "afternoon"
    if 17 <= h < 21: return "evening"
    return "night"


# ---------------------------------------------------------------------------
# PetAI
# ---------------------------------------------------------------------------

class PetAI(QObject):
    """
    Autonomous intelligence layer for the desktop pet.

    Signals:
        wants_reaction(str)    — pet wants to say something in a speech bubble
        wants_move_to(QPoint)  — pet wants to drift to a new screen position
        wants_emotion(str)     — pet wants to switch emotion sprite
    """

    wants_reaction = Signal(str)
    wants_move_to  = Signal(QPoint)
    wants_emotion  = Signal(str)

    # Tunables
    REACTION_MIN_MS = 18_000
    REACTION_MAX_MS = 45_000
    WANDER_MIN_MS   = 30_000
    WANDER_MAX_MS   = 90_000
    EMOTION_MIN_MS  = 60_000
    EMOTION_MAX_MS  = 180_000

    def __init__(self, pet_window, parent=None):
        super().__init__(parent)
        self._pet     = pet_window
        self._enabled = True
        self._energy  = 0.7
        self._mood    = "playful"
        self._use_llm = True   # flip to False to disable Ollama

        self._reaction_timer = QTimer(self)
        self._reaction_timer.setSingleShot(True)
        self._reaction_timer.timeout.connect(self._ambient_reaction)

        self._wander_timer = QTimer(self)
        self._wander_timer.setSingleShot(True)
        self._wander_timer.timeout.connect(self._wander)

        self._emotion_timer = QTimer(self)
        self._emotion_timer.setSingleShot(True)
        self._emotion_timer.timeout.connect(self._emotion_event)

        self._tick = QTimer(self)
        self._tick.setInterval(60_000)
        self._tick.timeout.connect(self._update_mood)

    # ------------------------------------------------------------------ public

    def start(self) -> None:
        self._schedule_reaction()
        self._schedule_wander()
        self._schedule_emotion()
        self._tick.start()
        QTimer.singleShot(2_000, self._launch_greeting)
        log.info("PetAI started (LLM=%s, model=%s).", self._use_llm, OLLAMA_MODEL)

    def stop(self) -> None:
        self._reaction_timer.stop()
        self._wander_timer.stop()
        self._emotion_timer.stop()
        self._tick.stop()

    def pause(self) -> None:
        self._reaction_timer.stop()
        self._wander_timer.stop()
        self._emotion_timer.stop()

    def resume(self) -> None:
        self._schedule_reaction()
        self._schedule_wander()
        self._schedule_emotion()

    # ------------------------------------------------------------------ private

    def _schedule_reaction(self) -> None:
        self._reaction_timer.start(random.randint(self.REACTION_MIN_MS, self.REACTION_MAX_MS))

    def _schedule_wander(self) -> None:
        self._wander_timer.start(random.randint(self.WANDER_MIN_MS, self.WANDER_MAX_MS))

    def _schedule_emotion(self) -> None:
        self._emotion_timer.start(random.randint(self.EMOTION_MIN_MS, self.EMOTION_MAX_MS))

    def _emotion_event(self) -> None:
        names   = ["LOVE", "CURIOUS", "SLEEPY", "DIZZY", "SAD", "ANGRY"]
        weights = [1.0,    1.2,       1.0,      0.6,     0.5,   0.5   ]
        self.wants_emotion.emit(random.choices(names, weights=weights, k=1)[0])
        self._schedule_emotion()

    def _ambient_reaction(self) -> None:
        if not self._enabled:
            return
        self._schedule_reaction()
        if self._use_llm:
            bucket  = _time_bucket()
            context = (
                f"Time of day: {bucket}. "
                f"Pet energy: {'high' if self._energy > 0.6 else 'low'}. "
                f"Mood: {self._mood}."
            )
            threading.Thread(
                target=self._llm_react,
                args=(context,),
                daemon=True,
            ).start()
        else:
            self.wants_reaction.emit(random.choice(AMBIENT_REACTIONS))

    def _llm_react(self, context: str) -> None:
        """Run in background thread; emit signal back on completion."""
        line = _ask_ollama(context, AMBIENT_REACTIONS)
        self.wants_reaction.emit(line)  # Signal is thread-safe in PySide6

    def _wander(self) -> None:
        try:
            screen = QApplication.primaryScreen().availableGeometry()
            cur    = self._pet.pos()
            dx = random.randint(-180, 180)
            dy = random.randint(-120, 120)
            nx = max(screen.left(), min(cur.x() + dx, screen.right()  - self._pet.width()))
            ny = max(screen.top(),  min(cur.y() + dy, screen.bottom() - self._pet.height()))
            self.wants_move_to.emit(QPoint(nx, ny))
        except Exception as exc:
            log.debug("Wander aborted: %s", exc)
        finally:
            self._schedule_wander()

    def _update_mood(self) -> None:
        self._energy += (0.5 - self._energy) * 0.1
        self._energy += random.uniform(-0.05, 0.05)
        self._energy = max(0.0, min(1.0, self._energy))

    def _launch_greeting(self) -> None:
        if self._use_llm:
            bucket = _time_bucket()
            threading.Thread(
                target=self._llm_react,
                args=(f"Just woke up. Time: {bucket}. Say a short hello.",),
                daemon=True,
            ).start()
        else:
            self.wants_reaction.emit(random.choice(TIME_GREETINGS[_time_bucket()]))