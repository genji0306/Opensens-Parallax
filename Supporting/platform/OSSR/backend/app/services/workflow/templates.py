"""
Project Templates
Pre-configured pipeline settings for common research workflows.
Templates include sources, model selections, and per-step settings.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...db import get_connection

logger = logging.getLogger(__name__)

# ── Built-in Templates ──────────────────────────────────────────────

BUILTIN_TEMPLATES = [
    {
        "template_id": "tpl_electrochemistry",
        "name": "Electrochemistry Research",
        "description": "Optimized for EIS, CV, and battery research papers. Includes specialist review domains for electrochemistry and energy systems.",
        "config": {
            "max_papers": 150,
            "num_ideas": 10,
            "num_reflections": 3,
            "paper_format": "ieee",
        },
        "step_settings": {
            "validate": {"specialist_domains": ["electrochemistry", "eis", "energy_systems", "statistics"]},
            "revise": {"min_score": 6.5, "max_revisions": 3},
        },
        "sources": ["arxiv", "semantic_scholar", "crossref", "pubmed"],
        "category": "materials",
    },
    {
        "template_id": "tpl_ml_paper",
        "name": "ML Research Paper",
        "description": "For machine learning and deep learning research. Experiment design agent enabled with GPU templates.",
        "config": {
            "max_papers": 200,
            "num_ideas": 15,
            "num_reflections": 5,
            "paper_format": "neurips",
        },
        "step_settings": {
            "validate": {"specialist_domains": ["ml_methodology", "statistics", "reproducibility"]},
            "experiment_design": {"auto_detect_gaps": True, "required": True},
            "revise": {"min_score": 7.0, "max_revisions": 3},
        },
        "sources": ["arxiv", "semantic_scholar", "openalex"],
        "category": "cs",
    },
    {
        "template_id": "tpl_biomedical",
        "name": "Biomedical Review",
        "description": "Literature review for biomedical and clinical research. Includes PubMed and Europe PMC sources.",
        "config": {
            "max_papers": 200,
            "num_ideas": 8,
            "num_reflections": 3,
            "paper_format": "apa",
        },
        "step_settings": {
            "validate": {"specialist_domains": ["reproducibility", "statistics"]},
            "revise": {"min_score": 6.0, "max_revisions": 2},
        },
        "sources": ["pubmed", "europe_pmc", "semantic_scholar", "crossref"],
        "category": "biology",
    },
    {
        "template_id": "tpl_survey",
        "name": "Survey / Literature Review",
        "description": "Comprehensive literature survey. Maximizes paper coverage, skips experiment stage.",
        "config": {
            "max_papers": 300,
            "num_ideas": 5,
            "num_reflections": 2,
            "paper_format": "ieee",
        },
        "step_settings": {
            "experiment_design": {"required": False},
            "revise": {"min_score": 5.5, "max_revisions": 2},
        },
        "sources": ["arxiv", "semantic_scholar", "openalex", "crossref", "core"],
        "category": "general",
    },
    {
        "template_id": "tpl_quick_exploration",
        "name": "Quick Exploration",
        "description": "Fast, low-cost exploration of a research topic. Fewer papers, fewer ideas, uses fast models.",
        "config": {
            "max_papers": 50,
            "num_ideas": 5,
            "num_reflections": 1,
            "paper_format": "ieee",
        },
        "step_settings": {
            "search": {"model": "claude-haiku-4-20250414"},
            "ideate": {"model": "claude-haiku-4-20250414"},
            "debate": {"model": "claude-haiku-4-20250414", "max_rounds": 3, "agents": 4},
            "experiment_design": {"required": False},
            "revise": {"min_score": 5.0, "max_revisions": 1},
        },
        "sources": ["arxiv", "semantic_scholar"],
        "category": "general",
    },
]


def ensure_builtins():
    """Insert built-in templates if they don't exist."""
    conn = get_connection()
    for tpl in BUILTIN_TEMPLATES:
        existing = conn.execute(
            "SELECT template_id FROM project_templates WHERE template_id = ?",
            (tpl["template_id"],),
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO project_templates
                (template_id, name, description, config, step_settings, sources, category, created_at, is_builtin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    tpl["template_id"], tpl["name"], tpl["description"],
                    json.dumps(tpl["config"]), json.dumps(tpl["step_settings"]),
                    json.dumps(tpl["sources"]), tpl["category"],
                    datetime.now().isoformat(),
                ),
            )
    conn.commit()


def list_templates() -> List[Dict[str, Any]]:
    """List all available templates (builtins + user-created)."""
    conn = get_connection()
    ensure_builtins()

    rows = conn.execute(
        "SELECT * FROM project_templates ORDER BY is_builtin DESC, name ASC"
    ).fetchall()

    return [
        {
            "template_id": row["template_id"],
            "name": row["name"],
            "description": row["description"],
            "config": json.loads(row["config"]) if row["config"] else {},
            "step_settings": json.loads(row["step_settings"]) if row["step_settings"] else {},
            "sources": json.loads(row["sources"]) if row["sources"] else [],
            "category": row["category"],
            "is_builtin": bool(row["is_builtin"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Get a single template by ID."""
    conn = get_connection()
    ensure_builtins()

    row = conn.execute(
        "SELECT * FROM project_templates WHERE template_id = ?", (template_id,)
    ).fetchone()

    if not row:
        return None

    return {
        "template_id": row["template_id"],
        "name": row["name"],
        "description": row["description"],
        "config": json.loads(row["config"]) if row["config"] else {},
        "step_settings": json.loads(row["step_settings"]) if row["step_settings"] else {},
        "sources": json.loads(row["sources"]) if row["sources"] else [],
        "category": row["category"],
        "is_builtin": bool(row["is_builtin"]),
        "created_at": row["created_at"],
    }


def save_template(
    name: str,
    description: str,
    config: Dict[str, Any],
    step_settings: Dict[str, Any],
    sources: List[str],
    category: str = "custom",
) -> str:
    """Save a user-created template. Returns template_id."""
    conn = get_connection()
    template_id = f"tpl_{uuid.uuid4().hex[:10]}"

    conn.execute(
        """INSERT INTO project_templates
        (template_id, name, description, config, step_settings, sources, category, created_at, is_builtin)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
        (
            template_id, name, description,
            json.dumps(config), json.dumps(step_settings),
            json.dumps(sources), category,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    return template_id


def delete_template(template_id: str) -> bool:
    """Delete a user-created template. Cannot delete builtins."""
    conn = get_connection()
    row = conn.execute(
        "SELECT is_builtin FROM project_templates WHERE template_id = ?",
        (template_id,),
    ).fetchone()
    if not row:
        return False
    if row["is_builtin"]:
        return False

    conn.execute("DELETE FROM project_templates WHERE template_id = ?", (template_id,))
    conn.commit()
    return True
