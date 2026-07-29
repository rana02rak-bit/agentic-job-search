# RahulGPT — Agentic Job Search

RahulGPT is a local-first job intelligence workspace. The current build provides a usable company
watchlist, five-factor company scoring, AI-assisted company suggestions, verified job ingestion
from public ATS boards, and a dashboard. Manual watchlist and ATS discovery work without an OpenAI
API key.

## Current features

- Add, reprioritize, and remove target companies.
- Keep user-added companies as a first-class watchlist.
- Store companies, jobs, recruiters, and discovery runs in PostgreSQL.
- Score companies across funding, hiring, AI relevance, location, and role match (50 points).
- Generate structured AI suggestions using the OpenAI Responses API.
- Connect watchlist companies to Greenhouse, Lever, or Ashby job boards.
- Import only Rahul's target roles and locations, with external-ID and URL deduplication.
- Keep discovery run history and isolate failures to the affected company source.
- Run ATS discovery automatically each day at 08:00 Asia/Kolkata.
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
a currently open role. The separate **Sync live jobs** action reads verified public job-board APIs.

## Connect a company job board

Add the company to the watchlist, open **Connect ATS job board** on its card, and choose the
provider. The board slug is the company identifier in the public careers URL:

- Greenhouse: `boards.greenhouse.io/{slug}`
- Lever: `jobs.lever.co/{slug}`
- Ashby: `jobs.ashbyhq.com/{slug}`

Saving a source does not invent jobs or call AI. **Sync live jobs** reads the public board, retains
roles matching the configured profile, and skips roles already seen on an earlier run.

The current filters include Product Management, Chief of Staff, Founder's Office, Strategy, and
Growth roles in Bangalore/Bengaluru, Gurgaon/Gurugram, Mumbai, Remote, or India.

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
| `PUT` | `/api/companies/{id}/ats-source` | Connect or update a public ATS board |
| `DELETE` | `/api/companies/{id}/ats-source` | Disable an ATS board |
| `POST` | `/api/discovery/sync` | Import matching live jobs |
| `GET` | `/api/discovery/runs` | Read discovery run history |
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

## Product objective and progress

The objective is a daily job-search operating system: discover verified roles, rank companies and
jobs against Rahul's profile, identify the right recruiter or hiring manager, draft unique
outreach, and track the funnel while keeping LinkedIn sending behind manual approval.

Completed: local product foundation, PostgreSQL schema, watchlist, initial company scoring,
AI company suggestions, dashboard, and public ATS job ingestion.

Next:

1. Resume ingestion and job-level match scoring based on Rahul's updated experience.
2. Recruiter and hiring-manager research with reply-probability scoring.
3. Approval-first personalized outreach queue.
4. Reply, referral, and interview tracking.
