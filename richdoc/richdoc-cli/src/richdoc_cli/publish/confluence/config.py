"""Env-var-only configuration for `richdoc confluence`.

Four environment variables are the *only* configuration source. There are
no flags and no interactive prompts. This module is deliberately decoupled
from the CLI output layer: missing vars are returned as a list so the
caller can shape the JSON envelope however it likes.

    CONFLUENCE_SITE        e.g. https://acme.atlassian.net
    CONFLUENCE_EMAIL       Atlassian account email
    CONFLUENCE_TOKEN       Atlassian API token (HTTP Basic password)
    CONFLUENCE_SPACE_KEY   Target space key, e.g. DEV (required for
                           `pages` and `publish` only)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

ENV_SITE = "CONFLUENCE_SITE"
ENV_EMAIL = "CONFLUENCE_EMAIL"
ENV_TOKEN = "CONFLUENCE_TOKEN"
ENV_SPACE_KEY = "CONFLUENCE_SPACE_KEY"

AUTH_VARS: tuple[str, ...] = (ENV_SITE, ENV_EMAIL, ENV_TOKEN)
PUBLISH_VARS: tuple[str, ...] = AUTH_VARS + (ENV_SPACE_KEY,)


@dataclass(frozen=True)
class Config:
    """Resolved configuration for a Confluence subcommand.

    `space_key` is populated only when the calling subcommand asked for
    `CONFLUENCE_SPACE_KEY` in its required tuple; otherwise it's None.
    """

    site: str
    email: str
    token: str
    space_key: str | None


class ConfigError(RuntimeError):
    """Raised when an env var value is present but malformed.

    Distinct from "missing": malformed means the user set the variable but
    its value is unusable (e.g. a site URL that isn't a URL). Missing is
    reported separately via the `missing` list returned by `resolve_config`.
    """


def resolve_config(
    required: tuple[str, ...],
) -> tuple[Config, None] | tuple[None, list[str]]:
    """Read the required CONFLUENCE_* env vars.

    Returns `(config, None)` when every required var is set to a non-empty
    value (after stripping). Returns `(None, missing)` listing every
    required var that was unset or blank.

    Raises `ConfigError` if a required value is present but malformed
    (bad site URL, email without an `@`).
    """
    values: dict[str, str] = {}
    missing: list[str] = []
    for name in required:
        raw = (os.environ.get(name) or "").strip()
        if not raw:
            missing.append(name)
        else:
            values[name] = raw

    if missing:
        return None, missing

    site = _normalise_site(values[ENV_SITE]) if ENV_SITE in values else ""
    email = values.get(ENV_EMAIL, "")
    if email and "@" not in email:
        raise ConfigError(f"{ENV_EMAIL} looks malformed: {email!r}")
    token = values.get(ENV_TOKEN, "")
    space_key = values.get(ENV_SPACE_KEY)  # None when not requested

    return (
        Config(site=site, email=email, token=token, space_key=space_key),
        None,
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


# Whole-string match: scheme + non-empty host + optional path segments.
# Anchored at the end so values like "https://not a url" are rejected
# rather than silently truncated to the matching prefix.
_SITE_RE = re.compile(r"^https?://[^\s/]+(/[^\s]*)?$", re.IGNORECASE)


def _normalise_site(raw: str) -> str:
    """Strip trailing slashes, ensure a scheme. Bare host → https://host."""
    s = raw.strip()
    if not s.startswith(("http://", "https://")):
        s = "https://" + s
    if not _SITE_RE.match(s):
        raise ConfigError(f"{ENV_SITE} looks malformed: {raw!r}")
    return s.rstrip("/")
