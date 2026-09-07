"""
nudge_manager.py — Periodic health-reminder popups (FR-07, FR-08).

A QTimer fires every `interval_min` minutes and displays a NudgeBubble —
a small, frameless speech-bubble widget anchored near the pet window.
The bubble auto-dismisses after ~5 seconds without any user interaction.
"""

import random
import logging

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication

log = logging.getLogger(__name__)

# ---- Health nudge messages ------------------------------------------------
NUDGES: list[str] = [
    "💧 Drink some water!",
    "🧘 Stretch your back and shoulders.",
    "👁️ Look 20 ft away for 20 seconds.",
    "🌬️ Take a few slow, deep breaths.",
    "🚶 Stand up and walk around briefly.",
    "😌 Relax your jaw — you're clenching it.",
    "🍎 Had a snack? Fuel your brain.",
    "💤 Blink properly — your eyes are dry.",
    "🙆 Roll your shoulders back.",
    "☀️ Get some natural light if you can.",
]


# ---------------------------------------------------------------------------
# NudgeBubble
# ---------------------------------------------------------------------------

class NudgeBubble(QWidget):
    """
    A frameless, non-interactive speech-bubble popup.

    Floats above and to the left of the pet window, auto-closes after
    `duration_ms` milliseconds.
    """

    BUBBLE_WIDTH  = 230
    TAIL_HEIGHT   = 12   # pixels for the triangle pointing downward

    def __init__(self, message: str, anchor_x: int, anchor_y: int,
                 duration_ms: int = 5_000):
        # No parent → independent top-level window
        super().__init__(None)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput   # clicks pass through
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Label holds the nudge text.
        label = QLabel(message, self)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                color: #f2f2f2;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                font-weight: 600;
                padding: 10px 14px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        # Extra bottom margin leaves room for the painted tail.
        layout.setContentsMargins(14, 8, 14, self.TAIL_HEIGHT + 8)
        self.setFixedWidth(self.BUBBLE_WIDTH)
        self.adjustSize()

        # Position: above and slightly to the left of the pet.
        screen = QApplication.primaryScreen().availableGeometry()
        x = max(screen.left(), min(anchor_x - 20, screen.right() - self.width()))
        y = max(screen.top(),  anchor_y - self.height() - 10)
        self.move(x, y)

        # Auto-dismiss
        QTimer.singleShot(duration_ms, self.close)

    def paintEvent(self, event):
        """
        Paints a dark rounded card with a downward-pointing tail, a soft drop
        shadow, and an accent border — matching the pet's speech bubble.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w  = self.width()
        h  = self.height()
        th = self.TAIL_HEIGHT
        r  = 14   # corner radius

        # Drop shadow
        shadow = QPainterPath()
        shadow.addRoundedRect(3, 3, w, h - th, r, r)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 60))
        painter.drawPath(shadow)

        # Bubble body + tail as a single path so the fill is seamless.
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h - th, r, r)

        cx = w // 2
        path.moveTo(cx - 10, h - th)
        path.lineTo(cx + 10, h - th)
        path.lineTo(cx,      h)
        path.closeSubpath()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#232637"))
        painter.drawPath(path)

        # Border
        painter.setPen(QPen(QColor("#e94560"), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


# ---------------------------------------------------------------------------
# NudgeManager
# ---------------------------------------------------------------------------

class NudgeManager(QObject):
    """
    Owns the nudge QTimer and creates NudgeBubble instances on each fire.

    Usage:
        mgr = NudgeManager(pet_window=pet, interval_min=20)
        mgr.start()
    """

    def __init__(self, pet_window: QWidget, interval_min: int = 20, parent=None):
        super().__init__(parent)
        self._pet_window  = pet_window
        self._interval_ms = interval_min * 60 * 1_000

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._fire)

    # ------------------------------------------------------------------ public

    def start(self) -> None:
        self._timer.start(self._interval_ms)
        log.info("NudgeManager started — interval %d min", self._interval_ms // 60_000)

    def stop(self) -> None:
        self._timer.stop()
        log.debug("NudgeManager stopped.")

    def set_interval_min(self, minutes: int) -> None:
        """Update interval; restarts the timer if already running."""
        self._interval_ms = minutes * 60 * 1_000
        if self._timer.isActive():
            self._timer.setInterval(self._interval_ms)
        log.info("Nudge interval updated to %d min", minutes)

    def fire_now(self) -> None:
        """Trigger a nudge immediately (handy for testing from Settings dialog)."""
        self._fire()

    # ------------------------------------------------------------------ private

    def _fire(self) -> None:
        msg = random.choice(NUDGES)
        pos = self._pet_window.pos()
        log.info("Nudge: %s", msg)
        bubble = NudgeBubble(msg, anchor_x=pos.x(), anchor_y=pos.y())
        bubble.show()
