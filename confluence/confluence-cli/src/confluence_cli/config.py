"""Profile config file IO for the `confluence` skill.

Two config layers:

- **Project config** (`.confluence.json`, walked upward from cwd).
  Pins a profile, site, space key, and parent defaults to a project.

- **User config** (per-platform path; see :func:`user_config_dir`).
  Personal profiles with site/email/spaceKey and the token slot
  (`token` literal, `tokenEnv` env-var name, or `tokenRef` keyring
  reference).

Neither file is required: env vars and explicit flags still work.

The token slot may hold a literal API token. The CLI never asks the
AI agent to type one — instead, ``confluence auth init`` writes a
placeholder string and the human user opens the file in their editor
to paste the real token. See ``confluence/references/auth.md``.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_CONFIG_FILENAME = ".confluence.json"

#: Literal value written into the ``token`` field by ``auth init``.
#: Resolution refuses to use this string as a real token.
TOKEN_PLACEHOLDER = "<your-token-here>"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ProfileEntry:
    """One profile row.

    The token slot can be filled in one of three mutually exclusive
    ways, in order of preference for resolution:

    - ``token``: a literal API token written by the user into the
      config file (after ``auth init`` left a placeholder there).
      Plaintext on disk; protected by file permissions only.
    - ``token_env``: a named environment variable to read at runtime.
      The variable's value is the token. Use this for CI.
    - ``token_ref``: a ``keyring:<service>/<account>`` reference into
      the OS keyring. Set up manually by power users.
    """

    name: str
    site: str | None = None
    email: str | None = None
    space_key: str | None = None
    parent_id: str | None = None
    token: str | None = None
    token_env: str | None = None
    token_ref: str | None = None

    def to_json(self) -> dict:
        out: dict = {}
        if self.site:
            out["site"] = self.site
        if self.email:
            out["email"] = self.email
        if self.space_key:
            out["spaceKey"] = self.space_key
        if self.parent_id:
            out["parentId"] = self.parent_id
        if self.token is not None:
            out["token"] = self.token
        if self.token_env:
            out["tokenEnv"] = self.token_env
        if self.token_ref:
            out["tokenRef"] = self.token_ref
        return out

    @classmethod
    def from_json(cls, name: str, data: dict) -> ProfileEntry:
        return cls(
            name=name,
            site=(str(data["site"]) if data.get("site") else None),
            email=(str(data["email"]) if data.get("email") else None),
            space_key=(str(data["spaceKey"]) if data.get("spaceKey") else None),
            parent_id=(str(data["parentId"]) if data.get("parentId") else None),
            token=(str(data["token"]) if data.get("token") is not None else None),
            token_env=(str(data["tokenEnv"]) if data.get("tokenEnv") else None),
            token_ref=(str(data["tokenRef"]) if data.get("tokenRef") else None),
        )


@dataclass
class ConfigFile:
    """Parsed config from one file."""

    path: Path
    default_profile: str | None = None
    profiles: dict[str, ProfileEntry] = field(default_factory=dict)

    def to_json(self) -> dict:
        out: dict = {}
        if self.default_profile:
            out["defaultProfile"] = self.default_profile
        out["profiles"] = {n: p.to_json() for n, p in self.profiles.items()}
        return out


class ConfigError(RuntimeError):
    """Raised on malformed config files or values."""


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def user_config_dir() -> Path:
    """Per-user config directory, cross-platform.

    - Linux: ``$XDG_CONFIG_HOME/confluence-cli/`` (default ``~/.config``).
    - macOS: same as Linux (matches ``gh``, ``aws``, ``uv``).
    - Windows: ``%APPDATA%\\confluence-cli\\`` (default ``~/AppData/Roaming``).
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(
            Path.home() / "AppData" / "Roaming"
        )
        return Path(base) / "confluence-cli"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "confluence-cli"


def user_config_path() -> Path:
    """Path to the per-user ``config.json``."""
    return user_config_dir() / "config.json"


def find_project_config(start: Path | None = None) -> Path | None:
    """Walk upward from ``start`` (default cwd) looking for the project file."""
    cur = (start or Path.cwd()).resolve()
    for _ in range(64):
        candidate = cur / PROJECT_CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        parent = cur.parent
        if parent == cur:
            return None
        cur = parent
    return None


# ---------------------------------------------------------------------------
# Read / write
# ---------------------------------------------------------------------------


def read_config(path: Path) -> ConfigFile:
    """Parse one config file. Returns an empty ``ConfigFile`` if missing."""
    if not path.is_file():
        return ConfigFile(path=path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Malformed JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top-level value must be an object.")
    default_profile = data.get("defaultProfile")
    raw_profiles = data.get("profiles") or {}
    if not isinstance(raw_profiles, dict):
        raise ConfigError(f"{path}: 'profiles' must be an object.")
    profiles: dict[str, ProfileEntry] = {}
    for name, entry in raw_profiles.items():
        if not isinstance(entry, dict):
            raise ConfigError(f"{path}: profile {name!r} must be an object.")
        profiles[name] = ProfileEntry.from_json(name, entry)
    return ConfigFile(
        path=path,
        default_profile=(str(default_profile) if default_profile else None),
        profiles=profiles,
    )


def write_config(config: ConfigFile) -> None:
    """Write the config file, creating parent dirs and setting mode 0600."""
    config.path.parent.mkdir(parents=True, exist_ok=True)
    config.path.write_text(
        json.dumps(config.to_json(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    try:  # POSIX-only; best effort on Windows.
        config.path.chmod(0o600)
    except OSError:  # pragma: no cover
        pass
