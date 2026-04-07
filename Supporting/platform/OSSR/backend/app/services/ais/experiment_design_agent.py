"""
Experiment Design Agent
Identifies missing evidence in a paper draft and generates experiment designs,
including controls, calibration procedures, lab protocols, and data templates.

This agent sits between Draft and Revise in the V2 pipeline graph:
  Draft → Experiment Design → Revise

It produces:
1. Evidence gap analysis (what claims lack experimental support)
2. Proposed experiments (with controls, equipment, procedures)
3. Data collection templates (what measurements, formats, units)
4. Calibration requirements
5. Structured output that feeds directly into the Revise node
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from opensens_common.llm_client import LLMClient
from opensens_common.config import Config

logger = logging.getLogger(__name__)


@dataclass
class EvidenceGap:
    claim: str
    section: str
    gap_type: str  # "no_data", "weak_evidence", "missing_control", "no_baseline", "no_stats"
    severity: str  # "critical", "major", "minor"
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "section": self.section,
            "gap_type": self.gap_type,
            "severity": self.severity,
            "description": self.description,
        }


@dataclass
class ProposedExperiment:
    name: str
    objective: str
    addresses_gaps: List[str]  # references to EvidenceGap claims
    methodology: str
    equipment: List[str]
    controls: List[str]
    calibration: List[str]
    expected_measurements: List[Dict[str, str]]  # [{"parameter": "", "unit": "", "range": ""}]
    procedure_steps: List[str]
    estimated_duration: str = ""
    data_template: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "objective": self.objective,
            "addresses_gaps": self.addresses_gaps,
            "methodology": self.methodology,
            "equipment": self.equipment,
            "controls": self.controls,
            "calibration": self.calibration,
            "expected_measurements": self.expected_measurements,
            "procedure_steps": self.procedure_steps,
            "estimated_duration": self.estimated_duration,
            "data_template": self.data_template,
        }


@dataclass
class ExperimentDesignResult:
    gaps: List[EvidenceGap] = field(default_factory=list)
    experiments: List[ProposedExperiment] = field(default_factory=list)
    overall_readiness: float = 0.0  # 0-10 how ready the paper is for publication
    summary: str = ""
    model_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gaps": [g.to_dict() for g in self.gaps],
            "experiments": [e.to_dict() for e in self.experiments],
            "overall_readiness": self.overall_readiness,
            "summary": self.summary,
            "model_used": self.model_used,
            "gap_count": len(self.gaps),
            "critical_gaps": sum(1 for g in self.gaps if g.severity == "critical"),
            "experiment_count": len(self.experiments),
        }


class ExperimentDesignAgent:
    """Analyzes draft papers for evidence gaps and generates experiment designs."""

    def __init__(self):
        self.llm = LLMClient()

    def analyze_and_design(
        self,
        draft_sections: List[Dict[str, Any]],
        idea: Dict[str, Any],
        debate_transcript: List[Dict] = None,
        model: str = "",
    ) -> ExperimentDesignResult:
        """
        Full pipeline: identify gaps → design experiments → generate data templates.

        Args:
            draft_sections: List of {"name": str, "content": str}
            idea: Research idea dict with hypothesis, methodology
            debate_transcript: Optional debate turns for context
            model: LLM model override

        Returns:
            ExperimentDesignResult with gaps and proposed experiments
        """
        # Phase 1: Evidence gap analysis
        gaps = self._identify_gaps(draft_sections, idea, model)

        # Phase 2: Experiment design for critical/major gaps
        experiments = []
        if gaps:
            actionable_gaps = [g for g in gaps if g.severity in ("critical", "major")]
            if actionable_gaps:
                experiments = self._design_experiments(actionable_gaps, idea, debate_transcript, model)

        # Phase 3: Readiness assessment
        readiness = self._assess_readiness(gaps)

        summary = self._generate_summary(gaps, experiments, readiness)

        return ExperimentDesignResult(
            gaps=gaps,
            experiments=experiments,
            overall_readiness=readiness,
            summary=summary,
            model_used=model or Config.LLM_MODEL_NAME,
        )

    def _identify_gaps(
        self,
        draft_sections: List[Dict[str, Any]],
        idea: Dict[str, Any],
        model: str,
    ) -> List[EvidenceGap]:
        """Phase 1: Identify claims that lack experimental evidence."""
        sections_text = "\n\n".join(
            f"## {s.get('name', 'Section')}\n{s.get('content', '')[:2000]}"
            for s in draft_sections
        )

        system_prompt = """You are a rigorous scientific evidence auditor. Your job is to find claims in this paper draft that LACK proper experimental evidence.

For each gap, identify:
1. The specific claim being made
2. Which section it appears in
3. The type of gap (no_data, weak_evidence, missing_control, no_baseline, no_stats)
4. Severity (critical = paper cannot be published without this, major = significantly weakens paper, minor = nice to have)

Output as JSON:
{
  "gaps": [
    {
      "claim": "the specific claim text",
      "section": "methodology|results|discussion|etc",
      "gap_type": "no_data|weak_evidence|missing_control|no_baseline|no_stats",
      "severity": "critical|major|minor",
      "description": "what evidence is missing and why it matters"
    }
  ]
}"""

        user_prompt = f"""Research hypothesis: {idea.get('hypothesis', '')}
Methodology: {idea.get('methodology', '')}

Paper draft sections:
{sections_text[:6000]}

Identify ALL evidence gaps. Be thorough — a published paper needs solid experimental backing."""

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            response = self.llm.chat(messages, temperature=0.3, max_tokens=4096, response_format={"type": "json_object"})
            data = json.loads(response)
            return [
                EvidenceGap(
                    claim=g.get("claim", ""),
                    section=g.get("section", ""),
                    gap_type=g.get("gap_type", "no_data"),
                    severity=g.get("severity", "minor"),
                    description=g.get("description", ""),
                )
                for g in data.get("gaps", [])
            ]
        except Exception as e:
            logger.warning("[ExperimentDesign] Gap analysis failed: %s", e)
            return [EvidenceGap(
                claim="Unable to analyze gaps",
                section="all",
                gap_type="no_data",
                severity="minor",
                description=f"Gap analysis failed: {e}",
            )]

    def _design_experiments(
        self,
        gaps: List[EvidenceGap],
        idea: Dict[str, Any],
        transcript: List[Dict] = None,
        model: str = "",
    ) -> List[ProposedExperiment]:
        """Phase 2: Design experiments to fill evidence gaps."""
        gaps_text = "\n".join(
            f"- [{g.severity.upper()}] {g.claim}: {g.description}" for g in gaps
        )

        debate_context = ""
        if transcript:
            debate_context = "\n\nKey debate points:\n" + "\n".join(
                f"- {t.get('agent_name', 'Agent')}: {t.get('content', '')[:200]}"
                for t in transcript[:10]
            )

        system_prompt = """You are a senior experimental scientist. Design concrete, implementable experiments to fill evidence gaps in a research paper.

For each experiment, provide:
1. Clear objective tied to specific gap(s)
2. Detailed methodology
3. Required equipment
4. Controls (positive, negative, blanks)
5. Calibration procedures
6. Expected measurements (parameter, unit, expected range)
7. Step-by-step procedure
8. Estimated duration
9. Data template (columns for data collection spreadsheet)

Output as JSON:
{
  "experiments": [
    {
      "name": "Experiment name",
      "objective": "What this proves",
      "addresses_gaps": ["claim 1", "claim 2"],
      "methodology": "Detailed approach",
      "equipment": ["item1", "item2"],
      "controls": ["positive: ...", "negative: ...", "blank: ..."],
      "calibration": ["step1", "step2"],
      "expected_measurements": [{"parameter": "Resistance", "unit": "Ohm", "range": "10-1000"}],
      "procedure_steps": ["Step 1: ...", "Step 2: ..."],
      "estimated_duration": "2 weeks",
      "data_template": {"columns": ["sample_id", "measurement_1", "control_value"], "format": "csv"}
    }
  ]
}"""

        user_prompt = f"""Research: {idea.get('title', '')}
Hypothesis: {idea.get('hypothesis', '')}
Methodology: {idea.get('methodology', '')}

Evidence gaps to address:
{gaps_text}
{debate_context}

Design experiments that would make this paper publishable. Focus on critical and major gaps first."""

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            response = self.llm.chat(messages, temperature=0.3, max_tokens=4096, response_format={"type": "json_object"})
            data = json.loads(response)
            return [
                ProposedExperiment(
                    name=e.get("name", ""),
                    objective=e.get("objective", ""),
                    addresses_gaps=e.get("addresses_gaps", []),
                    methodology=e.get("methodology", ""),
                    equipment=e.get("equipment", []),
                    controls=e.get("controls", []),
                    calibration=e.get("calibration", []),
                    expected_measurements=e.get("expected_measurements", []),
                    procedure_steps=e.get("procedure_steps", []),
                    estimated_duration=e.get("estimated_duration", ""),
                    data_template=e.get("data_template", {}),
                )
                for e in data.get("experiments", [])
            ]
        except Exception as e:
            logger.warning("[ExperimentDesign] Experiment design failed: %s", e)
            return []

    def _assess_readiness(self, gaps: List[EvidenceGap]) -> float:
        """Score 0-10 based on gap severity distribution."""
        if not gaps:
            return 9.0

        critical = sum(1 for g in gaps if g.severity == "critical")
        major = sum(1 for g in gaps if g.severity == "major")
        minor = sum(1 for g in gaps if g.severity == "minor")

        # Deduct points for gaps
        score = 10.0
        score -= critical * 2.5
        score -= major * 1.0
        score -= minor * 0.3
        return max(0.0, min(10.0, round(score, 1)))

    def _generate_summary(
        self,
        gaps: List[EvidenceGap],
        experiments: List[ProposedExperiment],
        readiness: float,
    ) -> str:
        """Generate human-readable summary."""
        critical = sum(1 for g in gaps if g.severity == "critical")
        major = sum(1 for g in gaps if g.severity == "major")

        parts = [f"Publication readiness: {readiness}/10."]
        if critical:
            parts.append(f"{critical} critical evidence gap(s) must be addressed before submission.")
        if major:
            parts.append(f"{major} major gap(s) would significantly strengthen the paper.")
        if experiments:
            parts.append(f"{len(experiments)} experiment(s) designed to fill gaps.")
        if readiness >= 7:
            parts.append("Paper is approaching publication quality.")
        elif readiness >= 4:
            parts.append("Paper needs additional experimental work.")
        else:
            parts.append("Substantial experimental evidence is required.")
        return " ".join(parts)
