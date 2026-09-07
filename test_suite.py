"""
test_suite.py — Runnable unit test suite for DenjiPet core subsystems.
"""

import json
import os
import sys
import tempfile
import time
from unittest import mock

# Initialize QApplication for PySide6 Qt components test (covers QWidgets)
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from settings import Settings
from pomodoro_engine import PomodoroEngine
from animation_controller import AnimationController
from click_detector import ClickDetector
from name_speech import NameSpeech
from agent_hook import AgentHook
from pet_ai import _ask_ollama, AMBIENT_REACTIONS


def test_settings():
    print("[1/8] Testing Settings subsystem...")
    s = Settings()
    # main() redirects %APPDATA% to a throwaway dir — config must stay there.
    assert str(s._path).startswith(os.environ["APPDATA"]), \
        f"Config path escapes temp dir: {s._path}"
    assert s.work_duration_min == 25, f"Expected 25, got {s.work_duration_min}"
    s.user_name = "TestUser"
    assert s.user_name == "TestUser"
    s.save()

    # Reload from disk
    s2 = Settings()
    assert s2.user_name == "TestUser"
    print("  [OK] Settings test PASSED")


def test_pomodoro_engine():
    print("[2/8] Testing PomodoroEngine state machine...")
    engine = PomodoroEngine(work_min=1, break_min=1, long_break_min=1)
    assert engine.state == "IDLE"
    
    engine.start()
    assert engine.state == "WORKING"
    assert engine.is_running is True
    
    # Force tick countdown to 0
    engine._remaining_sec = 0
    engine._on_tick()
    assert engine.state == "BREAK"
    assert engine.sessions_completed == 1
    
    engine.reset()
    assert engine.state == "IDLE"
    assert engine.sessions_completed == 0
    print("  [OK] PomodoroEngine test PASSED")


def test_animation_controller():
    print("[3/8] Testing AnimationController...")
    anim = AnimationController(fps=10)
    anim.set_state("IDLE")
    assert anim.has_frames is True
    
    anim.set_emotion("LOVE", duration_ms=100)
    assert anim._emotion_timer is not None
    assert anim._emotion_timer.isActive() is True
    
    # Interrupt emotion with set_state
    anim.set_state("WORKING")
    assert anim._emotion_timer.isActive() is False
    print("  [OK] AnimationController test PASSED")


def test_click_detector():
    print("[4/8] Testing ClickDetector timing logic...")
    detector = ClickDetector()
    events = []
    detector.single_clicked.connect(lambda n: events.append(("single", n)))
    detector.double_clicked.connect(lambda: events.append(("double", 2)))
    detector.rapid_pet.connect(lambda count: events.append(("rapid", count)))
    detector.long_pressed.connect(lambda: events.append(("long", 1)))

    # Test single click
    detector.on_press()
    detector.on_release(was_dragging=False)
    assert len(events) == 1 and events[0] == ("single", 1)

    # Test dragging suppression
    events.clear()
    detector.on_press()
    detector.on_release(was_dragging=True)
    assert len(events) == 0

    # Test rapid pet — 3 quick clicks must beat the pending double
    events.clear()
    for _ in range(3):
        detector.on_press()
        detector.on_release(was_dragging=False)
    assert ("rapid", 3) in events, f"rapid pet missing: {events}"

    # Test double click — 2 clicks with no 3rd → double fires after the gap
    events.clear()
    detector2 = ClickDetector()
    detector2.double_clicked.connect(lambda: events.append(("double", 2)))
    detector2.on_press()
    detector2.on_release(was_dragging=False)
    detector2.on_press()
    detector2.on_release(was_dragging=False)
    time.sleep(0.45)
    app.processEvents()
    assert ("double", 2) in events, f"double click missing: {events}"
    print("  [OK] ClickDetector test PASSED")


def test_name_speech():
    print("[5/8] Testing NameSpeech personalization...")
    class MockSettings:
        def get(self, key, default=""):
            return "DenjiFan" if key == "user_name" else default

    speaker = NameSpeech(MockSettings())
    msg = speaker.personalize("Drink water!")
    assert msg == "Hey, DenjiFan — Drink water!", f"Got: {msg}"
    print("  [OK] NameSpeech test PASSED")


def test_agent_hook():
    print("[6/8] Testing AgentHook status file watcher...")
    class MockSettings:
        def get(self, key, default=False):
            return True

    hook = AgentHook(MockSettings())
    emotions = []
    hook.reaction.connect(emotions.append)
    
    hook.write_status("test_agent", "working", "sess1")
    hook._poll()
    assert len(emotions) == 1 and emotions[0] == "WORKING"
    print("  [OK] AgentHook test PASSED")


def test_pet_ai_ollama():
    print("[7/8] Testing PetAI Ollama integration & fallback (mocked)...")

    class _FakeResp:
        """Minimal context-manager stand-in for urllib's HTTPResponse."""
        def __init__(self, payload: bytes):
            self._payload = payload
        def read(self) -> bytes:
            return self._payload
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False

    # Success path — canned Ollama response, no real network call.
    canned = json.dumps({"response": "Tested! Ready for more!"}).encode()
    with mock.patch("urllib.request.urlopen", return_value=_FakeResp(canned)):
        res = _ask_ollama("Test prompt", AMBIENT_REACTIONS)
    assert res == "Tested! Ready for more!", f"Got: {res!r}"

    # Failure path — Ollama unreachable → must fall back to a local message.
    with mock.patch("urllib.request.urlopen", side_effect=OSError("ollama offline")):
        res = _ask_ollama("Test prompt", AMBIENT_REACTIONS)
    assert res in AMBIENT_REACTIONS, f"Got: {res!r}"

    print("  [OK] PetAI Ollama test PASSED")


def test_pet_window_jump():
    print("[8/8] Testing PetWindow agent-done jump...")
    from PySide6.QtCore import QEventLoop, QTimer
    from pet_window import PetWindow

    pet = PetWindow()
    pet.set_pet_size(128)
    pet.move(200, 400)
    pet.show()

    start = pet.pos()
    pet.jump(height=42)

    # Pump the event loop so the hop-up + land animations run to completion.
    loop = QEventLoop()
    QTimer.singleShot(900, loop.quit)
    loop.exec()
    end = pet.pos()
    pet.close()

    assert abs(end.y() - start.y()) <= 1, \
        f"Jump did not land back at start: start y={start.y()}, end y={end.y()}"
    print("  [OK] PetWindow jump test PASSED")


def main():
    print("==========================================")
    print("  DenjiPet Automated Test Suite")
    print("==========================================")

    # Redirect %APPDATA% to a throwaway dir so Settings, AgentHook, etc.
    # never read or write the user's real config. The temp dir is removed
    # automatically when the block exits.
    original_appdata = os.environ.get("APPDATA")
    with tempfile.TemporaryDirectory(prefix="denjipet_test_") as tmp:
        os.environ["APPDATA"] = tmp
        try:
            test_settings()
            test_pomodoro_engine()
            test_animation_controller()
            test_click_detector()
            test_name_speech()
            test_agent_hook()
            test_pet_ai_ollama()
            test_pet_window_jump()
        finally:
            if original_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = original_appdata

    print("==========================================")
    print("  ALL 8 TEST SUITES PASSED CLEANLY!")
    print("==========================================")


if __name__ == "__main__":
    main()
