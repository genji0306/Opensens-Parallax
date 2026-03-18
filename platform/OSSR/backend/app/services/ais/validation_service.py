"""
Agent AiS — Validation Service
Wraps ScienceClaw's 4-phase research protocol for citation verification and
novelty validation. Falls back to OSSR's own paper store when ScienceClaw is
unavailable.
"""

import importlib
import json
import logging
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

from opensens_common.llm_client import LLMClient

from ...db import get_connection
from ...models.research import ResearchDataStore

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Wraps ScienceClaw's 4-phase research protocol for citation verification
    and novelty validation. Falls back to OSSR's own paper store when
    ScienceClaw is unavailable.

    ScienceClaw phases:
        Phase 1 — Database discovery (Semantic Scholar, OpenAlex, CrossRef, etc.)
        Phase 2 — Deep retrieval and cross-referencing
        Phase 3 — Synthesis and gap analysis
        Phase 4 — Structured report generation

    When ScienceClaw is not installed, this service queries the local OSSR
    paper database (SQLite) for fuzzy title matching and DOI lookups.
    """

    SCIENCECLAW_DIR = Path(__file__).resolve().parents[5] / "tools" / "scienceclaw"

    # Similarity threshold for fuzzy title matching (0.0–1.0)
    FUZZY_THRESHOLD = 0.75

    # Maximum papers to return in survey results
    DEFAULT_MAX_PAPERS = 20

    # Academic databases that ScienceClaw can query
    SCIENCECLAW_DATABASES = [
        "semantic_scholar",
        "openalex",
        "crossref",
        "arxiv",
        "pubmed",
        "dblp",
        "google_scholar",
        "biorxiv",
    ]

    def __init__(self):
        self.llm = LLMClient()
        self.store = ResearchDataStore()
        self._scienceclaw = self._load_scienceclaw()

    # ── Public API ────────────────────────────────────────────────────

    def validate_citations(self, citations: List[Dict]) -> Dict[str, Any]:
        """
        Verify that citations exist in real academic databases.

        Each citation dict should contain at least one of:
        - "doi": a DOI string
        - "title": the paper title
        - "authors": list of author names (optional, improves matching)

        Returns:
            {
                "verified": [{"doi": ..., "title": ..., "source": ...}, ...],
                "unverified": [{"doi": ..., "title": ..., "reason": ...}, ...],
                "suspicious": [{"doi": ..., "title": ..., "reason": ...}, ...],
                "total": int,
                "verified_count": int,
                "verification_rate": float,
                "method": "scienceclaw" | "local_db",
            }
        """
        if not citations:
            return {
                "verified": [], "unverified": [], "suspicious": [],
                "total": 0, "verified_count": 0, "verification_rate": 0.0,
                "method": "none",
            }

        logger.info(
            "[ValidationService] Verifying %d citations", len(citations)
        )

        if self._scienceclaw:
            return self._validate_citations_scienceclaw(citations)
        return self._validate_citations_local(citations)

    def validate_novelty(self, idea_title: str, idea_abstract: str) -> Dict[str, Any]:
        """
        Cross-check idea novelty against multiple databases.

        Returns:
            {
                "is_novel": bool,
                "similar_papers": [
                    {"title": ..., "doi": ..., "similarity": float, "source": ...},
                    ...
                ],
                "databases_checked": [...],
                "method": "scienceclaw" | "local_db",
                "checked_at": str (ISO timestamp),
            }
        """
        if not idea_title:
            return {
                "is_novel": True, "similar_papers": [], "databases_checked": [],
                "method": "none", "checked_at": datetime.now().isoformat(),
            }

        logger.info(
            "[ValidationService] Checking novelty for: %s", idea_title[:80]
        )

        if self._scienceclaw:
            return self._validate_novelty_scienceclaw(idea_title, idea_abstract)
        return self._validate_novelty_local(idea_title, idea_abstract)

    def deep_literature_survey(
        self, topic: str, max_papers: int = DEFAULT_MAX_PAPERS
    ) -> Dict[str, Any]:
        """
        Run ScienceClaw's Phase 1-3 research protocol on a topic.

        Returns:
            {
                "topic": str,
                "papers": [
                    {"title": ..., "doi": ..., "abstract": ..., "year": ..., "relevance": float},
                    ...
                ],
                "synthesis": str,
                "gaps": [str, ...],
                "databases_checked": [...],
                "method": "scienceclaw" | "local_db",
                "paper_count": int,
                "surveyed_at": str (ISO timestamp),
            }
        """
        if not topic:
            return {
                "topic": "", "papers": [], "synthesis": "", "gaps": [],
                "databases_checked": [], "method": "none", "paper_count": 0,
                "surveyed_at": datetime.now().isoformat(),
            }

        logger.info(
            "[ValidationService] Running literature survey for: %s", topic[:80]
        )

        if self._scienceclaw:
            return self._survey_scienceclaw(topic, max_papers)
        return self._survey_local(topic, max_papers)

    # ── ScienceClaw Integration ───────────────────────────────────────

    def _load_scienceclaw(self):
        """
        Attempt to import ScienceClaw's research engine.
        Returns the module or None if unavailable.
        """
        if not self.SCIENCECLAW_DIR.is_dir():
            logger.warning(
                "ScienceClaw not found at %s. "
                "Validation will use local OSSR paper database only.",
                self.SCIENCECLAW_DIR,
            )
            return None

        try:
            import sys
            if str(self.SCIENCECLAW_DIR) not in sys.path:
                sys.path.insert(0, str(self.SCIENCECLAW_DIR))
            # ScienceClaw's main research module
            sc_module = importlib.import_module("scienceclaw.research")
            logger.info("[ValidationService] ScienceClaw loaded successfully.")
            return sc_module
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning(
                "ScienceClaw import failed (%s). Falling back to local DB.", e
            )
            return None

    def _validate_citations_scienceclaw(self, citations: List[Dict]) -> Dict[str, Any]:
        """Use ScienceClaw to verify citations against real databases."""
        verified = []
        unverified = []
        suspicious = []

        try:
            engine = self._scienceclaw.ResearchEngine()

            for cit in citations:
                doi = cit.get("doi", "")
                title = cit.get("title", "")

                try:
                    if doi:
                        result = engine.verify_doi(doi)
                    elif title:
                        result = engine.search_paper(title)
                    else:
                        unverified.append({**cit, "reason": "No DOI or title provided"})
                        continue

                    if result and result.get("found"):
                        verified.append({
                            "doi": result.get("doi", doi),
                            "title": result.get("title", title),
                            "source": result.get("source", "scienceclaw"),
                        })
                    elif result and result.get("partial_match"):
                        suspicious.append({
                            "doi": doi,
                            "title": title,
                            "reason": f"Partial match: {result.get('closest_title', '')}",
                            "similarity": result.get("similarity", 0.0),
                        })
                    else:
                        unverified.append({
                            "doi": doi,
                            "title": title,
                            "reason": "Not found in any database",
                        })
                except Exception as e:
                    logger.warning(
                        "[ValidationService] ScienceClaw verify failed for '%s': %s",
                        title[:40], e,
                    )
                    unverified.append({**cit, "reason": f"Lookup error: {e}"})

        except Exception as e:
            logger.error(
                "[ValidationService] ScienceClaw engine init failed: %s", e
            )
            return self._validate_citations_local(citations)

        total = len(citations)
        return {
            "verified": verified,
            "unverified": unverified,
            "suspicious": suspicious,
            "total": total,
            "verified_count": len(verified),
            "verification_rate": round(len(verified) / total, 3) if total else 0.0,
            "method": "scienceclaw",
        }

    def _validate_novelty_scienceclaw(
        self, idea_title: str, idea_abstract: str
    ) -> Dict[str, Any]:
        """Use ScienceClaw to check novelty across multiple databases."""
        try:
            engine = self._scienceclaw.ResearchEngine()
            results = engine.novelty_check(
                title=idea_title,
                abstract=idea_abstract,
                databases=self.SCIENCECLAW_DATABASES,
            )

            similar = [
                {
                    "title": p.get("title", ""),
                    "doi": p.get("doi", ""),
                    "similarity": p.get("similarity", 0.0),
                    "source": p.get("source", ""),
                }
                for p in results.get("similar_papers", [])
            ]

            # Consider novel if no paper exceeds 0.85 similarity
            is_novel = all(p["similarity"] < 0.85 for p in similar)

            return {
                "is_novel": is_novel,
                "similar_papers": similar,
                "databases_checked": results.get("databases_checked", self.SCIENCECLAW_DATABASES),
                "method": "scienceclaw",
                "checked_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(
                "[ValidationService] ScienceClaw novelty check failed: %s. "
                "Falling back to local DB.", e,
            )
            return self._validate_novelty_local(idea_title, idea_abstract)

    def _survey_scienceclaw(self, topic: str, max_papers: int) -> Dict[str, Any]:
        """Run ScienceClaw Phases 1-3 for a deep literature survey."""
        try:
            engine = self._scienceclaw.ResearchEngine()

            # Phase 1: Discovery
            phase1 = engine.discover(topic=topic, max_results=max_papers)

            # Phase 2: Deep retrieval
            phase2 = engine.deep_retrieve(papers=phase1.get("papers", []))

            # Phase 3: Synthesis
            phase3 = engine.synthesize(papers=phase2.get("papers", []), topic=topic)

            papers = [
                {
                    "title": p.get("title", ""),
                    "doi": p.get("doi", ""),
                    "abstract": p.get("abstract", "")[:300],
                    "year": p.get("year", 0),
                    "relevance": p.get("relevance", 0.0),
                }
                for p in phase3.get("papers", phase2.get("papers", []))[:max_papers]
            ]

            return {
                "topic": topic,
                "papers": papers,
                "synthesis": phase3.get("synthesis", ""),
                "gaps": phase3.get("gaps", []),
                "databases_checked": phase1.get("databases", self.SCIENCECLAW_DATABASES),
                "method": "scienceclaw",
                "paper_count": len(papers),
                "surveyed_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(
                "[ValidationService] ScienceClaw survey failed: %s. "
                "Falling back to local DB.", e,
            )
            return self._survey_local(topic, max_papers)

    # ── Local DB Fallback ─────────────────────────────────────────────

    def _validate_citations_local(self, citations: List[Dict]) -> Dict[str, Any]:
        """
        Verify citations against the local OSSR paper database.
        Uses DOI exact match and fuzzy title matching.
        """
        conn = get_connection()
        verified = []
        unverified = []
        suspicious = []

        for cit in citations:
            doi = cit.get("doi", "").strip()
            title = cit.get("title", "").strip()

            # Try DOI exact match first
            if doi:
                row = conn.execute(
                    "SELECT doi, title, source FROM papers WHERE doi = ?", (doi,)
                ).fetchone()
                if row:
                    verified.append({
                        "doi": row["doi"],
                        "title": row["title"],
                        "source": f"ossr_local ({row['source']})",
                    })
                    continue

            # Try fuzzy title match
            if title:
                match = self._fuzzy_title_search(conn, title)
                if match:
                    sim = match["similarity"]
                    if sim >= 0.90:
                        verified.append({
                            "doi": match["doi"],
                            "title": match["title"],
                            "source": f"ossr_local (fuzzy {sim:.0%})",
                        })
                    elif sim >= self.FUZZY_THRESHOLD:
                        suspicious.append({
                            "doi": match["doi"],
                            "title": title,
                            "reason": f"Fuzzy match ({sim:.0%}): '{match['title']}'",
                            "similarity": sim,
                        })
                    else:
                        unverified.append({
                            "doi": doi, "title": title,
                            "reason": "No close match in local database",
                        })
                    continue

            unverified.append({
                "doi": doi, "title": title,
                "reason": "No DOI or title match found locally",
            })

        total = len(citations)
        return {
            "verified": verified,
            "unverified": unverified,
            "suspicious": suspicious,
            "total": total,
            "verified_count": len(verified),
            "verification_rate": round(len(verified) / total, 3) if total else 0.0,
            "method": "local_db",
        }

    def _validate_novelty_local(
        self, idea_title: str, idea_abstract: str
    ) -> Dict[str, Any]:
        """
        Check novelty against local OSSR paper database using fuzzy matching.
        """
        conn = get_connection()
        similar_papers = []

        # Fetch recent papers for comparison (cap at 500 for performance)
        rows = conn.execute(
            "SELECT paper_id, doi, title, abstract FROM papers ORDER BY ingested_at DESC LIMIT 500"
        ).fetchall()

        search_text = f"{idea_title} {idea_abstract}".lower()

        for row in rows:
            paper_title = row["title"] or ""
            paper_abstract = row["abstract"] or ""
            paper_text = f"{paper_title} {paper_abstract}".lower()

            # Title similarity (weighted more heavily)
            title_sim = SequenceMatcher(
                None, idea_title.lower(), paper_title.lower()
            ).ratio()

            # Abstract similarity (if both available)
            abstract_sim = 0.0
            if idea_abstract and paper_abstract:
                abstract_sim = SequenceMatcher(
                    None, idea_abstract.lower()[:500], paper_abstract.lower()[:500]
                ).ratio()

            # Combined score: 60% title, 40% abstract
            combined = 0.6 * title_sim + 0.4 * abstract_sim

            if combined >= self.FUZZY_THRESHOLD:
                similar_papers.append({
                    "title": paper_title,
                    "doi": row["doi"],
                    "similarity": round(combined, 3),
                    "source": "ossr_local",
                })

        # Sort by similarity descending
        similar_papers.sort(key=lambda p: p["similarity"], reverse=True)
        similar_papers = similar_papers[:10]

        is_novel = all(p["similarity"] < 0.85 for p in similar_papers)

        return {
            "is_novel": is_novel,
            "similar_papers": similar_papers,
            "databases_checked": ["ossr_local"],
            "method": "local_db",
            "checked_at": datetime.now().isoformat(),
        }

    def _survey_local(self, topic: str, max_papers: int) -> Dict[str, Any]:
        """
        Perform a literature survey using the local OSSR paper database.
        Uses keyword matching and the LLM for synthesis.
        """
        conn = get_connection()

        # Keyword search: split topic into words for LIKE matching
        keywords = [w.strip().lower() for w in re.split(r"[\s,;]+", topic) if len(w.strip()) > 2]
        if not keywords:
            return {
                "topic": topic, "papers": [], "synthesis": "", "gaps": [],
                "databases_checked": ["ossr_local"], "method": "local_db",
                "paper_count": 0, "surveyed_at": datetime.now().isoformat(),
            }

        # Build a query that scores papers by keyword hit count
        # SQLite doesn't have great full-text, so we use LIKE per keyword
        all_rows = conn.execute(
            "SELECT paper_id, doi, title, abstract, publication_date FROM papers "
            "ORDER BY ingested_at DESC LIMIT 1000"
        ).fetchall()

        scored_papers = []
        for row in all_rows:
            text = f"{row['title']} {row['abstract']}".lower()
            hits = sum(1 for kw in keywords if kw in text)
            if hits > 0:
                relevance = hits / len(keywords)
                scored_papers.append({
                    "title": row["title"],
                    "doi": row["doi"],
                    "abstract": (row["abstract"] or "")[:300],
                    "year": self._extract_year(row["publication_date"]),
                    "relevance": round(relevance, 3),
                })

        scored_papers.sort(key=lambda p: p["relevance"], reverse=True)
        papers = scored_papers[:max_papers]

        # Generate synthesis using LLM if we have papers
        synthesis = ""
        gaps: List[str] = []
        if papers:
            synthesis, gaps = self._generate_synthesis(topic, papers)

        return {
            "topic": topic,
            "papers": papers,
            "synthesis": synthesis,
            "gaps": gaps,
            "databases_checked": ["ossr_local"],
            "method": "local_db",
            "paper_count": len(papers),
            "surveyed_at": datetime.now().isoformat(),
        }

    # ── Helpers ───────────────────────────────────────────────────────

    def _fuzzy_title_search(
        self, conn, query_title: str
    ) -> Optional[Dict[str, Any]]:
        """
        Search local papers for the closest title match.
        Returns the best match above FUZZY_THRESHOLD, or None.
        """
        rows = conn.execute(
            "SELECT doi, title FROM papers LIMIT 2000"
        ).fetchall()

        best_match = None
        best_sim = 0.0
        query_lower = query_title.lower()

        for row in rows:
            paper_title = (row["title"] or "").lower()
            sim = SequenceMatcher(None, query_lower, paper_title).ratio()
            if sim > best_sim:
                best_sim = sim
                best_match = {
                    "doi": row["doi"],
                    "title": row["title"],
                    "similarity": round(sim, 3),
                }

        if best_match and best_sim >= self.FUZZY_THRESHOLD:
            return best_match
        return None

    def _generate_synthesis(
        self, topic: str, papers: List[Dict]
    ) -> tuple:
        """
        Use the LLM to generate a synthesis and identify gaps.
        Returns (synthesis_text, gap_list).
        """
        try:
            paper_summaries = "\n".join(
                f"- {p['title']} ({p['year']}): {p['abstract'][:150]}"
                for p in papers[:15]
            )

            prompt = (
                f"You are a research analyst. Given the following papers related to "
                f"'{topic}', provide:\n\n"
                f"1. A concise synthesis (2-3 paragraphs) of the current state of research.\n"
                f"2. A list of 3-5 identified gaps or open questions.\n\n"
                f"Papers:\n{paper_summaries}\n\n"
                f"Format your response as:\n"
                f"SYNTHESIS:\n<your synthesis>\n\n"
                f"GAPS:\n- gap 1\n- gap 2\n..."
            )

            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
            )

            text = response if isinstance(response, str) else response.get("content", "")

            # Parse synthesis and gaps
            synthesis = ""
            gaps = []

            if "SYNTHESIS:" in text:
                parts = text.split("GAPS:")
                synthesis = parts[0].replace("SYNTHESIS:", "").strip()
                if len(parts) > 1:
                    gap_text = parts[1].strip()
                    gaps = [
                        line.strip().lstrip("- ").strip()
                        for line in gap_text.split("\n")
                        if line.strip() and line.strip() != "-"
                    ]
            else:
                synthesis = text.strip()

            return synthesis, gaps[:5]

        except Exception as e:
            logger.warning(
                "[ValidationService] LLM synthesis failed: %s", e
            )
            return "", []

    @staticmethod
    def _extract_year(date_str: str) -> int:
        """Extract a 4-digit year from a date string, or return 0."""
        if not date_str:
            return 0
        match = re.search(r"(\d{4})", date_str)
        return int(match.group(1)) if match else 0
