"""
theme.py — Shared UI stylesheet constants.

The dark palette used by menus across the app. Keep menu styling in one
place so the look stays consistent and tweaks land in a single file.
"""

# Standard dark-theme context menu (pet right-click menu + tray menu)
QMENU_STYLESHEET = """
    QMenu {
        background: #1a1a2e;
        color: #eaeaea;
        border: 1px solid #2d2d44;
        border-radius: 6px;
        padding: 4px;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 13px;
    }
    QMenu::item          { padding: 7px 20px; border-radius: 4px; }
    QMenu::item:selected { background: #e94560; }
    QMenu::separator     { height: 1px; background: #2d2d44; margin: 4px 8px; }
"""

# Compact variant used on small widgets (sticky-note menus)
QMENU_STYLESHEET_SMALL = """
    QMenu {
        background: #1a1a2e;
        color: #eaeaea;
        border: 1px solid #2d2d44;
        padding: 4px;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 12px;
    }
    QMenu::item          { padding: 6px 18px; border-radius: 4px; }
    QMenu::item:selected { background: #e94560; }
"""
