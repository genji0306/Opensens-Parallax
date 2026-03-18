"""
OSSR Research Graph Engine
Event-sourced knowledge graph that evolves during debate rounds.
Manages nodes, edges, clusters, events, and snapshots.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...db import get_connection
from ...models.orchestrator import (
    Cluster,
    GraphEdge,
    GraphEvent,
    GraphEventType,
    GraphNode,
    GraphSnapshot,
    NodeType,
    RelationType,
)

logger = logging.getLogger(__name__)


class ResearchGraphEngine:
    """
    Manages the evolving knowledge graph for a simulation.
    All mutations are recorded as immutable events.
    Snapshots are stored per round for zero-cost replay.
    """

    def __init__(self, simulation_id: str):
        self.simulation_id = simulation_id
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: Dict[str, GraphEdge] = {}
        self._clusters: Dict[str, Cluster] = {}
        self._pending_events: List[GraphEvent] = []

    # ── Node Operations ──────────────────────────────────────────────

    def add_node(self, node: GraphNode, round_num: int, turn_id: Optional[int] = None) -> GraphNode:
        node.created_at_round = round_num
        self._nodes[node.node_id] = node
        self._pending_events.append(GraphEvent(
            event_id="", simulation_id=self.simulation_id,
            round_num=round_num, event_type=GraphEventType.NODE_ADDED,
            payload=node.to_dict(), turn_id=turn_id,
        ))
        return node

    def update_node(self, node_id: str, updates: Dict[str, Any],
                    round_num: int, turn_id: Optional[int] = None) -> Optional[GraphNode]:
        node = self._nodes.get(node_id)
        if not node:
            return None
        for key, value in updates.items():
            if hasattr(node, key):
                setattr(node, key, value)
        self._pending_events.append(GraphEvent(
            event_id="", simulation_id=self.simulation_id,
            round_num=round_num, event_type=GraphEventType.NODE_UPDATED,
            payload={"node_id": node_id, "updates": updates}, turn_id=turn_id,
        ))
        return node

    def remove_node(self, node_id: str, round_num: int, turn_id: Optional[int] = None) -> bool:
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        # Remove edges referencing this node
        dead_edges = [eid for eid, e in self._edges.items()
                      if e.source_id == node_id or e.target_id == node_id]
        for eid in dead_edges:
            del self._edges[eid]
        self._pending_events.append(GraphEvent(
            event_id="", simulation_id=self.simulation_id,
            round_num=round_num, event_type=GraphEventType.NODE_REMOVED,
            payload={"node_id": node_id}, turn_id=turn_id,
        ))
        return True

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self._nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> List[GraphNode]:
        return [n for n in self._nodes.values() if n.node_type == node_type]

    # ── Edge Operations ──────────────────────────────────────────────

    def add_edge(self, edge: GraphEdge, round_num: int, turn_id: Optional[int] = None) -> GraphEdge:
        edge.created_at_round = round_num
        self._edges[edge.edge_id] = edge
        self._pending_events.append(GraphEvent(
            event_id="", simulation_id=self.simulation_id,
            round_num=round_num, event_type=GraphEventType.EDGE_ADDED,
            payload=edge.to_dict(), turn_id=turn_id,
        ))
        return edge

    def update_edge(self, edge_id: str, updates: Dict[str, Any],
                    round_num: int, turn_id: Optional[int] = None) -> Optional[GraphEdge]:
        edge = self._edges.get(edge_id)
        if not edge:
            return None
        for key, value in updates.items():
            if hasattr(edge, key):
                setattr(edge, key, value)
        self._pending_events.append(GraphEvent(
            event_id="", simulation_id=self.simulation_id,
            round_num=round_num, event_type=GraphEventType.EDGE_UPDATED,
            payload={"edge_id": edge_id, "updates": updates}, turn_id=turn_id,
        ))
        return edge

    def find_edge(self, source_id: str, target_id: str,
                  relation: Optional[RelationType] = None) -> Optional[GraphEdge]:
        for e in self._edges.values():
            if e.source_id == source_id and e.target_id == target_id:
                if relation is None or e.relation == relation:
                    return e
        return None

    def get_edges_for_node(self, node_id: str) -> List[GraphEdge]:
        return [e for e in self._edges.values()
                if e.source_id == node_id or e.target_id == node_id]

    # ── Cluster Operations ───────────────────────────────────────────

    def form_cluster(self, label: str, node_ids: List[str],
                     round_num: int) -> Cluster:
        cluster = Cluster(
            cluster_id=f"cl_{uuid.uuid4().hex[:8]}",
            label=label, node_ids=node_ids, formed_at_round=round_num,
        )
        self._clusters[cluster.cluster_id] = cluster
        for nid in node_ids:
            node = self._nodes.get(nid)
            if node:
                node.cluster_id = cluster.cluster_id
        self._pending_events.append(GraphEvent(
            event_id="", simulation_id=self.simulation_id,
            round_num=round_num, event_type=GraphEventType.CLUSTER_FORMED,
            payload=cluster.to_dict(),
        ))
        return cluster

    # ── Snapshot & Persistence ───────────────────────────────────────

    def take_snapshot(self, round_num: int) -> GraphSnapshot:
        """Create a snapshot of current graph state and persist it + events."""
        events = list(self._pending_events)
        self._pending_events.clear()

        snapshot = GraphSnapshot(
            simulation_id=self.simulation_id,
            round_num=round_num,
            nodes=list(self._nodes.values()),
            edges=list(self._edges.values()),
            clusters=list(self._clusters.values()),
            events_since_last=events,
        )

        # Persist to DB
        self._persist_snapshot(snapshot)
        self._persist_events(events)

        return snapshot

    def _persist_snapshot(self, snapshot: GraphSnapshot):
        conn = get_connection()
        snapshot_id = f"gs_{self.simulation_id}_{snapshot.round_num}"
        conn.execute(
            """INSERT OR REPLACE INTO graph_snapshots
               (snapshot_id, simulation_id, round_num, nodes, edges, clusters, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot_id, self.simulation_id, snapshot.round_num,
                json.dumps([n.to_dict() for n in snapshot.nodes]),
                json.dumps([e.to_dict() for e in snapshot.edges]),
                json.dumps([c.to_dict() for c in snapshot.clusters]),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()

    def _persist_events(self, events: List[GraphEvent]):
        if not events:
            return
        conn = get_connection()
        for ev in events:
            conn.execute(
                """INSERT OR IGNORE INTO graph_events
                   (event_id, simulation_id, round_num, turn_id, event_type, payload, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    ev.event_id, ev.simulation_id, ev.round_num,
                    ev.turn_id, ev.event_type.value if isinstance(ev.event_type, GraphEventType) else ev.event_type,
                    json.dumps(ev.payload), ev.timestamp,
                ),
            )
        conn.commit()

    # ── Load from DB ─────────────────────────────────────────────────

    def load_snapshot(self, round_num: int) -> Optional[GraphSnapshot]:
        """Load a graph snapshot from DB and restore in-memory state."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM graph_snapshots WHERE simulation_id = ? AND round_num = ?",
            (self.simulation_id, round_num),
        ).fetchone()
        if not row:
            return None

        nodes = [GraphNode.from_dict(n) for n in json.loads(row["nodes"])]
        edges = [GraphEdge.from_dict(e) for e in json.loads(row["edges"])]
        clusters = [Cluster.from_dict(c) for c in json.loads(row["clusters"])]

        # Restore in-memory state
        self._nodes = {n.node_id: n for n in nodes}
        self._edges = {e.edge_id: e for e in edges}
        self._clusters = {c.cluster_id: c for c in clusters}

        return GraphSnapshot(
            simulation_id=self.simulation_id,
            round_num=round_num,
            nodes=nodes, edges=edges, clusters=clusters,
        )

    @staticmethod
    def get_snapshot_from_db(simulation_id: str, round_num: int) -> Optional[GraphSnapshot]:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM graph_snapshots WHERE simulation_id = ? AND round_num = ?",
            (simulation_id, round_num),
        ).fetchone()
        if not row:
            return None
        return GraphSnapshot(
            simulation_id=simulation_id,
            round_num=round_num,
            nodes=[GraphNode.from_dict(n) for n in json.loads(row["nodes"])],
            edges=[GraphEdge.from_dict(e) for e in json.loads(row["edges"])],
            clusters=[Cluster.from_dict(c) for c in json.loads(row["clusters"])],
        )

    @staticmethod
    def get_events_from_db(simulation_id: str,
                           round_num: Optional[int] = None) -> List[GraphEvent]:
        conn = get_connection()
        if round_num is not None:
            rows = conn.execute(
                "SELECT * FROM graph_events WHERE simulation_id = ? AND round_num = ? ORDER BY timestamp",
                (simulation_id, round_num),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM graph_events WHERE simulation_id = ? ORDER BY round_num, timestamp",
                (simulation_id,),
            ).fetchall()
        return [
            GraphEvent(
                event_id=r["event_id"], simulation_id=r["simulation_id"],
                round_num=r["round_num"], event_type=GraphEventType(r["event_type"]),
                payload=json.loads(r["payload"]), turn_id=r["turn_id"],
                timestamp=r["timestamp"],
            )
            for r in rows
        ]

    # ── Graph Mutation from Agent Response ───────────────────────────

    def apply_agent_claims(self, agent_id: str, round_num: int, turn_id: int,
                           structured_response: Dict[str, Any]):
        """
        Apply structured claims from an agent's response to the graph.
        Expected structured_response format:
        {
            "claims": [{"text": "...", "claim_type": "supports|contradicts", "target_option": "opt_id", "evidence_doi": "..."}],
            "open_questions": ["..."],
            "stances": [{"option_id": "...", "position": 0.7, "confidence": 0.8}]
        }
        """
        claims = structured_response.get("claims", [])
        for claim_data in claims:
            claim_text = claim_data.get("text", "")
            if not claim_text:
                continue

            # Create claim node
            claim_node = GraphNode(
                node_id="", node_type=NodeType.CLAIM,
                label=claim_text[:100],
                metadata={"full_text": claim_text, "source_agent": agent_id},
                confidence=0.5, weight=1.0,
            )
            self.add_node(claim_node, round_num, turn_id)

            # Link claim to agent
            agent_node_id = f"agent_{agent_id}"
            if agent_node_id in self._nodes:
                rel = RelationType.PROPOSES_OPTION
                self.add_edge(GraphEdge(
                    edge_id="", source_id=agent_node_id, target_id=claim_node.node_id,
                    relation=rel, weight=1.0,
                    evidence=f"Proposed in round {round_num}",
                ), round_num, turn_id)

            # Link claim to target option
            target_option = claim_data.get("target_option", "")
            if target_option and target_option in self._nodes:
                claim_type = claim_data.get("claim_type", "supports")
                rel = RelationType.SUPPORTS if claim_type == "supports" else RelationType.CONTRADICTS
                self.add_edge(GraphEdge(
                    edge_id="", source_id=claim_node.node_id,
                    target_id=target_option, relation=rel,
                    weight=1.0, evidence=claim_text[:200],
                ), round_num, turn_id)

            # Link to cited paper if DOI provided
            evidence_doi = claim_data.get("evidence_doi", "")
            if evidence_doi:
                # Find paper node or create evidence reference
                paper_nodes = [n for n in self._nodes.values()
                               if n.node_type == NodeType.PAPER
                               and n.metadata.get("doi") == evidence_doi]
                if paper_nodes:
                    self.add_edge(GraphEdge(
                        edge_id="", source_id=claim_node.node_id,
                        target_id=paper_nodes[0].node_id,
                        relation=RelationType.CITES, weight=1.0,
                    ), round_num, turn_id)

        # Process open questions
        for q_text in structured_response.get("open_questions", []):
            if q_text:
                q_node = GraphNode(
                    node_id="", node_type=NodeType.OPEN_QUESTION,
                    label=q_text[:100],
                    metadata={"full_text": q_text, "source_agent": agent_id},
                    weight=0.8,
                )
                self.add_node(q_node, round_num, turn_id)
                self._pending_events.append(GraphEvent(
                    event_id="", simulation_id=self.simulation_id,
                    round_num=round_num, event_type=GraphEventType.QUESTION_RAISED,
                    payload={"question": q_text, "agent_id": agent_id},
                    turn_id=turn_id,
                ))

    def seed_from_frame(self, frame, round_num: int = 0):
        """Seed the graph from a DebateFrame's options and initial structure."""
        # Add option nodes
        for opt in frame.options:
            node = GraphNode(
                node_id=opt.option_id, node_type=NodeType.OPTION,
                label=opt.label,
                metadata={"description": opt.description},
                confidence=opt.initial_confidence, weight=2.0,
            )
            self.add_node(node, round_num)

        # If frame has an initial graph, merge it
        if frame.initial_graph:
            for n in frame.initial_graph.nodes:
                if n.node_id not in self._nodes:
                    self.add_node(n, round_num)
            for e in frame.initial_graph.edges:
                if e.edge_id not in self._edges:
                    self.add_edge(e, round_num)

    def add_agent_nodes(self, agents: List[Dict[str, Any]], round_num: int = 0):
        """Add agent persona nodes to the graph."""
        for agent in agents:
            aid = agent.get("agent_id", "")
            node = GraphNode(
                node_id=f"agent_{aid}",
                node_type=NodeType.AGENT_PERSONA,
                label=agent.get("name", "Unknown"),
                metadata={
                    "role": agent.get("role", ""),
                    "affiliation": agent.get("affiliation", ""),
                    "primary_field": agent.get("primary_field", ""),
                },
                weight=1.5,
            )
            self.add_node(node, round_num)
