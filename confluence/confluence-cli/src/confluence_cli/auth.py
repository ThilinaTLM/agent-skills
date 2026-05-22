"""Credential resolution and (optional) OS-keyring lookup.

Non-secret field precedence (first match wins):

1. Explicit command flags (``--site``, ``--email``, ``--space-key`` …).
2. Environment variables (``CONFLUENCE_SITE``, ``CONFLUENCE_EMAIL`` …).
3. Project config (``.confluence.json``).
4. User config (per-platform; see ``config.user_config_dir``).

Token precedence:

1. ``--token-env NAME`` flag, where ``$NAME`` is read at runtime.
2. ``CONFLUENCE_TOKEN`` environment variable.
3. Profile ``tokenEnv`` (project then user).
4. Profile ``token`` literal (project then user), unless its value
   equals the placeholder string written by ``auth init``.
5. Profile ``tokenRef`` (keyring reference; lazy import). Power-user
   path — the CLI no longer writes to the keyring on the user's
   behalf.

The resolved token is never echoed verbatim. Output payloads describe
each non-secret field's *source*, not its content.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import (
    TOKEN_PLACEHOLDER,
    ConfigError,
    ConfigFile,
    ProfileEntry,
    find_project_config,
    read_config,
    user_config_path,
)

ENV_SITE = "CONFLUENCE_SITE"
ENV_EMAIL = "CONFLUENCE_EMAIL"
ENV_TOKEN = "CONFLUENCE_TOKEN"
ENV_SPACE_KEY = "CONFLUENCE_SPACE_KEY"
ENV_PROFILE = "CONFLUENCE_PROFILE"

KEYRING_SERVICE = "confluence-cli"


@dataclass(frozen=True)
class ResolvedCredentials:
    """Effective credentials and metadata for one CLI invocation."""

    site: str
    email: str
    token: str
    space_key: str | None
    parent_id: str | None
    profile: str | None
    sources: dict[str, str] = field(default_factory=dict)

    def safe_payload(self) -> dict:
        """JSON-safe summary that omits the token."""
        return {
            "site": self.site,
            "email": self.email,
            "spaceKey": self.space_key,
            "parentId": self.parent_id,
            "profile": self.profile,
            "sources": dict(self.sources),
        }


@dataclass(frozen=True)
class CredentialRequest:
    """What the caller specifies on the command line.

    The token cannot be supplied directly via a flag; the CLI accepts
    only the name of an env var to read it from (``--token-env``).
    This keeps tokens out of shell history, ``ps`` listings, and the
    AI agent's command echo.
    """

    profile: str | None = None
    site: str | None = None
    email: str | None = None
    token_env: str | None = None
    space_key: str | None = None
    parent_id: str | None = None
    require_space_key: bool = False


class AuthError(RuntimeError):
    """Raised when credentials cannot be resolved."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "AUTH_ERROR",
        missing: list[str] | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.missing = list(missing or [])
        self.hint = hint


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_credentials(req: CredentialRequest) -> ResolvedCredentials:
    """Resolve credentials per the documented precedence."""
    sources: dict[str, str] = {}

    # 1. Project + user config (loaded eagerly because they may contribute
    #    defaults below).
    project = _read_optional(find_project_config())
    user = _read_optional(user_config_path())

    # 2. Pick the profile name.
    profile_name = (
        req.profile
        or os.environ.get(ENV_PROFILE)
        or (project.default_profile if project else None)
        or (user.default_profile if user else None)
    )
    project_profile = project.profiles.get(profile_name) if project and profile_name else None
    user_profile = user.profiles.get(profile_name) if user and profile_name else None

    # 3. Resolve each non-secret field with the documented precedence.
    site = _pick(
        ("flag", req.site),
        ("env", os.environ.get(ENV_SITE)),
        ("project", project_profile.site if project_profile else None),
        ("user", user_profile.site if user_profile else None),
        sources_key="site",
        sources=sources,
    )
    email = _pick(
        ("flag", req.email),
        ("env", os.environ.get(ENV_EMAIL)),
        ("project", project_profile.email if project_profile else None),
        ("user", user_profile.email if user_profile else None),
        sources_key="email",
        sources=sources,
    )
    space_key = _pick(
        ("flag", req.space_key),
        ("env", os.environ.get(ENV_SPACE_KEY)),
        ("project", project_profile.space_key if project_profile else None),
        ("user", user_profile.space_key if user_profile else None),
        sources_key="spaceKey",
        sources=sources,
        required=False,
    )
    parent_id = _pick(
        ("flag", req.parent_id),
        ("project", project_profile.parent_id if project_profile else None),
        ("user", user_profile.parent_id if user_profile else None),
        sources_key="parentId",
        sources=sources,
        required=False,
    )

    # 4. Token resolution.
    token, token_source = _resolve_token(
        req=req,
        profile_name=profile_name,
        project_profile=project_profile,
        user_profile=user_profile,
    )
    if token_source:
        sources["token"] = token_source

    missing: list[str] = []
    if not site:
        missing.append("site")
    if not email:
        missing.append("email")
    if not token:
        missing.append("token")
    if req.require_space_key and not space_key:
        missing.append("spaceKey")
    if missing:
        raise AuthError(
            "Missing required Confluence credentials: " + ", ".join(missing) + ".",
            code="CONFIG_MISSING",
            missing=missing,
            hint=(
                "Run `confluence auth init --profile NAME` to generate a "
                "config file, then open it in your editor and paste the "
                "token. Or set CONFLUENCE_TOKEN in your environment."
            ),
        )

    site = _normalise_site(site)

    return ResolvedCredentials(
        site=site,
        email=email,
        token=token,
        space_key=space_key,
        parent_id=parent_id,
        profile=profile_name,
        sources=sources,
    )


# ---------------------------------------------------------------------------
# Keyring helpers
# ---------------------------------------------------------------------------


def keyring_get(token_ref: str) -> str | None:
    """Read a token from the OS keyring. Returns None on miss.

    The :mod:`keyring` package is imported lazily; if it's not
    installed (or no usable backend is present), this returns ``None``
    silently so credential resolution can fall through to the next
    source.
    """
    service, account = _split_keyring_ref(token_ref)
    backend = _keyring_or_none()
    if backend is None:
        return None
    try:
        return backend.get_password(service, account)
    except Exception:
        return None


def keyring_ref_for(profile_name: str, site: str, email: str) -> str:
    """Build the canonical keyring reference for a profile.

    Used only by power users who choose to store tokens in their OS
    keyring; the CLI itself no longer writes to the keyring.
    """
    safe_site = site.replace("https://", "").replace("http://", "").strip("/")
    return f"keyring:{KEYRING_SERVICE}/{profile_name}|{safe_site}|{email}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_optional(path: Path | None) -> ConfigFile | None:
    if path is None:
        return None
    try:
        return read_config(path)
    except ConfigError:
        # Re-raise so the CLI can map it; auth resolution itself is
        # pure and should not swallow malformed config.
        raise


def _pick(
    *candidates: tuple[str, str | None],
    sources_key: str,
    sources: dict[str, str],
    required: bool = False,
) -> str | None:
    for label, value in candidates:
        if value:
            sources[sources_key] = label
            return value
    if required:
        sources[sources_key] = "missing"
    return None


def _resolve_token(
    *,
    req: CredentialRequest,
    profile_name: str | None,
    project_profile: ProfileEntry | None,
    user_profile: ProfileEntry | None,
) -> tuple[str, str]:
    # 1. Explicit --token-env.
    if req.token_env:
        val = os.environ.get(req.token_env)
        if val:
            return val, f"env:{req.token_env}"

    # 2. CONFLUENCE_TOKEN.
    val = os.environ.get(ENV_TOKEN)
    if val:
        return val, f"env:{ENV_TOKEN}"

    # 3. Profile tokenEnv (project then user).
    for label, prof in (("project", project_profile), ("user", user_profile)):
        if prof and prof.token_env:
            val = os.environ.get(prof.token_env)
            if val:
                return val, f"{label}:env:{prof.token_env}"

    # 4. Profile literal `token` (project then user). The placeholder
    #    string left by `auth init` is treated as "not set".
    for label, prof in (("project", project_profile), ("user", user_profile)):
        if prof and prof.token and prof.token != TOKEN_PLACEHOLDER:
            return prof.token, f"{label}:file"

    # 5. Profile tokenRef (keyring; opt-in advanced path).
    for label, prof in (("user", user_profile), ("project", project_profile)):
        if prof and prof.token_ref:
            val = keyring_get(prof.token_ref)
            if val:
                return val, f"{label}:keyring"

    _ = profile_name  # currently informational only
    return "", ""


_SITE_RE = re.compile(r"^https?://[^\s/]+(/[^\s]*)?$", re.IGNORECASE)


def _normalise_site(raw: str) -> str:
    s = raw.strip()
    if not s.startswith(("http://", "https://")):
        s = "https://" + s
    if not _SITE_RE.match(s):
        raise AuthError(
            f"CONFLUENCE_SITE looks malformed: {raw!r}",
            code="AUTH_ERROR",
        )
    return s.rstrip("/")


def _split_keyring_ref(token_ref: str) -> tuple[str, str]:
    """Parse ``keyring:<service>/<account>`` into a tuple."""
    if not token_ref.startswith("keyring:"):
        raise AuthError(
            f"Unsupported tokenRef format: {token_ref!r}. "
            "Expected `keyring:<service>/<account>`.",
            code="AUTH_ERROR",
        )
    body = token_ref[len("keyring:"):]
    if "/" not in body:
        raise AuthError(
            f"Malformed tokenRef: {token_ref!r}",
            code="AUTH_ERROR",
        )
    service, _, account = body.partition("/")
    return service, account


def _keyring_or_none():
    try:
        import keyring  # type: ignore[import-not-found]

        return keyring
    except Exception:
        return None
