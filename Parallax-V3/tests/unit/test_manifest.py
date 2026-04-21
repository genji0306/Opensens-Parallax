"""Unit tests for SessionManifest construction and validation."""

from __future__ import annotations

import json

import pytest

from parallax_v3.manifest import (
    SessionManifest,
    SessionManifestValidator,
    build_manifest,
    load_manifest_file,
    manifest_to_dict,
    manifest_to_json,
    validate_manifest_dict,
)
from parallax_v3.manifest.schema import ManifestValidationError


def _payload(session_id: str = "11111111-1111-4111-8111-111111111111") -> dict[str, object]:
    return {
        "session_id": session_id,
        "research_question": "Does method X outperform Y on benchmark Z?",
        "target_venue": "neurips",
        "citation_style": "ieee",
        "max_refinement_iters": 3,
        "budget_usd": 8.0,
        "ethics_flags": [],
        "refinement_policy": {"plateau_threshold": 1.0, "plateau_window": 2},
    }


def test_session_manifest_validate_round_trip(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")

    manifest = SessionManifest.validate(path)

    assert manifest.session_id == "11111111-1111-4111-8111-111111111111"
    assert manifest.target_venue == "neurips"
    assert manifest_to_dict(manifest)["research_question"].startswith("Does method X")
    assert json.loads(manifest_to_json(manifest))["citation_style"] == "ieee"
    assert load_manifest_file(path) == manifest
    assert SessionManifestValidator.validate(path) == manifest
    validate_manifest_dict(_payload())


def test_session_manifest_rejects_unknown_fields(tmp_path):
    payload = _payload()
    payload["default_model"] = "claude-sonnet-4-6"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ManifestValidationError):
        SessionManifest.validate(path)


def test_build_manifest_compatibility_wrapper():
    manifest = build_manifest(
        {
            "research_question": "Round-trip serialisation test for manifest fidelity",
            "target_venue": "grant_nsf",
            "citation_style": "apa",
            "budget_usd": 5.0,
            "ethics_flags": ["no_human_subjects"],
            "refinement_policy": {"plateau_window": 3},
        }
    )

    assert len(manifest.session_id) == 36
    assert manifest.research_question.startswith("Round-trip")
    assert manifest.budget_usd == 5.0
    assert manifest.ethics_flags == ["no_human_subjects"]


def test_session_manifest_is_frozen():
    manifest = SessionManifest(**_payload())

    with pytest.raises((AttributeError, TypeError)):
        manifest.research_question = "mutated"  # type: ignore[misc]

