# Job Automation Prototype

This repository contains a first-draft implementation of an automated job evaluation and application platform. It is structured so you can iteratively plug in real job sources, refine scoring, and add Playwright-driven form submissions.

## Service Layout

- `app/` – FastAPI entrypoint plus database models and schemas.
- `services/` – The domain layer for résumé ingestion, job evaluation, and application automation.
- `data/` – Sample job data and storage buckets for uploaded résumés/questionnaires.
- `workers/` – Reserved for future schedulers/background tasks.

The API exposes endpoints to ingest résumé/questionnaire data, evaluate matching jobs, and enqueue application submissions (with a CAPTCHA backlog when automation must pause).

## Quickstart

### 1. Install dependencies

```bash
uv sync
```

### 2. Install Playwright browsers (once)

```bash
uv run playwright install chromium
```

### 3. Run the API locally

```bash
uv run uvicorn app.main:app --reload
```

The server defaults to `http://127.0.0.1:8000`.

### 4. Seed demo data (optional)

Send a résumé plus questionnaire payload for a test user:

```bash
curl -X POST http://127.0.0.1:8000/users/demo-user/resume \
    -H "Content-Type: application/json" \
    -d '{"content": "Experienced Python engineer with FastAPI, AWS, and Kubernetes expertise."}'
```

```bash
curl -X POST http://127.0.0.1:8000/users/demo-user/questionnaire \
    -H "Content-Type: application/json" \
    -d '{"answers": {"preferred_salary_min": 130000, "preferred_salary_max": 170000, "preferred_locations": ["remote"], "remote_ok": true, "culture_keywords": ["remote-first", "inclusive"]}}'
```

Trigger the evaluator:

```bash
curl -X POST http://127.0.0.1:8000/users/demo-user/evaluate \
    -H "Content-Type: application/json" \
    -d '{"max_results": 5}'
```

List matches:

```bash
curl http://127.0.0.1:8000/users/demo-user/jobs
```

Submit an application (will fall back to Playwright scaffold and potentially land in the captcha queue):

```bash
curl -X POST http://127.0.0.1:8000/users/demo-user/jobs/{job_id}/submit
```

Review captcha items:

```bash
curl http://127.0.0.1:8000/captcha
```

### 5. Build a container image (optional)

```bash
docker build -t job-automation .
docker run --rm -p 8000:8000 job-automation
```

## GitHub & Cloudflare Deployment Sketch

1. **Repository structure** – keep this backend in the main branch. Add a `frontend/` directory later for a Next.js UI (deployed to Cloudflare Pages).
2. **CI/CD** – use GitHub Actions to lint (`uv run ruff`), test (`uv run pytest`), and publish Docker images. See the sample workflow in `.github/workflows/backend.yaml` below.
3. **Runtime** – host the FastAPI service on a container-friendly platform (Fly.io, Render, or Cloudflare Workers with Python WASM if you trim dependencies). For Playwright, a container or VM is recommended.
4. **Secrets** – store API keys, database URLs, and queue credentials in GitHub secrets and replicate them in Cloudflare Pages/Workers secrets.

### Sample GitHub Actions workflow

Create `.github/workflows/backend.yaml`:

```yaml
name: backend

on:
  push:
    branches: [main]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          version: "latest"
      - name: Install dependencies
        run: uv sync --all-extras
      - name: Lint
        run: uv run ruff check .
      - name: Tests
        run: uv run pytest
      - name: Build container image
        run: docker build -t ghcr.io/${{ github.repository }}:latest .
      - name: Push image
        if: github.ref == 'refs/heads/main'
        run: |
          echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
          docker push ghcr.io/${{ github.repository }}:latest
```

### Cloudflare Pages / Workers

- **Frontend** – deploy a Next.js app via Cloudflare Pages. Build the questionnaire UI, dashboard, and webhook triggers to this API.
- **Backend** – host the FastAPI container on an external service (e.g., Fly.io). Expose HTTPS and secure with an API token. Alternatively, wrap the API with Cloudflare Tunnel for routing through your domain.
- **Edge glue** – add a Cloudflare Worker that handles authentication, rate limiting, and proxies requests from the Pages frontend to the backend API.

## Next Extensions

- Replace the sample job loader with real integrations (APIs first, then Playwright scrapers where terms allow).
- Expand the scoring model (embeddings, ML ranking).
- Implement background schedulers in `workers/` using Celery or APScheduler.
- Flesh out Playwright form maps per ATS and add storage for completed applications.
