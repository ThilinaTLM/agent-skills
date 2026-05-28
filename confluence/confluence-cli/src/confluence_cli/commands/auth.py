"""`confluence auth` — init / profiles / use / logout / status.

No ``login`` subcommand: the CLI never accepts a token via flag, stdin,
or any other channel the AI agent controls. The supported workflow is:

1. Agent calls ``confluence auth init --profile NAME`` (and optionally
   ``--site``, ``--email``, etc).
2. The CLI writes a profile to the user config file with the token
   slot filled with the literal placeholder string ``<your-token-here>``.
3. The agent forwards the resulting ``next_steps`` array to the human
   user, asking them to open the file in their editor and paste the
   real token.
4. The user saves the file. Subsequent CLI calls resolve the token
   from the config file (or another higher-precedence source).
"""

from __future__ import annotations

import os

import click

from ..auth import (
    ENV_TOKEN,
    AuthError,
    CredentialRequest,
    resolve_credentials,
)
from ..client import ConfluenceClient
from ..config import (
    TOKEN_PLACEHOLDER,
    ConfigError,
    ConfigFile,
    ProfileEntry,
    find_project_config,
    read_config,
    user_config_path,
    write_config,
)
from ..output import json_error, json_ok


@click.group("auth", help="Manage Confluence credentials and profiles.")
def group() -> None:
    pass


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@group.command("init")
@click.option("--profile", "profile", type=str, required=True, help="Profile name.")
@click.option("--site", type=str, default=None, help="https://acme.atlassian.net")
@click.option("--email", type=str, default=None, help="Atlassian account email.")
@click.option(
    "--space-key", "space_key", type=str, default=None,
    help="Default space key for this profile.",
)
@click.option(
    "--parent-id", "parent_id", type=str, default=None,
    help="Default parent page id for this profile.",
)
@click.option(
    "--token-env", "token_env", type=str, default=None,
    help=(
        "Name of an env var the CLI should read the token from at "
        "runtime. When set, no placeholder token is written into the "
        "config file. Use this for CI."
    ),
)
@click.option(
    "--force", "force", is_flag=True,
    help="Overwrite an existing profile entry in the user config.",
)
def cmd_init(
    profile: str,
    site: str | None,
    email: str | None,
    space_key: str | None,
    parent_id: str | None,
    token_env: str | None,
    force: bool,
) -> None:
    """Write a profile entry to the user config file.

    Writes a placeholder ``<your-token-here>`` value into the ``token``
    field by default. The CLI refuses to use this string as a real
    token, so the user must edit the file before the profile becomes
    usable.

    The agent must NEVER attempt to fill in the token itself. Forward
    the returned ``next_steps`` array to the user verbatim.
    """
    from ..cli import safe_command

    @safe_command
    def run() -> None:
        path = user_config_path()
        try:
            cfg = read_config(path)
        except ConfigError as exc:
            json_error(str(exc), code="INVALID_PARAMS")

        existing = cfg.profiles.get(profile)
        if existing is not None and not force:
            json_error(
                f"Profile {profile!r} already exists in {path}. "
                "Re-run with --force to overwrite, or edit the file by hand.",
                code="FILE_EXISTS",
                profile=profile,
                config=str(path),
            )

        entry = ProfileEntry(
            name=profile,
            site=site,
            email=email,
            space_key=space_key,
            parent_id=parent_id,
            token=(None if token_env else TOKEN_PLACEHOLDER),
            token_env=token_env,
        )
        cfg.profiles[profile] = entry
        if cfg.default_profile is None:
            cfg.default_profile = profile
        write_config(cfg)

        next_steps: list[str]
        if token_env:
            next_steps = [
                f"Export the token in your shell: export {token_env}=<paste-your-atlassian-api-token>",
                "Then verify with: confluence auth status --profile " + profile,
                "Generate a token at https://id.atlassian.com/manage-profile/security/api-tokens.",
            ]
            token_source = "env-var-pending"
        else:
            next_steps = [
                f"Open {path} in your editor.",
                f"Replace \"{TOKEN_PLACEHOLDER}\" with your real Atlassian API token, then save.",
                "Verify with: confluence auth status --profile " + profile,
                "Generate a token at https://id.atlassian.com/manage-profile/security/api-tokens.",
            ]
            token_source = "file-placeholder"

        json_ok(
            profile=profile,
            config=str(path),
            site=site,
            email=email,
            spaceKey=space_key,
            parentId=parent_id,
            tokenSource=token_source,
            tokenEnv=token_env,
            overwritten=existing is not None,
            next_steps=next_steps,
        )

    run()


# ---------------------------------------------------------------------------
# profiles
# ---------------------------------------------------------------------------


@group.command("profiles")
def cmd_profiles() -> None:
    """List configured profiles (without exposing tokens)."""
    from ..cli import safe_command

    @safe_command
    def run() -> None:
        user = read_config(user_config_path())
        project_path = find_project_config()
        project = read_config(project_path) if project_path else ConfigFile(
            path=user_config_path(),  # placeholder; not used below
        )
        if project_path is None:
            project.profiles.clear()
            project.default_profile = None

        def _serialise(cfg: ConfigFile) -> list[dict]:
            rows: list[dict] = []
            for p in cfg.profiles.values():
                if p.token_ref:
                    src = "keyring"
                elif p.token_env:
                    src = "env"
                elif p.token == TOKEN_PLACEHOLDER:
                    src = "file-placeholder"
                elif p.token:
                    src = "file"
                else:
                    src = None
                rows.append(
                    {
                        "name": p.name,
                        "site": p.site,
                        "email": p.email,
                        "spaceKey": p.space_key,
                        "parentId": p.parent_id,
                        "tokenSource": src,
                        "tokenEnv": p.token_env,
                    }
                )
            return rows

        json_ok(
            userConfig=str(user_config_path()),
            projectConfig=(str(project_path) if project_path else None),
            defaultProfile=(
                (project.default_profile if project_path else None)
                or user.default_profile
            ),
            userProfiles=_serialise(user),
            projectProfiles=_serialise(project) if project_path else [],
        )

    run()


# ---------------------------------------------------------------------------
# use
# ---------------------------------------------------------------------------


@group.command("use")
@click.argument("profile", metavar="PROFILE")
def cmd_use(profile: str) -> None:
    """Set the default profile in the user config."""
    from ..cli import safe_command

    @safe_command
    def run() -> None:
        path = user_config_path()
        cfg = read_config(path)
        if profile not in cfg.profiles:
            json_error(
                f"Unknown profile {profile!r}. "
                "Run `confluence auth init --profile NAME ...` first.",
                code="NOT_FOUND",
            )
        cfg.default_profile = profile
        write_config(cfg)
        json_ok(profile=profile, config=str(path))

    run()


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------


@group.command("logout")
@click.option("--profile", "profile", type=str, required=True)
@click.option(
    "--keep-config", "keep_config", is_flag=True,
    help="Keep the profile entry in user config; only remove the token field.",
)
def cmd_logout(profile: str, keep_config: bool) -> None:
    """Forget a profile.

    Removes the profile entry from the user config (so any literal
    ``token`` field is wiped). With ``--keep-config``, keeps the other
    profile fields and only clears ``token``/``tokenRef``/``tokenEnv``.

    Does NOT attempt to delete from the OS keyring: the CLI doesn't
    own those entries (the user added them manually). Power users who
    want to revoke a keyring entry should use their OS tool
    (``secret-tool``, ``security``, Windows Credential Manager).
    """
    from ..cli import safe_command

    @safe_command
    def run() -> None:
        path = user_config_path()
        cfg = read_config(path)
        entry = cfg.profiles.get(profile)
        if entry is None:
            json_error(f"Unknown profile {profile!r}.", code="NOT_FOUND")
        # mypy narrow
        assert entry is not None
        had_keyring_ref = bool(entry.token_ref)
        if keep_config:
            entry.token = None
            entry.token_env = None
            entry.token_ref = None
        else:
            del cfg.profiles[profile]
            if cfg.default_profile == profile:
                cfg.default_profile = next(iter(cfg.profiles), None)
        write_config(cfg)
        json_ok(
            profile=profile,
            removedFromConfig=not keep_config,
            keyringRefForgottenByConfig=had_keyring_ref,
            note=(
                "Keyring entries (if any) were referenced by this profile "
                "but the CLI did not delete them. Use your OS keyring tool "
                "to revoke them if needed."
                if had_keyring_ref else None
            ),
        )

    run()


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@group.command("status")
@click.option("--profile", "profile", type=str, default=None)
@click.option(
    "--strict", "strict", is_flag=True,
    help=(
        "Exit non-zero if the token isn't stored in the OS keyring. "
        "Use this in agent harnesses that refuse to operate against "
        "plaintext-file tokens."
    ),
)
@click.option(
    "--no-verify", "no_verify", is_flag=True,
    help="Skip the read-only verification call against Confluence.",
)
def cmd_status(profile: str | None, strict: bool, no_verify: bool) -> None:
    """Resolve credentials end-to-end and report security posture.

    Reports where every non-secret field came from (``flag``, ``env``,
    ``project``, ``user``) and where the token was resolved from
    (``env:VAR``, ``user:file``, ``project:file``, ``user:keyring`` \u2026).
    Sets ``secure: true`` only when the token came from the keyring
    AND ``CONFLUENCE_TOKEN`` is not set in the environment.

    With ``--strict``, exits with a non-zero status when ``secure`` is
    false.
    """
    from ..cli import safe_command

    @safe_command
    def run() -> None:
        try:
            creds = resolve_credentials(CredentialRequest(profile=profile))
        except AuthError as exc:
            json_error(
                str(exc),
                code=exc.code,
                hint=exc.hint,
                missing=exc.missing,
            )

        token_source = creds.sources.get("token", "")
        token_location = _describe_token_location(token_source)
        secure_notes: list[str] = []
        secure = token_source.endswith(":keyring")
        if not secure:
            if token_source.startswith("env"):
                secure_notes.append(
                    "Token is read from an environment variable. Any "
                    "process that can read your env can read the token."
                )
            elif token_source.endswith(":file"):
                secure_notes.append(
                    "Token is stored in plaintext in your config file. "
                    "Other tools with read access to your home directory "
                    "can read it."
                )
                secure_notes.append(
                    "For a stronger boundary, store the token in your OS "
                    "keyring and reference it via `tokenRef`. See "
                    "confluence/references/auth.md."
                )
        if secure and os.environ.get(ENV_TOKEN):
            secure = False
            secure_notes.append(
                f"Token resolved from keyring but {ENV_TOKEN} is also "
                "set in the environment, which takes precedence and "
                "weakens the keyring guarantee."
            )

        payload = creds.safe_payload()
        payload["tokenSource"] = token_source
        payload["tokenLocation"] = token_location
        payload["secure"] = secure
        if secure_notes:
            payload["secureNotes"] = secure_notes

        from ..tls import _resolve_cafile

        if os.environ.get("CONFLUENCE_INSECURE") == "1":
            payload["tls"] = {
                "mode": "insecure-opt-in",
                "source": "CONFLUENCE_INSECURE",
            }
        else:
            resolved = _resolve_cafile()
            if resolved is None:
                payload["tls"] = {"mode": "system-default", "source": None}
            else:
                env_name, ca_path = resolved
                payload["tls"] = {
                    "mode": "custom-ca-bundle",
                    "source": f"env:{env_name}",
                    "caBundle": ca_path,
                }

        if not no_verify:
            client = ConfluenceClient(
                site=creds.site, email=creds.email, token=creds.token,
            )
            try:
                client.ping()
                payload["reachable"] = True
            except Exception as exc:
                json_error(
                    f"Credentials resolved but Confluence rejected the request: {exc}",
                    code="AUTH_ERROR",
                    **payload,
                )

        if strict and not secure:
            json_error(
                "Insecure token storage; refusing to proceed (--strict).",
                code="AUTH_INSECURE",
                hint=(
                    "Move the token into your OS keyring (see "
                    "confluence/references/auth.md \u2018Advanced: storing the "
                    "token in the OS keyring\u2019), or drop --strict if you "
                    "accept the file/env-var trade-off."
                ),
                **payload,
            )

        json_ok(**payload)

    run()


def _describe_token_location(token_source: str) -> str | None:
    """Translate a resolver source label into a user-friendly path or hint.

    Never returns the token itself. ``env:VAR`` becomes the env var
    name; ``user:file`` becomes the user config path; ``user:keyring``
    becomes the literal string ``"keyring"`` (no service name leak).
    """
    if not token_source:
        return None
    if token_source.startswith("env:"):
        return token_source  # e.g. "env:CONFLUENCE_TOKEN"
    if ":env:" in token_source:
        # e.g. "user:env:MY_VAR"
        _, _, env_part = token_source.partition(":env:")
        return f"env:{env_part}"
    if token_source.endswith(":file"):
        return str(user_config_path()) if token_source.startswith("user") else "project:.confluence.json"
    if token_source.endswith(":keyring"):
        return "keyring"
    return None
