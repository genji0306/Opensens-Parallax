"""
Project Artifact Exporter
Builds full run artifacts (all stages) and renders readable HTML/PDF exports.
"""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Any, Dict, Iterable, List, Optional

from ..db import get_connection
from ..models.ais_models import PipelineRunDAO
from ..models.knowledge_models import KnowledgeArtifactDAO
from ..models.review_models import RevisionHistoryDAO
from ..models.workflow_models import WorkflowNode, WorkflowNodeDAO
from .knowledge.claim_graph import ClaimGraph


@dataclass(frozen=True)
class StageSpec:
    stage_id: str
    title: str
    stage_result_keys: tuple[str, ...]
    workflow_node_types: tuple[str, ...]


STAGE_SPECS: tuple[StageSpec, ...] = (
    StageSpec("crawl", "Stage 1 - Crawl & Ingest", ("crawl", "stage_1"), ("search",)),
    StageSpec("map", "Stage 1b - Research Map", ("map", "stage_1"), ("map",)),
    StageSpec("ideas", "Stage 2 - Ideation", ("ideas", "stage_2", "selected_idea_id"), ("ideate",)),
    StageSpec("debate", "Stage 3 - Debate", ("debate", "stage_3"), ("debate",)),
    StageSpec(
        "validate",
        "Stage 4 - Validation / Review",
        ("validate", "stage_4", "specialist_review"),
        ("validate", "specialist_review", "human_review"),
    ),
    StageSpec("draft", "Stage 5 - Draft", ("draft", "stage_5", "stage_5c"), ("draft",)),
    StageSpec(
        "experiment",
        "Stage 6 - Experiment Design",
        ("experiment", "stage_6", "experiment_design"),
        ("experiment_design", "experiment_run"),
    ),
    StageSpec("rehab", "Stage 7 - Rehab", ("rehab", "stage_7"), ("revise",)),
    StageSpec("pass", "Stage 8 - Pass", ("pass", "stage_8"), ("pass",)),
)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _status_priority(status: str) -> int:
    order = {
        "failed": 100,
        "running": 90,
        "completed": 80,
        "invalidated": 70,
        "skipped": 60,
        "pending": 50,
    }
    return order.get(status, 0)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class ProjectArtifactExporter:
    """Build + render full project artifacts for pipeline runs."""

    def build_bundle(self, run_id: str) -> Optional[Dict[str, Any]]:
        run = PipelineRunDAO.load(run_id)
        if not run:
            return None

        stage_results = run.stage_results if isinstance(run.stage_results, dict) else {}
        nodes = WorkflowNodeDAO.list_by_run(run_id)
        nodes_by_type = self._group_nodes_by_type(nodes)
        resources = self._load_resources(run_id, stage_results)
        used_stage_result_keys: set[str] = set()

        stages: List[Dict[str, Any]] = []
        for spec in STAGE_SPECS:
            stage_payload, sources = self._stage_payload(
                spec,
                stage_results,
                nodes_by_type,
                resources,
                used_stage_result_keys,
            )
            statuses = self._collect_statuses(spec, nodes_by_type)
            stages.append(
                {
                    "stage_id": spec.stage_id,
                    "title": spec.title,
                    "status": self._resolve_stage_status(statuses, stage_payload),
                    "sources": sources,
                    "preview": self._stage_preview(spec.stage_id, stage_payload),
                    "result": stage_payload or None,
                }
            )

        additional_stage_results = {
            key: value
            for key, value in stage_results.items()
            if key not in used_stage_result_keys and not _is_empty(value)
        }

        status_counts = self._workflow_status_counts(nodes)
        workflow_nodes = [self._node_snapshot(node) for node in nodes]

        return {
            "generated_at": datetime.now().isoformat(),
            "run": {
                "run_id": run.run_id,
                "research_idea": run.research_idea,
                "status": run.status.value if hasattr(run.status, "value") else run.status,
                "current_stage": run.current_stage,
                "created_at": run.created_at,
                "updated_at": run.updated_at,
                "error": run.error,
                "config": run.config if isinstance(run.config, dict) else {},
            },
            "workflow_summary": {
                "total_nodes": len(nodes),
                "status_counts": status_counts,
                "nodes": workflow_nodes,
            },
            "stages": stages,
            "resources": resources,
            "additional_stage_results": additional_stage_results,
            "raw_stage_results": stage_results,
        }

    def render_html(self, bundle: Dict[str, Any]) -> str:
        run = bundle.get("run", {})
        summary = bundle.get("workflow_summary", {})
        resources = bundle.get("resources", {})
        stages = bundle.get("stages", [])

        sections = [
            self._render_stage_overview(stages),
            self._render_workflow_section(summary),
            self._render_knowledge_section(resources.get("knowledge")),
            self._render_map_section(resources.get("topic_map"), resources.get("top_papers")),
            self._render_idea_section(resources.get("selected_idea")),
            self._render_debate_section(resources.get("debate")),
            self._render_draft_section(resources.get("draft")),
            self._render_experiment_section(resources.get("experiment_design")),
            self._render_review_section(resources.get("review")),
            self._render_translation_section(resources.get("translation")),
            self._render_appendix_section(
                bundle.get("additional_stage_results", {}),
                bundle.get("raw_stage_results", {}),
                run.get("config", {}),
            ),
        ]

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Full Project Artifact - {escape(str(run.get("run_id", "")))}</title>
  <style>
    :root {{
      --bg: #eef4f2;
      --panel: rgba(255,255,255,0.92);
      --panel-strong: #ffffff;
      --ink: #17212b;
      --muted: #64748b;
      --border: #d6e2df;
      --border-strong: #bccfcb;
      --accent: #0f8b8d;
      --accent-soft: #e0f4f1;
      --success: #1f9d55;
      --warning: #d97706;
      --danger: #d64545;
      --pending: #7b8798;
      --active: #2563eb;
      --shadow: 0 18px 45px rgba(23, 33, 43, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(15, 139, 141, 0.12), transparent 30%),
        radial-gradient(circle at top right, rgba(31, 157, 85, 0.10), transparent 22%),
        linear-gradient(180deg, #f8fbfa 0%, var(--bg) 60%, #f5f8f9 100%);
      font-family: "Avenir Next", "Segoe UI", Helvetica, Arial, sans-serif;
      line-height: 1.55;
    }}
    .wrap {{
      max-width: 1360px;
      margin: 0 auto;
      padding: 28px 22px 64px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(255,255,255,0.96), rgba(240,248,246,0.96));
      border: 1px solid var(--border);
      border-radius: 28px;
      box-shadow: var(--shadow);
      padding: 28px;
      margin-bottom: 22px;
      overflow: hidden;
      position: relative;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -40px -50px auto;
      width: 220px;
      height: 220px;
      background: radial-gradient(circle, rgba(15, 139, 141, 0.12), transparent 70%);
      pointer-events: none;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 10px;
      padding: 7px 14px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 36px;
      line-height: 1.12;
    }}
    .hero__idea {{
      max-width: 980px;
      margin: 0 0 20px;
      color: var(--muted);
      font-size: 18px;
    }}
    .hero__meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }}
    .metric {{
      background: rgba(255,255,255,0.86);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 14px 16px;
    }}
    .metric__label {{
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .metric__value {{
      display: block;
      font-size: 24px;
      font-weight: 800;
      line-height: 1.1;
    }}
    .metric__value--small {{
      font-size: 18px;
    }}
    .section {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 24px;
      margin-bottom: 22px;
    }}
    .section__header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 14px;
      margin-bottom: 18px;
    }}
    .section__title {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
    }}
    .section__subtitle {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      border-radius: 999px;
      background: #eef3f5;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .stage-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 14px;
    }}
    .stage-card {{
      background: var(--panel-strong);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
      min-height: 150px;
    }}
    .stage-card__top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
      margin-bottom: 12px;
    }}
    .stage-card__title {{
      margin: 0;
      font-size: 16px;
      line-height: 1.35;
    }}
    .stage-card__preview {{
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 12px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 92px;
      padding: 6px 12px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: #fff;
    }}
    .badge--done, .badge--completed {{ background: var(--success); }}
    .badge--active, .badge--running {{ background: var(--active); }}
    .badge--failed {{ background: var(--danger); }}
    .badge--invalidated {{ background: var(--warning); }}
    .badge--pending {{ background: var(--pending); }}
    .columns-2 {{
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
      gap: 18px;
    }}
    .columns-3 {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 18px;
    }}
    .panel-card {{
      background: var(--panel-strong);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
    }}
    .panel-card__title {{
      margin: 0 0 10px;
      font-size: 16px;
      line-height: 1.35;
    }}
    .panel-card__subtle {{
      color: var(--muted);
      font-size: 13px;
      margin: 0 0 12px;
    }}
    .workflow-table,
    .table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .workflow-table th,
    .workflow-table td,
    .table th,
    .table td {{
      text-align: left;
      vertical-align: top;
      padding: 10px 12px;
      border-top: 1px solid var(--border);
    }}
    .workflow-table th,
    .table th {{
      border-top: none;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .muted {{
      color: var(--muted);
    }}
    .mini-list,
    .rich-list,
    .detail-list {{
      margin: 0;
      padding-left: 18px;
    }}
    .mini-list li,
    .rich-list li,
    .detail-list li {{
      margin: 6px 0;
    }}
    .prose {{
      color: var(--ink);
      font-size: 14px;
    }}
    .prose h1,
    .prose h2,
    .prose h3,
    .prose h4,
    .prose h5,
    .prose h6 {{
      margin: 18px 0 10px;
      font-size: 18px;
      line-height: 1.3;
    }}
    .prose p {{
      margin: 0 0 12px;
    }}
    .label {{
      display: inline-block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .topic-bars {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .topic-bar__row {{
      display: grid;
      grid-template-columns: minmax(0, 220px) minmax(0, 1fr) 54px;
      gap: 10px;
      align-items: center;
    }}
    .topic-bar__name {{
      font-size: 13px;
      font-weight: 600;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .topic-bar__track {{
      position: relative;
      height: 12px;
      background: #edf2f4;
      border-radius: 999px;
      overflow: hidden;
    }}
    .topic-bar__fill {{
      position: absolute;
      inset: 0 auto 0 0;
      border-radius: 999px;
      background: linear-gradient(90deg, #0f8b8d, #56c3b2);
    }}
    .topic-bar__value {{
      font-size: 12px;
      font-weight: 700;
      text-align: right;
      color: var(--muted);
    }}
    .paper-list,
    .idea-scores,
    .agent-list,
    .gaps-grid,
    .experiment-grid,
    .novelty-grid,
    .section-list,
    .round-list {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .paper-card,
    .agent-card,
    .gap-card,
    .experiment-card,
    .novelty-card,
    .draft-card,
    .round-card {{
      background: var(--panel-strong);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
    }}
    .paper-card h4,
    .agent-card h4,
    .gap-card h4,
    .experiment-card h4,
    .novelty-card h4,
    .draft-card h4,
    .round-card h4 {{
      margin: 0 0 8px;
      font-size: 16px;
      line-height: 1.35;
    }}
    .score-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 10px;
    }}
    .score-card {{
      background: #f8fafb;
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 12px;
    }}
    .score-card__value {{
      display: block;
      font-size: 22px;
      font-weight: 800;
      line-height: 1.05;
    }}
    .score-card__label {{
      display: block;
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .severity {{
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .severity--critical {{
      color: var(--danger);
      background: rgba(214, 69, 69, 0.10);
    }}
    .severity--major {{
      color: var(--warning);
      background: rgba(217, 119, 6, 0.12);
    }}
    .severity--medium,
    .severity--minor {{
      color: var(--accent);
      background: rgba(15, 139, 141, 0.10);
    }}
    .turn {{
      border-top: 1px solid var(--border);
      padding-top: 12px;
      margin-top: 12px;
    }}
    .turn:first-child {{
      margin-top: 0;
      padding-top: 0;
      border-top: none;
    }}
    .turn__meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 10px;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .turn__content {{
      font-size: 14px;
      white-space: pre-wrap;
    }}
    .doi-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 10px;
    }}
    .doi {{
      padding: 5px 8px;
      border-radius: 999px;
      background: #f1f5f7;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
    }}
    .coverage {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .coverage__track {{
      flex: 1;
      height: 8px;
      border-radius: 999px;
      background: #edf2f4;
      overflow: hidden;
    }}
    .coverage__fill {{
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, #0f8b8d, #62c584);
    }}
    .coverage__fill--medium {{
      background: linear-gradient(90deg, #eab308, #f59e0b);
    }}
    .coverage__fill--low {{
      background: linear-gradient(90deg, #ef4444, #f97316);
    }}
    .coverage__value {{
      min-width: 42px;
      text-align: right;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    details {{
      border: 1px solid var(--border);
      border-radius: 16px;
      background: rgba(255,255,255,0.88);
      overflow: hidden;
    }}
    summary {{
      cursor: pointer;
      padding: 14px 16px;
      font-weight: 700;
      list-style: none;
      user-select: none;
    }}
    summary::-webkit-details-marker {{
      display: none;
    }}
    .details-body {{
      padding: 0 16px 16px;
    }}
    .appendix pre {{
      margin: 0;
      padding: 14px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: #f6f8fb;
      color: #243244;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      line-height: 1.5;
    }}
    .graph-shell {{
      background: linear-gradient(180deg, #fcfefe, #f5f9f8);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 10px;
      overflow: auto;
    }}
    .graph-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 12px;
      font-size: 12px;
      color: var(--muted);
    }}
    .graph-legend span {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .graph-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}
    .footer {{
      margin-top: 18px;
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }}
    @media (max-width: 980px) {{
      .columns-2,
      .columns-3 {{
        grid-template-columns: 1fr;
      }}
      .topic-bar__row {{
        grid-template-columns: 1fr;
      }}
      .hero__meta,
      .stage-grid,
      .score-grid {{
        grid-template-columns: 1fr;
      }}
    }}
    @media print {{
      body {{
        background: #fff;
      }}
      .wrap {{
        max-width: none;
        padding: 0;
      }}
      .hero,
      .section {{
        box-shadow: none;
        break-inside: avoid;
        margin-bottom: 16px;
      }}
      details {{
        break-inside: avoid;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="eyebrow">Parallax Full Artifact</div>
      <h1>{escape(str(run.get("run_id", "")))}</h1>
      <p class="hero__idea">{escape(str(run.get("research_idea", "")))}</p>
      <div class="hero__meta">
        {self._metric_card("Status", str(run.get("status", "unknown")), small=True)}
        {self._metric_card("Current Stage", str(run.get("current_stage", "")))}
        {self._metric_card("Workflow Nodes", str(summary.get("total_nodes", 0)))}
        {self._metric_card("Generated", self._format_timestamp(bundle.get("generated_at", "")), small=True)}
        {self._metric_card("Created", self._format_timestamp(run.get("created_at", "")), small=True)}
        {self._metric_card("Updated", self._format_timestamp(run.get("updated_at", "")), small=True)}
      </div>
    </section>

    {"".join(section for section in sections if section)}

    <div class="footer">Generated by Parallax Full Artifact Exporter.</div>
  </div>
</body>
</html>"""

    def render_pdf(self, bundle: Dict[str, Any]) -> bytes:
        lines = self._bundle_to_text_lines(bundle)
        return self._lines_to_pdf(lines)

    def _load_resources(self, run_id: str, stage_results: Dict[str, Any]) -> Dict[str, Any]:
        selected_idea_id = stage_results.get("selected_idea_id")
        experiment_design = (
            stage_results.get("experiment_design")
            or stage_results.get("stage_6")
            or stage_results.get("experiment")
        )
        stage_3 = stage_results.get("stage_3") if isinstance(stage_results.get("stage_3"), dict) else {}
        stage_5 = stage_results.get("stage_5") if isinstance(stage_results.get("stage_5"), dict) else {}

        return {
            "selected_idea": self._load_selected_idea(selected_idea_id, stage_results.get("stage_2")),
            "debate": self._load_debate(stage_3.get("simulation_id")),
            "draft": self._load_draft(stage_5.get("draft_id")),
            "experiment_design": experiment_design if isinstance(experiment_design, dict) else None,
            "topic_map": self._load_topic_map(run_id),
            "top_papers": self._load_top_papers(run_id),
            "knowledge": self._load_knowledge_bundle(run_id),
            "review": self._load_review_bundle(run_id, stage_results),
            "translation": self._load_translation_bundle(stage_results),
        }

    def _load_selected_idea(self, selected_idea_id: Any, fallback_stage_2: Any) -> Optional[Dict[str, Any]]:
        if isinstance(selected_idea_id, str) and selected_idea_id:
            conn = get_connection()
            row = conn.execute(
                "SELECT data FROM research_ideas WHERE idea_id = ?",
                (selected_idea_id,),
            ).fetchone()
            if row and row["data"]:
                try:
                    data = json.loads(row["data"])
                    data["idea_id"] = data.get("idea_id") or selected_idea_id
                    return data
                except json.JSONDecodeError:
                    pass

        if isinstance(fallback_stage_2, dict):
            top_idea = fallback_stage_2.get("top_idea")
            if isinstance(top_idea, dict):
                return top_idea
        return None

    def _load_debate(self, simulation_id: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(simulation_id, str) or not simulation_id:
            return None

        conn = get_connection()
        row = conn.execute(
            "SELECT data FROM simulations WHERE simulation_id = ?",
            (simulation_id,),
        ).fetchone()
        if not row or not row["data"]:
            return None

        try:
            data = json.loads(row["data"])
        except json.JSONDecodeError:
            return None

        transcript = data.get("transcript") if isinstance(data.get("transcript"), list) else []
        rounds: Dict[int, List[Dict[str, Any]]] = {}
        agents: Dict[str, Dict[str, Any]] = {}
        total_citations = 0

        for turn in transcript:
            if not isinstance(turn, dict):
                continue
            round_num = _safe_int(turn.get("round_num"), 0)
            rounds.setdefault(round_num, []).append(turn)

            agent_id = str(turn.get("agent_id") or turn.get("agent_name") or "agent")
            agent = agents.setdefault(
                agent_id,
                {
                    "agent_id": agent_id,
                    "agent_name": str(turn.get("agent_name") or "Agent"),
                    "agent_role": str(turn.get("agent_role") or ""),
                    "turn_count": 0,
                    "citation_count": 0,
                },
            )
            agent["turn_count"] += 1
            cited = turn.get("cited_dois") if isinstance(turn.get("cited_dois"), list) else []
            agent["citation_count"] += len(cited)
            total_citations += len(cited)

        transcript_by_round = [
            {"round": round_num, "turns": rounds[round_num]}
            for round_num in sorted(rounds)
        ]
        agent_list = sorted(
            agents.values(),
            key=lambda agent: (-_safe_int(agent.get("turn_count")), str(agent.get("agent_name", ""))),
        )

        return {
            "simulation_id": simulation_id,
            "status": data.get("status", ""),
            "discussion_format": data.get("discussion_format", ""),
            "topic": data.get("topic", ""),
            "agent_ids": data.get("agent_ids", []),
            "max_rounds": data.get("max_rounds"),
            "current_round": data.get("current_round"),
            "transcript_length": data.get("transcript_length", len(transcript)),
            "started_at": data.get("started_at", ""),
            "completed_at": data.get("completed_at", ""),
            "agent_count": len(agent_list),
            "total_citations": total_citations,
            "agents": agent_list,
            "transcript": transcript,
            "transcript_by_round": transcript_by_round,
        }

    def _load_draft(self, draft_id: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(draft_id, str) or not draft_id:
            return None

        conn = get_connection()
        row = conn.execute(
            "SELECT data FROM paper_drafts WHERE draft_id = ?",
            (draft_id,),
        ).fetchone()
        if not row or not row["data"]:
            return None

        try:
            data = json.loads(row["data"])
        except json.JSONDecodeError:
            return None

        sections = data.get("sections") if isinstance(data.get("sections"), list) else []
        bibliography = data.get("bibliography") if isinstance(data.get("bibliography"), list) else []
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

        return {
            "draft_id": draft_id,
            "title": data.get("title", ""),
            "abstract": data.get("abstract", ""),
            "sections": sections,
            "bibliography": bibliography,
            "format": data.get("format", ""),
            "review": data.get("review") if isinstance(data.get("review"), dict) else {},
            "metadata": metadata,
            "created_at": data.get("created_at", ""),
            "total_word_count": metadata.get("total_word_count", 0),
            "section_count": metadata.get("section_count", len(sections)),
            "citation_count": metadata.get("citation_count", len(bibliography)),
        }

    def _load_topic_map(self, run_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        topic_rows = conn.execute(
            """
            SELECT t.topic_id, t.name, t.paper_count, t.metadata
            FROM run_topics rt
            JOIN topics t ON t.topic_id = rt.topic_id
            WHERE rt.run_id = ?
            ORDER BY t.paper_count DESC, t.name ASC
            LIMIT 60
            """,
            (run_id,),
        ).fetchall()

        if not topic_rows:
            return None

        unique_topics: Dict[str, Dict[str, Any]] = {}
        for row in topic_rows:
            name = str(row["name"] or "Untitled topic").strip()
            if not name:
                name = "Untitled topic"
            meta = {}
            if row["metadata"]:
                try:
                    meta = json.loads(row["metadata"])
                except json.JSONDecodeError:
                    meta = {}

            entry = {
                "topic_id": row["topic_id"],
                "name": name,
                "paper_count": _safe_int(row["paper_count"]),
                "gaps": meta.get("gaps", []) if isinstance(meta.get("gaps"), list) else [],
                "novelty_opportunities": (
                    meta.get("novelty_opportunities", [])
                    if isinstance(meta.get("novelty_opportunities"), list)
                    else []
                ),
                "cluster_summary": str(meta.get("cluster_summary") or ""),
            }

            existing = unique_topics.get(name)
            if existing is None or entry["paper_count"] > existing["paper_count"]:
                unique_topics[name] = entry

        top_topics = sorted(
            unique_topics.values(),
            key=lambda item: (-_safe_int(item.get("paper_count")), str(item.get("name", ""))),
        )[:12]

        paper_total = conn.execute(
            "SELECT COUNT(*) AS count FROM run_papers WHERE run_id = ?",
            (run_id,),
        ).fetchone()["count"]
        topic_total = conn.execute(
            "SELECT COUNT(*) AS count FROM run_topics WHERE run_id = ?",
            (run_id,),
        ).fetchone()["count"]

        gap_total = sum(len(topic.get("gaps", [])) for topic in top_topics)
        novelty_total = sum(len(topic.get("novelty_opportunities", [])) for topic in top_topics)

        return {
            "paper_total": _safe_int(paper_total),
            "topic_total": _safe_int(topic_total),
            "top_topics": top_topics,
            "gap_total": gap_total,
            "novelty_total": novelty_total,
        }

    def _load_top_papers(self, run_id: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT p.paper_id, p.doi, p.title, p.abstract, p.source, p.citation_count
            FROM papers p
            JOIN run_papers rp ON p.paper_id = rp.paper_id
            WHERE rp.run_id = ?
            ORDER BY p.citation_count DESC, p.title ASC
            LIMIT 10
            """,
            (run_id,),
        ).fetchall()

        return [
            {
                "paper_id": row["paper_id"],
                "doi": row["doi"],
                "title": row["title"],
                "abstract": row["abstract"],
                "source": row["source"],
                "citation_count": _safe_int(row["citation_count"]),
            }
            for row in rows
        ]

    def _load_knowledge_bundle(self, run_id: str) -> Optional[Dict[str, Any]]:
        artifact = KnowledgeArtifactDAO.load(run_id)
        if not artifact:
            return None

        artifact_dict = artifact.to_dict()
        claim_graph = ClaimGraph().build(run_id)
        novelty_map = self._build_novelty_map(artifact_dict)
        question_tree = self._build_question_tree(artifact_dict)

        return {
            "artifact": artifact_dict,
            "claim_graph": claim_graph,
            "novelty_map": novelty_map,
            "question_tree": question_tree,
            "summary": {
                "claims": len(artifact_dict.get("claims", [])),
                "evidence": len(artifact_dict.get("evidence", [])),
                "gaps": len(artifact_dict.get("gaps", [])),
                "novelty_assessments": len(artifact_dict.get("novelty_assessments", [])),
                "questions": len(artifact_dict.get("sub_questions", [])),
                "argument_sections": len(artifact_dict.get("argument_skeleton", [])),
            },
        }

    def _load_review_bundle(self, run_id: str, stage_results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        rounds = [round_.to_dict() for round_ in RevisionHistoryDAO.list_by_run(run_id)]
        latest = rounds[-1] if rounds else None
        revision_plan = (
            stage_results.get("review_revision_plan")
            if isinstance(stage_results.get("review_revision_plan"), dict)
            else None
        )
        rebuttal = (
            stage_results.get("review_rebuttal")
            if isinstance(stage_results.get("review_rebuttal"), dict)
            else None
        )

        if not rounds and not revision_plan and not rebuttal:
            return None

        score_trajectory = [
            {
                "round": _safe_int(round_.get("round_number")),
                "avg_score": float(round_.get("avg_score") or 0),
            }
            for round_ in rounds
            if isinstance(round_, dict)
        ]
        improving = None
        if len(score_trajectory) >= 2:
            improving = score_trajectory[-1]["avg_score"] >= score_trajectory[-2]["avg_score"]

        return {
            "rounds": rounds,
            "latest": latest,
            "summary": {
                "total_rounds": len(rounds),
                "latest_score": float(latest.get("avg_score") or 0) if isinstance(latest, dict) else 0,
                "improving": improving,
            },
            "score_trajectory": score_trajectory,
            "revision_plan": revision_plan,
            "rebuttal": rebuttal,
        }

    def _load_translation_bundle(self, stage_results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        outputs = (
            stage_results.get("translation_outputs")
            if isinstance(stage_results.get("translation_outputs"), dict)
            else {}
        )
        normalized_outputs = {
            str(mode): payload
            for mode, payload in outputs.items()
            if isinstance(payload, dict)
        }

        direct_mode_keys = {
            "journal": "journal_translation",
            "grant": "grant_translation",
            "funding": "funding_translation",
            "patent": "patent_analysis",
            "commercial": "commercial_analysis",
        }
        for mode, key in direct_mode_keys.items():
            value = stage_results.get(key)
            if mode not in normalized_outputs and isinstance(value, dict):
                normalized_outputs[mode] = value

        latest = (
            stage_results.get("translation_latest")
            if isinstance(stage_results.get("translation_latest"), dict)
            else None
        )
        if not normalized_outputs and not latest:
            return None

        preferred_order = ["journal", "grant", "funding", "patent", "commercial"]
        ordered_modes = [mode for mode in preferred_order if mode in normalized_outputs]
        ordered_modes.extend(
            sorted(mode for mode in normalized_outputs.keys() if mode not in preferred_order)
        )

        return {
            "outputs": normalized_outputs,
            "latest": latest,
            "modes": ordered_modes,
        }

    def _build_novelty_map(self, artifact: Dict[str, Any]) -> Dict[str, Any]:
        claims = artifact.get("claims") if isinstance(artifact.get("claims"), list) else []
        assessments = (
            artifact.get("novelty_assessments")
            if isinstance(artifact.get("novelty_assessments"), list)
            else []
        )
        claim_by_id = {
            str(claim.get("claim_id")): claim
            for claim in claims
            if isinstance(claim, dict) and claim.get("claim_id")
        }

        heatmap: List[Dict[str, Any]] = []
        for item in assessments:
            if not isinstance(item, dict):
                continue
            claim_id = str(item.get("claim_id") or "")
            score = float(item.get("novelty_score") or 0)
            zone = "novel" if score >= 0.7 else "partial" if score >= 0.3 else "covered"
            heatmap.append(
                {
                    "claim_id": claim_id,
                    "text": str(claim_by_id.get(claim_id, {}).get("text", "")),
                    "novelty_score": score,
                    "zone": zone,
                    "explanation": str(item.get("explanation") or ""),
                    "differentiators": (
                        item.get("differentiators")
                        if isinstance(item.get("differentiators"), list)
                        else []
                    ),
                }
            )

        scores = [float(item.get("novelty_score") or 0) for item in assessments if isinstance(item, dict)]
        return {
            "heatmap": heatmap,
            "stats": {
                "avg_novelty": round(sum(scores) / max(len(scores), 1), 2) if scores else 0,
                "novel_count": sum(1 for score in scores if score >= 0.7),
                "partial_count": sum(1 for score in scores if 0.3 <= score < 0.7),
                "covered_count": sum(1 for score in scores if score < 0.3),
            },
        }

    def _build_question_tree(self, artifact: Dict[str, Any]) -> Dict[str, Any]:
        questions = artifact.get("sub_questions") if isinstance(artifact.get("sub_questions"), list) else []
        nodes: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []

        for item in questions:
            if not isinstance(item, dict):
                continue
            question_id = str(item.get("question_id") or "")
            if not question_id:
                continue
            nodes[question_id] = {
                "id": question_id,
                "text": str(item.get("text") or ""),
                "evidence_coverage": float(item.get("evidence_coverage") or 0),
                "parent_id": item.get("parent_id"),
                "children": [],
            }
            order.append(question_id)

        roots: List[Dict[str, Any]] = []
        for question_id in order:
            node = nodes[question_id]
            parent_id = node.get("parent_id")
            if parent_id and parent_id in nodes:
                nodes[parent_id]["children"].append(node)
            else:
                roots.append(node)

        coverages = [float(node.get("evidence_coverage") or 0) for node in nodes.values()]
        return {
            "tree": roots,
            "stats": {
                "total_questions": len(nodes),
                "avg_coverage": round(sum(coverages) / max(len(coverages), 1), 2) if coverages else 0,
                "uncovered_count": sum(1 for coverage in coverages if coverage < 0.3),
            },
        }

    def _stage_payload(
        self,
        spec: StageSpec,
        stage_results: Dict[str, Any],
        nodes_by_type: Dict[str, List[WorkflowNode]],
        resources: Dict[str, Any],
        used_stage_result_keys: set[str],
    ) -> tuple[Dict[str, Any], List[str]]:
        payload: Dict[str, Any] = {}
        sources: List[str] = []

        for key in spec.stage_result_keys:
            value = stage_results.get(key)
            if _is_empty(value):
                continue
            payload[f"stage_results.{key}"] = value
            sources.append(f"stage_results.{key}")
            used_stage_result_keys.add(key)

        for node_type in spec.workflow_node_types:
            node_rows = nodes_by_type.get(node_type, [])
            if not node_rows:
                continue
            payload[f"workflow.{node_type}"] = [self._node_snapshot(node) for node in node_rows]
            sources.append(f"workflow.{node_type}")

        if spec.stage_id == "map" and resources.get("topic_map"):
            payload["resource.topic_map"] = resources["topic_map"]
            sources.append("resource.topic_map")
        elif spec.stage_id == "ideas" and resources.get("selected_idea"):
            payload["resource.selected_idea"] = resources["selected_idea"]
            sources.append("resource.selected_idea")
        elif spec.stage_id == "debate" and resources.get("debate"):
            payload["resource.debate"] = resources["debate"]
            sources.append("resource.debate")
        elif spec.stage_id == "draft" and resources.get("draft"):
            payload["resource.draft"] = resources["draft"]
            sources.append("resource.draft")
        elif spec.stage_id == "experiment" and resources.get("experiment_design"):
            payload["resource.experiment_design"] = resources["experiment_design"]
            sources.append("resource.experiment_design")

        return payload, sources

    def _stage_preview(self, stage_id: str, payload: Dict[str, Any]) -> str:
        if stage_id == "crawl":
            stage_1 = payload.get("stage_results.stage_1", {})
            if isinstance(stage_1, dict):
                return (
                    f"{_safe_int(stage_1.get('papers_ingested'))} papers ingested, "
                    f"{_safe_int(stage_1.get('topics_found'))} topics found"
                )
        if stage_id == "map":
            topic_map = payload.get("resource.topic_map", {})
            if isinstance(topic_map, dict):
                return (
                    f"{_safe_int(topic_map.get('topic_total'))} topic links, "
                    f"{_safe_int(topic_map.get('paper_total'))} papers"
                )
        if stage_id == "ideas":
            idea = payload.get("resource.selected_idea", {})
            if isinstance(idea, dict) and idea.get("title"):
                return str(idea.get("title"))
            stage_2 = payload.get("stage_results.stage_2", {})
            if isinstance(stage_2, dict):
                return f"{_safe_int(stage_2.get('ideas_generated'))} ideas generated"
        if stage_id == "debate":
            debate = payload.get("resource.debate", {})
            if isinstance(debate, dict):
                return (
                    f"{_safe_int(debate.get('agent_count'))} agents, "
                    f"{_safe_int(debate.get('current_round') or debate.get('max_rounds'))} rounds, "
                    f"{_safe_int(debate.get('transcript_length'))} turns"
                )
        if stage_id == "draft":
            draft = payload.get("resource.draft", {})
            if isinstance(draft, dict):
                return (
                    f"{_safe_int(draft.get('section_count'))} sections, "
                    f"{_safe_int(draft.get('total_word_count'))} words"
                )
        if stage_id == "experiment":
            experiment = payload.get("resource.experiment_design", {})
            if isinstance(experiment, dict):
                gaps = experiment.get("gaps") if isinstance(experiment.get("gaps"), list) else []
                experiments = (
                    experiment.get("experiments")
                    if isinstance(experiment.get("experiments"), list)
                    else experiment.get("proposed_experiments", [])
                )
                if isinstance(experiments, list):
                    return f"{len(gaps)} evidence gaps, {len(experiments)} proposed experiments"

        return "No stage data available."

    def _render_stage_overview(self, stages: List[Dict[str, Any]]) -> str:
        cards = []
        for stage in stages:
            status = str(stage.get("status", "pending"))
            source_chips = "".join(
                f"<span class='chip'>{escape(str(source))}</span>"
                for source in (stage.get("sources") or [])
            )
            cards.append(
                f"""
                <article class="stage-card">
                  <div class="stage-card__top">
                    <h3 class="stage-card__title">{escape(str(stage.get("title", "")))}</h3>
                    <span class="badge badge--{escape(status)}">{escape(status)}</span>
                  </div>
                  <div class="stage-card__preview">{escape(str(stage.get("preview", "")))}</div>
                  <div class="chip-row">{source_chips or "<span class='chip'>No sources attached</span>"}</div>
                </article>
                """
            )

        return f"""
        <section class="section">
          <div class="section__header">
            <div>
              <h2 class="section__title">Pipeline Overview</h2>
              <p class="section__subtitle">Stage-by-stage status with attached artifact sources.</p>
            </div>
          </div>
          <div class="stage-grid">
            {''.join(cards)}
          </div>
        </section>
        """

    def _render_workflow_section(self, summary: Dict[str, Any]) -> str:
        nodes = summary.get("nodes") if isinstance(summary.get("nodes"), list) else []
        status_counts = summary.get("status_counts") if isinstance(summary.get("status_counts"), dict) else {}
        rows = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            outputs = node.get("outputs", {})
            output_preview = ""
            if isinstance(outputs, dict) and outputs:
                output_preview = ", ".join(
                    f"{key}: {value}" for key, value in list(outputs.items())[:4]
                )
            rows.append(
                f"""
                <tr>
                  <td>{escape(str(node.get("label", "")))}</td>
                  <td>{escape(str(node.get("node_type", "")))}</td>
                  <td>{escape(str(node.get("status", "")))}</td>
                  <td>{escape(str(output_preview or "—"))}</td>
                </tr>
                """
            )

        chips = "".join(
            f"<span class='chip'>{escape(str(status))}: {escape(str(count))}</span>"
            for status, count in status_counts.items()
        )

        return f"""
        <section class="section">
          <div class="section__header">
            <div>
              <h2 class="section__title">Workflow Nodes</h2>
              <p class="section__subtitle">Execution summary for the DAG nodes that built this run.</p>
            </div>
            <div class="chip-row">{chips}</div>
          </div>
          <div class="panel-card">
            <table class="workflow-table">
              <thead>
                <tr>
                  <th>Node</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Outputs</th>
                </tr>
              </thead>
              <tbody>
                {''.join(rows) or "<tr><td colspan='4' class='muted'>No workflow nodes found.</td></tr>"}
              </tbody>
            </table>
          </div>
        </section>
        """

    def _render_knowledge_section(self, knowledge: Any) -> str:
        if not isinstance(knowledge, dict):
            return ""

        summary = knowledge.get("summary") if isinstance(knowledge.get("summary"), dict) else {}
        artifact = knowledge.get("artifact") if isinstance(knowledge.get("artifact"), dict) else {}
        novelty_map = knowledge.get("novelty_map") if isinstance(knowledge.get("novelty_map"), dict) else {}
        raw_question_tree = knowledge.get("question_tree")
        question_tree = raw_question_tree if isinstance(raw_question_tree, dict) else {}

        claim_rows = "".join(
            f"""
            <div class="paper-card">
              <div class="chip-row" style="margin-bottom: 8px">
                <span class="chip">{escape(str(claim.get("category", "claim")))}</span>
                <span class="chip">confidence {self._pct(float(claim.get("confidence") or 0))}</span>
              </div>
              <h4>{escape(str(claim.get("text", "")))}</h4>
              {self._render_string_list("Supporting evidence", claim.get("metadata", {}).get("supporting_evidence"))}
              {self._render_string_list("Contradicting evidence", claim.get("metadata", {}).get("contradicting_evidence"))}
            </div>
            """
            for claim in artifact.get("claims", [])
            if isinstance(claim, dict)
        )

        gap_rows = "".join(
            f"""
            <div class="gap-card">
              <div class="chip-row" style="margin-bottom: 8px">
                <span class="severity severity--{escape(str(gap.get("severity", "medium")))}">
                  {escape(str(gap.get("severity", "medium")))}
                </span>
              </div>
              <h4>{escape(str(gap.get("description", "")))}</h4>
              <p class="muted">{escape(str(gap.get("suggested_approach", "")))}</p>
              <p><strong>Evidence needed:</strong> {escape(str(gap.get("evidence_needed", "")))}</p>
            </div>
            """
            for gap in artifact.get("gaps", [])
            if isinstance(gap, dict)
        )

        evidence_rows = "".join(
            f"""
            <div class="paper-card">
              <div class="chip-row" style="margin-bottom: 8px">
                <span class="chip">{escape(str(evidence.get("source_type", "evidence")))}</span>
                <span class="chip">confidence {self._pct(float(evidence.get("confidence") or 0))}</span>
              </div>
              <h4>{escape(str(evidence.get("title", "")))}</h4>
              <p class="muted">{escape(str(evidence.get("excerpt", "")))}</p>
            </div>
            """
            for evidence in artifact.get("evidence", [])
            if isinstance(evidence, dict)
        )

        novelty_cards = self._render_novelty_cards(novelty_map)
        question_cards = self._render_question_tree(question_tree)
        hypothesis = artifact.get("hypothesis") if isinstance(artifact.get("hypothesis"), dict) else None
        argument_skeleton = (
            artifact.get("argument_skeleton")
            if isinstance(artifact.get("argument_skeleton"), list)
            else []
        )

        return f"""
        <section class="section">
          <div class="section__header">
            <div>
              <h2 class="section__title">Knowledge Mapping</h2>
              <p class="section__subtitle">Claims, evidence, gaps, novelty mapping, and decomposed questions from the knowledge artifact.</p>
            </div>
            <div class="chip-row">
              <span class="chip">{_safe_int(summary.get("claims"))} claims</span>
              <span class="chip">{_safe_int(summary.get("evidence"))} evidence</span>
              <span class="chip">{_safe_int(summary.get("gaps"))} gaps</span>
              <span class="chip">{_safe_int(summary.get("questions"))} questions</span>
            </div>
          </div>

          <div class="columns-2">
            <div class="panel-card">
              <h3 class="panel-card__title">Claim-Evidence Graph</h3>
              <p class="panel-card__subtle">Static export of the claim graph so the artifact opens as a visualization instead of raw JSON.</p>
              {self._render_claim_graph(knowledge.get("claim_graph"))}
            </div>
            <div class="panel-card">
              <h3 class="panel-card__title">Novelty Map</h3>
              <p class="panel-card__subtle">Novel vs covered claims derived from stored novelty assessments.</p>
              {novelty_cards}
            </div>
          </div>

          <div style="height: 18px"></div>

          <div class="columns-2">
            <div class="panel-card">
              <h3 class="panel-card__title">Question Tree</h3>
              <p class="panel-card__subtle">Evidence coverage across the decomposed research questions.</p>
              {question_cards}
            </div>
            <div class="panel-card">
              <h3 class="panel-card__title">Contribution Hypothesis</h3>
              {self._render_hypothesis(hypothesis)}
              {self._render_argument_skeleton(argument_skeleton)}
            </div>
          </div>

          <div style="height: 18px"></div>

          <div class="columns-3">
            <div class="panel-card">
              <h3 class="panel-card__title">Claims</h3>
              <div class="paper-list">{claim_rows or "<p class='muted'>No claims available.</p>"}</div>
            </div>
            <div class="panel-card">
              <h3 class="panel-card__title">Evidence</h3>
              <div class="paper-list">{evidence_rows or "<p class='muted'>No evidence available.</p>"}</div>
            </div>
            <div class="panel-card">
              <h3 class="panel-card__title">Gaps</h3>
              <div class="gaps-grid">{gap_rows or "<p class='muted'>No gaps available.</p>"}</div>
            </div>
          </div>
        </section>
        """

    def _render_map_section(self, topic_map: Any, top_papers: Any) -> str:
        if not isinstance(topic_map, dict) and not isinstance(top_papers, list):
            return ""

        top_topics = topic_map.get("top_topics") if isinstance(topic_map, dict) and isinstance(topic_map.get("top_topics"), list) else []
        max_papers = max((_safe_int(topic.get("paper_count")) for topic in top_topics), default=1)
        topic_rows = []
        for topic in top_topics:
            if not isinstance(topic, dict):
                continue
            width = int((_safe_int(topic.get("paper_count")) / max_papers) * 100) if max_papers else 0
            notes = []
            if topic.get("gaps"):
                notes.append(f"{len(topic.get('gaps', []))} gaps")
            if topic.get("novelty_opportunities"):
                notes.append(f"{len(topic.get('novelty_opportunities', []))} novelty leads")
            note_text = " • ".join(notes) if notes else (topic.get("cluster_summary") or "")
            topic_rows.append(
                f"""
                <div class="topic-bar__row">
                  <div>
                    <div class="topic-bar__name">{escape(str(topic.get("name", "")))}</div>
                    <div class="muted" style="font-size: 12px">{escape(str(note_text))}</div>
                  </div>
                  <div class="topic-bar__track">
                    <div class="topic-bar__fill" style="width: {width}%"></div>
                  </div>
                  <div class="topic-bar__value">{_safe_int(topic.get("paper_count"))}</div>
                </div>
                """
            )

        paper_cards = []
        paper_text_list = []
        if isinstance(top_papers, list):
            for paper in top_papers:
                if not isinstance(paper, dict):
                    continue
                title = escape(str(paper.get("title", "")))
                doi = escape(str(paper.get("doi", "")))
                paper_cards.append(
                    f"""
                    <div class="paper-card">
                      <div class="chip-row" style="margin-bottom: 8px">
                        <span class="chip">{escape(str(paper.get("source", "")))}</span>
                        <span class="chip">{_safe_int(paper.get("citation_count"))} citations</span>
                      </div>
                      <h4>{title}</h4>
                      <p class="muted">{escape(str(paper.get("abstract", "")))}</p>
                      <p><strong>DOI:</strong> {doi or "Unavailable"}</p>
                    </div>
                    """
                )
                paper_text_list.append(
                    f"<div><strong>{title}</strong> — DOI: {doi or 'Unavailable'}</div>"
                )

        return f"""
        <section class="section">
          <div class="section__header">
            <div>
              <h2 class="section__title">Research Map & Literature</h2>
              <p class="section__subtitle">Top topic clusters and the most cited papers attached to the run.</p>
            </div>
            <div class="chip-row">
              <span class="chip">{_safe_int(topic_map.get("paper_total") if isinstance(topic_map, dict) else 0)} papers</span>
              <span class="chip">{_safe_int(topic_map.get("topic_total") if isinstance(topic_map, dict) else 0)} topics</span>
              <span class="chip">{_safe_int(topic_map.get("gap_total") if isinstance(topic_map, dict) else 0)} mapped gaps</span>
            </div>
          </div>

          <div class="columns-2">
            <div class="panel-card">
              <h3 class="panel-card__title">Top Topics</h3>
              <div class="topic-bars">{''.join(topic_rows) or "<p class='muted'>No topic map available.</p>"}</div>
            </div>
            <div class="panel-card">
              <h3 class="panel-card__title">Top Papers</h3>
              <div class="paper-list">{''.join(paper_cards) or "<p class='muted'>No papers attached.</p>"}</div>
            </div>
          </div>

          <div style="height: 18px"></div>

          <div class="panel-card">
            <h3 class="panel-card__title">Paper List (Title + DOI)</h3>
            <div class="prose">{''.join(paper_text_list) or "<p class='muted'>No papers attached.</p>"}</div>
          </div>
        </section>
        """

    def _render_idea_section(self, idea: Any) -> str:
        if not isinstance(idea, dict):
            return ""

        score_breakdown = idea.get("score_breakdown") if isinstance(idea.get("score_breakdown"), dict) else {}
        score_cards = []
        base_scores = [
            ("Composite score", idea.get("composite_score")),
            ("Interestingness", idea.get("interestingness")),
            ("Feasibility", idea.get("feasibility")),
            ("Novelty", idea.get("novelty")),
            ("Debate support", idea.get("debate_support")),
        ]
        for label, value in base_scores:
            if value is None or value == "":
                continue
            score_cards.append(
                f"""
                <div class="score-card">
                  <span class="score-card__value">{escape(str(value))}</span>
                  <span class="score-card__label">{escape(label)}</span>
                </div>
                """
            )

        for label, detail in score_breakdown.items():
            if not isinstance(detail, dict):
                continue
            score_cards.append(
                f"""
                <div class="score-card">
                  <span class="score-card__value">{escape(str(detail.get("value", "")))}</span>
                  <span class="score-card__label">{escape(str(label))} ({escape(str(detail.get("weight", "")))})</span>
                </div>
                """
            )

        novelty_reason = ""
        novelty_check = idea.get("novelty_check_result")
        if isinstance(novelty_check, dict):
            novelty_reason = str(novelty_check.get("reasoning") or "")

        return f"""
        <section class="section">
          <div class="section__header">
            <div>
              <h2 class="section__title">Selected Idea</h2>
              <p class="section__subtitle">The idea that fed the downstream debate and draft generation.</p>
            </div>
            <div class="chip-row">
              <span class="chip">{escape(str(idea.get("idea_id", "")))}</span>
            </div>
          </div>

          <div class="panel-card">
            <h3 class="panel-card__title">{escape(str(idea.get("title", "")))}</h3>
            <div class="score-grid">{''.join(score_cards)}</div>
          </div>

          <div style="height: 18px"></div>

          <div class="columns-2">
            <div class="panel-card">
              <span class="label">Hypothesis</span>
              <div class="prose">{self._render_rich_text(str(idea.get("hypothesis", "")))}</div>
            </div>
            <div class="panel-card">
              <span class="label">Expected Contribution</span>
              <div class="prose">{self._render_rich_text(str(idea.get("expected_contribution", "")))}</div>
              {"<p class='muted'><strong>Novelty reasoning:</strong> " + escape(novelty_reason) + "</p>" if novelty_reason else ""}
            </div>
          </div>

          <div style="height: 18px"></div>

          <div class="panel-card">
            <span class="label">Methodology</span>
            <div class="prose">{self._render_rich_text(str(idea.get("methodology", "")))}</div>
          </div>
        </section>
        """

    def _render_debate_section(self, debate: Any) -> str:
        if not isinstance(debate, dict):
            return ""

        agent_cards = []
        for agent in debate.get("agents", []):
            if not isinstance(agent, dict):
                continue
            agent_cards.append(
                f"""
                <div class="agent-card">
                  <h4>{escape(str(agent.get("agent_name", "")))}</h4>
                  <p class="muted">{escape(str(agent.get("agent_role", "")))}</p>
                  <div class="chip-row">
                    <span class="chip">{_safe_int(agent.get("turn_count"))} turns</span>
                    <span class="chip">{_safe_int(agent.get("citation_count"))} citations</span>
                  </div>
                </div>
                """
            )

        round_cards = []
        for group in debate.get("transcript_by_round", []):
            if not isinstance(group, dict):
                continue
            turns_html = []
            for turn in group.get("turns", []):
                if not isinstance(turn, dict):
                    continue
                doi_html = "".join(
                    f"<span class='doi'>{escape(str(doi))}</span>"
                    for doi in (turn.get("cited_dois") or [])
                )
                turns_html.append(
                    f"""
                    <div class="turn">
                      <div class="turn__meta">
                        <span>{escape(str(turn.get("agent_name", "Agent")))}</span>
                        <span>{escape(str(turn.get("agent_role", "")))}</span>
                        <span>{escape(str(turn.get("turn_type", "")))}</span>
                        <span>{self._format_timestamp(turn.get("timestamp", ""))}</span>
                      </div>
                      <div class="turn__content">{escape(str(turn.get("content", "")))}</div>
                      {"<div class='doi-list'>" + doi_html + "</div>" if doi_html else ""}
                    </div>
                    """
                )
            round_cards.append(
                f"""
                <details open class="round-card">
                  <summary>Round {escape(str(group.get("round", "")))}</summary>
                  <div class="details-body">
                    {''.join(turns_html) or "<p class='muted'>No transcript turns found.</p>"}
                  </div>
                </details>
                """
            )

        return f"""
        <section class="section">
          <div class="section__header">
            <div>
              <h2 class="section__title">Debate</h2>
              <p class="section__subtitle">Full transcript and agent roster for the multi-agent debate stage.</p>
            </div>
            <div class="chip-row">
              <span class="chip">{escape(str(debate.get("discussion_format", "")))}</span>
              <span class="chip">{_safe_int(debate.get("agent_count"))} agents</span>
              <span class="chip">{_safe_int(debate.get("current_round") or debate.get("max_rounds"))} rounds</span>
              <span class="chip">{_safe_int(debate.get("transcript_length"))} turns</span>
            </div>
          </div>

          <div class="panel-card" style="margin-bottom: 18px">
            <span class="label">Debate Prompt</span>
            <div class="prose">{self._render_rich_text(str(debate.get("topic", "")))}</div>
          </div>

          <div class="columns-2">
            <div class="panel-card">
              <h3 class="panel-card__title">Agent Roster</h3>
              <div class="agent-list">{''.join(agent_cards) or "<p class='muted'>No agents found.</p>"}</div>
            </div>
            <div class="panel-card">
              <h3 class="panel-card__title">Debate Metrics</h3>
              <div class="score-grid">
                <div class="score-card">
                  <span class="score-card__value">{_safe_int(debate.get("agent_count"))}</span>
                  <span class="score-card__label">Agents</span>
                </div>
                <div class="score-card">
                  <span class="score-card__value">{_safe_int(debate.get("current_round") or debate.get("max_rounds"))}</span>
                  <span class="score-card__label">Rounds</span>
                </div>
                <div class="score-card">
                  <span class="score-card__value">{_safe_int(debate.get("transcript_length"))}</span>
                  <span class="score-card__label">Turns</span>
                </div>
                <div class="score-card">
                  <span class="score-card__value">{_safe_int(debate.get("total_citations"))}</span>
                  <span class="score-card__label">Cited DOIs</span>
                </div>
              </div>
              <div style="height: 14px"></div>
              <p><strong>Started:</strong> {escape(self._format_timestamp(debate.get("started_at", "")))}</p>
              <p><strong>Completed:</strong> {escape(self._format_timestamp(debate.get("completed_at", "")))}</p>
              <p><strong>Simulation ID:</strong> {escape(str(debate.get("simulation_id", "")))}</p>
            </div>
          </div>

          <div style="height: 18px"></div>

          <div class="round-list">{''.join(round_cards) or "<p class='muted'>No transcript available.</p>"}</div>
        </section>
        """

    def _render_draft_section(self, draft: Any) -> str:
        if not isinstance(draft, dict):
            return ""

        section_details = []
        for section in draft.get("sections", []):
            if not isinstance(section, dict):
                continue
            section_details.append(
                f"""
                <details open class="draft-card">
                  <summary>{escape(str(section.get("heading") or section.get("name") or "Section"))}</summary>
                  <div class="details-body prose">
                    {self._render_rich_text(str(section.get("content", "")))}
                  </div>
                </details>
                """
            )

        bibliography_rows = []
        for entry in draft.get("bibliography", []):
            if not isinstance(entry, dict):
                continue
            bibliography_rows.append(
                f"""
                <tr>
                  <td>{escape(str(entry.get("title", "")))}</td>
                  <td>{escape(str(entry.get("year", "")))}</td>
                  <td>{escape(str(entry.get("venue", "")))}</td>
                  <td>{escape(str(entry.get("doi", "")))}</td>
                </tr>
                """
            )

        return f"""
        <section class="section">
          <div class="section__header">
            <div>
              <h2 class="section__title">Draft</h2>
              <p class="section__subtitle">Full manuscript artifact, including abstract, section content, and bibliography.</p>
            </div>
            <div class="chip-row">
              <span class="chip">{_safe_int(draft.get("section_count"))} sections</span>
              <span class="chip">{_safe_int(draft.get("total_word_count"))} words</span>
              <span class="chip">{_safe_int(draft.get("citation_count"))} citations</span>
              <span class="chip">{escape(str(draft.get("format", "")))}</span>
            </div>
          </div>

          <div class="panel-card">
            <h3 class="panel-card__title">{escape(str(draft.get("title", "")))}</h3>
            <span class="label">Abstract</span>
            <div class="prose">{self._render_rich_text(str(draft.get("abstract", "")))}</div>
          </div>

          <div style="height: 18px"></div>

          <div class="section-list">{''.join(section_details) or "<p class='muted'>No draft sections available.</p>"}</div>

          <div style="height: 18px"></div>

          <div class="panel-card">
            <h3 class="panel-card__title">Bibliography</h3>
            <table class="table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Year</th>
                  <th>Venue</th>
                  <th>DOI</th>
                </tr>
              </thead>
              <tbody>
                {''.join(bibliography_rows) or "<tr><td colspan='4' class='muted'>No bibliography entries.</td></tr>"}
              </tbody>
            </table>
          </div>
        </section>
        """

    def _render_experiment_section(self, experiment: Any) -> str:
        if not isinstance(experiment, dict):
            return ""

        gaps = experiment.get("gaps") if isinstance(experiment.get("gaps"), list) else []
        experiments = experiment.get("experiments")
        if not isinstance(experiments, list):
            experiments = experiment.get("proposed_experiments") if isinstance(experiment.get("proposed_experiments"), list) else []

        gap_cards = []
        for gap in gaps:
            if not isinstance(gap, dict):
                continue
            gap_cards.append(
                f"""
                <div class="gap-card">
                  <div class="chip-row" style="margin-bottom: 8px">
                    <span class="severity severity--{escape(str(gap.get("severity", "medium")))}">{escape(str(gap.get("severity", "medium")))}</span>
                    <span class="chip">{escape(str(gap.get("section", "")))}</span>
                    <span class="chip">{escape(str(gap.get("gap_type", "")))}</span>
                  </div>
                  <h4>{escape(str(gap.get("claim", "")))}</h4>
                  <p class="muted">{escape(str(gap.get("description", "")))}</p>
                </div>
                """
            )

        experiment_cards = []
        for item in experiments:
            if not isinstance(item, dict):
                continue
            measurements = item.get("expected_measurements") if isinstance(item.get("expected_measurements"), list) else []
            measurement_rows = "".join(
                f"""
                <tr>
                  <td>{escape(str(m.get("parameter", "")))}</td>
                  <td>{escape(str(m.get("unit", "")))}</td>
                  <td>{escape(str(m.get("range", "")))}</td>
                </tr>
                """
                for m in measurements
                if isinstance(m, dict)
            )
            template = item.get("data_template") if isinstance(item.get("data_template"), dict) else {}
            columns = template.get("columns") if isinstance(template.get("columns"), list) else []
            experiment_cards.append(
                f"""
                <div class="experiment-card">
                  <h4>{escape(str(item.get("name") or item.get("objective") or "Experiment"))}</h4>
                  <p><strong>Objective:</strong> {escape(str(item.get("objective", "")))}</p>
                  <p><strong>Methodology:</strong> {escape(str(item.get("methodology", "")))}</p>
                  {self._render_string_list("Addresses gaps", item.get("addresses_gaps"))}
                  {self._render_string_list("Equipment", item.get("equipment"))}
                  {self._render_string_list("Controls", item.get("controls"))}
                  {self._render_string_list("Calibration", item.get("calibration"))}
                  {self._render_string_list("Procedure", item.get("procedure_steps"))}
                  <p><strong>Estimated duration:</strong> {escape(str(item.get("estimated_duration", "")))}</p>
                  <div style="height: 10px"></div>
                  <table class="table">
                    <thead>
                      <tr>
                        <th>Measurement</th>
                        <th>Unit</th>
                        <th>Range</th>
                      </tr>
                    </thead>
                    <tbody>
                      {measurement_rows or "<tr><td colspan='3' class='muted'>No expected measurements specified.</td></tr>"}
                    </tbody>
                  </table>
                  {self._render_string_list("Data template columns", columns)}
                </div>
                """
            )

        return f"""
        <section class="section">
          <div class="section__header">
            <div>
              <h2 class="section__title">Experiment Design</h2>
              <p class="section__subtitle">Evidence gaps and proposed validation experiments exported from the experiment design agent.</p>
            </div>
            <div class="chip-row">
              <span class="chip">{len(gaps)} gaps</span>
              <span class="chip">{len(experiments)} experiments</span>
            </div>
          </div>

          <div class="columns-2">
            <div class="panel-card">
              <h3 class="panel-card__title">Evidence Gaps</h3>
              <div class="gaps-grid">{''.join(gap_cards) or "<p class='muted'>No evidence gaps available.</p>"}</div>
            </div>
            <div class="panel-card">
              <h3 class="panel-card__title">Proposed Experiments</h3>
              <div class="experiment-grid">{''.join(experiment_cards) or "<p class='muted'>No experiments proposed.</p>"}</div>
            </div>
          </div>
        </section>
        """

    def _render_review_section(self, review: Any) -> str:
        if not isinstance(review, dict):
            return ""

        summary = review.get("summary") if isinstance(review.get("summary"), dict) else {}
        latest = review.get("latest") if isinstance(review.get("latest"), dict) else None
        trajectory = review.get("score_trajectory") if isinstance(review.get("score_trajectory"), list) else []
        revision_plan = (
            review.get("revision_plan")
            if isinstance(review.get("revision_plan"), dict)
            else {}
        )
        rebuttal = review.get("rebuttal") if isinstance(review.get("rebuttal"), dict) else {}

        trajectory_cards = "".join(
            f"""
            <div class="score-card">
              <span class="score-card__value">{escape(str(round_.get("avg_score", 0)))}</span>
              <span class="score-card__label">Round {escape(str(round_.get("round", "")))}</span>
            </div>
            """
            for round_ in trajectory
            if isinstance(round_, dict)
        )

        reviewer_cards = []
        if latest:
            for result in latest.get("results", []):
                if not isinstance(result, dict):
                    continue
                comment_preview = []
                for comment in result.get("comments", [])[:6]:
                    if not isinstance(comment, dict):
                        continue
                    severity = str(comment.get("severity") or "note")
                    section = str(comment.get("section") or "section")
                    text = str(comment.get("text") or "")
                    comment_preview.append(f"[{severity}] {section}: {text}")
                reviewer_cards.append(
                    f"""
                    <div class="paper-card">
                      <div class="chip-row" style="margin-bottom: 8px">
                        <span class="chip">{escape(str(result.get("reviewer_type", "")))}</span>
                        <span class="chip">{escape(str(result.get("overall_score", 0)))}/10</span>
                      </div>
                      <h4>{escape(str(result.get("reviewer_name", "")))}</h4>
                      <p class="muted">{escape(str(result.get("summary", "")))}</p>
                      {self._render_string_list("Strengths", result.get("strengths"))}
                      {self._render_string_list("Weaknesses", result.get("weaknesses"))}
                      {self._render_string_list("Comment highlights", comment_preview)}
                    </div>
                    """
                )

        theme_cards = []
        conflict_cards = []
        if latest:
            for theme in latest.get("themes", []):
                if not isinstance(theme, dict):
                    continue
                theme_cards.append(
                    f"""
                    <div class="paper-card">
                      <div class="chip-row" style="margin-bottom: 8px">
                        <span class="chip">P{_safe_int(theme.get("priority"), 0)}</span>
                        <span class="chip">{escape(str(theme.get("impact", "")))}</span>
                      </div>
                      <h4>{escape(str(theme.get("title", "")))}</h4>
                      <p class="muted">{escape(str(theme.get("description", "")))}</p>
                      <p><strong>Suggested action:</strong> {escape(str(theme.get("suggested_action", "")))}</p>
                    </div>
                    """
                )
            for conflict in latest.get("conflicts", []):
                if not isinstance(conflict, dict):
                    continue
                conflict_cards.append(
                    f"""
                    <div class="paper-card">
                      <div class="chip-row" style="margin-bottom: 8px">
                        <span class="chip">{escape(str(conflict.get("reviewer_a", "")))}</span>
                        <span class="chip">{escape(str(conflict.get("reviewer_b", "")))}</span>
                      </div>
                      <h4>{escape(str(conflict.get("description", "")))}</h4>
                      <p class="muted">{escape(str(conflict.get("resolution_suggestion", "")))}</p>
                    </div>
                    """
                )

        plan_cards = []
        for item in revision_plan.get("plan", []):
            if not isinstance(item, dict):
                continue
            plan_cards.append(
                f"""
                <div class="paper-card">
                  <div class="chip-row" style="margin-bottom: 8px">
                    <span class="chip">P{_safe_int(item.get("priority"), 0)}</span>
                    <span class="chip">{escape(str(item.get("estimated_effort", "")))}</span>
                  </div>
                  <h4>{escape(str(item.get("theme", "")))}</h4>
                  <p>{escape(str(item.get("action", "")))}</p>
                  {self._render_string_list("Sections affected", item.get("sections_affected"))}
                  <p class="muted">{escape(str(item.get("rationale", "")))}</p>
                </div>
                """
            )

        rebuttal_cards = []
        for item in rebuttal.get("responses", []):
            if not isinstance(item, dict):
                continue
            rebuttal_cards.append(
                f"""
                <div class="paper-card">
                  <div class="chip-row" style="margin-bottom: 8px">
                    <span class="chip">{escape(str(item.get("reviewer_type", "")))}</span>
                    <span class="chip">{escape(str(item.get("status", "")))}</span>
                  </div>
                  <p>{escape(str(item.get("response", "")))}</p>
                  <p class="muted"><strong>Action taken:</strong> {escape(str(item.get("action_taken", "")))}</p>
                </div>
                """
            )

        improving = summary.get("improving")
        improving_label = ""
        if improving is True:
            improving_label = "<span class='chip'>improving</span>"
        elif improving is False:
            improving_label = "<span class='chip'>needs follow-up</span>"

        return f"""
        <section class="section">
          <div class="section__header">
            <div>
              <h2 class="section__title">Review Board</h2>
              <p class="section__subtitle">Persisted reviewer rounds, conflict clustering, revision planning, and rebuttal drafting.</p>
            </div>
            <div class="chip-row">
              <span class="chip">{_safe_int(summary.get("total_rounds"))} rounds</span>
              <span class="chip">{escape(str(summary.get("latest_score", 0)))}/10 latest</span>
              {improving_label}
            </div>
          </div>

          <div class="panel-card" style="margin-bottom: 18px">
            <h3 class="panel-card__title">Score Trajectory</h3>
            <div class="score-grid">{trajectory_cards or "<p class='muted'>No review rounds have been completed yet.</p>"}</div>
          </div>

          <div class="columns-2">
            <div class="panel-card">
              <h3 class="panel-card__title">Latest Reviewer Round</h3>
              <div class="paper-list">{''.join(reviewer_cards) or "<p class='muted'>No reviewer results stored.</p>"}</div>
            </div>
            <div class="panel-card">
              <h3 class="panel-card__title">Themes & Conflicts</h3>
              <div class="paper-list">
                {''.join(theme_cards) or "<p class='muted'>No revision themes stored.</p>"}
                {''.join(conflict_cards) or "<p class='muted'>No reviewer conflicts stored.</p>"}
              </div>
            </div>
          </div>

          <div style="height: 18px"></div>

          <div class="columns-2">
            <div class="panel-card">
              <h3 class="panel-card__title">Revision Plan</h3>
              <div class="paper-list">{''.join(plan_cards) or "<p class='muted'>No persisted revision plan found.</p>"}</div>
            </div>
            <div class="panel-card">
              <h3 class="panel-card__title">Response to Reviewers</h3>
              <div class="paper-list">{''.join(rebuttal_cards) or "<p class='muted'>No persisted rebuttal found.</p>"}</div>
            </div>
          </div>
        </section>
        """

    def _render_translation_section(self, translation: Any) -> str:
        if not isinstance(translation, dict):
            return ""

        outputs = translation.get("outputs") if isinstance(translation.get("outputs"), dict) else {}
        modes = translation.get("modes") if isinstance(translation.get("modes"), list) else list(outputs.keys())
        latest = translation.get("latest") if isinstance(translation.get("latest"), dict) else {}

        mode_cards = []
        for mode in modes:
            payload = outputs.get(mode)
            if not isinstance(mode, str) or not isinstance(payload, dict):
                continue
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            chip_bits = []
            if metadata.get("word_count"):
                chip_bits.append(f"<span class='chip'>{_safe_int(metadata.get('word_count'))} words</span>")
            key_terms = metadata.get("key_terms") if isinstance(metadata.get("key_terms"), list) else []
            mode_cards.append(
                f"""
                <details open class="round-card">
                  <summary>{escape(mode.title())} · {escape(str(payload.get("title", mode)))}</summary>
                  <div class="details-body">
                    {"<div class='chip-row' style='margin-bottom: 12px'>" + ''.join(chip_bits) + "</div>" if chip_bits else ""}
                    {self._render_translation_payload(payload)}
                    {self._render_string_list("Key terms", key_terms)}
                  </div>
                </details>
                """
            )

        latest_mode = str(latest.get("mode") or "")

        return f"""
        <section class="section">
          <div class="section__header">
            <div>
              <h2 class="section__title">Translation Outputs</h2>
              <p class="section__subtitle">Saved downstream translations for journal, funding, grant, patent, and commercialization views.</p>
            </div>
            <div class="chip-row">
              <span class="chip">{len(outputs)} saved outputs</span>
              {"<span class='chip'>latest " + escape(latest_mode) + "</span>" if latest_mode else ""}
            </div>
          </div>

          <div class="section-list">
            {''.join(mode_cards) or "<div class='panel-card'><p class='muted'>No translation outputs have been saved for this run.</p></div>"}
          </div>
        </section>
        """

    def _render_translation_payload(self, payload: Dict[str, Any]) -> str:
        sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
        if sections:
            cards = []
            for section in sections:
                if not isinstance(section, dict):
                    continue
                cards.append(
                    f"""
                    <div class="paper-card">
                      <span class="label">{escape(str(section.get("heading", "Section")))}</span>
                      <div class="prose">{self._render_rich_text(str(section.get("content", "")))}</div>
                    </div>
                    """
                )
            return "".join(cards) or "<p class='muted'>No translated sections stored.</p>"

        field_cards = []
        for key, value in payload.items():
            if key in {"title", "mode", "metadata"} or _is_empty(value):
                continue
            label = str(key).replace("_", " ").title()
            if isinstance(value, str):
                field_cards.append(
                    f"""
                    <div class="paper-card">
                      <span class="label">{escape(label)}</span>
                      <div class="prose">{self._render_rich_text(value)}</div>
                    </div>
                    """
                )
            elif isinstance(value, list):
                rendered_items = []
                for item in value:
                    if isinstance(item, dict):
                        parts = [
                            f"{str(k).replace('_', ' ')}: {v}"
                            for k, v in item.items()
                            if not _is_empty(v)
                        ]
                        rendered_items.append(" | ".join(parts))
                    else:
                        rendered_items.append(str(item))
                field_cards.append(
                    f"""
                    <div class="paper-card">
                      {self._render_string_list(label, rendered_items)}
                    </div>
                    """
                )
            elif isinstance(value, dict):
                details = "".join(
                    f"<p><strong>{escape(str(k).replace('_', ' ').title())}:</strong> {escape(str(v))}</p>"
                    for k, v in value.items()
                    if not _is_empty(v)
                )
                field_cards.append(
                    f"""
                    <div class="paper-card">
                      <span class="label">{escape(label)}</span>
                      {details or "<p class='muted'>No structured details available.</p>"}
                    </div>
                    """
                )
            else:
                field_cards.append(
                    f"""
                    <div class="paper-card">
                      <span class="label">{escape(label)}</span>
                      <p>{escape(str(value))}</p>
                    </div>
                    """
                )

        return "".join(field_cards) or "<p class='muted'>No translation payload stored.</p>"

    def _render_appendix_section(
        self,
        additional_stage_results: Dict[str, Any],
        raw_stage_results: Dict[str, Any],
        config: Dict[str, Any],
    ) -> str:
        return f"""
        <section class="section appendix">
          <div class="section__header">
            <div>
              <h2 class="section__title">Appendix</h2>
              <p class="section__subtitle">Raw configuration and machine-readable stage data are preserved here for debugging and audits.</p>
            </div>
          </div>

          <div class="section-list">
            <details>
              <summary>Run Configuration</summary>
              <div class="details-body"><pre>{escape(json.dumps(config, indent=2, ensure_ascii=False))}</pre></div>
            </details>
            <details>
              <summary>Additional Stage Results</summary>
              <div class="details-body"><pre>{escape(json.dumps(additional_stage_results, indent=2, ensure_ascii=False))}</pre></div>
            </details>
            <details>
              <summary>Raw Stage Results</summary>
              <div class="details-body"><pre>{escape(json.dumps(raw_stage_results, indent=2, ensure_ascii=False))}</pre></div>
            </details>
          </div>
        </section>
        """

    def _render_claim_graph(self, graph: Any) -> str:
        if not isinstance(graph, dict):
            return "<p class='muted'>No claim graph available.</p>"

        nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
        links = graph.get("links") if isinstance(graph.get("links"), list) else []
        if not nodes:
            return "<p class='muted'>No claim graph nodes available.</p>"

        claims = [node for node in nodes if isinstance(node, dict) and node.get("type") == "claim"]
        gaps = [node for node in nodes if isinstance(node, dict) and node.get("type") == "gap"]
        evidence = [node for node in nodes if isinstance(node, dict) and node.get("type") == "evidence"]

        positions: Dict[str, tuple[int, int]] = {}

        def place(items: List[Dict[str, Any]], x: int, start_y: int, spacing: int) -> None:
            for idx, item in enumerate(items):
                positions[str(item.get("id"))] = (x, start_y + idx * spacing)

        place(claims, 170, 80, 62)
        place(gaps, 560, 80, 62)
        place(evidence, 940, 80, 48)

        height = max(
            320,
            (80 + max(len(claims) * 62, len(gaps) * 62, len(evidence) * 48)) + 40,
        )
        width = 1080

        link_palette = {
            "supports": "#1f9d55",
            "contradicts": "#d64545",
            "extends": "#2563eb",
            "gap_for": "#d97706",
        }
        node_palette = {
            "claim": "#0f8b8d",
            "gap": "#d64545",
            "evidence": "#1f9d55",
        }

        svg_links = []
        for link in links:
            if not isinstance(link, dict):
                continue
            source = positions.get(str(link.get("source")))
            target = positions.get(str(link.get("target")))
            if not source or not target:
                continue
            color = link_palette.get(str(link.get("type")), "#94a3b8")
            svg_links.append(
                f"<line x1='{source[0]}' y1='{source[1]}' x2='{target[0]}' y2='{target[1]}' stroke='{color}' stroke-width='1.7' opacity='0.58' />"
            )

        def node_label(node: Dict[str, Any]) -> str:
            label = str(node.get("label") or node.get("full_text") or "")
            return textwrap.shorten(label, width=28, placeholder="...")

        svg_nodes = []
        for node in claims + gaps + evidence:
            node_id = str(node.get("id"))
            if node_id not in positions:
                continue
            x, y = positions[node_id]
            node_type = str(node.get("type"))
            fill = node_palette.get(node_type, "#64748b")
            radius = 11 if node_type == "claim" else 9 if node_type == "gap" else 7
            label = escape(node_label(node))
            if node_type == "evidence":
                text_x = x - 16
                anchor = "end"
            else:
                text_x = x + 16
                anchor = "start"
            svg_nodes.append(
                f"""
                <circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}" stroke="#ffffff" stroke-width="2.2" />
                <text x="{text_x}" y="{y + 4}" font-size="11" fill="#334155" text-anchor="{anchor}">
                  {label}
                </text>
                """
            )

        stats = graph.get("stats") if isinstance(graph.get("stats"), dict) else {}
        legend = f"""
          <div class="graph-legend">
            <span><span class="graph-dot" style="background:#0f8b8d"></span>{_safe_int(stats.get("claims"))} claims</span>
            <span><span class="graph-dot" style="background:#1f9d55"></span>{_safe_int(stats.get("evidence"))} evidence</span>
            <span><span class="graph-dot" style="background:#d64545"></span>{_safe_int(stats.get("gaps"))} gaps</span>
            <span>{_safe_int(stats.get("links"))} links</span>
          </div>
        """

        return f"""
        {legend}
        <div class="graph-shell">
          <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Claim graph">
            <rect x="0" y="0" width="{width}" height="{height}" rx="16" fill="#fbfdfd" />
            <text x="120" y="32" font-size="12" fill="#64748b" font-weight="700">Claims</text>
            <text x="520" y="32" font-size="12" fill="#64748b" font-weight="700">Gaps</text>
            <text x="900" y="32" font-size="12" fill="#64748b" font-weight="700">Evidence</text>
            {''.join(svg_links)}
            {''.join(svg_nodes)}
          </svg>
        </div>
        """

    def _render_novelty_cards(self, novelty_map: Dict[str, Any]) -> str:
        heatmap = novelty_map.get("heatmap") if isinstance(novelty_map.get("heatmap"), list) else []
        stats = novelty_map.get("stats") if isinstance(novelty_map.get("stats"), dict) else {}

        cards = []
        for item in heatmap:
            if not isinstance(item, dict):
                continue
            zone = str(item.get("zone", "covered"))
            background = {
                "novel": "rgba(31, 157, 85, 0.10)",
                "partial": "rgba(217, 119, 6, 0.12)",
                "covered": "rgba(100, 116, 139, 0.10)",
            }.get(zone, "rgba(100, 116, 139, 0.10)")
            cards.append(
                f"""
                <div class="novelty-card" style="background:{background}">
                  <div class="chip-row" style="margin-bottom: 8px">
                    <span class="chip">{escape(zone)}</span>
                    <span class="chip">{self._pct(float(item.get("novelty_score") or 0))}</span>
                  </div>
                  <h4>{escape(str(item.get("text", "")))}</h4>
                  <p class="muted">{escape(str(item.get("explanation", "")))}</p>
                  {self._render_string_list("Differentiators", item.get("differentiators"))}
                </div>
                """
            )

        stats_row = (
            f"<div class='chip-row' style='margin-bottom: 12px'>"
            f"<span class='chip'>avg {self._pct(float(stats.get('avg_novelty') or 0))}</span>"
            f"<span class='chip'>{_safe_int(stats.get('novel_count'))} novel</span>"
            f"<span class='chip'>{_safe_int(stats.get('partial_count'))} partial</span>"
            f"<span class='chip'>{_safe_int(stats.get('covered_count'))} covered</span>"
            f"</div>"
        )
        return stats_row + (f"<div class='novelty-grid'>{''.join(cards)}</div>" if cards else "<p class='muted'>No novelty assessments available.</p>")

    def _render_question_tree(self, question_tree: Dict[str, Any]) -> str:
        stats = question_tree.get("stats") if isinstance(question_tree.get("stats"), dict) else {}
        tree = question_tree.get("tree") if isinstance(question_tree.get("tree"), list) else []

        def render_nodes(nodes: List[Dict[str, Any]], child: bool = False) -> str:
            rendered = []
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                coverage = float(node.get("evidence_coverage") or 0)
                fill_class = "coverage__fill"
                if coverage < 0.3:
                    fill_class = "coverage__fill coverage__fill--low"
                elif coverage < 0.7:
                    fill_class = "coverage__fill coverage__fill--medium"
                children = node.get("children") if isinstance(node.get("children"), list) else []
                rendered.append(
                    f"""
                    <div class="paper-card" style="margin-left:{20 if child else 0}px">
                      <p style="margin: 0 0 10px"><strong>{escape(str(node.get("text", "")))}</strong></p>
                      <div class="coverage">
                        <div class="coverage__track">
                          <div class="{fill_class}" style="width:{max(int(coverage * 100), 4)}%"></div>
                        </div>
                        <span class="coverage__value">{self._pct(coverage)}</span>
                      </div>
                      {render_nodes(children, True) if children else ""}
                    </div>
                    """
                )
            return "".join(rendered)

        stats_row = (
            f"<div class='chip-row' style='margin-bottom: 12px'>"
            f"<span class='chip'>{_safe_int(stats.get('total_questions'))} questions</span>"
            f"<span class='chip'>avg {self._pct(float(stats.get('avg_coverage') or 0))}</span>"
            f"<span class='chip'>{_safe_int(stats.get('uncovered_count'))} uncovered</span>"
            f"</div>"
        )
        return stats_row + (render_nodes(tree) or "<p class='muted'>No question tree available.</p>")

    def _render_hypothesis(self, hypothesis: Optional[Dict[str, Any]]) -> str:
        if not hypothesis:
            return "<p class='muted'>No contribution hypothesis has been stored for this run yet.</p>"
        return (
            f"<span class='label'>Problem Statement</span>"
            f"<p>{escape(str(hypothesis.get('problem_statement', '')))}</p>"
            f"<span class='label'>Contribution</span>"
            f"<p>{escape(str(hypothesis.get('contribution', '')))}</p>"
            f"{self._render_string_list('Differentiators', hypothesis.get('differentiators'))}"
            f"<span class='label'>Predicted Impact</span>"
            f"<p>{escape(str(hypothesis.get('predicted_impact', '')))}</p>"
        )

    def _render_argument_skeleton(self, sections: List[Dict[str, Any]]) -> str:
        if not sections:
            return "<p class='muted'>No argument skeleton has been stored yet.</p>"

        items = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            items.append(
                f"""
                <div class="paper-card">
                  <h4>{escape(str(section.get("heading", "")))}</h4>
                  <p class="muted">{escape(str(section.get("purpose", "")))}</p>
                  {self._render_string_list("Key points", section.get("key_points"))}
                  {self._render_string_list("Assigned citations", section.get("assigned_citations"))}
                </div>
                """
            )
        return f"<div style='height: 16px'></div><h3 class='panel-card__title'>Argument Skeleton</h3><div class='paper-list'>{''.join(items)}</div>"

    def _render_string_list(self, label: str, values: Any) -> str:
        if not isinstance(values, list) or not values:
            return ""
        items = "".join(f"<li>{escape(str(value))}</li>" for value in values)
        return f"<div><span class='label'>{escape(label)}</span><ul class='mini-list'>{items}</ul></div>"

    def _render_rich_text(self, text: str) -> str:
        if not text.strip():
            return "<p class='muted'>No content available.</p>"

        parts: List[str] = []
        in_list = False
        for raw_line in text.replace("\r\n", "\n").split("\n"):
            line = raw_line.strip()
            if not line:
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                continue

            if line.startswith("#"):
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                level = min(max(len(line) - len(line.lstrip("#")), 1), 4) + 1
                content = line.lstrip("#").strip()
                parts.append(f"<h{level}>{self._format_inline(content)}</h{level}>")
                continue

            if line.startswith(("- ", "* ")):
                if not in_list:
                    parts.append("<ul class='rich-list'>")
                    in_list = True
                parts.append(f"<li>{self._format_inline(line[2:].strip())}</li>")
                continue

            if in_list:
                parts.append("</ul>")
                in_list = False

            parts.append(f"<p>{self._format_inline(line)}</p>")

        if in_list:
            parts.append("</ul>")
        return "".join(parts)

    def _format_inline(self, text: str) -> str:
        value = escape(text)
        value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
        value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
        return value

    def _metric_card(self, label: str, value: str, small: bool = False) -> str:
        class_name = "metric__value metric__value--small" if small else "metric__value"
        return (
            "<div class='metric'>"
            f"<span class='metric__label'>{escape(label)}</span>"
            f"<span class='{class_name}'>{escape(value)}</span>"
            "</div>"
        )

    def _format_timestamp(self, value: Any) -> str:
        if not value:
            return "—"
        text = str(value)
        try:
            dt = datetime.fromisoformat(text)
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return text

    def _pct(self, value: float) -> str:
        return f"{round(value * 100)}%"

    def _group_nodes_by_type(self, nodes: Iterable[WorkflowNode]) -> Dict[str, List[WorkflowNode]]:
        grouped: Dict[str, List[WorkflowNode]] = {}
        for node in nodes:
            node_type = node.node_type.value if hasattr(node.node_type, "value") else str(node.node_type)
            grouped.setdefault(node_type, []).append(node)
        return grouped

    def _collect_statuses(
        self,
        spec: StageSpec,
        nodes_by_type: Dict[str, List[WorkflowNode]],
    ) -> List[str]:
        statuses: List[str] = []
        for node_type in spec.workflow_node_types:
            for node in nodes_by_type.get(node_type, []):
                raw = node.status.value if hasattr(node.status, "value") else str(node.status)
                statuses.append(raw)
        return statuses

    def _resolve_stage_status(self, statuses: List[str], stage_payload: Dict[str, Any]) -> str:
        if statuses:
            return sorted(statuses, key=_status_priority, reverse=True)[0]
        return "done" if stage_payload else "pending"

    def _node_snapshot(self, node: WorkflowNode) -> Dict[str, Any]:
        return {
            "node_id": node.node_id,
            "label": node.label,
            "node_type": node.node_type.value if hasattr(node.node_type, "value") else node.node_type,
            "status": node.status.value if hasattr(node.status, "value") else node.status,
            "model_used": node.model_used,
            "score": node.score,
            "error": node.error,
            "started_at": node.started_at,
            "completed_at": node.completed_at,
            "outputs": node.outputs if isinstance(node.outputs, dict) else node.outputs,
        }

    def _workflow_status_counts(self, nodes: Iterable[WorkflowNode]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for node in nodes:
            status = node.status.value if hasattr(node.status, "value") else str(node.status)
            counts[status] = counts.get(status, 0) + 1
        return counts

    def _bundle_to_text_lines(self, bundle: Dict[str, Any]) -> List[str]:
        run = bundle.get("run", {})
        summary = bundle.get("workflow_summary", {})
        resources = bundle.get("resources", {})
        lines: List[str] = [
            "Parallax Full Project Artifact",
            f"Generated: {bundle.get('generated_at', '')}",
            "",
            f"Run ID: {run.get('run_id', '')}",
            f"Research Idea: {run.get('research_idea', '')}",
            f"Status: {run.get('status', '')}",
            f"Current Stage: {run.get('current_stage', '')}",
            f"Created: {run.get('created_at', '')}",
            f"Updated: {run.get('updated_at', '')}",
            f"Total Workflow Nodes: {summary.get('total_nodes', 0)}",
            f"Workflow Node Status Counts: {json.dumps(summary.get('status_counts', {}), ensure_ascii=False)}",
        ]

        nodes = summary.get("nodes") if isinstance(summary.get("nodes"), list) else []
        if nodes:
            lines.extend(["", "=== Workflow Nodes ==="])
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                lines.append(
                    f"- {node.get('label', '')} [{node.get('node_type', '')}] "
                    f"status={node.get('status', '')}"
                )
                outputs = node.get("outputs")
                if isinstance(outputs, dict) and outputs:
                    lines.extend(json.dumps(outputs, indent=2, ensure_ascii=False).splitlines())

        knowledge = resources.get("knowledge")
        if isinstance(knowledge, dict):
            artifact = knowledge.get("artifact") if isinstance(knowledge.get("artifact"), dict) else {}
            novelty = knowledge.get("novelty_map") if isinstance(knowledge.get("novelty_map"), dict) else {}
            question_tree = knowledge.get("question_tree") if isinstance(knowledge.get("question_tree"), dict) else {}
            lines.extend(
                [
                    "",
                    "=== Knowledge Mapping ===",
                    f"Claims: {len(artifact.get('claims', []))}",
                    f"Evidence: {len(artifact.get('evidence', []))}",
                    f"Gaps: {len(artifact.get('gaps', []))}",
                ]
            )
            for claim in artifact.get("claims", []):
                if isinstance(claim, dict):
                    lines.append(
                        f"- Claim ({claim.get('category', 'claim')}, {self._pct(float(claim.get('confidence') or 0))}): "
                        f"{claim.get('text', '')}"
                    )
            for gap in artifact.get("gaps", []):
                if isinstance(gap, dict):
                    lines.append(f"- Gap ({gap.get('severity', '')}): {gap.get('description', '')}")
                    if gap.get("suggested_approach"):
                        lines.append(f"  Suggested approach: {gap.get('suggested_approach')}")
            heatmap = novelty.get("heatmap") if isinstance(novelty.get("heatmap"), list) else []
            if heatmap:
                lines.extend(["", "Novelty Map:"])
                for item in heatmap:
                    if isinstance(item, dict):
                        lines.append(
                            f"- {item.get('zone', '')} {self._pct(float(item.get('novelty_score') or 0))}: "
                            f"{item.get('text', '')}"
                        )
                        if item.get("explanation"):
                            lines.append(f"  {item.get('explanation')}")
            roots = question_tree.get("tree") if isinstance(question_tree.get("tree"), list) else []
            if roots:
                lines.extend(["", "Question Tree:"])
                for root in roots:
                    if not isinstance(root, dict):
                        continue
                    lines.append(f"- {self._pct(float(root.get('evidence_coverage') or 0))}: {root.get('text', '')}")
                    for child in root.get("children", []):
                        if isinstance(child, dict):
                            lines.append(
                                f"  - {self._pct(float(child.get('evidence_coverage') or 0))}: "
                                f"{child.get('text', '')}"
                            )

        topic_map = resources.get("topic_map")
        if isinstance(topic_map, dict):
            lines.extend(
                [
                    "",
                    "=== Research Map & Literature ===",
                    f"Papers: {topic_map.get('paper_total', 0)}",
                    f"Topics: {topic_map.get('topic_total', 0)}",
                ]
            )
            for topic in topic_map.get("top_topics", []):
                if isinstance(topic, dict):
                    lines.append(f"- {topic.get('name', '')}: {topic.get('paper_count', 0)} papers")
            top_papers = resources.get("top_papers") if isinstance(resources.get("top_papers"), list) else []
            for paper in top_papers:
                if isinstance(paper, dict):
                    lines.append(f"- Paper: {paper.get('title', '')} (doi={paper.get('doi', '')})")

        selected_idea = resources.get("selected_idea")
        if isinstance(selected_idea, dict):
            lines.extend(
                [
                    "",
                    "=== Selected Idea ===",
                    f"Title: {selected_idea.get('title', '')}",
                    f"Composite Score: {selected_idea.get('composite_score', '')}",
                    "Hypothesis:",
                ]
            )
            lines.extend(str(selected_idea.get("hypothesis", "")).splitlines())
            lines.extend(["", "Methodology:"])
            lines.extend(str(selected_idea.get("methodology", "")).splitlines())
            lines.extend(["", "Expected Contribution:"])
            lines.extend(str(selected_idea.get("expected_contribution", "")).splitlines())

        debate = resources.get("debate")
        if isinstance(debate, dict):
            lines.extend(
                [
                    "",
                    "=== Debate ===",
                    f"Simulation ID: {debate.get('simulation_id', '')}",
                    f"Format: {debate.get('discussion_format', '')}",
                    f"Agents: {debate.get('agent_count', 0)}",
                    f"Rounds: {debate.get('current_round') or debate.get('max_rounds') or 0}",
                    f"Turns: {debate.get('transcript_length', 0)}",
                ]
            )
            for agent in debate.get("agents", []):
                if isinstance(agent, dict):
                    lines.append(
                        f"- Agent: {agent.get('agent_name', '')} / {agent.get('agent_role', '')} "
                        f"({agent.get('turn_count', 0)} turns, {agent.get('citation_count', 0)} citations)"
                    )
            for group in debate.get("transcript_by_round", []):
                if not isinstance(group, dict):
                    continue
                lines.extend(["", f"Round {group.get('round', '')}:"])
                for turn in group.get("turns", []):
                    if isinstance(turn, dict):
                        lines.append(
                            f"{turn.get('agent_name', 'Agent')} [{turn.get('agent_role', '')}] "
                            f"{turn.get('turn_type', '')}"
                        )
                        lines.extend(str(turn.get("content", "")).splitlines())
                        cited = turn.get("cited_dois") if isinstance(turn.get("cited_dois"), list) else []
                        if cited:
                            lines.append("Cited DOIs: " + ", ".join(str(doi) for doi in cited))

        draft = resources.get("draft")
        if isinstance(draft, dict):
            lines.extend(
                [
                    "",
                    "=== Draft ===",
                    f"Draft ID: {draft.get('draft_id', '')}",
                    f"Title: {draft.get('title', '')}",
                    f"Sections: {draft.get('section_count', 0)}",
                    f"Words: {draft.get('total_word_count', 0)}",
                    "",
                    "Abstract:",
                ]
            )
            lines.extend(str(draft.get("abstract", "")).splitlines())
            for section in draft.get("sections", []):
                if isinstance(section, dict):
                    lines.extend(
                        [
                            "",
                            f"Section: {section.get('heading') or section.get('name') or 'Section'}",
                        ]
                    )
                    lines.extend(str(section.get("content", "")).splitlines())
            bibliography = draft.get("bibliography") if isinstance(draft.get("bibliography"), list) else []
            if bibliography:
                lines.extend(["", "Bibliography:"])
                for entry in bibliography:
                    if isinstance(entry, dict):
                        lines.append(
                            f"- {entry.get('title', '')} ({entry.get('year', '')}) "
                            f"{entry.get('doi', '')}"
                        )

        experiment = resources.get("experiment_design")
        if isinstance(experiment, dict):
            gaps = experiment.get("gaps") if isinstance(experiment.get("gaps"), list) else []
            experiments = experiment.get("experiments")
            if not isinstance(experiments, list):
                experiments = (
                    experiment.get("proposed_experiments")
                    if isinstance(experiment.get("proposed_experiments"), list)
                    else []
                )
            lines.extend(
                [
                    "",
                    "=== Experiment Design ===",
                    f"Gaps: {len(gaps)}",
                    f"Experiments: {len(experiments)}",
                ]
            )
            for gap in gaps:
                if isinstance(gap, dict):
                    lines.append(
                        f"- Gap ({gap.get('severity', '')}, {gap.get('section', '')}, {gap.get('gap_type', '')}): "
                        f"{gap.get('claim', '')}"
                    )
                    lines.append(f"  {gap.get('description', '')}")
            for item in experiments:
                if isinstance(item, dict):
                    lines.extend(
                        [
                            "",
                            f"Experiment: {item.get('name') or item.get('objective') or 'Experiment'}",
                            f"Objective: {item.get('objective', '')}",
                            f"Methodology: {item.get('methodology', '')}",
                        ]
                    )
                    for label in ("addresses_gaps", "equipment", "controls", "calibration", "procedure_steps"):
                        values = item.get(label)
                        if isinstance(values, list) and values:
                            lines.append(f"{label}:")
                            for value in values:
                                lines.append(f"- {value}")
                    measurements = item.get("expected_measurements")
                    if isinstance(measurements, list) and measurements:
                        lines.append("expected_measurements:")
                        for measurement in measurements:
                            if isinstance(measurement, dict):
                                lines.append(
                                    f"- {measurement.get('parameter', '')}: "
                                    f"{measurement.get('range', '')} {measurement.get('unit', '')}"
                                )

        review = resources.get("review")
        if isinstance(review, dict):
            summary = review.get("summary") if isinstance(review.get("summary"), dict) else {}
            latest = review.get("latest") if isinstance(review.get("latest"), dict) else {}
            lines.extend(
                [
                    "",
                    "=== Review Board ===",
                    f"Rounds: {summary.get('total_rounds', 0)}",
                    f"Latest Score: {summary.get('latest_score', 0)}",
                ]
            )
            if summary.get("improving") is True:
                lines.append("Trend: improving")
            elif summary.get("improving") is False:
                lines.append("Trend: needs follow-up")

            for round_ in review.get("score_trajectory", []):
                if isinstance(round_, dict):
                    lines.append(
                        f"- Round {round_.get('round', 0)} score {round_.get('avg_score', 0)}"
                    )

            for result in latest.get("results", []):
                if not isinstance(result, dict):
                    continue
                lines.extend(
                    [
                        "",
                        f"Reviewer: {result.get('reviewer_name', '')} ({result.get('reviewer_type', '')})",
                        f"Score: {result.get('overall_score', 0)}",
                        str(result.get("summary", "")),
                    ]
                )
                for strength in result.get("strengths", []):
                    lines.append(f"- Strength: {strength}")
                for weakness in result.get("weaknesses", []):
                    lines.append(f"- Weakness: {weakness}")
                for comment in result.get("comments", []):
                    if isinstance(comment, dict):
                        lines.append(
                            f"- Comment [{comment.get('severity', '')}] {comment.get('section', '')}: "
                            f"{comment.get('text', '')}"
                        )

            themes = latest.get("themes") if isinstance(latest.get("themes"), list) else []
            if themes:
                lines.extend(["", "Revision Themes:"])
                for theme in themes:
                    if isinstance(theme, dict):
                        lines.append(
                            f"- P{theme.get('priority', '')} {theme.get('title', '')}: "
                            f"{theme.get('suggested_action', '')}"
                        )

            conflicts = latest.get("conflicts") if isinstance(latest.get("conflicts"), list) else []
            if conflicts:
                lines.extend(["", "Reviewer Conflicts:"])
                for conflict in conflicts:
                    if isinstance(conflict, dict):
                        lines.append(
                            f"- {conflict.get('reviewer_a', '')} vs {conflict.get('reviewer_b', '')}: "
                            f"{conflict.get('description', '')}"
                        )
                        lines.append(f"  {conflict.get('resolution_suggestion', '')}")

            revision_plan = review.get("revision_plan") if isinstance(review.get("revision_plan"), dict) else {}
            if revision_plan.get("plan"):
                lines.extend(["", "Revision Plan:"])
                for item in revision_plan.get("plan", []):
                    if isinstance(item, dict):
                        lines.append(
                            f"- P{item.get('priority', '')} {item.get('theme', '')}: {item.get('action', '')}"
                        )
                        if item.get("sections_affected"):
                            lines.append(
                                "  Sections: " + ", ".join(str(section) for section in item.get("sections_affected", []))
                            )
                        if item.get("rationale"):
                            lines.append(f"  {item.get('rationale', '')}")

            rebuttal = review.get("rebuttal") if isinstance(review.get("rebuttal"), dict) else {}
            if rebuttal.get("responses"):
                lines.extend(["", "Response to Reviewers:"])
                for item in rebuttal.get("responses", []):
                    if isinstance(item, dict):
                        lines.append(
                            f"- {item.get('reviewer_type', '')} [{item.get('status', '')}] {item.get('comment_id', '')}"
                        )
                        lines.extend(str(item.get("response", "")).splitlines())
                        if item.get("action_taken"):
                            lines.append(f"  Action taken: {item.get('action_taken', '')}")

        translation = resources.get("translation")
        if isinstance(translation, dict):
            outputs = translation.get("outputs") if isinstance(translation.get("outputs"), dict) else {}
            lines.extend(
                [
                    "",
                    "=== Translation ===",
                    f"Saved Outputs: {len(outputs)}",
                ]
            )
            latest = translation.get("latest") if isinstance(translation.get("latest"), dict) else {}
            if latest.get("mode"):
                lines.append(f"Latest Mode: {latest.get('mode', '')}")

            modes = translation.get("modes") if isinstance(translation.get("modes"), list) else list(outputs.keys())
            for mode in modes:
                payload = outputs.get(mode) if isinstance(mode, str) else None
                if not isinstance(payload, dict):
                    continue
                lines.extend(
                    [
                        "",
                        f"{str(mode).title()} Output: {payload.get('title', '')}",
                    ]
                )
                sections = payload.get("sections") if isinstance(payload.get("sections"), list) else []
                if sections:
                    for section in sections:
                        if isinstance(section, dict):
                            lines.extend(
                                [
                                    f"Section: {section.get('heading', 'Section')}",
                                ]
                            )
                            lines.extend(str(section.get("content", "")).splitlines())
                    continue

                for key, value in payload.items():
                    if key in {"title", "mode", "metadata"} or _is_empty(value):
                        continue
                    if isinstance(value, list):
                        lines.append(f"{key}:")
                        for item in value:
                            if isinstance(item, dict):
                                lines.append("- " + json.dumps(item, ensure_ascii=False))
                            else:
                                lines.append(f"- {item}")
                    elif isinstance(value, dict):
                        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
                    else:
                        lines.append(f"{key}: {value}")

        additional = bundle.get("additional_stage_results", {})
        if additional:
            lines.extend(["", "=== Additional Stage Result Entries ==="])
            lines.extend(json.dumps(additional, indent=2, ensure_ascii=False).splitlines())

        lines.extend(["", "=== Raw Stage Results (Complete) ==="])
        lines.extend(json.dumps(bundle.get("raw_stage_results", {}), indent=2, ensure_ascii=False).splitlines())

        wrapped_lines: List[str] = []
        for line in lines:
            if line == "":
                wrapped_lines.append("")
                continue
            wrapped = textwrap.wrap(
                line,
                width=106,
                break_long_words=True,
                break_on_hyphens=False,
                replace_whitespace=False,
            )
            wrapped_lines.extend(wrapped or [""])
        return wrapped_lines

    def _lines_to_pdf(self, lines: List[str]) -> bytes:
        if not lines:
            lines = [""]

        page_width = 595
        page_height = 842
        margin_left = 40
        margin_top = 802
        margin_bottom = 40
        line_height = 13
        lines_per_page = max(1, int((margin_top - margin_bottom) / line_height))

        pages: List[List[str]] = [
            lines[i:i + lines_per_page]
            for i in range(0, len(lines), lines_per_page)
        ]

        object_map: Dict[int, bytes] = {}
        catalog_obj = 1
        pages_obj = 2
        first_page_obj = 3
        font_obj = first_page_obj + len(pages) * 2
        max_obj = font_obj

        kids: List[str] = []
        for idx, page_lines in enumerate(pages):
            page_obj = first_page_obj + idx * 2
            content_obj = page_obj + 1
            kids.append(f"{page_obj} 0 R")

            stream_lines = [
                "BT",
                "/F1 10 Tf",
                "14 TL",
                "0 g",
                f"1 0 0 1 {margin_left} {margin_top} Tm",
            ]
            for i, raw_line in enumerate(page_lines):
                safe = raw_line.encode("latin-1", "replace").decode("latin-1")
                safe = (
                    safe.replace("\\", "\\\\")
                    .replace("(", "\\(")
                    .replace(")", "\\)")
                )
                if i > 0:
                    stream_lines.append("T*")
                stream_lines.append(f"({safe}) Tj")
            stream_lines.append("ET")
            stream_body = "\n".join(stream_lines).encode("latin-1")
            content_body = (
                f"<< /Length {len(stream_body)} >>\nstream\n".encode("latin-1")
                + stream_body
                + b"\nendstream"
            )

            page_body = (
                f"<< /Type /Page /Parent {pages_obj} 0 R "
                f"/MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            ).encode("latin-1")

            object_map[page_obj] = page_body
            object_map[content_obj] = content_body

        object_map[catalog_obj] = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode("latin-1")
        object_map[pages_obj] = (
            f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(kids)}] >>"
        ).encode("latin-1")
        object_map[font_obj] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets: List[int] = [0] * (max_obj + 1)

        for obj_num in range(1, max_obj + 1):
            offsets[obj_num] = len(out)
            out.extend(f"{obj_num} 0 obj\n".encode("latin-1"))
            out.extend(object_map[obj_num])
            out.extend(b"\nendobj\n")

        xref_pos = len(out)
        out.extend(f"xref\n0 {max_obj + 1}\n".encode("latin-1"))
        out.extend(b"0000000000 65535 f \n")
        for obj_num in range(1, max_obj + 1):
            out.extend(f"{offsets[obj_num]:010d} 00000 n \n".encode("latin-1"))

        out.extend(
            (
                f"trailer\n<< /Size {max_obj + 1} /Root {catalog_obj} 0 R >>\n"
                f"startxref\n{xref_pos}\n%%EOF"
            ).encode("latin-1")
        )
        return bytes(out)
