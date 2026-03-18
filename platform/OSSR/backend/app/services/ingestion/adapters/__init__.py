# Data source adapters for academic paper ingestion

from .acm import ACMSource
from .springer import SpringerSource

__all__ = ["ACMSource", "SpringerSource"]
