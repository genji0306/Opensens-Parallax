from .research_data_routes import research_data_bp
from .research_sim_routes import research_sim_bp
from .research_report_routes import research_report_bp

# All sub-blueprints registered under /api/research/
research_blueprints = [research_data_bp, research_sim_bp, research_report_bp]

__all__ = ["research_blueprints", "research_data_bp", "research_sim_bp", "research_report_bp"]
