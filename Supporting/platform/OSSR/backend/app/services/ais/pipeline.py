"""
Agent AiS — Pipeline Orchestrator
Sequences the 6 stages: Crawl → Ideate → Debate → Human Review → Draft → Experiment.
Stages 1-2 run in ais_routes.py (_run_pipeline_stages_1_2).
This module handles Stages 3-6 after human idea selection.
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
from ...models.ais_models import PipelineRun, PipelineRunDAO, PipelineStatus, ResearchIdea
from ...models.research import ResearchDataStore
from .experiment_planner import ExperimentPlanner
from .experiment_runner import ExperimentRunner
from .idea_generator import IdeaGenerator
from .paper_draft_generator import PaperDraftGenerator
from ..agents.profile_gen import ResearcherProfileGenerator
from ..simulation.runner import ResearchSimulationRunner
from ..workflow.engine import WorkflowEngine
from ...models.workflow_models import NodeType

logger = logging.getLogger(__name__)


class AisPipeline:
    """Orchestrates Agent AiS Stages 3-6."""

    def __init__(self):
        self.tm = TaskManager()
        self.store = ResearchDataStore()
        self.idea_gen = IdeaGenerator()
        self.draft_gen = PaperDraftGenerator()
        self.exp_planner = ExperimentPlanner()
        self.exp_runner = ExperimentRunner()
        self.profile_gen = ResearcherProfileGenerator()
        self.sim_runner = ResearchSimulationRunner()
        self.wf = WorkflowEngine()

    def run_stage_3(self, run_id: str, task_id: str):
        """
        Stage 3: Agent-to-Agent Debate.
        Generates agents, creates an adversarial simulation, runs it.
        """
        debate_node = None
        try:
            run = PipelineRunDAO.load(run_id)
            if not run:
                raise ValueError(f"Run not found: {run_id}")

            selected_idea_id = run.stage_results.get("selected_idea_id")
            if not selected_idea_id:
                raise ValueError("No idea selected — run select-idea first")

            # Load the selected idea
            idea = self._load_idea(selected_idea_id)
            if not idea:
                raise ValueError(f"Idea not found: {selected_idea_id}")

            PipelineRunDAO.update_status(run_id, PipelineStatus.DEBATING, stage=3)
            self.tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=10,
                                message="Stage 3: Generating debate agents...")

            # V2: Track debate node
            debate_node = self.wf.get_node_by_type(run_id, NodeType.DEBATE)
            if debate_node:
                self.wf.mark_node_running(debate_node.node_id)

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

            debate_agent_ids = agent_ids[:6]

            self.tm.update_task(task_id, progress=30,
                                message=f"Stage 3: Starting debate with {len(debate_agent_ids)} agents...")

            # Create and run adversarial simulation
            topic = f"Evaluate research direction: {idea.title}\n\nHypothesis: {idea.hypothesis}\nMethodology: {idea.methodology}"
            sim = self.sim_runner.create_simulation(
                discussion_format="adversarial",
                topic=topic,
                agent_ids=debate_agent_ids,
                max_rounds=5,
            )

            sim_task_id = self.sim_runner.start_async(sim.simulation_id)

            # Persist the simulation ID immediately so the UI can attach to the live debate
            # while the async simulation is still in progress.
            PipelineRunDAO.update_stage_result(run_id, "stage_3", {
                "simulation_id": sim.simulation_id,
                "agent_count": len(debate_agent_ids),
                "agent_ids": debate_agent_ids,
                "rounds_completed": 0,
                "total_turns": 0,
            })

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
            PipelineRunDAO.update_stage_result(run_id, "stage_3", {
                "simulation_id": sim.simulation_id,
                "agent_count": len(debate_agent_ids),
                "agent_ids": debate_agent_ids,
                "rounds_completed": sim_task.result.get("rounds_completed", 5) if sim_task.result else 5,
                "total_turns": len(transcript),
            })

            PipelineRunDAO.update_status(run_id, PipelineStatus.HUMAN_REVIEW, stage=4)
            self.tm.update_task(task_id, progress=60,
                                message="Stage 3 complete. Awaiting human review (approve to proceed to drafting).")

            # V2: Complete debate node
            if debate_node:
                self.wf.complete_node(debate_node.node_id, {
                    "simulation_id": sim.simulation_id,
                    "agent_count": len(debate_agent_ids),
                    "total_turns": len(transcript),
                })

            logger.info("[AiS %s] Stage 3 complete. Sim: %s", run_id, sim.simulation_id)

        except Exception as e:
            logger.error("[AiS %s] Stage 3 failed: %s", run_id, e, exc_info=True)
            PipelineRunDAO.update_status(run_id, PipelineStatus.FAILED, error=str(e))
            if debate_node:
                self.wf.fail_node(debate_node.node_id, str(e))
            self.tm.fail_task(task_id, str(e))

    def run_stage_5(self, run_id: str, task_id: str):
        """
        Stage 5: Paper Draft Generation + Self-Review.
        Generates a structured paper from the debate-refined hypothesis.
        """
        draft_node = None
        try:
            run = PipelineRunDAO.load(run_id)
            if not run:
                raise ValueError(f"Run not found: {run_id}")

            PipelineRunDAO.update_status(run_id, PipelineStatus.DRAFTING, stage=5)
            self.tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=10,
                                message="Stage 5: Generating paper draft...")

            # V2: Track draft node
            draft_node = self.wf.get_node_by_type(run_id, NodeType.DRAFT)
            if draft_node:
                self.wf.mark_node_running(draft_node.node_id)

            # Load idea (DB first, then inline stage_results fallback, then synthetic)
            selected_idea_id = run.stage_results.get("selected_idea_id")
            idea = self._load_idea(selected_idea_id) if selected_idea_id else None
            if not idea:
                inline_idea = run.stage_results.get("stage_2", {}).get("top_idea")
                if inline_idea and isinstance(inline_idea, dict):
                    idea = ResearchIdea.from_dict(inline_idea)
            if not idea and run.stage_results.get("direct_draft"):
                # Direct draft from existing simulation — synthesize idea from topic
                idea = ResearchIdea(
                    idea_id=f"direct_{run_id[:8]}",
                    title=run.research_idea,
                    hypothesis=f"Investigation of: {run.research_idea}",
                    methodology="Multi-agent debate analysis and synthesis",
                    expected_contribution="Novel insights from parallel-perspective research debate",
                    interestingness=7,
                    feasibility=8,
                    novelty=7,
                    composite_score=7.3,
                    grounding_papers=[],
                )
                # Persist synthetic idea so Stage 6 can find it
                conn = get_connection()
                conn.execute(
                    "INSERT OR REPLACE INTO research_ideas (idea_id, data) VALUES (?, ?)",
                    (idea.idea_id, json.dumps(idea.to_dict())),
                )
                conn.commit()
                # Store selected_idea_id at top level of stage_results
                row = conn.execute("SELECT stage_results FROM ais_pipeline_runs WHERE run_id = ?", (run_id,)).fetchone()
                if row:
                    sr = json.loads(row["stage_results"]) if row["stage_results"] else {}
                    sr["selected_idea_id"] = idea.idea_id
                    conn.execute(
                        "UPDATE ais_pipeline_runs SET stage_results = ? WHERE run_id = ?",
                        (json.dumps(sr), run_id),
                    )
                    conn.commit()
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

            # Progress callback for section-level updates
            def _draft_progress(msg, frac):
                # Map frac (0-1) to progress range 30-70
                self.tm.update_task(task_id, progress=int(30 + frac * 40),
                                    message=f"Stage 5: {msg}")

            # Generate draft (single pass — write+refine merged)
            draft = self.draft_gen.generate_draft(
                idea=idea,
                debate_transcript=transcript,
                landscape=landscape,
                paper_format=run.config.get("paper_format", "ieee"),
                run_id=run_id,
                on_progress=_draft_progress,
            )

            self.tm.update_task(task_id, progress=70,
                                message="Stage 5: Running self-review...")

            # Self-review
            review = self.draft_gen.self_review(draft, num_reviewers=3)

            # Save Stage 5 results
            PipelineRunDAO.update_stage_result(run_id, "stage_5", {
                "draft_id": draft.draft_id,
                "title": draft.title,
                "section_count": len(draft.sections),
                "section_titles": [s.title for s in draft.sections],
                "total_word_count": sum(s.word_count for s in draft.sections),
                "citation_count": len(draft.bibliography),
                "review_overall": review.get("overall", 0),
                "review_decision": review.get("decision", ""),
                "review_strengths": review.get("strengths", []),
                "review_weaknesses": review.get("weaknesses", []),
                "review_suggestions": review.get("suggestions", []),
            })

            # Stage 5C: Social amplification (optional)
            social_result = None
            if run.config.get("social_amplify", False):
                self.tm.update_task(task_id, progress=80,
                                    message="Stage 5C: Social amplification...")
                social_result = self._social_amplify(draft, run)
                if social_result:
                    PipelineRunDAO.update_stage_result(run_id, "stage_5c", social_result)

            # Check if revision needed
            if review.get("overall", 0) < 5 and review.get("decision") == "Reject":
                PipelineRunDAO.update_status(run_id, PipelineStatus.REVIEWING, stage=5)
                self.tm.update_task(task_id, progress=85,
                                    message="Stage 5: Review score low, draft may need revision.")
            else:
                PipelineRunDAO.update_status(run_id, PipelineStatus.COMPLETED, stage=5)

            self.tm.complete_task(task_id, {
                "run_id": run_id,
                "draft_id": draft.draft_id,
                "review_overall": review.get("overall", 0),
                "review_decision": review.get("decision", ""),
                "word_count": sum(s.word_count for s in draft.sections),
            })

            # V2: Complete draft node
            if draft_node:
                self.wf.complete_node(draft_node.node_id, {
                    "draft_id": draft.draft_id,
                    "section_count": len(draft.sections),
                    "word_count": sum(s.word_count for s in draft.sections),
                    "review_overall": review.get("overall", 0),
                }, score=review.get("overall", 0))

            logger.info(
                "[AiS %s] Stage 5 complete. Draft: %s, Review: %s/10 (%s)",
                run_id, draft.draft_id, review.get("overall", 0), review.get("decision", ""),
            )

        except Exception as e:
            logger.error("[AiS %s] Stage 5 failed: %s", run_id, e, exc_info=True)
            PipelineRunDAO.update_status(run_id, PipelineStatus.FAILED, error=str(e))
            if draft_node:
                self.wf.fail_node(draft_node.node_id, str(e))
            self.tm.fail_task(task_id, str(e))

    def run_stage_6(self, run_id: str, task_id: str, config_overrides: Optional[Dict[str, Any]] = None, version: str = "v1"):
        """
        Stage 6: Experiment Execution.
        Plans and runs an experiment via AI-Scientist, then optionally
        generates an enriched v2 paper draft with experimental evidence.
        """
        exp_design_node = None
        try:
            run = PipelineRunDAO.load(run_id)
            if not run:
                raise ValueError(f"Run not found: {run_id}")

            PipelineRunDAO.update_status(run_id, PipelineStatus.EXPERIMENTING, stage=6)
            self.tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=5,
                                message="Stage 6: Planning experiment...")

            # V2: Track experiment design node
            exp_design_node = self.wf.get_node_by_type(run_id, NodeType.EXPERIMENT_DESIGN)
            if exp_design_node:
                self.wf.mark_node_running(exp_design_node.node_id)

            # Load the selected idea (DB first, then inline stage_results fallback)
            selected_idea_id = run.stage_results.get("selected_idea_id")
            idea = self._load_idea(selected_idea_id) if selected_idea_id else None
            if not idea:
                # Fallback: idea may be stored inline in stage_2.top_idea (demo/seeded runs)
                inline_idea = run.stage_results.get("stage_2", {}).get("top_idea")
                if inline_idea and isinstance(inline_idea, dict):
                    idea = ResearchIdea.from_dict(inline_idea)
                    logger.info("[AiS %s] Loaded idea from inline stage_results", run_id)
            if not idea:
                raise ValueError("No selected idea found for experiment")

            # Collect debate transcript and landscape (graceful on DB errors)
            transcript = self._collect_transcript(run)
            landscape = {"papers": [], "topics": []}
            try:
                papers = self.store.list_papers(limit=200)
                landscape["papers"] = [p.to_dict() for p in papers]
            except Exception as e:
                logger.warning("[AiS %s] Could not load papers for landscape: %s", run_id, e)
            try:
                topics = self.store.list_topics()
                landscape["topics"] = [t.to_dict() for t in topics]
            except Exception as e:
                logger.warning("[AiS %s] Could not load topics for landscape: %s", run_id, e)

            # Plan experiment (template selection for V1, template-free for V2)
            self.tm.update_task(task_id, progress=15,
                                message=f"Stage 6: Planning {version.upper()} experiment...")
            spec = self.exp_planner.plan_experiment(
                idea=idea,
                debate_transcript=transcript,
                landscape=landscape,
                run_id=run_id,
                config_overrides=config_overrides,
                version=version,
            )

            # Run experiment — route to V1 or V2 runner
            if version == "v2":
                self.tm.update_task(task_id, progress=25,
                                    message=f"Stage 6: Running V2 BFTS experiment...")
                exp_task_id = self.tm.create_task(f"experiment_v2_{spec.spec_id}")
                from .experiment_runner_v2 import ExperimentRunnerV2
                v2_runner = ExperimentRunnerV2()
                v2_runner.run_experiment(spec, exp_task_id)
            else:
                self.tm.update_task(task_id, progress=25,
                                    message=f"Stage 6: Running experiment (template={spec.template})...")
                exp_task_id = self.tm.create_task(f"experiment_{spec.spec_id}")
                self.exp_runner.run_experiment(spec, exp_task_id)

            # Fetch result
            result = self.exp_runner.get_result(spec.spec_id)
            if not result:
                raise RuntimeError(f"No result found after experiment {spec.spec_id}")

            self.tm.update_task(task_id, progress=70,
                                message="Stage 6: Experiment complete. Generating enriched draft...")

            # Generate enriched v2 draft with experimental evidence (optional — may fail if LLM unavailable)
            enriched_draft = None
            try:
                enriched_draft = self.draft_gen.generate_enriched_draft(
                    idea=idea,
                    debate_transcript=transcript,
                    landscape=landscape,
                    experiment_results=result.to_dict(),
                    paper_format=run.config.get("paper_format", "ieee"),
                    run_id=run_id,
                )
            except Exception as draft_err:
                logger.warning("[AiS %s] Enriched draft generation failed (non-fatal): %s", run_id, draft_err)

            # Save Stage 6 results
            PipelineRunDAO.update_stage_result(run_id, "stage_6", {
                "spec_id": spec.spec_id,
                "result_id": result.result_id,
                "template": spec.template,
                "metrics": result.metrics,
                "artifact_count": len(result.artifacts),
                "paper_path": result.paper_path,
                "status": result.status.value,
            })

            if enriched_draft:
                PipelineRunDAO.update_stage_result(run_id, "stage_6_draft", {
                    "draft_id": enriched_draft.draft_id,
                    "title": enriched_draft.title,
                    "version": enriched_draft.metadata.get("version", "v2_enriched"),
                    "section_count": len(enriched_draft.sections),
                    "total_word_count": sum(s.word_count for s in enriched_draft.sections),
                })

            PipelineRunDAO.update_status(run_id, PipelineStatus.COMPLETED, stage=6)
            self.tm.complete_task(task_id, {
                "run_id": run_id,
                "spec_id": spec.spec_id,
                "result_id": result.result_id,
                "template": spec.template,
                "metrics": result.metrics,
                "enriched_draft_id": enriched_draft.draft_id if enriched_draft else None,
            })

            # V2: Complete experiment design node
            if exp_design_node:
                self.wf.complete_node(exp_design_node.node_id, {
                    "spec_id": spec.spec_id,
                    "result_id": result.result_id,
                    "template": spec.template,
                }, score=7.0 if result.status.value == "completed" else 3.0)

            logger.info(
                "[AiS %s] Stage 6 complete. Spec: %s, Result: %s, Template: %s",
                run_id, spec.spec_id, result.result_id, spec.template,
            )

        except Exception as e:
            logger.error("[AiS %s] Stage 6 failed: %s", run_id, e, exc_info=True)
            PipelineRunDAO.update_status(run_id, PipelineStatus.FAILED, error=str(e))
            exp_design_node = self.wf.get_node_by_type(run_id, NodeType.EXPERIMENT_DESIGN)
            if exp_design_node:
                self.wf.fail_node(exp_design_node.node_id, str(e))
            self.tm.fail_task(task_id, str(e))

    # ── Helpers ──────────────────────────────────────────────────────

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
