"""
OSSR Analyst Narrator
Generates human-readable explanations of what changed in the graph and debate.
Uses a cheap LLM model (Haiku) for narration.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...db import get_connection
from ...models.orchestrator import (
    AnalystFeedEntry,
    GraphEvent,
    Scoreboard,
)

logger = logging.getLogger(__name__)


class AnalystNarrator:
    """
    Generates per-round narrative explanations of debate dynamics.
    Explains *why the graph changed*, not just what agents said.
    """

    def __init__(self, simulation_id: str):
        self.simulation_id = simulation_id

    def narrate_round(self, round_num: int,
                      scoreboard: Scoreboard,
                      graph_events: List[GraphEvent],
                      shifts: List[Dict[str, Any]],
                      agent_names: Dict[str, str],
                      llm_client=None) -> AnalystFeedEntry:
        """
        Generate a narrative for a completed round.
        Uses LLM if available, otherwise falls back to rule-based summary.
        """
        key_events = self._extract_key_events(graph_events, scoreboard, shifts, agent_names)

        if llm_client:
            narrative = self._llm_narrate(
                round_num, scoreboard, key_events, agent_names, llm_client,
            )
        else:
            narrative = self._rule_based_narrate(
                round_num, scoreboard, key_events, agent_names,
            )

        entry = AnalystFeedEntry(
            feed_id="", simulation_id=self.simulation_id,
            round_num=round_num, narrative=narrative,
            key_events=key_events,
        )

        self._persist(entry)
        return entry

    def _extract_key_events(self, graph_events: List[GraphEvent],
                            scoreboard: Scoreboard,
                            shifts: List[Dict[str, Any]],
                            agent_names: Dict[str, str]) -> List[str]:
        """Extract top key events from graph changes and scoreboard."""
        events = []

        # Count graph mutations
        new_claims = sum(1 for e in graph_events
                         if e.event_type.value == "node_added"
                         and e.payload.get("node_type") == "claim")
        new_questions = sum(1 for e in graph_events
                            if e.event_type.value == "question_raised")
        new_edges = sum(1 for e in graph_events if e.event_type.value == "edge_added")

        if new_claims:
            events.append(f"{new_claims} new claim(s) introduced")
        if new_questions:
            events.append(f"{new_questions} new question(s) raised")
        if new_edges:
            events.append(f"{new_edges} new relationship(s) added to graph")

        # Stance shifts
        for s in shifts:
            name = agent_names.get(s.get("agent_id", ""), s.get("agent_id", ""))
            events.append(
                f"{name} shifted stance: {s.get('previous_position', 0):+.1f} → {s.get('new_position', 0):+.1f}"
            )

        # Leading option changes
        for opt in scoreboard.options:
            if opt.status == "leading":
                events.append(f"Leading option: {opt.label} ({opt.confidence:.0%})")

        # Consensus
        events.append(f"Consensus: {scoreboard.consensus_level:.0%} ({scoreboard.consensus_trend})")

        # Coalitions
        for c in scoreboard.coalitions:
            names = [agent_names.get(a, a) for a in c.agent_ids[:3]]
            events.append(f"Coalition formed: {', '.join(names)}")

        return events[:10]  # Cap at 10

    def _rule_based_narrate(self, round_num: int,
                            scoreboard: Scoreboard,
                            key_events: List[str],
                            agent_names: Dict[str, str]) -> str:
        """Generate narrative without LLM (free)."""
        parts = [f"**Round {round_num} Summary**\n"]

        # Leading options
        leading = [o for o in scoreboard.options if o.status == "leading"]
        competitive = [o for o in scoreboard.options if o.status == "competitive"]
        if leading:
            labels = ", ".join(f"{o.label} ({o.confidence:.0%})" for o in leading)
            parts.append(f"Leading option(s): {labels}.")
        if competitive:
            labels = ", ".join(f"{o.label} ({o.confidence:.0%})" for o in competitive)
            parts.append(f"Still competitive: {labels}.")

        # Consensus
        parts.append(
            f"Overall consensus is at {scoreboard.consensus_level:.0%} "
            f"and {scoreboard.consensus_trend}."
        )

        # Shifts
        if scoreboard.key_shifts_this_round:
            parts.append("Key shifts: " + "; ".join(scoreboard.key_shifts_this_round[:3]) + ".")

        # Disagreements
        if scoreboard.major_disagreements:
            d = scoreboard.major_disagreements[0]
            parts.append(
                f"Main disagreement: {d.claim_a} vs {d.claim_b} "
                f"(severity {d.severity:.0%}, active {d.rounds_active} round(s))."
            )

        # Coalitions
        if scoreboard.coalitions:
            c = scoreboard.coalitions[0]
            names = [agent_names.get(a, a) for a in c.agent_ids[:3]]
            parts.append(f"Coalition: {', '.join(names)} (strength {c.strength:.0%}).")

        return " ".join(parts)

    def _llm_narrate(self, round_num: int,
                     scoreboard: Scoreboard,
                     key_events: List[str],
                     agent_names: Dict[str, str],
                     llm_client) -> str:
        """Generate richer narrative using a cheap LLM model."""
        prompt = (
            f"You are an analyst narrator for a research debate simulation. "
            f"Write a concise 2-3 sentence summary of Round {round_num}.\n\n"
            f"Key events this round:\n"
            + "\n".join(f"- {e}" for e in key_events) +
            f"\n\nConsensus: {scoreboard.consensus_level:.0%} ({scoreboard.consensus_trend})\n"
            f"Options: "
            + ", ".join(f"{o.label}: {o.confidence:.0%} ({o.status})" for o in scoreboard.options)
            + "\n\nExplain *why* the state changed, not just what happened. "
            f"Focus on the most important dynamic shift. Be specific about agent names and evidence."
        )
        try:
            return llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4, max_tokens=300,
            )
        except Exception as e:
            logger.warning(f"LLM narration failed: {e}")
            return self._rule_based_narrate(round_num, scoreboard, key_events, agent_names)

    def _persist(self, entry: AnalystFeedEntry):
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO analyst_feed
               (feed_id, simulation_id, round_num, narrative, key_events, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entry.feed_id, entry.simulation_id, entry.round_num,
             entry.narrative, json.dumps(entry.key_events), entry.created_at),
        )
        conn.commit()

    @staticmethod
    def load_feed(simulation_id: str,
                  max_round: Optional[int] = None) -> List[AnalystFeedEntry]:
        conn = get_connection()
        if max_round is not None:
            rows = conn.execute(
                "SELECT * FROM analyst_feed WHERE simulation_id = ? AND round_num <= ? ORDER BY round_num",
                (simulation_id, max_round),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM analyst_feed WHERE simulation_id = ? ORDER BY round_num",
                (simulation_id,),
            ).fetchall()
        return [
            AnalystFeedEntry(
                feed_id=r["feed_id"], simulation_id=r["simulation_id"],
                round_num=r["round_num"], narrative=r["narrative"],
                key_events=json.loads(r["key_events"]), created_at=r["created_at"],
            )
            for r in rows
        ]
