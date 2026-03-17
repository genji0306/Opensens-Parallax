# Social AI Service

Flask microservice for publishing and scheduling social content across:

- Twitter/X
- Reddit
- YouTube
- Instagram

## Endpoints

- `GET /health`
- `POST /api/social/post`
- `POST /api/social/schedule`
- `GET /api/social/status`
- `GET /api/social/status/<job_id>`

## Run

```bash
python3 app.py
```

The service listens on port `5003` by default and stores job state in
`social-ai-service/data/social_ai.db`.
