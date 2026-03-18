"""
Agent AiS — Pipeline Orchestrator
Sequences the 5 stages: Crawl → Ideate → Debate → Human Review → Draft.
Stages 1-2 run in ais_routes.py (_run_pipeline_stages_1_2).
This module handles Stages 3-5 after human idea selection.
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from opensens_common.task import TaskManager, TaskStatus

from ...db import get_connection
from ...models.ais_models import PipelineRun, PipelineStatus, ResearchIdea
from ...models.research import ResearchDataStore
from .idea_generator import IdeaGenerator
from .paper_draft_generator import PaperDraftGenerator
from ..agents.profile_gen import ResearcherProfileGenerator
from ..simulation.runner import ResearchSimulationRunner

logger = logging.getLogger(__name__)


class AisPipeline:
    """Orchestrates Agent AiS Stages 3-5."""

    def __init__(self):
        self.tm = TaskManager()
        self.store = ResearchDataStore()
        self.idea_gen = IdeaGenerator()
        self.draft_gen = PaperDraftGenerator()
        self.profile_gen = ResearcherProfileGenerator()
        self.sim_runner = ResearchSimulationRunner()

    def run_stage_3(self, run_id: str, task_id: str):
        """
        Stage 3: Agent-to-Agent Debate.
        Generates agents, creates an adversarial simulation, runs it.
        """
        try:
            run = self._load_run(run_id)
            if not run:
                raise ValueError(f"Run not found: {run_id}")

            selected_idea_id = run.stage_results.get("selected_idea_id")
            if not selected_idea_id:
                raise ValueError("No idea selected — run select-idea first")

            # Load the selected idea
            idea = self._load_idea(selected_idea_id)
            if not idea:
                raise ValueError(f"Idea not found: {selected_idea_id}")

            self._update_status(run_id, PipelineStatus.DEBATING, stage=3)
            self.tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=10,
                                message="Stage 3: Generating debate agents...")

            # Generate agents for debate
            topic_ids = self._get_topic_ids_for_idea(idea)
            agent_task_id = self.profile_gen.generate_async(
                agents_per_cluster=2,
            )

            # Poll agent generation
            for _ in range(90):
                task = self.tm.get_task(agent_task_id)
                if task and task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    break
                time.sleep(2)

            agent_task = self.tm.get_task(agent_task_id)
            if not agent_task or agent_task.status == TaskStatus.FAILED:
                raise RuntimeError(f"Agent generation failed: {agent_task.error if agent_task else 'timeout'}")

            # Get generated agent IDs
            agent_ids = []
            if agent_task.result:
                agent_ids = agent_task.result.get("agent_ids", [])
            if not agent_ids:
                # Fallback: list all agents
                from ..agents.profile_gen import ResearcherProfileStore
                profile_store = ResearcherProfileStore()
                all_agents = profile_store.list_all()
                agent_ids = [a.agent_id for a in all_agents[:4]]

            if not agent_ids:
                raise RuntimeError("No agents available for debate")

            self.tm.update_task(task_id, progress=30,
                                message=f"Stage 3: Starting debate with {len(agent_ids)} agents...")

            # Create and run adversarial simulation
            topic = f"Evaluate research direction: {idea.title}\n\nHypothesis: {idea.hypothesis}\nMethodology: {idea.methodology}"
            sim = self.sim_runner.create_simulation(
                discussion_format="adversarial",
                topic=topic,
                agent_ids=agent_ids[:6],
                max_rounds=5,
            )

            sim_task_id = self.sim_runner.start_async(sim.simulation_id)

            # Poll simulation
            for _ in range(180):
                task = self.tm.get_task(sim_task_id)
                if task and task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    break
                time.sleep(2)

            sim_task = self.tm.get_task(sim_task_id)
            if not sim_task or sim_task.status == TaskStatus.FAILED:
                raise RuntimeError(f"Simulation failed: {sim_task.error if sim_task else 'timeout'}")

            # Collect debate results
            sim_result = self.sim_runner.get_simulation(sim.simulation_id)
            transcript = []
            if sim_result and hasattr(sim_result, "transcript"):
                transcript = sim_result.transcript or []
            elif sim_result:
                transcript = getattr(sim_result, "turns", [])

            # Save Stage 3 results
            self._update_stage_result(run_id, "stage_3", {
                "simulation_id": sim.simulation_id,
                "agent_count": len(agent_ids),
                "agent_ids": agent_ids[:6],
                "rounds_completed": sim_task.result.get("rounds_completed", 5) if sim_task.result else 5,
            })

            self._update_status(run_id, PipelineStatus.HUMAN_REVIEW, stage=4)
            self.tm.update_task(task_id, progress=60,
                                message="Stage 3 complete. Awaiting human review (approve to proceed to drafting).")

            logger.info("[AiS %s] Stage 3 complete. Sim: %s", run_id, sim.simulation_id)

        except Exception as e:
            logger.error("[AiS %s] Stage 3 failed: %s", run_id, e, exc_info=True)
            self._update_status(run_id, PipelineStatus.FAILED, error=str(e))
            self.tm.fail_task(task_id, str(e))

    def run_stage_5(self, run_id: str, task_id: str):
        """
        Stage 5: Paper Draft Generation + Self-Review.
        Generates a structured paper from the debate-refined hypothesis.
        """
        try:
            run = self._load_run(run_id)
            if not run:
                raise ValueError(f"Run not found: {run_id}")

            self._update_status(run_id, PipelineStatus.DRAFTING, stage=5)
            self.tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=10,
                                message="Stage 5: Generating paper draft...")

            # Load idea
            selected_idea_id = run.stage_results.get("selected_idea_id")
            idea = self._load_idea(selected_idea_id) if selected_idea_id else None
            if not idea:
                raise ValueError("No selected idea found")

            # Collect debate transcript
            transcript = self._collect_transcript(run)

            # Collect landscape from DB
            papers = self.store.list_papers(limit=200)
            topics = self.store.list_topics()
            landscape = {
                "papers": [p.to_dict() for p in papers],
                "topics": [t.to_dict() for t in topics],
            }

            self.tm.update_task(task_id, progress=30,
                                message="Stage 5: Writing paper sections...")

            # Generate draft
            draft = self.draft_gen.generate_draft(
                idea=idea,
                debate_transcript=transcript,
                landscape=landscape,
                paper_format=run.config.get("paper_format", "ieee"),
                run_id=run_id,
            )

            self.tm.update_task(task_id, progress=70,
                                message="Stage 5: Running self-review...")

            # Self-review
            review = self.draft_gen.self_review(draft, num_reviewers=3)

            # Save Stage 5 results
            self._update_stage_result(run_id, "stage_5", {
                "draft_id": draft.draft_id,
                "title": draft.title,
                "section_count": len(draft.sections),
                "total_word_count": sum(s.word_count for s in draft.sections),
                "citation_count": len(draft.bibliography),
                "review_overall": review.get("overall", 0),
                "review_decision": review.get("decision", ""),
            })

            # Stage 5C: Social amplification (optional)
            social_result = None
            if run.config.get("social_amplify", False):
                self.tm.update_task(task_id, progress=80,
                                    message="Stage 5C: Social amplification...")
                social_result = self._social_amplify(draft, run)
                if social_result:
                    self._update_stage_result(run_id, "stage_5c", social_result)

            # Check if revision needed
            if review.get("overall", 0) < 5 and review.get("decision") == "Reject":
                self._update_status(run_id, PipelineStatus.REVIEWING, stage=5)
                self.tm.update_task(task_id, progress=85,
                                    message="Stage 5: Review score low, draft may need revision.")
            else:
                self._update_status(run_id, PipelineStatus.COMPLETED, stage=5)

            self.tm.complete_task(task_id, {
                "run_id": run_id,
                "draft_id": draft.draft_id,
                "review_overall": review.get("overall", 0),
                "review_decision": review.get("decision", ""),
                "word_count": sum(s.word_count for s in draft.sections),
            })

            logger.info(
                "[AiS %s] Stage 5 complete. Draft: %s, Review: %s/10 (%s)",
                run_id, draft.draft_id, review.get("overall", 0), review.get("decision", ""),
            )

        except Exception as e:
            logger.error("[AiS %s] Stage 5 failed: %s", run_id, e, exc_info=True)
            self._update_status(run_id, PipelineStatus.FAILED, error=str(e))
            self.tm.fail_task(task_id, str(e))

    # ── Helpers ──────────────────────────────────────────────────────

    def _load_run(self, run_id: str) -> Optional[PipelineRun]:
        conn = get_connection()
        row = conn.execute("SELECT * FROM ais_pipeline_runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return PipelineRun(
            run_id=row["run_id"],
            research_idea=row["research_idea"],
            status=PipelineStatus(row["status"]),
            current_stage=row["current_stage"],
            stage_results=json.loads(row["stage_results"]) if row["stage_results"] else {},
            config=json.loads(row["config"]) if row["config"] else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error=row["error"],
        )

    def _load_idea(self, idea_id: str) -> Optional[ResearchIdea]:
        conn = get_connection()
        row = conn.execute("SELECT data FROM research_ideas WHERE idea_id = ?", (idea_id,)).fetchone()
        if row:
            return ResearchIdea.from_dict(json.loads(row["data"]))
        return None

    def _collect_transcript(self, run: PipelineRun) -> List[Dict]:
        """Collect debate transcript from Stage 3 simulation."""
        sim_id = run.stage_results.get("stage_3", {}).get("simulation_id")
        if not sim_id:
            return []
        sim = self.sim_runner.get_simulation(sim_id)
        if not sim:
            return []
        # Extract turns from simulation
        turns = getattr(sim, "transcript", None) or getattr(sim, "turns", None) or []
        if isinstance(turns, list):
            return [t if isinstance(t, dict) else t.to_dict() if hasattr(t, "to_dict") else {} for t in turns]
        return []

    def _social_amplify(self, draft, run: "PipelineRun") -> Optional[Dict]:
        """
        Stage 5C: Call social-ai-service to generate and optionally schedule
        platform-specific content from the paper draft.
        """
        social_url = os.environ.get("SOCIAL_AI_URL", "http://localhost:5003")
        platforms = run.config.get("social_platforms", ["twitter", "reddit"])
        results = []

        for platform in platforms:
            try:
                resp = requests.post(
                    f"{social_url}/api/social/generate",
                    json={
                        "platform": platform,
                        "transcript_summary": draft.abstract or (
                            draft.sections[0].content[:500] if draft.sections else ""
                        ),
                        "agent_name": draft.authors[0] if draft.authors else "OSSR Agent",
                        "agent_role": "AI Scientist",
                        "topic": draft.title,
                    },
                    timeout=30,
                )
                if resp.ok:
                    gen_data = resp.json().get("data", {})

                    # Optionally auto-post if configured
                    if run.config.get("social_auto_post", False):
                        post_resp = requests.post(
                            f"{social_url}/api/social/post",
                            json={
                                "platform": platform,
                                "content": gen_data.get("content", ""),
                                "title": gen_data.get("title"),
                                "author": draft.authors[0] if draft.authors else "OSSR",
                            },
                            timeout=30,
                        )
                        if post_resp.ok:
                            gen_data["posted"] = True
                            gen_data["post_result"] = post_resp.json().get("data", {})

                    results.append(gen_data)
                else:
                    logger.warning(
                        "[AiS] Social generate failed for %s: %s", platform, resp.text[:200]
                    )
            except Exception as e:
                logger.warning("[AiS] Social amplify %s failed: %s", platform, e)

        if results:
            return {"platforms": platforms, "posts": results, "count": len(results)}
        return None

    def _get_topic_ids_for_idea(self, idea: ResearchIdea) -> List[str]:
        """Get relevant topic IDs for the idea."""
        topics = self.store.list_topics()
        return [t.topic_id for t in topics[:5]]

    def _update_status(self, run_id: str, status: PipelineStatus, stage: int = None, error: str = None):
        conn = get_connection()
        now = datetime.now().isoformat()
        if stage is not None:
            conn.execute(
                "UPDATE ais_pipeline_runs SET status = ?, current_stage = ?, updated_at = ?, error = ? WHERE run_id = ?",
                (status.value, stage, now, error, run_id),
            )
        else:
            conn.execute(
                "UPDATE ais_pipeline_runs SET status = ?, updated_at = ?, error = ? WHERE run_id = ?",
                (status.value, now, error, run_id),
            )
        conn.commit()

    def _update_stage_result(self, run_id: str, stage_key: str, result: dict):
        conn = get_connection()
        row = conn.execute("SELECT stage_results FROM ais_pipeline_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row:
            existing = json.loads(row["stage_results"]) if row["stage_results"] else {}
            existing[stage_key] = result
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE ais_pipeline_runs SET stage_results = ?, updated_at = ? WHERE run_id = ?",
                (json.dumps(existing), now, run_id),
            )
            conn.commit()
