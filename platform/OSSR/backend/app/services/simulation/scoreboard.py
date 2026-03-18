"""
OSSR Scoreboard Engine
Computes and persists research debate outcomes after each round.
All computation is rule-based (zero LLM cost).
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...db import get_connection
from ...models.orchestrator import (
    AgentInfluence,
    Coalition,
    Disagreement,
    Option,
    OptionScore,
    Scoreboard,
)
from .stance_tracker import StanceTracker

logger = logging.getLogger(__name__)


class ScoreboardEngine:
    """
    Computes scoreboard metrics from stance data, graph events, and transcript.
    Entirely rule-based — no LLM calls.
    """

    def __init__(self, simulation_id: str, options: List[Option],
                 stance_tracker: StanceTracker):
        self.simulation_id = simulation_id
        self.options = options
        self._options_map = {o.option_id: o for o in options}
        self.tracker = stance_tracker
        self._history: List[Scoreboard] = []

    def compute(self, round_num: int, agent_names: Dict[str, str],
                transcript_this_round: List[Dict[str, Any]],
                is_final: bool = False) -> Scoreboard:
        """Compute full scoreboard for a round."""

        # Option scores
        option_scores = []
        for opt in self.options:
            conf = self.tracker.compute_option_confidence(opt.option_id, round_num)
            trend = self.tracker.get_option_confidence_trend(opt.option_id)

            # Determine supporting/opposing agents
            stances = self.tracker._history.get(round_num, [])
            supporting = [s.agent_id for s in stances
                          if s.option_id == opt.option_id and s.position > 0.2]
            opposing = [s.agent_id for s in stances
                        if s.option_id == opt.option_id and s.position < -0.2]

            # Determine status
            if conf >= 0.7:
                status = "leading"
            elif conf >= 0.4:
                status = "competitive"
            elif conf >= 0.2:
                status = "declining"
            else:
                status = "eliminated"

            option_scores.append(OptionScore(
                option_id=opt.option_id, label=opt.label,
                confidence=round(conf, 3), confidence_trend=trend,
                supporting_agents=supporting, opposing_agents=opposing,
                status=status,
            ))

        # Consensus
        consensus_level = self.tracker.compute_consensus(round_num)
        consensus_trend = self.tracker.consensus_trend(round_num)

        # Coalitions
        coalitions = self.tracker.detect_coalitions(round_num)

        # Agent influence
        all_agent_ids = {s.agent_id for stances in self.tracker._history.values() for s in stances}
        agent_influence = []
        for aid in all_agent_ids:
            inf_score = self.tracker.compute_agent_influence(aid)
            consistency = self.tracker.compute_stance_consistency(aid)
            # Count citations from transcript
            citations = 0
            for turn in transcript_this_round:
                if turn.get("agent_id") == aid:
                    citations += len(turn.get("cited_dois", []))

            agent_influence.append(AgentInfluence(
                agent_id=aid, agent_name=agent_names.get(aid, aid),
                influence_score=round(inf_score, 3),
                stance_consistency=round(consistency, 3),
                evidence_citations=citations,
            ))

        # Stance shifts this round
        shifts = self.tracker.detect_shifts(round_num)
        key_shifts = [
            f"{agent_names.get(s.agent_id, s.agent_id)} shifted on "
            f"{self._options_map[s.option_id].label if s.option_id in self._options_map else s.option_id}: "
            f"{s.previous_position:+.1f} → {s.new_position:+.1f}"
            for s in shifts
        ]

        # Disagreements: find options where agents are split
        disagreements = self._detect_disagreements(round_num, agent_names)

        # Unresolved questions from graph (passed externally if available)
        scoreboard = Scoreboard(
            simulation_id=self.simulation_id,
            round_num=round_num,
            is_final=is_final,
            options=option_scores,
            consensus_level=round(consensus_level, 3),
            consensus_trend=consensus_trend,
            major_disagreements=disagreements,
            agent_influence=agent_influence,
            coalitions=coalitions,
            key_shifts_this_round=key_shifts,
        )

        self._history.append(scoreboard)
        self._persist(scoreboard)
        return scoreboard

    def _detect_disagreements(self, round_num: int,
                              agent_names: Dict[str, str]) -> List[Disagreement]:
        """Find options where agents strongly disagree."""
        stances = self.tracker._history.get(round_num, [])
        disagreements = []

        for opt in self.options:
            opt_stances = [s for s in stances if s.option_id == opt.option_id]
            supporters = [s for s in opt_stances if s.position > 0.3]
            opposers = [s for s in opt_stances if s.position < -0.3]

            if supporters and opposers:
                avg_support = sum(s.position for s in supporters) / len(supporters)
                avg_oppose = sum(s.position for s in opposers) / len(opposers)
                severity = min(1.0, (avg_support - avg_oppose) / 2.0)

                # Check how many rounds this has persisted
                rounds_active = 1
                for prev_round in range(round_num - 1, 0, -1):
                    prev_stances = self.tracker._history.get(prev_round, [])
                    prev_sup = [s for s in prev_stances
                                if s.option_id == opt.option_id and s.position > 0.3]
                    prev_opp = [s for s in prev_stances
                                if s.option_id == opt.option_id and s.position < -0.3]
                    if prev_sup and prev_opp:
                        rounds_active += 1
                    else:
                        break

                disagreements.append(Disagreement(
                    claim_a=f"Support for {opt.label}",
                    claim_b=f"Opposition to {opt.label}",
                    agents_a=[s.agent_id for s in supporters],
                    agents_b=[s.agent_id for s in opposers],
                    severity=round(severity, 3),
                    rounds_active=rounds_active,
                ))

        return disagreements

    def _persist(self, scoreboard: Scoreboard):
        conn = get_connection()
        sid = f"sb_{self.simulation_id}_{scoreboard.round_num}"
        conn.execute(
            """INSERT OR REPLACE INTO scoreboards
               (scoreboard_id, simulation_id, round_num, scoreboard_data, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (sid, self.simulation_id, scoreboard.round_num,
             json.dumps(scoreboard.to_dict()), datetime.now().isoformat()),
        )
        conn.commit()

    @staticmethod
    def load_from_db(simulation_id: str,
                     round_num: Optional[int] = None) -> List[Scoreboard]:
        conn = get_connection()
        if round_num is not None:
            rows = conn.execute(
                "SELECT scoreboard_data FROM scoreboards WHERE simulation_id = ? AND round_num = ?",
                (simulation_id, round_num),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT scoreboard_data FROM scoreboards WHERE simulation_id = ? ORDER BY round_num",
                (simulation_id,),
            ).fetchall()
        return [Scoreboard.from_dict(json.loads(r["scoreboard_data"])) for r in rows]
