---
model:
temperature: 0.4
rollout_n: 3
tags: knowledge, hypothesis, grounding
---

## When to use

Invoked by `services/knowledge/hypothesis_builder.py` once a knowledge
artifact (claims + evidence + gaps) exists. Produces a structured
contribution hypothesis that MUST cite ≥2 supporting claims (UniScientist
evidence-integration requirement). Runs with rollout_n=3 and the rubric
rejects any rollout that fails the grounding requirement.

## Inputs

- `idea`: the underlying research idea
- `claims`: JSON array of claim records from the artifact
- `gaps`: JSON array of identified gaps
- `evidence`: JSON array of evidence nodes

## Output schema

```json
{
  "hypothesis": "one or two sentences",
  "contribution_type": "method | finding | framework | benchmark | survey",
  "supporting_claim_ids": ["cl_1", "cl_2"],
  "addressed_gap_ids": ["gap_1"],
  "counter_evidence_acknowledged": "what could disprove this",
  "confidence": 0.0,
  "rollout_rationale": "why this framing beats alternatives"
}
```

A rollout is invalid (score=0) if `supporting_claim_ids` has fewer than 2
entries.

## Prompt

You are a research strategist drafting a contribution hypothesis.

Research idea: {idea}

Claims:
{claims}

Gaps:
{gaps}

Evidence:
{evidence}

Produce ONE contribution hypothesis that:
1. cites at least two of the listed claims by id;
2. addresses at least one gap;
3. explicitly states what counter-evidence would disprove it.

Return ONLY valid JSON matching the schema above.
