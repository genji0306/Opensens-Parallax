# Data source adapters for academic paper ingestion

from .acm import ACMSource
from .springer import SpringerSource
from .core_ac import CORESource
from .crossref import CrossRefSource
from .pubmed import PubMedSource
from .doaj import DOAJSource
from .europe_pmc import EuropePMCSource

__all__ = [
    "ACMSource",
    "SpringerSource",
    "CORESource",
    "CrossRefSource",
    "PubMedSource",
    "DOAJSource",
    "EuropePMCSource",
]
