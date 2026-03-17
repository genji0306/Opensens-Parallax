"""
OSSR Research Mapper Service
Builds topic hierarchies from ingested papers using LLM-assisted clustering,
citation network analysis (NetworkX), community detection (Louvain), and gap analysis.
"""

import logging
import uuid
import threading
from collections import Counter, defaultdict
from typing import Dict, Any, List, Optional, Tuple

from opensens_common.config import Config
from ..models.research import (
    AcademicSource,
    Paper,
    Topic,
    TopicLevel,
    PaperTopic,
    ResearchDataStore,
)
from opensens_common.task import TaskManager, TaskStatus
from opensens_common.llm_client import LLMClient

logger = logging.getLogger(__name__)

# Optional graph analysis dependencies
try:
    import networkx as nx

    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.info("networkx not installed — citation graph analysis disabled")

try:
    import community as community_louvain

    HAS_LOUVAIN = True
except ImportError:
    HAS_LOUVAIN = False
    logger.info("python-louvain not installed — community detection disabled")


# ── LLM Prompts ──────────────────────────────────────────────────────

TOPIC_CLUSTERING_PROMPT = """You are a research taxonomy expert. Given these paper titles and keywords, organize them into a hierarchical topic structure.

Papers:
{papers_text}

Create a JSON object with this structure:
{{
  "domains": [
    {{
      "name": "Domain Name",
      "description": "Brief description",
      "subfields": [
        {{
          "name": "Subfield Name",
          "description": "Brief description",
          "threads": [
            {{
              "name": "Specific Thread Name",
              "description": "Brief description",
              "paper_indices": [0, 1, 5]
            }}
          ]
        }}
      ]
    }}
  ]
}}

Rules:
- Create 2-5 broad domains
- Each domain has 2-6 subfields
- Each subfield has 1-5 specific threads
- Assign every paper index to exactly one thread
- Paper indices are zero-based, matching the order above
- Thread names should be specific enough to distinguish from siblings
"""

GAP_ANALYSIS_PROMPT = """You are a research strategist. Given two research topic clusters, analyze potential gaps and synergies.

Cluster A — "{cluster_a_name}":
Keywords: {cluster_a_keywords}
Paper count: {cluster_a_count}

Cluster B — "{cluster_b_name}":
Keywords: {cluster_b_keywords}
Paper count: {cluster_b_count}

Keyword overlap: {overlap_keywords}

Return a JSON object:
{{
  "gap_score": 0.0 to 1.0 (higher = bigger gap worth exploring),
  "opportunity": "one sentence describing the research opportunity",
  "suggested_questions": ["research question 1", "research question 2"]
}}
"""


class ResearchMapper:
    """
    Builds a hierarchical topic map from ingested papers.
    Pipeline: collect papers → LLM clustering → citation graph → community detection → gap analysis.
    """

    def __init__(self):
        self.store = ResearchDataStore()
        self.task_manager = TaskManager()

    # ── Public API ────────────────────────────────────────────────────

    def map_async(self, include_gaps: bool = True) -> str:
        """Start async mapping job. Returns task_id."""
        task_id = self.task_manager.create_task(
            task_type="research_mapping",
            metadata={"include_gaps": include_gaps},
        )
        thread = threading.Thread(
            target=self._map_worker,
            args=(task_id, include_gaps),
            daemon=True,
        )
        thread.start()
        return task_id

    def get_landscape(self) -> Dict[str, Any]:
        """
        Return the current research landscape as graph data
        suitable for force-directed visualization.
        Returns { nodes: [...], edges: [...], topics: [...] }
        """
        papers = self.store.list_papers(limit=10000)
        topics = self.store.list_topics()

        nodes = []
        edges = []

        # Topic nodes
        for topic in topics:
            topic_node = {
                "id": topic.topic_id,
                "type": "topic",
                "label": topic.name,
                "level": topic.level.value if isinstance(topic.level, TopicLevel) else topic.level,
                "paper_count": topic.paper_count,
                "parent_id": topic.parent_id,
            }
            # Compute max gap score from topic metadata
            gaps = topic.metadata.get("gaps", []) if topic.metadata else []
            if gaps:
                max_gap = max(g.get("gap_score", 0) for g in gaps)
                topic_node["max_gap_score"] = round(max_gap, 2)
            nodes.append(topic_node)

        # Topic hierarchy edges
        for topic in topics:
            if topic.parent_id:
                edges.append({
                    "source": topic.parent_id,
                    "target": topic.topic_id,
                    "type": "hierarchy",
                })

        # Paper nodes (lightweight)
        for paper in papers[:500]:  # Cap for performance
            nodes.append({
                "id": paper.paper_id,
                "type": "paper",
                "label": paper.title[:80],
                "doi": paper.doi,
                "date": paper.publication_date,
                "citation_count": paper.citation_count,
                "source": paper.source.value if isinstance(paper.source, AcademicSource) else paper.source,
                "keywords": paper.keywords[:5],
            })

        # Paper-topic edges
        for paper in papers[:500]:
            for pt in self.store.get_paper_topics(paper.paper_id):
                edges.append({
                    "source": paper.paper_id,
                    "target": pt.topic_id,
                    "type": "belongs_to",
                    "weight": pt.relevance_score,
                })

        # Citation edges
        for paper in papers[:500]:
            for ref in self.store.get_references_of(paper.paper_id):
                edges.append({
                    "source": ref.citing_paper_id,
                    "target": ref.cited_paper_id,
                    "type": "cites",
                })

        return {
            "nodes": nodes,
            "edges": edges,
            "topic_tree": self.store.get_topic_tree(),
            "stats": self.store.stats(),
        }

    def find_gaps(self, min_score: float = 0.3) -> List[Dict[str, Any]]:
        """Return stored gap analysis results filtered by minimum score."""
        topics = self.store.list_topics(level=TopicLevel.SUBFIELD)
        gaps = []
        for topic in topics:
            stored_gaps = topic.metadata.get("gaps", [])
            for gap in stored_gaps:
                if gap.get("gap_score", 0) >= min_score:
                    gaps.append({
                        "topic_a": topic.name,
                        "topic_a_id": topic.topic_id,
                        **gap,
                    })
        gaps.sort(key=lambda g: g.get("gap_score", 0), reverse=True)
        return gaps

    # ── Mapping Pipeline ──────────────────────────────────────────────

    def _map_worker(self, task_id: str, include_gaps: bool):
        """Background mapping pipeline."""
        self.task_manager.update_task(
            task_id, status=TaskStatus.PROCESSING, progress=0,
            message="Starting research mapping...",
        )

        try:
            papers = self.store.list_papers(limit=10000)
            if not papers:
                self.task_manager.complete_task(task_id, result={
                    "message": "No papers to map.",
                    "topics_created": 0,
                })
                return

            # Step 1: LLM topic clustering
            self.task_manager.update_task(
                task_id, progress=10,
                message=f"Clustering {len(papers)} papers into topics...",
            )
            topics_created = self._llm_topic_clustering(papers)

            # Step 2: Citation network analysis
            self.task_manager.update_task(
                task_id, progress=50,
                message="Building citation network...",
            )
            graph_stats = self._build_citation_network(papers)

            # Step 3: Community detection (refines clusters)
            self.task_manager.update_task(
                task_id, progress=65,
                message="Detecting research communities...",
            )
            communities = self._detect_communities(papers)

            # Step 4: Gap analysis
            gap_count = 0
            if include_gaps:
                self.task_manager.update_task(
                    task_id, progress=80,
                    message="Analyzing research gaps...",
                )
                gap_count = self._analyze_gaps()

            self.task_manager.complete_task(task_id, result={
                "topics_created": topics_created,
                "graph_stats": graph_stats,
                "communities_found": len(communities),
                "gaps_found": gap_count,
                "store_stats": self.store.stats(),
            })

        except Exception as e:
            logger.exception(f"Research mapping failed: {e}")
            self.task_manager.fail_task(task_id, str(e))

    # ── Step 1: LLM Topic Clustering ─────────────────────────────────

    def _llm_topic_clustering(self, papers: List[Paper]) -> int:
        """Use LLM to cluster papers into a 3-level topic hierarchy."""
        try:
            llm = LLMClient()
        except ValueError:
            logger.warning("LLM not configured — using keyword-based clustering fallback")
            return self._keyword_clustering_fallback(papers)

        # Prepare paper summaries for the prompt (cap at 100 for token limits)
        batch = papers[:100]
        papers_text = ""
        for i, p in enumerate(batch):
            kw = ", ".join(p.keywords[:5]) if p.keywords else "N/A"
            extracted = p.metadata.get("extracted", {})
            domain = extracted.get("domain", "")
            subfield = extracted.get("subfield", "")
            papers_text += f"[{i}] {p.title}\n    Keywords: {kw}"
            if domain:
                papers_text += f" | Domain: {domain}"
            if subfield:
                papers_text += f" | Subfield: {subfield}"
            papers_text += "\n"

        prompt = TOPIC_CLUSTERING_PROMPT.format(papers_text=papers_text)
        try:
            result = llm.chat_json(
                messages=[
                    {"role": "system", "content": "You are a research taxonomy expert."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
        except Exception as e:
            logger.warning(f"LLM clustering failed: {e} — using fallback")
            return self._keyword_clustering_fallback(papers)

        # Parse the LLM response into Topic objects
        topics_created = 0
        domains = result.get("domains", [])

        for domain_def in domains:
            domain_topic = Topic(
                topic_id="",
                name=domain_def.get("name", "Unknown Domain"),
                level=TopicLevel.DOMAIN,
                description=domain_def.get("description", ""),
            )
            self.store.add_topic(domain_topic)
            topics_created += 1

            for sf_def in domain_def.get("subfields", []):
                sf_topic = Topic(
                    topic_id="",
                    name=sf_def.get("name", "Unknown Subfield"),
                    level=TopicLevel.SUBFIELD,
                    description=sf_def.get("description", ""),
                    parent_id=domain_topic.topic_id,
                )
                self.store.add_topic(sf_topic)
                topics_created += 1

                for thread_def in sf_def.get("threads", []):
                    thread_topic = Topic(
                        topic_id="",
                        name=thread_def.get("name", "Unknown Thread"),
                        level=TopicLevel.THREAD,
                        description=thread_def.get("description", ""),
                        parent_id=sf_topic.topic_id,
                    )
                    self.store.add_topic(thread_topic)
                    topics_created += 1

                    # Link papers to this thread
                    for idx in thread_def.get("paper_indices", []):
                        if 0 <= idx < len(batch):
                            paper = batch[idx]
                            self.store.link_paper_topic(
                                paper.paper_id, thread_topic.topic_id, 1.0
                            )
                            if thread_topic.topic_id not in paper.topics:
                                paper.topics.append(thread_topic.topic_id)

        # For papers beyond the first 100, assign by keyword similarity
        if len(papers) > 100:
            self._assign_remaining_papers(papers[100:])

        logger.info(f"LLM clustering created {topics_created} topics")
        return topics_created

    def _keyword_clustering_fallback(self, papers: List[Paper]) -> int:
        """
        Fallback clustering when LLM is unavailable.
        Groups papers by extracted domain/subfield metadata, or top keywords.
        """
        domain_groups: Dict[str, List[Paper]] = defaultdict(list)

        for paper in papers:
            extracted = paper.metadata.get("extracted", {})
            domain = extracted.get("domain", "")
            if not domain and paper.keywords:
                domain = paper.keywords[0]
            if not domain:
                domain = "Unclassified"
            domain_groups[domain].append(paper)

        topics_created = 0
        for domain_name, group in domain_groups.items():
            domain_topic = Topic(
                topic_id="",
                name=domain_name,
                level=TopicLevel.DOMAIN,
                description=f"Auto-grouped: {len(group)} papers",
            )
            self.store.add_topic(domain_topic)
            topics_created += 1

            # Create subfield topics from extracted subfields
            subfield_groups: Dict[str, List[Paper]] = defaultdict(list)
            for p in group:
                sf = p.metadata.get("extracted", {}).get("subfield", "General")
                subfield_groups[sf].append(p)

            for sf_name, sf_papers in subfield_groups.items():
                sf_topic = Topic(
                    topic_id="",
                    name=sf_name,
                    level=TopicLevel.SUBFIELD,
                    description=f"Auto-grouped: {len(sf_papers)} papers",
                    parent_id=domain_topic.topic_id,
                )
                self.store.add_topic(sf_topic)
                topics_created += 1

                for p in sf_papers:
                    self.store.link_paper_topic(p.paper_id, sf_topic.topic_id, 0.8)
                    if sf_topic.topic_id not in p.topics:
                        p.topics.append(sf_topic.topic_id)

        logger.info(f"Fallback clustering created {topics_created} topics")
        return topics_created

    def _assign_remaining_papers(self, papers: List[Paper]):
        """Assign papers beyond the LLM batch to existing topics by keyword overlap."""
        thread_topics = self.store.list_topics(level=TopicLevel.THREAD)
        if not thread_topics:
            thread_topics = self.store.list_topics(level=TopicLevel.SUBFIELD)
        if not thread_topics:
            return

        # Build keyword index for each topic
        topic_keywords: Dict[str, set] = {}
        for topic in thread_topics:
            # Collect keywords from papers already linked to this topic
            linked_paper_ids = self.store.get_topic_papers(topic.topic_id)
            kw_set = set()
            for pid in linked_paper_ids:
                p = self.store.get_paper_by_id(pid)
                if p:
                    kw_set.update(k.lower() for k in p.keywords)
            topic_keywords[topic.topic_id] = kw_set

        for paper in papers:
            paper_kw = set(k.lower() for k in paper.keywords)
            best_topic_id = None
            best_overlap = 0
            for tid, tkw in topic_keywords.items():
                overlap = len(paper_kw & tkw)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_topic_id = tid
            if best_topic_id and best_overlap > 0:
                relevance = min(best_overlap / max(len(paper_kw), 1), 1.0)
                self.store.link_paper_topic(paper.paper_id, best_topic_id, relevance)
                if best_topic_id not in paper.topics:
                    paper.topics.append(best_topic_id)

    # ── Step 2: Citation Network ─────────────────────────────────────

    def _build_citation_network(self, papers: List[Paper]) -> Dict[str, Any]:
        """Build a NetworkX citation graph and compute basic metrics."""
        if not HAS_NETWORKX:
            return {"status": "networkx_not_available"}

        G = nx.DiGraph()

        # Add paper nodes
        paper_ids = set()
        for p in papers:
            G.add_node(p.paper_id, doi=p.doi, title=p.title[:60])
            paper_ids.add(p.paper_id)

        # Add citation edges
        edge_count = 0
        for p in papers:
            for cit in self.store.get_references_of(p.paper_id):
                if cit.cited_paper_id in paper_ids:
                    G.add_edge(cit.citing_paper_id, cit.cited_paper_id)
                    edge_count += 1

        if G.number_of_nodes() == 0:
            return {"nodes": 0, "edges": 0}

        # Compute centrality metrics
        in_degree = dict(G.in_degree())
        top_cited = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:10]

        try:
            pagerank = nx.pagerank(G, alpha=0.85)
            top_pagerank = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:10]
        except Exception:
            top_pagerank = []

        stats = {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "top_cited": [
                {"paper_id": pid, "in_degree": deg} for pid, deg in top_cited
            ],
            "top_pagerank": [
                {"paper_id": pid, "score": round(score, 4)} for pid, score in top_pagerank
            ],
        }

        # Store the graph object for community detection
        self._citation_graph = G
        return stats

    # ── Step 3: Community Detection ──────────────────────────────────

    def _detect_communities(self, papers: List[Paper]) -> Dict[int, List[str]]:
        """Use Louvain community detection on the citation graph."""
        if not HAS_NETWORKX or not HAS_LOUVAIN:
            return {}

        G = getattr(self, "_citation_graph", None)
        if G is None or G.number_of_nodes() < 3:
            return {}

        # Louvain works on undirected graphs
        G_undirected = G.to_undirected()

        try:
            partition = community_louvain.best_partition(G_undirected)
        except Exception as e:
            logger.warning(f"Community detection failed: {e}")
            return {}

        # Group papers by community
        communities: Dict[int, List[str]] = defaultdict(list)
        for paper_id, comm_id in partition.items():
            communities[comm_id].append(paper_id)

        # Store community info in paper metadata
        for paper_id, comm_id in partition.items():
            paper = self.store.get_paper_by_id(paper_id)
            if paper:
                paper.metadata["community_id"] = comm_id

        logger.info(f"Detected {len(communities)} research communities")
        return dict(communities)

    # ── Step 4: Gap Analysis ─────────────────────────────────────────

    def _analyze_gaps(self) -> int:
        """Identify gaps between subfield-level topic clusters."""
        subfields = self.store.list_topics(level=TopicLevel.SUBFIELD)
        if len(subfields) < 2:
            return 0

        # Build keyword sets per subfield
        sf_keywords: Dict[str, set] = {}
        for sf in subfields:
            linked_ids = self.store.get_topic_papers(sf.topic_id)
            kw = set()
            for pid in linked_ids:
                paper = self.store.get_paper_by_id(pid)
                if paper:
                    kw.update(k.lower() for k in paper.keywords)
            sf_keywords[sf.topic_id] = kw

        # Compare pairs using keyword overlap
        try:
            llm = LLMClient()
            use_llm = True
        except ValueError:
            use_llm = False

        gap_count = 0
        processed_pairs = set()

        for i, sf_a in enumerate(subfields):
            for sf_b in subfields[i + 1 :]:
                pair_key = tuple(sorted([sf_a.topic_id, sf_b.topic_id]))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)

                kw_a = sf_keywords.get(sf_a.topic_id, set())
                kw_b = sf_keywords.get(sf_b.topic_id, set())
                overlap = kw_a & kw_b

                # Only analyze pairs with some but not total overlap
                if not kw_a or not kw_b:
                    continue
                jaccard = len(overlap) / len(kw_a | kw_b) if (kw_a | kw_b) else 0
                if jaccard > 0.7 or jaccard < 0.05:
                    continue  # too similar or too different

                if use_llm:
                    gap = self._llm_gap_analysis(sf_a, sf_b, kw_a, kw_b, overlap)
                else:
                    gap = self._heuristic_gap_analysis(sf_a, sf_b, kw_a, kw_b, overlap)

                if gap and gap.get("gap_score", 0) > 0:
                    # Store gap data in topic metadata
                    gaps_a = sf_a.metadata.get("gaps", [])
                    gaps_a.append({
                        "partner_topic": sf_b.name,
                        "partner_id": sf_b.topic_id,
                        **gap,
                    })
                    sf_a.metadata["gaps"] = gaps_a
                    gap_count += 1

        logger.info(f"Gap analysis found {gap_count} potential gaps")
        return gap_count

    def _llm_gap_analysis(
        self,
        sf_a: Topic,
        sf_b: Topic,
        kw_a: set,
        kw_b: set,
        overlap: set,
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to assess gap between two topic clusters."""
        try:
            llm = LLMClient()
            prompt = GAP_ANALYSIS_PROMPT.format(
                cluster_a_name=sf_a.name,
                cluster_a_keywords=", ".join(list(kw_a)[:15]),
                cluster_a_count=sf_a.paper_count,
                cluster_b_name=sf_b.name,
                cluster_b_keywords=", ".join(list(kw_b)[:15]),
                cluster_b_count=sf_b.paper_count,
                overlap_keywords=", ".join(list(overlap)[:10]) or "none",
            )
            return llm.chat_json(
                messages=[
                    {"role": "system", "content": "You are a research strategist."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
        except Exception as e:
            logger.warning(f"LLM gap analysis failed: {e}")
            return self._heuristic_gap_analysis(sf_a, sf_b, kw_a, kw_b, overlap)

    @staticmethod
    def _heuristic_gap_analysis(
        sf_a: Topic,
        sf_b: Topic,
        kw_a: set,
        kw_b: set,
        overlap: set,
    ) -> Dict[str, Any]:
        """Simple heuristic gap scoring when LLM is unavailable."""
        jaccard = len(overlap) / len(kw_a | kw_b) if (kw_a | kw_b) else 0
        # Sweet spot: some overlap but lots of unique keywords
        gap_score = round(jaccard * (1 - jaccard) * 4, 2)  # peaks at jaccard=0.5
        return {
            "gap_score": gap_score,
            "opportunity": f"Potential intersection between {sf_a.name} and {sf_b.name}",
            "suggested_questions": [],
            "keyword_overlap": list(overlap)[:10],
        }
