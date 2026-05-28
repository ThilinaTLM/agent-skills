"""Build the SSL context used for every Confluence HTTPS request.

Stdlib-only. Honors the same CA-bundle env vars ``requests``, ``pip``,
``aws``, and ``curl`` honor, plus a CLI-specific override. Relaxes
``VERIFY_X509_STRICT`` (Python 3.13+) so corporate roots whose Basic
Constraints extension is not marked critical still validate \u2014 matches
pre-3.13 stdlib behavior and what ``requests`` ships with today.

Env vars consulted, in precedence order:

1. ``CONFLUENCE_INSECURE=1`` \u2014 return an unverified context (loud
   opt-in; prints a one-time warning to stderr at import). Mirrors
   ``curl -k``.
2. ``CONFLUENCE_CA_BUNDLE`` \u2014 CLI-specific override.
3. ``SSL_CERT_FILE`` \u2014 stdlib-standard.
4. ``REQUESTS_CA_BUNDLE`` \u2014 what ``requests`` honors.
5. ``CURL_CA_BUNDLE`` \u2014 what ``curl`` honors.

If none point at an existing file, returns ``None``; callers pass that
to ``urlopen(..., context=None)`` which is a no-op (Python uses its
default context). Users on non-intercepted networks see no change.
"""

from __future__ import annotations

import os
import ssl
import sys

_CA_ENV_VARS = (
    "CONFLUENCE_CA_BUNDLE",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
)


def _resolve_cafile() -> tuple[str, str] | None:
    """Return ``(env_var_name, path)`` for the first env var that points
    at an existing file, or ``None`` if no override is configured."""
    for name in _CA_ENV_VARS:
        val = os.environ.get(name)
        if val and os.path.exists(val):
            return name, val
    return None


def build_ssl_context() -> ssl.SSLContext | None:
    """Build the shared SSL context. See module docstring for semantics."""
    if os.environ.get("CONFLUENCE_INSECURE") == "1":
        print(
            "confluence-cli: WARNING \u2014 CONFLUENCE_INSECURE=1 set; TLS "
            "certificate verification is DISABLED for this process.",
            file=sys.stderr,
        )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    resolved = _resolve_cafile()
    if resolved is None:
        return None

    _, cafile = resolved
    ctx = ssl.create_default_context(cafile=cafile)
    # Python 3.13+ defaults VERIFY_X509_STRICT on. Most corporate roots
    # in the wild have non-critical Basic Constraints; clearing the
    # flag matches pre-3.13 stdlib + current `requests` behavior.
    try:
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    except AttributeError:
        pass
    return ctx


# Built once at import. Re-importing won't rebuild; that's fine because
# the env vars are read once per process anyway.
SSL_CONTEXT: ssl.SSLContext | None = build_ssl_context()
