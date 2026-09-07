"""
settings_dialog.py — Modal settings dialog for DenjiPet.

Provides controls for:
  • Pomodoro durations (work / break / long break)
  • Health nudge intervals (generic + water + stretch)
  • User name (for personalised reminders)
  • Display (Pomodoro HUD, pet size, always-on-top)
  • Sound pack toggle
  • AI agent hook toggle

Changes are saved to disk and emitted via settings_applied so live
components can update without a restart.
"""

import logging
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QPushButton, QGroupBox, QFormLayout, QFrame,
    QCheckBox, QLineEdit, QComboBox,
)

log = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """
    Modal settings dialog.

    Signals:
        settings_applied(dict): Emitted on Save.
            Keys: work, break, long_break, nudge, water, stretch,
                  user_name, pomodoro_hud, sound_enabled, agent_hooks,
                  pet_size, always_on_top.
    """

    settings_applied = Signal(dict)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings

        self.setWindowTitle("DenjiPet — Settings")
        self.setMinimumWidth(420)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._build_ui()
        self._apply_stylesheet()

    # ------------------------------------------------------------------ build UI

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(24, 24, 24, 20)

        # Header
        title = QLabel("⚙️  Settings")
        title.setObjectName("dlgTitle")
        root.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("separator")
        root.addWidget(sep)

        # ---- Pomodoro ----
        pomo_group = QGroupBox("Pomodoro Durations")
        pomo_form  = QFormLayout(pomo_group)
        pomo_form.setSpacing(8)
        self._work_spin       = self._spin(1, 120, self._settings.work_duration_min)
        self._break_spin      = self._spin(1,  60, self._settings.break_duration_min)
        self._long_break_spin = self._spin(1, 120, self._settings.long_break_duration_min)
        pomo_form.addRow("Work session:",           self._work_spin)
        pomo_form.addRow("Short break:",            self._break_spin)
        pomo_form.addRow("Long break (every 4th):", self._long_break_spin)
        root.addWidget(pomo_group)

        # ---- Nudges ----
        nudge_group = QGroupBox("Health Nudges")
        nudge_form  = QFormLayout(nudge_group)
        nudge_form.setSpacing(8)
        self._nudge_spin   = self._spin(1, 120, self._settings.nudge_interval_min)
        self._water_spin   = self._spin(15, 240, self._settings.water_interval_min)
        self._stretch_spin = self._spin(15, 180, self._settings.stretch_interval_min)
        nudge_form.addRow("Generic nudge every:", self._nudge_spin)
        nudge_form.addRow("Drink water every:",   self._water_spin)
        nudge_form.addRow("Stretch every:",       self._stretch_spin)
        root.addWidget(nudge_group)

        # ---- Identity ----
        id_group = QGroupBox("Identity (Comnyang's name-speaking)")
        id_form  = QFormLayout(id_group)
        id_form.setSpacing(8)
        self._name_edit = QLineEdit(self._settings.user_name)
        self._name_edit.setPlaceholderText("Leave empty to disable")
        self._name_edit.setMaxLength(40)
        id_form.addRow("Your name:", self._name_edit)
        root.addWidget(id_group)

        # ---- Display ----
        disp_group = QGroupBox("Display")
        disp_form  = QFormLayout(disp_group)
        disp_form.setSpacing(8)

        self._hud_chk = QCheckBox("Show floating Pomodoro timer HUD")
        self._hud_chk.setChecked(self._settings.pomodoro_hud)

        self._aot_chk = QCheckBox("Always on top")
        self._aot_chk.setChecked(self._settings.always_on_top)

        self._size_combo = QComboBox()
        self._size_combo.addItems(["Small (96px)", "Medium (128px)", "Large (192px)"])
        # Map current value → index
        size_idx = {96: 0, 128: 1, 192: 2}.get(self._settings.pet_size, 1)
        self._size_combo.setCurrentIndex(size_idx)

        disp_form.addRow(self._hud_chk)
        disp_form.addRow(self._aot_chk)
        disp_form.addRow("Pet size:", self._size_combo)
        root.addWidget(disp_group)

        # ---- Features ----
        feat_group = QGroupBox("Features")
        feat_form  = QFormLayout(feat_group)
        feat_form.setSpacing(8)

        self._sound_chk = QCheckBox("Sound effects (Windows system sounds)")
        self._sound_chk.setChecked(self._settings.sound_enabled)
        feat_form.addRow(self._sound_chk)

        self._agent_chk = QCheckBox("React to AI coding agents (Claude Code, Cursor)")
        self._agent_chk.setChecked(self._settings.agent_hooks_enabled)
        feat_form.addRow(self._agent_chk)

        root.addWidget(feat_group)

        # ---- Buttons ----
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("cancelBtn")
        self._save_btn   = QPushButton("Save && Apply")
        self._save_btn.setObjectName("saveBtn")
        self._save_btn.setDefault(True)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._save_btn)
        root.addLayout(btn_row)

        self._cancel_btn.clicked.connect(self.reject)
        self._save_btn.clicked.connect(self._on_save)

    @staticmethod
    def _spin(min_v: int, max_v: int, value: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(min_v, max_v)
        s.setValue(value)
        s.setSuffix(" min")
        s.setFixedWidth(100)
        return s

    # ------------------------------------------------------------------ slots

    def _on_save(self) -> None:
        size_map = {0: 96, 1: 128, 2: 192}
        pet_size = size_map.get(self._size_combo.currentIndex(), 128)

        data = {
            "work":         self._work_spin.value(),
            "break":        self._break_spin.value(),
            "long_break":   self._long_break_spin.value(),
            "nudge":        self._nudge_spin.value(),
            "water":        self._water_spin.value(),
            "stretch":      self._stretch_spin.value(),
            "user_name":    self._name_edit.text().strip(),
            "pomodoro_hud": self._hud_chk.isChecked(),
            "always_on_top": self._aot_chk.isChecked(),
            "sound_enabled": self._sound_chk.isChecked(),
            "agent_hooks":   self._agent_chk.isChecked(),
            "pet_size":     pet_size,
        }

        # Persist to disk
        self._settings.work_duration_min        = data["work"]
        self._settings.break_duration_min       = data["break"]
        self._settings.long_break_duration_min  = data["long_break"]
        self._settings.nudge_interval_min       = data["nudge"]
        self._settings.water_interval_min       = data["water"]
        self._settings.stretch_interval_min     = data["stretch"]
        self._settings.user_name                = data["user_name"]
        self._settings.pomodoro_hud             = data["pomodoro_hud"]
        self._settings.always_on_top            = data["always_on_top"]
        self._settings.sound_enabled            = data["sound_enabled"]
        self._settings.agent_hooks_enabled      = data["agent_hooks"]
        self._settings.pet_size                 = data["pet_size"]
        self._settings.save()

        self.settings_applied.emit(data)
        log.info("Settings saved: %s", data)
        self.accept()

    # ------------------------------------------------------------------ style

    def _apply_stylesheet(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background: #1a1a2e;
                color: #eaeaea;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel#dlgTitle {
                font-size: 18px;
                font-weight: 700;
                color: #e94560;
            }
            QFrame#separator {
                border: none;
                border-top: 1px solid #2d2d44;
                margin: 2px 0;
            }
            QGroupBox {
                color: #a0a0c0;
                font-size: 12px;
                font-weight: 600;
                border: 1px solid #2d2d44;
                border-radius: 8px;
                margin-top: 10px;
                padding: 14px 10px 10px 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QLabel {
                color: #c0c0d8;
                font-size: 13px;
            }
            QLineEdit, QSpinBox, QComboBox {
                background: #0f3460;
                color: #eaeaea;
                border: 1px solid #2d2d44;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 13px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border-color: #e94560;
            }
            QCheckBox {
                color: #c0c0d8;
                font-size: 13px;
                padding: 4px 0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #2d2d44;
                background: #0f3460;
            }
            QCheckBox::indicator:checked {
                background: #e94560;
                border-color: #e94560;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                background: #16213e;
                border: none;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #e94560;
            }
            QPushButton#saveBtn {
                background: #e94560;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 22px;
                font-size: 13px;
                font-weight: 600;
                min-width: 110px;
            }
            QPushButton#saveBtn:hover   { background: #c73652; }
            QPushButton#saveBtn:pressed { background: #a82d43; }
            QPushButton#cancelBtn {
                background: #2d2d44;
                color: #a0a0c0;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton#cancelBtn:hover { background: #3d3d5c; color: #eaeaea; }
        """)