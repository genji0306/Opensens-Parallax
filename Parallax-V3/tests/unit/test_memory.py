"""Sprint 2 — Memory subsystem tests (hot / warm / cold, router, context_builder,
compaction, consolidation)."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from parallax_v3.contracts import ScopeKey
from parallax_v3.memory.compaction import ProgressiveCompactor
from parallax_v3.memory.consolidation import ConsolidationAgent
from parallax_v3.memory.context_builder import ContextBuilder
from parallax_v3.memory.router import MemoryRouter
from parallax_v3.memory.stores.cold import ColdStore, ColdStoreError
from parallax_v3.memory.stores.hot import HotStore
from parallax_v3.memory.stores.warm import WarmStore


# ---------------------------------------------------------------------------
# HotStore
# ---------------------------------------------------------------------------

def test_hot_store_set_get():
    store = HotStore(ttl_seconds=60)
    store.set("a", 123)
    assert store.get("a") == 123
    assert store.get("missing", default="fallback") == "fallback"


def test_hot_store_ttl_expiry():
    store = HotStore(ttl_seconds=0.01)
    store.set("short", "value")
    time.sleep(0.02)
    assert store.get("short") is None


def test_hot_store_clear():
    store = HotStore()
    store.set("x", 1)
    store.set("y", 2)
    assert len(store) == 2
    store.clear()
    assert len(store) == 0


# ---------------------------------------------------------------------------
# ColdStore
# ---------------------------------------------------------------------------

def test_cold_store_write_and_read(tmp_path):
    store = ColdStore(workspace_path=tmp_path, session_id="s1")
    store.write("inputs/idea.md", "my idea")
    assert store.read("inputs/idea.md") == "my idea"
    assert store.exists("inputs/idea.md")


def test_cold_store_absolute_path_rejected(tmp_path):
    store = ColdStore(workspace_path=tmp_path, session_id="s1")
    with pytest.raises(ColdStoreError):
        store.read("/etc/passwd")


def test_cold_store_escape_blocked(tmp_path):
    store = ColdStore(workspace_path=tmp_path, session_id="s1")
    with pytest.raises(ColdStoreError):
        store.read("../escape.txt")


def test_cold_store_list_and_hash(tmp_path):
    store = ColdStore(workspace_path=tmp_path, session_id="s1")
    store.write("a.txt", "one")
    store.write("nested/b.txt", "two")
    files = store.list_files("")
    assert "a.txt" in files
    assert "nested/b.txt" in files
    h = store.hash("a.txt")
    assert len(h) == 64  # sha256 hex digest


# ---------------------------------------------------------------------------
# WarmStore — semantic retrieval
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_warm_store_add_and_search(tmp_path):
    ws = WarmStore(session_id="s1", db_dir=tmp_path)
    await ws.add("k1", "sparse attention for long documents")
    await ws.add("k2", "battery electrolyte conductivity")
    await ws.add("k3", "transformer architecture improvements")
    results = await ws.search("attention mechanisms in transformers", top_k=2)
    assert len(results) == 2
    # Each result has key, score, text, scope metadata
    assert all("key" in r and "score" in r and "text" in r for r in results)
    # Scores should be in descending order
    assert results[0]["score"] >= results[1]["score"]


@pytest.mark.asyncio
async def test_warm_store_scope_filter(tmp_path):
    ws = WarmStore(session_id="s1", db_dir=tmp_path)
    await ws.add("k1", "intro text", scope="section.intro")
    await ws.add("k2", "methods text", scope="section.methods")
    results = await ws.search("anything", top_k=5, scope_filter="section.intro")
    assert all(r["scope"] == "section.intro" for r in results)


# ---------------------------------------------------------------------------
# MemoryRouter
# ---------------------------------------------------------------------------

def test_memory_router_hot_put_get():
    router = MemoryRouter()
    router.put("foo", "bar")
    assert router.get("foo") == "bar"


def test_memory_router_cold_put(tmp_path):
    cold = ColdStore(workspace_path=tmp_path, session_id="s1")
    router = MemoryRouter(cold=cold)
    router.put("file.txt", "content", tier="cold")
    assert cold.read("file.txt") == "content"


# ---------------------------------------------------------------------------
# ContextBuilder
# ---------------------------------------------------------------------------

def test_context_builder_builds_bundle(tmp_path):
    hot = HotStore()
    hot.set("outline", "1. intro")
    cold = ColdStore(workspace_path=tmp_path, session_id="s1")
    cold.write("inputs/idea.md", "novel idea")
    builder = ContextBuilder(
        scope=ScopeKey.OUTLINE,
        hot_store=hot,
        warm_summaries=["summary A", "summary B"],
        cold_store=cold,
    )
    bundle = builder.build()
    assert bundle.scope == ScopeKey.OUTLINE
    assert any("outline" in item for item in bundle.hot_items)
    assert "summary A" in bundle.warm_summaries
    assert bundle.token_estimate > 0
    assert bundle.cold_paths  # some path should be present


# ---------------------------------------------------------------------------
# ProgressiveCompactor — Pattern #5
# ---------------------------------------------------------------------------

def test_compactor_retains_newest():
    compactor = ProgressiveCompactor(retain_fraction=0.7)
    result = compactor.compact([f"item-{i}" for i in range(10)])
    # 30% compacted, 70% retained
    assert len(result.compacted) == 3
    assert len(result.retained) == 7
    assert result.retained[-1] == "item-9"  # newest retained


def test_compactor_empty():
    compactor = ProgressiveCompactor()
    result = compactor.compact([])
    assert result.retained == []
    assert result.compacted == []


# ---------------------------------------------------------------------------
# ConsolidationAgent — Pattern #4
# ---------------------------------------------------------------------------

def test_consolidation_builds_digest():
    agent = ConsolidationAgent()
    items = ["finding one", "finding two", "finding three"]
    digest = agent.consolidate("litreview", items)
    assert digest.stage_name == "litreview"
    assert digest.source_count == 3
    assert "finding" in digest.summary
    assert digest.metadata["token_estimate"] > 0
