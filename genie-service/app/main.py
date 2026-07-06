"""genie-service — authenticated proxy in front of the Databricks Genie API.

Only this service holds the Databricks PAT. The conversation-service calls these
endpoints; it never talks to Databricks directly.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .genie_client import GenieClient, GenieError
from .models import ProcessRequest

app = FastAPI(title="genie-service", version="1.0.0")

# In dev, conversation-service calls this over HTTP; allow local origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = GenieClient()


@app.on_event("startup")
async def _startup() -> None:
    get_settings().validate()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "genie-service"}


def _handle(exc: GenieError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@app.post("/genie/process-message")
async def process_message(body: ProcessRequest) -> dict:
    """Single operation: submit the question (start or follow-up), wait for Genie
    to finish, fetch the query result, and return the normalized answer."""
    try:
        return await client.process_message(body.content, body.conversation_id)
    except GenieError as exc:
        raise _handle(exc)
