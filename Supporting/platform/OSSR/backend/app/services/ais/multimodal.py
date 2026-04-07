"""
Multimodal Capability Layer
Vision-capable API integration for processing figures, graphs, and tables in papers.

Architecture:
- Supports Anthropic Claude (vision), OpenAI GPT-4o (vision), and future providers
- Falls back gracefully to text-only mode when vision is unavailable
- Extracts captions, axes, legends from figures
- Links figures to claims in the paper

Usage:
    mm = MultimodalService()
    if mm.is_vision_available():
        result = mm.analyze_figure(image_bytes, context="EIS Nyquist plot")
    else:
        result = mm.text_fallback(caption="Figure 3: Nyquist plot of...")
"""

import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from opensens_common.config import Config

logger = logging.getLogger(__name__)


@dataclass
class FigureAnalysis:
    """Result of analyzing a single figure/graph/table."""
    figure_id: str = ""
    figure_type: str = ""  # "plot", "micrograph", "table", "diagram", "photo"
    caption: str = ""
    description: str = ""
    axes: Dict[str, str] = field(default_factory=dict)  # {"x": "Frequency (Hz)", "y": "Z'' (Ohm)"}
    legends: List[str] = field(default_factory=list)
    data_points_summary: str = ""
    key_observations: List[str] = field(default_factory=list)
    linked_claims: List[str] = field(default_factory=list)
    quality_issues: List[str] = field(default_factory=list)
    model_used: str = ""
    mode: str = "vision"  # "vision" or "text_fallback"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "figure_id": self.figure_id,
            "figure_type": self.figure_type,
            "caption": self.caption,
            "description": self.description,
            "axes": self.axes,
            "legends": self.legends,
            "data_points_summary": self.data_points_summary,
            "key_observations": self.key_observations,
            "linked_claims": self.linked_claims,
            "quality_issues": self.quality_issues,
            "model_used": self.model_used,
            "mode": self.mode,
        }


@dataclass
class DocumentFigures:
    """All figures extracted from a document."""
    figures: List[FigureAnalysis] = field(default_factory=list)
    total_figures: int = 0
    vision_analyzed: int = 0
    text_fallback_count: int = 0
    extraction_method: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "figures": [f.to_dict() for f in self.figures],
            "total_figures": self.total_figures,
            "vision_analyzed": self.vision_analyzed,
            "text_fallback_count": self.text_fallback_count,
            "extraction_method": self.extraction_method,
        }


# Vision-capable model identifiers
VISION_MODELS = {
    "anthropic": [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-haiku-4-5-20251001",
    ],
    "openai": [
        "gpt-4o", "gpt-4o-mini", "gpt-4-turbo",
    ],
    "gemini": [
        "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash",
    ],
}


class MultimodalService:
    """
    Multimodal processing service for paper figures and visual content.

    Supports:
    - Direct image analysis via vision-capable LLMs
    - Caption/text fallback when vision is unavailable
    - Figure extraction from PDF/DOCX documents
    - Linking figures to paper claims
    """

    def __init__(self):
        self._vision_available = None

    def is_vision_available(self) -> bool:
        """Check if the current LLM configuration supports vision."""
        if self._vision_available is not None:
            return self._vision_available

        provider = Config.LLM_PROVIDER
        model = Config.LLM_MODEL_NAME

        # Check if current model is vision-capable
        provider_models = VISION_MODELS.get(provider, [])
        self._vision_available = any(vm in model for vm in provider_models)

        if not self._vision_available:
            logger.info("[Multimodal] Vision not available (provider=%s, model=%s). Using text fallback.",
                        provider, model)
        return self._vision_available

    def analyze_figure(
        self,
        image_data: bytes,
        context: str = "",
        caption: str = "",
        paper_claims: List[str] = None,
        model: str = "",
    ) -> FigureAnalysis:
        """
        Analyze a figure using vision-capable LLM.

        Args:
            image_data: Raw image bytes (PNG, JPEG)
            context: What the figure is about (e.g., "EIS measurement results")
            caption: Original caption from the paper
            paper_claims: Claims from the paper to link against
            model: Model override

        Returns:
            FigureAnalysis with extracted information
        """
        if not self.is_vision_available() and not model:
            return self.text_fallback(caption=caption, context=context, paper_claims=paper_claims)

        try:
            from opensens_common.llm_client import LLMClient
            llm = LLMClient()

            # Encode image as base64
            b64_image = base64.b64encode(image_data).decode("utf-8")

            # Detect image type
            media_type = "image/png"
            if image_data[:2] == b'\xff\xd8':
                media_type = "image/jpeg"

            system_prompt = """You are an expert scientific figure analyst. Analyze the provided figure and extract:
1. Figure type (plot, micrograph, table, diagram, photo)
2. Detailed description of what the figure shows
3. Axis labels and units (if applicable)
4. Legend items (if applicable)
5. Key data points or trends summary
6. Important observations
7. Any quality issues (poor resolution, missing labels, inconsistent data)

Output as JSON:
{
  "figure_type": "plot|micrograph|table|diagram|photo",
  "description": "detailed description",
  "axes": {"x": "label (unit)", "y": "label (unit)"},
  "legends": ["series1", "series2"],
  "data_points_summary": "summary of key data",
  "key_observations": ["obs1", "obs2"],
  "quality_issues": ["issue1"]
}"""

            claims_context = ""
            if paper_claims:
                claims_context = "\n\nPaper claims to verify against this figure:\n" + "\n".join(
                    f"- {c}" for c in paper_claims[:10]
                )

            user_content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64_image,
                    },
                },
                {
                    "type": "text",
                    "text": f"Analyze this scientific figure.\nContext: {context}\nCaption: {caption}{claims_context}",
                },
            ]

            # Use vision-capable model
            target_model = model or Config.LLM_MODEL_NAME
            response = llm.generate(
                system=system_prompt,
                user=user_content,
                model=target_model,
                json_mode=True,
            )

            data = json.loads(response)

            # Link claims if provided
            linked = []
            if paper_claims and data.get("key_observations"):
                linked = self._match_claims(data["key_observations"], paper_claims)

            return FigureAnalysis(
                figure_type=data.get("figure_type", "unknown"),
                caption=caption,
                description=data.get("description", ""),
                axes=data.get("axes", {}),
                legends=data.get("legends", []),
                data_points_summary=data.get("data_points_summary", ""),
                key_observations=data.get("key_observations", []),
                linked_claims=linked,
                quality_issues=data.get("quality_issues", []),
                model_used=target_model,
                mode="vision",
            )

        except Exception as e:
            logger.warning("[Multimodal] Vision analysis failed: %s. Falling back to text.", e)
            return self.text_fallback(caption=caption, context=context, paper_claims=paper_claims)

    def text_fallback(
        self,
        caption: str = "",
        context: str = "",
        paper_claims: List[str] = None,
    ) -> FigureAnalysis:
        """
        Text-only fallback when vision is unavailable.
        Extracts what it can from caption and context alone.
        """
        figure_type = self._infer_type_from_caption(caption)
        description = f"Figure described by caption: {caption}" if caption else "No visual analysis available (text-only mode)"

        observations = []
        if caption:
            observations.append(f"Caption indicates: {caption[:200]}")

        linked = []
        if paper_claims and caption:
            linked = self._match_claims([caption], paper_claims)

        return FigureAnalysis(
            figure_type=figure_type,
            caption=caption,
            description=description,
            key_observations=observations,
            linked_claims=linked,
            quality_issues=["Visual analysis unavailable — using text-only mode"],
            model_used="text_fallback",
            mode="text_fallback",
        )

    def extract_figures_from_docx(self, docx_path: str) -> List[Tuple[bytes, str]]:
        """
        Extract images and their captions from a DOCX file.

        Returns:
            List of (image_bytes, caption_text) tuples
        """
        try:
            from docx import Document
            from docx.opc.constants import RELATIONSHIP_TYPE as RT
        except ImportError:
            logger.warning("[Multimodal] python-docx not available for figure extraction")
            return []

        figures = []
        try:
            doc = Document(docx_path)

            # Extract embedded images
            for rel in doc.part.rels.values():
                if "image" in rel.reltype:
                    image_data = rel.target_part.blob
                    # Try to find associated caption
                    caption = ""  # Captions require paragraph-level analysis
                    figures.append((image_data, caption))

            # Extract captions from paragraphs
            for i, para in enumerate(doc.paragraphs):
                text = para.text.strip()
                if text.lower().startswith(("figure ", "fig.", "fig ")) and i < len(figures):
                    # Associate caption with figure
                    idx = min(i, len(figures) - 1)
                    figures[idx] = (figures[idx][0], text)

        except Exception as e:
            logger.warning("[Multimodal] DOCX figure extraction failed: %s", e)

        return figures

    def analyze_document_figures(
        self,
        docx_path: str,
        paper_claims: List[str] = None,
        model: str = "",
    ) -> DocumentFigures:
        """
        Extract and analyze all figures from a document.

        Args:
            docx_path: Path to DOCX file
            paper_claims: Claims to link against
            model: Model override

        Returns:
            DocumentFigures with all analyzed figures
        """
        raw_figures = self.extract_figures_from_docx(docx_path)

        analyses = []
        vision_count = 0
        fallback_count = 0

        for i, (image_data, caption) in enumerate(raw_figures):
            analysis = self.analyze_figure(
                image_data=image_data,
                context=f"Figure {i+1} from research paper",
                caption=caption,
                paper_claims=paper_claims,
                model=model,
            )
            analysis.figure_id = f"fig_{i+1}"
            analyses.append(analysis)

            if analysis.mode == "vision":
                vision_count += 1
            else:
                fallback_count += 1

        return DocumentFigures(
            figures=analyses,
            total_figures=len(analyses),
            vision_analyzed=vision_count,
            text_fallback_count=fallback_count,
            extraction_method="docx" if raw_figures else "none",
        )

    def _infer_type_from_caption(self, caption: str) -> str:
        """Infer figure type from caption text."""
        if not caption:
            return "unknown"
        c = caption.lower()
        if any(w in c for w in ["plot", "graph", "curve", "spectrum", "spectra", "nyquist", "bode"]):
            return "plot"
        if any(w in c for w in ["micrograph", "sem", "tem", "afm", "microscop"]):
            return "micrograph"
        if any(w in c for w in ["table", "comparison", "summary"]):
            return "table"
        if any(w in c for w in ["diagram", "schematic", "flowchart", "architecture"]):
            return "diagram"
        if any(w in c for w in ["photo", "image", "picture"]):
            return "photo"
        return "plot"  # default for scientific papers

    def _match_claims(self, observations: List[str], claims: List[str]) -> List[str]:
        """Simple keyword-based claim matching. Future: use embeddings."""
        matched = []
        obs_text = " ".join(observations).lower()
        for claim in claims:
            claim_words = set(claim.lower().split())
            # Match if >30% of significant claim words appear in observations
            significant = {w for w in claim_words if len(w) > 3}
            if significant:
                overlap = sum(1 for w in significant if w in obs_text)
                if overlap / len(significant) > 0.3:
                    matched.append(claim)
        return matched
