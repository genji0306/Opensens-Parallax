from pathlib import Path


def test_parse_text_builds_parsed_document_v2(tmp_path):
    from app.services.ais.paper_parser import PaperParser

    path = tmp_path / "paper.md"
    path.write_text(
        "# Battery Paper\n\n## Abstract\nA short abstract.\n\n## Methods\nWe test discharge curves.\n\n## References\nDoe et al. 10.1000/testdoi",
        encoding="utf-8",
    )

    parsed = PaperParser().parse(str(path))

    assert parsed.title == "Battery Paper"
    assert parsed.metadata["document_schema"] == "ParsedDocumentV2"
    assert parsed.metadata["parser_engine"] == "legacy_text"
    assert parsed.metadata["parsed_document_v2"]["source_type"] == "md"
    assert parsed.metadata["parsed_document_v2"]["quality_scores"]["overall"] > 0


def test_parse_pdf_uses_pdf_route(monkeypatch, tmp_path):
    from app.services.ais.paper_parser import PaperParser, ParsedDocumentV2
    from app.models.ais_models import PaperSection

    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF-1.4 stub")

    def fake_parse_pdf(self, file_path: Path):
        return ParsedDocumentV2(
            document_id="doc_test",
            source_path=str(file_path),
            source_filename=file_path.name,
            source_type="pdf",
            mime_type="application/pdf",
            parser_engine="opendataloader_pdf",
            parser_mode="layout_aware",
            ocr_used=False,
            language="en",
            title="Parsed PDF",
            sections=[PaperSection(name="abstract", content="Abstract text", word_count=2)],
            citations=[],
            markdown="# Parsed PDF",
            plain_text="Abstract text",
            quality_scores={"overall": 0.9},
        )

    monkeypatch.setattr(PaperParser, "_parse_pdf", fake_parse_pdf)
    parsed = PaperParser().parse(str(path))

    assert parsed.title == "Parsed PDF"
    assert parsed.metadata["parser_engine"] == "opendataloader_pdf"
    assert parsed.metadata["parsed_document_v2"]["source_type"] == "pdf"


def test_parse_doc_converts_before_docx_parse(monkeypatch, tmp_path):
    from app.services.ais.paper_parser import PaperParser, ParsedDocumentV2
    from app.models.ais_models import PaperSection

    doc_path = tmp_path / "legacy.doc"
    doc_path.write_bytes(b"legacy-doc")
    converted = tmp_path / "legacy.converted.docx"
    converted.write_bytes(b"docx")

    def fake_convert(self, file_path: Path):
        return converted

    def fake_parse_docx(self, file_path: Path):
        return ParsedDocumentV2(
            document_id="doc_docx",
            source_path=str(file_path),
            source_filename=file_path.name,
            source_type="docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            parser_engine="python-docx",
            parser_mode="native",
            ocr_used=False,
            language="en",
            title="Converted DOC",
            sections=[PaperSection(name="body", content="Body text", word_count=2)],
            citations=[],
            markdown="# Converted DOC",
            plain_text="Body text",
            quality_scores={"overall": 0.7},
        )

    monkeypatch.setattr(PaperParser, "_convert_doc_to_docx", fake_convert)
    monkeypatch.setattr(PaperParser, "_parse_docx_document", fake_parse_docx)
    parsed = PaperParser().parse(str(doc_path))

    assert parsed.title == "Converted DOC"
    assert parsed.metadata["parser_mode"] == "converted"
    assert "Legacy .doc converted before parsing." in parsed.metadata["parse_warnings"]
