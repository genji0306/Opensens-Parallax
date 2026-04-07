"""
Multi-rollout → rubric-aggregate helper (UniScientist pattern).

The idea is simple: for agents whose output quality varies run-to-run
(ideation, hypothesis, review), we run the same function N times with
perturbed temperature, score each candidate with a rubric, and return the
winner plus all candidates so the caller can display the runner-up set.

Usage::

    def _one():
        return idea_generator.run({"topic": topic})

    best = rollout_and_aggregate(_one, n=3, rubric=rubric_fn)

``rubric`` receives the ``AgentResult`` of each rollout and must return a
float score. The default rubric uses the candidate's own ``confidence`` or
``score`` field if present, else 0.5. Failed rollouts are skipped unless
every rollout failed, in which case the last failure is returned.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from .base import AgentResult

logger = logging.getLogger(__name__)


@dataclass
class RolloutCandidate:
    result: AgentResult
    score: float = 0.0
    rank: int = 0
    metadata: dict = field(default_factory=dict)


def _default_rubric(result: AgentResult) -> float:
    if not result.ok or result.data is None:
        return 0.0
    data = result.data
    # Prefer explicit score-like fields if present
    if isinstance(data, dict):
        for key in ("score", "quality", "confidence", "overall_score"):
            value = data.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        # If there's a list of items with their own scores, average them
        for key in ("items", "ideas", "claims", "annotations"):
            items = data.get(key)
            if isinstance(items, list) and items:
                scores = [
                    float(it.get("score", it.get("confidence", 0.5)))
                    for it in items
                    if isinstance(it, dict)
                ]
                if scores:
                    return sum(scores) / len(scores)
    return 0.5


def rollout_and_aggregate(
    fn: Callable[[], AgentResult],
    *,
    n: int = 3,
    rubric: Optional[Callable[[AgentResult], float]] = None,
    temperature_jitter: Optional[List[float]] = None,
    keep_all: bool = True,
) -> AgentResult:
    """
    Run ``fn`` up to ``n`` times, score each result with ``rubric``, return
    the top candidate as an ``AgentResult`` with all candidates attached on
    ``rollouts``.

    Parameters
    ----------
    fn
        Zero-arg callable that returns an :class:`AgentResult`. Use a closure
        to pass your inputs. The caller is responsible for varying temperature
        between calls (or let the agent's own default jitter handle it).
    n
        Number of rollouts.
    rubric
        Scoring function. Defaults to a best-effort scorer that looks for
        ``score``/``confidence`` fields.
    keep_all
        When True, attach every candidate's result dict to the winner's
        ``rollouts`` list so the UI can show runner-ups.
    """
    if n < 1:
        n = 1
    rubric = rubric or _default_rubric

    candidates: List[RolloutCandidate] = []
    last_failure: Optional[AgentResult] = None

    for i in range(n):
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[rollout] rollout %d raised: %s", i + 1, exc)
            last_failure = AgentResult(ok=False, error=str(exc))
            continue

        if not isinstance(result, AgentResult):
            logger.warning("[rollout] rollout %d returned non-AgentResult", i + 1)
            continue

        if not result.ok:
            last_failure = result
            continue

        score = 0.0
        try:
            score = float(rubric(result))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[rollout] rubric raised for rollout %d: %s", i + 1, exc)

        candidates.append(RolloutCandidate(result=result, score=score))

    if not candidates:
        return last_failure or AgentResult(ok=False, error="all_rollouts_failed")

    candidates.sort(key=lambda c: c.score, reverse=True)
    for idx, cand in enumerate(candidates):
        cand.rank = idx

    winner = candidates[0].result
    if keep_all:
        winner.rollouts = [
            {
                "rank": c.rank,
                "score": c.score,
                "data": c.result.data,
                "model": c.result.model,
                "duration_ms": c.result.duration_ms,
            }
            for c in candidates
        ]
    winner.metadata.setdefault("rollout_n", len(candidates))
    winner.metadata.setdefault("rollout_winner_score", candidates[0].score)
    return winner
