"""
Agent AiS — Paper Parser
Parses uploaded .docx files into structured ParsedPaper objects for the
Paper Rehabilitation pipeline (cli_test_paper_rehab.py).

Supports: .docx (python-docx), .txt, .md (plain text).
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...models.ais_models import PaperSection

logger = logging.getLogger(__name__)

# Vietnamese diacritical characters (unique to Vietnamese)
_VI_CHARS = set("àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợ"
                "ùúủũụưứừửữựỳýỷỹỵđ"
                "ÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢ"
                "ÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ")

# Common academic section headings (case-insensitive matching)
_SECTION_ALIASES = {
    "abstract": "abstract",
    "tóm tắt": "abstract",
    "introduction": "introduction",
    "giới thiệu": "introduction",
    "mở đầu": "introduction",
    "đặt vấn đề": "introduction",
    "background": "background",
    "cơ sở lý thuyết": "background",
    "tổng quan": "background",
    "literature review": "related_work",
    "related work": "related_work",
    "tài liệu tham khảo": "references",
    "methodology": "methodology",
    "phương pháp": "methodology",
    "phương pháp nghiên cứu": "methodology",
    "results": "results",
    "kết quả": "results",
    "kết quả và thảo luận": "results",
    "discussion": "discussion",
    "thảo luận": "discussion",
    "bàn luận": "discussion",
    "conclusion": "conclusion",
    "kết luận": "conclusion",
    "references": "references",
    "tài liệu": "references",
    "acknowledgments": "acknowledgments",
    "acknowledgements": "acknowledgments",
}

# DOI regex
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;}\]]+")

# Author-year citation pattern: (Author, Year) or [Author, Year] or Author (Year)
_CITE_RE = re.compile(r"\(([A-Z][a-z]+(?:\s+(?:et\s+al\.?|&|and)\s+[A-Z][a-z]+)?),?\s*(\d{4})\)")


@dataclass
class ParsedPaper:
    """Structured representation of an uploaded paper draft."""
    source_path: str
    title: str
    language: str                           # "vi", "en", "mixed"
    detected_field: str                     # e.g. "mechanical engineering"
    sections: List[PaperSection] = field(default_factory=list)
    raw_references: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    full_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "title": self.title,
            "language": self.language,
            "detected_field": self.detected_field,
            "sections": [s.to_dict() for s in self.sections],
            "raw_references": self.raw_references,
            "metadata": self.metadata,
            "word_count": self.metadata.get("word_count", 0),
            "section_count": len(self.sections),
        }


class PaperParser:
    """Parses .docx / .txt / .md files into ParsedPaper objects."""

    # ── Field detection keywords ────────────────────────────────────
    FIELD_KEYWORDS: Dict[str, List[str]] = {
        "mechanical engineering": [
            "stress", "strain", "deformation", "tensile", "compressive",
            "elastic", "modulus", "fatigue", "fracture", "FEM", "FEA",
            "finite element", "ứng suất", "biến dạng", "cơ học",
        ],
        "materials science": [
            "alloy", "composite", "microstructure", "crystalline",
            "nanostructure", "polymer", "ceramic", "coating",
            "vật liệu", "hợp kim", "vi cấu trúc",
        ],
        "thermal engineering": [
            "temperature", "heat transfer", "thermal conductivity",
            "convection", "radiation", "cooling", "heating",
            "nhiệt độ", "truyền nhiệt", "dẫn nhiệt", "tản nhiệt",
        ],
        "electrical engineering": [
            "impedance", "circuit", "voltage", "current", "sensor",
            "electrode", "capacitance", "resistance",
            "trở kháng", "điện trở", "cảm biến",
        ],
        "civil engineering": [
            "concrete", "reinforcement", "beam", "column", "foundation",
            "structural", "load", "bê tông", "cốt thép", "kết cấu",
        ],
        "physics": [
            "quantum", "relativity", "photon", "electron", "wave",
            "particle", "magnetic", "electric field",
        ],
        "chemistry": [
            "reaction", "catalyst", "molecular", "compound", "synthesis",
            "oxidation", "reduction", "phản ứng", "xúc tác",
        ],
        "computer science": [
            "algorithm", "machine learning", "neural network", "deep learning",
            "classification", "regression", "optimization",
            "thuật toán", "học máy",
        ],
    }

    def parse(self, file_path: str) -> ParsedPaper:
        """Parse a document file into a structured ParsedPaper."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Paper not found: {file_path}")

        ext = path.suffix.lower()
        if ext == ".docx":
            sections, full_text, meta = self._parse_docx(path)
        elif ext in (".txt", ".md", ".markdown"):
            sections, full_text, meta = self._parse_text(path)
        else:
            raise ValueError(f"Unsupported file type: {ext}. Supported: .docx, .txt, .md")

        title = meta.get("title", path.stem)
        language = self._detect_language(full_text)
        detected_field = self._detect_field(full_text)
        raw_references = self._extract_references_from_text(full_text, sections)

        meta.update({
            "word_count": len(full_text.split()),
            "section_count": len(sections),
            "reference_count": len(raw_references),
            "file_extension": ext,
            "file_size_kb": round(path.stat().st_size / 1024, 1),
        })

        return ParsedPaper(
            source_path=str(path.resolve()),
            title=title,
            language=language,
            detected_field=detected_field,
            sections=sections,
            raw_references=raw_references,
            metadata=meta,
            full_text=full_text,
        )

    # ── .docx parsing ───────────────────────────────────────────────

    def _parse_docx(self, path: Path):
        """Parse .docx using python-docx. Groups paragraphs by heading styles.
        Falls back to heuristic section detection when no headings are styled."""
        from docx import Document

        doc = Document(str(path))

        # First pass: check if document uses heading styles
        has_heading_styles = any(
            "heading" in (p.style.name or "").lower()
            for p in doc.paragraphs if p.text.strip()
        )

        title = ""
        sections: List[PaperSection] = []
        current_heading = "preamble"
        current_content: List[str] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            style_name = (para.style.name or "").lower()
            is_heading = "heading" in style_name

            # Heuristic heading detection when no styled headings exist:
            # bold short paragraphs, ALL CAPS lines, or known section keywords
            if not has_heading_styles and not is_heading:
                is_bold = all(run.bold for run in para.runs if run.text.strip()) and para.runs
                is_short = len(text.split()) <= 8
                is_caps = text.isupper() and len(text) > 3
                matches_keyword = text.lower().strip(":. ") in _SECTION_ALIASES
                if (is_bold and is_short) or is_caps or matches_keyword:
                    is_heading = True

            if is_heading:
                if current_content:
                    section_name = self._normalize_section_name(current_heading)
                    content_text = "\n".join(current_content)
                    sections.append(PaperSection(
                        name=section_name,
                        content=content_text,
                        word_count=len(content_text.split()),
                    ))
                    current_content = []

                current_heading = text
                if not title:
                    title = text
            else:
                current_content.append(text)

        # Save last section
        if current_content:
            section_name = self._normalize_section_name(current_heading)
            content_text = "\n".join(current_content)
            sections.append(PaperSection(
                name=section_name,
                content=content_text,
                word_count=len(content_text.split()),
            ))

        # If still just one preamble section, infer title from first line
        if len(sections) <= 1 and not title:
            full = "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
            lines = full.split("\n")
            title = lines[0][:120] if lines else path.stem
            if len(sections) == 0:
                sections = [PaperSection(
                    name="body",
                    content=full,
                    word_count=len(full.split()),
                )]

        # Use filename as title fallback
        if not title:
            title = path.stem

        full_text = "\n\n".join(s.content for s in sections)
        meta = {"title": title, "parser": "python-docx"}
        return sections, full_text, meta

    # ── Plain text parsing ──────────────────────────────────────────

    def _parse_text(self, path: Path):
        """Parse .txt/.md files. Detect sections from Markdown headings or ALL-CAPS lines."""
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.split("\n")

        title = ""
        sections: List[PaperSection] = []
        current_heading = "body"
        current_content: List[str] = []

        for line in lines:
            stripped = line.strip()
            is_md_heading = stripped.startswith("#")
            is_caps_heading = (stripped.isupper() and 3 < len(stripped) < 80)

            if is_md_heading or is_caps_heading:
                # Save previous section
                if current_content:
                    section_name = self._normalize_section_name(current_heading)
                    content_text = "\n".join(current_content)
                    sections.append(PaperSection(
                        name=section_name,
                        content=content_text,
                        word_count=len(content_text.split()),
                    ))
                    current_content = []

                heading_text = stripped.lstrip("#").strip()
                current_heading = heading_text
                if not title:
                    title = heading_text
            else:
                if stripped:
                    current_content.append(stripped)

        # Save last section
        if current_content:
            section_name = self._normalize_section_name(current_heading)
            content_text = "\n".join(current_content)
            sections.append(PaperSection(
                name=section_name,
                content=content_text,
                word_count=len(content_text.split()),
            ))

        if not sections:
            sections = [PaperSection(name="body", content=text, word_count=len(text.split()))]
            title = path.stem

        full_text = "\n\n".join(s.content for s in sections)
        meta = {"title": title or path.stem, "parser": "text"}
        return sections, full_text, meta

    # ── Helpers ─────────────────────────────────────────────────────

    def _normalize_section_name(self, heading: str) -> str:
        """Map a heading string to a canonical section name."""
        key = heading.lower().strip()
        if key in _SECTION_ALIASES:
            return _SECTION_ALIASES[key]
        # Partial match
        for alias, canon in _SECTION_ALIASES.items():
            if alias in key or key in alias:
                return canon
        # Fallback: slugify
        slug = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
        return slug or "unnamed"

    def _detect_language(self, text: str) -> str:
        """Detect whether text is Vietnamese, English, or mixed."""
        if not text:
            return "en"
        sample = text[:5000]
        vi_count = sum(1 for ch in sample if ch in _VI_CHARS)
        ratio = vi_count / max(len(sample), 1)
        if ratio > 0.02:
            # Check if there's also significant English content
            ascii_words = len(re.findall(r"\b[a-zA-Z]{3,}\b", sample))
            total_words = len(sample.split())
            en_ratio = ascii_words / max(total_words, 1)
            if en_ratio > 0.5:
                return "mixed"
            return "vi"
        return "en"

    def _detect_field(self, text: str) -> str:
        """Detect research field from keyword frequency in text."""
        text_lower = text.lower()
        scores: Dict[str, int] = {}
        for field_name, keywords in self.FIELD_KEYWORDS.items():
            score = sum(text_lower.count(kw.lower()) for kw in keywords)
            if score > 0:
                scores[field_name] = score

        if not scores:
            return "general science"
        return max(scores, key=scores.get)

    def _extract_references_from_text(
        self, full_text: str, sections: List[PaperSection]
    ) -> List[Dict[str, Any]]:
        """Extract references from text: DOIs and author-year citations."""
        refs: List[Dict[str, Any]] = []
        seen_dois = set()

        # Extract DOIs
        for match in _DOI_RE.finditer(full_text):
            doi = match.group().rstrip(".")
            if doi not in seen_dois:
                seen_dois.add(doi)
                refs.append({"type": "doi", "doi": doi, "raw": doi})

        # Find the references/bibliography section
        ref_section = None
        for s in sections:
            if s.name in ("references", "tài_liệu", "tài_liệu_tham_khảo", "bibliography"):
                ref_section = s
                break

        if ref_section:
            # Split references section into individual entries
            # Common patterns: numbered [1], [2] or 1. 2. or bullet points
            lines = ref_section.content.split("\n")
            for line in lines:
                line = line.strip()
                if not line or len(line) < 10:
                    continue
                # Strip leading number/bracket
                cleaned = re.sub(r"^\[?\d+\]?\.?\s*", "", line).strip()
                if cleaned:
                    # Extract DOI from this reference line
                    doi_match = _DOI_RE.search(cleaned)
                    doi = doi_match.group().rstrip(".") if doi_match else ""
                    if doi and doi in seen_dois:
                        continue
                    if doi:
                        seen_dois.add(doi)
                    refs.append({
                        "type": "reference_entry",
                        "doi": doi,
                        "raw": cleaned[:300],
                        "title": self._guess_title_from_ref(cleaned),
                    })

        # Extract author-year citations from body text
        for match in _CITE_RE.finditer(full_text):
            author, year = match.group(1), match.group(2)
            refs.append({
                "type": "author_year",
                "doi": "",
                "raw": f"{author}, {year}",
                "author": author,
                "year": int(year),
            })

        return refs

    @staticmethod
    def _guess_title_from_ref(ref_line: str) -> str:
        """Attempt to extract a paper title from a reference line.
        Heuristic: titles are often in quotes or after the author list (before the journal)."""
        # Quoted title
        quoted = re.search(r'["""](.+?)["""]', ref_line)
        if quoted:
            return quoted.group(1)
        # After period following authors, before next period
        parts = ref_line.split(".")
        if len(parts) >= 3:
            # Second segment is often the title
            candidate = parts[1].strip()
            if 10 < len(candidate) < 200:
                return candidate
        return ""
