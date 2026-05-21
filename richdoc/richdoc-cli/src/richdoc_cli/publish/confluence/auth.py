"""Credential resolution for `richdoc publish confluence`.

Three inputs are needed every run: site URL, email, API token. None are
persisted to disk. Resolution order per field:

    site  : --site flag → $CONFLUENCE_SITE  → interactive prompt
    email : --email flag → $CONFLUENCE_EMAIL → interactive prompt
    token : --token-stdin (read one line) → $CONFLUENCE_TOKEN → getpass prompt

When stdin is not a TTY and the required value is not supplied via flag /
env, we error out rather than block on a prompt — keeps the CLI agent-safe.
"""

from __future__ import annotations

import getpass
import os
import re
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Creds:
    """Resolved Atlassian Cloud credentials."""

    site: str   # canonical e.g. "https://acme.atlassian.net"
    email: str
    token: str


class CredentialError(RuntimeError):
    """Raised when a credential can't be resolved."""


def resolve_creds(
    *,
    site: str | None,
    email: str | None,
    token_stdin: bool,
    allow_prompt: bool = True,
) -> Creds:
    """Resolve site, email, and token from flags / env / prompts.

    `allow_prompt` is False under non-interactive use (no TTY); a missing
    field raises `CredentialError` with a clear message.
    """
    site_value = (site or os.environ.get("CONFLUENCE_SITE") or "").strip()
    if not site_value:
        site_value = _prompt(
            "Confluence site URL (e.g. https://acme.atlassian.net): ",
            allow=allow_prompt,
            field="site",
        )
    site_value = _normalise_site(site_value)

    email_value = (email or os.environ.get("CONFLUENCE_EMAIL") or "").strip()
    if not email_value:
        email_value = _prompt(
            "Atlassian account email: ",
            allow=allow_prompt,
            field="email",
        )
    if "@" not in email_value:
        raise CredentialError(f"Email looks malformed: {email_value!r}")

    if token_stdin:
        token_value = sys.stdin.readline().strip()
        if not token_value:
            raise CredentialError(
                "--token-stdin set but no token read from stdin."
            )
    else:
        token_value = (os.environ.get("CONFLUENCE_TOKEN") or "").strip()
        if not token_value:
            if not allow_prompt:
                raise CredentialError(
                    "No API token. Pass --token-stdin or set $CONFLUENCE_TOKEN."
                )
            # getpass writes its prompt to stderr — keeps stdout clean for
            # the JSON envelope.
            token_value = getpass.getpass(
                "Atlassian API token (input hidden): ", stream=sys.stderr
            ).strip()
            if not token_value:
                raise CredentialError("Empty API token.")

    return Creds(site=site_value, email=email_value, token=token_value)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


_SITE_RE = re.compile(r"^https?://[^/\s]+", re.IGNORECASE)


def _normalise_site(raw: str) -> str:
    """Strip trailing slashes, ensure a scheme. Bare host → https://host."""
    s = raw.strip()
    if not s:
        raise CredentialError("Empty site URL.")
    if not s.startswith(("http://", "https://")):
        s = "https://" + s
    if not _SITE_RE.match(s):
        raise CredentialError(f"Site URL looks malformed: {raw!r}")
    return s.rstrip("/")


def _prompt(text: str, *, allow: bool, field: str) -> str:
    if not allow:
        raise CredentialError(
            f"Missing {field}. Pass --{field} or set $CONFLUENCE_{field.upper()}."
        )
    # Echo the prompt to stderr, leaving stdout clean for the JSON envelope.
    sys.stderr.write(text)
    sys.stderr.flush()
    value = sys.stdin.readline().strip()
    if not value:
        raise CredentialError(f"Empty {field}.")
    return value
