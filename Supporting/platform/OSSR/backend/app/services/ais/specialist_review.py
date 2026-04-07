"""
Specialist Review Service
Domain-expert review agents that detect methodological issues in research ideas and drafts.

Specialist domains:
- Electrochemistry (EIS, CV, DPV, SWV techniques)
- Spectroscopy (Raman, FTIR, XRD, NMR)
- Materials Science (synthesis, characterization, phase analysis)
- Statistics (experimental design, hypothesis testing, power analysis)
- ML Methodology (model validation, data leakage, benchmark fairness)
- Energy Systems (battery, fuel cell, solar cell design)
- Reproducibility (protocol completeness, data availability, code sharing)
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from opensens_common.llm_client import LLMClient
from opensens_common.config import Config

logger = logging.getLogger(__name__)


# ── Specialist Definitions ──────────────────────────────────────────

SPECIALIST_PROFILES = {
    "electrochemistry": {
        "name": "Electrochemistry Specialist",
        "expertise": "EIS, CV, DPV, SWV, potentiostat protocols, equivalent circuit modeling",
        "focus": [
            "Missing electrode preparation controls",
            "Incorrect equivalent circuit fitting",
            "Neglected solution resistance correction",
            "Insufficient cycling data for stability claims",
            "Improper reference electrode handling",
        ],
    },
    "eis": {
        "name": "EIS / Impedance Specialist",
        "expertise": "Electrochemical impedance spectroscopy, Nyquist/Bode analysis, Kramers-Kronig validation",
        "focus": [
            "Kramers-Kronig compliance not verified",
            "Frequency range too narrow for claimed phenomena",
            "Missing linearity check (amplitude dependence)",
            "Improper deconvolution of overlapping arcs",
            "Temperature effects not controlled",
        ],
    },
    "spectroscopy": {
        "name": "Spectroscopy Specialist",
        "expertise": "Raman, FTIR, XRD, NMR, UV-Vis, mass spectrometry",
        "focus": [
            "Missing baseline correction details",
            "Peak assignment without reference standards",
            "Resolution insufficient for claimed features",
            "Sample preparation artifacts",
            "Fluorescence interference in Raman not addressed",
        ],
    },
    "materials_science": {
        "name": "Materials Science Specialist",
        "expertise": "Synthesis, characterization, phase diagrams, microstructure, mechanical testing",
        "focus": [
            "Synthesis conditions not fully specified (reproducibility risk)",
            "Phase identification without supporting XRD/TEM evidence",
            "Missing error bars on mechanical property measurements",
            "Insufficient sample size for statistical claims",
            "Environmental degradation not considered",
        ],
    },
    "statistics": {
        "name": "Statistics & Experimental Design Specialist",
        "expertise": "DOE, hypothesis testing, power analysis, multiple comparisons, Bayesian methods",
        "focus": [
            "No power analysis for sample size justification",
            "Multiple comparisons without correction (Bonferroni, FDR)",
            "Pseudo-replication (technical vs biological replicates)",
            "Inappropriate statistical test for data distribution",
            "Missing effect size reporting",
        ],
    },
    "ml_methodology": {
        "name": "ML Methodology Specialist",
        "expertise": "Model validation, cross-validation, data leakage, benchmark design, ablation studies",
        "focus": [
            "Data leakage between train and test sets",
            "No ablation study for claimed improvements",
            "Hyperparameter tuning on test set",
            "Missing baselines or unfair comparison",
            "Overfitting to specific dataset without generalization evidence",
        ],
    },
    "energy_systems": {
        "name": "Energy Systems Specialist",
        "expertise": "Batteries, fuel cells, solar cells, supercapacitors, energy storage",
        "focus": [
            "Missing long-term cycling stability data",
            "Coulombic efficiency not reported or calculated incorrectly",
            "Rate capability tested at non-standard conditions",
            "Self-discharge not characterized",
            "Insufficient comparison with state-of-the-art",
        ],
    },
    "reproducibility": {
        "name": "Reproducibility Auditor",
        "expertise": "FAIR data principles, protocol documentation, code/data availability",
        "focus": [
            "Key experimental parameters missing from methods section",
            "Software/code not available or version not specified",
            "Raw data not deposited in public repository",
            "Custom equipment without sufficient description",
            "Environmental conditions (temperature, humidity) not logged",
        ],
    },
}


@dataclass
class ReviewFinding:
    domain: str
    severity: str  # "critical", "major", "minor", "suggestion"
    category: str  # e.g., "missing_control", "weak_baseline"
    description: str
    recommendation: str
    evidence_reference: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "recommendation": self.recommendation,
            "evidence_reference": self.evidence_reference,
        }


@dataclass
class SpecialistReviewResult:
    domain: str
    specialist_name: str
    findings: List[ReviewFinding] = field(default_factory=list)
    overall_score: float = 0.0
    summary: str = ""
    model_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "specialist_name": self.specialist_name,
            "findings": [f.to_dict() for f in self.findings],
            "overall_score": self.overall_score,
            "summary": self.summary,
            "model_used": self.model_used,
            "finding_count": len(self.findings),
            "critical_count": sum(1 for f in self.findings if f.severity == "critical"),
            "major_count": sum(1 for f in self.findings if f.severity == "major"),
        }


class SpecialistReviewService:
    """Run domain-specific specialist reviews on research ideas or paper drafts."""

    def __init__(self):
        self.llm = LLMClient()

    def detect_relevant_domains(self, text: str) -> List[str]:
        """Auto-detect which specialist domains are relevant for the given text."""
        text_lower = text.lower()
        relevant = []

        keyword_map = {
            "electrochemistry": ["electrochemi", "electrode", "potentiostat", "galvanostatic", "voltammetry", "cyclic voltammetry"],
            "eis": ["impedance", "nyquist", "bode", "eis ", "equivalent circuit"],
            "spectroscopy": ["raman", "ftir", "xrd", "nmr", "uv-vis", "spectroscop", "diffraction"],
            "materials_science": ["synthesis", "nanoparticle", "thin film", "crystal", "alloy", "ceramic", "polymer blend"],
            "statistics": ["p-value", "anova", "regression", "hypothesis test", "confidence interval", "statistical"],
            "ml_methodology": ["machine learning", "deep learning", "neural network", "classification", "training", "model accuracy", "cross-validation"],
            "energy_systems": ["battery", "fuel cell", "solar cell", "supercapacitor", "energy storage", "lithium"],
        }

        for domain, keywords in keyword_map.items():
            if any(kw in text_lower for kw in keywords):
                relevant.append(domain)

        # Always include reproducibility
        if relevant:
            relevant.append("reproducibility")

        return relevant or ["statistics", "reproducibility"]  # fallback

    def review(
        self,
        content: str,
        domains: List[str] = None,
        strictness: float = 0.7,
        model: str = "",
    ) -> List[SpecialistReviewResult]:
        """
        Run specialist reviews on content.

        Args:
            content: Research idea text, methodology, or draft sections
            domains: List of specialist domains to activate (auto-detect if None)
            strictness: 0-1 scale for review harshness
            model: LLM model override

        Returns:
            List of SpecialistReviewResult, one per domain
        """
        if not domains:
            domains = self.detect_relevant_domains(content)

        results = []
        for domain in domains:
            profile = SPECIALIST_PROFILES.get(domain)
            if not profile:
                continue

            result = self._run_single_review(content, domain, profile, strictness, model)
            results.append(result)

        return results

    def _run_single_review(
        self,
        content: str,
        domain: str,
        profile: Dict[str, Any],
        strictness: float,
        model: str,
    ) -> SpecialistReviewResult:
        """Run a single specialist review."""
        strictness_label = "very strict" if strictness > 0.8 else "moderate" if strictness > 0.5 else "lenient"

        system_prompt = f"""You are the {profile['name']}, an expert reviewer in {profile['expertise']}.

Your review style is {strictness_label}. You actively look for:
{chr(10).join(f'- {f}' for f in profile['focus'])}

You MUST detect:
- Missing controls
- Weak baselines
- Invalid interpretations
- Reproducibility risks

Output your review as JSON with this structure:
{{
  "findings": [
    {{
      "severity": "critical|major|minor|suggestion",
      "category": "missing_control|weak_baseline|invalid_interpretation|reproducibility_risk|methodological_gap|data_quality",
      "description": "...",
      "recommendation": "...",
      "evidence_reference": "which part of the text this refers to"
    }}
  ],
  "overall_score": 0-10,
  "summary": "2-3 sentence overall assessment"
}}"""

        user_prompt = f"Review the following research content as the {profile['name']}:\n\n{content[:8000]}"

        try:
            response = self.llm.generate(
                system=system_prompt,
                user=user_prompt,
                model=model or None,
                json_mode=True,
            )

            data = json.loads(response)
            findings = [
                ReviewFinding(
                    domain=domain,
                    severity=f.get("severity", "minor"),
                    category=f.get("category", "other"),
                    description=f.get("description", ""),
                    recommendation=f.get("recommendation", ""),
                    evidence_reference=f.get("evidence_reference", ""),
                )
                for f in data.get("findings", [])
            ]

            return SpecialistReviewResult(
                domain=domain,
                specialist_name=profile["name"],
                findings=findings,
                overall_score=data.get("overall_score", 0),
                summary=data.get("summary", ""),
                model_used=model or Config.LLM_MODEL_NAME,
            )

        except Exception as e:
            logger.warning("[SpecialistReview] %s review failed: %s", domain, e)
            return SpecialistReviewResult(
                domain=domain,
                specialist_name=profile["name"],
                findings=[ReviewFinding(
                    domain=domain,
                    severity="minor",
                    category="review_error",
                    description=f"Review could not be completed: {e}",
                    recommendation="Run review again with available LLM",
                )],
                overall_score=0,
                summary=f"Review failed: {e}",
                model_used=model or "none",
            )

    @staticmethod
    def available_domains() -> List[Dict[str, str]]:
        """List available specialist review domains."""
        return [
            {"domain": k, "name": v["name"], "expertise": v["expertise"]}
            for k, v in SPECIALIST_PROFILES.items()
        ]
