import json
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytest


@pytest.fixture()
def client(isolated_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def seeded_paper_upload(isolated_db):
    from app.db import get_connection

    conn = get_connection()
    upload_id = "paper_test_001"
    now = datetime.now().isoformat()
    conn.execute(
        """
        INSERT INTO paper_uploads (
            upload_id, title, language, detected_field, sections, raw_references,
            full_text, metadata, source_filename, status, review_config,
            review_rounds, source_audit, reviewers, authors, current_draft,
            score_progression, created_at, updated_at, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            upload_id,
            "Structured Battery Study",
            "en",
            "energy_systems",
            json.dumps([
                {"name": "Abstract", "content": "We evaluate a battery model and compare results across conditions."},
                {"name": "Methods", "content": "Figure 1 shows the workflow and Figure 2 reports discharge curves."},
                {"name": "Results", "content": "Results indicate improved performance under the proposed method."},
            ]),
            json.dumps([]),
            "Abstract. Figure 1 shows the workflow. Figure 2 reports discharge curves. Results indicate improved performance.",
            json.dumps({
                "current_review_session_id": "sess_current",
                "parser_engine": "opendataloader_pdf",
                "parser_mode": "layout_aware",
                "parse_quality": {"overall": 0.91},
                "ocr_used": False,
                "word_count": 3210,
                "tables": [{"table_id": "T1"}, {"table_id": "T2"}],
                "figures": [{"figure_id": "F1"}, {"figure_id": "F2"}, {"figure_id": "F3"}],
                "formulas": [{"formula_id": "Eq1"}],
                "specialist_review": {
                    "reviews": [
                        {
                            "domain": "energy_systems",
                            "findings": [
                                {
                                    "description": "Long-term cycling stability needs stronger visualization.",
                                    "recommendation": "Add a lifecycle figure with uncertainty bands.",
                                }
                            ],
                        }
                    ]
                },
            }),
            "battery.md",
            "review_complete",
            json.dumps({"rounds": 2}),
            json.dumps([
                {
                    "round_num": 1,
                    "review": {
                        "avg_overall_score": 5.2,
                        "final_decision": "major_revision",
                        "all_weaknesses": [
                            {"text": "Results need a stronger figure-driven explanation."},
                            {"text": "Literature grounding is thin in related work."},
                        ],
                    },
                    "revision": {
                        "triage": [
                            {"weakness": "Results need a stronger figure-driven explanation.", "action": "accept"},
                        ],
                        "accepted_count": 1,
                        "rebutted_count": 0,
                        "deferred_count": 0,
                    },
                }
            ]),
            json.dumps({"verified": ["Ref A"], "unverified": ["Ref B"], "method": "heuristic"}),
            json.dumps([{"name": "Reviewer A"}]),
            json.dumps([{"name": "Author A"}]),
            "Abstract. Revised methods and results with better figure cues.",
            json.dumps([5.2, 6.8]),
            now,
            now,
            None,
        ),
    )
    conn.commit()
    return upload_id


class TestPaperLabV2Routes:
    def test_upload_accepts_pdf_and_returns_parser_metadata(self, client, monkeypatch):
        from app.services.ais.paper_parser import ParsedPaper
        from app.models.ais_models import PaperSection
        from app.api import paper_rehab_routes

        class FakeParser:
            def parse(self, _file_path):
                return ParsedPaper(
                    source_path=_file_path,
                    title="PDF Upload",
                    language="en",
                    detected_field="energy systems",
                    sections=[PaperSection(name="abstract", content="Abstract text", word_count=2)],
                    raw_references=[],
                    metadata={
                        "word_count": 2,
                        "parser_engine": "opendataloader_pdf",
                        "parser_mode": "layout_aware",
                        "parse_quality": {"overall": 0.88},
                    },
                    full_text="Abstract text",
                )

        monkeypatch.setattr("app.services.ais.paper_parser.PaperParser", FakeParser)
        monkeypatch.setattr(paper_rehab_routes, "UPLOAD_DIR", Path(client.application.root_path) / "test_uploads")

        resp = client.post(
            "/api/research/paper-lab/upload",
            data={"file": (BytesIO(b"%PDF-1.4 stub"), "paper.pdf")},
            content_type="multipart/form-data",
        )

        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["parser_engine"] == "opendataloader_pdf"
        assert data["parser_mode"] == "layout_aware"
        assert data["parse_quality"]["overall"] == 0.88

    def test_stream_filters_events_by_session(self, client, seeded_paper_upload):
        from app.api.paper_rehab_routes import _sse_events

        _sse_events[seeded_paper_upload] = [
            {"type": "complete", "data": {"message": "old"}, "session_id": "sess_old", "timestamp": "t1"},
            {"type": "review_start", "data": {"round": 1}, "session_id": "sess_current", "timestamp": "t2"},
            {"type": "complete", "data": {"message": "new"}, "session_id": "sess_current", "timestamp": "t3"},
        ]

        resp = client.get(f"/api/research/paper-lab/{seeded_paper_upload}/stream?session_id=sess_current")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert '"session_id": "sess_current"' in body
        assert '"message": "new"' in body
        assert '"message": "old"' not in body

    def test_status_and_list_include_parser_metadata(self, client, seeded_paper_upload):
        status_resp = client.get(f"/api/research/paper-lab/{seeded_paper_upload}/status")
        assert status_resp.status_code == 200
        status_data = status_resp.get_json()["data"]
        assert status_data["parser_engine"] == "opendataloader_pdf"
        assert status_data["parser_mode"] == "layout_aware"
        assert status_data["parse_quality"]["overall"] == 0.91
        assert status_data["document_counts"]["figures"] == 3
        assert status_data["document_counts"]["tables"] == 2
        assert status_data["document_counts"]["formulas"] == 1

        list_resp = client.get("/api/research/paper-lab/uploads")
        assert list_resp.status_code == 200
        uploads = list_resp.get_json()["data"]
        matched = next(item for item in uploads if item["upload_id"] == seeded_paper_upload)
        assert matched["parser_engine"] == "opendataloader_pdf"
        assert matched["parse_quality"]["overall"] == 0.91
        assert matched["document_counts"]["references"] == 0

    def test_visualization_plan_returns_grouped_sections(self, client, seeded_paper_upload):
        resp = client.post(f"/api/research/paper-lab/{seeded_paper_upload}/visualization-plan", json={})
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert set(data.keys()) == {
            "reconstruct",
            "improve",
            "create_missing",
            "graphical_abstract",
            "communication_outputs",
        }
        assert isinstance(data["graphical_abstract"], list)

    def test_artifact_crud_render_audit_export(self, client, seeded_paper_upload):
        create_resp = client.post(
            f"/api/research/paper-lab/{seeded_paper_upload}/artifacts",
            json={
                "type": "chart",
                "intent": "reconstruct",
                "title": "Figure 2",
                "payload": {
                    "assumptions": ["Confirm data values"],
                    "recommended_engine": "vega-lite",
                },
            },
        )
        assert create_resp.status_code == 201
        artifact = create_resp.get_json()["data"]
        artifact_id = artifact["artifact_id"]

        list_resp = client.get(f"/api/research/paper-lab/{seeded_paper_upload}/visualization-artifacts")
        assert list_resp.status_code == 200
        assert any(item["artifact_id"] == artifact_id for item in list_resp.get_json()["data"])

        update_resp = client.put(
            f"/api/research/paper-lab/{seeded_paper_upload}/artifacts/{artifact_id}",
            json={"payload": {"assumptions": []}, "status": "draft"},
        )
        assert update_resp.status_code == 200
        assert update_resp.get_json()["data"]["version"] >= 2

        render_resp = client.post(f"/api/research/paper-lab/{seeded_paper_upload}/artifacts/{artifact_id}/render", json={})
        assert render_resp.status_code == 200

        audit_resp = client.post(f"/api/research/paper-lab/{seeded_paper_upload}/artifacts/{artifact_id}/audit", json={})
        assert audit_resp.status_code == 200
        assert audit_resp.get_json()["data"]["audit"]["consistency_status"] == "pass"

        export_resp = client.post(f"/api/research/paper-lab/{seeded_paper_upload}/artifacts/{artifact_id}/export", json={})
        assert export_resp.status_code == 200
        assert export_resp.get_json()["data"]["ready"] is True
        package = export_resp.get_json()["data"]["package"]
        assert package["bundle_name"] == "figure_2"
        assert any(file["filename"].endswith(".spec.json") for file in package["files"])
        assert any(file["filename"].endswith(".svg") for file in package["files"])

    def test_section_refinement_and_grounded_literature(self, client, seeded_paper_upload):
        refine_resp = client.post(
            f"/api/research/paper-lab/{seeded_paper_upload}/refine-section",
            json={"action": "strengthen_literature_review"},
        )
        assert refine_resp.status_code == 200
        refine_data = refine_resp.get_json()["data"]
        assert "revised_text" in refine_data
        assert "addressed_recommendations" in refine_data
        assert "refinement_id" in refine_data

        apply_resp = client.post(
            f"/api/research/paper-lab/{seeded_paper_upload}/apply-refinement",
            json={"refinement": refine_data},
        )
        assert apply_resp.status_code == 200
        assert refine_data["revised_text"] in apply_resp.get_json()["data"]["current_draft"]

        lit_resp = client.post(
            f"/api/research/paper-lab/{seeded_paper_upload}/literature-review",
            json={"focus": "battery benchmark"},
        )
        assert lit_resp.status_code == 200
        lit_data = lit_resp.get_json()["data"]
        assert lit_data["focus"] == "battery benchmark"
        assert "ready" in lit_data

        from app.api.paper_rehab_routes import _load_upload

        stored = _load_upload(seeded_paper_upload)
        assert stored is not None
        assert refine_data["revised_text"] in stored["current_draft"]
        assert stored["metadata"]["last_grounded_literature_review"]["focus"] == "battery benchmark"
        assert stored["metadata"]["last_applied_refinement_id"] == refine_data["refinement_id"]

        history_resp = client.get(f"/api/research/paper-lab/{seeded_paper_upload}/draft-history")
        assert history_resp.status_code == 200
        history = history_resp.get_json()["data"]
        assert history["last_applied_refinement_id"] == refine_data["refinement_id"]
        assert history["applied_refinements"][-1]["refinement_id"] == refine_data["refinement_id"]
        assert history["grounded_literature_history"][-1]["focus"] == "battery benchmark"
        assert history["grounded_literature_history"][-1]["verified_count"] >= 0

        revert_resp = client.post(
            f"/api/research/paper-lab/{seeded_paper_upload}/revert-refinement",
            json={"refinement_id": refine_data["refinement_id"]},
        )
        assert revert_resp.status_code == 200
        reverted = revert_resp.get_json()["data"]
        assert refine_data["revised_text"] not in reverted["current_draft"]

    def test_blocked_export_and_metadata_persistence(self, client, seeded_paper_upload):
        create_resp = client.post(
            f"/api/research/paper-lab/{seeded_paper_upload}/artifacts",
            json={
                "type": "graphical_abstract",
                "intent": "summarize",
                "title": "Blocked Abstract",
                "payload": {
                    "assumptions": ["Confirm mechanism panel"],
                    "export_formats": ["html", "json"],
                },
            },
        )
        artifact_id = create_resp.get_json()["data"]["artifact_id"]

        audit_resp = client.post(f"/api/research/paper-lab/{seeded_paper_upload}/artifacts/{artifact_id}/audit", json={})
        assert audit_resp.status_code == 200
        assert audit_resp.get_json()["data"]["audit"]["ready"] is False

        export_resp = client.post(f"/api/research/paper-lab/{seeded_paper_upload}/artifacts/{artifact_id}/export", json={})
        assert export_resp.status_code == 200
        export_data = export_resp.get_json()["data"]
        assert export_data["ready"] is False
        assert "Confirm mechanism panel" in export_data["blocked_by"]

    def test_graphical_abstract_and_output_starters_persist_as_artifacts(self, client, seeded_paper_upload):
        ga_resp = client.post(f"/api/research/paper-lab/{seeded_paper_upload}/graphical-abstract", json={"layout_mode": "process_summary"})
        assert ga_resp.status_code == 200
        assert ga_resp.get_json()["data"]["type"] == "graphical_abstract"

        slide_resp = client.post(f"/api/research/paper-lab/{seeded_paper_upload}/slide-starter", json={})
        assert slide_resp.status_code == 200
        assert slide_resp.get_json()["data"]["type"] == "slide"
        slide_export = client.post(
            f"/api/research/paper-lab/{seeded_paper_upload}/artifacts/{slide_resp.get_json()['data']['artifact_id']}/export",
            json={},
        )
        assert any(file["filename"].endswith(".html") for file in slide_export.get_json()["data"]["package"]["files"])

        poster_resp = client.post(f"/api/research/paper-lab/{seeded_paper_upload}/poster-starter", json={})
        assert poster_resp.status_code == 200
        assert poster_resp.get_json()["data"]["type"] == "poster_panel"
