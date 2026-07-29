# RahulGPT — Agentic Job Search

RahulGPT is a local-first job intelligence workspace. Sprint 1 provides a usable company
watchlist, five-factor company scoring, AI-assisted company suggestions, job storage, and a
dashboard. Manual watchlist features work without an OpenAI API key.

## Sprint 1 features

- Add, reprioritize, and remove target companies.
- Keep user-added companies as a first-class watchlist.
- Store companies, jobs, recruiters, and discovery runs in PostgreSQL.
- Score companies across funding, hiring, AI relevance, location, and role match (50 points).
- Generate structured AI suggestions using the OpenAI Responses API.
- Show the current pipeline in a responsive Next.js dashboard.
- Run the full stack locally with Docker Compose.

The application does **not** automate LinkedIn messages. Later outreach modules will prepare a
draft and stop at the approval/send boundary.

## Quick start

Prerequisites: Docker Desktop with Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Dashboard: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

In another terminal, seed the initial watchlist:

```bash
docker compose run --rm backend python -m app.seed
```

## OpenAI configuration

Create a new OpenAI Platform API key and set it only in your local `.env`:

```dotenv
OPENAI_API_KEY=your_new_key
OPENAI_MODEL=gpt-5.6-luna
```

Never commit `.env` or paste API keys into chat. The previously shared `AIza...` credential is a
Google API key, not an OpenAI API key, and should be revoked or restricted in Google Cloud.

AI suggestions are generated as candidates for verification. They do not claim that a company has
a currently open role; live job discovery will come from verified ATS and company-careers sources.

## API overview

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/companies` | List companies |
| `POST` | `/api/companies` | Add a target company |
| `PATCH` | `/api/companies/{id}` | Change priority/watchlist state |
| `DELETE` | `/api/companies/{id}` | Remove from watchlist |
| `GET` | `/api/jobs` | List stored jobs |
| `POST` | `/api/jobs` | Store a job |
| `POST` | `/api/discovery/suggest` | Generate scored AI suggestions |
| `GET` | `/api/dashboard/stats` | Read dashboard totals |

## Tests

With Docker:

```bash
docker compose run --rm backend pytest
```

For a lightweight local check without installing the runtime stack:

```bash
cd backend
python -m unittest discover -s tests
python -m compileall app tests
```

## Architecture

```text
agentic-job-search/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   └── services/
│   └── tests/
├── frontend/
│   ├── app/
│   ├── components/
│   └── lib/
└── docker-compose.yml
```

## Next build

1. ATS discovery adapters for Greenhouse, Lever, Ashby, and selected company career pages.
2. Scheduled daily discovery with run history and source-level failure reporting.
3. Resume ingestion and role-match scoring based on Rahul's updated experience.
4. Recruiter discovery and reply-probability scoring.
5. Approval-first personalized outreach queue.

