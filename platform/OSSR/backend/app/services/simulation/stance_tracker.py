"""
OSSR Stance Tracker
Tracks agent positions on options across debate rounds.
Detects shifts, coalitions, and convergence.
"""

import json
import logging
import math
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ...db import get_connection
from ...models.orchestrator import (
    AgentStance,
    AgentStanceShift,
    Coalition,
    Option,
)

logger = logging.getLogger(__name__)


class StanceTracker:
    """
    Tracks each agent's position on each option across rounds.
    Provides shift detection, coalition detection, and convergence metrics.
    All operations are rule-based (no LLM calls).
    """

    def __init__(self, simulation_id: str, options: List[Option]):
        self.simulation_id = simulation_id
        self.options = {o.option_id: o for o in options}
        self._history: Dict[int, List[AgentStance]] = {}  # round_num → stances

    # ── Record Stances ───────────────────────────────────────────────

    def record_stances(self, round_num: int, stances: List[AgentStance]):
        """Record stances for a round and persist to DB."""
        self._history[round_num] = stances
        self._persist_stances(stances)

    def record_stance_from_response(self, agent_id: str, round_num: int,
                                    structured_response: Dict[str, Any]):
        """Extract and record stances from a structured agent response."""
        stances = []
        for s in structured_response.get("stances", []):
            option_id = s.get("option_id", "")
            if option_id not in self.options:
                continue
            stance = AgentStance(
                agent_id=agent_id, option_id=option_id,
                round_num=round_num,
                position=max(-1.0, min(1.0, float(s.get("position", 0.0)))),
                confidence=max(0.0, min(1.0, float(s.get("confidence", 0.5)))),
                reasoning=s.get("reasoning", ""),
            )
            stances.append(stance)
            self._persist_stance(stance)

        # Merge into round history
        existing = self._history.get(round_num, [])
        existing.extend(stances)
        self._history[round_num] = existing
        return stances

    # ── Shift Detection ──────────────────────────────────────────────

    def detect_shifts(self, round_num: int, threshold: float = 0.2) -> List[AgentStanceShift]:
        """Detect stance shifts between this round and the previous round."""
        if round_num < 2:
            return []

        prev_stances = self._history.get(round_num - 1, [])
        curr_stances = self._history.get(round_num, [])

        prev_map: Dict[Tuple[str, str], AgentStance] = {
            (s.agent_id, s.option_id): s for s in prev_stances
        }
        shifts = []
        for cs in curr_stances:
            key = (cs.agent_id, cs.option_id)
            ps = prev_map.get(key)
            if ps and abs(cs.position - ps.position) >= threshold:
                shifts.append(AgentStanceShift(
                    agent_id=cs.agent_id, option_id=cs.option_id,
                    previous_position=ps.position, new_position=cs.position,
                    reason=cs.reasoning,
                ))
        return shifts

    # ── Consensus Measurement ────────────────────────────────────────

    def compute_consensus(self, round_num: int) -> float:
        """
        Compute consensus level for a round.
        0.0 = total disagreement, 1.0 = full consensus.
        Based on inverse of average position variance across options.
        """
        stances = self._history.get(round_num, [])
        if not stances:
            return 0.0

        variances = []
        for option_id in self.options:
            positions = [s.position for s in stances if s.option_id == option_id]
            if len(positions) > 1:
                mean = sum(positions) / len(positions)
                var = sum((p - mean) ** 2 for p in positions) / len(positions)
                variances.append(math.sqrt(var))  # stdev
            elif len(positions) == 1:
                variances.append(0.0)

        if not variances:
            return 0.0

        avg_stdev = sum(variances) / len(variances)
        # Normalize: max possible stdev on [-1, 1] range is 1.0
        return max(0.0, 1.0 - avg_stdev)

    def consensus_trend(self, round_num: int) -> str:
        """Determine if consensus is converging, diverging, or stable."""
        if round_num < 2:
            return "stable"
        curr = self.compute_consensus(round_num)
        prev = self.compute_consensus(round_num - 1)
        diff = curr - prev
        if diff > 0.05:
            return "converging"
        elif diff < -0.05:
            return "diverging"
        return "stable"

    # ── Coalition Detection ──────────────────────────────────────────

    def detect_coalitions(self, round_num: int, threshold: float = 0.7) -> List[Coalition]:
        """
        Find groups of agents with similar stance vectors.
        Uses cosine similarity on stance vectors.
        """
        stances = self._history.get(round_num, [])
        if not stances:
            return []

        # Build per-agent stance vectors
        agent_ids = list({s.agent_id for s in stances})
        option_ids = sorted(self.options.keys())

        if len(agent_ids) < 2 or not option_ids:
            return []

        vectors: Dict[str, List[float]] = {}
        for aid in agent_ids:
            vec = []
            for oid in option_ids:
                matching = [s for s in stances if s.agent_id == aid and s.option_id == oid]
                vec.append(matching[0].position if matching else 0.0)
            vectors[aid] = vec

        # Simple pairwise clustering
        coalitions = []
        used = set()
        for i, a1 in enumerate(agent_ids):
            if a1 in used:
                continue
            group = [a1]
            for a2 in agent_ids[i + 1:]:
                if a2 in used:
                    continue
                sim = self._cosine_similarity(vectors[a1], vectors[a2])
                if sim >= threshold:
                    group.append(a2)
                    used.add(a2)
            if len(group) > 1:
                used.add(a1)
                # Find shared positions (options where all group members agree in direction)
                shared = []
                for oid in option_ids:
                    positions = []
                    for aid in group:
                        matching = [s for s in stances if s.agent_id == aid and s.option_id == oid]
                        if matching:
                            positions.append(matching[0].position)
                    if positions and all(p > 0.2 for p in positions):
                        shared.append(oid)
                    elif positions and all(p < -0.2 for p in positions):
                        shared.append(oid)

                coalitions.append(Coalition(
                    coalition_id=f"coal_{uuid.uuid4().hex[:8]}",
                    agent_ids=group, shared_positions=shared,
                    formed_at_round=round_num,
                    strength=self._avg_similarity(group, vectors),
                ))

        return coalitions

    # ── Option Confidence ────────────────────────────────────────────

    def compute_option_confidence(self, option_id: str, round_num: int) -> float:
        """Weighted average of agent positions on an option, normalized to 0-1."""
        stances = [s for s in self._history.get(round_num, []) if s.option_id == option_id]
        if not stances:
            return 0.5

        weighted_sum = sum(s.position * s.confidence for s in stances)
        weight_total = sum(s.confidence for s in stances)
        if weight_total == 0:
            return 0.5

        raw = weighted_sum / weight_total  # -1 to +1
        return (raw + 1) / 2  # normalize to 0-1

    def get_option_confidence_trend(self, option_id: str) -> List[float]:
        """Get confidence values for an option across all recorded rounds."""
        rounds = sorted(self._history.keys())
        return [self.compute_option_confidence(option_id, r) for r in rounds]

    # ── Agent Influence ──────────────────────────────────────────────

    def compute_agent_influence(self, agent_id: str) -> float:
        """
        How much did other agents shift toward this agent's positions?
        Returns 0.0-1.0.
        """
        rounds = sorted(self._history.keys())
        if len(rounds) < 2:
            return 0.0

        influence_events = 0
        total_opportunities = 0

        for i in range(1, len(rounds)):
            prev_round = rounds[i - 1]
            curr_round = rounds[i]
            prev_stances = self._history.get(prev_round, [])
            curr_stances = self._history.get(curr_round, [])

            # Get this agent's previous positions
            agent_prev = {s.option_id: s.position for s in prev_stances if s.agent_id == agent_id}

            other_agents = {s.agent_id for s in curr_stances if s.agent_id != agent_id}
            for other_id in other_agents:
                for option_id, agent_pos in agent_prev.items():
                    prev_other = [s for s in prev_stances
                                  if s.agent_id == other_id and s.option_id == option_id]
                    curr_other = [s for s in curr_stances
                                  if s.agent_id == other_id and s.option_id == option_id]
                    if prev_other and curr_other:
                        total_opportunities += 1
                        old_dist = abs(prev_other[0].position - agent_pos)
                        new_dist = abs(curr_other[0].position - agent_pos)
                        if new_dist < old_dist - 0.1:
                            influence_events += 1

        return min(1.0, influence_events / max(1, total_opportunities))

    def compute_stance_consistency(self, agent_id: str) -> float:
        """How stable were the agent's positions across rounds? 0=volatile, 1=consistent."""
        rounds = sorted(self._history.keys())
        if len(rounds) < 2:
            return 1.0

        total_shift = 0.0
        count = 0
        for i in range(1, len(rounds)):
            prev = {s.option_id: s.position for s in self._history.get(rounds[i - 1], [])
                    if s.agent_id == agent_id}
            curr = {s.option_id: s.position for s in self._history.get(rounds[i], [])
                    if s.agent_id == agent_id}
            for oid in set(prev) & set(curr):
                total_shift += abs(curr[oid] - prev[oid])
                count += 1

        if count == 0:
            return 1.0
        avg_shift = total_shift / count
        return max(0.0, 1.0 - avg_shift)

    # ── Persistence ──────────────────────────────────────────────────

    def _persist_stance(self, stance: AgentStance):
        conn = get_connection()
        stance_id = f"st_{self.simulation_id}_{stance.agent_id}_{stance.option_id}_{stance.round_num}"
        conn.execute(
            """INSERT OR REPLACE INTO agent_stances
               (stance_id, simulation_id, agent_id, option_id, round_num, position, confidence, reasoning)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (stance_id, self.simulation_id, stance.agent_id, stance.option_id,
             stance.round_num, stance.position, stance.confidence, stance.reasoning),
        )
        conn.commit()

    def _persist_stances(self, stances: List[AgentStance]):
        for s in stances:
            self._persist_stance(s)

    def load_history(self) -> Dict[int, List[AgentStance]]:
        """Load all stance history from DB."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM agent_stances WHERE simulation_id = ? ORDER BY round_num",
            (self.simulation_id,),
        ).fetchall()
        history: Dict[int, List[AgentStance]] = {}
        for r in rows:
            stance = AgentStance(
                agent_id=r["agent_id"], option_id=r["option_id"],
                round_num=r["round_num"], position=r["position"],
                confidence=r["confidence"], reasoning=r["reasoning"],
            )
            history.setdefault(r["round_num"], []).append(stance)
        self._history = history
        return history

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x ** 2 for x in a))
        mag_b = math.sqrt(sum(x ** 2 for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def _avg_similarity(self, group: List[str],
                        vectors: Dict[str, List[float]]) -> float:
        if len(group) < 2:
            return 1.0
        sims = []
        for i, a1 in enumerate(group):
            for a2 in group[i + 1:]:
                sims.append(self._cosine_similarity(vectors[a1], vectors[a2]))
        return sum(sims) / len(sims) if sims else 0.0
