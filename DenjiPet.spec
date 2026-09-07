# DenjiPet.spec — PyInstaller packaging specification
#
# Build command (from the project root):
#   pyinstaller DenjiPet.spec
#
# Output:
#   dist/DenjiPet.exe   — standalone executable, no Python install required
#
# Notes:
#   • console=False removes the black terminal window on launch.
#   • The assets/ folder is bundled — it holds only the custom pet sprite (assets/custom/).
#   • All Comnyang-parity modules are auto-picked via hiddenimports to be safe.
#   • Add icon='assets/icon.ico' to the EXE() call to set a custom tray icon.

import sys
from pathlib import Path

block_cipher = None

# All DenjiPet modules — explicit list so PyInstaller never misses one
DENJI_MODULES = [
    'main',
    'settings',
    'animation_controller',
    'pomodoro_engine',
    'pet_window',
    'tray_menu',
    'nudge_manager',
    'settings_dialog',
    'input_listener',
    'pet_ai',
    'hydration_reminder',
    'stretch_reminder',
    'periodic_reminder',
    'agent_hook',
    'pomodoro_hud',
    'sticky_notes',
    'sound_pack',
    'click_detector',
    'name_speech',
    'intelligence',
    'theme',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include the custom pet sprite (assets/custom/pet.png + source SVG).
        ('assets', 'assets'),
    ],
    hiddenimports=[
        # PySide6
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
        # Project modules (defensive — Analysis auto-detects from main.py imports)
        *DENJI_MODULES,
        # vendor modules
        'plyer.platforms.win.notification',
        'logging.handlers',
        'pynput.mouse._win32',
        'pynput.keyboard._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Don't bundle test/lint packages to reduce size
        'pytest', 'pytest_asyncio', 'unittest', 'pydoc_data',
        'matplotlib', 'numpy.tests', 'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DenjiPet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # uncomment when an .ico exists
)
