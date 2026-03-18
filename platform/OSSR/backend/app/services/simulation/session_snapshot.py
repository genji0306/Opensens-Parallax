"""
OSSR Session Snapshot Service
Creates portable snapshots for research → live mode handoff.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...db import get_connection
from ...models.orchestrator import (
    DebateFrame,
    GraphSnapshot,
    Scoreboard,
    SessionSnapshot,
)
from .analyst_narrator import AnalystNarrator
from ..mapping.graph import ResearchGraphEngine
from .scoreboard import ScoreboardEngine

logger = logging.getLogger(__name__)


class SessionSnapshotService:
    """Creates and loads session snapshots for mode transitions."""

    @staticmethod
    def create_snapshot(simulation_id: str, topic: str,
                        current_round: int, max_rounds: int,
                        source_mode: str = "research") -> SessionSnapshot:
        """
        Assemble a full session snapshot from all stored components.
        """
        # Load debate frame
        frame = SessionSnapshotService._load_frame(simulation_id)

        # Load latest graph snapshot
        graph = ResearchGraphEngine.get_snapshot_from_db(simulation_id, current_round)

        # Load scoreboards
        all_scoreboards = ScoreboardEngine.load_from_db(simulation_id)
        latest_scoreboard = all_scoreboards[-1] if all_scoreboards else None

        # Load analyst feed
        feed_entries = AnalystNarrator.load_feed(simulation_id)
        round_summaries = [e.narrative for e in feed_entries]

        # Load transcript
        transcript = SessionSnapshotService._load_transcript(simulation_id)

        # Generate continuation suggestions
        suggestions = []
        if latest_scoreboard:
            for oq in latest_scoreboard.unresolved_questions[:3]:
                suggestions.append(f"Investigate: {oq}")
            for d in latest_scoreboard.major_disagreements[:2]:
                suggestions.append(f"Resolve: {d.claim_a} vs {d.claim_b}")

        open_questions = []
        if latest_scoreboard:
            open_questions = list(latest_scoreboard.unresolved_questions)

        snapshot = SessionSnapshot(
            snapshot_id="",
            simulation_id=simulation_id,
            topic=topic,
            source_mode=source_mode,
            frame=frame,
            graph=graph,
            scoreboard=latest_scoreboard,
            scoreboard_history=[sb.to_dict() for sb in all_scoreboards],
            transcript=transcript,
            round_summaries=round_summaries,
            current_round=current_round,
            max_rounds=max_rounds,
            continuation_suggestions=suggestions,
            open_questions=open_questions,
        )

        # Persist
        SessionSnapshotService._persist(snapshot)

        return snapshot

    @staticmethod
    def load_snapshot(snapshot_id: str) -> Optional[SessionSnapshot]:
        conn = get_connection()
        row = conn.execute(
            "SELECT snapshot_data FROM session_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        if not row:
            return None
        return SessionSnapshot.from_dict(json.loads(row["snapshot_data"]))

    @staticmethod
    def list_snapshots(simulation_id: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT snapshot_id, created_at FROM session_snapshots WHERE simulation_id = ? ORDER BY created_at DESC",
            (simulation_id,),
        ).fetchall()
        return [{"snapshot_id": r["snapshot_id"], "created_at": r["created_at"]} for r in rows]

    @staticmethod
    def _load_frame(simulation_id: str) -> Optional[DebateFrame]:
        conn = get_connection()
        row = conn.execute(
            "SELECT frame_data FROM debate_frames WHERE simulation_id = ?",
            (simulation_id,),
        ).fetchone()
        if not row:
            return None
        return DebateFrame.from_dict(json.loads(row["frame_data"]))

    @staticmethod
    def _load_transcript(simulation_id: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        row = conn.execute(
            "SELECT data FROM simulations WHERE simulation_id = ?",
            (simulation_id,),
        ).fetchone()
        if not row:
            return []
        sim_data = json.loads(row["data"])
        return sim_data.get("transcript", [])

    @staticmethod
    def _persist(snapshot: SessionSnapshot):
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO session_snapshots
               (snapshot_id, simulation_id, snapshot_data, created_at)
               VALUES (?, ?, ?, ?)""",
            (snapshot.snapshot_id, snapshot.simulation_id,
             json.dumps(snapshot.to_dict()), snapshot.created_at),
        )
        conn.commit()
