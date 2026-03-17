from __future__ import annotations

from abc import ABC
from typing import Any, Dict, List
import uuid


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


class TwitterAdapter(SocialPlatformAdapter):
    platform = "twitter"
    display_name = "Twitter/X"
    max_length = 280


class RedditAdapter(SocialPlatformAdapter):
    platform = "reddit"
    display_name = "Reddit"
    max_length = 40000


class YouTubeAdapter(SocialPlatformAdapter):
    platform = "youtube"
    display_name = "YouTube"
    max_length = 5000


class InstagramAdapter(SocialPlatformAdapter):
    platform = "instagram"
    display_name = "Instagram"
    max_length = 2200


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
