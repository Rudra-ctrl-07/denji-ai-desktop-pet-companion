"""
pomodoro_hud.py — Floating pixel-art Pomodoro timer HUD above the pet.

Comnyang-style: a small MM:SS countdown shown in chunky pixel font above
the pet's head, visible only when the Pomodoro engine is running.

The HUD is:
  • frameless, transparent background
  • drawn entirely with QPainter (no font dependency)
  • auto-positioned above the pet
  • auto-hidden when Pomodoro state is IDLE
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pixel digit bitmaps (5×7 each)
# ---------------------------------------------------------------------------
_DIGITS: dict[str, list[str]] = {
    "0": [
        " XXX ",
        "X   X",
        "X  XX",
        "X X X",
        "XX  X",
        "X   X",
        " XXX ",
    ],
    "1": [
        "  X  ",
        " XX  ",
        "X X  ",
        "  X  ",
        "  X  ",
        "  X  ",
        "XXXXX",
    ],
    "2": [
        " XXX ",
        "X   X",
        "    X",
        "  XX ",
        " X   ",
        "X    ",
        "XXXXX",
    ],
    "3": [
        " XXX ",
        "X   X",
        "    X",
        "  XX ",
        "    X",
        "X   X",
        " XXX ",
    ],
    "4": [
        "X   X",
        "X   X",
        "X   X",
        "XXXXX",
        "    X",
        "    X",
        "    X",
    ],
    "5": [
        "XXXXX",
        "X    ",
        "XXXX ",
        "    X",
        "    X",
        "X   X",
        " XXX ",
    ],
    "6": [
        " XXX ",
        "X    ",
        "X    ",
        "XXXX ",
        "X   X",
        "X   X",
        " XXX ",
    ],
    "7": [
        "XXXXX",
        "    X",
        "   X ",
        "  X  ",
        " X   ",
        " X   ",
        " X   ",
    ],
    "8": [
        " XXX ",
        "X   X",
        "X   X",
        " XXX ",
        "X   X",
        "X   X",
        " XXX ",
    ],
    "9": [
        " XXX ",
        "X   X",
        "X   X",
        " XXXX",
        "    X",
        "    X",
        " XXX ",
    ],
    ":": [
        "     ",
        "  X  ",
        "  X  ",
        "     ",
        "  X  ",
        "  X  ",
        "     ",
    ],
    "M": [
        "X   X",
        "XX XX",
        "X X X",
        "X   X",
        "X   X",
        "X   X",
        "X   X",
    ],
    "S": [
        " XXX ",
        "X   X",
        "X    ",
        " XXX ",
        "    X",
        "X   X",
        " XXX ",
    ],
}

DIGIT_W = 5
DIGIT_H = 7


def _draw_pixel_text(painter: QPainter, text: str, x: int, y: int,
                     pixel_size: int = 2, color: str = "#FFFFFF") -> int:
    """
    Draws `text` using pixel bitmaps. Returns the width consumed in pixels.
    """
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    cx = x
    for ch in text:
        glyph = _DIGITS.get(ch.upper())
        if glyph is None:
            continue
        for row, line in enumerate(glyph):
            for col, c in enumerate(line):
                if c == "X":
                    painter.drawRect(
                        cx + col * pixel_size,
                        y + row * pixel_size,
                        pixel_size, pixel_size,
                    )
        cx += (DIGIT_W + 1) * pixel_size
    return cx - x


# ---------------------------------------------------------------------------
# PomodoroHUD widget
# ---------------------------------------------------------------------------


class PomodoroHUD(QWidget):
    """Small pixel-art timer shown above the pet."""

    WIDTH  = 110
    HEIGHT = 32
    PAD    = 4

    def __init__(self, pet_window, parent=None):
        super().__init__(None)
        self._pet_window = pet_window
        self._remaining_sec = 0
        self._total_sec     = 0
        self._state         = "IDLE"
        self._enabled       = True

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.hide()

    # ------------------------------------------------------------------ public

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled:
            self.hide()

    def is_enabled(self) -> bool:
        return self._enabled

    def update_time(self, remaining_sec: int, total_sec: int) -> None:
        self._remaining_sec = remaining_sec
        self._total_sec     = total_sec
        self._refresh()

    def update_state(self, state: str, is_running: bool) -> None:
        self._state = state
        if not self._enabled or state == "IDLE":
            self.hide()
            return
        self._refresh()
        self.show()

    # ------------------------------------------------------------------ private

    def _refresh(self) -> None:
        # Reposition above the pet
        if self._pet_window is not None:
            px = self._pet_window.x()
            py = self._pet_window.y()
            self.move(px + (self._pet_window.width() - self.WIDTH) // 2, py - self.HEIGHT - 4)
        # Trigger repaint
        self.update()

    def paintEvent(self, event):
        if not self._enabled or self._state == "IDLE":
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Background pill
        painter.setBrush(QColor(26, 26, 46, 220))
        painter.setPen(QPen(QColor("#E94560"), 1.5))
        painter.drawRoundedRect(0, 0, self.WIDTH, self.HEIGHT, 6, 6)

        # Format MM:SS
        minutes = max(0, self._remaining_sec) // 60
        seconds = max(0, self._remaining_sec) % 60
        time_str = f"{minutes:02d}:{seconds:02d}"

        # Choose color by state
        if self._state == "WORKING":
            color = "#FF6F6F"
        elif self._state == "BREAK":
            color = "#7BE495"
        elif self._state == "LONG_BREAK":
            color = "#80D8FF"
        else:
            color = "#FFFFFF"

        # Draw MM:SS in pixel font
        px = self.PAD + 4
        py = (self.HEIGHT - DIGIT_H * 2) // 2 + 1
        _draw_pixel_text(painter, time_str, px, py, pixel_size=2, color=color)

        # Mini "M" / "S" suffix
        suffix = "M" if self._state in ("WORKING", "LONG_BREAK") else "S"
        _draw_pixel_text(painter, suffix, px + len(time_str) * 12 + 4, py + 4,
                         pixel_size=1, color="#E0E0E0")