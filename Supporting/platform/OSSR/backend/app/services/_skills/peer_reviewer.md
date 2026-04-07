---
model:
temperature: 0.35
rollout_n: 1
tags: review, annotations, peer_review
---

## When to use

Invoked by `services/review/board_manager.py` inside the AgentReview
5-phase pipeline. The reviewer agent renders itself with its 3D persona
fragment and emits LLM-Peer-style granular annotations (not prose review
blocks). Each annotation targets a section or figure and can be
individually accepted or rejected in the UI.

## Inputs

- `persona_prompt`: rendered persona fragment (commitment/intention/knowledgeability)
- `phase`: one of `independent`, `rebuttal`, `discussion`, `meta`, `decision`
- `draft_sections`: JSON array of `{section_id, heading, text}`
- `figures`: JSON array of `{figure_id, caption}` (may be empty)
- `prior_annotations`: annotations already produced in earlier phases
- `author_rebuttal`: optional rebuttal text (phase=discussion|meta)

## Output schema

```json
{
  "summary": "one paragraph reviewer summary",
  "scores": {"usefulness": 0.0, "rigor": 0.0, "reliability": 0.0},
  "recommendation": "accept | weak_accept | borderline | weak_reject | reject",
  "annotations": [
    {
      "kind": "comment | insert | replace",
      "target_id": "sec_intro",
      "span": [start, end],
      "original_text": "",
      "replacement_text": "",
      "comment": "specific actionable note",
      "severity": "critical | major | minor | nit",
      "confidence": 0.0
    }
  ]
}
```

Annotations MUST reference a real `section_id` or `figure_id`. `span` is
optional; when provided, start/end are character offsets inside
`original_text`.

## Prompt

{persona_prompt}

Review phase: {phase}
{phase_guidance}

Draft sections:
{draft_sections}

Figures:
{figures}

Prior annotations (do not repeat):
{prior_annotations}

Author rebuttal (if any):
{author_rebuttal}

Produce a structured review. Prefer specific, localisable annotations over
paragraph-level prose. Avoid bias towards length: a one-line nit is
perfectly fine if that is all the section needs.

Return ONLY valid JSON matching the schema.
