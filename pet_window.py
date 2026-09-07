"""
pet_window.py — The transparent, frameless, always-on-top pet window with full Comnyang mechanics.

Features (Comnyang-inspired):
  • Eye Follow: Denji's eyes track the mouse cursor in real-time.
  • Keyboard Kneading: Typing triggers chainsaw revving & punching animations.
  • Overheat Mode: High typing speed (>480 CPM) turns Denji red with steam & sparks!
  • Mochi Drag & Squish: Dragging stretches Denji, releasing causes mochi spring-wobble!
  • Shake Wobble: Dragging the pet rapidly causes directional noise wobble.
  • Purring: Pet action spawns heart particles above the head.
  • Rapid Pet Shower: Multiple quick pets spawn a heart shower.
  • Stretch Grow: Stretch animation temporarily grows the pet taller.
  • Speech bubble reactions, interactive context menu, and fallback graphics.
"""

import math
import random
import logging

from PySide6.QtCore import Qt, QPoint, QRect, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QPainterPath, QPolygon, QCursor,
)
from PySide6.QtWidgets import QWidget, QMenu, QApplication, QLabel, QVBoxLayout

from theme import QMENU_STYLESHEET

log = logging.getLogger(__name__)

IDLE_REACTIONS = [
    "( •_•) Hey.",
    "(ง'̀-'́)ง Let's go!",
    "( ´◡‿ゝ◡`) Cool.",
    "Heh. Pretty good.",
    "Zzz… resting up.",
    "( ˘▾˘)~♪ Good vibes.",
    "Echo, echo, echo…",
    "I can still fight!",
    "The Bat is here.",
]

PET_REACTIONS = [
    "( ♡‿♡ ) Feels nice.",
    "*purrs quietly*",
    "Heh. Do that again.",
    "( ˘▾˘) Direct dopamine.",
]

REV_REACTIONS = [
    "SCREEEECH! 🦇",
    "BAT-SIGNAL ENGAGED! 🦇⚡",
    "MAX POWER!! 💥",
]

_DRAG_THRESHOLD = 4


class SpeechBubble(QWidget):
    """Free-floating speech bubble — auto-sizes and word-wraps so text never clips."""

    TAIL_HEIGHT = 10

    def __init__(self, text: str, anchor_x: int, anchor_y: int,
                 duration_ms: int = 3_500, overheat: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput   # clicks pass through
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._accent = QColor("#D32F2F") if overheat else QColor("#E94560")

        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            "QLabel { color: #f2f2f2; font-family: 'Segoe UI', Arial, sans-serif;"
            " font-size: 11px; font-weight: 600; padding: 8px 12px; }"
        )

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.setContentsMargins(12, 6, 12, self.TAIL_HEIGHT + 6)
        self.setMaximumWidth(280)
        self.adjustSize()

        # Position: centered above the anchor, clamped to the work area.
        screen = QApplication.primaryScreen().availableGeometry()
        x = max(screen.left(), min(anchor_x - self.width() // 2, screen.right() - self.width()))
        y = max(screen.top(), anchor_y - self.height() - 8)
        self.move(x, y)

        QTimer.singleShot(duration_ms, self.close)

    def paintEvent(self, event) -> None:
        """Dark rounded card + accent border + downward tail."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        th, r = self.TAIL_HEIGHT, 12

        shadow = QPainterPath()
        shadow.addRoundedRect(3, 3, w, h - th, r, r)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 70))
        painter.drawPath(shadow)

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h - th, r, r)
        cx = w // 2
        path.moveTo(cx - 8, h - th)
        path.lineTo(cx + 8, h - th)
        path.lineTo(cx, h)
        path.closeSubpath()

        painter.setBrush(QColor("#232637"))
        painter.setPen(QPen(self._accent, 1.5))
        painter.drawPath(path)


class PetWindow(QWidget):
    """
    Main desktop pet widget with Comnyang-style interactive capabilities.
    """

    quit_requested            = Signal()
    toggle_pomodoro_requested = Signal()
    settings_requested        = Signal()
    action_triggered          = Signal(str)
    clicked                   = Signal()           # any user click on the pet
    double_clicked            = Signal()
    long_pressed              = Signal()
    rapid_pet                 = Signal(int)        # count of consecutive clicks
    dragging_changed          = Signal(bool)       # drag start / release

    PET_SIZE = 128

    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_pixmap: QPixmap | None = None

        # Drag state
        self._drag_start_global = QPoint()
        self._drag_start_local  = QPoint()
        self._is_dragging       = False

        # Mochi Stretch / Squish state
        self._scale_x = 1.0
        self._scale_y = 1.0
        self._squish_velocity = 0.0
        self._squish_timer = QTimer(self)
        self._squish_timer.setInterval(20)
        self._squish_timer.timeout.connect(self._update_squish)

        # Shake wobble state (Comnyang-style drag shake)
        self._shake_x = 0
        self._shake_y = 0
        self._shake_timer = QTimer(self)
        self._shake_timer.setInterval(40)
        self._shake_timer.timeout.connect(self._update_shake)

        # Stretch-grow state (Comnyang style — pet grows taller during stretch)
        self._stretch_scale_y = 1.0
        self._stretch_timer = QTimer(self)
        self._stretch_timer.setInterval(40)
        self._stretch_timer.timeout.connect(self._update_stretch)

        # Purring state — heart particles
        self._purr_hearts: list[dict] = []
        self._purr_timer = QTimer(self)
        self._purr_timer.setInterval(80)
        self._purr_timer.timeout.connect(self._update_purr_hearts)

        # Eye Follow state
        self._eye_offset_x = 0
        self._eye_offset_y = 0

        # Overheat state
        self._is_overheating = False

        # Speech-bubble reaction state
        self._reaction_text: str | None = None
        self._reaction_timer = QTimer(self)
        self._reaction_timer.setSingleShot(True)
        self._reaction_timer.timeout.connect(self._clear_reaction)
        self._bubble: SpeechBubble | None = None

        # Animation effect state (bounce/shake)
        self._anim_offset_y = 0
        self._anim_offset_x = 0
        self._anim_step = 0
        self._anim_type: str | None = None
        self._effect_timer = QTimer(self)
        self._effect_timer.setInterval(30)
        self._effect_timer.timeout.connect(self._update_effect)

        self._setup_window()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)



        bubble_zone = 60
        self.setFixedSize(self.PET_SIZE + 40, self.PET_SIZE + bubble_zone + 10)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def set_pet_size(self, size_px: int) -> None:
        """Dynamically resize the pet window and sprite bounding box."""
        self.PET_SIZE = size_px
        bubble_zone = 60
        self.setFixedSize(self.PET_SIZE + 40, self.PET_SIZE + bubble_zone + 10)
        self.update()


    # ------------------------------------------------------------------ public slots

    def set_frame(self, pixmap: QPixmap) -> None:
        self._current_pixmap = pixmap.scaled(
            self.PET_SIZE, self.PET_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.update()

    def update_cursor_pos(self, global_x: int, global_y: int) -> None:
        """Eye Follow: compute eye offset based on cursor position relative to pet."""
        pet_center = self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2))
        dx = global_x - pet_center.x()
        dy = global_y - pet_center.y()
        angle = math.atan2(dy, dx)
        dist = min(5, int(math.hypot(dx, dy) / 100))

        self._eye_offset_x = int(math.cos(angle) * dist)
        self._eye_offset_y = int(math.sin(angle) * dist)
        self.update()

    def set_overheat(self, overheat: bool) -> None:
        """Overheat Mode: Fast typing causes steam & red rage!"""
        if self._is_overheating != overheat:
            self._is_overheating = overheat
            if overheat:
                self._reaction_text = "🔥 OVERHEAT! TYPING TOO FAST!"
                self._reaction_timer.start(4_000)
                self._show_bubble(self._reaction_text, 4_000)
                self._start_shake_effect()
            self.update()

    def trigger_typing_punch(self) -> None:
        """Keyboard Kneading: Keypress triggers quick punch / jitter."""
        if not self._effect_timer.isActive():
            self._anim_offset_y = random.choice([-2, 2])
            QTimer.singleShot(80, lambda: setattr(self, '_anim_offset_y', 0))
            self.update()

    def trigger_action(self, action: str) -> None:
        """Trigger interactive pet action."""
        if action == "pet":
            self._reaction_text = random.choice(PET_REACTIONS)
            self._start_bounce_effect()
            self._spawn_purr_heart(initial=True)
            self._purr_timer.start()
        elif action == "rev":
            self._reaction_text = random.choice(REV_REACTIONS)
            self._start_shake_effect()
        else:
            self._reaction_text = random.choice(IDLE_REACTIONS)

        self._reaction_timer.start(3_000)
        self._show_bubble(self._reaction_text, 3_000)
        self.action_triggered.emit(action)
        self.update()

    def trigger_long_press_rev(self) -> None:
        """Comnyang-style: holding the pet triggers a bat screech."""
        self.trigger_action("rev")

    def trigger_rapid_pet(self, count: int) -> None:
        """Comnyang-style: rapid petting spawns a shower of hearts."""
        self._reaction_text = random.choice(PET_REACTIONS)
        self._reaction_timer.start(2_500)
        self._show_bubble(self._reaction_text, 2_500)
        self._spawn_heart_shower(count)
        self.rapid_pet.emit(count)
        self._purr_timer.start()
        self.update()

    def start_shake_wobble(self, duration_ms: int = 1500) -> None:
        """Comnyang-style: fast drag → directional noise wobble."""
        self._shake_x = 0
        self._shake_y = 0
        self._shake_timer.start()
        QTimer.singleShot(duration_ms, self._shake_timer.stop)

    def start_stretch_grow(self, duration_ms: int = 3500) -> None:
        """Comnyang-style: pet stretches taller (vertical scale-up)."""
        self._stretch_scale_y = 1.0
        self._stretch_phase = 0   # 0=grow, 1=hold, 2=shrink
        self._stretch_timer.start()
        QTimer.singleShot(max(100, duration_ms - 800), lambda: setattr(self, '_stretch_phase', 2))


    def trigger_reaction(self, text: str) -> None:
        """PetAI-driven ambient reaction — show a speech bubble."""
        self._reaction_text = text
        self._reaction_timer.start(3_500)
        self._show_bubble(text, 3_500)
        self._start_bounce_effect()
        self.update()

    def _show_bubble(self, text: str, duration_ms: int = 3_500) -> None:
        """Show the speech bubble as a free-floating window (never clips text)."""
        if self._bubble is not None:
            try:
                self._bubble.close()
            except RuntimeError:
                pass  # previous bubble already deleted
        pos = self.pos()
        # The sprite is drawn 60px below the window's top edge (bubble zone),
        # so anchor the tail at the logo itself — not the window top.
        self._bubble = SpeechBubble(
            text,
            anchor_x=pos.x() + self.width() // 2,
            anchor_y=pos.y() + 60,
            duration_ms=duration_ms,
            overheat=self._is_overheating,
        )
        self._bubble.show()

    def drift_to(self, target: QPoint) -> None:
        """PetAI-driven wandering — smoothly slide toward target over ~3s."""
        if self._is_dragging:
            return
        start_pos = self.pos()
        dx = target.x() - start_pos.x()
        dy = target.y() - start_pos.y()
        if abs(dx) < 2 and abs(dy) < 2:
            return

        self._drift_anim = QPropertyAnimation(self, b"pos")
        self._drift_anim.setDuration(3000)
        self._drift_anim.setStartValue(start_pos)
        self._drift_anim.setEndValue(target)
        self._drift_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._drift_anim.start()

    def jump(self, height: int = 42) -> None:
        """Comnyang-style: hop the whole window up, then land with a little bounce.

        Used to celebrate when an AI coding agent finishes (agent-done jump).
        """
        if self._is_dragging:
            return
        start = self.pos()
        apex = QPoint(start.x(), start.y() - height)
        self._jump_anim = QPropertyAnimation(self, b"pos")
        self._jump_anim.setDuration(250)
        self._jump_anim.setStartValue(start)
        self._jump_anim.setEndValue(apex)
        self._jump_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._jump_anim.finished.connect(lambda: self._jump_land(start))
        self._jump_anim.start()

    def _jump_land(self, start: QPoint) -> None:
        """Second half of the jump: fall back to the start position with a bounce."""
        self._jump_land_anim = QPropertyAnimation(self, b"pos")
        self._jump_land_anim.setDuration(380)
        self._jump_land_anim.setStartValue(self.pos())
        self._jump_land_anim.setEndValue(start)
        self._jump_land_anim.setEasingCurve(QEasingCurve.Type.OutBounce)
        self._jump_land_anim.start()

    # ------------------------------------------------------------------ animation & mochi effects

    def _start_bounce_effect(self) -> None:
        self._anim_type = "bounce"
        self._anim_step = 0
        self._effect_timer.start()

    def _start_shake_effect(self) -> None:
        self._anim_type = "shake"
        self._anim_step = 0
        self._effect_timer.start()

    def _update_effect(self) -> None:
        self._anim_step += 1
        if self._anim_type == "bounce":
            if self._anim_step <= 15:
                self._anim_offset_y = int(-14 * math.sin((self._anim_step / 15) * math.pi))
            else:
                self._anim_offset_y = 0
                self._effect_timer.stop()
        elif self._anim_type == "shake":
            if self._anim_step <= 20:
                self._anim_offset_x = random.randint(-6, 6)
                self._anim_offset_y = random.randint(-3, 3)
            else:
                self._anim_offset_x = 0
                self._anim_offset_y = 0
                self._effect_timer.stop()
        self.update()

    def _update_squish(self) -> None:
        """Mochi spring-wobble animation after drag release."""
        force = (1.0 - self._scale_y) * 0.3
        self._squish_velocity += force
        self._squish_velocity *= 0.75  # damping
        self._scale_y += self._squish_velocity
        self._scale_x = 2.0 - self._scale_y

        if abs(self._scale_y - 1.0) < 0.01 and abs(self._squish_velocity) < 0.01:
            self._scale_x = 1.0
            self._scale_y = 1.0
            self._squish_timer.stop()
        self.update()

    def _update_shake(self) -> None:
        """Shake wobble — directional noise while dragging."""
        self._shake_x = random.randint(-4, 4)
        self._shake_y = random.randint(-3, 3)
        self.update()

    def _update_stretch(self) -> None:
        """Stretch grow — smoothly scale the pet taller, hold, then settle."""
        # Phase machine: grow (0-800ms), hold (800-2400ms), shrink back (2400-end)
        if not hasattr(self, '_stretch_phase'):
            self._stretch_phase = 0

        if self._stretch_phase == 0:
            self._stretch_scale_y += 0.03
            if self._stretch_scale_y >= 1.35:
                self._stretch_scale_y = 1.35
                self._stretch_phase = 1
        elif self._stretch_phase == 2:
            self._stretch_scale_y -= 0.03
            if self._stretch_scale_y <= 1.0:
                self._stretch_scale_y = 1.0
                self._stretch_timer.stop()
        self.update()


    def _spawn_purr_heart(self, initial: bool = False) -> None:
        """Spawn one heart particle above the head (purring)."""
        self._purr_hearts.append({
            "x": self.width() // 2 + random.randint(-8, 8),
            "y": 40,
            "vy": -0.6 if initial else -0.4,
            "life": 30,
            "size": random.randint(3, 5),
            "color": random.choice(["#FF6B6B", "#E91E63", "#FF8A80"]),
        })

    def _spawn_heart_shower(self, count: int) -> None:
        """Rapid-petting heart shower."""
        for _ in range(min(count, 6)):
            self._spawn_purr_heart(initial=False)

    def _update_purr_hearts(self) -> None:
        """Tick heart particles upward, fade them out."""
        if not self._purr_hearts:
            self._purr_timer.stop()
            self.update()
            return
        new_hearts = []
        for h in self._purr_hearts:
            h["y"] += h["vy"]
            h["vy"] -= 0.05     # float up faster over time
            h["life"] -= 1
            if h["life"] > 0 and h["y"] > 0:
                new_hearts.append(h)
        self._purr_hearts = new_hearts
        # Spawn a fresh heart every few ticks while purring
        if random.random() < 0.7:
            self._spawn_purr_heart(initial=False)
        self.update()

    # ------------------------------------------------------------------ painting

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Apply shake wobble offset (Comnyang-style)
        shake_dx = self._shake_x if self._shake_timer.isActive() else 0
        shake_dy = self._shake_y if self._shake_timer.isActive() else 0
        if shake_dx or shake_dy:
            painter.translate(shake_dx, shake_dy)

        sprite_top = 60 + self._anim_offset_y
        cx = self.width() // 2 + self._anim_offset_x

        # Apply Mochi Stretch + Stretch-Grow scaling
        effective_scale_x = self._scale_x
        effective_scale_y = self._scale_y
        if self._stretch_timer.isActive():
            # Grow taller — composite with squish
            effective_scale_y = self._scale_y * self._stretch_scale_y
        if effective_scale_x != 1.0 or effective_scale_y != 1.0:
            painter.translate(cx, sprite_top + self.PET_SIZE // 2)
            painter.scale(effective_scale_x, effective_scale_y)
            painter.translate(-cx, -(sprite_top + self.PET_SIZE // 2))

        # Overheat Red Glow / Steam Effect
        if self._is_overheating:
            painter.setBrush(QColor(255, 50, 50, 40))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(cx - 50, sprite_top - 10, 100, 100)
            # Steam puff
            for _ in range(2):
                sx = cx + random.randint(-20, 20)
                sy = sprite_top - random.randint(10, 30)
                painter.setBrush(QColor(255, 255, 255, 180))
                painter.drawEllipse(sx, sy, random.randint(6, 12), random.randint(6, 12))

        # Draw sprite or fallback
        if self._current_pixmap and not self._current_pixmap.isNull():
            x = cx - self._current_pixmap.width() // 2
            painter.drawPixmap(x, sprite_top, self._current_pixmap)
        else:
            self._paint_fallback(painter, cx, sprite_top)

        # 3. Draw purr-heart particles (above pet, outside the scaled region)
        if self._purr_hearts:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.setPen(Qt.PenStyle.NoPen)
            for h in self._purr_hearts:
                # Use a per-heart color; alpha decays with life
                alpha = max(40, min(255, h["life"] * 8))
                col = QColor(h["color"])
                col.setAlpha(alpha)
                painter.setBrush(col)
                size = h["size"]
                cx_h = h["x"]
                cy_h = int(h["y"])
                # Tiny heart shape — 2 circles + triangle
                painter.drawEllipse(cx_h - size // 2,     cy_h - size // 2, size // 2, size // 2)
                painter.drawEllipse(cx_h,                 cy_h - size // 2, size // 2, size // 2)
                pts = [
                    QPoint(cx_h - size // 2, cy_h),
                    QPoint(cx_h + size // 2, cy_h),
                    QPoint(cx_h,             cy_h + size),
                ]
                painter.drawPolygon(QPolygon(pts))

    def _paint_fallback(self, painter: QPainter, cx: int, sprite_top: int) -> None:
        r = self.PET_SIZE // 2 - 6
        body_color = QColor("#FF3D00") if self._is_overheating else QColor("#FF6F00")
        painter.setBrush(body_color)
        painter.setPen(QPen(QColor("#111111"), 2))
        painter.drawEllipse(cx - r, sprite_top + 4, r * 2, r * 2)

        # Eye Follow dynamic pupils!
        eye_y = sprite_top + 4 + r - 18
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(cx - 14 - 5, eye_y - 5, 10, 10)
        painter.drawEllipse(cx + 14 - 5, eye_y - 5, 10, 10)

        # Pupils look toward cursor
        painter.setBrush(QColor("#111111"))
        painter.drawEllipse(cx - 14 - 2 + self._eye_offset_x, eye_y - 2 + self._eye_offset_y, 4, 4)
        painter.drawEllipse(cx + 14 - 2 + self._eye_offset_x, eye_y - 2 + self._eye_offset_y, 4, 4)

        # Smile
        painter.setPen(QPen(QColor("#111111"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        smile_rect = QRect(cx - 14, sprite_top + 4 + r - 2, 28, 18)
        painter.drawArc(smile_rect, 0, -180 * 16)

    # ------------------------------------------------------------------ mouse & drag events

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_local  = event.position().toPoint()
            self._is_dragging       = False
            # Mochi stretch while dragging
            self._scale_x = 0.85
            self._scale_y = 1.2
            self.update()
            # Tell ClickDetector a press started (for long-press detection)
            if hasattr(self, '_click_detector') and self._click_detector is not None:
                self._click_detector.on_press()

        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        delta = event.globalPosition().toPoint() - self._drag_start_global
        if not self._is_dragging and delta.manhattanLength() >= _DRAG_THRESHOLD:
            self._is_dragging = True
            self.dragging_changed.emit(True)
            # Comnyang-style shake wobble on fast drag — start it as soon as we drag
            self.start_shake_wobble()

        if self._is_dragging:
            new_pos = event.globalPosition().toPoint() - self._drag_start_local
            screen = QApplication.primaryScreen().availableGeometry()
            new_pos.setX(max(screen.left(), min(new_pos.x(), screen.right()  - self.width())))
            new_pos.setY(max(screen.top(),  min(new_pos.y(), screen.bottom() - self.height())))
            self.move(new_pos)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging_changed.emit(False)
            # Stop shake wobble on release
            self._shake_timer.stop()
            self._shake_x = 0
            self._shake_y = 0
            # Trigger Mochi spring-wobble on release
            self._squish_velocity = 0.4
            self._squish_timer.start()

            if not self._is_dragging:
                # No drag → this was a click; let ClickDetector decide
                if hasattr(self, '_click_detector') and self._click_detector is not None:
                    self._click_detector.on_release(was_dragging=False)
                else:
                    self.trigger_action("idle")
                    self.clicked.emit()

    # ------------------------------------------------------------------ context menu

    def _show_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(QMENU_STYLESHEET)

        pet_act   = menu.addAction("🖐️  Pat the Bat")
        rev_act   = menu.addAction("🦇  Screech!")

        menu.addSeparator()

        pomo_act  = menu.addAction("▶/⏸  Start/Pause Pomodoro")
        cfg_act   = menu.addAction("⚙  Settings…")

        menu.addSeparator()
        quit_act  = menu.addAction("✕  Quit DenjiPet")

        selected = menu.exec(global_pos)

        if selected == pet_act:
            self.trigger_action("pet")
        elif selected == rev_act:
            self.trigger_action("rev")
        elif selected == pomo_act:
            self.toggle_pomodoro_requested.emit()
        elif selected == cfg_act:
            self.settings_requested.emit()
        elif selected == quit_act:
            self.quit_requested.emit()

    def _clear_reaction(self) -> None:
        self._reaction_text = None
        if self._bubble is not None:
            try:
                self._bubble.close()
            except RuntimeError:
                pass  # bubble already deleted
            self._bubble = None
        self.update()

    # ------------------------------------------------------------------ click detector

    def attach_click_detector(self, detector) -> None:
        """
        Plug in a ClickDetector so the pet can distinguish between single /
        double / long-press / rapid-pets. Wired up by main.py after both
        objects exist.
        """
        self._click_detector = detector
        # Connect detector signals to pet slots + own signals
        detector.single_clicked.connect(lambda _c: self.clicked.emit())
        detector.double_clicked.connect(self._on_double_click)
        detector.long_pressed.connect(self._on_long_press)
        detector.rapid_pet.connect(self.trigger_rapid_pet)

    def _on_double_click(self) -> None:
        """Two quick clicks → pet action + heart."""
        self.trigger_action("pet")
        self.double_clicked.emit()

    def _on_long_press(self) -> None:
        """Holding the pet without moving → bat screech."""
        self.trigger_long_press_rev()
        self.long_pressed.emit()
