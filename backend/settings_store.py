"""
settings_store.py — Application settings persistence for ShellMate.
Settings are stored in settings.json at the project root.

Also provides effective-config helpers — settings.json overrides .env values
for API keys, model URLs, and the Chroma DB URL.
"""
import json
from pathlib import Path

from backend import config as env_config

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
    # User-overridable API keys / endpoints. Empty string means "fall back
    # to whatever .env provides". Keys persisted here override .env.
    "providers": {
        "anthropic_api_key": "",
        "openai_api_key": "",
        "xai_api_key": "",
        "deepseek_api_key": "",
        "ollama_host": "",
        "chroma_url": "",
        "chroma_collection": "design_guidelines",
    },
    "ai": {
        # "learn" | "tshoot" — controls which system-prompt persona is used.
        "mode": "tshoot",
    },
}

# Which env-var name backs each provider field, for the "preconfigured by env"
# indicator the settings UI shows.
ENV_BACKED_FIELDS: dict = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "openai_api_key":    "OPENAI_API_KEY",
    "xai_api_key":       "XAI_API_KEY",
    "deepseek_api_key":  "DEEPSEEK_API_KEY",
    "ollama_host":       "OLLAMA_HOST",
    "chroma_url":        "CHROMA_URL",
    "chroma_collection": "CHROMA_COLLECTION",
}

SECRET_FIELDS = {
    "anthropic_api_key", "openai_api_key", "xai_api_key", "deepseek_api_key",
}


def get_settings() -> dict:
    """Return raw stored settings deep-merged over the defaults."""
    if not SETTINGS_FILE.exists():
        return _deep_merge(DEFAULT_SETTINGS, {})
    try:
        stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return _deep_merge(DEFAULT_SETTINGS, stored)
    except Exception:
        return _deep_merge(DEFAULT_SETTINGS, {})


def get_settings_for_ui() -> dict:
    """
    Return settings shaped for the frontend:
      - secret API keys are masked (replaced by 8 dots) but a flag tells the UI
        whether a value is actually set
      - includes an "env_preconfigured" map listing which provider fields have
        an env var backing them so the UI can render the placeholder text
    """
    s = get_settings()
    providers = dict(s.get("providers", {}))
    out_providers: dict = {}
    has_value: dict = {}
    for k, v in providers.items():
        if k in SECRET_FIELDS and v:
            out_providers[k] = "•" * 8
        else:
            out_providers[k] = v or ""
        has_value[k] = bool(v)

    env_preconfigured: dict = {}
    for field, env_name in ENV_BACKED_FIELDS.items():
        env_preconfigured[field] = bool(getattr(env_config, env_name, "") if hasattr(env_config, env_name) else "")
        # CHROMA_URL/CHROMA_COLLECTION read directly from os.getenv since they
        # weren't in config.py originally
        if field in ("chroma_url", "chroma_collection"):
            import os
            env_preconfigured[field] = bool(os.getenv(env_name, ""))

    s_out = dict(s)
    s_out["providers"] = out_providers
    s_out["providers_has_value"] = has_value
    s_out["env_preconfigured"] = env_preconfigured
    return s_out


def update_settings(partial: dict) -> dict:
    """
    Persist a partial settings update.

    Special handling for `providers` secret fields: a value of all dots (the
    masked placeholder the UI receives) means "leave unchanged" — only real
    edits get written.
    """
    current = get_settings()
    cleaned = _strip_masked_secrets(partial, current)
    merged = _deep_merge(current, cleaned)
    SETTINGS_FILE.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return get_settings_for_ui()


def get_effective(field: str, env_fallback: str = "") -> str:
    """Return the active value for a provider field — settings.json wins, .env fills in."""
    s = get_settings()
    val = (s.get("providers", {}) or {}).get(field, "") or ""
    return val or env_fallback


def _strip_masked_secrets(partial: dict, current: dict) -> dict:
    """If a secret field arrived as the masked placeholder, drop it."""
    if "providers" not in partial or not isinstance(partial["providers"], dict):
        return partial
    out = dict(partial)
    p = dict(partial["providers"])
    cur_p = current.get("providers", {}) or {}
    for k in list(p.keys()):
        if k in SECRET_FIELDS:
            v = p[k]
            # Pure-mask placeholder → keep existing value
            if isinstance(v, str) and v and set(v) <= {"•"}:
                p[k] = cur_p.get(k, "")
    out["providers"] = p
    return out


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
