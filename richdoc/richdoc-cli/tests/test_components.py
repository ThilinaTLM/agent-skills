"""Snapshot tests for `richdoc components`."""

from __future__ import annotations


def _strip_schema_path(envelope: dict) -> dict:
    """Drop the absolute ``schemaPath`` so snapshots are portable."""
    payload = dict(envelope)
    payload.pop("schemaPath", None)
    payload.pop("generated", None)
    return payload


def test_components_lists_every_tag(cli_invoke, snapshot):
    result = cli_invoke("components")
    envelope = result.expect_ok()
    payload = _strip_schema_path(envelope)
    # The full tag list is ~50 entries; snapshot it whole so any
    # accidental schema edit shows up in the diff.
    assert payload == snapshot


def test_components_single_tag(cli_invoke, snapshot):
    result = cli_invoke("components", "--tag", "rd-callout")
    envelope = result.expect_ok()
    payload = _strip_schema_path(envelope)
    assert payload == snapshot


def test_components_unknown_tag_returns_empty(cli_invoke):
    result = cli_invoke("components", "--tag", "rd-does-not-exist")
    envelope = result.expect_ok()
    assert envelope["count"] == 0
    assert envelope["tags"] == []
