"""Sprint 3 — Single-purpose IO primitives (Pattern #11)."""
from __future__ import annotations

import pytest

from parallax_v3.memory.stores.cold import ColdStore, ColdStoreError
from parallax_v3.tools.primitives.io import (
    EditTool,
    GlobTool,
    GrepTool,
    ReadTool,
    WriteTool,
)


@pytest.fixture
def store(tmp_path):
    return ColdStore(workspace_path=tmp_path, session_id="s1")


def test_write_and_read(store):
    WriteTool(store).run("notes.txt", "hello world")
    content = ReadTool(store).run("notes.txt")
    assert content == "hello world"


def test_edit_replaces(store):
    WriteTool(store).run("notes.txt", "hello world")
    EditTool(store).run("notes.txt", "hello", "goodbye")
    assert ReadTool(store).run("notes.txt") == "goodbye world"


def test_edit_missing_substring_raises(store):
    WriteTool(store).run("notes.txt", "abc")
    with pytest.raises(ValueError):
        EditTool(store).run("notes.txt", "missing", "replacement")


def test_grep(store):
    WriteTool(store).run("log.txt", "alpha\nbeta\ngamma alpha\n")
    matches = GrepTool(store).run("alpha", "log.txt")
    assert len(matches) == 2
    assert matches[0]["line"] == 1


def test_glob(store):
    WriteTool(store).run("a.md", "x")
    WriteTool(store).run("b.md", "y")
    WriteTool(store).run("ignore.txt", "z")
    results = GlobTool(store).run("*.md", "")
    assert sorted(results) == ["a.md", "b.md"]


def test_workspace_escape_blocked(store):
    with pytest.raises(ColdStoreError):
        ReadTool(store).run("../../../etc/passwd")
