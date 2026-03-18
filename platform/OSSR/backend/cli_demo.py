#!/usr/bin/env python3
"""
OSSR Demo CLI — Seed the database with realistic research data for dashboard preview.

Usage:
    python cli_demo.py seed                  # Seed full demo dataset
    python cli_demo.py seed --topic "EIT"    # Seed around a specific topic
    python cli_demo.py svg                   # Generate SVG research map from DB
    python cli_demo.py svg --animated        # SVG with CSS animations
    python cli_demo.py history               # List existing pipeline runs
    python cli_demo.py clear                 # Clear all demo data

Run the backend first: python run.py
Then open http://localhost:3001 to see the dashboard.
"""

import argparse
import json
import math
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.db import init_db, get_connection

# ── Demo Data Definitions ──────────────────────────────────────────

DEMO_DOMAINS = {
    "Electrochemical Sensing": {
        "subfields": {
            "Impedance Spectroscopy (EIS)": [
                "Protein Binding Detection",
                "Corrosion Monitoring",
                "Battery State Estimation",
            ],
            "Electrical Impedance Tomography (EIT)": [
                "Lung Ventilation Imaging",
                "Neural Reconstruction",
                "Industrial Process Tomography",
            ],
            "Cyclic Voltammetry": [
                "Neurotransmitter Detection",
                "Heavy Metal Analysis",
            ],
        },
    },
    "AI for Science": {
        "subfields": {
            "Neural Network Architectures": [
                "Transformer Probing",
                "Graph Neural Networks for Molecules",
                "Diffusion Models for Simulation",
            ],
            "Automated Experiment Design": [
                "Bayesian Optimization",
                "Autonomous Lab Systems",
            ],
            "AI-Driven Paper Generation": [
                "LLM Literature Synthesis",
                "Multi-Agent Research Debate",
            ],
        },
    },
    "Biosensor Design": {
        "subfields": {
            "Aptamer-based Sensors": [
                "SARS-CoV-2 Detection",
                "Glucose Monitoring",
            ],
            "Microfluidic Integration": [
                "Lab-on-Chip Platforms",
                "Point-of-Care Diagnostics",
            ],
        },
    },
}

DEMO_AUTHORS = [
    "Chen, W.", "Park, J.", "Mueller, K.", "Santos, M.", "Kim, H.",
    "Patel, R.", "Zhang, L.", "Thompson, A.", "Nakamura, T.", "Garcia, E.",
    "Li, X.", "Johnson, B.", "Rossi, F.", "Tanaka, S.", "Wang, Y.",
]

DEMO_VENUES = [
    "Nature Electronics", "Biosensors and Bioelectronics", "Analytical Chemistry",
    "ACS Nano", "Lab on a Chip", "Sensors and Actuators B", "NeurIPS",
    "IEEE Sensors Journal", "Electrochimica Acta", "ICLR",
]

DEMO_AGENTS = [
    {"name": "Dr. Sarah Chen", "role": "Electrochemist", "affiliation": "MIT"},
    {"name": "Prof. Kenji Tanaka", "role": "ML Researcher", "affiliation": "U. Tokyo"},
    {"name": "Dr. Elena Rossi", "role": "Biosensor Engineer", "affiliation": "ETH Zurich"},
    {"name": "Dr. Marcus Thompson", "role": "Signal Processing", "affiliation": "Stanford"},
    {"name": "Prof. Wei Zhang", "role": "Materials Scientist", "affiliation": "Tsinghua"},
]

DEMO_IDEAS = [
    {
        "title": "Transformer-Accelerated EIT Reconstruction",
        "hypothesis": "Vision Transformers can reconstruct impedance maps from boundary voltages 10x faster than traditional back-projection, enabling real-time medical imaging.",
        "methodology": "Train ViT on 50K simulated EIDORS phantoms, benchmark against GREIT and D-bar methods on experimental tank data.",
        "expected_contribution": "First real-time neural EIT system suitable for bedside lung monitoring.",
        "interestingness": 9, "feasibility": 7, "novelty": 8,
    },
    {
        "title": "Multi-Agent Debate for Hypothesis Refinement",
        "hypothesis": "Structured adversarial debate between AI agents produces more robust research hypotheses than single-agent reflection.",
        "methodology": "Compare Mirofish-orchestrated 5-round debates against chain-of-thought on 100 seed ideas from OSSR landscape.",
        "expected_contribution": "Empirical validation of multi-agent research methodology.",
        "interestingness": 8, "feasibility": 9, "novelty": 7,
    },
    {
        "title": "Aptamer-EIS Fusion for Rapid Pathogen Detection",
        "hypothesis": "Combining aptamer selectivity with EIS readout enables sub-minute pathogen identification at point-of-care.",
        "methodology": "Screen aptamer library against 5 common pathogens, characterize binding kinetics via Nyquist plot analysis.",
        "expected_contribution": "Portable diagnostic platform for field-deployable disease surveillance.",
        "interestingness": 9, "feasibility": 6, "novelty": 8,
    },
]


# ── Seed Functions ──────────────────────────────────────────────────


def seed_papers(conn, topic_filter=None):
    """Seed papers with realistic metadata."""
    papers = []
    now = datetime.now()

    for domain, domain_data in DEMO_DOMAINS.items():
        if topic_filter and topic_filter.lower() not in domain.lower():
            continue
        for subfield, threads in domain_data["subfields"].items():
            for thread in threads:
                # 3-8 papers per thread
                n_papers = random.randint(3, 8)
                for i in range(n_papers):
                    doi = f"10.{random.randint(1000,9999)}/{uuid.uuid4().hex[:8]}"
                    pub_date = (now - timedelta(days=random.randint(30, 1200))).strftime("%Y-%m-%d")
                    authors = random.sample(DEMO_AUTHORS, k=random.randint(2, 5))
                    title = f"{random.choice(['Novel', 'Improved', 'Scalable', 'Rapid', 'Low-cost'])} {thread}: {random.choice(['A comparative study', 'New approaches', 'Performance analysis', 'Design optimization', 'Experimental validation'])}"

                    paper = {
                        "doi": doi,
                        "title": title,
                        "abstract": f"This paper presents advances in {thread.lower()} within {subfield.lower()}. We demonstrate {random.choice(['improved sensitivity', 'faster processing', 'novel architecture', 'reduced cost'])} compared to existing methods. Results show {random.choice(['2x improvement', '95% accuracy', 'sub-second response', 'nanomolar detection limits'])}.",
                        "authors": json.dumps(authors),
                        "year": int(pub_date[:4]),
                        "venue": random.choice(DEMO_VENUES),
                        "source": random.choice(["arxiv", "semantic_scholar", "openalex", "ieee"]),
                        "keywords": json.dumps([thread.lower(), subfield.lower(), domain.lower()]),
                        "citation_count": random.randint(0, 150),
                        "status": "ingested",
                        "ingested_at": pub_date,
                    }
                    papers.append(paper)

    for p in papers:
        meta = json.dumps({"venue": p["venue"], "year": p["year"]})
        conn.execute(
            "INSERT OR IGNORE INTO papers (doi, title, abstract, authors, publication_date, source, keywords, citation_count, status, ingested_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p["doi"], p["title"], p["abstract"], p["authors"], p["ingested_at"],
             p["source"], p["keywords"], p["citation_count"],
             p["status"], p["ingested_at"], meta),
        )
    conn.commit()
    return papers


def seed_topics(conn, topic_filter=None):
    """Seed 3-level topic hierarchy."""
    topics = []
    for domain_name, domain_data in DEMO_DOMAINS.items():
        if topic_filter and topic_filter.lower() not in domain_name.lower():
            continue

        domain_id = f"domain_{uuid.uuid4().hex[:8]}"
        topics.append({
            "topic_id": domain_id, "name": domain_name,
            "level": 0, "parent_id": None,
            "paper_count": sum(len(ts) * 5 for ts in domain_data["subfields"].values()),
            "metadata": json.dumps({}),
        })

        for sf_name, threads in domain_data["subfields"].items():
            sf_id = f"subfield_{uuid.uuid4().hex[:8]}"
            topics.append({
                "topic_id": sf_id, "name": sf_name,
                "level": 1, "parent_id": domain_id,
                "paper_count": len(threads) * 5,
                "metadata": json.dumps({}),
            })

            for thread_name in threads:
                thread_id = f"thread_{uuid.uuid4().hex[:8]}"
                topics.append({
                    "topic_id": thread_id, "name": thread_name,
                    "level": 2, "parent_id": sf_id,
                    "paper_count": random.randint(3, 8),
                    "metadata": json.dumps({"gaps": [{
                        "gap_score": round(random.uniform(0.3, 0.9), 2),
                        "topic_a": thread_name,
                        "partner_topic": random.choice(["ML Integration", "Real-time Systems", "Miniaturization"]),
                        "opportunity": f"Underexplored intersection of {thread_name.lower()} with emerging techniques.",
                    }]}),
                })

    for t in topics:
        conn.execute(
            "INSERT OR IGNORE INTO topics (topic_id, name, level, description, parent_id, paper_count, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (t["topic_id"], t["name"], t["level"], "", t["parent_id"], t["paper_count"], t["metadata"]),
        )
    conn.commit()
    return topics


def seed_agents(conn):
    """Seed researcher agent profiles."""
    agents = []
    for a in DEMO_AGENTS:
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        profile = {
            "agent_id": agent_id,
            "name": a["name"],
            "role": a["role"],
            "affiliation": a["affiliation"],
            "expertise": [a["role"].lower(), "research methodology"],
            "llm_provider": "anthropic",
            "llm_model": "claude-sonnet-4-20250514",
            "skills": ["literature_review", "experimental_design", "statistical_analysis"],
            "system_prompt": f"You are {a['name']}, a {a['role']} at {a['affiliation']}.",
        }
        agents.append(profile)
        conn.execute(
            "INSERT OR IGNORE INTO researcher_profiles (agent_id, data) VALUES (?, ?)",
            (agent_id, json.dumps(profile)),
        )
    conn.commit()
    return agents


def seed_ais_pipeline(conn):
    """Seed a completed AiS pipeline run with ideas, draft, and experiment."""
    run_id = f"ais_run_{uuid.uuid4().hex[:10]}"
    now = datetime.now().isoformat()

    # Create pipeline run
    ideas_data = []
    for idx, idea_def in enumerate(DEMO_IDEAS):
        idea_id = f"ais_idea_{uuid.uuid4().hex[:10]}"
        score = round(0.3 * idea_def["interestingness"] + 0.3 * idea_def["novelty"] + 0.4 * idea_def["feasibility"], 2)
        idea = {
            "idea_id": idea_id,
            "title": idea_def["title"],
            "hypothesis": idea_def["hypothesis"],
            "methodology": idea_def["methodology"],
            "expected_contribution": idea_def["expected_contribution"],
            "interestingness": idea_def["interestingness"],
            "feasibility": idea_def["feasibility"],
            "novelty": idea_def["novelty"],
            "composite_score": score,
            "grounding_papers": [],
            "target_gap": None,
            "novelty_check_result": {"is_novel": True, "similar_count": random.randint(0, 3)},
            "reflection_rounds_used": 3,
        }
        ideas_data.append(idea)

        conn.execute(
            "INSERT OR IGNORE INTO research_ideas (idea_id, run_id, data, created_at) VALUES (?, ?, ?, ?)",
            (idea_id, run_id, json.dumps(idea), now),
        )

    selected_idea = ideas_data[0]

    # Create draft
    draft_id = f"ais_draft_{uuid.uuid4().hex[:10]}"
    draft = {
        "draft_id": draft_id,
        "title": selected_idea["title"],
        "authors": [a["name"] for a in DEMO_AGENTS[:3]],
        "abstract": f"We present {selected_idea['title'].lower()}, a novel approach that {selected_idea['hypothesis'].lower()} Our methodology involves {selected_idea['methodology'][:100].lower()}...",
        "sections": [
            {"name": "introduction", "heading": "Introduction", "content": f"Research in {selected_idea['title'].split(':')[0].lower()} has seen significant growth...", "citations": [], "word_count": 450},
            {"name": "background", "heading": "Background", "content": "Prior work has established foundational approaches...", "citations": [], "word_count": 380},
            {"name": "methodology", "heading": "Methodology", "content": selected_idea["methodology"], "citations": [], "word_count": 620},
            {"name": "results", "heading": "Results", "content": "Our experiments demonstrate significant improvements over baseline methods...", "citations": [], "word_count": 550},
            {"name": "discussion", "heading": "Discussion", "content": "The results validate our hypothesis and open new research directions...", "citations": [], "word_count": 400},
            {"name": "conclusion", "heading": "Conclusion", "content": "We have presented a novel approach that advances the state of the art...", "citations": [], "word_count": 200},
        ],
        "bibliography": [
            {"doi": f"10.{random.randint(1000,9999)}/ref{i}", "key": f"ref{i}", "title": f"Reference paper {i}", "authors": random.sample(DEMO_AUTHORS, 2), "venue": random.choice(DEMO_VENUES), "year": random.randint(2020, 2025), "bibtex": "", "source": "ossr_ingested"}
            for i in range(1, 9)
        ],
        "format": "ieee",
        "review_scores": {"overall": 7.5, "decision": "Accept", "reviews": [
            {"reviewer": 1, "originality": 8, "quality": 7, "clarity": 8, "significance": 7},
            {"reviewer": 2, "originality": 7, "quality": 8, "clarity": 7, "significance": 8},
            {"reviewer": 3, "originality": 8, "quality": 7, "clarity": 8, "significance": 7},
        ]},
        "metadata": {"generated_by": "Agent AiS v1.0 (demo)"},
        "created_at": now,
    }

    conn.execute(
        "INSERT OR IGNORE INTO paper_drafts (draft_id, run_id, data, created_at) VALUES (?, ?, ?, ?)",
        (draft_id, run_id, json.dumps(draft), now),
    )

    # Create pipeline run record
    stage_results = {
        "stage_1": {"papers_ingested": 150, "topics_found": 25, "gaps_found": 8},
        "stage_2": {"set_id": f"ais_set_{uuid.uuid4().hex[:10]}", "ideas_generated": len(ideas_data), "top_idea": ideas_data[0]},
        "selected_idea_id": selected_idea["idea_id"],
        "stage_3": {"simulation_id": f"ossr_sim_{uuid.uuid4().hex[:8]}", "agent_count": 4, "rounds_completed": 5},
        "stage_5": {
            "draft_id": draft_id, "title": draft["title"],
            "section_count": len(draft["sections"]),
            "total_word_count": sum(s["word_count"] for s in draft["sections"]),
            "citation_count": len(draft["bibliography"]),
            "review_overall": 7.5, "review_decision": "Accept",
        },
    }

    conn.execute(
        "INSERT OR IGNORE INTO ais_pipeline_runs "
        "(run_id, research_idea, status, current_stage, stage_results, config, created_at, updated_at, error) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, selected_idea["title"], "completed", 5,
         json.dumps(stage_results), json.dumps({"sources": ["arxiv", "semantic_scholar", "openalex"]}),
         now, now, None),
    )
    conn.commit()

    return run_id, ideas_data, draft


# ── SVG Map Generator ──────────────────────────────────────────────


def generate_svg_map(conn, animated=False, output_path=None):
    """
    Generate an SVG research landscape map from DB topics and papers.
    Returns SVG string. Writes to file if output_path given.
    """
    topics = conn.execute("SELECT * FROM topics ORDER BY level, name").fetchall()
    if not topics:
        print("No topics in database. Run 'seed' first.")
        return ""

    # Layout: radial for domains, clustered for subfields/threads
    W, H = 1200, 800
    CX, CY = W // 2, H // 2

    # Assign positions
    domains = [t for t in topics if t["level"] == 0]
    subfields = [t for t in topics if t["level"] == 1]
    threads = [t for t in topics if t["level"] == 2]

    positions = {}
    domain_angles = {}

    for i, d in enumerate(domains):
        angle = (2 * math.pi * i) / max(len(domains), 1) - math.pi / 2
        domain_angles[d["topic_id"]] = angle
        r = 200
        x = CX + r * math.cos(angle)
        y = CY + r * math.sin(angle)
        positions[d["topic_id"]] = (x, y)

    for sf in subfields:
        parent_pos = positions.get(sf["parent_id"], (CX, CY))
        base_angle = domain_angles.get(sf["parent_id"], 0)
        # Fan out from parent
        sf_siblings = [s for s in subfields if s["parent_id"] == sf["parent_id"]]
        idx = sf_siblings.index(sf) if sf in sf_siblings else 0
        spread = 0.6
        angle = base_angle + (idx - len(sf_siblings) / 2) * spread
        r = 120
        x = parent_pos[0] + r * math.cos(angle)
        y = parent_pos[1] + r * math.sin(angle)
        positions[sf["topic_id"]] = (x, y)

    for th in threads:
        parent_pos = positions.get(th["parent_id"], (CX, CY))
        th_siblings = [t for t in threads if t["parent_id"] == th["parent_id"]]
        idx = th_siblings.index(th) if th in th_siblings else 0
        angle = random.uniform(0, 2 * math.pi)
        r = 50 + idx * 25
        x = parent_pos[0] + r * math.cos(angle)
        y = parent_pos[1] + r * math.sin(angle)
        positions[th["topic_id"]] = (x, y)

    # Color palette
    DOMAIN_COLORS = ["#1ea88e", "#e8725a", "#5b8def", "#f0a030", "#9b59b6"]
    domain_color_map = {d["topic_id"]: DOMAIN_COLORS[i % len(DOMAIN_COLORS)] for i, d in enumerate(domains)}

    def get_color(topic):
        if topic["level"] == 0:
            return domain_color_map.get(topic["topic_id"], "#1ea88e")
        elif topic["level"] == 1:
            return domain_color_map.get(topic["parent_id"], "#1ea88e")
        else:
            # Find grandparent
            parent = next((s for s in subfields if s["topic_id"] == topic["parent_id"]), None)
            if parent:
                return domain_color_map.get(parent["parent_id"], "#1ea88e")
            return "#888"

    # Build SVG
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
    lines.append('<style>')
    lines.append("""
      .domain { font: bold 14px sans-serif; fill: #fff; }
      .subfield { font: 11px sans-serif; fill: #e0e0e0; }
      .thread { font: 9px sans-serif; fill: #aaa; }
      .edge { stroke-opacity: 0.3; fill: none; }
      .gap-edge { stroke: #ff4444; stroke-dasharray: 6,4; stroke-opacity: 0.5; }
      text { pointer-events: none; }
    """)

    if animated:
        lines.append("""
      @keyframes pulse { 0%, 100% { opacity: 0.6; } 50% { opacity: 1; } }
      @keyframes drift { 0% { transform: translate(0, 0); } 50% { transform: translate(2px, -2px); } 100% { transform: translate(0, 0); } }
      @keyframes glow-travel {
        0% { stroke-dashoffset: 40; }
        100% { stroke-dashoffset: 0; }
      }
      .domain-node { animation: pulse 3s ease-in-out infinite; }
      .thread-node { animation: drift 5s ease-in-out infinite; }
      .synapse { stroke-dasharray: 8,4; animation: glow-travel 2s linear infinite; }
      .particle {
        animation: drift 4s ease-in-out infinite;
        opacity: 0.7;
      }
    """)

    lines.append('</style>')
    lines.append('<defs>')
    lines.append('  <filter id="glow"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    lines.append('  <radialGradient id="neuron-grad"><stop offset="0%" stop-color="#fff" stop-opacity="0.3"/><stop offset="100%" stop-color="#fff" stop-opacity="0"/></radialGradient>')
    lines.append('</defs>')
    lines.append(f'<rect width="{W}" height="{H}" fill="#0a0a1a" rx="12"/>')

    # Title
    lines.append(f'<text x="{W//2}" y="30" text-anchor="middle" fill="#fff" font-size="18" font-family="sans-serif" font-weight="bold">OSSR Research Landscape</text>')

    # Draw edges (hierarchy)
    for sf in subfields:
        if sf["parent_id"] in positions and sf["topic_id"] in positions:
            x1, y1 = positions[sf["parent_id"]]
            x2, y2 = positions[sf["topic_id"]]
            color = get_color(sf)
            cls = "edge synapse" if animated else "edge"
            lines.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{color}" stroke-width="2" class="{cls}"/>')

    for th in threads:
        if th["parent_id"] in positions and th["topic_id"] in positions:
            x1, y1 = positions[th["parent_id"]]
            x2, y2 = positions[th["topic_id"]]
            color = get_color(th)
            lines.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{color}" stroke-width="1" class="edge"/>')

    # Draw gap edges (dashed red)
    for th in threads:
        meta = json.loads(th["metadata"]) if th["metadata"] else {}
        for gap in meta.get("gaps", []):
            if gap.get("gap_score", 0) > 0.5 and th["topic_id"] in positions:
                # Connect to a random other thread
                other = random.choice([t for t in threads if t["topic_id"] != th["topic_id"] and t["topic_id"] in positions])
                x1, y1 = positions[th["topic_id"]]
                x2, y2 = positions[other["topic_id"]]
                lines.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" class="gap-edge"/>')

    # Draw nodes
    for d in domains:
        x, y = positions[d["topic_id"]]
        color = get_color(d)
        r = 30 + d["paper_count"] * 0.3
        cls = "domain-node" if animated else ""
        lines.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="{color}" fill-opacity="0.25" stroke="{color}" stroke-width="2" filter="url(#glow)" class="{cls}"/>')
        lines.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r*0.6:.0f}" fill="url(#neuron-grad)"/>')
        lines.append(f'<text x="{x:.0f}" y="{y+4:.0f}" text-anchor="middle" class="domain">{d["name"]}</text>')

    for sf in subfields:
        x, y = positions[sf["topic_id"]]
        color = get_color(sf)
        r = 12 + sf["paper_count"] * 0.2
        lines.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="{color}" fill-opacity="0.4" stroke="{color}" stroke-width="1"/>')
        lines.append(f'<text x="{x:.0f}" y="{y+r+12:.0f}" text-anchor="middle" class="subfield">{sf["name"][:30]}</text>')

    for th in threads:
        x, y = positions[th["topic_id"]]
        color = get_color(th)
        r = 5 + th["paper_count"] * 0.3
        cls = "thread-node" if animated else ""
        lines.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="{color}" fill-opacity="0.6" class="{cls}"/>')
        lines.append(f'<text x="{x+r+4:.0f}" y="{y+3:.0f}" class="thread">{th["name"][:25]}</text>')

    # Scatter paper particles around threads (animated)
    if animated:
        for th in threads:
            x, y = positions[th["topic_id"]]
            for _ in range(min(th["paper_count"], 5)):
                px = x + random.uniform(-20, 20)
                py = y + random.uniform(-20, 20)
                color = get_color(th)
                delay = random.uniform(0, 4)
                lines.append(f'<circle cx="{px:.0f}" cy="{py:.0f}" r="2" fill="{color}" class="particle" style="animation-delay: {delay:.1f}s"/>')

    # Legend
    ly = H - 80
    lines.append(f'<rect x="20" y="{ly}" width="200" height="70" fill="#111" fill-opacity="0.8" rx="6"/>')
    lines.append(f'<text x="30" y="{ly+18}" fill="#fff" font-size="11" font-weight="bold">Legend</text>')
    lines.append(f'<circle cx="40" cy="{ly+34}" r="8" fill="#1ea88e" fill-opacity="0.4" stroke="#1ea88e"/>')
    lines.append(f'<text x="55" y="{ly+38}" fill="#aaa" font-size="10">Domain / Subfield / Thread</text>')
    lines.append(f'<line x1="30" y1="{ly+52}" x2="50" y2="{ly+52}" stroke="#ff4444" stroke-dasharray="4,3"/>')
    lines.append(f'<text x="55" y="{ly+56}" fill="#aaa" font-size="10">Research Gap</text>')

    # Stats overlay
    total_papers = conn.execute("SELECT COUNT(*) as c FROM papers").fetchone()["c"]
    total_topics = len(topics)
    lines.append(f'<text x="{W-20}" y="30" text-anchor="end" fill="#666" font-size="11" font-family="monospace">{total_papers} papers | {total_topics} topics</text>')

    lines.append('</svg>')

    svg = "\n".join(lines)

    if output_path:
        Path(output_path).write_text(svg)
        print(f"SVG written to {output_path}")

    return svg


# ── Commands ───────────────────────────────────────────────────────


def cmd_seed(args):
    init_db()
    conn = get_connection()
    topic_filter = args.topic

    print("Seeding demo data...")
    papers = seed_papers(conn, topic_filter)
    print(f"  Papers: {len(papers)}")

    topics = seed_topics(conn, topic_filter)
    print(f"  Topics: {len(topics)}")

    agents = seed_agents(conn)
    print(f"  Agents: {len(agents)}")

    run_id, ideas, draft = seed_ais_pipeline(conn)
    print(f"  AiS run: {run_id}")
    print(f"  Ideas: {len(ideas)}")
    print(f"  Draft: {draft['title']}")

    # Generate SVG map
    svg_path = Path(__file__).parent / "data" / "research_map.svg"
    generate_svg_map(conn, animated=True, output_path=str(svg_path))

    print(f"\nDone. Open http://localhost:3001 to view the dashboard.")
    print(f"SVG map: {svg_path}")


def cmd_svg(args):
    init_db()
    conn = get_connection()
    output = args.output or str(Path(__file__).parent / "data" / "research_map.svg")
    svg = generate_svg_map(conn, animated=args.animated, output_path=output)
    if svg:
        print(f"SVG generated ({len(svg)} bytes)")


def cmd_history(args):
    init_db()
    conn = get_connection()

    runs = conn.execute("SELECT * FROM ais_pipeline_runs ORDER BY created_at DESC").fetchall()
    if not runs:
        print("No pipeline runs found. Run 'seed' first.")
        return

    print(f"{'Run ID':<28} {'Status':<18} {'Stage':<6} {'Idea':<50}")
    print("-" * 105)
    for r in runs:
        print(f"{r['run_id']:<28} {r['status']:<18} {r['current_stage']:<6} {r['research_idea'][:50]}")


def cmd_clear(args):
    init_db()
    conn = get_connection()
    for table in ["papers", "topics", "paper_topics", "researcher_profiles",
                   "research_ideas", "paper_drafts", "ais_pipeline_runs",
                   "experiment_specs", "experiment_results", "autoresearch_runs"]:
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    print("Demo data cleared.")


# ── Main ───────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="OSSR Demo CLI")
    sub = parser.add_subparsers(dest="command")

    p_seed = sub.add_parser("seed", help="Seed demo data")
    p_seed.add_argument("--topic", help="Filter to a specific domain (e.g., 'EIT')")

    p_svg = sub.add_parser("svg", help="Generate SVG research map")
    p_svg.add_argument("--animated", action="store_true", help="Include CSS animations")
    p_svg.add_argument("--output", "-o", help="Output file path")

    sub.add_parser("history", help="List pipeline runs")
    sub.add_parser("clear", help="Clear demo data")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    {"seed": cmd_seed, "svg": cmd_svg, "history": cmd_history, "clear": cmd_clear}[args.command](args)


if __name__ == "__main__":
    main()
