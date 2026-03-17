from datetime import datetime, timedelta, timezone


def test_create_post_persists_published_job(client):
    response = client.post(
        "/api/social/post",
        json={
            "platform": "twitter",
            "content": "Launching the new OSSR ingestion pipeline today.",
            "author": "codex",
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["platform"] == "twitter"
    assert payload["data"]["state"] == "published"
    assert payload["data"]["platform_status"]["delivery_state"] == "published"


def test_schedule_requires_future_timestamp(client):
    response = client.post(
        "/api/social/schedule",
        json={
            "platform": "reddit",
            "content": "This should fail because the time is in the past.",
            "scheduled_for": "2020-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert "future" in payload["error"]


def test_status_endpoints_return_scheduled_job(client):
    scheduled_for = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    create_response = client.post(
        "/api/social/schedule",
        json={
            "platform": "instagram",
            "content": "Scheduled update for the research simulation launch.",
            "scheduled_for": scheduled_for,
            "media_urls": ["https://example.com/launch.png"],
        },
    )

    assert create_response.status_code == 202
    job = create_response.get_json()["data"]

    list_response = client.get("/api/social/status?platform=instagram")
    assert list_response.status_code == 200
    listed_jobs = list_response.get_json()["data"]
    assert len(listed_jobs) == 1
    assert listed_jobs[0]["job_id"] == job["job_id"]

    detail_response = client.get(f"/api/social/status/{job['job_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.get_json()["data"]
    assert detail["state"] == "scheduled"
    assert detail["platform_status"]["delivery_state"] == "scheduled"
