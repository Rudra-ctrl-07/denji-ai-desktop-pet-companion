"""
input_listener.py — Global input listener for Comnyang-style interactive features.

Monitors:
  - Global mouse position (for Eye Follow)
  - Global typing activity (for Keyboard Kneading & Overheat Mode)
  - Global scroll events (for Scroll Reaction)
"""

import time
import threading
import logging
from PySide6.QtCore import QObject, Signal, QTimer
from pynput import mouse, keyboard

log = logging.getLogger(__name__)

class InputListener(QObject):
    """
    Global input tracker using pynput.

    Signals:
        mouse_moved(int, int)       — (cursor_x, cursor_y)
        typing_event(int)           — keys typed in last second (CPM)
        overheat_triggered(bool)    — True when typing speed > threshold
        scroll_event(int)           — scroll delta
    """

    mouse_moved        = Signal(int, int)
    typing_event       = Signal(int)
    overheat_triggered = Signal(bool)
    scroll_event       = Signal(int)

    OVERHEAT_THRESHOLD_CPS = 8.0   # >8 keys/sec (480 CPM) triggers Overheat!

    def __init__(self, parent=None):
        super().__init__(parent)

        self._last_mouse_pos = (0, 0)
        self._last_mouse_time = time.time()

        self._key_timestamps: list[float] = []
        self._is_overheating = False
        self._lock = threading.Lock()

        # Periodic timer (10 Hz) to compute rates and emit signals smoothly
        self._calc_timer = QTimer(self)
        self._calc_timer.setInterval(100)
        self._calc_timer.timeout.connect(self._evaluate_rates)

        self._mouse_listener: mouse.Listener | None = None
        self._keyboard_listener: keyboard.Listener | None = None

    def start(self) -> None:
        """Start global background listeners."""
        try:
            self._mouse_listener = mouse.Listener(
                on_move=self._on_mouse_move,
                on_scroll=self._on_mouse_scroll
            )
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press
            )
            self._mouse_listener.start()
            self._keyboard_listener.start()
            self._calc_timer.start()
            log.info("Global input listener started (mouse & keyboard tracking active).")
        except Exception as exc:
            log.error("Failed to start global input listener: %s", exc)

    def stop(self) -> None:
        """Stop global listeners."""
        self._calc_timer.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        log.info("Global input listener stopped.")

    # ------------------------------------------------------------------ callbacks

    def _on_mouse_move(self, x: int, y: int) -> None:
        now = time.time()
        dt = now - self._last_mouse_time
        if dt > 0.05:  # sample at max 20Hz
            self._last_mouse_pos = (x, y)
            self._last_mouse_time = now

            self.mouse_moved.emit(x, y)

    def _on_mouse_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        self.scroll_event.emit(dy)

    def _on_key_press(self, key) -> None:
        with self._lock:
            self._key_timestamps.append(time.time())

    def _evaluate_rates(self) -> None:
        now = time.time()
        with self._lock:
            # Keep key presses from last 1.5 seconds
            self._key_timestamps = [t for t in self._key_timestamps if now - t <= 1.5]
            count = len(self._key_timestamps)

        # Keys per second calculation
        cps = count / 1.5 if count else 0.0
        self.typing_event.emit(int(cps * 60))  # Emit CPM

        overheat = cps >= self.OVERHEAT_THRESHOLD_CPS
        if overheat != self._is_overheating:
            self._is_overheating = overheat
            self.overheat_triggered.emit(overheat)
            if overheat:
                log.info("🔥 OVERHEAT MODE TRIGGERED! (Typing speed: %.1f keys/sec)", cps)

