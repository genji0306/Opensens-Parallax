# Re-export shim — real module at services/reports/report_service.py
from .reports.report_service import *  # noqa: F401,F403
from .reports.report_service import ResearchReportGenerator  # noqa: F811
