"""Snapshot + behavioural tests for the scaffolding commands.

`new`, `init`, `update` all write to disk; tests run in `tmp_path` to
keep the repo clean. Idempotency is asserted: re-running each command
in the same directory either skips (without --force) or is a no-op.
"""

from __future__ import annotations

import filecmp

import pytest

# ---------------------------------------------------------------------------
# new
# ---------------------------------------------------------------------------


def test_new_default_template(cli_invoke, tmp_path):
    out = tmp_path / "draft.html"
    result = cli_invoke("new", str(out))
    envelope = result.expect_ok()
    assert out.is_file()
    assert envelope["file"] == str(out.resolve())
    assert envelope["template"] == "plan"
    # No assets in tmp_path, so the command flags them.
    assert envelope["assets_needed"]


@pytest.mark.parametrize(
    "template",
    ["plan", "adr", "research", "runbook", "onepager", "comparison"],
)
def test_new_named_template(cli_invoke, tmp_path, template):
    out = tmp_path / f"{template}.html"
    result = cli_invoke("new", str(out), "--template", template)
    envelope = result.expect_ok()
    assert out.is_file()
    assert envelope["template"] == template


def test_new_unknown_template_lists_available(cli_invoke, tmp_path):
    out = tmp_path / "draft.html"
    result = cli_invoke("new", str(out), "--template", "nonexistent")
    envelope = result.expect_error("TEMPLATE_NOT_FOUND")
    assert "available" in envelope
    assert len(envelope["available"]) > 0


def test_new_refuses_to_overwrite(cli_invoke, tmp_path):
    out = tmp_path / "draft.html"
    out.write_text("existing", encoding="utf-8")
    result = cli_invoke("new", str(out))
    result.expect_error("FILE_EXISTS")


def test_new_force_overwrites(cli_invoke, tmp_path):
    out = tmp_path / "draft.html"
    out.write_text("stale", encoding="utf-8")
    result = cli_invoke("new", "-f", str(out))
    result.expect_ok()
    assert out.read_text(encoding="utf-8") != "stale"


def test_new_non_html_extension_rejected(cli_invoke, tmp_path):
    out = tmp_path / "draft.txt"
    result = cli_invoke("new", str(out))
    result.expect_error("INVALID_PARAMS")


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def test_init_copies_assets(cli_invoke, tmp_path):
    result = cli_invoke("init", str(tmp_path))
    envelope = result.expect_ok()
    assert (tmp_path / "richdoc.css").is_file()
    assert (tmp_path / "richdoc.js").is_file()
    assert set(envelope["written"]) >= {"richdoc.css", "richdoc.js"}
    assert envelope["skipped"] == []


def test_init_skips_existing_assets(cli_invoke, tmp_path):
    first = cli_invoke("init", str(tmp_path))
    first.expect_ok()
    second = cli_invoke("init", str(tmp_path))
    envelope = second.expect_ok()
    assert envelope["written"] == []
    assert set(envelope["skipped"]) >= {"richdoc.css", "richdoc.js"}


def test_init_force_overwrites(cli_invoke, tmp_path):
    cli_invoke("init", str(tmp_path)).expect_ok()
    # Tamper with the CSS so we can verify --force restored it.
    (tmp_path / "richdoc.css").write_text("/* tampered */", encoding="utf-8")
    result = cli_invoke("init", "--force", str(tmp_path))
    envelope = result.expect_ok()
    assert set(envelope["written"]) >= {"richdoc.css", "richdoc.js"}
    content = (tmp_path / "richdoc.css").read_text(encoding="utf-8")
    assert "tampered" not in content


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


def test_update_report_only_default(cli_invoke, tmp_path):
    """Without --apply, `update` only reports drift; nothing is written."""
    (tmp_path / "richdoc.css").write_text("/* old */", encoding="utf-8")
    (tmp_path / "richdoc.js").write_text("// old", encoding="utf-8")
    before_css = (tmp_path / "richdoc.css").read_text(encoding="utf-8")
    result = cli_invoke("update", str(tmp_path))
    envelope = result.expect_ok()
    assert envelope["applied"] is False
    assert envelope["scanned"] == 1
    assert envelope["stale"], envelope
    # File contents are unchanged in report-only mode.
    assert (tmp_path / "richdoc.css").read_text(encoding="utf-8") == before_css


def test_update_apply_refreshes_stale_assets(cli_invoke, tmp_path, assets_dir):
    (tmp_path / "richdoc.css").write_text("/* old */", encoding="utf-8")
    (tmp_path / "richdoc.js").write_text("// old", encoding="utf-8")
    result = cli_invoke("update", "--apply", str(tmp_path))
    envelope = result.expect_ok()
    assert envelope["applied"] is True
    assert envelope["refreshed"], envelope
    # Updated files match the shipped assets byte-for-byte.
    assert filecmp.cmp(
        tmp_path / "richdoc.css", assets_dir / "richdoc.css", shallow=False
    )
    assert filecmp.cmp(
        tmp_path / "richdoc.js", assets_dir / "richdoc.js", shallow=False
    )


def test_update_apply_is_no_op_when_assets_match(cli_invoke, tmp_path):
    cli_invoke("init", str(tmp_path)).expect_ok()
    result = cli_invoke("update", "--apply", str(tmp_path))
    envelope = result.expect_ok()
    assert envelope["applied"] is True
    assert envelope["refreshed"] == []
    # The folder shows up as up-to-date (no `stale` field in apply mode).
    assert len(envelope["up_to_date"]) == 1
