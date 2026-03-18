from __future__ import annotations

from abc import ABC
from typing import Any, Dict, List
import logging
import os
import uuid

logger = logging.getLogger(__name__)


class SocialPlatformAdapter(ABC):
    platform = ""
    display_name = ""
    max_length = 0
    supports_media = True
    supports_scheduling = True

    def normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        content = (payload.get("content") or "").strip()
        if not content:
            raise ValueError("content is required")
        if self.max_length and len(content) > self.max_length:
            raise ValueError(f"content exceeds {self.max_length} characters for {self.display_name}")

        media_urls = payload.get("media_urls") or []
        if not isinstance(media_urls, list):
            raise ValueError("media_urls must be a list")
        if media_urls and not self.supports_media:
            raise ValueError(f"{self.display_name} adapter does not support media_urls")

        return {
            "platform": self.platform,
            "content": content,
            "author": (payload.get("author") or "system").strip() or "system",
            "media_urls": media_urls,
            "metadata": payload.get("metadata") or {},
        }

    def publish(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self.normalize_payload(payload)
        normalized["external_id"] = f"{self.platform}-{uuid.uuid4().hex[:12]}"
        normalized["platform_status"] = "published"
        normalized["adapter"] = self.adapter_summary()
        return normalized

    def schedule(self, payload: Dict[str, Any], scheduled_for: str) -> Dict[str, Any]:
        normalized = self.normalize_payload(payload)
        normalized["scheduled_for"] = scheduled_for
        normalized["external_id"] = f"{self.platform}-scheduled-{uuid.uuid4().hex[:12]}"
        normalized["platform_status"] = "scheduled"
        normalized["adapter"] = self.adapter_summary()
        return normalized

    def status(self, job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "external_id": job.get("external_id"),
            "delivery_state": job.get("state"),
            "supports_media": self.supports_media,
            "supports_scheduling": self.supports_scheduling,
        }

    def adapter_summary(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "max_length": self.max_length,
            "supports_media": self.supports_media,
            "supports_scheduling": self.supports_scheduling,
        }

    def generate_content(
        self,
        transcript_summary: str,
        agent_name: str,
        agent_role: str,
        topic: str,
    ) -> Dict[str, Any]:
        """Generate platform-specific content from simulation data. Override per platform."""
        content = transcript_summary[:self.max_length] if self.max_length else transcript_summary
        return {
            "platform": self.platform,
            "content": content,
            "title": None,
            "hashtags": [],
            "char_count": len(content),
            "max_length": self.max_length,
        }


class TwitterAdapter(SocialPlatformAdapter):
    platform = "twitter"
    display_name = "Twitter/X"
    max_length = 280

    def generate_content(self, transcript_summary, agent_name, agent_role, topic):
        tag = topic.replace(" ", "").replace("-", "")[:20]
        hashtags = [f"#{tag}", "#AcademicResearch", "#OSSR"]
        tag_str = " ".join(hashtags)
        # Reserve space for hashtags
        max_body = 280 - len(tag_str) - 1
        # Build body: "Agent on topic: key insight..."
        prefix = f"{agent_name} ({agent_role}) on {topic}: "
        body = prefix + transcript_summary
        if len(body) > max_body:
            body = body[: max_body - 3] + "..."
        content = f"{body} {tag_str}"
        return {
            "platform": self.platform,
            "content": content,
            "title": None,
            "hashtags": hashtags,
            "char_count": len(content),
            "max_length": self.max_length,
        }


class RedditAdapter(SocialPlatformAdapter):
    """
    Reddit adapter with optional real PRAW integration.
    Set env vars to enable real posting:
      REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME,
      REDDIT_PASSWORD, REDDIT_USER_AGENT (optional)
    Without these, publish() returns a mock external_id (stub mode).
    """
    platform = "reddit"
    display_name = "Reddit"
    max_length = 40000

    def _get_praw_client(self):
        """Return a praw.Reddit instance if credentials are configured, else None."""
        client_id = os.environ.get("REDDIT_CLIENT_ID")
        client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
        username = os.environ.get("REDDIT_USERNAME")
        password = os.environ.get("REDDIT_PASSWORD")
        if not all([client_id, client_secret, username, password]):
            return None
        try:
            import praw
            return praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                username=username,
                password=password,
                user_agent=os.environ.get("REDDIT_USER_AGENT", "OSSR-SocialAI/1.0"),
            )
        except ImportError:
            logger.warning("praw not installed — Reddit adapter running in stub mode")
            return None

    def publish(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self.normalize_payload(payload)
        subreddit_name = (payload.get("metadata") or {}).get("subreddit", "test")
        title = payload.get("title") or normalized["content"][:200]

        reddit = self._get_praw_client()
        if reddit:
            try:
                subreddit = reddit.subreddit(subreddit_name)
                submission = subreddit.submit(
                    title=title,
                    selftext=normalized["content"],
                    flair_id=payload.get("metadata", {}).get("flair_id"),
                )
                normalized["external_id"] = f"reddit-{submission.id}"
                normalized["platform_status"] = "published"
                normalized["url"] = f"https://reddit.com{submission.permalink}"
                logger.info("Published to r/%s: %s", subreddit_name, submission.id)
            except Exception as e:
                logger.error("Reddit publish failed: %s", e)
                normalized["external_id"] = f"reddit-failed-{uuid.uuid4().hex[:12]}"
                normalized["platform_status"] = "failed"
                normalized["error"] = str(e)
        else:
            normalized["external_id"] = f"reddit-stub-{uuid.uuid4().hex[:12]}"
            normalized["platform_status"] = "published"

        normalized["adapter"] = self.adapter_summary()
        return normalized

    def generate_content(self, transcript_summary, agent_name, agent_role, topic):
        title = f"[OSSR Research] {agent_name} on {topic}"
        if len(title) > 300:
            title = title[:297] + "..."

        sentences = [s.strip() for s in transcript_summary.split(".") if s.strip()]
        key_findings = sentences[:3]
        remaining = ". ".join(sentences[3:]) if len(sentences) > 3 else ""

        body_parts = [
            f"**Topic:** {topic}\n",
            f"**Researcher:** {agent_name} ({agent_role})\n",
            "---\n",
            "## Key Findings\n",
        ]
        for i, finding in enumerate(key_findings, 1):
            body_parts.append(f"{i}. {finding}.\n")
        if remaining:
            body_parts.append(f"\n## Discussion\n\n{remaining}.\n")
        body_parts.append("\n---\n*Generated by OSSR — Opensens Social-network Simulation for Research*")

        content = "\n".join(body_parts)
        return {
            "platform": self.platform,
            "content": content,
            "title": title,
            "hashtags": [],
            "char_count": len(content),
            "max_length": self.max_length,
        }


class YouTubeAdapter(SocialPlatformAdapter):
    platform = "youtube"
    display_name = "YouTube"
    max_length = 5000

    def generate_content(self, transcript_summary, agent_name, agent_role, topic):
        title = f"{topic} — Research Discussion with {agent_name}"
        if len(title) > 100:
            title = title[:97] + "..."

        content = (
            f"{agent_name} ({agent_role}) discusses {topic}.\n\n"
            f"{transcript_summary}\n\n"
            f"Timestamps:\n"
            f"0:00 — Introduction\n"
            f"0:30 — Key findings\n"
            f"2:00 — Discussion & implications\n\n"
            f"Generated by OSSR — Opensens Social-network Simulation for Research\n"
            f"#Research #{topic.replace(' ', '')} #AcademicDiscourse"
        )
        return {
            "platform": self.platform,
            "content": content[:self.max_length],
            "title": title,
            "hashtags": [f"#{topic.replace(' ', '')}", "#Research", "#AcademicDiscourse"],
            "char_count": len(content),
            "max_length": self.max_length,
        }


class InstagramAdapter(SocialPlatformAdapter):
    platform = "instagram"
    display_name = "Instagram"
    max_length = 2200

    def generate_content(self, transcript_summary, agent_name, agent_role, topic):
        tag = topic.replace(" ", "").replace("-", "")[:25]
        hashtags = [f"#{tag}", "#Research", "#Science", "#AcademicLife", "#OSSR"]

        body = (
            f"Research spotlight: {topic}\n\n"
            f"{agent_name} ({agent_role}) shares key insights:\n\n"
            f"{transcript_summary}\n\n"
        )
        tag_str = " ".join(hashtags)
        max_body = self.max_length - len(tag_str) - 1
        if len(body) > max_body:
            body = body[: max_body - 3] + "..."

        content = f"{body}{tag_str}"
        return {
            "platform": self.platform,
            "content": content,
            "title": None,
            "hashtags": hashtags,
            "char_count": len(content),
            "max_length": self.max_length,
        }


ADAPTERS = {
    "twitter": TwitterAdapter,
    "x": TwitterAdapter,
    "reddit": RedditAdapter,
    "youtube": YouTubeAdapter,
    "instagram": InstagramAdapter,
}


def get_adapter(platform: str) -> SocialPlatformAdapter:
    key = (platform or "").strip().lower()
    adapter_cls = ADAPTERS.get(key)
    if not adapter_cls:
        supported = ", ".join(sorted(list_supported_platforms()))
        raise ValueError(f"unsupported platform '{platform}'. Supported platforms: {supported}")
    return adapter_cls()


def list_supported_platforms() -> List[str]:
    canonical_names = []
    for adapter_cls in ADAPTERS.values():
        if adapter_cls.platform not in canonical_names:
            canonical_names.append(adapter_cls.platform)
    return canonical_names
