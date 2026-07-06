# Genie NL2SQL

Ask natural-language questions in a web UI. The question is translated to SQL by
**Databricks Genie**, executed, and the resulting data is returned to the user.

## Architecture

```
┌────────────┐      ┌──────────────────────┐      ┌────────────────┐      ┌───────────────────┐
│  UI app    │ ───► │ conversation-service │ ───► │ genie-service  │ ───► │ Databricks Genie  │
│ (React)    │ ◄─── │   (FastAPI :8000)    │ ◄─── │ (FastAPI :8001)│ ◄─── │   REST API        │
│  :5173     │ poll └──────────────────────┘      └────────────────┘      └───────────────────┘
└────────────┘
```

Flow:

1. User types a question in the **UI**.
2. UI calls **conversation-service** to create a conversation (or send a follow-up).
3. conversation-service forwards the message to **genie-service**.
4. genie-service calls the **Databricks Genie REST API** (start conversation / send
   message / get message / get query result).
5. The UI **polls** conversation-service for the message status until the answer +
   data are ready, then renders the SQL and the result table.

## Services

| Service                | Port | Purpose                                                      |
|------------------------|------|--------------------------------------------------------------|
| `genie-service`        | 8001 | Thin, authenticated client for the Databricks Genie API.     |
| `conversation-service` | 8000 | Orchestration/API the UI talks to. Merges message + result.  |
| `ui-app`               | 5173 | React + Vite chat interface with polling.                    |

## Prerequisites

- Python 3.10+
- Node.js 18+
- A Databricks Genie space and a PAT token.

## Setup

### 1. genie-service

```bash
cd genie-service
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then edit .env with your real values
uvicorn app.main:app --reload --port 8001
```

### 2. conversation-service

```bash
cd conversation-service
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

### 3. ui-app

```bash
cd ui-app
npm install
copy .env.example .env
npm run dev
```

Open http://localhost:5173.

## Configuration

Secrets live in each service's `.env` (git-ignored). See each service's
`.env.example`. **Never commit real tokens.** If the token in your prompt was ever
shared, rotate it in Databricks.

## API (conversation-service — what the UI uses)

- `POST /conversations` `{ "question": "..." }` → `{ conversation_id, message_id, status }`
- `POST /conversations/{conversation_id}/messages` `{ "question": "..." }` → `{ message_id, status }`
- `GET  /conversations/{conversation_id}/messages/{message_id}` → message status; when
  complete, includes `answer_text`, `sql`, and `result` (`columns` + `rows`).
