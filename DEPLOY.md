# Deploying genie-nl2sql to Render (free tier, Google login)

Four resources, all on Render's **free** tier:

| Resource | Type | Public | Notes |
|---|---|---|---|
| genie-redis | Key Value (Redis) | no | conversation history |
| genie-service | Web service | yes* | *public but guarded by a shared `INTERNAL_API_KEY` |
| conversation-service | Web service | yes | the API the UI calls; Google-auth protected |
| ui-app | Static site | yes | the site you share |

> Free web services **sleep after ~15 min idle**; the first request then takes
> ~30–60s to wake. See "Cold starts & the 502" at the bottom.

---

## Prerequisites

1. **Repo on GitHub** — already at `github.com/kartik-reddy-m/genie-nl2sql`.
2. **Rotated Databricks PAT** — Databricks → avatar → Settings → Developer →
   Access tokens → Generate. Keep the new `dapi…` value.
3. **Google OAuth Client ID** — already created:
   `195671407876-1nld8enmuj6hp09ojq8qc5g74g4dm01v.apps.googleusercontent.com`
   (Google Cloud Console → APIs & Services → Credentials → Web application client.)

---

## Step 1 — Create the Blueprint

1. Render → **New +** → **Blueprint** → pick `kartik-reddy-m/genie-nl2sql`.
2. Render reads `render.yaml` and lists the 4 resources + the `internal-auth` env
   group. It should show **no charge** (all free).
3. Fill the secret env vars it prompts for:

   **genie-service**
   | Key | Value |
   |---|---|
   | `DATABRICKS_HOST` | `https://dbc-fcb3311b-2b4b.cloud.databricks.com` |
   | `DATABRICKS_TOKEN` | *your rotated `dapi…` token* |
   | `GENIE_SPACE_ID` | `01f178e8f2751f9e8e896570d7d6e289` |

   **conversation-service**
   | Key | Value |
   |---|---|
   | `GOOGLE_CLIENT_ID` | `195671407876-1nld8enmuj6hp09ojq8qc5g74g4dm01v.apps.googleusercontent.com` |
   | `GENIE_SERVICE_URL` | *leave blank for now — set in Step 2* |
   | `GOOGLE_ALLOWED_DOMAINS` / `GOOGLE_ALLOWED_EMAILS` | *optional allowlist* |

   **ui-app**
   | Key | Value |
   |---|---|
   | `VITE_GOOGLE_CLIENT_ID` | `195671407876-1nld8enmuj6hp09ojq8qc5g74g4dm01v.apps.googleusercontent.com` |
   | `VITE_CONVERSATION_API` | *leave blank for now — set in Step 2* |

   > `INTERNAL_API_KEY` is generated automatically and shared by both backends —
   > don't set it.

4. **Apply.** Wait for all resources to be created (each backend gets a public
   `*.onrender.com` URL).

---

## Step 2 — Wire the cross-service URLs (THE critical step)

Render's blueprint can't auto-fill one service's **public** URL into another, so you
set these two by hand **after** the services exist. Skipping this is what caused the
`Failed to fetch` / `502` errors.

1. Copy the two public URLs from their Render pages:
   - **genie-service** → e.g. `https://genie-service-xxxx.onrender.com`
   - **conversation-service** → e.g. `https://conversation-service-xxxx.onrender.com`

2. **conversation-service → Environment →** set
   `GENIE_SERVICE_URL = https://genie-service-xxxx.onrender.com`
   → **Save** (auto-redeploys; backends read env at startup, so no cache clear needed).

3. **ui-app → Environment →** set
   `VITE_CONVERSATION_API = https://conversation-service-xxxx.onrender.com`
   → **Save**, then **Manual Deploy → "Clear build cache & deploy"**.
   > The API URL is compiled **into** the static build, so the UI **must rebuild**.
   > Saving alone does nothing until it rebuilds.

Full https, **no trailing slash**, no `/docs` or `/health` suffix.

---

## Step 3 — Register the UI origin with Google

Without this you get `Access blocked … no registered origin (401 invalid_client)`.

1. Copy the **ui-app** public URL, e.g. `https://ui-app-xxxx.onrender.com`.
2. Google Cloud Console → **APIs & Services → Credentials** → click the OAuth client.
3. **Authorized JavaScript origins → + Add URI** → paste the ui-app origin
   (`https://ui-app-xxxx.onrender.com`, no path, no trailing slash) → **Save**.
4. **Wait ~5 minutes** for Google to propagate.
5. If the **OAuth consent screen** is in **Testing**, add your Google email under
   **Audience → Test users** (else Google blocks non-test users).

---

## Step 4 — Test

1. Open the **ui-app** URL, hard-refresh (Ctrl+Shift+R), **Sign in with Google**.
2. Ask a question.

If it works, share the **ui-app** URL with others.

---

## Verifying / debugging (curl)

```bash
# backends healthy?
curl https://conversation-service-xxxx.onrender.com/health   # {"redis":true,"auth_enabled":true,...}
curl https://genie-service-xxxx.onrender.com/health          # {"service":"genie-service",...}

# CORS preflight (should return access-control-allow-origin: *)
curl -i -X OPTIONS https://conversation-service-xxxx.onrender.com/conversations \
  -H "Origin: https://ui-app-xxxx.onrender.com" \
  -H "Access-Control-Request-Method: POST"
```

| Symptom | Cause | Fix |
|---|---|---|
| `Failed to fetch` / `ERR_NAME_NOT_RESOLVED` | `VITE_CONVERSATION_API` wrong / UI not rebuilt | Step 2.3, then Clear-cache deploy |
| CORS: `No Access-Control-Allow-Origin` | service **restarting/asleep** (Render edge error page) | wait for "Live", retry |
| `502 Could not reach genie-service … Name or service not known` | `GENIE_SERVICE_URL` wrong | Step 2.2 |
| `Access blocked … no registered origin` | UI origin not in Google | Step 3 |
| Bare `502 Bad Gateway` on a question | cold start + long query > Render timeout | see below |

---

## Cold starts & the 502 (important)

conversation-service answers a question by holding **one request open** while it
wakes genie-service and waits for Databricks (up to ~150s). On the free tier, if
genie-service was asleep, that combined time can exceed Render's proxy timeout →
a bare **502 Bad Gateway**.

Workarounds, easiest first:
1. **Warm the services** before asking: open each backend's `/health` once (or hit
   the curl commands above) so neither is cold, then ask in the UI.
2. **Keep them awake** with an external uptime pinger (e.g. a cron hitting `/health`
   every 10 min), or upgrade the two backends off free.
3. **Robust fix (code change):** switch conversation-service back to returning a
   `message_id` immediately and have the UI **poll** for the result — no long-held
   request, immune to edge timeouts. Ask and I'll implement it.

---

## Notes

- **CORS** is open (`*`) — fine here (bearer-token auth, no cookies). Lock to the
  ui-app origin later if desired.
- **History is per-user** (keyed by Google email); users only see their own.
- **Local dev** is unaffected: with `GOOGLE_CLIENT_ID`/`VITE_GOOGLE_CLIENT_ID`
  blank, login is skipped and it runs via Docker Compose (`docker compose up -d`).
- After code changes: `git push` → Render auto-deploys (if enabled) or use
  **Manual Deploy**. Static-site (ui-app) changes to env vars need a rebuild.
