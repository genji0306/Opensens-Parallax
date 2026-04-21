"""Refinement halt rule helper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ...contracts import RefinementState


def evaluate_halt(
    state: RefinementState,
    overall_new: float,
    overall_prev: float,
    net_subaxis_delta: float,
    plateau_threshold: float = 1.0,
    plateau_window: int = 2,
    iter_cap: int | None = None,
) -> RefinementState:
    if iter_cap is not None and state.iteration >= iter_cap:
        state.verdict = "halt_cap"
        return state
    if overall_new > overall_prev or (overall_new == overall_prev and net_subaxis_delta >= 0):
        state.verdict = "accept"
        state.plateau_count = 0
        return state
    if abs(overall_new - overall_prev) < plateau_threshold:
        state.plateau_count += 1
        if state.plateau_count >= plateau_window:
            state.verdict = "halt_plateau"
            return state
    state.verdict = "revert"
    return state


