"""
Tests for new features: draft version history, LaTeX export, project templates.
"""

import json
import pytest


@pytest.fixture()
def client(isolated_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def seeded_run(isolated_db):
    from app.models.ais_models import PipelineRun, PipelineRunDAO
    from app.services.workflow.engine import WorkflowEngine
    run = PipelineRun(run_id="", research_idea="Feature test idea")
    PipelineRunDAO.save(run)
    engine = WorkflowEngine()
    engine.create_pipeline_graph(run.run_id)
    return run.run_id


class TestDraftVersionHistory:
    def test_save_and_list_versions(self, isolated_db):
        from app.services.ais.draft_history import save_version, list_versions

        vid1 = save_version(
            draft_id="d1", run_id="r1", title="Test Paper",
            sections=[{"name": "intro", "content": "Hello world"}],
            bibliography=[], review_score=5.0, change_summary="Initial draft",
        )
        vid2 = save_version(
            draft_id="d1", run_id="r1", title="Test Paper v2",
            sections=[{"name": "intro", "content": "Hello world extended"}],
            bibliography=[], review_score=6.5, change_summary="Added more content",
        )

        versions = list_versions("d1")
        assert len(versions) == 2
        assert versions[0]["version_num"] == 1
        assert versions[1]["version_num"] == 2

    def test_get_version_full(self, isolated_db):
        from app.services.ais.draft_history import save_version, get_version

        vid = save_version(
            draft_id="d2", run_id="r2", title="Full Version Test",
            sections=[{"name": "abstract", "content": "Abstract text"}],
            bibliography=[{"doi": "10.1234", "title": "Ref 1"}],
            abstract="Abstract here",
        )
        v = get_version(vid)
        assert v is not None
        assert len(v["sections"]) == 1
        assert v["abstract"] == "Abstract here"

    def test_diff_versions(self, isolated_db):
        from app.services.ais.draft_history import save_version, diff_versions

        vid1 = save_version(
            draft_id="d3", run_id="r3", title="Diff Test",
            sections=[{"name": "intro", "content": "Short intro"}],
            bibliography=[], review_score=4.0,
        )
        vid2 = save_version(
            draft_id="d3", run_id="r3", title="Diff Test",
            sections=[
                {"name": "intro", "content": "Extended intro with more words"},
                {"name": "methods", "content": "New section"},
            ],
            bibliography=[], review_score=6.0,
        )

        diff = diff_versions(vid1, vid2)
        assert diff["added_sections"] == ["methods"]
        assert diff["word_count_delta"] > 0
        assert diff["score_delta"] == 2.0

    def test_api_list_versions(self, client, seeded_run):
        resp = client.get(f"/api/research/ais/{seeded_run}/draft/versions")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert "versions" in body["data"]


class TestLatexExport:
    def test_latex_export_no_draft(self, client, seeded_run):
        resp = client.get(f"/api/research/ais/{seeded_run}/export/latex")
        assert resp.status_code == 404

    def test_bibtex_export_no_draft(self, client, seeded_run):
        resp = client.get(f"/api/research/ais/{seeded_run}/export/bibtex")
        assert resp.status_code == 404

    def test_latex_helper_escape(self, isolated_db):
        from app.services.ais.paper_draft_generator import _latex_escape
        assert r"\&" in _latex_escape("A & B")
        assert r"\%" in _latex_escape("100%")

    def test_md_to_latex_bold(self, isolated_db):
        from app.services.ais.paper_draft_generator import _md_to_latex
        result = _md_to_latex("This is **bold** text")
        assert r"\textbf{bold}" in result

    def test_md_to_latex_list(self, isolated_db):
        from app.services.ais.paper_draft_generator import _md_to_latex
        result = _md_to_latex("- item one\n- item two\nDone")
        assert r"\begin{itemize}" in result
        assert r"\item item one" in result
        assert r"\end{itemize}" in result


class TestProjectTemplates:
    def test_list_templates_returns_builtins(self, client, isolated_db):
        resp = client.get("/api/research/ais/templates")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        templates = body["data"]["templates"]
        assert len(templates) >= 5  # 5 builtins
        assert any(t["template_id"] == "tpl_ml_paper" for t in templates)

    def test_get_single_template(self, client, isolated_db):
        resp = client.get("/api/research/ais/templates/tpl_electrochemistry")
        assert resp.status_code == 200
        body = resp.get_json()
        tpl = body["data"]
        assert tpl["name"] == "Electrochemistry Research"
        assert "specialist_domains" in tpl["step_settings"].get("validate", {})

    def test_create_user_template(self, client, isolated_db):
        resp = client.post(
            "/api/research/ais/templates",
            data=json.dumps({
                "name": "My Custom Template",
                "description": "Custom settings",
                "config": {"max_papers": 42},
                "sources": ["arxiv"],
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["data"]["name"] == "My Custom Template"
        tpl_id = body["data"]["template_id"]

        # Verify it shows in list
        resp2 = client.get("/api/research/ais/templates")
        templates = resp2.get_json()["data"]["templates"]
        assert any(t["template_id"] == tpl_id for t in templates)

    def test_delete_user_template(self, client, isolated_db):
        # Create first
        resp = client.post(
            "/api/research/ais/templates",
            data=json.dumps({"name": "Delete Me"}),
            content_type="application/json",
        )
        tpl_id = resp.get_json()["data"]["template_id"]

        # Delete
        resp2 = client.delete(f"/api/research/ais/templates/{tpl_id}")
        assert resp2.status_code == 200

    def test_cannot_delete_builtin(self, client, isolated_db):
        # Ensure builtins exist
        client.get("/api/research/ais/templates")
        resp = client.delete("/api/research/ais/templates/tpl_ml_paper")
        assert resp.status_code == 404

    def test_create_requires_name(self, client, isolated_db):
        resp = client.post(
            "/api/research/ais/templates",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestPersistedStageArtifacts:
    def test_translation_route_persists_outputs(self, client, seeded_run, monkeypatch):
        from app.models.ais_models import PipelineRunDAO
        from app.services.translation.template_engine import TemplateEngine

        def fake_translate(self, run_id: str, mode: str = "journal", model: str = ""):
            return {
                "title": "Grant View",
                "mode": mode,
                "sections": [
                    {"heading": "Executive Summary", "content": "Persist me."},
                ],
                "metadata": {"word_count": 12, "key_terms": ["separator"]},
            }

        monkeypatch.setattr(TemplateEngine, "translate", fake_translate)

        resp = client.post(
            f"/api/research/ais/{seeded_run}/translate",
            data=json.dumps({"mode": "grant"}),
            content_type="application/json",
        )
        assert resp.status_code == 200

        run = PipelineRunDAO.load(seeded_run)
        assert run is not None
        assert run.stage_results["translation_outputs"]["grant"]["title"] == "Grant View"
        assert run.stage_results["translation_latest"]["mode"] == "grant"
        assert run.stage_results["grant_translation"]["title"] == "Grant View"

    def test_review_plan_and_rebuttal_persist_outputs(self, client, seeded_run, monkeypatch):
        from app.models.ais_models import PipelineRunDAO
        from app.services.review.revision_planner import RevisionPlanner

        monkeypatch.setattr(
            RevisionPlanner,
            "create_plan",
            lambda self, run_id, model="": {
                "plan": [
                    {
                        "priority": 1,
                        "theme": "Strengthen evidence",
                        "action": "Add direct morphology evidence",
                        "sections_affected": ["Results"],
                        "estimated_effort": "major",
                        "rationale": "This is the main reviewer concern.",
                    },
                ],
                "stats": {"total_actions": 1, "major_actions": 1},
            },
        )
        monkeypatch.setattr(
            RevisionPlanner,
            "generate_rebuttal",
            lambda self, run_id, model="": {
                "responses": [
                    {
                        "comment_id": "rc_1",
                        "reviewer_type": "novelty",
                        "response": "We added new microscopy evidence.",
                        "action_taken": "Expanded the results section.",
                        "status": "addressed",
                    },
                ],
                "stats": {"total": 1, "addressed": 1, "disagreed": 0},
            },
        )

        plan_resp = client.post(f"/api/research/ais/{seeded_run}/review/revision-plan")
        rebuttal_resp = client.post(f"/api/research/ais/{seeded_run}/review/rebuttal")

        assert plan_resp.status_code == 200
        assert rebuttal_resp.status_code == 200

        run = PipelineRunDAO.load(seeded_run)
        assert run is not None
        assert run.stage_results["review_revision_plan"]["plan"][0]["theme"] == "Strengthen evidence"
        assert run.stage_results["review_rebuttal"]["responses"][0]["status"] == "addressed"


class TestFullProjectArtifactExport:
    def test_html_export_includes_visual_sections(self, client, seeded_run):
        from app import db
        from app.models.ais_models import PipelineRunDAO
        from app.models.knowledge_models import (
            Claim,
            Evidence,
            Gap,
            KnowledgeArtifact,
            KnowledgeArtifactDAO,
            NoveltyAssessment,
            SubQuestion,
        )
        from app.models.review_models import (
            ReviewComment,
            ReviewConflict,
            ReviewerResult,
            RevisionHistoryDAO,
            RevisionRound,
            RevisionTheme,
        )

        run = PipelineRunDAO.load(seeded_run)
        assert run is not None
        run.stage_results["stage_1"] = {"papers_ingested": 12, "topics_found": 4}
        run.stage_results["stage_2"] = {
            "ideas_generated": 3,
            "top_idea": {
                "idea_id": "idea_test_1",
                "title": "Charge-balanced separator for zinc cells",
                "hypothesis": "Neutral separator chemistry improves ion selectivity.",
                "methodology": "1) Build separator 2) Test cells",
                "expected_contribution": "Higher cycle life with better selectivity",
                "interestingness": 7,
                "feasibility": 8,
                "novelty": 9,
                "composite_score": 8.1,
            },
        }
        run.stage_results["selected_idea_id"] = "idea_test_1"
        run.stage_results["stage_3"] = {
            "simulation_id": "sim_test_1",
            "agent_count": 2,
            "rounds_completed": 2,
            "total_turns": 4,
        }
        run.stage_results["stage_5"] = {
            "draft_id": "draft_test_1",
            "title": "Artifact export draft",
            "section_count": 2,
            "total_word_count": 420,
            "citation_count": 1,
        }
        run.stage_results["experiment_design"] = {
            "gaps": [
                {
                    "claim": "Separator suppresses dendrites",
                    "section": "results",
                    "gap_type": "no_data",
                    "severity": "critical",
                    "description": "Need direct microscopy evidence.",
                },
            ],
            "experiments": [
                {
                    "name": "Microscopy validation",
                    "objective": "Validate dendrite suppression.",
                    "methodology": "Cycle symmetric cells and inspect surfaces.",
                    "controls": ["Baseline separator"],
                    "expected_measurements": [
                        {"parameter": "dendrite_length", "unit": "um", "range": "0-100"},
                    ],
                    "procedure_steps": ["Cycle cell", "Capture SEM images"],
                },
            ],
        }
        run.stage_results["review_revision_plan"] = {
            "plan": [
                {
                    "priority": 1,
                    "theme": "Evidence strengthening",
                    "action": "Add microscopy validation and control comparisons.",
                    "sections_affected": ["Results", "Discussion"],
                    "estimated_effort": "major",
                    "rationale": "Directly addresses the core reviewer criticism.",
                },
            ],
        }
        run.stage_results["review_rebuttal"] = {
            "responses": [
                {
                    "comment_id": "rc_test_1",
                    "reviewer_type": "novelty",
                    "response": "We expanded the manuscript with microscopy evidence and a stronger prior-art comparison.",
                    "action_taken": "Updated results and discussion.",
                    "status": "addressed",
                },
            ],
        }
        translation_output = {
            "title": "Grant Translation",
            "mode": "grant",
            "sections": [
                {"heading": "Executive Summary", "content": "This export should include the translated grant view."},
                {"heading": "Expected Outcomes", "content": "- Longer cycle life\n- Better cation selectivity"},
            ],
            "metadata": {"word_count": 120, "key_terms": ["separator", "zinc battery"]},
        }
        run.stage_results["translation_outputs"] = {"grant": translation_output}
        run.stage_results["translation_latest"] = {"mode": "grant", "result": translation_output}
        run.stage_results["grant_translation"] = translation_output
        PipelineRunDAO.save(run)

        conn = db.get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO simulations (simulation_id, data) VALUES (?, ?)",
            (
                "sim_test_1",
                json.dumps(
                    {
                        "simulation_id": "sim_test_1",
                        "discussion_format": "adversarial",
                        "status": "completed",
                        "topic": "Debate whether charge-balanced separators improve Zn transport.",
                        "agent_ids": ["a1", "a2"],
                        "max_rounds": 2,
                        "current_round": 2,
                        "transcript_length": 4,
                        "started_at": "2026-04-01T10:00:00",
                        "completed_at": "2026-04-01T10:05:00",
                        "transcript": [
                            {
                                "round_num": 1,
                                "agent_id": "a1",
                                "agent_name": "Agent One",
                                "agent_role": "Electrochemist",
                                "turn_type": "claim",
                                "content": "Charge-balanced membranes should improve Zn transport.",
                                "cited_dois": ["10.1000/test1"],
                            },
                            {
                                "round_num": 1,
                                "agent_id": "a2",
                                "agent_name": "Agent Two",
                                "agent_role": "Reviewer",
                                "turn_type": "counterargument",
                                "content": "Only if morphology data confirms dendrite suppression.",
                                "cited_dois": ["10.1000/test2"],
                            },
                        ],
                    }
                ),
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO paper_drafts (draft_id, run_id, data, created_at) VALUES (?, ?, ?, ?)",
            (
                "draft_test_1",
                seeded_run,
                json.dumps(
                    {
                        "draft_id": "draft_test_1",
                        "title": "Artifact export draft",
                        "abstract": "## Abstract\n\nThis is a full artifact export test.",
                        "sections": [
                            {
                                "name": "intro",
                                "heading": "Introduction",
                                "content": "# Introduction\n\nThe export should render this as prose.",
                            },
                            {
                                "name": "results",
                                "heading": "Results",
                                "content": "# Results\n\nThe separator showed improved cycling.",
                            },
                        ],
                        "bibliography": [
                            {
                                "title": "Reference paper",
                                "year": 2026,
                                "venue": "crossref",
                                "doi": "10.1000/ref",
                            },
                        ],
                        "format": "ieee",
                        "metadata": {
                            "total_word_count": 420,
                            "section_count": 2,
                            "citation_count": 1,
                        },
                    }
                ),
                "2026-04-01T10:10:00",
            ),
        )
        conn.commit()

        artifact = KnowledgeArtifact(
            run_id=seeded_run,
            research_idea="Feature test idea",
            claims=[Claim(text="Claim A", category="finding", confidence=0.8)],
            evidence=[Evidence(source_type="paper", title="Paper 1", excerpt="Supports Claim A", confidence=0.7)],
            gaps=[Gap(description="Gap 1", severity="critical", suggested_approach="Run microscopy")],
        )
        artifact.claims[0].supporting.append(artifact.evidence[0].evidence_id)
        artifact.novelty_assessments = [
            NoveltyAssessment(
                claim_id=artifact.claims[0].claim_id,
                novelty_score=0.82,
                explanation="Looks novel in this test context.",
                differentiators=["Charge balance"],
            )
        ]
        artifact.sub_questions = [
            SubQuestion(text="Does charge balance improve Zn transport?", evidence_coverage=0.75),
            SubQuestion(text="Do microscopy results confirm suppression?", evidence_coverage=0.25),
        ]
        KnowledgeArtifactDAO.save(artifact)

        review_round = RevisionRound(
            run_id=seeded_run,
            round_number=1,
            rewrite_mode="clarity",
            reviewer_types=["novelty"],
            avg_score=7.3,
        )
        review_round.results = [
            ReviewerResult(
                reviewer_type="novelty",
                reviewer_name="Novelty Reviewer",
                overall_score=7.3,
                summary="Promising contribution, but stronger evidence is needed.",
                comments=[
                    ReviewComment(
                        reviewer_type="novelty",
                        section="Results",
                        text="The microscopy evidence should be made explicit.",
                        severity="major",
                    ),
                ],
                strengths=["Clear separator rationale"],
                weaknesses=["Evidence gap around morphology validation"],
            )
        ]
        review_round.themes = [
            RevisionTheme(
                title="Evidence strengthening",
                description="Add direct validation for dendrite suppression.",
                priority=1,
                impact="high",
                suggested_action="Insert microscopy and control comparisons.",
            )
        ]
        review_round.conflicts = [
            ReviewConflict(
                reviewer_a="novelty",
                reviewer_b="methodological",
                description="One reviewer wants stronger novelty framing while another wants more conservative claims.",
                resolution_suggestion="Add evidence first, then tighten the novelty framing.",
            )
        ]
        RevisionHistoryDAO.save(review_round)

        resp = client.get(f"/api/research/ais/{seeded_run}/artifact?format=html")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        assert "full_artifact.html" in (resp.headers.get("Content-Disposition") or "")

        body = resp.get_data(as_text=True)
        assert "Full Project Artifact" in body
        assert "Pipeline Overview" in body
        assert "Knowledge Mapping" in body
        assert "Claim-Evidence Graph" in body
        assert "Debate" in body
        assert "Experiment Design" in body
        assert "Review Board" in body
        assert "Translation Outputs" in body
        assert "Artifact export draft" in body

    def test_pdf_export_returns_pdf_file(self, client, seeded_run):
        from app.models.ais_models import PipelineRunDAO
        from app.models.review_models import ReviewerResult, RevisionHistoryDAO, RevisionRound

        run = PipelineRunDAO.load(seeded_run)
        assert run is not None
        run.stage_results["stage_3"] = {"rounds_completed": 5, "agent_count": 6}
        run.stage_results["experiment_design"] = {
            "gaps": [{"claim": "Claim A", "section": "results", "gap_type": "no_data", "severity": "major", "description": "Need data"}],
            "experiments": [{"name": "Experiment A", "objective": "Validate claim", "methodology": "Run test"}],
        }
        run.stage_results["translation_outputs"] = {
            "grant": {
                "title": "Grant Translation",
                "mode": "grant",
                "sections": [{"heading": "Executive Summary", "content": "Persist into the PDF export."}],
                "metadata": {"word_count": 18},
            },
        }
        run.stage_results["translation_latest"] = {
            "mode": "grant",
            "result": run.stage_results["translation_outputs"]["grant"],
        }
        PipelineRunDAO.save(run)

        review_round = RevisionRound(
            run_id=seeded_run,
            round_number=1,
            rewrite_mode="conservative",
            reviewer_types=["novelty"],
            avg_score=6.8,
        )
        review_round.results = [
            ReviewerResult(
                reviewer_type="novelty",
                reviewer_name="Novelty Reviewer",
                overall_score=6.8,
                summary="Needs stronger validation support.",
            )
        ]
        RevisionHistoryDAO.save(review_round)

        resp = client.get(f"/api/research/ais/{seeded_run}/artifact?format=pdf")
        assert resp.status_code == 200
        assert resp.mimetype == "application/pdf"
        assert "full_artifact.pdf" in (resp.headers.get("Content-Disposition") or "")
        assert resp.data.startswith(b"%PDF-")
        assert b"Parallax Full Project Artifact" in resp.data
        assert b"Experiment Design" in resp.data
        assert b"Review Board" in resp.data
        assert b"Translation" in resp.data
        assert resp.data.endswith(b"%%EOF")

    def test_json_export_and_missing_run(self, client, seeded_run):
        resp = client.get(f"/api/research/ais/{seeded_run}/artifact?format=json")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["run"]["run_id"] == seeded_run
        assert "stages" in body["data"]

        missing = client.get("/api/research/ais/nonexistent_run/artifact?format=html")
        assert missing.status_code == 404
