# Deploying genie-nl2sql to Render (with Google login)

This deploys four things on Render:

| Component | Type | Public |
|---|---|---|
| genie-redis | Key Value (Redis) | no |
| genie-service | Private service | no |
| conversation-service | Web service (API) | yes |
| ui-app | Static site | yes |

The API is protected by **Google Sign-In**: the UI gets an ID token, the API
verifies it on every request. Optionally restrict to specific emails/domains.

---

## 0. Before you start

- **Rotate the Databricks PAT.** The old token was shared in plaintext — generate a
  new one in Databricks (User Settings → Developer → Access tokens) and use that below.
- Push this repo to **GitHub** (Render deploys from a Git repo).

---

## 1. Create a Google OAuth Client ID

1. Go to <https://console.cloud.google.com/apis/credentials>.
2. Create (or pick) a project → **Configure Consent Screen** (External is fine;
   add yourself as a test user if you keep it in "Testing").
3. **Create Credentials → OAuth client ID → Web application.**
4. Under **Authorized JavaScript origins**, add your UI URL. You won't know it until
   after step 2 below, so you can come back — it'll look like
   `https://ask-mits-ai.onrender.com` (Render assigns it). For local testing also add
   `http://localhost:5173`.
5. Copy the **Client ID** (looks like `xxxx.apps.googleusercontent.com`). You'll paste
   it into Render as both `GOOGLE_CLIENT_ID` (backend) and `VITE_GOOGLE_CLIENT_ID` (UI).

> No client secret is needed — the SPA uses the ID-token flow, verified server-side.

---

## 2. Deploy the Blueprint on Render

1. Create an account at <https://render.com> and connect your GitHub.
2. **New → Blueprint** → select this repo. Render reads [`render.yaml`](render.yaml)
   and proposes the 4 components.
3. Fill in the secrets it asks for (the `sync: false` vars):
   - **genie-service:** `DATABRICKS_HOST`, `DATABRICKS_TOKEN` (the rotated one),
     `GENIE_SPACE_ID`.
   - **conversation-service:** `GOOGLE_CLIENT_ID`, and optionally
     `GOOGLE_ALLOWED_DOMAINS` (e.g. `yourcompany.com`) and/or `GOOGLE_ALLOWED_EMAILS`
     (comma-separated). Leave both blank to allow any verified Google account.
   - **ui-app:** `VITE_GOOGLE_CLIENT_ID` (same client id).
4. Click **Apply**. Render builds and deploys. `REDIS_URL`, `GENIE_SERVICE_URL`, and
   `VITE_CONVERSATION_API` are wired automatically between services.

---

## 3. Finish the Google origin

Once Render gives the UI its URL (e.g. `https://ui-app-xxxx.onrender.com`):

1. Add that exact URL to **Authorized JavaScript origins** in the Google credential
   (step 1.4).
2. If your consent screen is in **Testing**, add users under **Audience → Test users**,
   or **Publish** the app.

Open the UI URL → **Sign in with Google** → ask a question.

---

## Access control

- **Allowlist by domain:** set `GOOGLE_ALLOWED_DOMAINS=yourcompany.com` → only
  `@yourcompany.com` accounts can use it.
- **Allowlist by email:** set `GOOGLE_ALLOWED_EMAILS=a@x.com,b@y.com`.
- Both blank → any Google account that passes the consent screen is allowed.
- A user who signs in but isn't allowed gets **403**.

---

## Notes & gotchas

- **CORS** is currently open (`*`). That's fine here because auth is a bearer token
  (no cookies). Lock it to the UI origin later if you want.
- **Free Redis / free tiers** on Render sleep/limit; use paid plans for always-on.
- **History is shared** across all signed-in users (no per-user partitioning yet). If
  you want each user to see only their own conversations, that's a follow-up: key the
  Redis index by `user.email`.
- **Local dev is unchanged:** with `GOOGLE_CLIENT_ID`/`VITE_GOOGLE_CLIENT_ID` blank,
  the login gate is skipped and everything works as before.
