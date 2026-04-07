# Parallax V2 Skill Cards

LabClaw-style skill cards. One `<agent>.md` per agent. Each card is parsed by
`services/_agents/prompt_loader.py` into a `SkillCard` with four sections:

```
## When to use
## Inputs
## Output schema
## Prompt
```

An optional YAML-ish front matter block carries metadata:

```markdown
---
model: claude-sonnet-4-20250514
temperature: 0.35
rollout_n: 3
tags: idea_generation, creative
---
```

Placeholders in `## Prompt` use `{name}` syntax. Missing placeholders are
left intact so layered rendering is safe. Agents that have not been
migrated yet keep their legacy hard-coded prompts — the loader gracefully
returns an empty card if a file is missing.
