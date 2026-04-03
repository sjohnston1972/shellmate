"""
settings_store.py — Application settings persistence for MATE.
Settings are stored in settings.json at the project root.
"""
import json
from pathlib import Path

SETTINGS_FILE = Path(__file__).parent.parent / "settings.json"

DEFAULT_SETTINGS: dict = {
    "terminal": {
        "font_family": "JetBrains Mono, Fira Code, Consolas, monospace",
        "font_size": 14,
        "line_height": 1.2,
        "cursor_style": "block",
        "cursor_blink": True,
        "scrollback_lines": 5000,
        "right_click_paste": True,
        "copy_on_select": False,
    },
    "logging": {
        "enabled": False,
        "directory": "logs",
    },
    "appearance": {
        "color_scheme": "deep_space",
    },
}


def get_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        # Deep merge stored over defaults so new keys always have a value
        merged = _deep_merge(DEFAULT_SETTINGS, stored)
        return merged
    except Exception:
        return DEFAULT_SETTINGS.copy()


def update_settings(partial: dict) -> dict:
    current = get_settings()
    merged = _deep_merge(current, partial)
    SETTINGS_FILE.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
