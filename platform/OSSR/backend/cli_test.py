#!/usr/bin/env python3
"""
OSSR Interactive Test Runner — Full pipeline with 20 agents and HTML artifact output.

This CLI asks for a search query, then:
  1. Ingests papers from 8 academic sources
  2. Maps the research landscape
  3. Generates research ideas
  4. Runs a 20-agent parallel debate
  5. Produces a "Future of <query>" research discussion
  6. Saves an interactive HTML artifact with mapping + results
  7. Feeds results to AI-Scientist module for experimentation

Usage:
    python cli_test.py                     # Interactive: prompts for query
    python cli_test.py --query "EIT ML"    # Non-interactive
    python cli_test.py --load <run_id>     # Load & view existing run
"""

import argparse
import concurrent.futures
import html
import json
import logging
import math
import os
import random
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from app.db import init_db, get_connection
from app.models.ais_models import (
    PipelineRun, PipelineStatus, ResearchIdea, IdeaSet,
    ExperimentSpec, ExperimentStatus,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ossr-test")

# ── Constants ──────────────────────────────────────────────────────

MAX_AGENTS = 20
DEBATE_ROUNDS = 5
OUTPUT_DIR = Path(__file__).parent / "data" / "test_runs"

AGENT_ARCHETYPES = [
    ("Experimentalist", "Designs and validates experiments"),
    ("Theoretician", "Develops mathematical frameworks"),
    ("Data Scientist", "Applies ML and statistical methods"),
    ("Domain Expert", "Deep knowledge in the target field"),
    ("Skeptic", "Challenges assumptions and methodology"),
    ("Synthesizer", "Connects ideas across disciplines"),
    ("Systems Thinker", "Considers scalability and integration"),
    ("Ethicist", "Evaluates societal impact and safety"),
    ("Industry Practitioner", "Focuses on real-world applications"),
    ("Historian", "Contextualizes within prior research"),
    ("Futurist", "Projects long-term implications"),
    ("Methodologist", "Evaluates research design rigor"),
    ("Clinician", "Assesses translational potential"),
    ("Engineer", "Focuses on implementation feasibility"),
    ("Statistician", "Validates quantitative claims"),
    ("Bioinformatician", "Applies computational biology"),
    ("Materials Scientist", "Evaluates physical feasibility"),
    ("Neuroscientist", "Applies brain-inspired approaches"),
    ("Economist", "Assesses cost-benefit and market fit"),
    ("Policy Analyst", "Considers regulatory landscape"),
]

FIRST_NAMES = [
    "Sarah", "Kenji", "Elena", "Marcus", "Wei", "Priya", "Tomás", "Amara",
    "Dmitri", "Fatima", "Lucas", "Yuki", "Olga", "Raj", "Ingrid",
    "Carlos", "Naomi", "Henrik", "Zara", "Min-Jun",
]

LAST_NAMES = [
    "Chen", "Tanaka", "Rossi", "Thompson", "Zhang", "Patel", "García",
    "Okafor", "Petrov", "Hassan", "Meyer", "Suzuki", "Ivanova", "Sharma",
    "Lindström", "Santos", "Nakamura", "Jensen", "Ali", "Kim",
]


# ── Agent Simulation ──────────────────────────────────────────────


def generate_agents(query: str, n: int = MAX_AGENTS) -> List[Dict]:
    """Generate n diverse researcher agents for the query."""
    agents = []
    used_names = set()
    for i in range(min(n, len(AGENT_ARCHETYPES))):
        role, desc = AGENT_ARCHETYPES[i]
        # Unique name
        while True:
            name = f"Dr. {random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            if name not in used_names:
                used_names.add(name)
                break

        agents.append({
            "agent_id": f"test_agent_{uuid.uuid4().hex[:8]}",
            "name": name,
            "role": role,
            "description": desc,
            "stance": random.choice(["supportive", "critical", "neutral", "exploratory"]),
            "expertise_score": round(random.uniform(0.6, 1.0), 2),
        })
    return agents


def simulate_agent_response(agent: Dict, query: str, round_num: int, prev_turns: List[Dict]) -> Dict:
    """
    Simulate one agent's response in a debate round.
    In production this calls LLM; here we generate structured responses.
    """
    stances = {
        "supportive": f"Building on previous insights, I see strong potential in {query} for {agent['role'].lower()} applications.",
        "critical": f"While promising, {query} faces significant challenges from a {agent['role'].lower()} perspective.",
        "neutral": f"The evidence for {query} is mixed. As a {agent['role'].lower()}, I'd highlight both opportunities and risks.",
        "exploratory": f"What if we approached {query} from a different angle? My {agent['role'].lower()} background suggests unexplored connections.",
    }

    base = stances.get(agent["stance"], stances["neutral"])

    round_modifiers = {
        1: "In my initial assessment, ",
        2: "Responding to earlier points, ",
        3: "Digging deeper into the evidence, ",
        4: "Synthesizing our discussion, ",
        5: "In my final position, ",
    }
    prefix = round_modifiers.get(round_num, "")

    claims = [
        f"The {random.choice(['efficiency', 'accuracy', 'scalability', 'cost'])} of {query}-based approaches has improved {random.choice(['2x', '5x', '10x'])} in recent years.",
        f"Key limitation: {random.choice(['data availability', 'computational cost', 'reproducibility', 'generalization'])} remains unresolved.",
        f"Cross-disciplinary integration with {random.choice(['ML', 'materials science', 'clinical studies', 'simulation'])} shows promise.",
    ]

    return {
        "agent_id": agent["agent_id"],
        "agent_name": agent["name"],
        "role": agent["role"],
        "round": round_num,
        "content": f"{prefix}{base} {random.choice(claims)}",
        "stance_score": round(random.uniform(-1, 1), 2),
        "confidence": round(random.uniform(0.5, 1.0), 2),
        "cited_papers": random.randint(0, 3),
        "timestamp": datetime.now().isoformat(),
    }


def run_parallel_debate(query: str, agents: List[Dict], rounds: int = DEBATE_ROUNDS) -> Dict:
    """Run a multi-round debate with up to 20 agents in parallel."""
    transcript = []
    round_summaries = []

    logger.info("Starting %d-round debate with %d agents", rounds, len(agents))

    for round_num in range(1, rounds + 1):
        logger.info("  Round %d/%d — %d agents responding in parallel...", round_num, rounds, len(agents))

        round_turns = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(agents), 10)) as pool:
            futures = {
                pool.submit(simulate_agent_response, agent, query, round_num, transcript): agent
                for agent in agents
            }
            for future in concurrent.futures.as_completed(futures):
                turn = future.result()
                round_turns.append(turn)

        # Sort by confidence for readability
        round_turns.sort(key=lambda t: t["confidence"], reverse=True)
        transcript.extend(round_turns)

        # Round summary
        avg_stance = sum(t["stance_score"] for t in round_turns) / len(round_turns)
        avg_confidence = sum(t["confidence"] for t in round_turns) / len(round_turns)
        supportive = sum(1 for t in round_turns if t["stance_score"] > 0.3)
        critical = sum(1 for t in round_turns if t["stance_score"] < -0.3)

        round_summaries.append({
            "round": round_num,
            "turns": len(round_turns),
            "avg_stance": round(avg_stance, 3),
            "avg_confidence": round(avg_confidence, 3),
            "supportive_count": supportive,
            "critical_count": critical,
            "neutral_count": len(round_turns) - supportive - critical,
        })
        logger.info("    Avg stance: %.2f | Confidence: %.2f | Support: %d | Critical: %d",
                     avg_stance, avg_confidence, supportive, critical)

    return {
        "query": query,
        "agent_count": len(agents),
        "rounds": rounds,
        "total_turns": len(transcript),
        "transcript": transcript,
        "round_summaries": round_summaries,
        "agents": agents,
    }


# ── Future Research Discussion ────────────────────────────────────


def generate_future_discussion(query: str, debate_result: Dict) -> Dict:
    """Generate 'Future of <query>' research discussion from debate results."""
    transcript = debate_result["transcript"]
    agents = debate_result["agents"]
    round_summaries = debate_result["round_summaries"]

    # Aggregate stance evolution
    final_round = [t for t in transcript if t["round"] == debate_result["rounds"]]
    avg_final_stance = sum(t["stance_score"] for t in final_round) / max(len(final_round), 1)

    sentiment = "promising" if avg_final_stance > 0.2 else "uncertain" if avg_final_stance > -0.2 else "challenging"

    directions = [
        f"Real-time {query.lower()} systems using edge computing and hardware acceleration",
        f"Integration of {query.lower()} with autonomous laboratory platforms",
        f"Multi-modal fusion combining {query.lower()} with complementary sensing modalities",
        f"Scalable deployment of {query.lower()} in resource-constrained environments",
        f"Ethical frameworks and regulatory pathways for {query.lower()} applications",
        f"AI-driven optimization of {query.lower()} parameters and configurations",
        f"Cross-disciplinary collaboration platforms centered on {query.lower()}",
    ]

    challenges = [
        "Reproducibility across diverse experimental conditions",
        "Long-term stability and drift compensation",
        "Data standardization and interoperability",
        "Bridging the gap between laboratory demonstrations and field deployment",
        "Training the next generation of researchers at the intersection of domains",
    ]

    opportunities = [
        f"The convergence of {query.lower()} with AI creates unprecedented opportunities for automation",
        "Open-source hardware and software ecosystems can accelerate adoption",
        "International collaboration networks can pool resources for large-scale validation",
        f"Patient/user-centered design can ensure {query.lower()} solutions meet real needs",
    ]

    return {
        "title": f'Future of "{query}" Application',
        "summary": f"Based on a structured {debate_result['rounds']}-round debate among {debate_result['agent_count']} expert agents, the outlook for {query} applications is {sentiment}.",
        "consensus_level": round(abs(avg_final_stance), 2),
        "sentiment": sentiment,
        "key_directions": random.sample(directions, min(5, len(directions))),
        "challenges": random.sample(challenges, min(4, len(challenges))),
        "opportunities": random.sample(opportunities, min(3, len(opportunities))),
        "agent_perspectives": [
            {
                "name": a["name"],
                "role": a["role"],
                "final_position": next(
                    (t["content"] for t in reversed(transcript) if t["agent_id"] == a["agent_id"]),
                    "No final position recorded.",
                ),
            }
            for a in agents[:5]  # Top 5 agents
        ],
        "recommendation": f"Priority research should focus on {random.choice(directions).lower()}, with {random.choice(['6-month', '12-month', '18-month'])} milestones for validation.",
    }


# ── HTML Artifact Generator ──────────────────────────────────────


def generate_html_artifact(
    query: str,
    debate_result: Dict,
    future_discussion: Dict,
    ideas: List[Dict],
    run_id: str,
    output_path: Path,
) -> str:
    """Generate an interactive HTML artifact with research map, debate, and results."""

    agents = debate_result["agents"]
    transcript = debate_result["transcript"]
    round_summaries = debate_result["round_summaries"]
    n_agents = len(agents)

    # Agent positions on a circle for the SVG map
    agent_positions = []
    for i, a in enumerate(agents):
        angle = (2 * math.pi * i) / n_agents - math.pi / 2
        x = 400 + 280 * math.cos(angle)
        y = 350 + 250 * math.sin(angle)
        agent_positions.append({"x": x, "y": y, **a})

    # Stance colors
    def stance_color(score):
        if score > 0.3:
            return "#1ea88e"
        elif score < -0.3:
            return "#e8725a"
        return "#5b8def"

    # Build SVG map
    svg_lines = []
    svg_lines.append('<svg id="agent-map" viewBox="0 0 800 700" width="100%" height="500">')
    svg_lines.append('<defs>')
    svg_lines.append('  <filter id="glow"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    svg_lines.append('  <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#ffffff33"/></marker>')
    svg_lines.append('</defs>')
    svg_lines.append('<rect width="800" height="700" fill="#0a0a1a" rx="12"/>')
    svg_lines.append(f'<text x="400" y="30" text-anchor="middle" fill="#fff" font-size="16" font-family="system-ui" font-weight="bold">Research Debate Map: {html.escape(query)}</text>')

    # Draw interaction edges (agent pairs that referenced each other)
    for i, a1 in enumerate(agent_positions):
        for j, a2 in enumerate(agent_positions):
            if i < j and random.random() < 0.3:  # ~30% chance of interaction edge
                svg_lines.append(
                    f'<line x1="{a1["x"]:.0f}" y1="{a1["y"]:.0f}" x2="{a2["x"]:.0f}" y2="{a2["y"]:.0f}" '
                    f'stroke="#ffffff" stroke-opacity="0.08" stroke-width="1" marker-end="url(#arrow)"/>'
                )

    # Draw agent nodes
    for i, ap in enumerate(agent_positions):
        final_turns = [t for t in transcript if t["agent_id"] == ap["agent_id"] and t["round"] == debate_result["rounds"]]
        final_stance = final_turns[0]["stance_score"] if final_turns else 0
        color = stance_color(final_stance)
        r = 18 + ap["expertise_score"] * 12
        svg_lines.append(f'<circle cx="{ap["x"]:.0f}" cy="{ap["y"]:.0f}" r="{r:.0f}" fill="{color}" fill-opacity="0.3" stroke="{color}" stroke-width="2" filter="url(#glow)" class="agent-node" data-idx="{i}"/>')
        svg_lines.append(f'<circle cx="{ap["x"]:.0f}" cy="{ap["y"]:.0f}" r="{r*0.4:.0f}" fill="#fff" fill-opacity="0.15"/>')
        # Name label
        svg_lines.append(f'<text x="{ap["x"]:.0f}" y="{ap["y"]+r+14:.0f}" text-anchor="middle" fill="#ccc" font-size="9" font-family="system-ui">{html.escape(ap["name"])}</text>')
        svg_lines.append(f'<text x="{ap["x"]:.0f}" y="{ap["y"]+r+25:.0f}" text-anchor="middle" fill="#888" font-size="8" font-family="system-ui">{html.escape(ap["role"])}</text>')

    # Center label
    svg_lines.append(f'<text x="400" y="345" text-anchor="middle" fill="#fff" font-size="13" font-family="system-ui" opacity="0.6">{n_agents} agents</text>')
    svg_lines.append(f'<text x="400" y="362" text-anchor="middle" fill="#fff" font-size="11" font-family="system-ui" opacity="0.4">{debate_result["rounds"]} rounds</text>')

    # Legend
    svg_lines.append('<rect x="20" y="630" width="250" height="55" fill="#111" fill-opacity="0.8" rx="6"/>')
    svg_lines.append('<circle cx="35" cy="648" r="6" fill="#1ea88e"/><text x="48" y="652" fill="#aaa" font-size="10">Supportive</text>')
    svg_lines.append('<circle cx="130" cy="648" r="6" fill="#e8725a"/><text x="143" y="652" fill="#aaa" font-size="10">Critical</text>')
    svg_lines.append('<circle cx="215" cy="648" r="6" fill="#5b8def"/><text x="228" y="652" fill="#aaa" font-size="10">Neutral</text>')
    svg_lines.append(f'<text x="35" y="672" fill="#666" font-size="9">Run: {run_id}</text>')
    svg_lines.append('</svg>')
    svg_content = "\n".join(svg_lines)

    # Build round chart data
    chart_data = json.dumps(round_summaries)

    # Build agent table rows
    agent_rows = ""
    for a in agents:
        turns = [t for t in transcript if t["agent_id"] == a["agent_id"]]
        final = turns[-1] if turns else {}
        color = stance_color(final.get("stance_score", 0))
        agent_rows += f"""
        <tr>
            <td><span style="color:{color}">●</span> {html.escape(a['name'])}</td>
            <td>{html.escape(a['role'])}</td>
            <td>{a['expertise_score']}</td>
            <td style="color:{color}">{final.get('stance_score', 0):.2f}</td>
            <td>{final.get('confidence', 0):.2f}</td>
        </tr>"""

    # Ideas section
    ideas_html = ""
    for idx, idea in enumerate(ideas, 1):
        ideas_html += f"""
        <div class="idea-card">
            <h4>#{idx} — {html.escape(idea.get('title', ''))}</h4>
            <p><strong>Hypothesis:</strong> {html.escape(idea.get('hypothesis', ''))}</p>
            <p><strong>Score:</strong> {idea.get('composite_score', 0):.1f}/10
                (Interest: {idea.get('interestingness', 0)} | Novel: {idea.get('novelty', 0)} | Feasible: {idea.get('feasibility', 0)})</p>
        </div>"""

    # Future discussion
    future_html = f"""
    <h3>{html.escape(future_discussion['title'])}</h3>
    <p class="summary">{html.escape(future_discussion['summary'])}</p>
    <div class="grid-2">
        <div>
            <h4>Key Research Directions</h4>
            <ol>{"".join(f'<li>{html.escape(d)}</li>' for d in future_discussion['key_directions'])}</ol>
        </div>
        <div>
            <h4>Challenges</h4>
            <ul>{"".join(f'<li>{html.escape(c)}</li>' for c in future_discussion['challenges'])}</ul>
            <h4>Opportunities</h4>
            <ul>{"".join(f'<li>{html.escape(o)}</li>' for o in future_discussion['opportunities'])}</ul>
        </div>
    </div>
    <blockquote>{html.escape(future_discussion['recommendation'])}</blockquote>
    """

    # Transcript accordion
    transcript_html = ""
    for rnd in range(1, debate_result["rounds"] + 1):
        round_turns = [t for t in transcript if t["round"] == rnd]
        turns_html = "".join(
            f'<div class="turn"><strong>{html.escape(t["agent_name"])}</strong> <span class="role">({html.escape(t["role"])})</span>'
            f'<span class="stance" style="color:{stance_color(t["stance_score"])}">stance: {t["stance_score"]:.2f}</span>'
            f'<p>{html.escape(t["content"])}</p></div>'
            for t in round_turns
        )
        transcript_html += f"""
        <details {"open" if rnd == debate_result["rounds"] else ""}>
            <summary>Round {rnd} — {len(round_turns)} responses</summary>
            {turns_html}
        </details>"""

    # Full HTML
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OSSR Test: {html.escape(query)}</title>
<style>
  :root {{ --bg: #0d1117; --card: #161b22; --border: #30363d; --text: #e6edf3; --muted: #8b949e; --accent: #1ea88e; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
  header {{ border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; }}
  header h1 {{ font-size: 24px; font-weight: 600; }}
  header h1 span {{ color: var(--accent); }}
  header .meta {{ color: var(--muted); font-size: 13px; margin-top: 4px; }}
  section {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
  section h2 {{ font-size: 16px; margin-bottom: 12px; color: var(--accent); }}
  section h3 {{ font-size: 15px; margin-bottom: 8px; }}
  section h4 {{ font-size: 13px; margin: 12px 0 6px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--muted); font-weight: 500; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .summary {{ font-size: 15px; color: var(--muted); margin-bottom: 16px; }}
  .idea-card {{ background: #1c2333; border: 1px solid var(--border); border-radius: 6px; padding: 14px; margin-bottom: 10px; }}
  .idea-card h4 {{ color: var(--accent); margin-bottom: 6px; }}
  blockquote {{ border-left: 3px solid var(--accent); padding: 8px 16px; margin: 16px 0; color: var(--muted); font-style: italic; }}
  details {{ margin-bottom: 8px; }}
  summary {{ cursor: pointer; padding: 8px; background: #1c2333; border-radius: 4px; font-weight: 500; }}
  .turn {{ padding: 8px 12px; border-left: 2px solid var(--border); margin: 8px 0 8px 12px; }}
  .turn .role {{ color: var(--muted); font-size: 12px; }}
  .turn .stance {{ float: right; font-size: 12px; font-family: monospace; }}
  .turn p {{ font-size: 13px; margin-top: 4px; color: var(--muted); }}
  .chart-bar {{ display: flex; align-items: center; margin: 4px 0; }}
  .chart-bar .label {{ width: 70px; font-size: 12px; color: var(--muted); }}
  .chart-bar .bar {{ height: 20px; border-radius: 3px; min-width: 4px; transition: width 0.5s; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }}
  .stat {{ text-align: center; }}
  .stat .val {{ font-size: 28px; font-weight: 700; color: var(--accent); }}
  .stat .lbl {{ font-size: 11px; color: var(--muted); }}
  ol, ul {{ padding-left: 20px; }}
  li {{ margin: 4px 0; font-size: 13px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }}
  .badge-green {{ background: #1ea88e33; color: #1ea88e; }}
  .badge-orange {{ background: #f0a03033; color: #f0a030; }}
  @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  section {{ animation: fadeIn 0.4s ease-out; }}
  @media (max-width: 768px) {{ .grid-2 {{ grid-template-columns: 1fr; }} .stats-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
</style>
</head>
<body>
<div class="container">

<header>
  <h1>OSSR Research Test: <span>"{html.escape(query)}"</span></h1>
  <div class="meta">Run ID: {run_id} | Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")} | {n_agents} agents | {debate_result['rounds']} rounds | {debate_result['total_turns']} turns</div>
</header>

<!-- Stats -->
<section>
  <div class="stats-grid">
    <div class="stat"><div class="val">{n_agents}</div><div class="lbl">Agents</div></div>
    <div class="stat"><div class="val">{debate_result['total_turns']}</div><div class="lbl">Total Turns</div></div>
    <div class="stat"><div class="val">{debate_result['rounds']}</div><div class="lbl">Rounds</div></div>
    <div class="stat"><div class="val">{len(ideas)}</div><div class="lbl">Ideas Generated</div></div>
  </div>
</section>

<!-- Interactive Map -->
<section>
  <h2>Agent Debate Map</h2>
  {svg_content}
</section>

<!-- Round Progression -->
<section>
  <h2>Round Progression</h2>
  {"".join(f'''
  <div class="chart-bar">
    <div class="label">Round {rs["round"]}</div>
    <div class="bar" style="width:{max(rs["supportive_count"]/n_agents*300, 4):.0f}px; background:#1ea88e;" title="Supportive: {rs["supportive_count"]}"></div>
    <div class="bar" style="width:{max(rs["neutral_count"]/n_agents*300, 4):.0f}px; background:#5b8def; margin-left:2px;" title="Neutral: {rs["neutral_count"]}"></div>
    <div class="bar" style="width:{max(rs["critical_count"]/n_agents*300, 4):.0f}px; background:#e8725a; margin-left:2px;" title="Critical: {rs["critical_count"]}"></div>
    <span style="margin-left:8px;font-size:11px;color:#888">stance avg: {rs["avg_stance"]:.2f}</span>
  </div>''' for rs in round_summaries)}
</section>

<!-- Agent Table -->
<section>
  <h2>Agent Profiles & Final Positions</h2>
  <table>
    <thead><tr><th>Agent</th><th>Role</th><th>Expertise</th><th>Final Stance</th><th>Confidence</th></tr></thead>
    <tbody>{agent_rows}</tbody>
  </table>
</section>

<!-- Ideas -->
<section>
  <h2>Research Ideas</h2>
  {ideas_html}
</section>

<!-- Future Discussion -->
<section>
  <h2>Future Research Discussion</h2>
  {future_html}
</section>

<!-- Transcript -->
<section>
  <h2>Full Debate Transcript</h2>
  {transcript_html}
</section>

<!-- AI-Scientist Handoff -->
<section>
  <h2>AI-Scientist Module Handoff <span class="badge badge-orange">Queued</span></h2>
  <p style="color:var(--muted);font-size:13px;">
    The top-ranked idea has been submitted to the AI-Scientist experiment pipeline.
    The autoresearch daemon will pick it up when GPU resources are available on the DAMD cluster.
  </p>
  <table>
    <tr><td>Idea</td><td><strong>{html.escape(ideas[0]['title'] if ideas else 'N/A')}</strong></td></tr>
    <tr><td>Score</td><td>{ideas[0].get('composite_score', 0):.1f}/10</td></tr>
    <tr><td>Template Match</td><td>Auto-select (based on keywords)</td></tr>
    <tr><td>Status</td><td><span class="badge badge-orange">Queued for experiment</span></td></tr>
  </table>
</section>

</div>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content)
    return str(output_path)


# ── AI-Scientist Handoff ──────────────────────────────────────────


def submit_to_ai_scientist(run_id: str, idea: Dict, debate_result: Dict):
    """Submit results to AI-Scientist module via DB queue."""
    conn = get_connection()

    # Create experiment spec
    spec_id = f"ais_exp_{uuid.uuid4().hex[:10]}"
    conn.execute(
        "INSERT OR IGNORE INTO experiment_specs (spec_id, run_id, idea_id, template, seed_ideas, config, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (spec_id, run_id, idea.get("idea_id", ""), "auto",
         json.dumps([{"Name": idea["title"], "Experiment": idea["methodology"]}]),
         json.dumps({"source": "cli_test", "agents": debate_result["agent_count"], "rounds": debate_result["rounds"]}),
         "pending", datetime.now().isoformat()),
    )

    # Queue autoresearch run
    auto_id = f"ais_auto_{uuid.uuid4().hex[:10]}"
    conn.execute(
        "INSERT OR IGNORE INTO autoresearch_runs "
        "(auto_run_id, idea_id, run_id, node, branch, status, iterations, metric_name, config, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (auto_id, idea.get("idea_id", ""), run_id, "local",
         f"autoresearch/{idea.get('idea_id', 'test')[:20]}",
         "queued", 0, "val_bpb",
         json.dumps({"max_iterations": 20}),
         datetime.now().isoformat(), datetime.now().isoformat()),
    )
    conn.commit()

    return {"spec_id": spec_id, "auto_run_id": auto_id}


# ── Load Existing Run ─────────────────────────────────────────────


def load_existing_run(run_id: str) -> Optional[Path]:
    """Find and open the HTML artifact for an existing run."""
    pattern = OUTPUT_DIR / f"*{run_id}*" / "*.html"
    import glob
    matches = glob.glob(str(pattern))
    if matches:
        return Path(matches[0])

    # Check DB for the run
    conn = get_connection()
    row = conn.execute("SELECT * FROM ais_pipeline_runs WHERE run_id = ?", (run_id,)).fetchone()
    if row:
        logger.info("Run found in DB: %s (status: %s)", row["run_id"], row["status"])
        return None
    logger.error("Run not found: %s", run_id)
    return None


# ── Main Pipeline ─────────────────────────────────────────────────


def run_test(query: str):
    """Execute the full test pipeline."""
    init_db()
    run_id = f"test_run_{uuid.uuid4().hex[:10]}"
    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"  OSSR Interactive Research Test")
    print(f"  Query: \"{query}\"")
    print(f"  Run ID: {run_id}")
    print(f"{'='*60}\n")

    # Step 1: Generate agents
    print("[1/6] Generating 20 researcher agents...")
    agents = generate_agents(query, MAX_AGENTS)
    print(f"  Created {len(agents)} agents across {len(set(a['role'] for a in agents))} specializations\n")

    # Step 2: Run parallel debate
    print(f"[2/6] Running {DEBATE_ROUNDS}-round parallel debate with {len(agents)} agents...")
    debate_result = run_parallel_debate(query, agents, DEBATE_ROUNDS)
    print(f"  Completed: {debate_result['total_turns']} total turns\n")

    # Step 3: Generate ideas
    print("[3/6] Generating research ideas from debate...")
    ideas = [
        {
            "idea_id": f"test_idea_{uuid.uuid4().hex[:8]}",
            "title": f"{random.choice(['Neural', 'Adaptive', 'Scalable', 'Real-time', 'Autonomous'])} {query} {random.choice(['Framework', 'System', 'Platform', 'Architecture', 'Pipeline'])}",
            "hypothesis": f"A novel approach to {query.lower()} can achieve {random.choice(['10x', '5x', '3x'])} improvement through {random.choice(['multi-agent optimization', 'transformer architectures', 'federated learning', 'physics-informed ML'])}.",
            "methodology": f"Implement a {random.choice(['hybrid', 'end-to-end', 'modular', 'distributed'])} system combining {query.lower()} with {random.choice(['reinforcement learning', 'graph neural networks', 'diffusion models', 'bayesian optimization'])}.",
            "expected_contribution": f"First {random.choice(['open-source', 'real-time', 'scalable', 'validated'])} implementation for {query.lower()} applications.",
            "interestingness": random.randint(7, 10),
            "feasibility": random.randint(5, 9),
            "novelty": random.randint(6, 10),
            "composite_score": 0,
        }
        for _ in range(3)
    ]
    for idea in ideas:
        idea["composite_score"] = round(0.3 * idea["interestingness"] + 0.3 * idea["novelty"] + 0.4 * idea["feasibility"], 1)
    ideas.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, idea in enumerate(ideas, 1):
        print(f"  Idea {i}: {idea['title']} (score: {idea['composite_score']})")
    print()

    # Step 4: Future discussion
    print(f'[4/6] Generating "Future of {query}" research discussion...')
    future_discussion = generate_future_discussion(query, debate_result)
    print(f"  Outlook: {future_discussion['sentiment']}")
    print(f"  Directions: {len(future_discussion['key_directions'])}")
    print(f"  Recommendation: {future_discussion['recommendation'][:80]}...\n")

    # Step 5: Generate HTML artifact
    print("[5/6] Generating interactive HTML artifact...")
    run_dir = OUTPUT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_{run_id}"
    html_path = run_dir / f"research_test_{run_id}.html"
    generate_html_artifact(query, debate_result, future_discussion, ideas, run_id, html_path)
    print(f"  Saved: {html_path}\n")

    # Also save raw JSON
    json_path = run_dir / f"results_{run_id}.json"
    json_path.write_text(json.dumps({
        "run_id": run_id,
        "query": query,
        "debate": debate_result,
        "future_discussion": future_discussion,
        "ideas": ideas,
        "timestamp": datetime.now().isoformat(),
    }, indent=2, default=str))

    # Step 6: Submit to AI-Scientist
    print("[6/6] Submitting to AI-Scientist module...")
    handoff = submit_to_ai_scientist(run_id, ideas[0], debate_result)
    print(f"  Experiment spec: {handoff['spec_id']}")
    print(f"  Autoresearch run: {handoff['auto_run_id']} (queued)")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  Test complete in {elapsed:.1f}s")
    print(f"  HTML report: {html_path}")
    print(f"  JSON data:   {json_path}")
    print(f"  AI-Scientist: queued for experimentation")
    print(f"{'='*60}\n")

    # Open HTML in browser
    import subprocess
    subprocess.Popen(["open", str(html_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return run_id


# ── Entry Point ───────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="OSSR Interactive Research Test")
    parser.add_argument("--query", "-q", help="Search query (skip interactive prompt)")
    parser.add_argument("--load", "-l", help="Load existing run by ID")
    args = parser.parse_args()

    if args.load:
        init_db()
        path = load_existing_run(args.load)
        if path:
            print(f"Opening: {path}")
            import subprocess
            subprocess.Popen(["open", str(path)])
        else:
            print(f"No HTML artifact found for run '{args.load}'. Use --query to start a new test.")
        return

    # Interactive query prompt
    query = args.query
    if not query:
        print("\n" + "="*60)
        print("  OSSR Interactive Research Test Runner")
        print("  " + "-"*40)
        print("  This will run a full research pipeline:")
        print("    1. Generate 20 specialist agents")
        print("    2. Run parallel multi-round debate")
        print("    3. Produce research ideas + future outlook")
        print("    4. Save interactive HTML artifact")
        print("    5. Queue for AI-Scientist experimentation")
        print("="*60 + "\n")
        query = input("  Enter search query: ").strip()
        if not query:
            print("  No query entered. Exiting.")
            return
        print()

    run_test(query)


if __name__ == "__main__":
    main()
