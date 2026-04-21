"""Sprint 6 — Gateway bridge unit tests (structure, not live HTTP)."""
from __future__ import annotations

import os

from parallax_v3.gateways.v2_bridge import V2Bridge, V2BridgeError
from parallax_v3.gateways.cost_bridge import CostBridge
from parallax_v3.gateways.bfts_bridge import BFTSBridge
from parallax_v3.gateways.review_board_bridge import ReviewBoardBridge


def test_v2_bridge_default_url():
    bridge = V2Bridge()
    assert "5002" in bridge.base_url or "localhost" in bridge.base_url


def test_v2_bridge_respects_env_override(monkeypatch):
    monkeypatch.setenv("V2_API_URL", "http://custom:9999")
    bridge = V2Bridge()
    assert bridge.base_url == "http://custom:9999"


def test_cost_bridge_instantiates():
    bridge = CostBridge()
    assert hasattr(bridge, "record")


def test_bfts_bridge_instantiates():
    bridge = BFTSBridge()
    assert bridge is not None


def test_review_board_bridge_instantiates():
    bridge = ReviewBoardBridge()
    assert bridge is not None
