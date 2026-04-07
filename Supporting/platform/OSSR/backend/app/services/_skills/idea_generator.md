---
model:
temperature: 0.85
rollout_n: 3
tags: ideation, creative, research
---

## When to use

Invoked by `services/ais/idea_generator.py` after the topic map and debate
summary are available. Generates novel, concrete, testable research ideas
grounded in the supplied landscape. Runs with rollout_n=3 so the caller
can rubric-aggregate across candidates (UniScientist pattern).

## Inputs

- `topic`: the research area the user is exploring
- `topic_map`: short bullet list of known subtopics + coverage
- `debate_summary`: condensed multi-agent debate transcript
- `existing_ideas`: previously-generated ideas the new batch must not duplicate
- `count`: how many ideas to emit (default 5)

## Output schema

```json
{
  "ideas": [
    {
      "title": "short",
      "summary": "2-3 sentences",
      "novelty": 0.0,
      "feasibility": 0.0,
      "interestingness": 0.0,
      "experiment_sketch": "how one could test it",
      "required_evidence": ["what sources would ground this"],
      "risks": ["main risks or confounders"]
    }
  ]
}
```

The three self-assessed scores (novelty / feasibility / interestingness)
are inputs to the rollout rubric. They must be realistic — over-confident
rollouts are penalised at aggregation time.

## Prompt

You are a senior research scientist generating new project ideas.

Topic: {topic}

Landscape:
{topic_map}

Debate highlights:
{debate_summary}

Ideas already on the table (do NOT duplicate):
{existing_ideas}

Produce exactly {count} new research ideas. Each must be:
- grounded in the landscape (reference at least one subtopic or debate point);
- specific enough to design an experiment against in a few sentences;
- genuinely different from every previously-listed idea.

Return ONLY valid JSON matching the schema. No prose, no markdown fence.
