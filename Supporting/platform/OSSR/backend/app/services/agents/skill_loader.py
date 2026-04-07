"""
Scientific Skills Loader.
Reads SKILL.md files from the skills directory and provides
skill metadata + content for injection into agent prompts.
"""

import os
import re
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Skill:
    """A loaded scientific skill."""
    name: str
    description: str
    license: str = ""
    category: str = ""       # Inferred: database, package, analysis, integration
    content: str = ""        # Full SKILL.md content (for prompt injection)
    summary: str = ""        # First ~500 chars of content (for listing)


class SkillLoader:
    """Singleton loader for scientific skills."""

    _instance = None
    _skills: Dict[str, Skill] = {}
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, skills_dir: Optional[str] = None):
        """Load all skills from the skills directory."""
        if self._loaded and not skills_dir:
            return

        if not skills_dir:
            # Default: OSSR/skills/scientific-skills/
            # __file__ is backend/app/services/skill_loader.py — go up 3 to OSSR/
            base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            skills_dir = os.path.join(base, "skills", "scientific-skills")

        if not os.path.isdir(skills_dir):
            return

        for entry in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, entry, "SKILL.md")
            if os.path.isfile(skill_path):
                skill = self._parse_skill(skill_path, entry)
                if skill:
                    self._skills[skill.name] = skill

        self._loaded = True

    def _parse_skill(self, path: str, folder_name: str) -> Optional[Skill]:
        """Parse a SKILL.md file into a Skill object."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            return None

        # Parse YAML frontmatter
        name = folder_name
        description = ""
        license_str = ""

        fm_match = re.match(r'^---\s*\n(.*?)\n---', raw, re.DOTALL)
        if fm_match:
            try:
                fm = yaml.safe_load(fm_match.group(1))
                if isinstance(fm, dict):
                    name = fm.get("name", folder_name)
                    description = fm.get("description", "")
                    license_str = fm.get("license", "")
            except yaml.YAMLError:
                pass

        # Strip frontmatter for content
        content = re.sub(r'^---\s*\n.*?\n---\s*\n?', '', raw, count=1, flags=re.DOTALL).strip()

        # Infer category from folder name
        category = "package"
        if "database" in folder_name:
            category = "database"
        elif "integration" in folder_name:
            category = "integration"
        elif folder_name in (
            "statistical-analysis", "hypothesis-generation", "literature-review",
            "scientific-brainstorming", "scientific-critical-thinking",
            "scientific-writing", "peer-review", "exploratory-data-analysis",
            "scientific-visualization", "scientific-schematics",
            "consciousness-council", "what-if-oracle", "scholar-evaluation",
            "market-research-reports", "research-grants", "research-lookup",
        ):
            category = "analysis"

        # Summary: first 500 chars of content (strip markdown headers)
        summary_text = re.sub(r'^#+\s+.*$', '', content, flags=re.MULTILINE).strip()
        summary = summary_text[:500] + ("..." if len(summary_text) > 500 else "")

        return Skill(
            name=name,
            description=description,
            license=license_str,
            category=category,
            content=content,
            summary=summary,
        )

    def list_skills(self, category: Optional[str] = None) -> List[Dict]:
        """Return skill metadata for API/UI listing."""
        self.load()
        result = []
        for skill in self._skills.values():
            if category and skill.category != category:
                continue
            result.append({
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "license": skill.license,
            })
        result.sort(key=lambda s: s["name"])
        return result

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        self.load()
        return self._skills.get(name)

    def get_skill_context(self, skill_names: List[str], max_chars: int = 3000) -> str:
        """
        Build a prompt context block from selected skills.
        Truncates each skill's content to fit within max_chars total.
        """
        self.load()
        if not skill_names:
            return ""

        skills = [self._skills[n] for n in skill_names if n in self._skills]
        if not skills:
            return ""

        per_skill = max_chars // len(skills)
        parts = []
        for s in skills:
            truncated = s.content[:per_skill]
            parts.append(f"## Skill: {s.name}\n{s.description}\n\n{truncated}")

        return "\n\n---\n\n".join(parts)

    @property
    def skill_count(self) -> int:
        self.load()
        return len(self._skills)

    def categories(self) -> Dict[str, int]:
        """Return category counts."""
        self.load()
        cats = {}
        for s in self._skills.values():
            cats[s.category] = cats.get(s.category, 0) + 1
        return cats
