#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import importlib
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
ALLOWED_EVENT_TYPES = {
    "progress",
    "complete",
    "error",
    "heartbeat",
    "phase_transition",
    "fork_started",
    "fork_joined",
    "memory_compacted",
    "audit",
}


def add_gap(gaps: list[tuple[str, str]], name: str, detail: str) -> None:
    gaps.append((name, detail))


async def collect_events(conductor, run_id: str, *, timeout_s: float = 5.0, limit: int = 32):
    events = []
    iterator = conductor.stream_events(run_id).__aiter__()
    while len(events) < limit:
        try:
            event = await asyncio.wait_for(iterator.__anext__(), timeout=timeout_s)
        except StopAsyncIteration:
            break
        except TimeoutError:
            break
        events.append(event)
        if event.get("type") in {"complete", "error"}:
            break
    return events


def main() -> int:
    gaps: list[tuple[str, str]] = []
    app = None

    try:
        api_main = importlib.import_module("parallax_v3.api.main")
        app = getattr(api_main, "app")
        if not isinstance(app, FastAPI):
            add_gap(gaps, "api.main", f"app is not FastAPI: {type(app).__name__}")
            app = None
    except Exception as exc:  # pragma: no cover - verifier should degrade to a counted gap
        add_gap(gaps, "api.main", repr(exc))
        try:
            routes = importlib.import_module("parallax_v3.api.routes")
            router = getattr(routes, "router")
            app = FastAPI()
            app.include_router(router)
        except Exception as fallback_exc:  # pragma: no cover
            add_gap(gaps, "api.routes fallback", repr(fallback_exc))

    if app is not None:
        try:
            client = TestClient(app)
            session_response = client.post(
                "/api/v3/sessions",
                json={
                    "research_question": "Hydrolysis of TBT binder system for zinc flake coatings",
                    "target_venue": "coatings_science",
                    "citation_style": "nature",
                    "budget_usd": 5.0,
                    "max_refinement_iters": 2,
                },
            )
            session_payload = session_response.json()
            if not session_payload.get("success"):
                add_gap(gaps, "POST /sessions", str(session_payload))
            else:
                session_id = session_payload["data"]["session_id"]
                temp_dir = Path(tempfile.mkdtemp(prefix="parallax-v3-api-oath-"))
                idea_path = temp_dir / "idea.md"
                log_path = temp_dir / "experimental_log.md"
                idea_path.write_text("Binder concept and hydrolysis outline.\n", encoding="utf-8")
                log_path.write_text("Preliminary observations for zinc flake coating process.\n", encoding="utf-8")

                run_response = client.post(
                    "/api/v3/run",
                    json={
                        "session_id": session_id,
                        "pipeline": "paper_orchestra",
                        "idea_path": str(idea_path),
                        "log_path": str(log_path),
                    },
                )
                run_payload = run_response.json()
                if not run_payload.get("success"):
                    add_gap(gaps, "POST /run", str(run_payload))
                else:
                    run_id = run_payload["data"]["run_id"]
                    routes = importlib.import_module("parallax_v3.api.routes")
                    conductor = getattr(routes, "conductor")
                    events = asyncio.run(collect_events(conductor, run_id))
                    event_types = {event.get("type") for event in events}
                    if not event_types:
                        add_gap(gaps, "GET /run/{run_id}/events", "no events emitted")
                    unknown = sorted(str(value) for value in event_types - ALLOWED_EVENT_TYPES)
                    if unknown:
                        add_gap(gaps, "SSE contract", f"unknown event types: {unknown}")
                    if "complete" not in event_types:
                        add_gap(gaps, "pipeline completion", f"missing complete event: {sorted(event_types)}")

                    workspace_root = REPO_ROOT / "workspace" / session_id
                    inputs_dir = workspace_root / "inputs"
                    expected_inputs = [inputs_dir / "idea.md", inputs_dir / "experimental_log.md"]
                    if not workspace_root.exists():
                        add_gap(gaps, "workspace contract", f"missing workspace directory: {workspace_root}")
                    elif not all(path.exists() for path in expected_inputs):
                        missing = [str(path.relative_to(REPO_ROOT)) for path in expected_inputs if not path.exists()]
                        add_gap(gaps, "workspace inputs", f"missing copied inputs: {missing}")

                    audit_payload = client.get(f"/api/v3/run/{run_id}/audit").json()
                    if not audit_payload.get("success"):
                        add_gap(gaps, "GET /run/{run_id}/audit", str(audit_payload))

                    memory_payload = client.get(f"/api/v3/run/{run_id}/memory").json()
                    if not memory_payload.get("success"):
                        add_gap(gaps, "GET /run/{run_id}/memory", str(memory_payload))
        except Exception as exc:  # pragma: no cover - verifier should degrade to a counted gap
            add_gap(gaps, "api_flow", repr(exc))

    try:
        from parallax_v3.contracts import Phase
        from parallax_v3.runtime.conductor import Conductor

        class _Request:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        conductor = Conductor()
        session = asyncio.run(
            conductor.create_session(
                _Request(
                    research_question="Phase discipline check",
                    target_venue="neurips",
                    citation_style="nature",
                    budget_usd=1.0,
                    max_refinement_iters=2,
                )
            )
        )
        run = asyncio.run(
            conductor.run_pipeline(
                _Request(
                    session_id=session["session_id"],
                    pipeline="paper_orchestra",
                    idea_path="workspace/fixtures/idea.md",
                    log_path="workspace/fixtures/experimental_log.md",
                )
            )
        )
        phase = conductor.transition_phase(run["run_id"], Phase.ACT)
        if phase == Phase.ACT:
            add_gap(gaps, "phase discipline", "Conductor allows direct EXPLORE -> ACT transition")
    except Exception as exc:  # pragma: no cover - verifier should degrade to a counted gap
        add_gap(gaps, "phase discipline", repr(exc))

    for name, detail in gaps:
        print(f"GAP {name}: {detail}")
    print(f"API_OATH_GAP_COUNT={len(gaps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
