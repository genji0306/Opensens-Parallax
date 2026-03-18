"""
OSSR Researcher Profile Generator (AntiGravity Agent — S2)
Generates academic researcher agent personas from paper clusters.
Extends OasisAgentProfile with research-specific fields.
"""

import json
import random
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from opensens_common.config import Config
from ...models.research import Paper, Topic, ResearchDataStore, TopicLevel
from opensens_common.task import TaskManager, TaskStatus
from opensens_common.llm_client import LLMClient
from ...db import get_connection

import logging

logger = logging.getLogger(__name__)


# ── Research Agent Profile ────────────────────────────────────────────


@dataclass
class ResearcherProfile:
    """
    Academic researcher agent persona for OSSR simulations.
    Compatible with OASIS OasisAgentProfile but with research-specific fields.
    """
    agent_id: str
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str

    # Academic identity
    role: str = "researcher"  # professor, postdoc, phd_student, industry_researcher, reviewer
    affiliation: str = ""
    department: str = ""
    h_index: int = 0
    years_active: int = 5

    # Research profile
    primary_field: str = ""
    specializations: List[str] = field(default_factory=list)
    methodologies: List[str] = field(default_factory=list)
    publication_count: int = 0

    # Personality traits (influence discussion behavior)
    openness: float = 0.5        # 0=conservative, 1=open to new ideas
    assertiveness: float = 0.5   # 0=passive, 1=confrontational
    detail_orientation: float = 0.5  # 0=big-picture, 1=detail-focused
    collaboration_tendency: float = 0.5  # 0=independent, 1=collaborative

    # Knowledge base
    known_paper_dois: List[str] = field(default_factory=list)
    topic_ids: List[str] = field(default_factory=list)

    # OASIS compatibility
    karma: int = 1000
    friend_count: int = 50
    follower_count: int = 100
    statuses_count: int = 200
    interested_topics: List[str] = field(default_factory=list)

    # LLM configuration (per-agent model selection)
    llm_provider: str = ""    # "" = use default; "anthropic", "openai", "gemini", "perplexity"
    llm_model: str = ""       # "" = use provider default; specific model id

    # Skills & capabilities
    skills: List[str] = field(default_factory=list)  # scientific skill names
    is_super_agent: bool = False  # can generate code, simulations, math

    # Metadata
    source_topic_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "role": self.role,
            "affiliation": self.affiliation,
            "department": self.department,
            "h_index": self.h_index,
            "years_active": self.years_active,
            "primary_field": self.primary_field,
            "specializations": self.specializations,
            "methodologies": self.methodologies,
            "publication_count": self.publication_count,
            "openness": self.openness,
            "assertiveness": self.assertiveness,
            "detail_orientation": self.detail_orientation,
            "collaboration_tendency": self.collaboration_tendency,
            "known_paper_dois": self.known_paper_dois,
            "topic_ids": self.topic_ids,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "interested_topics": self.interested_topics,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "skills": self.skills,
            "is_super_agent": self.is_super_agent,
            "source_topic_id": self.source_topic_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResearcherProfile':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_oasis_reddit_format(self) -> Dict[str, Any]:
        """Convert to OASIS Reddit-compatible profile."""
        return {
            "user_id": self.user_id,
            "username": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at[:10],
            "age": self.years_active + 25,
            "profession": f"{self.role} — {self.primary_field}",
            "interested_topics": self.interested_topics,
        }

    def to_oasis_twitter_format(self) -> Dict[str, Any]:
        """Convert to OASIS Twitter-compatible profile."""
        return {
            "user_id": self.user_id,
            "username": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at[:10],
            "profession": f"{self.role} — {self.primary_field}",
            "interested_topics": self.interested_topics,
        }


# ── Profile Store ─────────────────────────────────────────────────────


class ResearcherProfileStore:
    """SQLite-backed store for generated researcher profiles. Singleton."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def add(self, profile: ResearcherProfile):
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO researcher_profiles (agent_id, data) VALUES (?, ?)",
            (profile.agent_id, json.dumps(profile.to_dict())),
        )
        conn.commit()

    def get(self, agent_id: str) -> Optional[ResearcherProfile]:
        conn = get_connection()
        row = conn.execute(
            "SELECT data FROM researcher_profiles WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        if row is None:
            return None
        return ResearcherProfile.from_dict(json.loads(row["data"]))

    def list_all(self, topic_id: Optional[str] = None) -> List[ResearcherProfile]:
        conn = get_connection()
        rows = conn.execute("SELECT data FROM researcher_profiles").fetchall()
        profiles = [ResearcherProfile.from_dict(json.loads(r["data"])) for r in rows]
        if topic_id:
            profiles = [p for p in profiles if topic_id in p.topic_ids]
        return profiles

    def count(self) -> int:
        conn = get_connection()
        row = conn.execute("SELECT COUNT(*) AS cnt FROM researcher_profiles").fetchone()
        return row["cnt"]

    def clear(self):
        conn = get_connection()
        conn.execute("DELETE FROM researcher_profiles")
        conn.commit()


# ── LLM Prompts ───────────────────────────────────────────────────────


RESEARCHER_PERSONA_PROMPT = """You are building a realistic academic researcher persona for a research simulation.

Given this research context, generate a detailed researcher profile.
IMPORTANT: Generate a UNIQUE fictional name — do NOT reuse author names from the papers below. The persona should be inspired by the research area but must be an original character.

Research cluster: {cluster_name}
Field: {field_name}
Key topics: {topics}
Representative papers this researcher would know:
{papers_summary}

Role type: {role_type}

Generate a JSON object with:
{{
  "name": "Full Name (realistic, diverse background)",
  "affiliation": "University or Research Institution",
  "department": "Department name",
  "bio": "2-3 sentence academic bio",
  "persona": "Detailed persona paragraph (4-6 sentences) describing research philosophy, communication style, career stage, key contributions, and intellectual tendencies. This shapes how they argue in academic discussions.",
  "specializations": ["specific expertise 1", "specific expertise 2", "specific expertise 3"],
  "methodologies": ["method 1", "method 2"],
  "h_index": <realistic number based on role>,
  "years_active": <number>,
  "publication_count": <realistic number>,
  "openness": <0.0-1.0>,
  "assertiveness": <0.0-1.0>,
  "detail_orientation": <0.0-1.0>,
  "collaboration_tendency": <0.0-1.0>
}}
"""

ROLE_ARCHETYPES = [
    "professor",
    "associate_professor",
    "assistant_professor",
    "postdoc",
    "phd_student",
    "industry_researcher",
    "reviewer",
]


# ── Generator ─────────────────────────────────────────────────────────


class ResearcherProfileGenerator:
    """
    Generates researcher agent profiles from paper clusters.
    Each cluster produces 2-5 agents with distinct roles and perspectives.
    """

    def __init__(self):
        self.store = ResearchDataStore()
        self.profile_store = ResearcherProfileStore()
        self.task_manager = TaskManager()
        self._next_user_id = 1

    def _recommend_agents_per_cluster(self, topic_id: Optional[str]) -> int:
        """Recommend agents_per_cluster based on number of clusters."""
        if topic_id:
            return 3  # single cluster: 3 is fine
        topics = self.store.list_topics(level=TopicLevel.SUBFIELD)
        if not topics:
            topics = self.store.list_topics(level=TopicLevel.DOMAIN)
        n = len(topics)
        if n <= 3:
            return 3
        elif n <= 8:
            return 2
        else:
            return 1  # many clusters: 1 agent each avoids slow generation + duplicates

    def generate_async(
        self,
        topic_id: Optional[str] = None,
        agents_per_cluster: int = 0,  # 0 = auto-recommend
        role_distribution: Optional[List[str]] = None,
    ) -> str:
        """
        Start async agent generation. If topic_id is provided, generate for that
        cluster only. Otherwise generate from all subfield-level topics.
        agents_per_cluster=0 auto-selects based on cluster count.
        Returns task_id.
        """
        if agents_per_cluster <= 0:
            agents_per_cluster = self._recommend_agents_per_cluster(topic_id)

        task_id = self.task_manager.create_task(
            task_type="researcher_generation",
            metadata={
                "topic_id": topic_id,
                "agents_per_cluster": agents_per_cluster,
            },
        )

        thread = threading.Thread(
            target=self._generate_worker,
            args=(task_id, topic_id, agents_per_cluster, role_distribution),
            daemon=True,
        )
        thread.start()
        return task_id

    def _generate_worker(
        self,
        task_id: str,
        topic_id: Optional[str],
        agents_per_cluster: int,
        role_distribution: Optional[List[str]],
    ):
        self.task_manager.update_task(
            task_id, status=TaskStatus.PROCESSING, progress=0,
            message="Starting researcher profile generation...",
        )

        try:
            # Determine which clusters to generate from
            if topic_id:
                topics = [self.store.get_topic(topic_id)]
                topics = [t for t in topics if t is not None]
            else:
                topics = self.store.list_topics(level=TopicLevel.SUBFIELD)
                if not topics:
                    topics = self.store.list_topics(level=TopicLevel.DOMAIN)

            if not topics:
                self.task_manager.complete_task(task_id, result={
                    "agents_generated": 0,
                    "message": "No topic clusters found. Ingest papers and build map first.",
                })
                return

            total_agents = 0
            duplicates_merged = 0
            for i, topic in enumerate(topics):
                pct = int(100 * i / len(topics))
                self.task_manager.update_task(
                    task_id, progress=pct,
                    message=f"Generating agents for '{topic.name}' ({i+1}/{len(topics)})...",
                )

                agents = self._generate_for_cluster(
                    topic, agents_per_cluster, role_distribution
                )
                for agent in agents:
                    existing = self._find_duplicate(agent)
                    if existing:
                        # Merge: add new topic_ids and paper DOIs to existing profile
                        merged = False
                        for tid in agent.topic_ids:
                            if tid not in existing.topic_ids:
                                existing.topic_ids.append(tid)
                                merged = True
                        for doi in agent.known_paper_dois:
                            if doi not in existing.known_paper_dois:
                                existing.known_paper_dois.append(doi)
                                merged = True
                        if merged:
                            self.profile_store.add(existing)
                        duplicates_merged += 1
                    else:
                        self.profile_store.add(agent)
                        total_agents += 1

            self.task_manager.complete_task(task_id, result={
                "agents_generated": total_agents,
                "duplicates_merged": duplicates_merged,
                "clusters_processed": len(topics),
                "agents_per_cluster_used": agents_per_cluster,
                "total_agents": self.profile_store.count(),
            })

        except Exception as e:
            logger.exception(f"Researcher generation failed: {e}")
            self.task_manager.fail_task(task_id, str(e))

    def _generate_for_cluster(
        self,
        topic: Topic,
        count: int,
        role_distribution: Optional[List[str]],
    ) -> List[ResearcherProfile]:
        """Generate researcher profiles for a single topic cluster."""
        # Get papers in this cluster
        paper_ids = self.store.get_topic_papers(topic.topic_id)
        papers = []
        for pid in paper_ids:
            p = self.store.get_paper_by_id(pid)
            if p:
                papers.append(p)

        # Build summary of representative papers
        papers_summary = ""
        for p in papers[:8]:
            kw = ", ".join(p.keywords[:5])
            papers_summary += f"- {p.title} (Keywords: {kw})\n"

        if not papers_summary:
            papers_summary = f"(No papers yet — topic: {topic.name})"

        # Determine roles
        if role_distribution:
            roles = role_distribution[:count]
        else:
            roles = self._default_role_distribution(count)

        # Determine field from parent topic
        field_name = topic.name
        parent = self.store.get_topic(topic.parent_id) if topic.parent_id else None
        if parent:
            field_name = f"{parent.name} / {topic.name}"

        # Collect topic keywords from papers
        all_keywords = set()
        for p in papers:
            all_keywords.update(p.keywords[:5])
        topics_str = ", ".join(list(all_keywords)[:15])

        # Try LLM generation, fallback to template
        try:
            llm = LLMClient()
            use_llm = True
        except ValueError:
            use_llm = False

        agents = []
        for role in roles:
            if use_llm:
                profile = self._llm_generate_profile(
                    llm, topic, field_name, topics_str, papers_summary, role, papers
                )
            else:
                profile = self._template_generate_profile(
                    topic, field_name, role, papers
                )
            agents.append(profile)

        return agents

    def _llm_generate_profile(
        self,
        llm: LLMClient,
        topic: Topic,
        field_name: str,
        topics_str: str,
        papers_summary: str,
        role: str,
        papers: List[Paper],
    ) -> ResearcherProfile:
        """Use LLM to generate a rich researcher profile."""
        prompt = RESEARCHER_PERSONA_PROMPT.format(
            cluster_name=topic.name,
            field_name=field_name,
            topics=topics_str,
            papers_summary=papers_summary,
            role_type=role,
        )

        try:
            result = llm.chat_json(
                messages=[
                    {"role": "system", "content": "You are an academic persona designer."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,
            )
        except Exception as e:
            logger.warning(f"LLM profile generation failed: {e}")
            return self._template_generate_profile(topic, field_name, role, papers)

        uid = self._next_user_id
        self._next_user_id += 1

        name = result.get("name", f"Dr. Researcher {uid}")
        username = name.lower().replace(" ", "_").replace(".", "")[:20]

        profile = ResearcherProfile(
            agent_id=f"ossr_agent_{uid}",
            user_id=uid,
            user_name=username,
            name=name,
            bio=result.get("bio", f"{role} in {field_name}"),
            persona=result.get("persona", f"A {role} specializing in {topic.name}."),
            role=role,
            affiliation=result.get("affiliation", ""),
            department=result.get("department", ""),
            h_index=result.get("h_index", 10),
            years_active=result.get("years_active", 5),
            primary_field=field_name,
            specializations=result.get("specializations", []),
            methodologies=result.get("methodologies", []),
            publication_count=result.get("publication_count", 20),
            openness=result.get("openness", 0.5),
            assertiveness=result.get("assertiveness", 0.5),
            detail_orientation=result.get("detail_orientation", 0.5),
            collaboration_tendency=result.get("collaboration_tendency", 0.5),
            known_paper_dois=[p.doi for p in papers[:10]],
            topic_ids=[topic.topic_id],
            interested_topics=list(set(kw for p in papers[:5] for kw in p.keywords[:3])),
            source_topic_id=topic.topic_id,
            follower_count=self._realistic_followers(role),
            karma=result.get("publication_count", 20) * 50 + result.get("h_index", 10) * 100,
        )
        return profile

    def _template_generate_profile(
        self,
        topic: Topic,
        field_name: str,
        role: str,
        papers: List[Paper],
    ) -> ResearcherProfile:
        """Fallback template-based profile generation (no LLM)."""
        uid = self._next_user_id
        self._next_user_id += 1

        role_templates = {
            "professor": {
                "name_prefix": "Prof.",
                "h_index": random.randint(25, 60),
                "years": random.randint(15, 30),
                "pubs": random.randint(80, 250),
                "openness": round(random.uniform(0.3, 0.7), 2),
                "assertiveness": round(random.uniform(0.5, 0.9), 2),
            },
            "associate_professor": {
                "name_prefix": "Dr.",
                "h_index": random.randint(15, 35),
                "years": random.randint(8, 18),
                "pubs": random.randint(40, 100),
                "openness": round(random.uniform(0.4, 0.8), 2),
                "assertiveness": round(random.uniform(0.4, 0.7), 2),
            },
            "postdoc": {
                "name_prefix": "Dr.",
                "h_index": random.randint(5, 15),
                "years": random.randint(3, 7),
                "pubs": random.randint(10, 40),
                "openness": round(random.uniform(0.6, 0.95), 2),
                "assertiveness": round(random.uniform(0.3, 0.6), 2),
            },
            "phd_student": {
                "name_prefix": "",
                "h_index": random.randint(1, 8),
                "years": random.randint(1, 5),
                "pubs": random.randint(1, 10),
                "openness": round(random.uniform(0.7, 1.0), 2),
                "assertiveness": round(random.uniform(0.2, 0.5), 2),
            },
            "industry_researcher": {
                "name_prefix": "Dr.",
                "h_index": random.randint(8, 25),
                "years": random.randint(5, 15),
                "pubs": random.randint(15, 60),
                "openness": round(random.uniform(0.3, 0.6), 2),
                "assertiveness": round(random.uniform(0.5, 0.8), 2),
            },
        }

        tmpl = role_templates.get(role, role_templates["postdoc"])
        prefix = tmpl["name_prefix"]
        name = f"{prefix} Researcher_{uid}".strip()
        username = f"researcher_{uid}"

        return ResearcherProfile(
            agent_id=f"ossr_agent_{uid}",
            user_id=uid,
            user_name=username,
            name=name,
            bio=f"{role.replace('_', ' ').title()} in {field_name}.",
            persona=(
                f"A {role.replace('_', ' ')} specializing in {topic.name}. "
                f"Has {tmpl['years']} years of experience and {tmpl['pubs']} publications. "
                f"Known for rigorous methodology and active participation in academic debates."
            ),
            role=role,
            affiliation="Research University",
            primary_field=field_name,
            specializations=[topic.name],
            h_index=tmpl["h_index"],
            years_active=tmpl["years"],
            publication_count=tmpl["pubs"],
            openness=tmpl["openness"],
            assertiveness=tmpl["assertiveness"],
            detail_orientation=round(random.uniform(0.3, 0.9), 2),
            collaboration_tendency=round(random.uniform(0.3, 0.8), 2),
            known_paper_dois=[p.doi for p in papers[:10]],
            topic_ids=[topic.topic_id],
            interested_topics=[topic.name],
            source_topic_id=topic.topic_id,
            follower_count=self._realistic_followers(role),
            karma=tmpl["pubs"] * 50 + tmpl["h_index"] * 100,
        )

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize agent name for duplicate detection."""
        n = name.lower().strip()
        # Strip common prefixes
        for prefix in ("prof.", "prof ", "dr.", "dr "):
            if n.startswith(prefix):
                n = n[len(prefix):].strip()
        return n

    def _find_duplicate(self, agent: ResearcherProfile) -> Optional[ResearcherProfile]:
        """Check if an agent with same/similar name already exists."""
        norm_name = self._normalize_name(agent.name)
        if not norm_name:
            return None
        for existing in self.profile_store.list_all():
            if self._normalize_name(existing.name) == norm_name:
                return existing
        return None

    @staticmethod
    def _default_role_distribution(count: int) -> List[str]:
        """Pick a balanced distribution of academic roles."""
        base = ["professor", "postdoc", "phd_student"]
        extended = base + ["associate_professor", "industry_researcher", "reviewer"]
        return (extended * ((count // len(extended)) + 1))[:count]

    @staticmethod
    def _realistic_followers(role: str) -> int:
        ranges = {
            "professor": (500, 5000),
            "associate_professor": (200, 2000),
            "assistant_professor": (100, 800),
            "postdoc": (50, 500),
            "phd_student": (20, 200),
            "industry_researcher": (100, 1000),
            "reviewer": (150, 1200),
        }
        lo, hi = ranges.get(role, (50, 500))
        return random.randint(lo, hi)
