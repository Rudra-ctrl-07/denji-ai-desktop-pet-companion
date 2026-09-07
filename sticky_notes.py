"""
sticky_note.py — Single yellow sticky-note widget.

sticky_notes.py — Manager that floats up to 3 notes above the pet, persists
them as JSON in the config dir, and exposes signals for tray UI.
"""

import json
import logging
import os
import time
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QObject, Signal, QPoint, QEvent
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QPainterPath, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QInputDialog, QMenu,
)

from theme import QMENU_STYLESHEET_SMALL

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# StickyNote widget
# ---------------------------------------------------------------------------


class StickyNote(QWidget):
    """A single yellow pixel-styled sticky note (frameless, draggable)."""

    NOTE_W = 140
    NOTE_H = 110

    dismissed = Signal(str)  # note_id

    def __init__(self, note_id: str, text: str, parent=None):
        super().__init__(parent)
        self.note_id = note_id
        self.text    = text.strip()
        self._drag_pos: QPoint | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.NOTE_W, self.NOTE_H)

    # ------------------------------------------------------------------ mouse

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            menu = QMenu(self)
            menu.setStyleSheet(QMENU_STYLESHEET_SMALL)
            act_dismiss = menu.addAction("✕  Dismiss")
            chosen = menu.exec(event.globalPosition().toPoint())
            if chosen == act_dismiss:
                self.dismissed.emit(self.note_id)
                self.close()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ------------------------------------------------------------------ paint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(2, 2, w - 4, h - 4, 6, 6)
        painter.setPen(QPen(QColor("#D4A000"), 1.5))
        painter.setBrush(QColor("#FFF59D"))
        painter.drawPath(path)

        # Curl shadow
        painter.setBrush(QColor(0, 0, 0, 30))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, h - 3, w, 3)

        # Text
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        painter.setPen(QColor("#1A1A1A"))
        fm = QFontMetrics(font)
        # Word-wrap text within note width minus padding
        pad = 10
        wrapped_lines = self._wrap(self.text, fm, w - pad * 2)
        y = 14 + fm.ascent()
        for line in wrapped_lines:
            painter.drawText(pad, y, line)
            y += fm.lineSpacing()
            if y > h - 8:
                break

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _wrap(text: str, fm: QFontMetrics, max_w: int) -> list[str]:
        out: list[str] = []
        for para in text.split("\n"):
            line = ""
            for word in para.split(" "):
                candidate = (line + " " + word).strip()
                if fm.horizontalAdvance(candidate) <= max_w:
                    line = candidate
                else:
                    if line:
                        out.append(line)
                    line = word
            out.append(line)
        return out


# ---------------------------------------------------------------------------
# StickyNotesManager
# ---------------------------------------------------------------------------


def _notes_path() -> Path:
    base = Path(os.environ.get("APPDATA", ".")) / "DenjiPet"
    base.mkdir(parents=True, exist_ok=True)
    return base / "sticky_notes.json"


class StickyNotesManager(QObject):
    """
    Owns up to MAX_VISIBLE StickyNote widgets floating above the pet.

    Signals:
        updated(int)    — emitted when count changes (for tray menu)
    """

    MAX_VISIBLE = 3
    MAX_STORED  = 10   # keep at most 10 in JSON storage

    updated = Signal(int)

    def __init__(self, settings, pet_window, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._pet_window = pet_window
        self._active: dict[str, StickyNote] = {}

        self._load_from_disk()

        # Reposition visible notes whenever pet moves
        if pet_window is not None:
            pet_window.installEventFilter(self)

    # ------------------------------------------------------------------ public

    def count(self) -> int:
        return len(self._active)

    def add_note(self, text: str | None = None) -> str | None:
        """Prompt for text (or use supplied), create + show note."""
        if text is None:
            text, ok = QInputDialog.getText(
                None,
                "New Sticky Note",
                "Note text:",
            )
            if not ok or not text.strip():
                return None

        note_id = str(uuid.uuid4())[:8]
        # Persist
        self._persist_add(note_id, text.strip())

        # Hide oldest if we exceed MAX_VISIBLE
        if len(self._active) >= self.MAX_VISIBLE:
            oldest_id = next(iter(self._active))
            self._active[oldest_id].close()
            del self._active[oldest_id]

        note = StickyNote(note_id, text.strip())
        note.dismissed.connect(self._on_dismissed)
        self._active[note_id] = note
        self._reposition_all()
        note.show()
        self.updated.emit(self.count())
        return note_id

    # ------------------------------------------------------------------ private

    def _on_dismissed(self, note_id: str) -> None:
        if note_id in self._active:
            del self._active[note_id]
            self._persist_remove(note_id)
            self._reposition_all()
            self.updated.emit(self.count())

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched == self._pet_window and event.type() == QEvent.Type.Move:
            self._reposition_all()
        return super().eventFilter(watched, event)

    def _reposition_all(self) -> None:
        if self._pet_window is None:
            return
        pet_x = self._pet_window.x()
        pet_y = self._pet_window.y()
        # Stack notes vertically above the pet (with gap)
        for i, note in enumerate(self._active.values()):
            note_x = pet_x - StickyNote.NOTE_W - 8
            note_y = pet_y - (i + 1) * (StickyNote.NOTE_H + 6) - 20
            note.move(note_x, note_y)

    # ------------------------------------------------------------------ persistence

    def _load_from_disk(self) -> None:
        path = _notes_path()
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            log.warning("Failed to load sticky notes: %s", exc)
            return

        notes = data.get("notes", [])
        for entry in notes[-self.MAX_VISIBLE:]:
            note_id = entry.get("id")
            text    = entry.get("text", "")
            if not note_id or not text:
                continue
            note = StickyNote(note_id, text)
            note.dismissed.connect(self._on_dismissed)
            self._active[note_id] = note
            note.show()

    def _persist_add(self, note_id: str, text: str) -> None:
        path = _notes_path()
        data: dict = {"notes": []}
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {"notes": []}
        data["notes"].append({
            "id":         note_id,
            "text":       text,
            "created_at": int(time.time()),
        })
        data["notes"] = data["notes"][-self.MAX_STORED:]
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            log.warning("Failed to persist sticky note: %s", exc)

    def _persist_remove(self, note_id: str) -> None:
        path = _notes_path()
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["notes"] = [n for n in data.get("notes", []) if n.get("id") != note_id]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as exc:
            log.warning("Failed to remove sticky note from disk: %s", exc)