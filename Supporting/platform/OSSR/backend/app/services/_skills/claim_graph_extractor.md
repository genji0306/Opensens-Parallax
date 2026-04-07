---
model:
temperature: 0.2
rollout_n: 1
tags: knowledge, triples, kg
---

## When to use

Invoked by `services/knowledge/claim_graph.py` when the pipeline artifact
exposes a set of claims and evidence nodes but does not yet carry typed
inter-claim edges. Produces Awesome-LLM-KG-style `(subject, relation,
object)` triples so downstream agents can walk the knowledge graph.

## Inputs

- `claims`: JSON array of `{claim_id, text, category}`
- `evidence`: JSON array of `{evidence_id, title, excerpt}`
- `max_triples`: soft cap, default 30

## Output schema

```json
{
  "triples": [
    {
      "subject_id": "claim_abc",
      "relation": "supports | contradicts | extends | grounded_in",
      "object_id": "claim_xyz | evidence_123",
      "confidence": 0.0,
      "evidence_ids": ["evidence_123"],
      "rationale": "one sentence justification"
    }
  ]
}
```

Only emit a triple when the textual overlap is non-trivial. Prefer fewer
high-confidence triples over many speculative ones. Every `supports` /
`contradicts` / `extends` triple between two claims MUST list at least one
`evidence_ids` entry that justifies the edge — this is the grounding
requirement borrowed from UniScientist.

## Prompt

You are a knowledge-graph extraction agent. Given a set of research claims
and evidence items, produce typed edges between them.

Claims:
{claims}

Evidence:
{evidence}

Rules:
1. `grounded_in` goes from a claim to an evidence node and does NOT require
   another evidence id.
2. `supports`, `contradicts`, `extends` go between TWO claims. Each such
   triple MUST cite at least one `evidence_ids` entry.
3. Keep `confidence` between 0 and 1. Use <0.5 for weak signals.
4. Emit at most {max_triples} triples.
5. Return ONLY valid JSON matching the schema above. No prose, no markdown.
