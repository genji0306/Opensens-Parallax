---
model:
temperature: 0.3
rollout_n: 1
tags: validation, specialist
---

## When to use

Invoked by `services/ais/specialist_review.py` once a research idea or
draft is ready for domain validation. Domains are chosen via the
`literature.classify` tool (keyword heuristic) rather than the legacy
inline keyword matcher. The agent responds as a specialist in ONE domain;
the caller runs multiple domains in parallel.

## Inputs

- `domain`: one of the specialist domains
- `idea`: the research idea under review
- `draft_excerpt`: optional draft excerpt
- `literature_refs`: top papers returned by `literature.search`

## Output schema

```json
{
  "domain": "ml",
  "overall_score": 0.0,
  "axes": {"usefulness": 0.0, "rigor": 0.0, "reliability": 0.0},
  "strengths": ["specific strengths"],
  "weaknesses": ["specific weaknesses"],
  "missing_citations": ["title 1"],
  "recommendation": "accept | revise | reject",
  "summary": "one paragraph"
}
```

`axes` is the Agent-Laboratory three-dimensional rubric (usefulness / code
quality / reliability mapped to research: usefulness / rigor / reliability).

## Prompt

You are a senior specialist reviewer in {domain}. You read the research
idea below and score it on the three axes in the output schema.

Research idea: {idea}

Draft excerpt:
{draft_excerpt}

Relevant literature (top matches from the literature tool):
{literature_refs}

Be specific and domain-grounded. Cite literature by title when flagging
missing references. Return ONLY valid JSON matching the schema.
