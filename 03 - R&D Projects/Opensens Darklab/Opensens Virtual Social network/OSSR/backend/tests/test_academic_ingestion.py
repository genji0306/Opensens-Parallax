from app.models.research import AcademicSource
from app.services import academic_ingestion as ingestion_module


class FakeAdapter:
    def __init__(self, results_by_call=None, error=None):
        self.results_by_call = results_by_call or [[]]
        self.error = error
        self.calls = []

    def search(self, query, date_from=None, date_to=None, max_results=50):
        self.calls.append(
            {
                "query": query,
                "date_from": date_from,
                "date_to": date_to,
                "max_results": max_results,
            }
        )
        if self.error:
            raise self.error
        index = min(len(self.calls) - 1, len(self.results_by_call) - 1)
        return self.results_by_call[index]

    def get_paper(self, identifier):
        return None

    def get_citations(self, doi):
        return []


def make_metadata(doi, source=AcademicSource.ARXIV, publication_date="2026-03-10"):
    return ingestion_module.PaperMetadata(
        doi=doi,
        title=f"Title for {doi}",
        abstract="Abstract",
        authors=[{"name": "Author"}],
        publication_date=publication_date,
        source=source,
        keywords=["ml"],
    )


def test_fetch_uses_cached_results(monkeypatch, isolated_db):
    adapter = FakeAdapter(results_by_call=[[make_metadata("10.1000/cache-hit")]])
    monkeypatch.setattr(ingestion_module, "get_source", lambda source: adapter)

    pipeline = ingestion_module.IngestionPipeline()

    first = pipeline._fetch(
        query="graph rag",
        sources=[AcademicSource.ARXIV.value],
        date_from="2026-01-01",
        date_to="2026-03-17",
        max_results=10,
    )
    second = pipeline._fetch(
        query="graph rag",
        sources=[AcademicSource.ARXIV.value],
        date_from="2026-01-01",
        date_to="2026-03-17",
        max_results=10,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert adapter.calls == [
        {
            "query": "graph rag",
            "date_from": "2026-01-01",
            "date_to": "2026-03-17",
            "max_results": 10,
        }
    ]


def test_fetch_uses_high_water_mark_when_date_from_omitted(monkeypatch, isolated_db):
    adapter = FakeAdapter(
        results_by_call=[
            [make_metadata("10.1000/first", publication_date="2026-03-10")],
            [],
        ]
    )
    monkeypatch.setattr(ingestion_module, "get_source", lambda source: adapter)

    pipeline = ingestion_module.IngestionPipeline()

    pipeline._fetch(
        query="agent societies",
        sources=[AcademicSource.ARXIV.value],
        date_from=None,
        date_to="2026-03-17",
        max_results=5,
    )
    pipeline._fetch(
        query="agent societies",
        sources=[AcademicSource.ARXIV.value],
        date_from=None,
        date_to="2026-03-17",
        max_results=5,
    )

    assert adapter.calls[0]["date_from"] is None
    assert adapter.calls[1]["date_from"] == "2026-03-10"
    assert pipeline.store.get_high_water_mark(
        AcademicSource.ARXIV.value,
        pipeline._normalize_query("agent societies"),
    ) == "2026-03-10"


def test_fetch_keeps_partial_results_when_one_source_fails(monkeypatch, isolated_db):
    adapters = {
        AcademicSource.ARXIV: FakeAdapter(results_by_call=[[make_metadata("10.1000/good")]]),
        AcademicSource.OPENALEX: FakeAdapter(error=RuntimeError("source unavailable")),
    }
    monkeypatch.setattr(ingestion_module, "get_source", lambda source: adapters[source])

    pipeline = ingestion_module.IngestionPipeline()
    results = pipeline._fetch(
        query="multi agent research",
        sources=[AcademicSource.ARXIV.value, AcademicSource.OPENALEX.value],
        date_from="2026-01-01",
        date_to="2026-03-17",
        max_results=8,
    )

    assert [paper.doi for paper in results] == ["10.1000/good"]
    assert len(adapters[AcademicSource.ARXIV].calls) == 1
    assert len(adapters[AcademicSource.OPENALEX].calls) == 1
