"""
Agent AiS Data Models
Dataclasses for the AI Scientist pipeline: research ideas, paper drafts, pipeline runs.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Enums ────────────────────────────────────────────────────────────


class PipelineStage(str, Enum):
    CRAWL = "crawl"
    IDEATE = "ideate"
    DEBATE = "debate"
    HUMAN_REVIEW = "human_review"
    DRAFT = "draft"
    EXPERIMENT = "experiment"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    CRAWLING = "crawling"
    MAPPING = "mapping"
    IDEATING = "ideating"
    AWAITING_SELECTION = "awaiting_selection"
    DEBATING = "debating"
    HUMAN_REVIEW = "human_review"
    DRAFTING = "drafting"
    REVIEWING = "reviewing"
    EXPERIMENTING = "experimenting"
    COMPLETED = "completed"
    FAILED = "failed"


class ExperimentStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AutoresearchStatus(str, Enum):
    QUEUED = "queued"
    WAITING_GPU = "waiting_gpu"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


# ── Research Idea ────────────────────────────────────────────────────


@dataclass
class ResearchIdea:
    idea_id: str
    title: str
    hypothesis: str
    methodology: str
    expected_contribution: str
    interestingness: int = 5
    feasibility: int = 5
    novelty: int = 5
    composite_score: float = 0.0
    grounding_papers: List[str] = field(default_factory=list)
    target_gap: Optional[str] = None
    novelty_check_result: Dict[str, Any] = field(default_factory=dict)
    reflection_rounds_used: int = 0

    def __post_init__(self):
        if not self.idea_id:
            self.idea_id = f"ais_idea_{uuid.uuid4().hex[:10]}"
        if self.composite_score == 0.0:
            self.composite_score = self._compute_score()

    def _compute_score(self) -> float:
        return round(
            0.3 * self.interestingness + 0.3 * self.novelty + 0.4 * self.feasibility,
            2,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "idea_id": self.idea_id,
            "title": self.title,
            "hypothesis": self.hypothesis,
            "methodology": self.methodology,
            "expected_contribution": self.expected_contribution,
            "interestingness": self.interestingness,
            "feasibility": self.feasibility,
            "novelty": self.novelty,
            "composite_score": self.composite_score,
            "grounding_papers": self.grounding_papers,
            "target_gap": self.target_gap,
            "novelty_check_result": self.novelty_check_result,
            "reflection_rounds_used": self.reflection_rounds_used,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchIdea":
        return cls(
            idea_id=data.get("idea_id", ""),
            title=data.get("title", ""),
            hypothesis=data.get("hypothesis", ""),
            methodology=data.get("methodology", ""),
            expected_contribution=data.get("expected_contribution", ""),
            interestingness=data.get("interestingness", 5),
            feasibility=data.get("feasibility", 5),
            novelty=data.get("novelty", 5),
            composite_score=data.get("composite_score", 0.0),
            grounding_papers=data.get("grounding_papers", []),
            target_gap=data.get("target_gap"),
            novelty_check_result=data.get("novelty_check_result", {}),
            reflection_rounds_used=data.get("reflection_rounds_used", 0),
        )


# ── Idea Set ─────────────────────────────────────────────────────────


@dataclass
class IdeaSet:
    set_id: str
    research_query: str
    ideas: List[ResearchIdea] = field(default_factory=list)
    landscape_summary: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.set_id:
            self.set_id = f"ais_set_{uuid.uuid4().hex[:10]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "set_id": self.set_id,
            "research_query": self.research_query,
            "ideas": [i.to_dict() for i in self.ideas],
            "landscape_summary": self.landscape_summary,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IdeaSet":
        return cls(
            set_id=data.get("set_id", ""),
            research_query=data.get("research_query", ""),
            ideas=[ResearchIdea.from_dict(i) for i in data.get("ideas", [])],
            landscape_summary=data.get("landscape_summary", {}),
            created_at=data.get("created_at", ""),
        )


# ── Pipeline Run ─────────────────────────────────────────────────────


@dataclass
class PipelineRun:
    run_id: str
    research_idea: str
    status: PipelineStatus = PipelineStatus.PENDING
    current_stage: int = 1
    stage_results: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    error: Optional[str] = None

    def __post_init__(self):
        if not self.run_id:
            self.run_id = f"ais_run_{uuid.uuid4().hex[:10]}"
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "research_idea": self.research_idea,
            "status": self.status.value if isinstance(self.status, PipelineStatus) else self.status,
            "current_stage": self.current_stage,
            "stage_results": self.stage_results,
            "config": self.config,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineRun":
        status = data.get("status", "pending")
        if isinstance(status, str):
            status = PipelineStatus(status)
        return cls(
            run_id=data.get("run_id", ""),
            research_idea=data.get("research_idea", ""),
            status=status,
            current_stage=data.get("current_stage", 1),
            stage_results=data.get("stage_results", {}),
            config=data.get("config", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            error=data.get("error"),
        )


# ── Paper Draft (Stage 5 — placeholder for Phase B) ─────────────────


@dataclass
class PaperSection:
    name: str
    content: str = ""
    citations: List[str] = field(default_factory=list)
    word_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        heading = self.name.replace("_", " ").title()
        return {
            "name": self.name,
            "heading": heading,
            "content": self.content,
            "citations": self.citations,
            "word_count": self.word_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaperSection":
        return cls(
            name=data.get("name", ""),
            content=data.get("content", ""),
            citations=data.get("citations", []),
            word_count=data.get("word_count", 0),
        )


@dataclass
class BibEntry:
    doi: str
    title: str
    authors: List[str] = field(default_factory=list)
    venue: str = ""
    year: int = 0
    bibtex: str = ""
    source: str = "ossr_ingested"
    key: str = ""

    def __post_init__(self):
        if not self.key:
            first_author_last = self.authors[0].split()[-1].lower() if self.authors else "unknown"
            self.key = f"{first_author_last}{self.year}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doi": self.doi,
            "key": self.key,
            "title": self.title,
            "authors": self.authors,
            "venue": self.venue,
            "year": self.year,
            "bibtex": self.bibtex,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BibEntry":
        return cls(
            doi=data.get("doi", ""),
            title=data.get("title", ""),
            authors=data.get("authors", []),
            venue=data.get("venue", ""),
            year=data.get("year", 0),
            bibtex=data.get("bibtex", ""),
            source=data.get("source", "ossr_ingested"),
            key=data.get("key", ""),
        )


@dataclass
class PaperDraft:
    draft_id: str
    title: str
    authors: List[str] = field(default_factory=list)
    abstract: str = ""
    sections: List[PaperSection] = field(default_factory=list)
    bibliography: List[BibEntry] = field(default_factory=list)
    format: str = "ieee"
    review_scores: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.draft_id:
            self.draft_id = f"ais_draft_{uuid.uuid4().hex[:10]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "draft_id": self.draft_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "sections": [s.to_dict() for s in self.sections],
            "bibliography": [b.to_dict() for b in self.bibliography],
            "format": self.format,
            "review_scores": self.review_scores,
            "review": self.review_scores,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaperDraft":
        return cls(
            draft_id=data.get("draft_id", ""),
            title=data.get("title", ""),
            authors=data.get("authors", []),
            abstract=data.get("abstract", ""),
            sections=[PaperSection.from_dict(s) for s in data.get("sections", [])],
            bibliography=[BibEntry.from_dict(b) for b in data.get("bibliography", [])],
            format=data.get("format", "ieee"),
            review_scores=data.get("review_scores", {}),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", ""),
        )


# ── Experiment Spec (Stage 6) ──────────────────────────────────────


@dataclass
class ExperimentSpec:
    spec_id: str
    run_id: str
    idea_id: str
    template: str = ""
    seed_ideas: List[Dict[str, Any]] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    status: ExperimentStatus = ExperimentStatus.PENDING
    created_at: str = ""

    def __post_init__(self):
        if not self.spec_id:
            self.spec_id = f"ais_exp_{uuid.uuid4().hex[:10]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "run_id": self.run_id,
            "idea_id": self.idea_id,
            "template": self.template,
            "seed_ideas": self.seed_ideas,
            "config": self.config,
            "status": self.status.value if isinstance(self.status, ExperimentStatus) else self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentSpec":
        status = data.get("status", "pending")
        if isinstance(status, str):
            status = ExperimentStatus(status)
        return cls(
            spec_id=data.get("spec_id", ""),
            run_id=data.get("run_id", ""),
            idea_id=data.get("idea_id", ""),
            template=data.get("template", ""),
            seed_ideas=data.get("seed_ideas", []),
            config=data.get("config", {}),
            status=status,
            created_at=data.get("created_at", ""),
        )


# ── Experiment Result ──────────────────────────────────────────────


@dataclass
class ExperimentResult:
    result_id: str
    spec_id: str
    run_id: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    log_summary: str = ""
    paper_path: Optional[str] = None
    status: ExperimentStatus = ExperimentStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if not self.result_id:
            self.result_id = f"ais_res_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "spec_id": self.spec_id,
            "run_id": self.run_id,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "log_summary": self.log_summary,
            "paper_path": self.paper_path,
            "status": self.status.value if isinstance(self.status, ExperimentStatus) else self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentResult":
        status = data.get("status", "pending")
        if isinstance(status, str):
            status = ExperimentStatus(status)
        return cls(
            result_id=data.get("result_id", ""),
            spec_id=data.get("spec_id", ""),
            run_id=data.get("run_id", ""),
            metrics=data.get("metrics", {}),
            artifacts=data.get("artifacts", []),
            log_summary=data.get("log_summary", ""),
            paper_path=data.get("paper_path"),
            status=status,
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
        )


# ── Autoresearch Run ──────────────────────────────────────────────


@dataclass
class AutoresearchRun:
    auto_run_id: str
    idea_id: str
    run_id: Optional[str] = None
    node: str = "local"
    branch: str = ""
    status: AutoresearchStatus = AutoresearchStatus.QUEUED
    iterations: int = 0
    best_metric: Optional[float] = None
    metric_name: str = "val_bpb"
    results_tsv: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    error: Optional[str] = None

    def __post_init__(self):
        if not self.auto_run_id:
            self.auto_run_id = f"ais_auto_{uuid.uuid4().hex[:10]}"
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.branch:
            self.branch = f"autoresearch/{self.idea_id[:20]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "auto_run_id": self.auto_run_id,
            "idea_id": self.idea_id,
            "run_id": self.run_id,
            "node": self.node,
            "branch": self.branch,
            "status": self.status.value if isinstance(self.status, AutoresearchStatus) else self.status,
            "iterations": self.iterations,
            "best_metric": self.best_metric,
            "metric_name": self.metric_name,
            "results_tsv": self.results_tsv,
            "config": self.config,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }
