"""
profiles.py — Connection profile persistence for ShellMate.
Profiles are saved to profiles/saved.json (no passwords ever stored).
"""
import json
import uuid
from pathlib import Path

PROFILES_FILE = Path(__file__).parent.parent / "profiles" / "saved.json"


def _load() -> list[dict]:
    if not PROFILES_FILE.exists():
        return []
    try:
        return json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(profiles: list[dict]) -> None:
    PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_FILE.write_text(json.dumps(profiles, indent=2), encoding="utf-8")


def get_profiles() -> list[dict]:
    return _load()


def save_profile(name: str, hostname: str, port: int, username: str, connection_type: str) -> dict:
    profiles = _load()
    profile = {
        "id": str(uuid.uuid4()),
        "name": name or hostname,
        "hostname": hostname,
        "port": port,
        "username": username,
        "connection_type": connection_type,
    }
    profiles.append(profile)
    _save(profiles)
    return profile


def delete_profile(profile_id: str) -> bool:
    profiles = _load()
    new_profiles = [p for p in profiles if p.get("id") != profile_id]
    if len(new_profiles) == len(profiles):
        return False
    _save(new_profiles)
    return True
