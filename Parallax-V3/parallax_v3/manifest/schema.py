"""Session manifest validation and loading."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from jsonschema import ValidationError, validate as jsonschema_validate

from ..contracts import SessionManifest
from ..errors import ParallaxV3Error


class ManifestValidationError(ValueError, ParallaxV3Error):
    """Raised when a manifest file does not conform to schema."""


def _schema_path() -> Path:
    return Path(__file__).resolve().with_name("manifests") / "schema.json"


def _load_schema() -> dict[str, Any]:
    return json.loads(_schema_path().read_text(encoding="utf-8"))


def _validate_data(data: dict[str, Any]) -> None:
    try:
        jsonschema_validate(instance=data, schema=_load_schema())
    except ValidationError as exc:
        raise ManifestValidationError(f"Manifest validation failed: {exc.message}") from exc


@classmethod
def validate(cls, manifest_json_path: str | Path) -> SessionManifest:
    path = Path(manifest_json_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate_data(data)
    return cls(
        session_id=data["session_id"],
        research_question=data["research_question"],
        target_venue=data["target_venue"],
        citation_style=data["citation_style"],
        max_refinement_iters=data.get("max_refinement_iters", 3),
        budget_usd=data.get("budget_usd", 0.0),
        ethics_flags=list(data.get("ethics_flags", [])),
        refinement_policy=dict(data.get("refinement_policy", {})),
    )


SessionManifest.validate = validate  # type: ignore[assignment]
SessionManifestValidator = SessionManifest


def validate_manifest_dict(data: dict[str, Any]) -> None:
    _validate_data(data)


def build_manifest(data: dict[str, Any]) -> SessionManifest:
    payload = {**data}
    payload.setdefault("session_id", str(uuid4()))
    manifest_fields = {
        "session_id",
        "research_question",
        "target_venue",
        "citation_style",
        "max_refinement_iters",
        "budget_usd",
        "ethics_flags",
        "refinement_policy",
    }
    filtered = {key: value for key, value in payload.items() if key in manifest_fields}
    _validate_data(filtered)
    return SessionManifest(
        session_id=filtered["session_id"],
        research_question=filtered["research_question"],
        target_venue=filtered["target_venue"],
        citation_style=filtered["citation_style"],
        max_refinement_iters=filtered.get("max_refinement_iters", 3),
        budget_usd=filtered.get("budget_usd", 0.0),
        ethics_flags=list(filtered.get("ethics_flags", [])),
        refinement_policy=dict(filtered.get("refinement_policy", {})),
    )


def load_manifest_file(path: str | Path) -> SessionManifest:
    return SessionManifest.validate(path)


def to_dict(manifest: SessionManifest) -> dict[str, Any]:
    return asdict(manifest)


def to_json(manifest: SessionManifest) -> str:
    return json.dumps(to_dict(manifest), indent=2, sort_keys=True)


def manifest_to_dict(manifest: SessionManifest) -> dict[str, Any]:
    return to_dict(manifest)


def manifest_to_json(manifest: SessionManifest) -> str:
    return to_json(manifest)

