"""
Paper Lab Visualization Artifact Service

Persists renderable scientific visualization assets as first-class records rather
than ephemeral upload metadata.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from ...db import get_connection


def _now() -> str:
    return datetime.now().isoformat()


class VisualizationArtifactService:
    """CRUD helpers for Paper Lab visualization artifacts."""

    def list_for_upload(self, upload_id: str) -> list[dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT * FROM paper_visualization_artifacts
            WHERE upload_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (upload_id,),
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM paper_visualization_artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def create(
        self,
        *,
        upload_id: str,
        artifact_type: str,
        intent: str,
        title: str,
        payload: dict[str, Any] | None = None,
        audit: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        status: str = "draft",
    ) -> dict[str, Any]:
        artifact_id = f"viz_{uuid.uuid4().hex[:12]}"
        now = _now()
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO paper_visualization_artifacts (
                artifact_id, upload_id, artifact_type, intent, title, status,
                version, payload_json, audit_json, provenance_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                upload_id,
                artifact_type,
                intent,
                title,
                status,
                1,
                json.dumps(payload or {}),
                json.dumps(audit or {}),
                json.dumps(provenance or {}),
                now,
                now,
            ),
        )
        conn.commit()
        return self.get(artifact_id) or {}

    def update(
        self,
        artifact_id: str,
        *,
        title: str | None = None,
        status: str | None = None,
        payload_patch: dict[str, Any] | None = None,
        audit_patch: dict[str, Any] | None = None,
        provenance_patch: dict[str, Any] | None = None,
        increment_version: bool = False,
    ) -> dict[str, Any] | None:
        current = self.get(artifact_id)
        if not current:
            return None

        payload = {**(current.get("payload") or {}), **(payload_patch or {})}
        audit = {**(current.get("audit") or {}), **(audit_patch or {})}
        provenance = {**(current.get("provenance") or {}), **(provenance_patch or {})}
        version = int(current.get("version") or 1) + (1 if increment_version else 0)

        conn = get_connection()
        conn.execute(
            """
            UPDATE paper_visualization_artifacts
            SET title = ?, status = ?, version = ?, payload_json = ?, audit_json = ?,
                provenance_json = ?, updated_at = ?
            WHERE artifact_id = ?
            """,
            (
                title if title is not None else current.get("title", ""),
                status if status is not None else current.get("status", "draft"),
                version,
                json.dumps(payload),
                json.dumps(audit),
                json.dumps(provenance),
                _now(),
                artifact_id,
            ),
        )
        conn.commit()
        return self.get(artifact_id)

    def create_or_replace_by_title(
        self,
        *,
        upload_id: str,
        artifact_type: str,
        intent: str,
        title: str,
        payload: dict[str, Any] | None = None,
        audit: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        status: str = "draft",
    ) -> dict[str, Any]:
        conn = get_connection()
        row = conn.execute(
            """
            SELECT artifact_id FROM paper_visualization_artifacts
            WHERE upload_id = ? AND artifact_type = ? AND title = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (upload_id, artifact_type, title),
        ).fetchone()
        if not row:
            return self.create(
                upload_id=upload_id,
                artifact_type=artifact_type,
                intent=intent,
                title=title,
                payload=payload,
                audit=audit,
                provenance=provenance,
                status=status,
            )
        return self.update(
            row["artifact_id"],
            title=title,
            status=status,
            payload_patch=payload,
            audit_patch=audit,
            provenance_patch=provenance,
            increment_version=True,
        ) or {}

    def _row_to_dict(self, row: Any) -> dict[str, Any]:
        payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
        audit = json.loads(row["audit_json"]) if row["audit_json"] else {}
        provenance = json.loads(row["provenance_json"]) if row["provenance_json"] else {}
        return {
            "artifact_id": row["artifact_id"],
            "upload_id": row["upload_id"],
            "type": row["artifact_type"],
            "intent": row["intent"],
            "title": row["title"],
            "status": row["status"],
            "version": row["version"],
            "payload": payload,
            "audit": audit,
            "provenance": provenance,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
