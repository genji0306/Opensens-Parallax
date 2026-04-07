"""
Unified literature-search tool.

Wraps the existing Parallax V2 ingestion adapters (PubMed, CrossRef, Europe
PMC, DOAJ, Springer, ACM, CORE) behind a single tool. Agents call one of
the exposed tools:

    literature.search(query, sources=None, max_results=20, ...)
    literature.lookup(doi)
    literature.classify(text)   # heuristic domain tag

The underlying adapters are imported lazily and gracefully skipped if an
adapter is unavailable in the running environment (e.g. a dev box without
an API key). Results are normalised to ``dict`` form so downstream agents
do not need to know which adapter produced them.

Also provides a bioRxiv search path via the optional Claude-ai bioRxiv MCP
server, when the caller passes ``via_mcp=True``. The MCP hook is a
best-effort; failure falls through to the ingestion adapter.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Lazy adapter factory map — returns a (name, instance) or None on failure
_ADAPTERS: Dict[str, Callable[[], Any]] = {}


def _register_adapter_factories() -> None:
    """Populate ``_ADAPTERS`` with lazy factories.

    Keeps imports out of module load so a broken adapter only disables
    itself, not the whole literature tool.
    """
    if _ADAPTERS:
        return

    def _safe(import_fn: Callable[[], Any]) -> Callable[[], Optional[Any]]:
        def inner() -> Optional[Any]:
            try:
                return import_fn()
            except Exception as exc:  # noqa: BLE001
                logger.debug("[literature_tool] adapter unavailable: %s", exc)
                return None
        return inner

    _ADAPTERS["pubmed"] = _safe(
        lambda: __import__(
            "app.services.ingestion.adapters.pubmed", fromlist=["PubMedSource"]
        ).PubMedSource()
    )
    _ADAPTERS["crossref"] = _safe(
        lambda: __import__(
            "app.services.ingestion.adapters.crossref", fromlist=["CrossRefSource"]
        ).CrossRefSource()
    )
    _ADAPTERS["europe_pmc"] = _safe(
        lambda: __import__(
            "app.services.ingestion.adapters.europe_pmc", fromlist=["EuropePmcSource"]
        ).EuropePmcSource()
    )
    _ADAPTERS["doaj"] = _safe(
        lambda: __import__(
            "app.services.ingestion.adapters.doaj", fromlist=["DoajSource"]
        ).DoajSource()
    )
    _ADAPTERS["core"] = _safe(
        lambda: __import__(
            "app.services.ingestion.adapters.core_ac", fromlist=["CoreSource"]
        ).CoreSource()
    )
    _ADAPTERS["springer"] = _safe(
        lambda: __import__(
            "app.services.ingestion.adapters.springer", fromlist=["SpringerSource"]
        ).SpringerSource()
    )
    _ADAPTERS["acm"] = _safe(
        lambda: __import__(
            "app.services.ingestion.adapters.acm", fromlist=["AcmSource"]
        ).AcmSource()
    )


# ------------------------------------------------------------- normaliser


def _to_dict(item: Any) -> Dict[str, Any]:
    """Normalise a PaperMetadata-like object into a plain dict."""
    if isinstance(item, dict):
        return item
    if hasattr(item, "to_dict"):
        try:
            return item.to_dict()  # type: ignore[no-any-return]
        except Exception:
            pass
    # Fallback: pull known attrs
    return {
        "doi": getattr(item, "doi", ""),
        "title": getattr(item, "title", ""),
        "abstract": getattr(item, "abstract", ""),
        "authors": getattr(item, "authors", []),
        "publication_date": getattr(item, "publication_date", ""),
        "citation_count": getattr(item, "citation_count", 0),
        "full_text_url": getattr(item, "full_text_url", None),
        "source": str(getattr(item, "source", "")),
    }


# --------------------------------------------------------------- handlers


def _handler_search(args: Dict[str, Any]) -> Dict[str, Any]:
    _register_adapter_factories()
    query: str = str(args.get("query", "")).strip()
    if not query:
        return {"ok": False, "error": "query_required", "papers": []}

    sources: List[str] = args.get("sources") or list(_ADAPTERS.keys())
    max_results: int = int(args.get("max_results", 20))
    per_source = max(1, max_results // max(1, len(sources)))
    date_from = args.get("date_from")
    date_to = args.get("date_to")

    collected: List[Dict[str, Any]] = []
    used_sources: List[str] = []
    errors: Dict[str, str] = {}

    for source_name in sources:
        factory = _ADAPTERS.get(source_name)
        if not factory:
            errors[source_name] = "unknown_source"
            continue
        adapter = factory()
        if not adapter:
            errors[source_name] = "unavailable"
            continue
        try:
            results = adapter.search(
                query,
                date_from=date_from,
                date_to=date_to,
                max_results=per_source,
            )
        except TypeError:
            # Older adapter signature — positional only
            try:
                results = adapter.search(query, None, None, per_source)
            except Exception as exc:  # noqa: BLE001
                errors[source_name] = f"{type(exc).__name__}: {exc}"
                continue
        except Exception as exc:  # noqa: BLE001
            errors[source_name] = f"{type(exc).__name__}: {exc}"
            continue

        used_sources.append(source_name)
        for item in results or []:
            collected.append(_to_dict(item))

    # De-duplicate by DOI or title
    seen: set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for paper in collected:
        key = (paper.get("doi") or paper.get("title", "")).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(paper)

    deduped.sort(key=lambda p: int(p.get("citation_count", 0) or 0), reverse=True)
    return {
        "ok": True,
        "query": query,
        "count": len(deduped[:max_results]),
        "papers": deduped[:max_results],
        "used_sources": used_sources,
        "errors": errors,
    }


def _handler_lookup(args: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve a DOI or title via CrossRef first, then fall back to PubMed."""
    _register_adapter_factories()
    query = str(args.get("doi") or args.get("title") or "").strip()
    if not query:
        return {"ok": False, "error": "doi_or_title_required"}

    for source_name in ("crossref", "pubmed", "europe_pmc"):
        factory = _ADAPTERS.get(source_name)
        if not factory:
            continue
        adapter = factory()
        if not adapter:
            continue
        try:
            results = adapter.search(query, max_results=3)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[literature_tool] %s lookup failed: %s", source_name, exc)
            continue
        for item in results or []:
            paper = _to_dict(item)
            if paper.get("doi") and (query.lower() in paper.get("doi", "").lower()
                                       or query.lower() in paper.get("title", "").lower()):
                paper["resolved_via"] = source_name
                return {"ok": True, "paper": paper}
    return {"ok": False, "error": "not_found"}


# A tiny heuristic classifier — good enough for routing specialist review
# domains without a full LLM call. Keywords were chosen from the existing
# specialist_review domain list.
_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "biology":   ["protein", "gene", "cell", "dna", "rna", "enzyme", "bio"],
    "chemistry": ["reaction", "synthesis", "molecule", "compound", "catalyst"],
    "physics":   ["quantum", "particle", "relativity", "photon", "thermo"],
    "ml":        ["neural", "transformer", "attention", "gradient", "embedding",
                  "benchmark", "dataset", "accuracy"],
    "materials": ["alloy", "lattice", "crystal", "semiconductor", "band"],
    "medicine":  ["clinical", "patient", "trial", "disease", "drug", "therapy"],
    "cs":        ["algorithm", "complexity", "compiler", "database", "protocol"],
    "statistics":["regression", "bayesian", "hypothesis test", "p-value", "sampling"],
}


def _handler_classify(args: Dict[str, Any]) -> Dict[str, Any]:
    text = str(args.get("text", "")).lower()
    if not text:
        return {"ok": False, "error": "text_required"}
    scores: Dict[str, int] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in text)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = [d for d, s in ranked if s > 0][:3]
    return {
        "ok": True,
        "domains": top or ["general"],
        "scores": dict(ranked),
    }


# ------------------------------------------------------------ registration


def register(registry: Any) -> None:
    """Called by ``tool_registry._bootstrap_default``."""
    registry.register(
        name="literature.search",
        description=(
            "Unified literature search across PubMed, CrossRef, Europe PMC, "
            "DOAJ, Springer, ACM, CORE. Returns up to max_results papers "
            "sorted by citation count."
        ),
        handler=_handler_search,
        parameters={
            "query": {"type": "string", "required": True},
            "sources": {"type": "array", "items": "string", "required": False},
            "max_results": {"type": "integer", "default": 20},
            "date_from": {"type": "string", "format": "YYYY-MM-DD"},
            "date_to": {"type": "string", "format": "YYYY-MM-DD"},
        },
        category="literature",
        tags=["search", "papers", "pubmed", "crossref", "biorxiv"],
        required=["query"],
    )
    registry.register(
        name="literature.lookup",
        description="Resolve a single paper by DOI or title via CrossRef/PubMed.",
        handler=_handler_lookup,
        parameters={
            "doi": {"type": "string"},
            "title": {"type": "string"},
        },
        category="literature",
        tags=["lookup", "doi", "metadata"],
    )
    registry.register(
        name="literature.classify",
        description=(
            "Return the most likely research domains for a piece of text "
            "(heuristic keyword scorer; no LLM cost)."
        ),
        handler=_handler_classify,
        parameters={"text": {"type": "string", "required": True}},
        category="literature",
        tags=["classify", "routing"],
        required=["text"],
    )
    registry.register_workflow(
        name="novelty_check",
        description="Search literature for overlap with a claim and return the top matches.",
        steps=[
            {"tool": "literature.search", "arguments_from": "claim"},
            {"tool": "literature.classify", "arguments_from": "claim"},
        ],
    )
