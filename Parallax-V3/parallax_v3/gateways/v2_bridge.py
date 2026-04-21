"""HTTP bridge to the V2 Flask API."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..errors import ParallaxV3Error


class V2BridgeError(ParallaxV3Error):
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.body = body
        super().__init__(f"V2 bridge request failed with {status_code}: {body}")


@dataclass
class V2Bridge:
    base_url: str = field(default_factory=lambda: os.environ.get("V2_API_URL", "http://localhost:5002"))

    async def _request(self, method: str, path: str, json_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
            response = await client.request(method, path, json=json_payload)
        try:
            body = response.json()
        except Exception:
            body = response.text
        if not 200 <= response.status_code < 300:
            raise V2BridgeError(response.status_code, body)
        if isinstance(body, dict) and body.get("success") is False:
            raise V2BridgeError(response.status_code, body)
        if isinstance(body, dict) and "data" in body:
            return body["data"]
        return body if isinstance(body, dict) else {"data": body}

    async def get_run_status(self, run_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/research/ais/{run_id}/status")

    async def get_stage_result(self, run_id: str, stage: str) -> dict[str, Any]:
        payload = await self.get_run_status(run_id)
        stage_results = payload.get("stage_results", {}) if isinstance(payload, dict) else {}
        result = stage_results.get(stage, {}) if isinstance(stage_results, dict) else {}
        return result if isinstance(result, dict) else {"data": result}

    async def post_execute_node(self, run_id: str, node_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/api/research/ais/{run_id}/execute/{node_id}", json_payload={})
