# RahulGPT — Agentic Job Search

RahulGPT is a local-first job-search operating system. It finds and scores target companies,
imports verified jobs, searches LinkedIn for relevant people, creates job-specific messages with
Gemini or OpenAI, and sends only drafts Rahul explicitly approves.

## Product objective and current progress

The objective is:

```text
Auto-pick companies → find live jobs → find relevant people → shortlist
→ AI draft → Rahul reviews → Rahul approves → ConnectSafely sends
→ track sent messages and replies
```

Working now:

- PostgreSQL storage for companies, jobs, people, shortlists, messages, and discovery runs.
- Manual target-company watchlist plus AI company suggestions and five-factor scoring.
- Greenhouse, Lever, and Ashby job ingestion with role/location filtering and deduplication.
- Daily ATS sync at 08:00 Asia/Kolkata.
- ConnectSafely LinkedIn people search by target company and job.
- Reply-probability scoring and job-specific shortlisting.
- Non-template LinkedIn drafts based on Rahul's resume, job, and recipient.
- Preview, edit, explicit approval, ConnectSafely delivery, and reply tracking.
- A hard local limit of 100 LinkedIn sends per day.

Not yet included: automatic reply detection, referral/interview objects, and cloud deployment.

## Security: rotate the pasted keys first

Any API key pasted into chat must be considered exposed. Regenerate the selected AI-provider key
and the ConnectSafely key before using this app. Never commit `.env`.

The app supports Gemini and OpenAI Platform keys. `AI_PROVIDER=auto` chooses Gemini first when both
exist; the terminal configurator writes an explicit provider. Gemini uses the current stable
`gemini-3.6-flash` model; rerunning the configurator migrates older local model settings.

## Configure entirely from Terminal

Prerequisite: Docker Desktop is open and running.

From the repository root:

```bash
bash scripts/configure-local.sh
```

The script asks for both fresh keys without showing them on screen, writes `.env`, and restricts the
file to your user account. It configures:

```dotenv
AI_PROVIDER=openai
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.6-flash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-sol
CONNECTSAFELY_API_KEY=
CONNECTSAFELY_ACCOUNT_ID=
OUTREACH_DAILY_SEND_LIMIT=100
```

`CONNECTSAFELY_ACCOUNT_ID` is optional when the ConnectSafely workspace has one default LinkedIn
account. If it has multiple accounts, add the desired account ID to `.env`.

The MCP URL and the REST API use the same ConnectSafely credential. This application uses the
server-side REST API because it is the provider's recommended production integration and keeps the
secret out of the browser.

## Connect LinkedIn

In the ConnectSafely dashboard, connect the LinkedIn account that will send messages. The app checks
`GET /linkedin/account/status`; a valid API key alone is not enough if no LinkedIn account is
connected.

Normal DMs generally require a first-degree connection. Messages to non-connections can require
InMail/Premium access. The provider decides the available channel when the approved message is
sent.

## Run the app

```bash
docker compose up --build
```

Open:

- Dashboard: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Backend health: <http://localhost:8000/health>

See live backend progress and provider errors:

```bash
docker compose logs -f backend
```

In a second terminal, seed the initial watchlist if needed:

```bash
docker compose run --rm backend python -m app.seed
```

## Daily workflow

1. Use **Discover with AI** to auto-pick companies or add a firm manually.
2. Connect the firm's Greenhouse, Lever, or Ashby board and run **Sync live jobs**.
3. In **People intelligence**, select a company and optional job, then choose
   **Find recruiters and managers**.
4. Review the people found and shortlist someone against a job.
5. Save Rahul's updated resume/profile once.
6. Generate a unique draft and edit it.
7. Click **Approve & send LinkedIn DM**. This is the final confirmation and send action.

All sends are audited in PostgreSQL. The app reserves a send slot before calling ConnectSafely and
will not exceed 100 sends in the configured local day.

## Connect a company job board

Open **Connect ATS job board** on a company card and choose the provider. The slug is the identifier
in the public careers URL:

- Greenhouse: `boards.greenhouse.io/{slug}`
- Lever: `jobs.lever.co/{slug}`
- Ashby: `jobs.ashbyhq.com/{slug}`

The filters cover Product Management, Chief of Staff, Founder's Office, Strategy, and Growth roles
in Bangalore/Bengaluru, Gurgaon/Gurugram, Mumbai, Remote, or India.

## ATS certificate errors

The backend image installs public root certificates. On a company network that performs TLS
inspection, export the approved company root certificate to
`backend/certs/company-root-ca.pem`, set:

```dotenv
ATS_CA_BUNDLE=/app/certs/company-root-ca.pem
OUTBOUND_CA_BUNDLE=/app/certs/company-root-ca.pem
```

`ATS_CA_BUNDLE` covers job-board sync. `OUTBOUND_CA_BUNDLE` covers ConnectSafely. If only
`ATS_CA_BUNDLE` is present, ConnectSafely reuses it for backward compatibility.

If the company network requires an explicit proxy, also set `HTTPS_PROXY` in `.env`. Then rebuild.
Do not disable TLS verification.

## API overview

| Method | Path | Purpose |
|---|---|---|
| `GET/POST` | `/api/companies` | List or add target companies |
| `PATCH` | `/api/companies/{id}` | Change priority/watchlist state |
| `POST` | `/api/discovery/suggest` | Generate scored AI company suggestions |
| `POST` | `/api/discovery/sync` | Import matching live ATS jobs |
| `POST` | `/api/recruiters/discover` | Find people with ConnectSafely |
| `GET/POST` | `/api/recruiters` | List or manually add people |
| `POST` | `/api/recruiters/{id}/shortlist` | Shortlist a person for a job |
| `GET` | `/api/integrations/status` | Check AI-provider and LinkedIn readiness |
| `PUT` | `/api/outreach/profile` | Save Rahul's resume profile |
| `POST` | `/api/outreach/messages` | Generate a personalized DM |
| `PATCH` | `/api/outreach/messages/{id}` | Edit a draft |
| `POST` | `/api/outreach/messages/{id}/approve` | Approve without sending |
| `POST` | `/api/outreach/messages/{id}/send` | Send an approved DM |
| `GET` | `/api/outreach/capabilities` | Read provider health and daily usage |
| `GET` | `/api/dashboard/stats` | Read dashboard totals |

## Tests

```bash
docker compose run --rm backend pytest
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run build
```
