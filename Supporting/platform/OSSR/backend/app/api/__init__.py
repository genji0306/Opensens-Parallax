from .research_data_routes import research_data_bp
from .research_sim_routes import research_sim_bp
from .research_report_routes import research_report_bp
from .ais_routes import ais_bp
from .history_routes import history_bp
from .paper_rehab_routes import paper_rehab_bp
from .grants_routes import grants_bp

# All sub-blueprints registered under /api/research/
research_blueprints = [
    research_data_bp,
    research_sim_bp,
    research_report_bp,
    ais_bp,
    history_bp,
    paper_rehab_bp,
    grants_bp,
]

__all__ = [
    "research_blueprints",
    "research_data_bp",
    "research_sim_bp",
    "research_report_bp",
    "ais_bp",
    "history_bp",
    "paper_rehab_bp",
    "grants_bp",
]
