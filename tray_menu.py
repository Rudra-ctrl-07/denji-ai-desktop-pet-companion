"""
tray_menu.py — System-tray icon and right-click context menu (FR-06).

The tray icon:
  • Left-click  → toggles Start / Pause of the Pomodoro engine.
  • Right-click → opens a context menu with Pomodoro & Pet actions.

The fallback tray icon is generated programmatically (an orange/red circle with ears) when
no image file is available, so the app always shows something recognizable.
"""

import logging
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import QSystemTrayIcon, QMenu

from theme import QMENU_STYLESHEET

log = logging.getLogger(__name__)


def _make_fallback_icon(size: int = 32) -> QIcon:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#FF6F00"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)

    painter.setBrush(QColor("#111111"))
    painter.drawEllipse(10, 12, 4, 4)
    painter.drawEllipse(18, 12, 4, 4)
    painter.end()

    return QIcon(px)


class TrayMenu(QSystemTrayIcon):
    """
    System-tray icon with Pomodoro & Pet controls.

    Signals:
        start_pause_requested  — user wants to start or pause the timer
        reset_requested        — user wants to reset to IDLE
        settings_requested     — user wants to open the Settings dialog
        action_requested(str)  — user triggered a pet action ("pet", "rev")
        new_sticky_requested   — user wants a new sticky note
        quit_requested         — user wants to exit the application
    """

    start_pause_requested = Signal()
    reset_requested       = Signal()
    settings_requested    = Signal()
    action_requested      = Signal(str)
    new_sticky_requested  = Signal()
    toggle_sound_requested   = Signal()
    toggle_hud_requested     = Signal()
    change_size_requested    = Signal(int)   # new pixel size
    quit_requested        = Signal()

    def __init__(self, icon_path: str | None = None, settings=None, parent=None):
        icon = QIcon(icon_path) if icon_path else _make_fallback_icon()
        super().__init__(icon, parent)

        self._settings = settings
        self._is_running = False
        self._sound_on  = bool(settings.sound_enabled) if settings else False
        self._hud_on    = bool(settings.pomodoro_hud) if settings else True
        self._pet_size  = int(settings.pet_size) if settings else 128

        self._build_menu()
        self.setToolTip("DenjiPet — The Bat")
        self.activated.connect(self._on_activated)

    def _build_menu(self) -> None:
        menu = QMenu()
        menu.setStyleSheet(QMENU_STYLESHEET)

        # Interactive Actions
        self._pet_act  = menu.addAction("🖐️  Pat the Bat")
        self._rev_act  = menu.addAction("🦇  Screech!")

        menu.addSeparator()

        # Pomodoro
        self._start_pause_act = menu.addAction("▶  Start Pomodoro")
        self._reset_act       = menu.addAction("↺  Reset")

        menu.addSeparator()

        # Comnyang-parity quick toggles
        self._sticky_act   = menu.addAction("📌  New Sticky Note")
        self._hud_act      = menu.addAction("⏱️  Show Timer HUD")
        self._sound_act    = menu.addAction("🔊  Sound: Off")
        self._size_menu    = menu.addMenu("📏  Pet Size")
        self._size_small   = self._size_menu.addAction("Small (96px)")
        self._size_medium  = self._size_menu.addAction("Medium (128px)")
        self._size_large   = self._size_menu.addAction("Large (192px)")

        menu.addSeparator()

        self._settings_act = menu.addAction("⚙  Settings…")

        menu.addSeparator()
        self._quit_act     = menu.addAction("✕  Quit")

        self.setContextMenu(menu)

        self._pet_act.triggered.connect(lambda: self.action_requested.emit("pet"))
        self._rev_act.triggered.connect(lambda: self.action_requested.emit("rev"))

        self._start_pause_act.triggered.connect(self.start_pause_requested)
        self._reset_act.triggered.connect(self.reset_requested)
        self._settings_act.triggered.connect(self.settings_requested)
        self._quit_act.triggered.connect(self.quit_requested)

        self._sticky_act.triggered.connect(self.new_sticky_requested)
        self._hud_act.triggered.connect(self.toggle_hud_requested)
        self._sound_act.triggered.connect(self.toggle_sound_requested)
        self._size_small.triggered.connect(lambda: self.change_size_requested.emit(96))
        self._size_medium.triggered.connect(lambda: self.change_size_requested.emit(128))
        self._size_large.triggered.connect(lambda: self.change_size_requested.emit(192))

        self._refresh_toggle_labels()

    # ------------------------------------------------------------------ public

    def update_state(self, state: str, is_running: bool) -> None:
        self._is_running = is_running

        if state == "IDLE":
            btn_label = "▶  Start Pomodoro"
        elif is_running:
            btn_label = "⏸  Pause"
        else:
            btn_label = "▶  Resume"

        self._start_pause_act.setText(btn_label)

        state_display = {
            "IDLE":       "Idle",
            "WORKING":    "🔥 Working",
            "BREAK":      "☕ Break",
            "LONG_BREAK": "😴 Long Break",
            "CELEBRATE":  "🎉 Done",
        }.get(state, state)
        self.setToolTip(f"DenjiPet — {state_display}")

    def refresh_from_settings(self) -> None:
        """Re-read toggles from settings and update menu labels."""
        if self._settings is not None:
            self._sound_on = bool(self._settings.sound_enabled)
            self._hud_on   = bool(self._settings.pomodoro_hud)
            self._pet_size = int(self._settings.pet_size)
        self._refresh_toggle_labels()

    # ------------------------------------------------------------------ private

    def _refresh_toggle_labels(self) -> None:
        self._hud_act.setText(
            "⏱️  Hide Timer HUD" if self._hud_on else "⏱️  Show Timer HUD"
        )
        self._sound_act.setText(
            f"🔊  Sound: {'On' if self._sound_on else 'Off'}"
        )

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.start_pause_requested.emit()