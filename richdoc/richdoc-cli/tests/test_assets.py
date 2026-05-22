"""Unit tests for `export/common/assets.AssetStore`.

The store powers asset materialisation for the md and docx exporters
and the Confluence publish path. Tests cover URL classification,
content-addressed dedup, and the materialise-to-disk pass.
"""

from __future__ import annotations

import hashlib

from richdoc_cli.export.common.assets import (
    AssetStore,
    is_relative_url,
    is_remote_url,
)

# ---------------------------------------------------------------------------
# URL classifiers
# ---------------------------------------------------------------------------


def test_is_relative_url_distinguishes_local():
    assert is_relative_url("image.png")
    assert is_relative_url("./image.png")
    assert is_relative_url("../up/image.png")
    assert is_relative_url("sub/dir/image.png")


def test_is_relative_url_rejects_absolute():
    assert not is_relative_url("")
    assert not is_relative_url("#fragment")
    assert not is_relative_url("//cdn.example.com/image.png")
    assert not is_relative_url("http://example.com/image.png")
    assert not is_relative_url("https://example.com/image.png")
    assert not is_relative_url("data:image/png;base64,AAA")
    assert not is_relative_url("mailto:a@b")


def test_is_remote_url_only_http_https():
    assert is_remote_url("http://example.com")
    assert is_remote_url("https://example.com")
    assert not is_remote_url("./image.png")
    assert not is_remote_url("data:image/png;base64,AAA")


# ---------------------------------------------------------------------------
# AssetStore.add \u2014 local files
# ---------------------------------------------------------------------------


def test_add_local_file_returns_stable_name(tmp_path):
    img = tmp_path / "hello.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    store = AssetStore()
    ref = store.add("hello.png", base_dir=tmp_path, fetch_remote=False)
    assert ref is not None
    assert ref.data == img.read_bytes()
    # Filename starts with sha1[:12] of contents.
    expected_prefix = hashlib.sha1(img.read_bytes(), usedforsecurity=False).hexdigest()[:12]
    assert ref.local_name.startswith(expected_prefix)
    assert ref.local_name.endswith(".png")


def test_add_dedups_same_source(tmp_path):
    img = tmp_path / "hello.png"
    img.write_bytes(b"data")
    store = AssetStore()
    a = store.add("hello.png", base_dir=tmp_path, fetch_remote=False)
    b = store.add("hello.png", base_dir=tmp_path, fetch_remote=False)
    assert a is b


def test_add_two_different_paths_same_content_share_local_name(tmp_path):
    (tmp_path / "a.png").write_bytes(b"identical")
    (tmp_path / "b.png").write_bytes(b"identical")
    store = AssetStore()
    a = store.add("a.png", base_dir=tmp_path, fetch_remote=False)
    b = store.add("b.png", base_dir=tmp_path, fetch_remote=False)
    assert a is not None and b is not None
    # Different sources, same hash \u2192 same local_name.
    assert a.local_name == b.local_name


def test_add_records_missing_for_unresolvable_source(tmp_path):
    store = AssetStore()
    ref = store.add("does-not-exist.png", base_dir=tmp_path, fetch_remote=False)
    assert ref is None
    assert store.missing == ["does-not-exist.png"]
    # Re-adding the same source doesn't duplicate the missing entry.
    store.add("does-not-exist.png", base_dir=tmp_path, fetch_remote=False)
    assert store.missing == ["does-not-exist.png"]


def test_add_ignores_empty_and_fragment(tmp_path):
    store = AssetStore()
    assert store.add("", base_dir=tmp_path, fetch_remote=False) is None
    assert store.add("#anchor", base_dir=tmp_path, fetch_remote=False) is None
    assert store.add("data:image/png;base64,AAA", base_dir=tmp_path, fetch_remote=False) is None
    assert store.missing == []


def test_add_remote_skipped_when_fetch_disabled(tmp_path):
    store = AssetStore()
    ref = store.add("https://example.com/x.png", base_dir=tmp_path, fetch_remote=False)
    assert ref is None
    assert store.missing == []  # not flagged \u2014 just skipped


# ---------------------------------------------------------------------------
# write_to
# ---------------------------------------------------------------------------


def test_write_to_materialises_each_unique_blob(tmp_path):
    (tmp_path / "a.png").write_bytes(b"A")
    (tmp_path / "b.png").write_bytes(b"B")
    store = AssetStore()
    store.add("a.png", base_dir=tmp_path, fetch_remote=False)
    store.add("b.png", base_dir=tmp_path, fetch_remote=False)

    out = tmp_path / "out"
    mapping = store.write_to(out)
    assert set(mapping) == {"a.png", "b.png"}
    # Both files exist on disk.
    written = sorted(p.name for p in out.iterdir())
    assert len(written) == 2
    # Mapping points each source to a real on-disk filename.
    for filename in mapping.values():
        assert (out / filename).is_file()


def test_write_to_is_idempotent(tmp_path):
    (tmp_path / "a.png").write_bytes(b"A")
    store = AssetStore()
    store.add("a.png", base_dir=tmp_path, fetch_remote=False)

    out = tmp_path / "out"
    store.write_to(out)
    files1 = {p.name: p.read_bytes() for p in out.iterdir()}
    store.write_to(out)  # writing twice doesn't change anything
    files2 = {p.name: p.read_bytes() for p in out.iterdir()}
    assert files1 == files2
