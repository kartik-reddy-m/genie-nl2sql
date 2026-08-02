import { getToken, setToken } from "./auth.js";

let BASE = import.meta.env.VITE_CONVERSATION_API || "http://localhost:8000";
// Render's fromService provides a bare host (no scheme); make it absolute.
if (BASE && !/^https?:\/\//.test(BASE)) BASE = "https://" + BASE;

// The App registers a callback so it can force re-login when the token expires.
let onAuthExpired = null;
export function setOnAuthExpired(fn) {
  onAuthExpired = fn;
}

function authHeaders(extra = {}) {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function handle(res) {
  if (res.status === 401) {
    setToken("");
    if (onAuthExpired) onAuthExpired();
    throw new Error("Your session expired — please sign in again.");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(friendlyError(res.status, text));
  }
  return res.json();
}

// Turn raw server errors (JSON details, HTML 502 pages, rate limits) into
// short, human-friendly messages.
function friendlyError(status, text) {
  if (status === 429)
    return "The system is busy right now (too many requests). Please wait a few seconds and try again.";
  if (status === 502 || status === 503 || status === 504)
    return "The service is waking up. Please try again in a few seconds.";

  const t = (text || "").trim();
  if (t.startsWith("{")) {
    try {
      const detail = JSON.parse(t).detail;
      // Ignore nested HTML error pages; only surface short, clean details.
      if (
        typeof detail === "string" &&
        detail.trim() &&
        !detail.trim().startsWith("<") &&
        detail.length < 200
      ) {
        return detail;
      }
    } catch {
      /* not JSON */
    }
  }
  return `Something went wrong (error ${status}). Please try again.`;
}

// Both calls block until Genie has finished and return the fully-resolved
// answer: { conversation_id, message_id, status, done, answer_text, sql, result, error }

export async function startConversation(question) {
  const res = await fetch(`${BASE}/conversations`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ question }),
  });
  return handle(res);
}

export async function sendFollowUp(conversationId, question) {
  const res = await fetch(
    `${BASE}/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ question }),
    }
  );
  return handle(res);
}

// --- History ---

export async function listConversations() {
  const res = await fetch(`${BASE}/conversations`, { headers: authHeaders() });
  return handle(res);
}

export async function getConversation(conversationId) {
  const res = await fetch(`${BASE}/conversations/${conversationId}`, {
    headers: authHeaders(),
  });
  return handle(res);
}

export async function deleteConversation(conversationId) {
  const res = await fetch(`${BASE}/conversations/${conversationId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return handle(res);
}
