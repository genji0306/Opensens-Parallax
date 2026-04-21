"""Sprint 4 — Snapshot + SHA-256 rollback."""
from __future__ import annotations

import pytest

from parallax_v3.runtime.snapshot import Snapshot, SnapshotError


def test_snapshot_create(tmp_path):
    (tmp_path / "file_a.txt").write_text("original-a")
    (tmp_path / "file_b.txt").write_text("original-b")
    snap = Snapshot.create(tmp_path)
    assert snap.iteration == 1
    assert snap.snapshot_path.exists()
    assert (snap.snapshot_path / "file_a.txt").read_text() == "original-a"
    assert snap.hashes  # SHA-256 for each file
    assert len(next(iter(snap.hashes.values()))) == 64


def test_snapshot_verify_true_on_unchanged(tmp_path):
    (tmp_path / "x.txt").write_text("content")
    snap = Snapshot.create(tmp_path)
    assert Snapshot.verify(snap) is True


def test_snapshot_restore_recovers_original(tmp_path):
    (tmp_path / "x.txt").write_text("original")
    snap = Snapshot.create(tmp_path)
    # Mutate the workspace
    (tmp_path / "x.txt").write_text("mutated")
    (tmp_path / "new_file.txt").write_text("added")
    Snapshot.restore(snap)
    assert (tmp_path / "x.txt").read_text() == "original"
    assert not (tmp_path / "new_file.txt").exists()


def test_snapshot_multiple_iterations(tmp_path):
    (tmp_path / "f.txt").write_text("v1")
    s1 = Snapshot.create(tmp_path)
    (tmp_path / "f.txt").write_text("v2")
    s2 = Snapshot.create(tmp_path)
    assert s1.iteration == 1
    assert s2.iteration == 2
    assert s1.snapshot_path != s2.snapshot_path


def test_snapshot_missing_workspace_raises(tmp_path):
    missing = tmp_path / "does_not_exist"
    with pytest.raises(SnapshotError):
        Snapshot.create(missing)
